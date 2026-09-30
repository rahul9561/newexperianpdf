"""Experian credit report JSON -> PDF engine.

    from experian_pdf import generate_pdf, generate_pdf_file, InvalidReportError

    pdf_bytes = generate_pdf(experian_response)                 # renderer="auto"
    generate_pdf_file("report.json", "report.pdf", renderer="weasyprint")
"""

from .engine import (
    RENDERERS,
    available_renderers,
    build_context,
    generate_pdf,
    generate_pdf_file,
    render_html,
    resolve_renderer,
)
from .exceptions import ConfigurationError, ExperianPDFError, InvalidReportError, RenderError
from .parser import parse_report

__version__ = "1.0.0"

__all__ = [
    "generate_pdf",
    "generate_pdf_file",
    "render_html",
    "build_context",
    "parse_report",
    "available_renderers",
    "resolve_renderer",
    "RENDERERS",
    "ExperianPDFError",
    "InvalidReportError",
    "RenderError",
    "ConfigurationError",
    "__version__",
]
