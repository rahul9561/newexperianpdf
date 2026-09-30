"""Optional Chromium renderer (Playwright). Same HTML/CSS as WeasyPrint, much faster on big reports.

Playwright's sync API runs an asyncio event loop in the thread that uses it. If that were a
Django request thread, Django would then refuse ORM calls there ("You cannot call this from an
async context"). So Chromium lives in a small pool of dedicated worker threads, each owning one
headless browser that is reused across reports. Callers only wait on a Future.

Environment:
    EXPERIAN_PDF_CHROMIUM_WORKERS   number of browser threads per process (default 2)
    EXPERIAN_PDF_CHROMIUM_TIMEOUT   seconds to wait for one render (default 120)
"""

from __future__ import annotations

import atexit
import importlib.util
import logging
import os
import queue
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout

from .exceptions import RenderError

logger = logging.getLogger(__name__)

INSTALL_HINT = ("renderer 'chromium' needs: pip install 'experian-pdf[chromium]' && "
                "playwright install chromium")
_PROBE = object()  # job that only makes sure the browser can launch
_STOP = None


def _first_line(exc: Exception) -> str:
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0]


class _Worker(threading.Thread):
    def __init__(self, jobs: queue.Queue, n: int):
        super().__init__(name=f"experian-pdf-chromium-{n}", daemon=True)
        self.jobs = jobs
        self._pw = None
        self._browser = None

    def _ensure_browser(self):
        if self._browser is not None and self._browser.is_connected():
            return self._browser
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RenderError(INSTALL_HINT) from exc
        if self._pw is None:
            self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--disable-gpu", "--no-sandbox"])
        return self._browser

    def _render(self, html: str) -> bytes:
        page = self._ensure_browser().new_page()
        try:
            page.set_content(html, wait_until="load")
            return page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            page.close()

    def _run_job(self, payload):
        if payload is _PROBE:
            self._ensure_browser()
            return True
        had_browser = self._browser is not None
        try:
            return self._render(payload)
        except RenderError:
            raise
        except Exception as exc:
            if not had_browser:  # launch failure: retrying will not help
                raise
            logger.warning("Chromium render failed (%s); restarting browser", _first_line(exc))
            self._close_browser()
            return self._render(payload)

    def _close_browser(self):
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        self._browser = None

    def run(self):
        while True:
            item = self.jobs.get()
            if item is _STOP:
                break
            payload, future = item
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(self._run_job(payload))
            except RenderError as exc:
                future.set_exception(exc)
            except Exception as exc:
                message = f"Chromium rendering failed: {_first_line(exc)}"
                if "Executable doesn't exist" in str(exc):
                    message += f" ({INSTALL_HINT})"
                future.set_exception(RenderError(message))
        self._close_browser()
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass


class _Pool:
    def __init__(self, size: int):
        self.pid = os.getpid()
        self.jobs: queue.Queue = queue.Queue()
        self.workers = [_Worker(self.jobs, i + 1) for i in range(size)]
        for w in self.workers:
            w.start()

    def submit(self, payload) -> Future:
        future: Future = Future()
        self.jobs.put((payload, future))
        return future

    def shutdown(self, timeout: float = 10.0):
        for _ in self.workers:
            self.jobs.put(_STOP)
        for w in self.workers:
            w.join(timeout)


_pool: _Pool | None = None
_pool_lock = threading.Lock()
_available: bool | None = None


def _get_pool() -> _Pool:
    global _pool
    with _pool_lock:
        # threads do not survive fork (gunicorn --preload, Celery prefork): rebuild per process
        if _pool is None or _pool.pid != os.getpid():
            size = max(1, int(os.environ.get("EXPERIAN_PDF_CHROMIUM_WORKERS", "2")))
            _pool = _Pool(size)
        return _pool


def _timeout() -> float:
    return float(os.environ.get("EXPERIAN_PDF_CHROMIUM_TIMEOUT", "120"))


def is_available() -> bool:
    """True when Playwright is installed and Chromium launches (checked once per process)."""
    global _available
    if _available is None:
        if importlib.util.find_spec("playwright") is None:
            _available = False
        else:
            try:
                _available = bool(_get_pool().submit(_PROBE).result(timeout=_timeout()))
            except Exception as exc:
                logger.warning("Chromium renderer unavailable, using WeasyPrint: %s", _first_line(exc))
                _available = False
    return _available


def html_to_pdf(html: str) -> bytes:
    """Render self-contained HTML (inline CSS, data-URI fonts/images) to PDF bytes."""
    future = _get_pool().submit(html)
    try:
        return future.result(timeout=_timeout())
    except FutureTimeout as exc:
        future.cancel()
        raise RenderError(f"Chromium rendering timed out after {_timeout():.0f}s") from exc


@atexit.register
def shutdown() -> None:
    """Close the browsers (called automatically at interpreter exit)."""
    global _pool
    with _pool_lock:
        if _pool is not None and _pool.pid == os.getpid():
            _pool.shutdown()
        _pool = None
