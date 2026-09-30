import json
import logging
from functools import lru_cache
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SAMPLE_PATH = ROOT / "input" / "sample.json"

logging.getLogger("weasyprint").setLevel(logging.ERROR)
logging.getLogger("fontTools").setLevel(logging.ERROR)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def profile(doc: dict) -> dict:
    return doc["data"]["result"]["result_json"]["INProfileResponse"]


def pdf_text(pdf: bytes, sort: bool = False) -> str:
    """All page text; ``sort=True`` returns it in reading order (top-to-bottom per page)."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return "\n".join(page.get_text(sort=sort) for page in doc)


def pdf_info(pdf: bytes) -> dict:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return {
            "pages": doc.page_count,
            "fonts": {f[3] for page in doc for f in page.get_fonts(full=True)},
            "embedded": all(f[1] != "n/a" for page in doc for f in page.get_fonts(full=True)),
            "size": (round(doc[0].rect.width), round(doc[0].rect.height)),
            "producer": (doc.metadata or {}).get("producer", ""),
        }


@lru_cache(maxsize=1)
def chromium_available() -> bool:
    from experian_pdf.chromium import is_available

    return is_available()


requires_chromium = pytest.mark.skipif(
    not chromium_available(), reason="playwright / Chromium not installed")
