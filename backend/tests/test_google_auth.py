# Google Auth (Emergent-managed) + unified get_current_user tests
# Covers /api/auth/session, /api/auth/me (both auth types), /api/auth/logout,
# and MongoDB indexes on user_sessions.
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import requests
from motor.motor_asyncio import AsyncIOMotorClient

from conftest import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


# ---------------------------------------------------------------------------
# 1) POST /api/auth/session — validation & rejection paths
# ---------------------------------------------------------------------------
class TestGoogleSessionEndpoint:
    """Verifies the /api/auth/session request/response schema and error handling."""

    def test_invalid_session_id_returns_401(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/session",
            json={"session_id": "totally_invalid"},
            timeout=20,
        )
        assert r.status_code == 401, r.text
        body = r.json()
        assert body.get("detail") == "Invalid or expired session", body

    def test_empty_session_id_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/session",
            json={"session_id": ""},
            timeout=15,
        )
        assert r.status_code == 400, r.text
        assert r.json().get("detail") == "session_id is required"

    def test_missing_session_id_field_returns_422(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/session",
            json={},
            timeout=15,
        )
        assert r.status_code == 422, r.text

    def test_whitespace_only_session_id_returns_400(self, api_client):
        # Confirms strip() path in server.py catches whitespace payloads.
        r = api_client.post(
            f"{BASE_URL}/api/auth/session",
            json={"session_id": "   "},
            timeout=15,
        )
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 2) GET /api/auth/me — anonymous & bogus bearer
# ---------------------------------------------------------------------------
class TestAuthMeUnauthenticated:
    def test_me_without_authorization_header_returns_401(self, api_client):
        # Fresh session — do not send default headers with auth
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401, r.text

    def test_me_with_bogus_bearer_returns_401_not_403(self, api_client):
        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer bogus_token_" + uuid.uuid4().hex},
            timeout=15,
        )
        # Explicitly not 403 — dependency should not gate on scheme presence.
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 3) Legacy admin JWT flow still works via unified get_current_user
# ---------------------------------------------------------------------------
class TestLegacyAdminJWTFlow:
    def test_admin_login_returns_jwt(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("access_token"), data
        assert data.get("token_type") == "bearer"

    def test_admin_me_with_jwt(self, api_client, admin_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "admin"


# ---------------------------------------------------------------------------
# 4) POST /api/auth/logout — 401 unauth, 204 with admin JWT
# ---------------------------------------------------------------------------
class TestLogoutEndpoint:
    def test_logout_no_token_returns_401(self, api_client):
        r = requests.post(f"{BASE_URL}/api/auth/logout", timeout=15)
        assert r.status_code == 401, r.text

    def test_logout_with_admin_jwt_returns_204(self, api_client, admin_headers):
        r = requests.post(f"{BASE_URL}/api/auth/logout", headers=admin_headers, timeout=15)
        assert r.status_code == 204, f"expected 204 got {r.status_code}: {r.text}"
        # Admin JWT should still work after logout — we only delete session_token rows.
        r2 = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=15)
        assert r2.status_code == 200, r2.text


# ---------------------------------------------------------------------------
# 5) MongoDB user_sessions indexes (session_token unique, user_id, expires_at TTL)
# ---------------------------------------------------------------------------
class TestUserSessionsIndexes:
    def _get_indexes(self):
        mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
        db_name = os.environ.get("DB_NAME") or "lux_family"

        async def _list():
            client = AsyncIOMotorClient(mongo_url)
            try:
                db = client[db_name]
                info = await db.command("listIndexes", "user_sessions")
                return info["cursor"]["firstBatch"]
            finally:
                client.close()

        return asyncio.get_event_loop().run_until_complete(_list())

    def test_session_token_index_unique(self):
        indexes = self._get_indexes()
        by_key = {tuple(sorted(idx["key"].items())): idx for idx in indexes}
        st_idx = by_key.get((("session_token", 1),))
        assert st_idx is not None, f"session_token index missing. Have: {indexes}"
        assert st_idx.get("unique") is True, f"session_token index not unique: {st_idx}"

    def test_user_id_index_exists(self):
        indexes = self._get_indexes()
        keys = [tuple(sorted(idx["key"].items())) for idx in indexes]
        assert (("user_id", 1),) in keys, f"user_id index missing. Have keys: {keys}"

    def test_expires_at_ttl_index(self):
        indexes = self._get_indexes()
        exp = next(
            (idx for idx in indexes if tuple(sorted(idx["key"].items())) == (("expires_at", 1),)),
            None,
        )
        assert exp is not None, f"expires_at index missing. Have: {indexes}"
        assert "expireAfterSeconds" in exp, f"expires_at is not a TTL index: {exp}"
        assert exp["expireAfterSeconds"] == 0


# ---------------------------------------------------------------------------
# 6) Unified get_current_user resolves a real session_token row
# ---------------------------------------------------------------------------
class TestGoogleSessionTokenPath:
    """Insert a fake session_token + user directly into Mongo, then hit /auth/me
    with it as a Bearer to prove the session_token branch of get_current_user works.
    This does NOT invoke the Emergent OAuth roundtrip."""

    TEST_TOKEN = f"TEST_sess_{uuid.uuid4().hex}"
    TEST_USER_ID = f"TEST_user_{uuid.uuid4().hex[:12]}"
    TEST_EMAIL = f"TEST_google_{uuid.uuid4().hex[:8]}@example.com"

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _client(self):
        mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
        db_name = os.environ.get("DB_NAME") or "lux_family"
        client = AsyncIOMotorClient(mongo_url)
        return client, client[db_name]

    def test_session_token_bearer_returns_user(self, api_client):
        async def _setup():
            client, db = self._client()
            try:
                await db.users.insert_one({
                    "id": self.TEST_USER_ID,
                    "email": self.TEST_EMAIL,
                    "name": "Test Google User",
                    "role": "user",
                    "provider": "google",
                    "hashed_password": "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                await db.user_sessions.insert_one({
                    "session_token": self.TEST_TOKEN,
                    "user_id": self.TEST_USER_ID,
                    "created_at": datetime.now(timezone.utc),
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
                })
            finally:
                client.close()

        async def _teardown():
            client, db = self._client()
            try:
                await db.user_sessions.delete_many({"session_token": self.TEST_TOKEN})
                await db.users.delete_many({"id": self.TEST_USER_ID})
            finally:
                client.close()

        try:
            self._run(_setup())

            r = requests.get(
                f"{BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {self.TEST_TOKEN}"},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["email"] == self.TEST_EMAIL
            assert body["role"] == "user"
            assert body["id"] == self.TEST_USER_ID

            # Logout with this token should invalidate the session row → 204.
            r_logout = requests.post(
                f"{BASE_URL}/api/auth/logout",
                headers={"Authorization": f"Bearer {self.TEST_TOKEN}"},
                timeout=15,
            )
            assert r_logout.status_code == 204, r_logout.text

            # After logout, the same token must fail.
            r_after = requests.get(
                f"{BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {self.TEST_TOKEN}"},
                timeout=15,
            )
            assert r_after.status_code == 401, r_after.text
        finally:
            self._run(_teardown())

    def test_expired_session_token_rejected(self, api_client):
        expired_token = f"TEST_expired_{uuid.uuid4().hex}"
        expired_user = f"TEST_user_exp_{uuid.uuid4().hex[:12]}"

        async def _setup():
            client, db = self._client()
            try:
                await db.users.insert_one({
                    "id": expired_user,
                    "email": f"TEST_exp_{uuid.uuid4().hex[:6]}@example.com",
                    "role": "user",
                    "provider": "google",
                    "hashed_password": "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                await db.user_sessions.insert_one({
                    "session_token": expired_token,
                    "user_id": expired_user,
                    "created_at": datetime.now(timezone.utc) - timedelta(days=10),
                    "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                })
            finally:
                client.close()

        async def _teardown():
            client, db = self._client()
            try:
                await db.user_sessions.delete_many({"session_token": expired_token})
                await db.users.delete_many({"id": expired_user})
            finally:
                client.close()

        try:
            self._run(_setup())
            r = requests.get(
                f"{BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
                timeout=15,
            )
            assert r.status_code == 401, r.text
        finally:
            self._run(_teardown())
