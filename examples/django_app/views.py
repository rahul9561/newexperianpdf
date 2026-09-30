"""POST /experian/pdf/ : Experian JSON in, PDF out.

    200  application/pdf (inline)
    400  body empty or not valid JSON
    405  any method other than POST
    422  JSON is valid but not an Experian report (no INProfileResponse)
    500  unexpected rendering error (logged with traceback)
"""

from __future__ import annotations

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from experian_pdf import InvalidReportError

from .services import build_experian_pdf

logger = logging.getLogger(__name__)

PDF_FILENAME = "experian_report.pdf"


# This is a machine-to-machine JSON API, so CSRF is disabled here. Protect it with your
# usual API authentication (DRF auth, API key middleware, @login_required, ...).
@csrf_exempt
@require_POST
def experian_pdf_view(request):
    if not request.body or not request.body.strip():
        return JsonResponse({"error": "Request body is empty; expected Experian JSON."}, status=400)
    try:
        experian_response = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return JsonResponse({"error": f"Invalid JSON: {exc}"}, status=400)

    try:
        pdf_bytes = build_experian_pdf(experian_response)
    except InvalidReportError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except Exception:
        logger.exception("Experian PDF generation failed")
        return JsonResponse({"error": "Could not generate the PDF report."}, status=500)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{PDF_FILENAME}"'
    response["Content-Length"] = str(len(pdf_bytes))
    response["Cache-Control"] = "no-store"  # personal financial data
    return response
