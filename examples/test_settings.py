"""Minimal settings to run the django_app example tests (not a real project)."""

import os

SECRET_KEY = "test-only-not-secret"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django_app.apps.ExperianPdfConfig",
]
MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
ROOT_URLCONF = "test_urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# experian_pdf settings used by django_app.services
EXPERIAN_PDF_RENDERER = os.environ.get("EXPERIAN_PDF_RENDERER", "auto")
EXPERIAN_PDF_S3_BUCKET = "test-bucket"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        "weasyprint": {"handlers": ["null"], "level": "ERROR", "propagate": False},
        "fontTools": {"handlers": ["null"], "level": "ERROR", "propagate": False},
    },
}
