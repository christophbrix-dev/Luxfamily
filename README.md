# Wat Elo?

Familienaktivitäten, Orte und Events in Luxemburg — Expo-App mit FastAPI-Backend.

- **Frontend** — Expo SDK 54 / React Native 0.81 / TypeScript, Routing über `expo-router`.
  Läuft auf iOS, Android und im Web.
- **Backend** — FastAPI + MongoDB, JWT-Auth für das Admin-Panel, Stripe Checkout für
  gesponserte Event-Plätze und ein robots.txt-konformer Importer, der dreimal täglich
  luxemburgische Veranstaltungsquellen einliest.

## Aufbau

```
backend/          FastAPI-Anwendung
  server.py         API — Auth, Events, Quellen, Partner, Sponsoring, Analytics
  importers.py      Importer für ical, data_public_lu, html_scraper, json_ld, sitemap
  crawler_utils.py  robots.txt-Cache und Per-Host-Rate-Limit
  crawlers/         Handgeschriebene Crawler für einzelne Portale
  seed_*.py         Seed-Skripte für Quellen und Beispiel-Events
  tests/            Integrationstests gegen eine laufende Instanz

frontend/         Expo-App
  app/              Routen (expo-router, dateibasiert)
    (tabs)/           Home, Explore, Events, Saved, Kalender, Profil
    admin/            Admin-Panel: Events, Quellen, Partner, Analytics
    sponsor/          Stripe-Checkout-Flow
  src/
    components/       Geteilte UI-Komponenten
    contexts/         AppContext — Sprache, Nutzer, Favoriten, Theme, Profil
    i18n/             Übersetzungen (en, de, fr; lb fällt auf de zurück)
    utils/api.ts      Typisierter API-Client
    theme.ts          Design-Tokens, Light- und Dark-Palette

memory/PRD.md     Produktbeschreibung und offene Punkte
```

## Entwicklung

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8001
```

Erwartet eine erreichbare MongoDB und eine `backend/.env`:

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `MONGO_URL` | ja | MongoDB-Verbindungsstring |
| `DB_NAME` | ja | Datenbankname |
| `JWT_SECRET` | ja | Signaturschlüssel für Admin-Tokens |
| `ADMIN_EMAIL` | ja | wird beim Start idempotent angelegt |
| `ADMIN_PASSWORD` | ja | Passwort für dieses Konto |
| `JWT_ALGORITHM` | nein | Vorgabe `HS256` |
| `JWT_EXPIRE_MINUTES` | nein | Vorgabe 10080 (7 Tage) |
| `STRIPE_SECRET_KEY` | für Sponsoring | Stripe-API-Schlüssel |
| `STRIPE_WEBHOOK_SECRET` | für Sponsoring | **ohne diesen Wert lehnt der Webhook ab** |
| `FRONTEND_URL` | für Sponsoring | Basis für Stripe-Rücksprungadressen |
| `DISABLE_SCHEDULER` | nein | `1` schaltet den Importer-Cron ab |

Der Importer läuft automatisch um 05:00, 12:00 und 18:00 Europe/Luxembourg.
Manuell auslösbar über `POST /api/admin/sources/run-all`.

### Frontend

```bash
cd frontend
yarn install
yarn start          # Expo Dev Server
yarn web            # nur Web
```

`frontend/.env` braucht `EXPO_PUBLIC_BACKEND_URL` — die Basis-URL des Backends
ohne abschließenden Schrägstrich.

## Prüfen

```bash
cd frontend && yarn check       # tsc --noEmit + eslint
cd backend  && flake8 --select=E9,F .
```

Beides läuft bei jedem Push über `.github/workflows/ci.yml`.

Die Backend-Tests sind Integrationstests: Sie brauchen ein laufendes Backend
auf `http://localhost:8001` (oder `EXPO_BACKEND_URL`), eine MongoDB und
`ADMIN_EMAIL` / `ADMIN_PASSWORD` in der Umgebung.

```bash
cd backend && pytest tests/
```

## Bekannte Baustellen

Der aktuelle Stand ist in `memory/PRD.md` festgehalten. Die größten offenen Punkte:

- Home, Explore, Saved, Kalender, Detail und Buchung lesen noch aus der statischen
  Liste in `frontend/src/data/places.ts` statt aus der Datenbank.
- Dark Mode: Screens sind umgestellt, die geteilten Komponenten noch nicht.
- Bundle-ID in `frontend/app.json` ist noch ein Platzhalter, es gibt keine `eas.json`.
- Datenschutzerklärung und AGB sind verlinkt, aber noch nicht veröffentlicht.
