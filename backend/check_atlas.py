#!/usr/bin/env python3
"""Before anything moves: does this connection string actually work?

The migration has Emergent copy a live database into a cluster nobody has ever
written to. If the user has the wrong password, or forgot to open network
access, or gave the database user read-only rights, that is discovered in the
middle of a paid run — and the failure looks like a broken migration rather
than a setup that was never finished.

This asks the four questions that can be asked beforehand, in order, and stops
at the first no:

    1. can we reach the cluster at all?
    2. does the user and password get us in?
    3. may we write?  (a read-only user copies nothing)
    4. is the target database empty?  (a non-empty one is a wrong name, or a
       second run about to happen)

    export TARGET_MONGO_URL='mongodb+srv://...'
    export TARGET_DB_NAME='luxfamily'
    python3 check_atlas.py

Writes one document into a throwaway collection and removes it again. It never
touches `events`, `places` or `sources`, and it prints nothing that contains
the password — see `_masked` in copy_database.py.
"""
from __future__ import annotations

import logging
import sys

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from copy_database import _masked, _target

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("check_atlas")

PROBE = "_luxfamily_connection_probe"
REAL_COLLECTIONS = ("events", "places", "sources", "users")


def _fail(what: str, advice: str) -> None:
    log.error("  ✗ %s\n\n    %s", what, advice)
    sys.exit(1)


def main() -> None:
    url, name = _target()
    log.info("Ziel: %s / %s\n", _masked(url), name)

    client = MongoClient(url, serverSelectionTimeoutMS=15_000)

    # 1 — reachable
    try:
        info = client.server_info()
    except PyMongoError as exc:
        text = str(exc)
        if "Authentication failed" in text or "auth" in text.lower():
            _fail(
                "Benutzername oder Passwort werden nicht akzeptiert.",
                "Atlas → Database Access → Passwort neu erzeugen und in beide\n"
                "    .env-Dateien eintragen. Achte auf Sonderzeichen: ein @ oder /\n"
                "    im Passwort muss in der URL kodiert werden — lass Atlas das\n"
                "    Passwort erzeugen, dann passiert das nicht.",
            )
        _fail(
            f"Cluster nicht erreichbar. ({type(exc).__name__})",
            "Meistens fehlt der Netzwerkzugang: Atlas → Network Access → IP\n"
            "    hinzufügen. Emergents Container hat keine feste Adresse, dort\n"
            "    wird 0.0.0.0/0 gebraucht.",
        )
    log.info("  ✓ erreichbar, MongoDB %s", info.get("version", "?"))

    db = client[name]

    # 2 — may we write
    try:
        db[PROBE].insert_one({"_id": "probe"})
        db[PROBE].delete_one({"_id": "probe"})
        db.drop_collection(PROBE)
    except OperationFailure:
        _fail(
            "Der Benutzer darf nicht schreiben.",
            "Atlas → Database Access → Benutzer bearbeiten → Rolle\n"
            "    'Read and write to any database'.",
        )
    log.info("  ✓ Schreibrecht vorhanden")

    # 3 — is it empty
    existing = {
        coll: db[coll].estimated_document_count()
        for coll in REAL_COLLECTIONS
        if coll in db.list_collection_names()
    }
    filled = {c: n for c, n in existing.items() if n}
    if filled:
        log.warning("  ! Die Zieldatenbank ist nicht leer:")
        for coll, n in sorted(filled.items()):
            log.warning("        %-10s %d Dokumente", coll, n)
        log.warning(
            "\n    Das ist kein Fehler, aber prüfe den Namen. copy_database.py\n"
            "    überspringt volle Sammlungen, es wird also nichts überschrieben."
        )
    else:
        log.info("  ✓ Zieldatenbank ist leer, bereit für den Umzug")

    log.info("\nAlles bereit. Der nächste Schritt läuft bei Emergent:")
    log.info("    python3 copy_database.py --write && python3 copy_database.py --verify")


if __name__ == "__main__":
    main()
