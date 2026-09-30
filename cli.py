"""Command line: python cli.py input/sample.json -o output/report.pdf [-r auto|weasyprint|chromium]

Thin wrapper; once the package is installed the same CLI is available as ``experian-pdf``.
"""

import sys

from experian_pdf.cli import main

if __name__ == "__main__":
    sys.exit(main())
