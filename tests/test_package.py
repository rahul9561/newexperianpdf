"""Public API, packaging and renderer selection."""

import importlib
from pathlib import Path

import pytest
from conftest import chromium_available, load_fixture, pdf_info, requires_chromium

import experian_pdf
from experian_pdf import engine


def test_public_api_importable():
    from experian_pdf import (ConfigurationError, ExperianPDFError, InvalidReportError,  # noqa: F401
                              RenderError, available_renderers, generate_pdf, generate_pdf_file)

    for name in ["generate_pdf", "generate_pdf_file", "InvalidReportError"]:
        assert name in experian_pdf.__all__
    assert experian_pdf.__version__ == "1.0.0"
    assert issubclass(InvalidReportError, ValueError)
    assert issubclass(InvalidReportError, ExperianPDFError)


def test_default_renderer_is_auto():
    import inspect

    for fn in (experian_pdf.generate_pdf, experian_pdf.generate_pdf_file):
        assert inspect.signature(fn).parameters["renderer"].default == "auto"


def test_resources_resolve_inside_package():
    pkg = Path(experian_pdf.__file__).resolve().parent
    assert engine.TEMPLATES_DIR == pkg / "templates"
    assert engine.CSS_PATH.is_file() and engine.CSS_PATH.is_relative_to(pkg)
    assert engine.DEFAULT_ASSETS_DIR == pkg / "assets"
    assert (engine.DEFAULT_ASSETS_DIR / engine.LOGO_FILE).is_file()
    for *_, rel in engine.FONT_FACES:
        assert (engine.DEFAULT_ASSETS_DIR / rel).is_file(), rel


def test_works_from_another_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf = experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer="weasyprint")
    assert pdf.startswith(b"%PDF")


def test_cli_entry_point(tmp_path, capsys):
    from conftest import FIXTURES

    from experian_pdf.cli import main

    out = tmp_path / "cli.pdf"
    assert main([str(FIXTURES / "dummy_report.json"), "-o", str(out), "-r", "weasyprint"]) == 0
    assert out.read_bytes().startswith(b"%PDF")
    assert main([str(tmp_path / "missing.json"), "-o", str(out)]) == 1
    assert "error:" in capsys.readouterr().err


# ------------------------------------------------------------------ renderers

def test_renderer_weasyprint():
    pdf = experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer="weasyprint")
    info = pdf_info(pdf)
    assert pdf.startswith(b"%PDF") and info["size"] == (595, 842)
    assert "WeasyPrint" in info["producer"]


@requires_chromium
def test_renderer_chromium():
    pdf = experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer="chromium")
    info = pdf_info(pdf)
    assert pdf.startswith(b"%PDF") and info["size"] == (595, 842)
    assert "Skia" in info["producer"]


def test_renderer_auto_picks_available_backend():
    expected = "chromium" if chromium_available() else "weasyprint"
    assert experian_pdf.resolve_renderer("auto") == expected
    assert experian_pdf.resolve_renderer("AUTO ") == expected
    assert experian_pdf.available_renderers()[0] == "weasyprint"
    pdf = experian_pdf.generate_pdf(load_fixture("dummy_report"))  # default = auto
    assert pdf.startswith(b"%PDF")


def test_renderer_auto_without_playwright(monkeypatch):
    monkeypatch.setattr(engine.chromium, "is_available", lambda: False)
    assert experian_pdf.resolve_renderer("auto") == "weasyprint"
    assert experian_pdf.generate_pdf(load_fixture("dummy_report")).startswith(b"%PDF")


def test_auto_falls_back_when_chromium_fails(monkeypatch, caplog):
    monkeypatch.setattr(engine.chromium, "is_available", lambda: True)

    def boom(html):
        raise experian_pdf.RenderError("browser crashed")

    monkeypatch.setattr(engine.chromium, "html_to_pdf", boom)
    assert experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer="auto").startswith(b"%PDF")
    assert "falling back to WeasyPrint" in caplog.text
    with pytest.raises(experian_pdf.RenderError):  # explicit chromium does not fall back
        experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer="chromium")


def test_renderer_from_environment(monkeypatch):
    monkeypatch.setenv("EXPERIAN_PDF_RENDERER", "weasyprint")
    assert experian_pdf.resolve_renderer(None) == "weasyprint"
    monkeypatch.setenv("EXPERIAN_PDF_RENDERER", "bogus")
    with pytest.raises(experian_pdf.ConfigurationError):
        experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer=None)


@pytest.mark.parametrize("bad", ["pdfkit", "", "weasy", 42])
def test_invalid_renderer_raises_clear_error(bad):
    with pytest.raises(experian_pdf.ConfigurationError) as exc:
        experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer=bad)
    assert "Unknown renderer" in str(exc.value)
    assert "auto, weasyprint, chromium" in str(exc.value)
    assert isinstance(exc.value, ValueError)


def test_chromium_module_has_no_hard_playwright_import():
    src = Path(importlib.util.find_spec("experian_pdf.chromium").origin).read_text(encoding="utf-8")
    top_level = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    assert not any("playwright" in ln for ln in top_level)


@requires_chromium
def test_chromium_leaves_no_event_loop_in_caller_thread():
    """Django refuses ORM calls in a thread with a running asyncio loop; rendering must not create one."""
    import asyncio

    experian_pdf.generate_pdf(load_fixture("dummy_report"), renderer="chromium")
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()


@requires_chromium
def test_chromium_concurrent_renders():
    from concurrent.futures import ThreadPoolExecutor

    data = load_fixture("dummy_report")
    with ThreadPoolExecutor(4) as pool:
        pdfs = list(pool.map(lambda _: experian_pdf.generate_pdf(data, renderer="chromium"), range(4)))
    assert all(p.startswith(b"%PDF") for p in pdfs)
