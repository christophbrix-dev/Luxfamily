import os
import pathlib

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or "http://localhost:8001").rstrip("/")

# These tests need admin credentials. Never fall back to hardcoded values —
# CI/local must inject them via env. Missing credentials *skip* rather than
# raise: raising at import time aborts collection for the whole backend/tests
# tree, including the offline suite below it, which needs no credentials at all
# and is the part CI can actually run.
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL") or ""
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD") or ""

requires_admin_creds = pytest.mark.skipif(
    not (ADMIN_EMAIL and ADMIN_PASSWORD),
    reason="Set ADMIN_EMAIL and ADMIN_PASSWORD (or TEST_ADMIN_* overrides)",
)


_BACKEND_REACHABLE = None


@pytest.fixture(autouse=True)
def _requires_live_backend(request):
    """Skip the HTTP tests in this directory when nothing is listening.

    These talk to a deployed backend, so without one they fail with connection
    errors instead of reporting the honest "nothing to test against". Probed
    once per session. Deliberately does not apply to tests/offline, which runs
    the app in-process and needs no server at all.
    """
    if "offline" in pathlib.Path(str(request.node.fspath)).parts:
        return
    global _BACKEND_REACHABLE
    if _BACKEND_REACHABLE is None:
        try:
            requests.get(f"{BASE_URL}/api/health", timeout=5)
            _BACKEND_REACHABLE = True
        except requests.RequestException:
            _BACKEND_REACHABLE = False
    if not _BACKEND_REACHABLE:
        pytest.skip(f"No backend reachable at {BASE_URL} (set EXPO_BACKEND_URL)")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    """HTTP session for the integration tests.

    Reachability is handled by the autouse fixture above.
    """
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api_client):
    if not (ADMIN_EMAIL and ADMIN_PASSWORD):
        pytest.skip("ADMIN_EMAIL / ADMIN_PASSWORD not set in the environment")
    r = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
