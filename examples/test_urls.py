"""Stand-in for a project's urls.py: shows how to include the example app."""

from django.urls import include, path

urlpatterns = [
    path("", include("django_app.urls")),  # -> POST /experian/pdf/
]
