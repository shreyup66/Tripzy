import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # Browser tests are optional: pip install playwright && playwright install chromium
    sync_playwright = None
    collect_ignore_glob = ["test_*.py"]

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server_url():
    """Run the real app with uvicorn on localhost (a trusted origin for geolocation)."""
    port = _free_port()
    db_dir = tempfile.mkdtemp(prefix="tripzy-e2e-")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_dir}/e2e.db", "PLACES_PROVIDER": "mock", "APP_ENV": "test"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    url = f"http://localhost:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError(proc.stderr.read().decode())
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def new_context(browser, server_url):
    contexts = []

    def _new(**kwargs):
        ctx = browser.new_context(base_url=server_url, **kwargs)
        ctx.set_default_timeout(8000)
        contexts.append(ctx)
        return ctx

    yield _new
    for ctx in contexts:
        ctx.close()


_counter = iter(range(1, 10_000))


def unique_email(name: str) -> str:
    return f"{name.lower()}{next(_counter)}-{int(time.time() * 1000)}@example.com"
