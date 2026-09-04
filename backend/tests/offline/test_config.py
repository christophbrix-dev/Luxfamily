# What the server needs to start, and what it only needs for one feature.
#
# A variable read as os.environ["..."] at import time turns a missing setting
# into a bare KeyError before any logging exists. That is how EMERGENT_SESSION_URL
# behaved: it blocked start-up on every deployment, including those that do not
# offer Google sign-in, and it was documented nowhere.

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def declared_in_example():
    text = (BACKEND / ".env.example").read_text(encoding="utf-8")
    return {m.group(1) for m in re.finditer(r"^([A-Z][A-Z0-9_]*)=", text, re.M)}


def read_from_environment():
    """Every env var server.py reads, however it reads it."""
    src = (BACKEND / "server.py").read_text(encoding="utf-8")
    names = set()
    for pat in (r'os\.environ\["([A-Z][A-Z0-9_]*)"\]',
                r'os\.environ\.get\("([A-Z][A-Z0-9_]*)"',
                r'_require_env\("([A-Z][A-Z0-9_]*)"\)'):
        names |= {m.group(1) for m in re.finditer(pat, src)}
    return names


def test_every_variable_the_server_reads_is_documented():
    missing = read_from_environment() - declared_in_example()
    assert not missing, (
        "server.py reads these, but .env.example never mentions them — "
        f"nobody setting this up can know they exist: {sorted(missing)}"
    )


def test_nothing_is_read_bare_at_import_time():
    """os.environ["X"] gives a KeyError with no explanation.

    _require_env names the variable and says it is required; .get() with a
    default makes it optional. Both are fine. The bare subscript is not.
    """
    src = (BACKEND / "server.py").read_text(encoding="utf-8")
    bare = re.findall(r'os\.environ\["([A-Z][A-Z0-9_]*)"\]', src)
    assert not bare, (
        "read with a bare subscript, which fails as an unexplained KeyError "
        f"before logging is up: {sorted(set(bare))}. "
        "Use _require_env(name) for required, os.environ.get(name, default) "
        "for optional."
    )


class TestOptionalGoogleSignIn:
    def test_the_server_starts_without_it(self, app_module):
        """Everything except one endpoint works without Google sign-in."""
        assert app_module.app is not None

    def test_the_endpoint_says_what_is_missing(self, app_module, client, run, monkeypatch):
        monkeypatch.setattr(app_module, "EMERGENT_SESSION_URL", "")

        async def call():
            async with client as c:
                return await c.post("/api/auth/session", json={"session_id": "abc"})

        res = run(call())
        assert res.status_code == 503
        # The message has to name the variable — "something went wrong" costs
        # whoever is deploying this an hour.
        assert "EMERGENT_SESSION_URL" in res.json()["detail"]
