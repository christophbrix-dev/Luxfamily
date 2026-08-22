# Luxembourg Family Activities — PRD

Expo mobile app + FastAPI backend for discovering family activities, places and events in Luxembourg.

## Stack
- Frontend: Expo SDK 54, expo-router, react-native-svg, OpenStreetMap, Open-Meteo, expo-application
- Backend: FastAPI + Motor + bcrypt + PyJWT + slowapi + APScheduler + icalendar + httpx + beautifulsoup4 + lxml
- Mobile user auth: local AsyncStorage. Admin auth: backend Bcrypt + JWT.

## Mobile routes
- `(tabs)/home|explore|events|saved|calendar|profile` (6 tabs)
- `/detail/[id]`, `/event/[id]`, `/book/[id]`, `/login`
- `/preferences` — age range, fav cantons (12), fav categories (7), notify toggle
- `/about` — version, privacy, terms, contact, IG/FB
- `/business` — partner submission form (with honest "why no FB/IG connect" explanation)

## Admin (web at /admin)
- `/admin` login, `/admin/events` (list + featured star + view counts), `/admin/events/[id]` (editor with image upload, featured toggle, featured_until)
- `/admin/sources` — auto-importer feeds (ical / data_public_lu / html_scraper kinds)
- `/admin/analytics` — total/published/drafts/featured, total views, monthly featured revenue projection (EUR 49 × featured), top events

## Backend endpoints
- Auth: POST /api/auth/login (10/min), GET /api/auth/me
- Events public: GET /api/events (featured-first), /api/events/{id}, POST /api/events/{id}/view (1/min/IP)
- Events admin: GET|POST|PATCH|DELETE
- Sources admin: GET|POST|PATCH|DELETE, POST /api/admin/sources/{id}/run, POST /api/admin/sources/run-all
- Analytics: GET /api/admin/analytics/overview
- Health: GET /api/health

## Auto-importer kinds
- `ical` — venue iCalendar feeds (Mudam/Philharmonie/Rockhal require B2B request — none expose public iCal as of June 2026)
- `data_public_lu` — CKAN JSON resources from data.public.lu and similar portals
- `html_scraper` — generic CSS-selector-based HTML scraper for commune/venue listing pages (BeautifulSoup4 + lxml)
- Scheduler runs every 24h via APScheduler; admin can also trigger manually

## Monetization
- `featured: bool` + `featured_until` per event → "Sponsored" amber badge + featured-first sort
- Analytics dashboard shows monthly revenue projection (featured × EUR 49)

## MOCKED / explicit limitations
- Mobile end-user auth is local-only (no backend) — intentional
- Booking flow has no payment integration yet
- Mudam/Philharmonie/Rockhal/Instagram/Facebook public events APIs are dead — only via partner submission or html_scraper
- Stripe Checkout for sponsored slots: deferred (test key available, not wired)
- Dark mode: toggle persists but full theming is BETA (only Profile screen reads `theme` from context; other screens still use the light palette)

## Next Action Items
- Full dark mode theming (touch every StyleSheet — about 2h refactor)
- Stripe self-service for sponsored slots
- Real Mudam/Philharmonie/Rockhal feeds — contact venues OR use html_scraper with their actual listing pages
- Move image storage from base64 → S3 once docs exceed 1 MB
- Wire `/api/partners` endpoint so business submissions write to MongoDB (currently emails)
## Hygiene-Bundle applied (2026-08-22)
- Metro-Build-Cache aus Git ausgenommen (`.gitignore`)
- Backend: ungenutzte Imports und Variablen entfernt (crawlers, importers, tests, server)
- yarn.lock eingecheckt (reproduzierbare Installs) + GitHub Actions CI + `typecheck` script
- README mit Stack/Setup/Env-Variablen aufgefüllt (104 Zeilen)
- **Security-Fix**: Stripe-Webhook antwortet jetzt 503 wenn `STRIPE_WEBHOOK_SECRET` fehlt (schließt vorherige Fake-Payment-Lücke)
- **Crash-Fix**: `/preferences`-Screen `styles = useMemo(...)` → kein Re-Create der StyleSheet-Instanz beim Öffnen
- **i18n-Fix**: `lb` fällt sauber auf `de` zurück in `event/[id]`, `pick-language` und `WeatherWidget`


## OSM POI Ingest (2026-08-22) — 8.138 Familien-Spots aus OpenStreetMap
- **Neue Backend-Dateien**: `osm_taxonomy.py` (7 Gruppen / 30 Kinds mit i18n de/fr/lb/en), `osm_ingest.py` (Geofabrik PBF-Parser, kein Overpass-Dependency)
- **Neue MongoDB-Collection**: `db.places` mit Indexes auf `id`, `kind`, `group`, `(lat,lng)`, `family_score`
- **Neue Public Endpoints**:
  - `GET /api/places/meta` → Taxonomie mit i18n-Labels
  - `GET /api/places?kind=&group=&min_score=&near_lat=&near_lng=&radius_km=` → gefilterte Liste
  - `GET /api/places/{id}` → Detail inkl. `tags_raw`
- **Neue Admin Endpoints**:
  - `POST /api/admin/osm/ingest` (Body optional: `{categories: [...]}`) → startet Background-Ingest
  - `GET /api/admin/osm/status` → Job-Status + `place_count` + `by_kind`-Statistik
- **Ingest-Kennzahlen** (Erst-Lauf, ~76 s auf lokalem Container):
  - 8.143 POIs upserted, 30 Kategorien
  - 1.869 Parks, 1.862 Picknick, 1.383 Spielplätze, 581 Aussichtspunkte,
    495 Wanderrouten, 375 Radrouten, 211 Naturlehrpfade, 194 Burgen/Schlösser,
    156 Reiterhöfe, 145 Höhlen/Felsen, 135 Schwimmbäder, 109 Grillplätze,
    100 Kinos/Theater, 99 Schutzhütten, 96 Museen, 85 Naturschutzgebiete,
    32 Skateparks, 29 Bauernhöfe, 21 Bibliotheken, 18 Klettern, 16 Badeseen,
    13 Wasserspielplätze, 11 Minigolf, 7 Bowling, 2 Freizeitparks
- **Datenquelle**: Geofabrik PBF (`https://download.geofabrik.de/europe/luxembourg-latest.osm.pbf`)
  → 47 MB, gecacht in `/tmp/luxembourg-latest.osm.pbf` mit 24 h TTL
- **Lizenz**: ODbL-1.0 (in jedem Place-Record vermerkt via `source_license`)
- **Package hinzugefügt**: `osmium` (pyosmium) — high-performance PBF Parser
