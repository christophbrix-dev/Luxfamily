import os
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or "http://localhost:8001").rstrip("/")

# Tests need admin credentials. Never fall back to hardcoded values — CI/local
# must inject them via env. Read them once at import time and let pytest fail
# loudly with a clear message if they're missing.
_ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL")
_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
if not _ADMIN_EMAIL or not _ADMIN_PASSWORD:
    raise RuntimeError(
        "Set ADMIN_EMAIL and ADMIN_PASSWORD (or TEST_ADMIN_* overrides) "
        "before running the test suite. See /app/memory/test_credentials.md."
    )
ADMIN_EMAIL = _ADMIN_EMAIL
ADMIN_PASSWORD = _ADMIN_PASSWORD


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api_client):
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
