"""Public API: ``generate_pdf(data) -> bytes`` and ``generate_pdf_file(json_path, out_path)``.

Framework independent. Heavy objects (Jinja environment, fonts, stylesheet, logo)
are built once per process and reused, so each report only pays for layout.

Two interchangeable renderers share the same templates and CSS:
- ``weasyprint``: pure Python, no browser.
- ``chromium``: headless Chromium via Playwright, much faster on large reports.
- ``auto`` (default): Chromium when Playwright + a Chromium build are installed, else WeasyPrint.
  If Chromium fails at runtime in auto mode, the report is re-rendered with WeasyPrint.

All resources (templates, CSS, fonts, logo) are resolved relative to this package,
so the engine works from any working directory once installed.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import chromium, content
from .exceptions import ConfigurationError, InvalidReportError, RenderError
from .gauge import gauge_svg
from .parser import parse_report

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
CSS_PATH = PACKAGE_DIR / "static" / "css" / "report.css"
# Fonts + logo ship inside the package; EXPERIAN_PDF_ASSETS can point at a replacement folder.
DEFAULT_ASSETS_DIR = PACKAGE_DIR / "assets"
LOGO_FILE = "experian_logo.svg"

FONT_FACES = [
    # family, weight, style, path relative to the assets dir
    ("Roboto", 400, "normal", "Roboto/static/Roboto-Regular.ttf"),
    ("Roboto", 700, "normal", "Roboto/static/Roboto-Bold.ttf"),
    ("Roboto", 400, "italic", "Roboto/static/Roboto-Italic.ttf"),
    ("Roboto", 700, "italic", "Roboto/static/Roboto-BoldItalic.ttf"),
]

RENDERERS = ("auto", "weasyprint", "chromium")

_lock = threading.Lock()


def _assets_dir() -> Path:
    return Path(os.environ.get("EXPERIAN_PDF_ASSETS") or DEFAULT_ASSETS_DIR).resolve()


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


@lru_cache(maxsize=1)
def _logo_src() -> str:
    path = _assets_dir() / LOGO_FILE
    try:
        data = path.read_bytes()
    except OSError:
        logger.warning("Logo not found at %s", path)
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")


def _font_files() -> list[tuple[str, int, str, Path]]:
    assets = _assets_dir()
    fonts = []
    for family, weight, style, rel in FONT_FACES:
        path = assets / rel
        if path.exists():
            fonts.append((family, weight, style, path))
        else:
            logger.warning("Font file missing: %s", path)
    return fonts


@lru_cache(maxsize=1)
def _stylesheet():
    """Return (CSS, FontConfiguration) for WeasyPrint, built once."""
    from weasyprint import CSS
    from weasyprint.text.fonts import FontConfiguration

    faces = [
        f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
        f'font-style: {style}; src: url("{path.as_uri()}"); }}'
        for family, weight, style, path in _font_files()
    ]
    font_config = FontConfiguration()
    css_text = "\n".join(faces) + "\n" + CSS_PATH.read_text(encoding="utf-8")
    return CSS(string=css_text, font_config=font_config, base_url=str(PACKAGE_DIR)), font_config


@lru_cache(maxsize=1)
def _inline_css() -> str:
    """Stylesheet with fonts embedded as data URIs (for the Chromium renderer)."""
    faces = []
    for family, weight, style, path in _font_files():
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        faces.append(
            f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
            f'font-style: {style}; src: url(data:font/ttf;base64,{b64}); }}'
        )
    return "\n".join(faces) + "\n" + CSS_PATH.read_text(encoding="utf-8")


def available_renderers() -> list[str]:
    """Renderers usable in this environment (WeasyPrint is a hard dependency)."""
    return ["weasyprint"] + (["chromium"] if chromium.is_available() else [])


def resolve_renderer(renderer: str | None = "auto") -> str:
    """Map ``auto``/``None`` to a concrete renderer name; raise on unknown names."""
    if renderer is None:
        renderer = os.environ.get("EXPERIAN_PDF_RENDERER") or "auto"
    name = str(renderer).strip().lower()
    if name not in RENDERERS:
        raise ConfigurationError(
            f"Unknown renderer {renderer!r}; expected one of: {', '.join(RENDERERS)}")
    if name == "auto":
        return "chromium" if chromium.is_available() else "weasyprint"
    return name


def build_context(data: Any) -> dict:
    ctx = parse_report(data)
    ctx["gauge_svg"] = gauge_svg(ctx["score"]["value"])
    ctx["logo_src"] = _logo_src()
    ctx["content"] = content
    return ctx


def render_html(data: Any) -> str:
    """Render the report HTML (useful for debugging the layout in a browser)."""
    ctx = build_context(data)
    try:
        return _jinja_env().get_template("base.html").render(**ctx)
    except Exception as exc:
        raise RenderError(f"Template rendering failed: {exc}") from exc


def _render_weasyprint(html: str) -> bytes:
    from weasyprint import HTML

    css, font_config = _stylesheet()
    try:
        # WeasyPrint's font configuration is not guaranteed thread-safe.
        with _lock:
            return HTML(string=html, base_url=str(PACKAGE_DIR)).write_pdf(
                stylesheets=[css], font_config=font_config
            )
    except Exception as exc:
        raise RenderError(f"PDF rendering failed: {exc}") from exc


def _render_chromium(html: str) -> bytes:
    return chromium.html_to_pdf(
        html.replace("</head>", f"<style>{_inline_css()}</style></head>", 1))


def generate_pdf(data: Any, renderer: str | None = "auto") -> bytes:
    """Convert an Experian response (dict, JSON string or bytes) into PDF bytes.

    ``renderer``: ``"auto"`` (default), ``"weasyprint"`` or ``"chromium"``; ``None`` reads the
    ``EXPERIAN_PDF_RENDERER`` environment variable (falling back to ``auto``).

    Raises ``InvalidReportError`` for unusable input, ``ConfigurationError`` for an unknown
    renderer and ``RenderError`` if rendering fails. Missing/extra keys never raise.
    """
    if renderer is None:
        renderer = os.environ.get("EXPERIAN_PDF_RENDERER") or "auto"
    name = resolve_renderer(renderer)
    html = render_html(data)
    if name == "weasyprint":
        return _render_weasyprint(html)
    try:
        return _render_chromium(html)
    except RenderError:
        if str(renderer).strip().lower() != "auto":
            raise
        logger.warning("Chromium rendering failed; falling back to WeasyPrint", exc_info=True)
        return _render_weasyprint(html)


def generate_pdf_file(json_path: str | os.PathLike, out_path: str | os.PathLike,
                      renderer: str | None = "auto") -> Path:
    """Read ``json_path``, write the PDF to ``out_path`` and return that path."""
    src = Path(json_path)
    try:
        raw = src.read_bytes()
    except OSError as exc:
        raise InvalidReportError(f"Cannot read {src}: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidReportError(f"{src} is not valid JSON: {exc}") from exc

    pdf = generate_pdf(data, renderer=renderer)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf)
    return out
