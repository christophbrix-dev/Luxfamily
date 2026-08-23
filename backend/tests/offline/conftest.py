"""Offline tests: the real FastAPI app driven against an in-memory MongoDB.

The suite one directory up talks to a deployed backend over HTTP and needs
credentials, so it can only run against a live environment. These need neither —
they import the app, swap in mongomock_motor and exercise the real route
handlers, so CI can run them on every push.

`run` is a fixture rather than an imported helper so nothing here depends on
sys.path layout, and async is driven with plain asyncio.run so the suite needs
no pytest-asyncio and no pytest configuration.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# server.py reads these at import time and refuses to start without them.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "lux_offline_tests")
os.environ.setdefault("JWT_SECRET", "offline-test-secret-at-least-32-bytes-long")
os.environ.setdefault("ADMIN_EMAIL", "offline-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "offline-test-password")
os.environ.setdefault("DISABLE_SCHEDULER", "1")
os.environ.setdefault("EMERGENT_SESSION_URL", "https://example.invalid/session")


@pytest.fixture
def run():
    """Run one coroutine to completion in a fresh event loop."""
    return lambda coro: asyncio.run(coro)


@pytest.fixture
def app_module():
    """The imported server module, wired to a fresh in-memory database."""
    pytest.importorskip("mongomock_motor", reason="pip install -r requirements-dev.txt")
    from mongomock_motor import AsyncMongoMockClient

    import server

    server.client = AsyncMongoMockClient()
    server.db = server.client["offline"]
    return server


@pytest.fixture
def client(app_module):
    """An httpx client bound to the ASGI app — no network involved.

    Returned un-entered: ASGITransport needs no connection pool, and entering
    the context manager twice inside one test raises.
    """
    import httpx

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_module.app),
        base_url="http://offline",
    )


@pytest.fixture
def admin_headers(app_module, run):
    """Bearer header for a seeded admin user."""

    async def _seed():
        await app_module.db.users.insert_one(
            {"id": "offline-admin", "email": "a@example.com", "role": "admin"}
        )

    run(_seed())
    return {"Authorization": "Bearer " + app_module.create_access_token("offline-admin", "admin")}
