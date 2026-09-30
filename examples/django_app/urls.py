from django.urls import path

from . import views

app_name = "experian_pdf"

urlpatterns = [
    # POST /experian/pdf/  (include this module from your project's urls.py with an empty prefix)
    path("experian/pdf/", views.experian_pdf_view, name="pdf"),
]
