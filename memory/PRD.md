# Luxembourg Family Activities — Mobile App PRD

## Overview
Native Expo mobile app for families in Luxembourg to discover places, events, and workshops for kids. Now backed by a FastAPI/MongoDB backend for event content management.

## Tech Stack
- **Frontend**: Expo SDK 54 + expo-router (file-based)
- **Backend**: FastAPI + Motor (async MongoDB) + bcrypt + PyJWT + slowapi
- **Persistence**: MongoDB for events/users; AsyncStorage for client-side prefs/saved/bookings
- **Maps**: OpenStreetMap embed (no API key)
- **Weather**: Open-Meteo (no API key)

## Architecture
### Backend (`/app/backend/server.py`)
- JWT auth with bcrypt password hashing
- Idempotent admin seeding on startup (from `.env`)
- slowapi rate limit on `/api/auth/login` (10/min)
- Indexes: `users.email` unique, `users.id` unique, `events.id` unique, `events.start_date`
- Endpoints
  - `POST /api/auth/login` → JWT + user
  - `GET /api/auth/me`
  - `GET /api/events` (public, filters: canton, upcoming)
  - `GET /api/events/{id}` (public)
  - `GET|POST /api/admin/events` (admin)
  - `PATCH|DELETE /api/admin/events/{id}` (admin)
  - `GET /api/health`

### Frontend
- `/app/_layout.tsx` — Root: SafeAreaProvider + GestureHandler + AppProvider + Stack
- `/app/index.tsx` — Auth gate
- `/app/login.tsx` — Local user login (Email/Pwd/Guest, language picker)
- `/app/(tabs)/_layout.tsx` — Custom bottom tab bar (6 tabs)
- `/app/(tabs)/{home,explore,events,saved,calendar,profile}.tsx`
- `/app/detail/[id].tsx` — Static place detail
- `/app/event/[id].tsx` — Backend-loaded event detail with OSM map
- `/app/book/[id].tsx` — Booking flow + confirmation
- `/app/admin/_layout.tsx` — Admin stack
- `/app/admin/index.tsx` — Admin login (Bcrypt + JWT)
- `/app/admin/events/index.tsx` — Admin events list (publish toggle, edit, delete)
- `/app/admin/events/[id].tsx` — Admin editor (handles `new` and existing IDs)
- `/src/utils/api.ts` — Typed API client with admin JWT injection
- `/src/components/LuxembourgMap.tsx` — Canton map header
- `/src/data/places.ts` — Static seed places (museums/parks, ~8 entries, EN/DE/FR)

## Features
- Multilingual UI (EN/DE/FR), instant switch from login + profile
- Real-time Luxembourg weather (Open-Meteo)
- **6-tab navigation**: Home / Explore / Events / Saved / Calendar / Profile
- Canton map header on Explore (12 clickable cantons + count badges)
- Filterable explore feed (canton / age / type / category / date)
- Save / unsave activities (AsyncStorage persistence)
- Booking flow with date picker, guest stepper, total
- Detail screens with embedded OSM map + "Open in Maps"
- **Events tab** loads upcoming events from backend, grouped by month
- **Admin CMS at `/admin`**: list/create/edit/delete events, publish toggle, multilingual fields
- Local-only mobile user auth via AsyncStorage

## Mocked / Local-Only
- Mobile user auth (local, no backend) — frontend stores user in AsyncStorage
- Booking confirmation (no payment integration)

## Next Action Items
- Auto-import events from `visitluxembourg.com` Open Data API (Phase 2)
- iCal feed aggregator for Mudam, Philharmonie, Rockhal (Phase 3)
- User-submitted events with moderation queue (Phase 4)
- Migrate mobile user auth to backend too (currently local-only)
