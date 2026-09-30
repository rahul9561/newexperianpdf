# experian-pdf

Turns an Experian India credit-report API response (`INProfileResponse`) into a PDF laid out like
`pdfsample/experiansample.pdf`: same sections, labels, colours, score gauge and tables. It is framework
independent: plain Python, a CLI, and a ready-made Django example.

Templates, CSS, the Roboto fonts and the Experian logo ship inside the package. Nothing is read from the current
directory and nothing is fetched from the internet.

```
experian_pdf/            the installable package
  engine.py              generate_pdf(), generate_pdf_file(), renderer selection
  parser.py              raw JSON -> display-ready context (all parsing logic)
  formatters.py          dates, amounts (plain / Indian grouping / ₹), "-" for empty, code lookups
  codes.py               Experian code tables  (see "Code tables to verify")
  content.py             fixed report wording (score factors, legend, disclaimer)
  gauge.py               300-900 score gauge as SVG; needle angle computed from the score
  chromium.py            optional Chromium renderer (Playwright), runs in its own worker threads
  cli.py                 `experian-pdf` command
  templates/  static/css/  assets/ (Roboto + logo)
examples/django_app/     Django view, urls, services (S3), Celery task, tests
tests/                   pytest suite + synthetic fixtures (dummy data only)
docs/field_mapping.md    every PDF field -> JSON path
```

## Install

Python 3.10 or later. The package name is `experian-pdf`; the import name is `experian_pdf`.

| How | Command |
|---|---|
| Editable, from a local checkout | `pip install -e /path/to/expriennewformate` |
| With the fast Chromium renderer | `pip install -e "/path/to/expriennewformate[chromium]"` then `playwright install chromium` |
| From git, pinned to a tag | `pip install "experian-pdf[chromium] @ git+https://github.com/<you>/experian-pdf.git@v1.0.0"` |
| From a built wheel | `python -m build` then `pip install dist/experian_pdf-1.0.0-py3-none-any.whl` |

In your Django project's `requirements.txt`, use one of these:

```text
experian-pdf[chromium] @ git+https://github.com/<you>/experian-pdf.git@v1.0.0
# or, for a sibling checkout during development:
-e ../expriennewformate[chromium]
```

This folder is not a git repository yet. To install from git, push it and tag the release:
`git init && git add . && git commit -m "experian-pdf 1.0.0" && git tag v1.0.0 && git push --tags`.

Dependencies:
- **Required:** WeasyPrint and Jinja2.
- **Optional:** Playwright, via the `[chromium]` extra.
- **Not needed by the engine:** boto3 and Celery. Only the Django example uses them, and only if you call those
  parts.

## Usage

### Python

```python
from experian_pdf import generate_pdf, generate_pdf_file, InvalidReportError

pdf_bytes = generate_pdf(experian_response)                   # dict, JSON str or bytes; renderer="auto"
pdf_bytes = generate_pdf(experian_response, renderer="weasyprint")
path = generate_pdf_file("report.json", "out/report.pdf")     # returns pathlib.Path

try:
    generate_pdf({"unexpected": "payload"})
except InvalidReportError as exc:                             # also a ValueError
    print(exc)                                                # "No 'INProfileResponse' found in input"
```

- **Accepted input:** the full gateway response, the `result_json` object, `INProfileResponse` itself, or a
  stringified `result_json`.
- **Missing, null, empty, extra or wrongly-typed fields** never raise. They render as `-` and are logged on the
  `experian_pdf.*` loggers.

Errors:

| Exception | When |
|---|---|
| `InvalidReportError` | Input is not JSON, or has no `INProfileResponse`. |
| `RenderError` | The renderer failed. |
| `ConfigurationError` | Unknown renderer name. |

All three subclass `ExperianPDFError`.

### Renderers

| `renderer=` | What it does |
|---|---|
| `"auto"` (default) | Uses Chromium if Playwright and a Chromium build are installed, otherwise WeasyPrint. If Chromium fails at runtime, it re-renders with WeasyPrint and logs a warning. |
| `"weasyprint"` | Pure Python plus Pango. No browser. |
| `"chromium"` | Headless Chromium. Much faster on large reports. Raises if unavailable. |
| `None` | Reads the `EXPERIAN_PDF_RENDERER` environment variable, falling back to `auto`. |

Measured on the development laptop (Windows, Python 3.11), which runs Python about 2× slower than a typical server:

| Report | WeasyPrint | Chromium (warm) | Chromium (first call, incl. browser launch) |
|---|---|---|---|
| sample.json, 15 accounts, 17 pages | ~5-6 s | ~0.8-1.2 s | ~1.5-1.8 s |
| 3 accounts | ~1 s | ~0.3 s | |
| 40 accounts, 45 pages | ~15 s | ~1-2 s | |

WeasyPrint cost grows at about 0.35 s per account here.

Run `pytest -m slow -s` to print timings on your own hardware.

How the Chromium renderer runs:
- Chromium runs in a small pool of dedicated threads. The pool size is set by `EXPERIAN_PDF_CHROMIUM_WORKERS`
  (default 2). Each thread keeps one browser open for reuse, at roughly 150-250 MB of RAM per browser.
- The per-render timeout is `EXPERIAN_PDF_CHROMIUM_TIMEOUT` (default 120 s).
- Because Playwright runs in those threads, your Django request threads never get an asyncio loop, and ORM calls
  keep working.
- The pool is rebuilt automatically after a fork (gunicorn `--preload`, Celery prefork).

### CLI

```bash
experian-pdf report.json -o report.pdf                  # installed console script
experian-pdf report.json -o report.pdf -r weasyprint    # force a renderer
python -m experian_pdf report.json -o report.pdf --html debug.html -v
python cli.py input/sample.json -o output/report.pdf    # from this checkout
```

### Django

See **[examples/django_app/](examples/django_app/)**. Copy the folder into your project, or copy the parts you
need.

| File | What it gives you |
|---|---|
| `views.py` | `POST /experian/pdf/`: Experian JSON in, PDF out (`inline`, `no-store`). Returns 400 for an empty or invalid body, 422 for `InvalidReportError`, 500 for any other failure (logged), and 405 for any method other than POST. |
| `urls.py` | Add it to your project with `path("", include("django_app.urls"))`. |
| `services.py` | `build_experian_pdf(experian_response) -> bytes` to call right after your Experian API call. Also `save_pdf_to_s3(pdf_bytes, key)` (private, SSE-encrypted) and `presigned_pdf_url(key)`. boto3 is imported only when used. |
| `tasks.py` | Celery task `generate_experian_pdf_task.delay(response, s3_key)`. It retries render failures and does not retry invalid input. |
| `tests.py` | 25 tests: view status codes and headers, mocked engine errors, S3 with mocked boto3, the task, and an ORM-after-render regression test. |

```python
# your code, right after the Experian call
from django_app.services import build_experian_pdf, save_pdf_to_s3

experian_response = experian_client.get_report(pan=..., mobile=...)
pdf_bytes = build_experian_pdf(experian_response)
save_pdf_to_s3(pdf_bytes, f"credit-reports/{application.pk}.pdf")   # optional
```

Settings the example reads (all optional):

| Setting | Default | Used by |
|---|---|---|
| `EXPERIAN_PDF_RENDERER` | `"auto"` | the view and services |
| `EXPERIAN_PDF_S3_BUCKET` | none | `save_pdf_to_s3()` and `presigned_pdf_url()` |
| `AWS_S3_REGION_NAME` | none | the boto3 client |

The view is `csrf_exempt` because it is a JSON API. Put your normal API authentication in front of it.

Run the example's tests without a Django project:

```bash
cd examples && python runtests.py
```

In your project, run `python manage.py test django_app`.

**Async views / ASGI:** `await sync_to_async(build_experian_pdf, thread_sensitive=False)(response)`.

**Use Celery + S3 when generation takes more than about 2 seconds.** That covers WeasyPrint with more than about
5 accounts on a typical server, or any report if you can't install Chromium. Enqueue
`generate_experian_pdf_task`, return 202 with a job id, and serve the file later from S3 via
`presigned_pdf_url()`. This keeps web workers free and avoids proxy timeouts.

## Server setup (AWS EC2 / Ubuntu 22.04+)

```bash
sudo apt-get update
# WeasyPrint needs Pango >= 1.44 (HarfBuzz and FreeType come with it)
sudo apt-get install -y python3-venv python3-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libcairo2 libffi-dev shared-mime-info

python3 -m venv /srv/app/venv && . /srv/app/venv/bin/activate
pip install "experian-pdf[chromium] @ git+https://github.com/<you>/experian-pdf.git@v1.0.0"

# Chromium + every system library it needs (uses sudo/apt):
python -m playwright install --with-deps chromium
```

Notes:
- **Cairo:** current WeasyPrint writes PDFs itself and does not use Cairo. `libcairo2` is harmless and some older
  guides require it.
- **Browser location:** Playwright downloads browsers to `~/.cache/ms-playwright` of the user who runs the command.
  Run it as the same user as gunicorn/Celery, or set `PLAYWRIGHT_BROWSERS_PATH=/srv/app/ms-playwright` for both
  the install and the service.
- **Verify the install:**
  ```bash
  python -c "import experian_pdf; print(experian_pdf.available_renderers())"
  ```
  Expect `['weasyprint', 'chromium']`.
- **Memory:** budget about 250 MB per Chromium worker thread per process. If Chromium cannot be installed (for
  example on very small instances), `renderer="auto"` falls back to WeasyPrint.
- **Upgrades:** the Playwright version in the venv must match its downloaded browsers. After upgrading
  `playwright`, re-run `playwright install chromium`.
- **Fonts:** they are embedded from the package. No system fonts are needed.

## Tests

```bash
pip install -e ".[test,chromium]"
python -m pytest -m "not slow"        # 122 tests: parser, formatters, gauge, engine, package API, output checks
python -m pytest -m slow -s           # timing per renderer (prints [perf] lines)
cd examples && python runtests.py     # 25 Django tests
python tests/fixtures/build_fixtures.py   # regenerate fixtures
```

The Chromium tests are skipped automatically when Playwright or Chromium is missing.

All fixtures in `tests/fixtures/` are synthetic: a fake name (TESTFIRST TESTLAST), PAN ABCDE1234F, phone
9000000001 and example.com emails. Tests on `input/sample.json` read their expected values from the JSON at run time
instead of hard-coding personal data.

## Formatting decisions (matching the sample)

- **Dates and time:** the header date and time are printed raw (`20260928`, `172052`). Table dates use
  `YYYY-MM-DD`.
- **Amounts:** plain integers (`3252600`), as in the sample. `formatters.indian_number` gives `32,52,600` and
  `formatters.currency_inr` gives `₹32,52,600`.
- **Loan Type, Ownership and SuitFiled Willful Default:** filled from the JSON. The sample shows `-` for these.
- **Credit Enquiries:** come from `CAPS.CAPS_Application_Details`. When there are none, the section says so.
- **Fonts:** Roboto throughout. The sample used Arial and Times New Roman; only Roboto, Montserrat and Poppins
  were provided, and Roboto is metrically close to Arial. Only the four Roboto files the report uses are packaged;
  the Montserrat and Poppins folders in `experian_pdf/assets/` are not shipped in the wheel.

## Code tables to verify

These mappings in `experian_pdf/codes.py` were written from the Experian India CAIS/CAPS code lists. **Check them
against the official Experian documentation for your contract before production.** Unknown codes print the raw
code and log `Unknown <field> code` warnings, so a gap is visible rather than silently wrong.

| Table in `codes.py` | JSON field | Notes |
|---|---|---|
| `ACCOUNT_TYPE` | `Account_Type` | ~60 codes (`01` AUTO LOAN, `10` CREDIT CARD, `53` BUSINESS LOAN -PRIORITY SECTOR - AGRICULTURE, ...). Spellings follow the sample PDF. |
| `ACCOUNT_STATUS_ACTIVE` / `ACCOUNT_STATUS_CLOSED` | `Account_Status` | Active = `11, 21-25, 71, 78, 80, 82-84`; Closed = `12-17`. Confirmed only for `11` and `12`/`13` against the sample's summary counts. |
| `ACCOUNT_STATUS` | `Account_Status` | Suit-filed / wilful-default / written-off / settled labels for `00`, `30-97`. |
| `OWNERSHIP` | `AccountHoldertypeCode` | `1` Individual, `2` Joint, `3` Authorised User, `7` Guarantor. |
| `SUIT_FILED_WILFUL_DEFAULT` | `SuitFiled_WilfulDefault` | `00`-`03`. |
| `GENDER` | `Gender_Code` | `1` Male, `2` Female, `3` Transgender. |
| `OCCUPATION` | `Occupation_Code` | `S`, `N`, `E`, `P`, `U`. |
| `STATE` | `State_non_normalized`, CAPS `State` | `01`-`38`, `99`. Check the codes for Telangana (`36`), Ladakh (`38`) and the post-2014 Andhra Pradesh split. |

These fields are **printed raw**, with no table, and may deserve labels:
- `Enquiry_Reason` (the enquiry "Search Type")
- `Written_off_Settled_Status` (the sample prints `99`)
- `Telephone_Type` (the sample prints `1`/`2`)
- `Asset_Classification` letters (explained in the legend)

Days-past-due colours are green for 0, orange for 1-89, and red for 90+ or B/D/L. Confirm these with your credit
team.

See `docs/field_mapping.md` for the complete PDF-field-to-JSON-path mapping.
