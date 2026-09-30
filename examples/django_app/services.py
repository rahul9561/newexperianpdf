"""Service helpers to call from your own code (views, Celery tasks, management commands).

    from django_app.services import build_experian_pdf, save_pdf_to_s3

    experian_response = experian_client.fetch_report(...)      # your existing API call
    pdf_bytes = build_experian_pdf(experian_response)
    save_pdf_to_s3(pdf_bytes, f"credit-reports/{application.id}.pdf")   # optional

Settings used (all optional):
    EXPERIAN_PDF_RENDERER   "auto" (default) | "weasyprint" | "chromium"
    EXPERIAN_PDF_S3_BUCKET  default bucket for save_pdf_to_s3()
    AWS_S3_REGION_NAME      region for the boto3 client
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from experian_pdf import generate_pdf

logger = logging.getLogger(__name__)


def build_experian_pdf(experian_response: dict, renderer: str | None = None) -> bytes:
    """Render the Experian API response as PDF bytes.

    Raises ``experian_pdf.InvalidReportError`` if the response has no ``INProfileResponse``
    and ``experian_pdf.RenderError`` if rendering fails.
    """
    renderer = renderer or getattr(settings, "EXPERIAN_PDF_RENDERER", "auto")
    return generate_pdf(experian_response, renderer=renderer)


def save_pdf_to_s3(pdf_bytes: bytes, key: str, bucket: str | None = None) -> str:
    """Upload the PDF to S3 (private, server-side encrypted) and return ``s3://bucket/key``.

    boto3 is imported lazily, so it is only needed if you actually use S3.
    """
    try:
        import boto3
    except ImportError as exc:
        raise ImproperlyConfigured("save_pdf_to_s3() needs boto3: pip install boto3") from exc

    bucket = bucket or getattr(settings, "EXPERIAN_PDF_S3_BUCKET", None)
    if not bucket:
        raise ImproperlyConfigured("Pass bucket= or set EXPERIAN_PDF_S3_BUCKET in settings")

    client = boto3.client("s3", region_name=getattr(settings, "AWS_S3_REGION_NAME", None))
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ContentDisposition="inline",
        ServerSideEncryption="AES256",  # credit reports are sensitive: never make them public
    )
    logger.info("Stored Experian PDF at s3://%s/%s (%d bytes)", bucket, key, len(pdf_bytes))
    return f"s3://{bucket}/{key}"


def presigned_pdf_url(key: str, bucket: str | None = None, expires_in: int = 900) -> str:
    """Short-lived download link for a stored report (default 15 minutes)."""
    try:
        import boto3
    except ImportError as exc:
        raise ImproperlyConfigured("presigned_pdf_url() needs boto3: pip install boto3") from exc

    bucket = bucket or getattr(settings, "EXPERIAN_PDF_S3_BUCKET", None)
    if not bucket:
        raise ImproperlyConfigured("Pass bucket= or set EXPERIAN_PDF_S3_BUCKET in settings")
    client = boto3.client("s3", region_name=getattr(settings, "AWS_S3_REGION_NAME", None))
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in)
