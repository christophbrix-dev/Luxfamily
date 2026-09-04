"""Where the tools write, decided in one place.

Every script beside the server had its own two lines for this, and they did not
agree. Three of them named a fallback database — osm_ingest "familyluxembourg",
the two seed scripts "test_database" — and none of the three read backend/.env,
so running one from a shell wrote to a database nobody serves. Nothing failed:
the ingest reported 7,856 places imported and the API returned none.

It had already cost real confusion. Emergent's first run of the commune seeder
put 40 sources into "test_database" and had to go and delete them.

So: read the .env the server reads, and refuse rather than guess. A tool that
cannot tell which database it is talking to should stop, not pick one.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent


def load_env() -> None:
    """Read backend/.env, the same file the server loads.

    Explicit about the path rather than searching upwards: a tool run from
    another directory must not find somebody else's .env.
    """
    load_dotenv(BACKEND_DIR / ".env")


def mongo_settings() -> tuple[str, str]:
    """(MONGO_URL, DB_NAME), or a clear stop.

    No default for the database name. A wrong guess writes real data somewhere
    nothing reads, and says it succeeded — which is worse than not running.
    """
    load_env()
    url = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
    name = os.environ.get("DB_NAME", "").strip()
    if not name:
        raise SystemExit(
            "DB_NAME is not set.\n"
            f"  Put it in {BACKEND_DIR / '.env'}, or export it before running.\n"
            "  Refusing to guess: writing to the wrong database looks like success."
        )
    return url, name
