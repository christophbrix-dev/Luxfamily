"""Seeds a starter set of Luxembourg event sources — communes + venues.

Coverage strategy:
  1. Big cultural venues (Philharmonie, Rockhal, Mudam, Neimënster, ...)
  2. All 12 canton capitals + biggest communes (Lux-City, Esch, Differdange,
     Dudelange, Bettembourg, Diekirch, Ettelbruck, Wiltz, Vianden, Mersch,
     Grevenmacher, Remich, Clervaux, Echternach, Bascharage, Kayl,
     Sanem, Pétange, Bertrange, Strassen).
  3. Cross-country aggregators (Visit Luxembourg, echo.lu, agenda.lu,
     Kulturkanner).

Every source is inserted with ``active=False``. Admins review them one by
one via /admin/sources, run the built-in robots-check, then flip active.

Idempotent: upserts by (name, url).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("seed-lu-sources")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Coordinates for common LU cities/venues.
LOC = {
    "lux": (49.6116, 6.1319),
    # Same point, spelled so src() derives "Luxembourg" rather than "Lux" —
    # town_names.canonical_town() would otherwise treat that as its own place.
    "luxembourg": (49.6116, 6.1319),
    "esch": (49.4953, 5.9764),
    "differdange": (49.5236, 5.8911),
    "dudelange": (49.4805, 6.0872),
    "bettembourg": (49.5179, 6.0922),
    "diekirch": (49.8683, 6.1553),
    "ettelbruck": (49.8478, 6.1050),
    "wiltz": (49.9667, 5.9333),
    "vianden": (49.9347, 6.2058),
    "mersch": (49.7500, 6.1000),
    "grevenmacher": (49.6789, 6.4419),
    "remich": (49.5450, 6.3672),
    "clervaux": (50.0553, 6.0286),
    "echternach": (49.7228, 6.4269),
    "petange": (49.5594, 5.8819),
    "sanem": (49.5433, 5.9425),
    "kayl": (49.4869, 6.0364),
    "bertrange": (49.6094, 6.0625),
    "strassen": (49.6181, 6.0780),
    "bascharage": (49.5675, 5.9061),
    "howald": (49.5808, 6.1244),
    "belval": (49.5025, 5.9489),
    "walferdange": (49.6608, 6.1336),
    "kirchberg": (49.6308, 6.1620),
    "niederanven": (49.6558, 6.2467),
    "hesperange": (49.5719, 6.1567),
    "leudelange": (49.5764, 6.0517),
    "lullange": (50.0608, 6.0028),
    "munshausen": (50.0050, 6.0639),
    "remerschen": (49.5012, 6.3633),
    "mullerthal": (49.7956, 6.3008),
}


def src(name, kind, url, canton, town_key, categories,
        age_min=0, age_max=99, selectors=None):
    lat, lng = LOC.get(town_key, LOC["lux"])
    return {
        "name": name, "kind": kind, "url": url,
        "canton_default": canton,
        "town_default": town_key.replace("_", " ").title(),
        "category_default": categories,
        "age_min_default": age_min, "age_max_default": age_max,
        "lat_default": lat, "lng_default": lng,
        "selectors": selectors,
    }


SOURCES = [
    # ============== VILLE DE LUXEMBOURG ==============
    # The capital publishes more than anyone else in the country and carries no
    # structured data at all — checked on both the listing and the detail
    # pages. So it gets the one thing per-site selectors are worth writing:
    # 365 event pages sit in its sitemap, and the agenda shows the day's
    # programme, which three runs a day accumulate.
    #
    # The date selector is deliberately the whole .media-date text rather than
    # span.start-date. On a multi-day entry that span holds "26.07" with the
    # year in a sibling, and on one entry the site itself writes "29.11.0206".
    # Read alone it yields July of this year, or the year 206. The full text
    # parses single-day entries correctly and returns nothing for ranges, so
    # those are skipped rather than filed under an invented date.
    src("Ville de Luxembourg — Agenda", "html_scraper",
        "https://www.vdl.lu/fr/agenda",
        "Luxembourg", "luxembourg", ["Culture", "Festivals"],
        selectors={
            "item": "a.media-event",
            "title": ".media-title",
            "date": ".media-date",
            # .place, not .media-category: the latter is the badge row
            # ("Cinéma Pour tous publics"), and stored as the town it made 28
            # events share one point and read "Cinéma" as a place name.
            "location": ".place",
            "link": "self",
        }),

    # ============== BIG VENUES ==============
    src("Philharmonie Luxembourg — Sitemap", "sitemap",
        "https://www.philharmonie.lu/sitemap.xml",
        "Luxembourg", "kirchberg", ["Culture", "Workshops"], age_min=6),
    src("Rockhal — Sitemap", "sitemap",
        "https://www.rockhal.lu/sitemap.xml",
        "Esch-sur-Alzette", "belval", ["Culture", "Festivals"], age_min=10),
    src("Mudam Luxembourg — Sitemap", "sitemap",
        "https://www.mudam.com/sitemap.xml",
        "Luxembourg", "kirchberg", ["Culture", "Workshops"], age_min=4),
    src("Neimënster Cultural Centre — Sitemap", "sitemap",
        "https://www.neimenster.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Workshops"]),
    src("Casino Luxembourg (Contemporary Art) — Sitemap", "sitemap",
        "https://www.casino-luxembourg.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Workshops"], age_min=6),
    src("Luxembourg City History Museum — Sitemap", "sitemap",
        "https://citymuseum.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture"], age_min=6),
    src("MNHA (National Museum of History & Art) — Sitemap", "sitemap",
        "https://www.mnha.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture"], age_min=6),
    src("CAPe Ettelbruck (Centre des Arts Pluriels) — Sitemap", "sitemap",
        "https://www.cape.lu/sitemap.xml",
        "Diekirch", "ettelbruck", ["Culture", "Workshops"]),
    src("Kulturfabrik Esch — Sitemap", "sitemap",
        "https://www.kulturfabrik.lu/sitemap.xml",
        "Esch-sur-Alzette", "esch", ["Culture", "Festivals"], age_min=10),
    src("opderschmelz Dudelange — Sitemap", "sitemap",
        "https://www.opderschmelz.lu/sitemap.xml",
        "Esch-sur-Alzette", "dudelange", ["Culture", "Festivals"], age_min=8),
    src("aalt Stadhaus Differdange — Sitemap", "sitemap",
        "https://www.stadhaus.lu/sitemap.xml",
        "Esch-sur-Alzette", "differdange", ["Culture"]),
    src("Grand Théâtre Luxembourg — Sitemap", "sitemap",
        "https://www.theatres.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture"], age_min=6),
    src("Ciné Utopia — Sitemap", "sitemap",
        "https://www.utopolis.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture"], age_min=6),
    src("Kulturhaus Niederanven — Sitemap", "sitemap",
        "https://www.khn.lu/sitemap.xml",
        "Luxembourg", "niederanven", ["Culture", "Workshops"], age_min=3),

    # ============== COMMUNES — CANTON CAPITALS ==============
    src("Ville de Luxembourg — Sitemap", "sitemap",
        "https://www.vdl.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Festivals"]),
    src("Ville d'Esch-sur-Alzette — Sitemap", "sitemap",
        "https://www.esch.lu/sitemap.xml",
        "Esch-sur-Alzette", "esch", ["Culture", "Festivals"]),
    src("Diekirch — Sitemap", "sitemap",
        "https://www.diekirch.lu/sitemap.xml",
        "Diekirch", "diekirch", ["Culture"]),
    src("Ettelbruck — Sitemap", "sitemap",
        "https://www.ettelbruck.lu/sitemap.xml",
        "Diekirch", "ettelbruck", ["Culture"]),
    src("Wiltz — Sitemap", "sitemap",
        "https://www.wiltz.lu/sitemap.xml",
        "Wiltz", "wiltz", ["Culture"]),
    src("Vianden — Sitemap", "sitemap",
        "https://www.vianden.lu/sitemap.xml",
        "Vianden", "vianden", ["Culture"]),
    src("Clervaux — Sitemap", "sitemap",
        "https://www.clervaux.lu/sitemap.xml",
        "Clervaux", "clervaux", ["Culture"]),
    src("Mersch — Sitemap", "sitemap",
        "https://www.mersch.lu/sitemap.xml",
        "Mersch", "mersch", ["Culture"]),
    src("Grevenmacher — Sitemap", "sitemap",
        "https://www.grevenmacher.lu/sitemap.xml",
        "Grevenmacher", "grevenmacher", ["Culture"]),
    src("Remich — Sitemap", "sitemap",
        "https://www.remich.lu/sitemap.xml",
        "Remich", "remich", ["Culture"]),
    src("Echternach — Sitemap", "sitemap",
        "https://www.echternach.lu/sitemap.xml",
        "Echternach", "echternach", ["Culture"]),

    # ============== COMMUNES — LARGER TOWNS ==============
    src("Differdange — Sitemap", "sitemap",
        "https://www.differdange.lu/sitemap.xml",
        "Esch-sur-Alzette", "differdange", ["Culture"]),
    src("Dudelange — Sitemap", "sitemap",
        "https://www.dudelange.lu/sitemap.xml",
        "Esch-sur-Alzette", "dudelange", ["Culture"]),
    src("Bettembourg — Sitemap", "sitemap",
        "https://www.bettembourg.lu/sitemap.xml",
        "Esch-sur-Alzette", "bettembourg", ["Culture"]),
    src("Pétange — Sitemap", "sitemap",
        "https://www.petange.lu/sitemap.xml",
        "Esch-sur-Alzette", "petange", ["Culture"]),
    src("Sanem — Sitemap", "sitemap",
        "https://www.sanem.lu/sitemap.xml",
        "Esch-sur-Alzette", "sanem", ["Culture"]),
    src("Kayl-Tétange — Sitemap", "sitemap",
        "https://www.kayl.lu/sitemap.xml",
        "Esch-sur-Alzette", "kayl", ["Culture"]),
    src("Käerjeng (Bascharage) — Sitemap", "sitemap",
        "https://www.kaerjeng.lu/sitemap.xml",
        "Capellen", "bascharage", ["Culture"]),
    src("Bertrange — Sitemap", "sitemap",
        "https://www.bertrange.lu/sitemap.xml",
        "Luxembourg", "bertrange", ["Culture"]),
    src("Strassen — Sitemap", "sitemap",
        "https://www.strassen.lu/sitemap.xml",
        "Luxembourg", "strassen", ["Culture"]),
    src("Hesperange — Sitemap", "sitemap",
        "https://www.hesperange.lu/sitemap.xml",
        "Luxembourg", "hesperange", ["Culture"]),
    src("Walferdange — Sitemap", "sitemap",
        "https://www.walfer.lu/sitemap.xml",
        "Luxembourg", "walferdange", ["Culture"]),
    src("Leudelange — Sitemap", "sitemap",
        "https://www.leudelange.lu/sitemap.xml",
        "Luxembourg", "leudelange", ["Culture"]),

    # ============== FAMILY / NATURE VENUES ==============
    src("Parc Merveilleux — Sitemap", "sitemap",
        "https://www.parc-merveilleux.lu/sitemap.xml",
        "Esch-sur-Alzette", "bettembourg", ["Animals", "Nature", "Playgrounds"],
        age_min=2, age_max=12),
    src("Park Sënnesräich — Sitemap", "sitemap",
        "https://www.sennesraich.lu/sitemap.xml",
        "Clervaux", "lullange", ["Nature", "Workshops"], age_min=3),
    src("Robbesscheier Munshausen — Sitemap", "sitemap",
        "https://www.robbesscheier.lu/sitemap.xml",
        "Clervaux", "munshausen", ["Animals", "Nature", "Workshops"], age_min=2),
    src("Luxembourg Science Center — Sitemap", "sitemap",
        "https://www.science-center.lu/sitemap.xml",
        "Esch-sur-Alzette", "differdange", ["Culture", "Workshops"], age_min=5),
    src("Naturmusée (MNHN) — Sitemap", "sitemap",
        "https://www.mnhn.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Nature"], age_min=4),

    # ============== AGGREGATORS ==============
    src("Visit Luxembourg — Sitemap", "sitemap",
        "https://www.visitluxembourg.com/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Festivals", "Nature"]),
    src("Kulturkanner (Kids agenda)", "sitemap",
        "https://www.kulturkanner.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Workshops"], age_min=3, age_max=12),
    src("echo.lu — Sitemap", "sitemap",
        "https://www.echo.lu/sitemap.xml",
        "Luxembourg", "lux", ["Culture", "Festivals"]),
]


async def main() -> None:
    log.info("Connecting to %s/%s", MONGO_URL, DB_NAME)
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo[DB_NAME]

    inserted = 0
    updated = 0
    for s in SOURCES:
        existing = await db.sources.find_one({"name": s["name"]}, {"_id": 0})
        if existing:
            await db.sources.update_one(
                {"id": existing["id"]},
                {"$set": {**s, "active": existing.get("active", False)}},
            )
            updated += 1
        else:
            doc = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "active": False,      # always start disabled
                "image_default": "",
                **s,
            }
            await db.sources.insert_one(doc)
            inserted += 1
            log.info("＋ %s", s["name"])

    total = await db.sources.count_documents({})
    log.info("Done. inserted=%d, updated=%d, total_sources=%d", inserted, updated, total)
    log.info("All new sources are INACTIVE — enable via /admin/sources after robots-check.")
    mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
