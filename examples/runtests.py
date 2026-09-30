"""Run the Django example tests without a Django project:

    cd examples && python runtests.py            # all django_app tests
    python runtests.py django_app.tests.ExperianPdfViewTests
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:  # use the installed package if present, else the source checkout next to examples/
    import experian_pdf  # noqa: F401
except ImportError:
    sys.path.insert(0, str(HERE.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_settings")

import django  # noqa: E402
from django.conf import settings  # noqa: E402
from django.test.utils import get_runner  # noqa: E402

if __name__ == "__main__":
    django.setup()
    runner = get_runner(settings)(verbosity=2)
    failures = runner.run_tests(sys.argv[1:] or ["django_app"])
    sys.exit(bool(failures))
