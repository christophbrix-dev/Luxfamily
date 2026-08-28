#!/usr/bin/env python3
"""Copy one MongoDB database into another, and prove afterwards that it worked.

Written for the move to a shared cluster. Until now there were two databases
that knew nothing about each other — one on the laptop, one inside Emergent's
container — and every report had to be read twice because the numbers never
matched. This copies one into the other so there can be a single one.

    export TARGET_MONGO_URL='mongodb+srv://...'   # not on the command line
    export TARGET_DB_NAME='luxfamily'

    python3 copy_database.py            # show what would be copied
    python3 copy_database.py --write    # copy it
    python3 copy_database.py --verify   # compare the two, change nothing

The source is whatever backend/.env points at, the same database every other
script here uses.

The target goes in environment variables and not in an argument, because a
connection string holds a password and command lines end up in shell history,
in `ps`, and in the logs of whatever ran them. Nothing here ever prints it —
`_masked` exists so an error message can name the host without the credentials.

Refuses rather than guesses:

  - it will not write into a collection that already has documents unless you
    pass --replace, so a second run cannot quietly double everything
  - it stops if source and target are the same database, which otherwise
    copies a collection onto itself
  - --verify is the real check. A copy that reports success and a target that
    actually holds the data are two different claims, and this repository has
    already had a script report the first without the second.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from typing import Iterator

from pymongo import MongoClient

from db_config import mongo_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("copy_database")

BATCH = 500


def _masked(url: str) -> str:
    """The host, without the credentials. Safe to log, safe to paste."""
    return re.sub(r"://[^@/]*@", "://***@", url)


def _target() -> tuple[str, str]:
    url = os.environ.get("TARGET_MONGO_URL", "").strip()
    name = os.environ.get("TARGET_DB_NAME", "").strip()
    if not url or not name:
        raise SystemExit(
            "TARGET_MONGO_URL and TARGET_DB_NAME must both be set.\n"
            "  export TARGET_MONGO_URL='mongodb+srv://user:password@cluster/'\n"
            "  export TARGET_DB_NAME='luxfamily'\n"
            "\n"
            "  Put them in the environment rather than in the command, so the\n"
            "  password does not end up in your shell history."
        )
    return url, name


def _batches(cursor) -> Iterator[list]:
    batch = []
    for doc in cursor:
        batch.append(doc)
        if len(batch) >= BATCH:
            yield batch
            batch = []
    if batch:
        yield batch


def plan(source_db, target_db) -> list[tuple[str, int, int]]:
    """(collection, documents in source, documents already in target)."""
    rows = []
    for name in sorted(source_db.list_collection_names()):
        rows.append((
            name,
            source_db[name].count_documents({}),
            target_db[name].count_documents({}),
        ))
    return rows


def copy(source_db, target_db, rows, replace: bool) -> int:
    copied = 0
    for name, in_source, in_target in rows:
        if not in_source:
            continue
        if in_target and not replace:
            log.info("    %-16s skipped — target already holds %d", name, in_target)
            continue
        if in_target and replace:
            target_db[name].delete_many({})
        for batch in _batches(source_db[name].find({})):
            target_db[name].insert_many(batch, ordered=False)
            copied += len(batch)
        log.info("    %-16s %d copied", name, in_source)
    return copied


def verify(source_db, target_db) -> bool:
    """Count both sides and say where they differ. Writes nothing."""
    ok = True
    log.info("%-16s %8s %8s", "collection", "source", "target")
    for name, in_source, in_target in plan(source_db, target_db):
        mark = "" if in_source == in_target else "   <-- differs"
        if in_source != in_target:
            ok = False
        log.info("%-16s %8d %8d%s", name, in_source, in_target, mark)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="perform the copy")
    ap.add_argument("--verify", action="store_true",
                    help="compare the two databases and change nothing")
    ap.add_argument("--replace", action="store_true",
                    help="empty a target collection first instead of skipping it")
    args = ap.parse_args()

    source_url, source_name = mongo_settings()
    target_url, target_name = _target()

    if (source_url, source_name) == (target_url, target_name):
        raise SystemExit("Source and target are the same database. Nothing to do.")

    log.info("from  %s / %s", _masked(source_url), source_name)
    log.info("to    %s / %s\n", _masked(target_url), target_name)

    source = MongoClient(source_url, serverSelectionTimeoutMS=10_000)[source_name]
    target = MongoClient(target_url, serverSelectionTimeoutMS=10_000)[target_name]

    if args.verify:
        sys.exit(0 if verify(source, target) else 1)

    rows = plan(source, target)
    total = sum(n for _, n, _ in rows)
    for name, in_source, in_target in rows:
        note = f"  (target already holds {in_target})" if in_target else ""
        log.info("    %-16s %6d%s", name, in_source, note)
    log.info("\n%d document(s) in %d collection(s).", total, len(rows))

    if not args.write:
        log.info("\nDry run. Re-run with --write to copy.")
        return

    copied = copy(source, target, rows, args.replace)
    log.info("\nCopied %d document(s).", copied)
    log.info("Now run --verify. A copy that says it worked and a target that")
    log.info("holds the data are two different claims.")


if __name__ == "__main__":
    main()
