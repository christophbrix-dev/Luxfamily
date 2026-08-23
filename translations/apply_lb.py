#!/usr/bin/env python3
"""Write the Lëtzebuergesch column of translations/lb.csv back into the source.

Reads the filled-in CSV and inserts an `lb: "..."` entry into every matching
localized object in frontend/src/i18n/strings.ts and frontend/src/data/places.ts.
Rows with an empty Lëtzebuergesch cell are left alone, so the file can be filled
in over several sittings.

Run from the repository root:

    python3 translations/apply_lb.py            # show what would change
    python3 translations/apply_lb.py --write    # actually change the files

Re-running is safe: an existing lb value is replaced, never duplicated.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "translations" / "lb.csv"
STRINGS = ROOT / "frontend" / "src" / "i18n" / "strings.ts"
PLACES = ROOT / "frontend" / "src" / "data" / "places.ts"


def escape(value: str) -> str:
    """Escape a string for a double-quoted TypeScript literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def set_lb(block: str, value: str) -> str:
    """Put `lb: "value"` into one { en, de, fr } object literal.

    Inserted after `fr` so the key order stays en, de, fr, lb everywhere. The
    indentation of the `fr` line is reused, which keeps both the single-line and
    the multi-line spelling of these objects intact.
    """
    existing = re.search(r'(\blb:\s*)"(?:[^"\\]|\\.)*"', block)
    if existing:
        return block[: existing.start()] + f'{existing.group(1)}"{escape(value)}"' + block[existing.end():]

    fr = re.search(r'([ \t]*)(\bfr:\s*"(?:[^"\\]|\\.)*")(,?)', block)
    if not fr:
        return block
    indent, text, comma = fr.group(1), fr.group(2), fr.group(3)
    if "\n" in block:  # multi-line object: put lb on its own line
        replacement = f'{indent}{text},\n{indent}lb: "{escape(value)}"{comma or ","}'
    else:  # single-line object: keep it on one line
        replacement = f'{indent}{text}, lb: "{escape(value)}"{comma}'
    return block[: fr.start()] + replacement + block[fr.end():]


def apply_to_strings(src: str, rows: dict[str, str]) -> tuple[str, int, list[str]]:
    """Fill in interface strings by editing LB_OVERRIDES.

    Not by adding `lb:` to the STRINGS entry — t() reads LB_OVERRIDES and
    nothing else for Luxembourgish (see the `lang === "lb"` branch), so an
    inline value would be written, committed, and then silently ignored at
    runtime. Place data is the opposite case: pickLang() does read the inline
    field, which is why apply_to_places works the other way round.
    """
    applied, unmatched = 0, []
    marker = "const LB_OVERRIDES: Record<string, string> = {"
    if marker not in src:
        return src, 0, list(rows)
    head, rest = src.split(marker, 1)
    block, tail = rest.split("\n};", 1)

    for key, value in rows.items():
        existing = re.search(r'^([ \t]*)%s:(\s*)"(?:[^"\\]|\\.)*",?$'
                             % re.escape(key), block, re.M)
        if existing:
            indent, gap = existing.group(1), existing.group(2)
            block = (block[: existing.start()]
                     + f'{indent}{key}:{gap}"{escape(value)}",'
                     + block[existing.end():])
        else:
            block = block.rstrip() + f'\n  {key}: "{escape(value)}",'
        applied += 1

    return head + marker + block + "\n};" + tail, applied, unmatched


def apply_to_places(src: str, rows: dict[str, str]) -> tuple[str, int, list[str]]:
    """Fill in placeN.field keys. Returns (source, applied, unmatched)."""
    applied, unmatched = 0, []
    for key, value in rows.items():
        m = re.match(r"place(\d+)\.(\w+)$", key)
        if not m:
            unmatched.append(key)
            continue
        pid, field = m.group(1), m.group(2)
        # Narrow to the one place object carrying this id, then to its field.
        place = re.search(r"\n  \{\s*\n\s*id:\s*%s\b.*?\n  \}," % pid, src, re.S)
        if not place:
            unmatched.append(key)
            continue
        block = place.group(0)
        fm = re.search(r"(\b%s:\s*\{)(.*?)(\})" % re.escape(field), block, re.S)
        if not fm:
            unmatched.append(key)
            continue
        updated_field = set_lb(fm.group(2), value)
        if updated_field == fm.group(2):
            unmatched.append(key)
            continue
        new_block = block[: fm.start(2)] + updated_field + block[fm.end(2):]
        src = src[: place.start()] + new_block + src[place.end():]
        applied += 1
    return src, applied, unmatched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the files instead of previewing")
    ap.add_argument("--csv", type=Path, default=CSV_PATH, help="path to the filled-in CSV")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 1

    ui: dict[str, str] = {}
    places: dict[str, str] = {}
    blank = 0
    with args.csv.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            value = (row.get("Lëtzebuergesch") or "").strip()
            key = (row.get("Schlüssel") or "").strip()
            if not key:
                continue
            if not value:
                blank += 1
                continue
            # Route on the placeN.field shape, not a "place" prefix: there is
            # an interface key literally called `places` ("Plazen") that would
            # otherwise be mistaken for place data.
            (places if re.match(r"place\d+\.", key) else ui)[key] = value

    print(f"{len(ui) + len(places)} translated, {blank} still empty")

    strings_src = STRINGS.read_text(encoding="utf-8")
    places_src = PLACES.read_text(encoding="utf-8")
    strings_out, n_ui, miss_ui = apply_to_strings(strings_src, ui)
    places_out, n_pl, miss_pl = apply_to_places(places_src, places)

    print(f"  strings.ts: {n_ui}/{len(ui)}")
    print(f"  places.ts:  {n_pl}/{len(places)}")

    missing = miss_ui + miss_pl
    if missing:
        # A key that no longer exists means the CSV and the code have drifted.
        # Refuse rather than silently dropping someone's translation work.
        print(f"\n{len(missing)} key(s) not found in the source — nothing written:")
        for key in missing[:20]:
            print(f"  {key}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        print("\nRegenerate the CSV, or check whether these keys were renamed.")
        return 1

    if not args.write:
        print("\nPreview only. Re-run with --write to apply.")
        return 0

    STRINGS.write_text(strings_out, encoding="utf-8")
    PLACES.write_text(places_out, encoding="utf-8")
    print("\nWritten. Check with: cd frontend && yarn typecheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
