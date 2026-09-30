"""Optional Celery task: generate the PDF in the background and store it in S3.

Use this when generation takes more than ~2 s (large reports on the WeasyPrint renderer),
so the web request can return immediately:

    from django_app.tasks import generate_experian_pdf_task

    result = generate_experian_pdf_task.delay(experian_response, f"credit-reports/{app_id}.pdf")
    # later: result.get() -> "s3://bucket/credit-reports/123.pdf"

The Experian response must be JSON-serialisable (it is, straight from the API).
Celery is optional: without it this module still imports, and ``.delay()`` runs inline.
"""

from __future__ import annotations

import logging

from experian_pdf import RenderError

from .services import build_experian_pdf, save_pdf_to_s3

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:  # Celery not installed: run tasks synchronously
    def shared_task(*_args, **_kwargs):
        def decorator(fn):
            fn.delay = fn
            return fn
        return decorator


@shared_task(
    autoretry_for=(RenderError,),  # transient renderer failures (e.g. browser crash)
    retry_backoff=True,
    max_retries=3,
)
def generate_experian_pdf_task(experian_response: dict, s3_key: str, bucket: str | None = None) -> str:
    """Render the report and upload it; returns ``s3://bucket/key``.

    ``InvalidReportError`` is not retried: bad input will not get better.
    """
    pdf_bytes = build_experian_pdf(experian_response)
    location = save_pdf_to_s3(pdf_bytes, s3_key, bucket=bucket)
    logger.info("Experian PDF task stored %s", location)
    return location
