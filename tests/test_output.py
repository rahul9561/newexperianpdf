"""Content checks on the rendered PDF, per renderer."""

import pytest
from conftest import load_fixture, load_sample, pdf_info, pdf_text, profile, requires_chromium

from experian_pdf import generate_pdf

# 15 accounts in input/sample.json lay out on 23 A4 pages with both renderers.
EXPECTED_SAMPLE_PAGES = 23
RENDERERS = ["weasyprint", pytest.param("chromium", marks=requires_chromium)]


def expected_values(doc: dict) -> dict:
    """Read the values to look for from the JSON itself (no personal data hard-coded here)."""
    r = profile(doc)
    app = r["Current_Application"]["Current_Application_Details"]["Current_Applicant_Details"]
    return {
        "name": f'{app["First_Name"]} {app["Last_Name"]}'.upper(),
        "pan": app["IncomeTaxPan"],
        "score": r["SCORE"]["BureauScore"],
        "report_number": r["CreditProfileHeader"]["ReportNumber"],
    }


@pytest.fixture(scope="module", params=RENDERERS)
def sample_pdf(request):
    return request.param, generate_pdf(load_sample(), renderer=request.param)


def test_sample_page_count(sample_pdf):
    renderer, pdf = sample_pdf
    info = pdf_info(pdf)
    assert info["pages"] == EXPECTED_SAMPLE_PAGES, renderer
    assert info["size"] == (595, 842)


def test_sample_text_contains_json_values(sample_pdf):
    _, pdf = sample_pdf
    text = pdf_text(pdf)
    for key, value in expected_values(load_sample()).items():
        assert value in text, key


def test_sample_sections_in_order(sample_pdf):
    _, pdf = sample_pdf
    text = pdf_text(pdf, sort=True)
    headings = ["Experian Credit Report", "CURRENT APPLICATION INFORMATION", "EXPERIAN CREDIT SCORE",
                "REPORT SUMMARY", "SUMMARY", "CREDIT ACCOUNT INFORMATION DETAILS", "CREDIT ENQUIRIES",
                "NON-CREDIT ENQUIRIES", "CONTACTING US", "LEGEND", "END OF REPORT"]
    positions = [text.index(h) for h in headings]
    assert positions == sorted(positions)


def test_sample_fonts_and_logo_embedded(sample_pdf):
    renderer, pdf = sample_pdf
    info = pdf_info(pdf)
    assert info["embedded"], renderer
    assert {"Roboto", "Roboto-Bold"} <= {f.split("+")[-1].replace("-Regular", "") for f in info["fonts"]}
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        first = doc[0]
        # the logo is vector artwork in the top-left corner (SVG converted to PDF paths or an XObject)
        logo_area = pymupdf.Rect(0, 0, 130, 55)
        drawn = [d for d in first.get_drawings() if d["rect"].intersects(logo_area)]
        images = [i for i in first.get_image_info() if pymupdf.Rect(i["bbox"]).intersects(logo_area)]
        assert drawn or images, "logo not found on page 1"


@pytest.mark.parametrize("renderer", RENDERERS)
def test_dummy_report_values(renderer):
    data = load_fixture("dummy_report")
    text = pdf_text(generate_pdf(data, renderer=renderer))
    for key, value in expected_values(data).items():
        assert value in text, key
    for fragment in ["Acct: 3", "Cr Enq :2", "HOUSING LOAN", "CREDIT CARD", "CLOSED", "9000000001"]:
        assert fragment in text
