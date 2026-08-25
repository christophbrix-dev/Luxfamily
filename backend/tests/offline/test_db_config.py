# Which database the command-line tools write to.
#
# Every script beside the server had its own two lines for this and they did not
# agree. osm_ingest fell back to "familyluxembourg", the two seed scripts to
# "test_database", and none of the three read backend/.env — so running one from
# a shell wrote to a database nothing serves and said it had succeeded. The
# ingest reported 7,856 places imported; the API returned none.
#
# It had already cost real work: Emergent's first run of the commune seeder put
# 40 sources into "test_database" and had to go back and delete them.

import re
from pathlib import Path

import pytest

import db_config

BACKEND = Path(db_config.__file__).resolve().parent

# Everything that talks to MongoDB outside the server process.
TOOLS = [
    "osm_ingest.py",
    "seed_commune_sources.py",
    "seed_venue_sources.py",
    "normalise_towns.py",
    "clear_stock_images.py",
]


class TestItRefusesToGuess:
    def test_a_missing_name_stops_the_tool(self, monkeypatch):
        monkeypatch.setattr(db_config, "load_env", lambda: None)
        monkeypatch.delenv("DB_NAME", raising=False)
        with pytest.raises(SystemExit) as exit_info:
            db_config.mongo_settings()
        assert "DB_NAME" in str(exit_info.value)

    def test_an_empty_name_stops_it_too(self, monkeypatch):
        monkeypatch.setattr(db_config, "load_env", lambda: None)
        monkeypatch.setenv("DB_NAME", "   ")
        with pytest.raises(SystemExit):
            db_config.mongo_settings()

    def test_the_message_says_where_to_put_it(self, monkeypatch):
        monkeypatch.setattr(db_config, "load_env", lambda: None)
        monkeypatch.delenv("DB_NAME", raising=False)
        with pytest.raises(SystemExit) as exit_info:
            db_config.mongo_settings()
        assert ".env" in str(exit_info.value)


class TestItReadsWhatIsSet:
    def test_both_values(self, monkeypatch):
        monkeypatch.setattr(db_config, "load_env", lambda: None)
        monkeypatch.setenv("DB_NAME", "luxfamily_local")
        monkeypatch.setenv("MONGO_URL", "mongodb://elsewhere:27017")
        assert db_config.mongo_settings() == ("mongodb://elsewhere:27017", "luxfamily_local")

    def test_a_local_url_is_a_fair_default(self, monkeypatch):
        """Only the URL. Guessing the host is recoverable; guessing the
        database name writes real data where nothing reads it."""
        monkeypatch.setattr(db_config, "load_env", lambda: None)
        monkeypatch.setenv("DB_NAME", "x")
        monkeypatch.delenv("MONGO_URL", raising=False)
        url, _ = db_config.mongo_settings()
        assert "127.0.0.1" in url or "localhost" in url


class TestNoToolDecidesForItself:
    @pytest.mark.parametrize("name", TOOLS)
    def test_it_uses_the_shared_settings(self, name):
        src = (BACKEND / name).read_text(encoding="utf-8")
        assert "mongo_settings" in src, f"{name} resolves the database on its own"

    @pytest.mark.parametrize("name", TOOLS)
    def test_it_names_no_fallback_database(self, name):
        """The bug in one line: a default that looked harmless."""
        src = (BACKEND / name).read_text(encoding="utf-8")
        guesses = re.findall(r'environ\.get\(\s*"DB_NAME"\s*,\s*"([^"]+)"', src)
        assert not guesses, f"{name} would silently write to {guesses}"

    def test_the_env_file_is_the_one_the_server_reads(self):
        server = (BACKEND / "server.py").read_text(encoding="utf-8")
        assert 'load_dotenv(ROOT_DIR / ".env")' in server
        assert 'BACKEND_DIR / ".env"' in (BACKEND / "db_config.py").read_text(encoding="utf-8")
