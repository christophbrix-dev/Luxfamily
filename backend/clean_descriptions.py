#!/usr/bin/env python3
"""Strip page-builder markup out of already-stored event descriptions.

The importers clean from now on, but events imported before that keep what
their source wrote. In the live database 51 of 354 descriptions read like

    [et_pb_section fb_built="1" _builder_version="4.24.2"][et_pb_row …]

with the real text buried inside, or with no text at all — every one of them
from a commune running Divi. Re-crawling does not fix them: dedup matches on
external_id, so an event already stored is never rewritten.

    python3 clean_descriptions.py            # show what would change
    python3 clean_descriptions.py --write    # change it

Where the description is markup end to end, the title takes its place: an
empty field is more honest than a wall of shortcodes. `short` is rebuilt from
the cleaned text so the list view matches the detail view. Safe to run twice —
the second run reports nothing to do.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from db_config import mongo_settings
from importers import _strip_page_builder

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("clean_descriptions")

LANGS = ("en", "de", "fr", "lb")
SHORT_LEN = 120


def _clean_localized(field: dict | None, fallback: dict | None) -> dict | None:
    """Cleaned copy of a localized field, or None when nothing changed."""
    if not isinstance(field, dict):
        return None
    out, touched = dict(field), False
    for lang in LANGS:
        value = field.get(lang)
        if not isinstance(value, str):
            continue
        cleaned = _strip_page_builder(value)
        if cleaned == value:
            continue
        if not cleaned and isinstance(fallback, dict):
            cleaned = fallback.get(lang) or ""
        out[lang], touched = cleaned, True
    return out if touched else None


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    ops, samples = [], []
    async for ev in db.events.find({}, {"title": 1, "short": 1, "description": 1}):
        title = ev.get("title")
        desc = _clean_localized(ev.get("description"), title)
        if desc is None:
            continue

        # Rebuild `short` from the cleaned description rather than cleaning it
        # separately: it is a truncation of that text and should stay one.
        short = {
            lang: (desc.get(lang) or "")[:SHORT_LEN]
            for lang in LANGS
            if isinstance((ev.get("short") or {}).get(lang), str)
        }

        update = {"description": desc}
        if short:
            update["short"] = short
        ops.append(UpdateOne({"_id": ev["_id"]}, {"$set": update}))

        if len(samples) < 5:
            de = (title or {}).get("de", "")[:36]
            samples.append((de, len(desc.get("de") or "")))

    if not ops:
        log.info("Nothing to clean — no description carries builder markup.")
        return 0

    log.info("%d event(s) carry page-builder markup:", len(ops))
    for name, length in samples:
        log.info("    %-38s → %d characters of text", name, length)

    if not write:
        log.info("\nDry run. Re-run with --write to apply.")
        return len(ops)

    result = await db.events.bulk_write(ops, ordered=False)
    log.info("\nCleaned %d event(s).", result.modified_count)
    return result.modified_count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the changes")
    asyncio.run(run(ap.parse_args().write))


if __name__ == "__main__":
    main()
