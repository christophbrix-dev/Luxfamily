#!/usr/bin/env python3
"""Tidy the text of already-stored events: markup, then padding.

The importers clean from now on, but events imported before that keep what
their source wrote, and re-crawling does not fix them — dedup matches on
external_id, so an event already stored is never rewritten.

Two things are removed. Page-builder markup: 51 of 354 descriptions read like

    [et_pb_section fb_built="1" _builder_version="4.24.2"][et_pb_row …]

with the real text buried inside or absent, all from communes running Divi.
And padding, which arrives with no markup at all — one commune's feed sends

    "      \xa0    Orchestre des Jeunes de l'Est    Bech-Berbuerger Musek"

Across the live database that was 294 fields with runs of spaces, 219 with
edge whitespace and 78 carrying a non-breaking space.

    python3 clean_descriptions.py            # show what would change
    python3 clean_descriptions.py --write    # change it

All three text fields are handled — title, short and description. Two earlier
versions of this script each covered fewer: one bailed out when the
description was already clean and left 27 padded titles behind, and the next
rebuilt `short` only as a by-product of a changed description, leaving 42.
Both reported success. Where a description is markup end to end, the title
takes its place: an empty field is more honest than a wall of shortcodes.

Safe to run twice — the second run reports nothing to do.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from db_config import mongo_settings
from importers import _normalise_text, _strip_page_builder

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
        # Shortcodes first, then the padding they leave behind — and the
        # padding that arrives without any markup at all: one commune's feed
        # sends "      \xa0    Orchestre des Jeunes    Bech-Berbuerger Musek".
        cleaned = _normalise_text(_strip_page_builder(value))
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
        # The title is cleaned too. An earlier version only looked at the
        # description and bailed out when that was already clean, so 27 padded
        # titles survived a run that reported success — the field a reader
        # sees first was the one field never checked.
        new_title = _clean_localized(title, None)
        desc = _clean_localized(ev.get("description"), new_title or title)

        update: dict = {}
        if new_title is not None:
            update["title"] = new_title
        if desc is not None:
            update["description"] = desc
            # Rebuild `short` from the cleaned description rather than cleaning
            # it separately: it is a truncation of that text and should stay one.
            short = {
                lang: (desc.get(lang) or "")[:SHORT_LEN]
                for lang in LANGS
                if isinstance((ev.get("short") or {}).get(lang), str)
            }
            if short:
                update["short"] = short

        if "short" not in update:
            # `short` is normally a truncation of the description and gets
            # rebuilt above. When the description was already clean it was
            # never looked at, and 42 of them kept their own padding — the
            # text the list screen shows, cleaned nowhere.
            own_short = _clean_localized(ev.get("short"), None)
            if own_short is not None:
                update["short"] = own_short

        if not update:
            continue
        ops.append(UpdateOne({"_id": ev["_id"]}, {"$set": update}))

        if len(samples) < 5:
            de = ((new_title or title) or {}).get("de", "")[:36]
            samples.append((de, len((desc or {}).get("de") or "")))

    if not ops:
        log.info("Nothing to clean — no description carries markup or padding.")
        return 0

    log.info("%d event(s) carry builder markup or padding:", len(ops))
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
