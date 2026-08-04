"""Seed script: replace all events with user-curated "Deep Dive" data.

Usage:
    cd /app/backend && python seed_deepdive.py

What it does:
1. Drops the entire `events` collection.
2. For each curated location, attempts to scrape an og:image / twitter:image
   from the official website URL (falls back to a sensible Unsplash image).
3. Inserts a fully-populated EventBase document into MongoDB.

Designed to be idempotent: running it again will re-fetch images and overwrite
everything.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("seed-deepdive")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Today's date — used as the "start date" so every entry is visible/upcoming.
TODAY = datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# og:image scraper
# ---------------------------------------------------------------------------
async def fetch_og_image(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Return an absolute image URL extracted from the page's OpenGraph tags."""
    try:
        r = await client.get(url, follow_redirects=True, timeout=12.0,
                             headers={"User-Agent": "Mozilla/5.0 (LuxFamilyBot/1.0)"})
        r.raise_for_status()
    except Exception as e:
        log.warning("fetch %s failed: %s", url, e)
        return None

    soup = BeautifulSoup(r.text, "lxml")
    candidates = [
        soup.find("meta", attrs={"property": "og:image"}),
        soup.find("meta", attrs={"property": "og:image:url"}),
        soup.find("meta", attrs={"name": "twitter:image"}),
        soup.find("meta", attrs={"name": "twitter:image:src"}),
    ]
    for tag in candidates:
        if tag and tag.get("content"):
            img = tag["content"].strip()
            if img.startswith("//"):
                img = "https:" + img
            elif img.startswith("/"):
                from urllib.parse import urljoin
                img = urljoin(url, img)
            return img

    # last fallback: first non-tiny <img> on page
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src", "")
        if src and not src.endswith(".svg") and "logo" not in src.lower():
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                from urllib.parse import urljoin
                return urljoin(url, src)
            if src.startswith("http"):
                return src
    return None


# ---------------------------------------------------------------------------
# Curated data
# ---------------------------------------------------------------------------
def l(en: str, de: str, fr: str) -> Dict[str, str]:
    return {"en": en, "de": de, "fr": fr}


LOCATIONS: List[Dict[str, Any]] = [
    # 1
    {
        "title": l("Parc Merveilleux Bettembourg", "Parc Merveilleux Bettemburg", "Parc Merveilleux Bettembourg"),
        "short": l(
            "Animal park, fairytale forest, playgrounds.",
            "Tierpark, Märchenwald, Spielplätze.",
            "Parc animalier, forêt de contes, aires de jeux.",
        ),
        "description": l(
            "A large adventure park combining fairytale scenes, animal enclosures, a water playground and rides. Easy Language info and accessibility statement on site. Tip: arrive at 10 AM on weekdays to avoid crowds.",
            "Großer Abenteuerpark mit Märchenwald, Tiergehegen, Wasserspielplatz und Fahrgeschäften. Bietet aktiv Informationen in Easy Language an. Tipp: an Wochentagen früh (10 Uhr) kommen.",
            "Grand parc d'aventure avec scènes de contes, enclos d'animaux, aire de jeux aquatique et manèges. Information en langage facile disponible. Astuce : venez tôt (10h) en semaine.",
        ),
        "type": "Outdoor", "canton": "Esch-sur-Alzette", "town": "Bettembourg",
        "category": ["Animals", "Nature", "Playgrounds"],
        "age_min": 2, "age_max": 12,
        "time": "10:00 - 19:00",
        "price_adult": 15.0, "price_child": 11.0,
        "price_label": l("EUR 15 / adult · EUR 11 / child (under 3 free)",
                          "15 € / Erw. · 11 € / Kind (unter 3 gratis)",
                          "15 € / adulte · 11 € / enfant (moins de 3 ans gratuit)"),
        "accessibility": l("Stroller friendly, paved paths", "Kinderwagenfreundlich, befestigte Wege",
                            "Accessible poussette, allées pavées"),
        "weather_fit": l("Best on sunny days", "Am besten an sonnigen Tagen", "Idéal par temps ensoleillé"),
        "lat": 49.5179, "lng": 6.0922,
        "website_url": "https://www.parc-merveilleux.lu/en/your-park-visit/entry-fee",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l(
            "Medium. Lots of space to retreat, but loud rides on summer weekends. Arrive early or pick a weekday.",
            "Mittel. Viel Platz zum Ausweichen, aber laut an Sommer-Wochenenden. Früh kommen oder Wochentag wählen.",
            "Moyen. Beaucoup d'espace, mais bruyant les week-ends d'été. Venir tôt ou en semaine.",
        ),
        "parking": l("Free. Large forest lot currently closed — use street parking; arrive early on peak days.",
                      "Gratis. Großer Waldparkplatz ist aktuell gesperrt — Straßenparkplätze nutzen; an Spitzentagen früh kommen.",
                      "Gratuit. Grand parking forestier fermé — utilisez le stationnement en bord de route ; venez tôt aux heures de pointe."),
        "food_allowed": True,
        "food_onsite": l("À la carte restaurant (400 seats), self-service cafeteria, food stalls. Picnic tolerated.",
                          "À-la-carte-Restaurant (400 Plätze), Self-Service-Cafeteria, Stände. Picknick wird geduldet.",
                          "Restaurant à la carte (400 places), cafétéria self-service, stands. Pique-nique toléré."),
        "preparation_tips": l(
            "Sturdy shoes (gravel/forest paths). In summer: swimwear, towel & change of clothes for the water playground. Stroller OK.",
            "Feste Schuhe (Kies-/Waldwege). Im Sommer: Badesachen, Handtuch, Wechselkleidung für den Wasserspielplatz. Kinderwagen problemlos.",
            "Chaussures solides (graviers/forêt). En été : maillot, serviette, vêtements de rechange pour l'aire aquatique. Poussette OK.",
        ),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily, March–October, 09:30–18:00", "Täglich, März–Oktober, 09:30–18:00",
                            "Tous les jours, mars-octobre, 09h30-18h00"),
        "peak_hours": l("Weekends 12:00–16:00", "Wochenenden 12:00–16:00", "Week-ends 12h00-16h00"),
        "changing_facilities": True, "restrooms": True,
    },
    # 2
    {
        "title": l("Escher Déierepark (Galgenberg)", "Escher Déierepark (Galgenberg)", "Parc Animalier d'Esch (Galgenberg)"),
        "short": l("Small, quiet forest animal park — top pick for sensitive kids.",
                    "Kleiner, ruhiger Waldtierpark — Top für reizempfindliche Kinder.",
                    "Petit parc animalier forestier — idéal pour enfants sensibles."),
        "description": l(
            "Free forest park with deer, Highland cattle, raccoons, guinea pigs (~150 animals). Walkable layout, never crowded. Two playgrounds along the way.",
            "Gratis Waldpark mit Damwild, Highland-Rindern, Waschbären, Meerschweinchen (~150 Tiere). Begehbar, nie überlaufen. Zwei Spielplätze entlang des Wegs.",
            "Parc forestier gratuit avec daims, vaches Highland, ratons laveurs, cochons d'Inde (~150 animaux). Jamais surchargé. Deux aires de jeux le long du chemin.",
        ),
        "type": "Outdoor", "canton": "Esch-sur-Alzette", "town": "Esch-sur-Alzette",
        "category": ["Animals", "Nature"],
        "age_min": 0, "age_max": 14,
        "time": "24/7 year-round",
        "price_adult": 0.0, "price_child": 0.0,
        "price_label": l("Free", "Kostenlos", "Gratuit"),
        "accessibility": l("Partially — hilly forest paths; Gaalgebus shuttle helps.",
                            "Teilweise — hügeliges Waldgelände; der Gaalgebus-Shuttle hilft.",
                            "Partiel — sentiers forestiers vallonnés ; navette Gaalgebus disponible."),
        "weather_fit": l("Cool forest, great in summer heat", "Kühler Wald, ideal bei Hitze",
                          "Forêt fraîche, idéale par chaleur"),
        "lat": 49.4953, "lng": 5.9764,
        "website_url": "https://deierepark.esch.lu/en/home/",
        "accessibility_wheelchair": False,
        "sensory_friendly": True,
        "free_parking": True,
        "sensory_notes": l("Very good. Quiet, no loud tech, never crowded.",
                            "Sehr gut. Ruhig, keine laute Technik, nie überlaufen.",
                            "Très bon. Calme, pas de technique bruyante, jamais bondé."),
        "parking": l("Limited free parking at access points. Gaalgebus shuttle from Esch station, stop C1, 11:30–18:30.",
                      "Begrenzte Gratis-Parkflächen an Zugängen. Gaalgebus-Shuttle ab Bahnhof Esch (Stop C1) 11:30–18:30.",
                      "Stationnement gratuit limité. Navette Gaalgebus depuis la gare d'Esch (arrêt C1) 11h30-18h30."),
        "food_allowed": True,
        "food_onsite": l("Bamhauscafé on site. Picnic possible.",
                          "Bamhauscafé vor Ort. Picknick problemlos möglich.",
                          "Bamhauscafé sur place. Pique-nique possible."),
        "preparation_tips": l("Comfortable shoes (forest paths, hilly). Stroller works but it goes up/down. Weather-appropriate clothing.",
                                "Bequeme Schuhe (Waldwege, hügelig). Kinderwagen geht, aber bergauf/bergab. Wetterfeste Kleidung.",
                                "Chaussures confortables (sentiers vallonnés). Poussette possible mais en pente. Vêtements adaptés."),
        "payment_methods": [],
        "opening_hours": l("Open 24/7, year-round", "Ganzjährig 24/7 geöffnet", "Ouvert 24h/24, toute l'année"),
        "peak_hours": l("Sunny weekend afternoons", "Sonnige Wochenend-Nachmittage", "Week-ends ensoleillés après-midi"),
        "changing_facilities": False, "restrooms": True,
    },
    # 3
    {
        "title": l("Naturmusée (National Museum of Natural History)",
                    "Naturmusée (Nationalmuseum für Naturgeschichte)",
                    "Naturmusée (Musée National d'Histoire Naturelle)"),
        "short": l("Interactive natural-history museum, free for under-18s.",
                    "Interaktives Naturkundemuseum, gratis für unter 18.",
                    "Musée d'histoire naturelle interactif, gratuit pour les moins de 18 ans."),
        "description": l(
            "Multi-floor interactive museum in the Grund (old town valley) on the Alzette. Panda-Club / Science-Club programs for kids. Combine with a riverside walk afterwards.",
            "Mehrstöckiges interaktives Museum im Grund (Altstadt-Tal) an der Alzette. Panda-Club / Science-Club für Kinder. Hinterher Spaziergang am Wasser.",
            "Musée interactif sur plusieurs étages dans le Grund, sur l'Alzette. Panda-Club / Science-Club pour enfants. Promenade fluviale possible après.",
        ),
        "type": "Educational", "canton": "Luxembourg", "town": "Luxembourg City",
        "category": ["Culture", "Nature"],
        "age_min": 4, "age_max": 14,
        "time": "10:00 - 18:00 (closed Mondays)",
        "price_adult": 5.0, "price_child": 0.0,
        "price_label": l("EUR 5 / adult · under-18 free",
                          "5 € / Erw. · unter 18 gratis",
                          "5 € / adulte · moins de 18 ans gratuit"),
        "accessibility": l("Barrier-free, lift available", "Barrierefrei, Aufzug vorhanden",
                            "Accessible, ascenseur disponible"),
        "weather_fit": l("Great rainy-day option", "Tolle Schlechtwetter-Option", "Excellente option pluvieuse"),
        "lat": 49.6126, "lng": 6.1399,
        "website_url": "https://www.mnhn.lu/",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": False,
        "sensory_notes": l("Medium-good. Indoor & interactive but busy in rain/school holidays. Some quieter corners.",
                            "Mittel-gut. Indoor & interaktiv, aber bei Regen/Ferien voll. Einzelne ruhige Ecken.",
                            "Moyen-bon. Intérieur & interactif mais bondé sous la pluie/vacances scolaires."),
        "parking": l("Hard in the Grund. Park at St-Esprit garage above + lift down, or use free Lux-City public transport.",
                      "Schwierig im Grund. Am besten Parkhaus St-Esprit oben + Aufzug runter, oder ÖPNV (gratis).",
                      "Difficile dans le Grund. Parking St-Esprit + ascenseur, ou transports publics gratuits."),
        "food_allowed": False,
        "food_onsite": l("Café/bistro in the neighbourhood; many Grund restaurants nearby.",
                          "Café/Bistro im Viertel; viele Restaurants im Grund.",
                          "Café/bistrot dans le quartier ; nombreux restaurants dans le Grund."),
        "preparation_tips": l("Normal city clothes. Stroller OK (modern museum, lift).",
                                "Normale Stadtkleidung. Kinderwagen kein Problem (Aufzug).",
                                "Tenue urbaine normale. Poussette OK (ascenseur)."),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Tue–Sun 10:00–18:00, Mondays closed", "Di–So 10:00–18:00, montags geschlossen",
                            "Mar-dim 10h-18h, fermé le lundi"),
        "peak_hours": l("Rainy weekends, school holidays", "Regnerische Wochenenden, Schulferien",
                          "Week-ends pluvieux, vacances scolaires"),
        "changing_facilities": True, "restrooms": True,
    },
    # 4
    {
        "title": l("Luxembourg Science Center", "Luxembourg Science Center", "Luxembourg Science Center"),
        "short": l("Hands-on science with 100+ experiments.",
                    "Mitmach-Wissenschaft mit 100+ Experimenten.",
                    "Science interactive avec 100+ expériences."),
        "description": l(
            "Hands-on science center: lots of buttons, experiments and shows. Great for curious and action-seeking kids. Mostly indoor — perfect rainy-day target.",
            "Mitmach-Wissenschaftszentrum: viele Knöpfe, Experimente und Shows. Toll für neugierige, aktive Kinder. Großteils Indoor — perfektes Schlechtwetter-Ziel.",
            "Centre scientifique interactif : boutons, expériences et spectacles. Idéal enfants curieux et actifs. Intérieur — parfait pour jours de pluie.",
        ),
        "type": "Educational", "canton": "Esch-sur-Alzette", "town": "Differdange",
        "category": ["Culture", "Workshops"],
        "age_min": 5, "age_max": 16,
        "time": "Weekdays 09:00-17:00 · Weekends 10:00-18:00",
        "price_adult": 13.0, "price_child": 9.0,
        "price_label": l("EUR 13 / adult · EUR 9 / child",
                          "13 € / Erw. · 9 € / Kind",
                          "13 € / adulte · 9 € / enfant"),
        "accessibility": l("Barrier-free, height-adjustable stations",
                            "Barrierefrei, Geräte höhenverstellbar",
                            "Accessible, stations réglables en hauteur"),
        "weather_fit": l("Perfect rainy-day option", "Perfektes Schlechtwetter-Ziel", "Parfait pour la pluie"),
        "lat": 49.5236, "lng": 5.8911,
        "website_url": "https://www.science-center.lu/en/useful-info",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l("High-stimulation: loud, many buttons, shows. Bring ear protection for noise-sensitive kids.",
                            "Reizintensiv: laut, viele Knöpfe, Shows. Gehörschutz für geräuschempfindliche Kinder mitnehmen.",
                            "Très stimulant : bruyant, beaucoup de boutons, spectacles. Apportez une protection auditive."),
        "parking": l("Public parking available nearby, free.",
                      "Öffentliche Parkplätze in der Nähe, gratis.",
                      "Stationnement public gratuit à proximité."),
        "food_allowed": True,
        "food_onsite": l("Picnic area on site. Restaurants in the adjacent shopping centre.",
                          "Picknickbereich vorhanden. Restaurants im Einkaufszentrum nebenan.",
                          "Aire de pique-nique. Restaurants dans le centre commercial voisin."),
        "preparation_tips": l("Normal clothing; stroller OK. Bring ear protection for sensitive kids.",
                                "Normale Kleidung; Kinderwagen ok. Gehörschutz für sensible Kinder.",
                                "Tenue normale ; poussette OK. Protection auditive recommandée."),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Mon-Fri 09:00-17:00 · Sat-Sun & holidays 10:00-18:00",
                            "Mo-Fr 09:00-17:00 · Sa-So/Feiertage 10:00-18:00",
                            "Lun-ven 09h-17h · Sam-dim/jours fériés 10h-18h"),
        "peak_hours": l("Weekend afternoons", "Wochenend-Nachmittage", "Après-midi week-end"),
        "changing_facilities": True, "restrooms": True,
    },
    # 5
    {
        "title": l("Park Sënnesräich (Sensory Park)", "Park Sënnesräich (Sinnespark)", "Park Sënnesräich (Parc des sens)"),
        "short": l("The only park in Luxembourg designed around the five senses.",
                    "Der einzige Park in Luxemburg, konzipiert um die fünf Sinne.",
                    "Le seul parc luxembourgeois conçu autour des cinq sens."),
        "description": l(
            "35+ experiment stations, barefoot path, hedge maze; plus indoor sensory museum and 10×10m Airtramp. Outdoor + indoor — flexible regardless of weather.",
            "35+ Experimentierstationen, Barfußpfad, Heckenlabyrinth; dazu Sinnesmuseum + 10×10m Airtramp indoor. Indoor & Outdoor — wetterunabhängig flexibel.",
            "35+ stations d'expérimentation, sentier pieds nus, labyrinthe. Musée des sens et Airtramp 10×10m intérieurs. Flexible par tous les temps.",
        ),
        "type": "Outdoor", "canton": "Clervaux", "town": "Lullange",
        "category": ["Nature", "Workshops", "Playgrounds"],
        "age_min": 3, "age_max": 14,
        "time": "10:00 - 18:00",
        "price_adult": 7.50, "price_child": 5.50,
        "price_label": l("EUR 7.50 adult · 5.50 child (5-12) · under-5 free",
                          "7,50 € Erw. · 5,50 € Kind (5-12) · unter 5 gratis",
                          "7,50 € adulte · 5,50 € enfant (5-12) · moins de 5 ans gratuit"),
        "accessibility": l("Partial — outdoor terrain is natural, ask in advance",
                            "Teilweise — Außengelände naturnah, vor Anreise anfragen",
                            "Partiel — terrain extérieur naturel, contactez avant la visite"),
        "weather_fit": l("Indoor + outdoor — works in any weather",
                          "Indoor & Outdoor — bei jedem Wetter",
                          "Intérieur et extérieur — par tous les temps"),
        "lat": 50.0608, "lng": 6.0028,
        "website_url": "https://www.sennesraich.lu/de/",
        "accessibility_wheelchair": False,
        "sensory_friendly": True,
        "free_parking": True,
        "sensory_notes": l(
            "Conceptually ideal — built around sensory exploration. Airtramp can be lively on full days; steerable by doing stations one at a time.",
            "Konzeptionell ideal — auf die fünf Sinne ausgelegt. Airtramp kann an vollen Tagen trubelig sein; steuerbar, wenn man Stationen einzeln angeht.",
            "Conceptuellement idéal — autour des cinq sens. Airtramp peut être agité ; gérable en faisant les stations une par une.",
        ),
        "parking": l("Free, directly in front of the entrance.",
                      "Gratis, direkt vor dem Eingang.",
                      "Gratuit, directement devant l'entrée."),
        "food_allowed": True,
        "food_onsite": l("Bistro Sënnesräich with terrace overlooking the play area; regional & seasonal.",
                          "Bistro Sënnesräich mit Terrasse und Blick auf Spielbereich; regional & saisonal.",
                          "Bistrot Sënnesräich avec terrasse sur l'aire de jeux ; régional et saisonnier."),
        "preparation_tips": l(
            "Spare socks/towel for the barefoot path. Outdoor sections — check weather. Stroller OK outdoors.",
            "Wechselsocken/Handtuch für den Barfußpfad. Außenteile — Wetter beachten. Kinderwagen draußen ok.",
            "Chaussettes/serviette pour le sentier pieds nus. Vérifier la météo. Poussette OK en extérieur.",
        ),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Easter–early November, Tue–Sun 10:00–18:00",
                            "Ostern–Anfang November, Di–So 10:00–18:00",
                            "Pâques-début novembre, mar-dim 10h-18h"),
        "peak_hours": l("School holidays afternoons", "Schulferien-Nachmittage",
                          "Après-midi vacances scolaires"),
        "changing_facilities": True, "restrooms": True,
    },
    # 6
    {
        "title": l("Biodiversum Haff Réimech", "Biodiversum Haff Réimech", "Biodiversum Haff Réimech"),
        "short": l("Quiet nature reserve + interactive exhibition on a Moselle island.",
                    "Ruhiges Naturschutzzentrum + interaktive Ausstellung auf einer Mosel-Insel.",
                    "Réserve naturelle calme + expo interactive sur une île de la Moselle."),
        "description": l(
            "20 interactive stations over 3 floors, plus quiet bird & lake trails. Combination of indoor exhibition + outdoor reserve — good in changeable weather.",
            "20 interaktive Stationen über 3 Etagen, dazu stille Naturpfade mit Vögeln/Seen. Kombi aus Indoor + Outdoor — gut bei wechselhaftem Wetter.",
            "20 stations interactives sur 3 étages + sentiers calmes (oiseaux/lacs). Intérieur + extérieur — idéal en météo changeante.",
        ),
        "type": "Educational", "canton": "Remich", "town": "Remerschen",
        "category": ["Nature", "Culture"],
        "age_min": 4, "age_max": 14,
        "time": "10:00 - 17:00 (closed Mondays)",
        "price_adult": 5.0, "price_child": 0.0,
        "price_label": l("EUR 5 / adult · under-18 free",
                          "5 € / Erw. · unter 18 gratis",
                          "5 € / adulte · moins de 18 ans gratuit"),
        "accessibility": l("Centre modern & accessible; some nature trails are natural surface",
                            "Zentrum modern & zugänglich; Naturpfade teils naturbelassen",
                            "Centre moderne et accessible ; certains sentiers en surface naturelle"),
        "weather_fit": l("Works in any weather (indoor + outdoor)",
                          "Bei jedem Wetter (Indoor + Outdoor)",
                          "Par tous les temps (intérieur + extérieur)"),
        "lat": 49.5012, "lng": 6.3633,
        "website_url": "https://www.visitluxembourg.com/de/attraktion/biodiversum-haff-reimech",
        "accessibility_wheelchair": True,
        "sensory_friendly": True,
        "free_parking": True,
        "sensory_notes": l("Very good. Quiet, spacious, little noise. Lots of openness.",
                            "Sehr gut. Ruhig, weitläufig, wenig Lärm. Viel Weite.",
                            "Très bon. Calme, spacieux, peu de bruit. Très ouvert."),
        "parking": l("Parking at the reserve, free.",
                      "Parkplatz am Reservat, gratis.",
                      "Stationnement gratuit à la réserve."),
        "food_allowed": True,
        "food_onsite": l("Limited on-site — bring a picnic; Remich/Schengen have nearby restaurants.",
                          "Vor Ort begrenzt — Picknick einplanen; Remich/Schengen mit Lokalen in der Nähe.",
                          "Limité sur place — apportez un pique-nique ; restaurants à Remich/Schengen."),
        "preparation_tips": l(
            "Sturdy shoes for nature trails. Binoculars (birds). Stroller OK in centre; some trails 3-4h — pick shorter ones.",
            "Feste Schuhe für Naturpfade. Fernglas (Vögel). Kinderwagen im Zentrum ja; manche Wege 3-4h — kürzere wählen.",
            "Chaussures solides. Jumelles (oiseaux). Poussette dans le centre ; certains sentiers 3-4h — choisir court.",
        ),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Tue-Sun 10:00-17:00, Mondays closed",
                            "Di-So 10:00-17:00, montags geschlossen",
                            "Mar-dim 10h-17h, fermé le lundi"),
        "peak_hours": l("Spring weekends (bird migration)",
                          "Frühlings-Wochenenden (Vogelzug)",
                          "Week-ends de printemps (migration)"),
        "changing_facilities": True, "restrooms": True,
    },
    # 7
    {
        "title": l("Robbesscheier Munshausen (Adventure Farm)",
                    "Robbesscheier Munshausen (Erlebnisbauernhof)",
                    "Robbesscheier Munshausen (Ferme découverte)"),
        "short": l("6-hectare adventure farm with hands-on crafts and animals.",
                    "6-ha Erlebnisbauernhof mit Handwerks-Ateliers und Tieren.",
                    "Ferme découverte de 6 ha avec ateliers d'artisanat et animaux."),
        "description": l(
            "Spacious site with animals to touch, craft workshops, donkey riding and covered-wagon rides. Smart pricing: free if you only walk around, pay only for workshops/activities. Restaurant with vegetarian/gluten-free/lactose-free options.",
            "Weitläufiges Gelände, Tiere zum Anfassen, Handwerks-Ateliers, Eselreiten und Planwagenfahrt. Cleveres Preismodell: kostenlos wer spaziert, Festpreis nur für Aktivitäten. Restaurant mit veg/glutenfrei/laktosefrei.",
            "Site spacieux avec animaux, ateliers d'artisanat, balades à dos d'âne et en chariot. Gratuit pour la promenade ; payant pour les ateliers. Restaurant avec options veg/sans gluten/sans lactose.",
        ),
        "type": "Outdoor", "canton": "Clervaux", "town": "Munshausen",
        "category": ["Animals", "Nature", "Workshops"],
        "age_min": 2, "age_max": 14,
        "time": "10:00 - 17:00",
        "price_adult": 0.0, "price_child": 0.0,
        "price_label": l("Free to walk around · pay per activity",
                          "Gratis zum Spazieren · zahlen nur für Aktivitäten",
                          "Promenade gratuite · payant par activité"),
        "accessibility": l("Partial — cobblestone access with 8% slope; metal ramp, restaurant wheelchair-accessible",
                            "Teilweise — Kopfsteinpflaster mit 8% Gefälle; Metallrampe, Restaurant rollstuhlzugänglich",
                            "Partiel — pavés avec pente 8% ; rampe métallique, restaurant accessible PMR"),
        "weather_fit": l("Mostly outdoor — pick a dry day",
                          "Meist Outdoor — trockenen Tag wählen",
                          "Surtout extérieur — privilégier un jour sec"),
        "lat": 50.0050, "lng": 6.0639,
        "website_url": "https://www.robbesscheier.lu/de/apropos-robbesscheier",
        "accessibility_wheelchair": True,
        "sensory_friendly": True,
        "free_parking": True,
        "sensory_notes": l(
            "Good. Spacious, animals to touch, calm pace. Donkey rides and wagon tours are gentle, well-dosed stimuli.",
            "Gut. Weitläufig, Tiere zum Anfassen, ruhiges Tempo. Eselreiten/Planwagen sind sanfte Reize.",
            "Bon. Spacieux, animaux à toucher, rythme calme. Promenades en âne/chariot : stimuli doux.",
        ),
        "parking": l("On-site parking, free.", "Vor Ort vorhanden, gratis.", "Stationnement gratuit sur place."),
        "food_allowed": True,
        "food_onsite": l("Family restaurant — regional dishes; vegetarian, gluten-free, lactose-free options.",
                          "Familienfreundliches Restaurant — regionale Gerichte; vegetarisch, glutenfrei, laktosefrei.",
                          "Restaurant familial — plats régionaux ; veg, sans gluten, sans lactose."),
        "preparation_tips": l(
            "Sturdy/dirt-tolerant shoes (farm, animals). Spare clothes for little ones. Stroller OK.",
            "Feste/schmutzunempfindliche Schuhe (Bauernhof, Tiere). Wechselkleidung. Kinderwagen ok.",
            "Chaussures solides (ferme). Vêtements de rechange. Poussette OK.",
        ),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Apr-Oct, Tue-Sun 10:00-17:00", "Apr-Okt, Di-So 10:00-17:00",
                            "Avr-oct, mar-dim 10h-17h"),
        "peak_hours": l("Weekend afternoons", "Wochenend-Nachmittage", "Après-midi week-end"),
        "changing_facilities": True, "restrooms": True,
    },
    # 8
    {
        "title": l("Vianden Castle + Chairlift", "Schloss Vianden + Sessellift", "Château de Vianden + Télésiège"),
        "short": l("Medieval castle and open 2-seater chairlift, 440m.",
                    "Mittelalterliche Burg und offener Zweisitzer-Sessellift, 440m.",
                    "Château médiéval et télésiège 2 places, 440m."),
        "description": l(
            "Iconic castle, separate ticket for chairlift. Café terrace at the top with view of castle and valley. Many restaurants in the old town along the Our.",
            "Ikonische Burg, separates Sessellift-Ticket. Café-Terrasse oben mit Blick auf Burg/Tal. Viele Restaurants in der Altstadt an der Our.",
            "Château emblématique, ticket télésiège séparé. Café en terrasse au sommet. Nombreux restaurants en vieille ville sur l'Our.",
        ),
        "type": "Outdoor", "canton": "Diekirch", "town": "Vianden",
        "category": ["Culture", "Nature"],
        "age_min": 4, "age_max": 99,
        "time": "10:00 - 18:00",
        "price_adult": 9.0, "price_child": 4.5,
        "price_label": l("Chairlift: EUR 9 return · Castle ticket separate",
                          "Sessellift: 9 € hin/zurück · Burg-Ticket separat",
                          "Télésiège : 9 € A/R · Château billet séparé"),
        "accessibility": l("Limited — medieval castle with stairs; chairlift not wheelchair-accessible",
                            "Eingeschränkt — Mittelalterburg mit Treppen; Sessellift nicht rollstuhlgeeignet",
                            "Limité — château médiéval avec escaliers ; télésiège non accessible PMR"),
        "weather_fit": l("Dry weather best — outdoor walking & open chairlift",
                          "Trockenes Wetter — Outdoor & offener Sessellift",
                          "Temps sec idéal — extérieur et télésiège ouvert"),
        "lat": 49.9347, "lng": 6.2058,
        "website_url": "https://www.visitluxembourg.com/de/attraktion/sessellift-vianden",
        "accessibility_wheelchair": False,
        "sensory_friendly": False,
        "free_parking": False,
        "sensory_notes": l(
            "Medium. Castle can be cramped/echoey and busy; open chairlift may worry height-sensitive kids — a highlight for others.",
            "Mittel. Burg kann eng/voll und akustisch hallig sein; offener Sessellift evtl. heikel für höhen-/reizempfindliche Kinder.",
            "Moyen. Château peut être bondé et résonner ; télésiège ouvert : prudence avec les enfants sensibles aux hauteurs.",
        ),
        "parking": l("Paid lots in the lower town; castle is uphill on foot or by shuttle/chairlift.",
                      "Parkplätze unten in Vianden (teils kostenpflichtig); Burg zu Fuß bergauf oder per Shuttle/Sessellift.",
                      "Parkings payants en bas-ville ; château accessible à pied ou par navette/télésiège."),
        "food_allowed": True,
        "food_onsite": l("Many restaurants/cafés in the old town; café at chairlift top station.",
                          "Viele Restaurants/Cafés in der Altstadt; Café an der Bergstation.",
                          "Nombreux restaurants en vieille ville ; café à la station d'arrivée."),
        "preparation_tips": l(
            "Sturdy shoes (cobblestones, steps, steep alleys). Stroller NOT practical in castle/chairlift — use a baby carrier.",
            "Feste Schuhe (Kopfsteinpflaster, Treppen, steile Gassen). Kinderwagen in der Burg/am Sessellift nicht praktisch — Babytrage besser.",
            "Chaussures solides (pavés, marches, ruelles). Poussette peu pratique au château/télésiège — porte-bébé recommandé.",
        ),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily 10:00-18:00 (chairlift Apr-Oct)",
                            "Täglich 10:00-18:00 (Sessellift Apr-Okt)",
                            "Tous les jours 10h-18h (télésiège avr-oct)"),
        "peak_hours": l("Summer afternoons", "Sommer-Nachmittage", "Après-midi été"),
        "changing_facilities": False, "restrooms": True,
    },
    # 9
    {
        "title": l("Schiessentümpel & Mullerthal Trail", "Schiessentümpel & Mullerthal-Pfad",
                    "Schiessentümpel & Sentier du Mullerthal"),
        "short": l("Iconic waterfall in 'Little Switzerland' — pure nature reset.",
                    "Ikonischer Wasserfall in der „Kleinen Schweiz\" — reine Natur.",
                    "Cascade emblématique dans la 'Petite Suisse' — nature pure."),
        "description": l(
            "Sandstone bridge (1879) and waterfall — the regional landmark. Currently a detour is in place due to wooden footbridge construction (check mullerthal.lu before going).",
            "Sandsteinbrücke (1879) und Wasserfall — Wahrzeichen der Region. Wegen Bauarbeiten am Holzsteg aktuell Umleitung — vor Anfahrt Status auf mullerthal.lu prüfen.",
            "Pont en grès (1879) et cascade — emblème régional. Détour actuel en raison de travaux ; vérifier mullerthal.lu avant le départ.",
        ),
        "type": "Outdoor", "canton": "Echternach", "town": "Mullerthal",
        "category": ["Nature"],
        "age_min": 5, "age_max": 99,
        "time": "08:00 - sunset",
        "price_adult": 0.0, "price_child": 0.0,
        "price_label": l("Free", "Kostenlos", "Gratuit"),
        "accessibility": l("Not wheelchair- or stroller-friendly — natural rocky terrain",
                            "Nicht rollstuhl- oder kinderwagentauglich — Naturgelände, Fels",
                            "Non accessible PMR ou poussette — terrain rocheux naturel"),
        "weather_fit": l("Best in dry weather; cool forest in summer",
                          "Am besten trocken; kühler Wald im Sommer",
                          "Idéal par temps sec ; forêt fraîche en été"),
        "lat": 49.7956, "lng": 6.3008,
        "website_url": "https://www.mullerthal.lu/de/attraktion/schiessentumpel-wasserfall",
        "accessibility_wheelchair": False,
        "sensory_friendly": True,
        "free_parking": True,
        "sensory_notes": l(
            "Very good — pure nature, waterfall sounds, forest, rock. Ideal sensory reset. Quiet outside peak times.",
            "Sehr gut — reine Natur, Wasserfall-Rauschen, Wald, Fels. Ideal zum Reize-Reset. Außerhalb der Hauptzeiten ruhig.",
            "Très bon — nature pure, son de la cascade, forêt, roche. Reset sensoriel idéal.",
        ),
        "parking": l("Parking Schiessentümpel (~500m walk) or Heringer Millen (~1km), free.",
                      "Parkplatz Schiessentümpel (~500m Fußweg) oder Heringer Millen (~1km), gratis.",
                      "Parking Schiessentümpel (~500m) ou Heringer Millen (~1km), gratuit."),
        "food_allowed": True,
        "food_onsite": l("Bring a picnic; 'Heringer Millen' restaurant nearby.",
                          "Picknick mitbringen; Restaurant „Heringer Millen\" in der Nähe.",
                          "Apportez un pique-nique ; restaurant 'Heringer Millen' à proximité."),
        "preparation_tips": l(
            "Sturdy / waterproof shoes essential (roots, rock, often slippery). Stroller unsuitable — use a baby carrier. Weather-resistant clothing.",
            "Festes/wasserfestes Schuhwerk Pflicht (Wurzeln, Fels, oft rutschig). Kinderwagen ungeeignet — Kraxe/Trage. Wetterfeste Kleidung.",
            "Chaussures imperméables solides (racines, roche, glissant). Poussette inadaptée — porte-bébé. Vêtements imperméables.",
        ),
        "payment_methods": [],
        "opening_hours": l("Open access, sunrise to sunset",
                            "Frei zugänglich, Sonnenaufgang bis Sonnenuntergang",
                            "Accès libre, du lever au coucher du soleil"),
        "peak_hours": l("Summer weekends", "Sommer-Wochenenden", "Week-ends d'été"),
        "changing_facilities": False, "restrooms": False,
    },
    # Indoor playgrounds (rainy-day plan B). Stimulating; ear protection helps.
    {
        "title": l("YOYO Howald (Indoor Playground)", "YOYO Howald (Indoor-Spielplatz)", "YOYO Howald (Aire de jeux couverte)"),
        "short": l("Soft-play indoor playground for toddlers/young kids (1-5).",
                    "Soft-Play Indoor-Spielplatz für Kleinkinder (1-5 J.).",
                    "Aire de jeux intérieure pour tout-petits (1-5 ans)."),
        "description": l(
            "Toddler-focused soft-play centre with parent lounge. Great rainy-day plan B for energetic young kids.",
            "Auf Kleinkinder ausgerichteter Soft-Play-Bereich mit Eltern-Lounge. Toller Plan B bei Regen für energiegeladene Kleine.",
            "Centre soft-play orienté tout-petits avec espace parents. Excellent plan B pluvieux.",
        ),
        "type": "Indoor", "canton": "Luxembourg", "town": "Howald",
        "category": ["Playgrounds"],
        "age_min": 1, "age_max": 5,
        "time": "10:00 - 19:00",
        "price_adult": 0.0, "price_child": 10.0,
        "price_label": l("EUR ~10 / child · adult often free",
                          "ca. 10 € / Kind · Erwachsene oft gratis",
                          "~10 € / enfant · adulte souvent gratuit"),
        "accessibility": l("Stroller parking, level access", "Kinderwagen-Parkplatz, ebenerdig",
                            "Parking poussette, accès de plain-pied"),
        "weather_fit": l("Perfect when it rains", "Perfekt bei Regen", "Idéal sous la pluie"),
        "lat": 49.5808, "lng": 6.1244,
        "website_url": "https://topkidsplay.com/indoor-playgrounds-in-luxembourg/",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l("Loud, busy, colourful. Bring ear protection if noise-sensitive.",
                            "Laut, voll, bunt. Bei Geräuschempfindlichkeit Gehörschutz mitnehmen.",
                            "Bruyant, animé, coloré. Apportez une protection auditive."),
        "parking": l("Free parking in front.", "Gratis Parkplatz davor.", "Stationnement gratuit devant."),
        "food_allowed": False,
        "food_onsite": l("Café/parent lounge on site.", "Café/Eltern-Lounge vor Ort.",
                          "Café/espace parents sur place."),
        "preparation_tips": l("Grippy/anti-slip socks required for kids.", "Stoppersocken (oft Pflicht).",
                                "Chaussettes anti-dérapantes obligatoires."),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily 10:00-19:00", "Täglich 10:00-19:00", "Tous les jours 10h-19h"),
        "peak_hours": l("Rainy weekends", "Regnerische Wochenenden", "Week-ends pluvieux"),
        "changing_facilities": True, "restrooms": True,
    },
    {
        "title": l("Hello Kids by Kouki Belval", "Hello Kids by Kouki Belval", "Hello Kids by Kouki Belval"),
        "short": l("Indoor playground for kids 1-5 with parent café.",
                    "Indoor-Spielplatz 1-5 J. mit Eltern-Café.",
                    "Aire couverte 1-5 ans avec café parents."),
        "description": l(
            "Toddler-focused soft-play in Belval. Good rainy-day plan B; can get noisy.",
            "Auf Kleinkinder fokussierter Soft-Play-Bereich in Belval. Gutes Schlechtwetter-Ziel; kann laut sein.",
            "Soft-play tout-petits à Belval. Bon plan B pluvieux ; peut être bruyant.",
        ),
        "type": "Indoor", "canton": "Esch-sur-Alzette", "town": "Esch-Belval",
        "category": ["Playgrounds"],
        "age_min": 1, "age_max": 5,
        "time": "10:00 - 19:00",
        "price_adult": 0.0, "price_child": 10.0,
        "price_label": l("EUR ~10 / child · adult often free",
                          "ca. 10 € / Kind · Erwachsene oft gratis",
                          "~10 € / enfant · adulte souvent gratuit"),
        "accessibility": l("Stroller parking, level access", "Kinderwagen-Parkplatz, ebenerdig",
                            "Parking poussette, plain-pied"),
        "weather_fit": l("Perfect when it rains", "Perfekt bei Regen", "Idéal sous la pluie"),
        "lat": 49.5025, "lng": 5.9489,
        "website_url": "https://topkidsplay.com/indoor-playgrounds-in-luxembourg/",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l("Loud and busy.", "Laut und voll.", "Bruyant et animé."),
        "parking": l("Free parking near the venue.", "Gratis Parkplatz in der Nähe.",
                      "Stationnement gratuit à proximité."),
        "food_allowed": False,
        "food_onsite": l("Parent café on site.", "Eltern-Café vor Ort.", "Café parents sur place."),
        "preparation_tips": l("Anti-slip socks required.", "Stoppersocken erforderlich.",
                                "Chaussettes anti-dérapantes."),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily 10:00-19:00", "Täglich 10:00-19:00", "Tous les jours 10h-19h"),
        "peak_hours": l("Weekends afternoons", "Wochenend-Nachmittage", "Après-midi week-end"),
        "changing_facilities": True, "restrooms": True,
    },
    {
        "title": l("Zigzag Bertrange (Indoor Playground)",
                    "Zigzag Bertrange (Indoor-Spielplatz)",
                    "Zigzag Bertrange (Aire couverte)"),
        "short": l("Indoor playground for 2-12 year olds.",
                    "Indoor-Spielplatz für 2-12 Jahre.",
                    "Aire de jeux couverte pour 2-12 ans."),
        "description": l(
            "Mid-size indoor playground covering toddlers up to pre-teens.",
            "Mittlerer Indoor-Spielplatz für Kleinkinder bis Vor-Teens.",
            "Aire de jeux couverte de taille moyenne, tout-petits aux pré-ados.",
        ),
        "type": "Indoor", "canton": "Luxembourg", "town": "Bertrange",
        "category": ["Playgrounds"],
        "age_min": 2, "age_max": 12,
        "time": "10:00 - 19:00",
        "price_adult": 0.0, "price_child": 12.0,
        "price_label": l("EUR ~12 / child", "ca. 12 € / Kind", "~12 € / enfant"),
        "accessibility": l("Level access", "Ebenerdig", "Plain-pied"),
        "weather_fit": l("Great when it rains", "Super bei Regen", "Idéal sous la pluie"),
        "lat": 49.6094, "lng": 6.0625,
        "website_url": "https://topkidsplay.com/indoor-playgrounds-in-luxembourg/",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l("Loud and stimulating.", "Laut und reizintensiv.", "Bruyant et stimulant."),
        "parking": l("Free parking in front.", "Gratis Parkplatz davor.", "Stationnement gratuit."),
        "food_allowed": False,
        "food_onsite": l("Café on site.", "Café vor Ort.", "Café sur place."),
        "preparation_tips": l("Anti-slip socks required.", "Stoppersocken erforderlich.",
                                "Chaussettes anti-dérapantes."),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily 10:00-19:00", "Täglich 10:00-19:00", "Tous les jours 10h-19h"),
        "peak_hours": l("Rainy weekends", "Regnerische Wochenenden", "Week-ends pluvieux"),
        "changing_facilities": True, "restrooms": True,
    },
    {
        "title": l("Fun-City Pétange", "Fun-City Pétange", "Fun-City Pétange"),
        "short": l("Large indoor park with laser tag and mini-golf.",
                    "Großer Indoor-Park mit Lasertag und Minigolf.",
                    "Grand parc couvert avec laser tag et mini-golf."),
        "description": l(
            "Big indoor centre for kids 2-12. Combines playground with laser tag, mini-golf and birthday spaces.",
            "Großer Indoor-Park für Kinder 2-12. Kombiniert Spielplatz mit Lasertag, Minigolf und Geburtstagsbereich.",
            "Grand centre intérieur 2-12 ans : aire de jeux, laser tag, mini-golf.",
        ),
        "type": "Indoor", "canton": "Esch-sur-Alzette", "town": "Pétange",
        "category": ["Playgrounds"],
        "age_min": 2, "age_max": 12,
        "time": "10:00 - 19:00",
        "price_adult": 0.0, "price_child": 12.0,
        "price_label": l("EUR ~12 / child", "ca. 12 € / Kind", "~12 € / enfant"),
        "accessibility": l("Level access", "Ebenerdig", "Plain-pied"),
        "weather_fit": l("Great when it rains", "Super bei Regen", "Idéal sous la pluie"),
        "lat": 49.5594, "lng": 5.8819,
        "website_url": "https://topkidsplay.com/indoor-playgrounds-in-luxembourg/",
        "accessibility_wheelchair": True,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l("Very loud and stimulating — bring ear protection.",
                            "Sehr laut und reizintensiv — Gehörschutz mitnehmen.",
                            "Très bruyant et stimulant — apportez une protection auditive."),
        "parking": l("Free parking on site.", "Gratis Parkplatz vor Ort.", "Stationnement gratuit sur place."),
        "food_allowed": False,
        "food_onsite": l("Café/snack bar.", "Café/Snack-Bar.", "Café/snack."),
        "preparation_tips": l("Anti-slip socks; laser-tag has age limit.",
                                "Stoppersocken; Lasertag mit Altersgrenze.",
                                "Chaussettes anti-dérapantes ; âge minimum laser-tag."),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily 10:00-19:00", "Täglich 10:00-19:00", "Tous les jours 10h-19h"),
        "peak_hours": l("Rainy weekends, school holidays", "Regnerische Wochenenden, Schulferien",
                          "Week-ends pluvieux, vacances scolaires"),
        "changing_facilities": True, "restrooms": True,
    },
    {
        "title": l("KOJUMP Foetz (Trampoline Park)",
                    "KOJUMP Foetz (Trampolinpark)",
                    "KOJUMP Foetz (Parc de trampolines)"),
        "short": l("Trampoline park for kids 5+.",
                    "Trampolinpark ab 5 Jahren.",
                    "Parc de trampolines à partir de 5 ans."),
        "description": l(
            "Trampoline park ideal to burn off energy. Best from ~5 years old.",
            "Trampolinpark ideal zum Auspowern. Am besten ab ~5 Jahren.",
            "Parc de trampolines pour se dépenser. Idéal à partir de ~5 ans.",
        ),
        "type": "Indoor", "canton": "Esch-sur-Alzette", "town": "Foetz",
        "category": ["Playgrounds", "Workshops"],
        "age_min": 5, "age_max": 16,
        "time": "10:00 - 21:00",
        "price_adult": 14.0, "price_child": 12.0,
        "price_label": l("EUR 12-14 / hour", "12-14 € / Stunde", "12-14 € / heure"),
        "accessibility": l("Level access; sport activity", "Ebenerdig; Sportaktivität",
                            "Plain-pied ; activité sportive"),
        "weather_fit": l("Great when it rains", "Super bei Regen", "Idéal sous la pluie"),
        "lat": 49.5258, "lng": 5.9869,
        "website_url": "https://topkidsplay.com/indoor-playgrounds-in-luxembourg/",
        "accessibility_wheelchair": False,
        "sensory_friendly": False,
        "free_parking": True,
        "sensory_notes": l("Lots of movement, loud — energetic kids love it.",
                            "Viel Bewegung, laut — energiegeladene Kinder lieben es.",
                            "Beaucoup de mouvement, bruyant — les enfants énergiques adorent."),
        "parking": l("Free parking on site.", "Gratis Parkplatz vor Ort.", "Stationnement gratuit sur place."),
        "food_allowed": False,
        "food_onsite": l("Snack bar on site.", "Snack-Bar vor Ort.", "Snack sur place."),
        "preparation_tips": l(
            "Mandatory grip socks (sold on site if needed). Sporty clothing.",
            "Spezielle Stoppersocken Pflicht (vor Ort erhältlich). Sportkleidung.",
            "Chaussettes anti-dérapantes obligatoires (en vente sur place). Tenue sportive.",
        ),
        "payment_methods": ["Cash", "Card"],
        "opening_hours": l("Daily 10:00-21:00", "Täglich 10:00-21:00", "Tous les jours 10h-21h"),
        "peak_hours": l("Weekend afternoons, school holidays",
                          "Wochenend-Nachmittage, Schulferien",
                          "Après-midi week-end, vacances scolaires"),
        "changing_facilities": True, "restrooms": True,
    },
]

# Fallback image when og:image cannot be found (themed Unsplash).
FALLBACK_IMAGES = {
    "Outdoor": "https://images.unsplash.com/photo-1500595046743-cd271d694d30?auto=format&fit=crop&w=1200&q=80",
    "Indoor": "https://images.unsplash.com/photo-1597524678053-faf08e5e1aff?auto=format&fit=crop&w=1200&q=80",
    "Educational": "https://images.unsplash.com/photo-1503424886307-b090341d25d1?auto=format&fit=crop&w=1200&q=80",
    "Event": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=1200&q=80",
}


# ---------------------------------------------------------------------------
# Build & insert
# ---------------------------------------------------------------------------
async def build_document(client: httpx.AsyncClient, loc: Dict[str, Any]) -> Dict[str, Any]:
    image_url = await fetch_og_image(client, loc["website_url"]) if loc.get("website_url") else None
    if not image_url:
        image_url = FALLBACK_IMAGES.get(loc["type"], FALLBACK_IMAGES["Outdoor"])
        log.info("  ↳ using fallback image for %s", loc["title"]["en"])
    else:
        log.info("  ↳ og:image: %s", image_url[:80])

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "image": image_url,
        "start_date": TODAY,
        "end_date": None,
        "bookable": False,
        "published": True,
        "rating": 4.6,
        "featured": False,
        "featured_until": None,
        "view_count": 0,
        "source_id": None,
        "source_name": "deep-dive-seed",
        "external_id": None,
        "created_at": now,
        "updated_at": now,
        "created_by": "seed-script",
        **loc,
    }
    return doc


async def main() -> None:
    log.info("Connecting to MongoDB %s/%s", MONGO_URL, DB_NAME)
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo[DB_NAME]
    events = db["events"]

    # Only clear our own previous seed rows — never touch crawler content.
    res = await events.delete_many({"source_name": "deep-dive-seed"})
    log.info("Cleared %d previous deep-dive-seed rows.", res.deleted_count)

    async with httpx.AsyncClient() as http:
        log.info("Inserting %d curated locations …", len(LOCATIONS))
        for i, loc in enumerate(LOCATIONS, 1):
            log.info("[%d/%d] %s", i, len(LOCATIONS), loc["title"]["en"])
            doc = await build_document(http, loc)
            await events.insert_one(doc)

    count = await events.count_documents({})
    log.info("Done. %d events now in DB.", count)
    mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
