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

Braucht **Python 3.10 oder neuer**: `fastapi`, `python-dotenv` und `icalendar`
liefern für ältere Versionen keine Pakete mehr. Unter 3.9 bricht `pip install`
mit „No matching distribution found" ab und nennt den Grund nicht. Die CI läuft
auf 3.11.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # requirements-dev.txt für Tests dazu
cp .env.example .env                   # ausfüllen, siehe Tabelle
uvicorn server:app --reload --port 8001
```

Erwartet eine erreichbare MongoDB und eine `backend/.env`
(`backend/.env.example` listet alles auf):

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `MONGO_URL` | ja | MongoDB-Verbindungsstring |
| `DB_NAME` | ja | Datenbankname |
| `JWT_SECRET` | ja | Signaturschlüssel für Admin-Tokens |
| `ADMIN_EMAIL` | ja | wird beim Start idempotent angelegt |
| `ADMIN_PASSWORD` | ja | Passwort für dieses Konto — maßgeblich, siehe unten |
| `JWT_ALGORITHM` | nein | Vorgabe `HS256` |
| `JWT_EXPIRE_MINUTES` | nein | Vorgabe 10080 (7 Tage) |
| `STRIPE_SECRET_KEY` | für Sponsoring | Stripe-API-Schlüssel |
| `STRIPE_WEBHOOK_SECRET` | für Sponsoring | **ohne diesen Wert lehnt der Webhook ab** |
| `FRONTEND_URL` | für Sponsoring | Basis für Stripe-Rücksprungadressen |
| `DISABLE_SCHEDULER` | nein | `1` schaltet den Importer-Cron ab |
| `CORS_ORIGINS` | nein | Kommagetrennt. Ohne Wert ist **jede** Herkunft erlaubt |
| `EMERGENT_SESSION_URL` | für Google-Login | ohne Wert antwortet `POST /api/auth/session` mit 503 |
| `VIEW_IP_SALT` | nein | salzt den Hash der Besucher-IPs; einmal setzen, dann nie ändern |

#### Admin-Passwort ändern

`ADMIN_PASSWORD` ist maßgeblich: Weicht der Wert beim Start vom gespeicherten
Hash ab, wird der Hash ersetzt. Zum Ändern also den Wert in der Umgebung setzen
und das Backend neu starten — das Konto selbst bleibt erhalten, nur das Passwort
wechselt. Im Log erscheint dann `Admin password rotated`.

Vorher gab es dafür keinen Weg: Die Variable wurde nur beim allerersten Start
ausgewertet, und einen Endpunkt zum Passwortwechsel gibt es nicht.

Der Importer läuft automatisch um 05:00, 12:00 und 18:00 Europe/Luxembourg.
Manuell auslösbar über `POST /api/admin/sources/run-all`.

### Frontend

```bash
cd frontend
yarn install
cp .env.example .env    # EXPO_PUBLIC_BACKEND_URL eintragen
yarn start              # Expo Dev Server
yarn web                # nur Web
```

`frontend/.env` braucht `EXPO_PUBLIC_BACKEND_URL` — die Basis-URL des Backends
ohne abschließenden Schrägstrich, also z. B. `http://localhost:8001`. Fehlt der
Wert, zeigt jeder Bildschirm „Failed to load"; das sieht nach einem Fehler in
der App aus, ist aber nur die fehlende Einstellung.

Alles mit `EXPO_PUBLIC_` wird in das App-Bundle kompiliert und ist für jeden
lesbar, der die App installiert — dort gehört niemals ein Schlüssel hin.

## Prüfen

```bash
cd frontend && yarn run check   # tsc --noEmit + eslint
cd backend  && flake8 --select=E9,F . && pytest tests/offline -q
```

`yarn check` ohne `run` ist ein **eingebauter Yarn-Befehl**, der das Skript
verdeckt und unverwandte Fehler meldet. Immer `yarn run check`.

Der Typecheck ist lokal strenger als in der CI. `app.json` setzt
`typedRoutes`, aber die Routen-Typen (`.expo/types/router.d.ts`) entstehen erst
beim Start des Dev-Servers und sind nicht eingecheckt. Wer die App einmal
gestartet hat, sieht deshalb Fehler, die auf GitHub nie erscheinen — echte
Fehler: ohne diese Typen prüft niemand, ob ein `router.push()` auf eine Route
zeigt, die es gibt. **Vor dem Push einmal `yarn web` starten und dann
`yarn run check`.**

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
