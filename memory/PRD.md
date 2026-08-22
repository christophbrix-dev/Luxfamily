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

