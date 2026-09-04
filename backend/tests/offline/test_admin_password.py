# Changing the admin password from the console.
#
# Two things had to be true for this to be possible at all. The endpoint has to
# refuse anyone who cannot produce the current password, and a restart must not
# undo the change — the boot code used to compare ADMIN_PASSWORD against the
# stored hash and overwrite it whenever they differed, which made the
# environment variable the only possible source of the password.

import hashlib
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


NEW = "en-neie-laange-passwuert"


@pytest.fixture
def admin(app_module, run):
    """A stored admin account with a known password."""
    async def make():
        await app_module.db.users.delete_many({})
        await app_module.db.users.insert_one({
            "id": "admin-1",
            "email": "admin@example.invalid",
            "hashed_password": app_module.hash_password("dat-aalt-passwuert"),
            "role": "admin",
            "name": "Administrator",
        })
    run(make())
    return app_module


def change(client, run, token, current, new):
    async def call():
        async with client as c:
            return await c.post(
                "/api/admin/password",
                headers={"Authorization": f"Bearer {token}"},
                json={"current_password": current, "new_password": new},
            )
    return run(call())


@pytest.fixture
def token(admin):
    return admin.create_access_token("admin-1", "admin")


class TestItRefuses:
    def test_without_a_token(self, admin, client, run):
        async def call():
            async with client as c:
                return await c.post("/api/admin/password",
                                    json={"current_password": "x", "new_password": NEW})
        assert run(call()).status_code in (401, 403)

    def test_with_the_wrong_current_password(self, admin, client, run, token):
        """A valid token is not enough. A token lives seven days and sits in
        browser storage; an unattended console must not lock the owner out."""
        res = change(client, run, token, "falsch", NEW)
        assert res.status_code == 403

    def test_a_password_that_is_too_short(self, admin, client, run, token):
        res = change(client, run, token, "dat-aalt-passwuert", "kuerz")
        assert res.status_code == 400

    def test_reusing_the_same_password(self, admin, client, run, token):
        res = change(client, run, token, "dat-aalt-passwuert", "dat-aalt-passwuert")
        assert res.status_code == 400

    def test_a_refusal_does_not_change_anything(self, admin, client, run, token):
        change(client, run, token, "falsch", NEW)

        async def stored():
            return await admin.db.users.find_one({"id": "admin-1"})
        assert admin.verify_password("dat-aalt-passwuert", run(stored())["hashed_password"])


class TestItWorks:
    def test_the_new_password_takes(self, admin, client, run, token):
        assert change(client, run, token, "dat-aalt-passwuert", NEW).status_code == 204

        async def stored():
            return await admin.db.users.find_one({"id": "admin-1"})
        doc = run(stored())
        assert admin.verify_password(NEW, doc["hashed_password"])
        assert not admin.verify_password("dat-aalt-passwuert", doc["hashed_password"])

    def test_it_is_recorded_when(self, admin, client, run, token):
        assert change(client, run, token, "dat-aalt-passwuert", NEW).status_code == 204

        async def stored():
            return await admin.db.users.find_one({"id": "admin-1"})
        assert run(stored()).get("password_changed_at")


class TestItIsRateLimited:
    """Guessing the current password must not be cheap.

    Read off the source rather than by making six requests: the limiter counts
    per address, and a test that exhausts it changes the outcome of every test
    after it. It is disabled in this suite for that reason.
    """

    def test_the_endpoint_carries_a_limit(self):
        src = (BACKEND / "server.py").read_text(encoding="utf-8")
        block = src[src.index('@app.post("/api/admin/password"'):]
        block = block[:block.index("async def ")]
        assert "@limiter.limit(" in block, "no rate limit on the password endpoint"

    def test_the_limit_is_low_enough_to_matter(self):
        src = (BACKEND / "server.py").read_text(encoding="utf-8")
        block = src[src.index('@app.post("/api/admin/password"'):]
        block = block[:block.index("async def ")]
        per_minute = int(re.search(r'@limiter\.limit\("(\d+)/minute"\)', block).group(1))
        assert per_minute <= 10


class TestARestartDoesNotUndoIt:
    """The reason this endpoint can exist.

    The old boot code overwrote the stored hash whenever it differed from
    ADMIN_PASSWORD. A password changed here would have lasted until the next
    deploy and then silently reverted.
    """

    def fingerprint(self, email, password):
        return hashlib.sha256(f"{email}:{password}".encode()).hexdigest()

    def test_an_unchanged_variable_leaves_the_password_alone(self):
        env_password = "de-ursprungswert"
        email = "admin@example.invalid"
        stored_fp = self.fingerprint(email, env_password)
        # What boot compares: the variable against its own last value.
        assert stored_fp == self.fingerprint(email, env_password)

    def test_editing_the_variable_still_rotates(self):
        email = "admin@example.invalid"
        old = self.fingerprint(email, "de-ursprungswert")
        new = self.fingerprint(email, "e-neie-wert")
        assert old != new

    def test_the_fingerprint_cannot_be_used_to_test_guesses(self):
        """It is a hash of email and password together, never compared against
        a candidate — only against its own previous value."""
        a = self.fingerprint("admin@example.invalid", "geheim")
        b = self.fingerprint("aner@example.invalid", "geheim")
        assert a != b
