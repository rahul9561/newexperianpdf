"""Timing report per renderer. Run with:  pytest -m slow -s"""

import time

import pytest
from conftest import load_fixture, load_sample, requires_chromium

from experian_pdf import generate_pdf

RENDERERS = ["weasyprint", pytest.param("chromium", marks=requires_chromium)]
CASES = {
    "sample.json (15 accounts)": load_sample,
    "dummy_report (3 accounts)": lambda: load_fixture("dummy_report"),
    "many_accounts (40 accounts)": lambda: load_fixture("many_accounts"),
}


@pytest.mark.slow
@pytest.mark.parametrize("renderer", RENDERERS)
@pytest.mark.parametrize("case", list(CASES))
def test_generation_time(case, renderer):
    data = CASES[case]()
    start = time.perf_counter()
    generate_pdf(data, renderer=renderer)  # first call includes warm-up (fonts / browser launch)
    cold = time.perf_counter() - start
    runs = []
    for _ in range(2):
        start = time.perf_counter()
        pdf = generate_pdf(data, renderer=renderer)
        runs.append(time.perf_counter() - start)
    warm = min(runs)
    print(f"\n[perf] {renderer:<10} {case:<30} first={cold:5.2f}s  warm={warm:5.2f}s  "
          f"({len(pdf) // 1024} KB)")
    assert pdf.startswith(b"%PDF")
    assert warm < 60  # sanity ceiling only; numbers are reported, not enforced
