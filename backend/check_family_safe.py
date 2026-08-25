#!/usr/bin/env python3
"""Audit everything already stored against the family-safety filter.

The filter in content_filter runs at import, which protects what arrives from
now on. It says nothing about what is already in the database: every event
stored before the filter existed came in unchecked, a source can change what
it publishes, and an importer added later could miss the check.

So this walks the whole collection and asks the same question again.

    python3 check_family_safe.py                # report
    python3 check_family_safe.py --quarantine   # hide the findings

Quarantine sets `published` to False and records why in `family_flag`. It does
not delete: a finding is a question for a human, and an event removed from the
database cannot be looked at afterwards to decide whether the rule was right.
Clearing the flag by hand publishes the entry again.

Exit code is 1 when anything is found, so this can run from cron or CI and
actually raise an alarm rather than scrolling past in a log.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from content_filter import assess
from db_config import mongo_settings

# No basicConfig at import time: server.py imports audit_family_safety from
# here to run the same check after each crawl, and a module that reconfigures
# the root logger on import would quietly rewrite the backend's log format.
log = logging.getLogger("check_family_safe")

COLLECTIONS = ("events", "places")
TEXT_FIELDS = ("title", "name", "short", "description")


def _all_text(doc: dict) -> str:
    """Every human-readable string on the document, in every language.

    Checking only the German text would let an explicit French description
    through on an entry whose German side is clean.
    """
    out = []
    for field in TEXT_FIELDS:
        value = doc.get(field)
        if isinstance(value, dict):
            out.extend(v for v in value.values() if isinstance(v, str))
        elif isinstance(value, str):
            out.append(value)
    cats = doc.get("category")
    if isinstance(cats, list):
        out.extend(c for c in cats if isinstance(c, str))
    return " ".join(out)


def _label(doc: dict) -> str:
    for field in ("title", "name"):
        value = doc.get(field)
        if isinstance(value, dict):
            for lang in ("de", "en", "fr", "lb"):
                if value.get(lang):
                    return str(value[lang])
        elif isinstance(value, str) and value:
            return value
    return doc.get("id", "?")


async def scan(db) -> tuple[int, list[tuple[str, dict, str, str]]]:
    """(documents checked, findings). Reads only — writes nothing."""
    findings: list[tuple[str, dict, str, str]] = []
    checked = 0
    projection = {f: 1 for f in (*TEXT_FIELDS, "id", "category", "source_name")}

    for name in COLLECTIONS:
        async for doc in db[name].find({}, projection):
            checked += 1
            verdict = assess(_all_text(doc))
            if verdict:
                findings.append((name, doc, *verdict))
    return checked, findings


async def _hide(db, findings) -> int:
    """Unpublish the findings and record why. Returns how many were hidden."""
    now = datetime.now(timezone.utc).isoformat()
    hidden = 0
    for coll in COLLECTIONS:
        ops = [
            UpdateOne(
                {"id": doc["id"]},
                {"$set": {
                    "published": False,
                    "family_flag": {"reason": reason, "matched": matched, "at": now},
                }},
            )
            for c, doc, reason, matched in findings
            if c == coll and doc.get("id")
        ]
        if ops:
            hidden += (await db[coll].bulk_write(ops, ordered=False)).modified_count
    return hidden


async def audit_family_safety(db) -> int:
    """Scan and hide in one call. The scheduler's entry point.

    Kept here rather than duplicated in server.py so the automatic check and
    the one Christoph runs by hand can never drift apart and disagree about
    what counts as safe.
    """
    _, findings = await scan(db)
    if not findings:
        return 0
    for coll, doc, reason, matched in findings:
        log.warning(
            "Family-safety: hiding %s %r from %s (%r matched)",
            coll, _label(doc)[:60], doc.get("source_name", "—"), matched,
        )
    return await _hide(db, findings)


async def run(quarantine: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    checked, findings = await scan(db)
    log.info("Checked %d document(s) across %s.", checked, " and ".join(COLLECTIONS))

    if not findings:
        log.info("Nothing found. Everything stored passes the family filter.")
        return 0

    log.info("\n%d entr(ies) do not belong in a family app:\n", len(findings))
    for coll, doc, reason, matched in findings:
        log.info(
            "    [%s] %-44s  %r matched  (%s)",
            coll, _label(doc)[:44], matched, doc.get("source_name", "—"),
        )

    if not quarantine:
        log.info("\nReport only. Re-run with --quarantine to hide these.")
        return 1

    hidden = await _hide(db, findings)
    log.info("\nHid %d entr(ies). Clear `family_flag` to publish again.", hidden)
    return 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quarantine", action="store_true",
                    help="unpublish what is found instead of only reporting it")
    sys.exit(asyncio.run(run(ap.parse_args().quarantine)))


if __name__ == "__main__":
    main()
