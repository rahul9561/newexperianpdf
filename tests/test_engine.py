import json

import pymupdf
import pytest
from conftest import (ROOT, SAMPLE_PATH, load_fixture, load_sample, pdf_info, pdf_text, profile,
                      requires_chromium)

from experian_pdf import InvalidReportError, generate_pdf, generate_pdf_file, render_html

RENDERERS = ["weasyprint", pytest.param("chromium", marks=requires_chromium)]


@pytest.mark.parametrize("renderer", RENDERERS)
@pytest.mark.parametrize("name", ["dummy_report", "many_accounts", "missing_sections", "empty_fields"])
def test_fixtures_render(name, renderer):
    pdf = generate_pdf(load_fixture(name), renderer=renderer)
    assert pdf.startswith(b"%PDF")
    text = pdf_text(pdf)
    assert "END OF REPORT" in text
    info = pdf_info(pdf)
    assert info["fonts"] and all("Roboto" in f for f in info["fonts"]), info["fonts"]
    assert info["embedded"]
    if name == "many_accounts":
        assert "Acct: 40" in text and "Cr Enq :8" in text
    if name == "missing_sections":
        assert "No credit accounts reported." in text
        assert "No credit enquiries reported." in text


def test_template_has_no_hardcoded_consumer_data():
    """Values from the real sample and the design PDF must never appear in templates."""
    r = profile(load_sample())
    applicant = r["Current_Application"]["Current_Application_Details"]["Current_Applicant_Details"]
    literals = [applicant["IncomeTaxPan"], applicant["MobilePhoneNumber"], applicant["First_Name"].upper(),
                r["SCORE"]["BureauScore"], r["CreditProfileHeader"]["ReportNumber"],
                r["CreditProfileHeader"]["ReportDate"]]
    blob = "".join(p.read_text(encoding="utf-8")
                   for p in (ROOT / "experian_pdf" / "templates").rglob("*.html"))
    for literal in literals:
        assert literal not in blob


def test_long_text_stays_on_page():
    pdf = generate_pdf(load_fixture("empty_fields"), renderer="weasyprint")
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            for x0, y0, x1, y1, *_ in page.get_text("words"):
                assert x1 <= page.rect.width - 5, "text overflows right edge"


def test_generate_pdf_file(tmp_path):
    out = generate_pdf_file(SAMPLE_PATH, tmp_path / "nested" / "r.pdf", renderer="weasyprint")
    assert out == tmp_path / "nested" / "r.pdf"
    assert out.read_bytes().startswith(b"%PDF")


def test_generate_pdf_file_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    with pytest.raises(InvalidReportError):
        generate_pdf_file(bad, tmp_path / "x.pdf")
    with pytest.raises(InvalidReportError):
        generate_pdf_file(tmp_path / "missing.json", tmp_path / "x.pdf")
    assert not (tmp_path / "x.pdf").exists()


def test_invalid_payload_raises():
    with pytest.raises(InvalidReportError):
        generate_pdf({"status": False, "message": "error"})


def test_json_string_and_bytes_accepted():
    raw = json.dumps(load_fixture("dummy_report"))
    assert generate_pdf(raw, renderer="weasyprint").startswith(b"%PDF")
    assert generate_pdf(raw.encode(), renderer="weasyprint").startswith(b"%PDF")


def test_html_is_escaped():
    data = load_fixture("dummy_report")
    profile(data)["Current_Application"]["Current_Application_Details"]["Current_Applicant_Details"][
        "First_Name"] = "<script>x</script>"
    html = render_html(data)
    assert "<SCRIPT>" not in html and "&lt;SCRIPT&gt;" in html


def test_sample_pdf_shows_lenders():
    text = pdf_text(generate_pdf(load_sample(), renderer="weasyprint"), sort=True)
    assert "HDFC Bank Ltd" in text and "ICICI Bank" in text
    assert "LENDER SUMMARY" in text  # section bars are upper-cased by CSS
    # lender header strip (name + "Acct: N" badge) sits above the first account's cards
    details = text.index("CREDIT ACCOUNT INFORMATION DETAILS")
    first_card = text.index("Account Holder Details", details)
    assert details < text.index("HDFC Bank Ltd", details) < first_card
    assert details < text.index("Acct: 1", details) < first_card


def test_lender_logo_used_when_present(tmp_path, monkeypatch):
    from experian_pdf import engine

    (tmp_path / "lenders").mkdir()
    (tmp_path / "lenders" / "hdfc-bank-ltd.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    monkeypatch.setenv("EXPERIAN_PDF_ASSETS", str(tmp_path))
    engine._lender_logo_src.cache_clear()
    try:
        accounts = engine.build_context(load_sample())["accounts"]
    finally:
        engine._lender_logo_src.cache_clear()
    assert engine.lender_slug("Citicorp Finance ( I ) ltd") == "citicorp-finance-i-ltd"
    assert accounts[0]["lender_logo"].startswith("data:image/png;base64,")
    assert accounts[1]["lender_logo"] == ""  # ICICI Bank: no file -> text-only header
