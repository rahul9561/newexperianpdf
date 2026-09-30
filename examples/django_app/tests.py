"""Tests for the Experian PDF view, services and task.

Run from the examples/ folder:  python runtests.py
In your own project:            python manage.py test django_app
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from experian_pdf import InvalidReportError, RenderError

from . import services, tasks

DUMMY_REPORT = json.loads(
    (Path(__file__).resolve().parent / "test_data" / "dummy_experian.json").read_text(encoding="utf-8"))


class ExperianPdfViewTests(TestCase):
    def setUp(self):
        self.url = reverse("experian_pdf:pdf")

    def post(self, body, content_type="application/json", client=None):
        return (client or self.client).post(self.url, data=body, content_type=content_type)

    # ---------------------------------------------------------------- success

    def test_url(self):
        self.assertEqual(self.url, "/experian/pdf/")

    def test_valid_report_returns_pdf(self):
        response = self.post(json.dumps(DUMMY_REPORT))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 10_000)

    def test_pdf_headers(self):
        response = self.post(json.dumps(DUMMY_REPORT))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="experian_report.pdf"')
        self.assertEqual(response["Content-Length"], str(len(response.content)))
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_orm_still_usable_after_rendering(self):
        """Regression: Playwright's sync API must not leave an event loop in the request thread."""
        from django.contrib.contenttypes.models import ContentType

        for renderer in ("chromium", "weasyprint", "auto"):
            with self.settings(EXPERIAN_PDF_RENDERER=renderer):
                self.assertEqual(self.post(json.dumps(DUMMY_REPORT)).status_code, 200)
            self.assertGreaterEqual(ContentType.objects.count(), 0)  # raises if an event loop runs here

    def test_csrf_exempt_for_api_clients(self):
        response = self.post(json.dumps(DUMMY_REPORT), client=Client(enforce_csrf_checks=True))
        self.assertEqual(response.status_code, 200)

    def test_passes_parsed_json_to_service(self):
        with mock.patch("django_app.views.build_experian_pdf", return_value=b"%PDF-1.7 fake") as build:
            response = self.post(json.dumps(DUMMY_REPORT))
        build.assert_called_once_with(DUMMY_REPORT)
        self.assertEqual(response.content, b"%PDF-1.7 fake")

    # ---------------------------------------------------------------- 400

    def test_empty_body_returns_400(self):
        for body in ["", "   "]:
            response = self.post(body)
            self.assertEqual(response.status_code, 400)
            self.assertIn("empty", response.json()["error"].lower())

    def test_invalid_json_returns_400(self):
        for body in ["{not json", "{'single': 'quotes'}", '{"a": 1,}']:
            response = self.post(body)
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertIn("Invalid JSON", response.json()["error"])

    def test_non_utf8_body_returns_400(self):
        response = self.post(b"\xff\xfe\xfa", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    # ---------------------------------------------------------------- 422

    def test_missing_inprofileresponse_returns_422(self):
        response = self.post(json.dumps({"status": True, "data": {"result": {"result_json": {}}}}))
        self.assertEqual(response.status_code, 422)
        self.assertIn("INProfileResponse", response.json()["error"])

    def test_json_that_is_not_an_object_returns_422(self):
        for body in ["[]", "42", '"text"', "null"]:
            response = self.post(body)
            self.assertEqual(response.status_code, 422, body)
            self.assertIn("error", response.json())

    def test_invalid_report_error_message_is_returned(self):
        with mock.patch("django_app.views.build_experian_pdf",
                        side_effect=InvalidReportError("No 'INProfileResponse' found in input")):
            response = self.post(json.dumps({"x": 1}))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error": "No 'INProfileResponse' found in input"})

    # ---------------------------------------------------------------- 500

    def test_engine_exception_returns_500_and_is_logged(self):
        with mock.patch("django_app.views.build_experian_pdf", side_effect=RuntimeError("boom")), \
                self.assertLogs("django_app.views", level="ERROR") as logs:
            response = self.post(json.dumps(DUMMY_REPORT))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Could not generate the PDF report."})
        self.assertNotIn("boom", response.content.decode())  # internals are not leaked
        self.assertIn("Experian PDF generation failed", logs.output[0])
        self.assertIn("RuntimeError: boom", "\n".join(logs.output))

    def test_render_error_returns_500(self):
        with mock.patch("django_app.views.build_experian_pdf", side_effect=RenderError("renderer died")), \
                self.assertLogs("django_app.views", level="ERROR"):
            response = self.post(json.dumps(DUMMY_REPORT))
        self.assertEqual(response.status_code, 500)

    # ---------------------------------------------------------------- 405

    def test_get_returns_405(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_other_methods_return_405(self):
        for method in ("put", "patch", "delete"):
            response = getattr(self.client, method)(self.url, data="{}", content_type="application/json")
            self.assertEqual(response.status_code, 405, method)


class ServicesTests(SimpleTestCase):
    @override_settings(EXPERIAN_PDF_RENDERER="weasyprint")
    def test_build_uses_renderer_setting(self):
        with mock.patch("django_app.services.generate_pdf", return_value=b"%PDF") as gen:
            self.assertEqual(services.build_experian_pdf({"a": 1}), b"%PDF")
        gen.assert_called_once_with({"a": 1}, renderer="weasyprint")

    def test_build_renderer_argument_wins(self):
        with mock.patch("django_app.services.generate_pdf", return_value=b"%PDF") as gen:
            services.build_experian_pdf({"a": 1}, renderer="chromium")
        gen.assert_called_once_with({"a": 1}, renderer="chromium")

    def test_build_real_pdf(self):
        self.assertTrue(services.build_experian_pdf(DUMMY_REPORT).startswith(b"%PDF"))

    def test_build_invalid_report(self):
        with self.assertRaises(InvalidReportError):
            services.build_experian_pdf({"no": "profile"})

    @override_settings(EXPERIAN_PDF_S3_BUCKET="reports-bucket", AWS_S3_REGION_NAME="ap-south-1")
    def test_save_pdf_to_s3(self):
        client = mock.Mock()
        fake_boto3 = SimpleNamespace(client=mock.Mock(return_value=client))
        with mock.patch.dict(sys.modules, {"boto3": fake_boto3}):
            location = services.save_pdf_to_s3(b"%PDF-data", "reports/1.pdf")
        self.assertEqual(location, "s3://reports-bucket/reports/1.pdf")
        fake_boto3.client.assert_called_once_with("s3", region_name="ap-south-1")
        kwargs = client.put_object.call_args.kwargs
        self.assertEqual(kwargs["Bucket"], "reports-bucket")
        self.assertEqual(kwargs["Key"], "reports/1.pdf")
        self.assertEqual(kwargs["Body"], b"%PDF-data")
        self.assertEqual(kwargs["ContentType"], "application/pdf")
        self.assertEqual(kwargs["ServerSideEncryption"], "AES256")

    def test_save_pdf_to_s3_without_boto3(self):
        with mock.patch.dict(sys.modules, {"boto3": None}), self.assertRaises(ImproperlyConfigured):
            services.save_pdf_to_s3(b"%PDF", "k.pdf", bucket="b")

    @override_settings(EXPERIAN_PDF_S3_BUCKET=None)
    def test_save_pdf_to_s3_without_bucket(self):
        with mock.patch.dict(sys.modules, {"boto3": SimpleNamespace(client=mock.Mock())}), \
                self.assertRaises(ImproperlyConfigured):
            services.save_pdf_to_s3(b"%PDF", "k.pdf")


class TaskTests(SimpleTestCase):
    def test_task_builds_and_uploads(self):
        with mock.patch("django_app.tasks.build_experian_pdf", return_value=b"%PDF") as build, \
                mock.patch("django_app.tasks.save_pdf_to_s3", return_value="s3://b/k.pdf") as save:
            result = tasks.generate_experian_pdf_task(DUMMY_REPORT, "k.pdf", bucket="b")
        self.assertEqual(result, "s3://b/k.pdf")
        build.assert_called_once_with(DUMMY_REPORT)
        save.assert_called_once_with(b"%PDF", "k.pdf", bucket="b")

    def test_task_is_celery_task_when_celery_installed(self):
        try:
            import celery  # noqa: F401
        except ImportError:
            self.skipTest("celery not installed")
        self.assertTrue(hasattr(tasks.generate_experian_pdf_task, "delay"))
        self.assertIn(RenderError, tasks.generate_experian_pdf_task.autoretry_for)
