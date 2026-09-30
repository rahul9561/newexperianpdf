"""Command line: experian-pdf input.json -o report.pdf  (or: python -m experian_pdf ...)"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import RENDERERS, ExperianPDFError, generate_pdf_file, render_html


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="experian-pdf", description="Convert an Experian credit report JSON into a PDF.")
    ap.add_argument("json_path", help="Experian API response JSON file")
    ap.add_argument("-o", "--output", help="output PDF path (default: output/<input name>.pdf)")
    ap.add_argument("-r", "--renderer", choices=RENDERERS, default=None,
                    help="auto (default; Chromium if installed, else WeasyPrint), weasyprint or chromium. "
                         "Default comes from $EXPERIAN_PDF_RENDERER when set.")
    ap.add_argument("--html", help="also write the intermediate HTML here (for debugging)")
    ap.add_argument("-v", "--verbose", action="store_true", help="show parser warnings")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING if args.verbose else logging.ERROR,
                        format="%(levelname)s %(name)s: %(message)s")
    # WeasyPrint is chatty about unsupported CSS; keep it quiet unless verbose.
    logging.getLogger("weasyprint").setLevel(logging.WARNING if args.verbose else logging.ERROR)

    out = Path(args.output) if args.output else Path("output") / (Path(args.json_path).stem + ".pdf")
    try:
        start = time.perf_counter()
        generate_pdf_file(args.json_path, out, renderer=args.renderer)
        elapsed = time.perf_counter() - start
        if args.html:
            Path(args.html).write_text(
                render_html(Path(args.json_path).read_text(encoding="utf-8-sig")), encoding="utf-8")
    except ExperianPDFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out} in {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
