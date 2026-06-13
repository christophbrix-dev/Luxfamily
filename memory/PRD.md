# Luxembourg Family Activities — PRD

Native Expo + FastAPI + MongoDB app discovering family activities in Luxembourg.

## Stack
- Frontend: Expo SDK 54, expo-router, react-native-svg, OpenStreetMap (no key), Open-Meteo (no key)
- Backend: FastAPI + Motor + bcrypt + PyJWT + slowapi + APScheduler + icalendar + httpx
- Mobile auth: local (AsyncStorage). Admin auth: real backend (Bcrypt + JWT).

## Routes
### Mobile (`/(tabs)/...`, 6 tabs)
home / explore / events / saved / calendar / profile
+ `/detail/[id]` (static places), `/event/[id]` (backend), `/book/[id]`, `/login`

### Admin (web-only at `/admin`)
- `/admin` — login
- `/admin/events` — list, publish toggle, edit, delete, sponsored star, view counts
- `/admin/events/new`, `/admin/events/[id]` — multilingual editor + image upload (base64) + featured toggle + featured_until
- `/admin/sources` — configurable auto-importer feeds (iCal / data.public.lu)
- `/admin/analytics` — total/published/drafts/featured + total views + monthly featured revenue (EUR 49 × featured) + top events

## Backend endpoints
- Auth: POST /api/auth/login (rate-limited 10/min), GET /api/auth/me
- Events public: GET /api/events (featured-first), GET /api/events/{id}, POST /api/events/{id}/view (rate-limited 1/min/IP)
- Events admin: GET|POST /api/admin/events, PATCH|DELETE /api/admin/events/{id}
- Sources admin: GET|POST /api/admin/sources, PATCH|DELETE /api/admin/sources/{id}, POST /api/admin/sources/{id}/run, POST /api/admin/sources/run-all
- Analytics: GET /api/admin/analytics/overview
- Health: GET /api/health

## Auto-importer
- APScheduler runs `run_all_active(db)` every 24h (`DISABLE_SCHEDULER=1` in tests)
- iCal importer parses VEVENTs, dedupes by (source_id, UID)
- data.public.lu importer parses CKAN-style JSON (records[]), dedupes by (source_id, id)
- All imports write `published=false` so admin reviews first

## Monetization
- `featured: bool` + `featured_until: date` on events
- Featured events surfaced first in public list + "Sponsored" amber badge on mobile + admin
- Analytics dashboard projects EUR 49/month/featured

## MOCKED / Local-only
- Mobile end-user auth (intentional)
- Booking flow (no payment)
- Sponsored revenue is a projection from `featured` count — no Stripe integration yet

## Next Action Items
- Image upload to S3/Cloudinary instead of base64 (when MongoDB doc sizes grow)
- Add Stripe checkout for partners to self-serve "Sponsored" upgrade
- Add SourceLogs collection for audit history of imports (currently last-only)
- Mudam / Philharmonie / Rockhal: add specific source records with verified iCal URLs
