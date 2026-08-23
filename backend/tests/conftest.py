import os
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


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    """HTTP session for the integration tests.

    Every test in this suite takes it, so this is also where we check a backend
    is actually listening — otherwise these fail with connection errors instead
    of reporting the honest "nothing to test against". The offline suite does
    not use this fixture and is unaffected.
    """
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    try:
        s.get(f"{BASE_URL}/api/health", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"No backend reachable at {BASE_URL} (set EXPO_BACKEND_URL): {exc}")
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
