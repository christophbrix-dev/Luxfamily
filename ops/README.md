# Der Crawler läuft über launchd

## Warum nicht über den Scheduler im Backend

Das Backend hat einen eigenen Scheduler (APScheduler, drei Zeiten am Tag). Der
war am 30.09.2026 korrekt eingeschaltet — `DISABLE_SCHEDULER=0` — und hatte am
nächsten Morgen **keinen einzigen Lauf** gemacht.

Nichts war falsch konfiguriert. Der Scheduler lebt im Backend-Prozess, und der
läuft auf einem Laptop nur, solange jemand ein Terminal offen hält. Dazu sind
05:00, 12:00 und 18:00 Zeiten, zu denen ein Laptop meist schläft oder aus ist.
Ein Prozess, der nicht läuft, verpasst nicht nur den Termin — er merkt es auch
nicht und holt nichts nach.

`launchd` hat dieses Problem nicht. Ein `StartCalendarInterval`, dessen
Zeitpunkt im Schlaf vergeht, wird **beim Aufwachen ausgeführt**, und mehrere
verpasste Termine werden zu einem Lauf zusammengefasst. Damit braucht der Mac
nicht um 5 Uhr wach zu sein, sondern nur irgendwann am Tag.

Deshalb: `DISABLE_SCHEDULER=1` in `backend/.env`, und der Zeitplan liegt bei
launchd. **Es soll genau einen Weg geben, auf dem gecrawlt wird.**

## Einrichten

```bash
ops/install-launchagent.sh
```

Das Skript findet das Repository von sich aus, füllt die Vorlage
`lu.luxfamily.importers.plist.template` mit den echten Pfaden, prüft das
Ergebnis mit `plutil -lint` und lädt es in launchd. Nochmal ausführen ersetzt,
es stapelt sich nicht.

```bash
ops/install-launchagent.sh --status    # geladen? wie oft gelaufen? letzte Zeilen
ops/install-launchagent.sh --remove    # wieder heraus
```

Einen Lauf von Hand auslösen — das ist der ehrlichste Test, weil er denselben
Weg nimmt wie ein echter Termin:

```bash
launchctl kickstart -p gui/$(id -u)/lu.luxfamily.importers
```

Oder das Skript direkt, ohne launchd:

```bash
cd backend && .venv/bin/python run_importers.py
```

## Was ein Lauf tut

In dieser Reihenfolge, alles unter **einer** Sperre in der Datenbank:

1. **Sperre nehmen** (`locks`-Sammlung). Kriegt sie jemand anderes, endet der
   Lauf hier — und das ist kein Fehler. Mehrere Rechner dürfen den Job
   gleichzeitig anstoßen; der erste macht ihn, die anderen treten zurück.
2. **Crawlen** — alle aktiven Quellen (`run_all_active`).
3. **Geokodieren** — nur das, was noch keine Koordinaten hat, mit gedeckeltem
   Stapel, weil jede Anfrage auf das Geoportal fremde Infrastruktur kostet.
4. **Familienfreundlichkeit prüfen** — über den ganzen Bestand, nicht nur über
   das Neue. Treffer werden versteckt, nie gelöscht.
5. **Sperre freigeben.**

Jede Stufe fängt ihre eigenen Fehler. Ein fehlgeschlagenes Geokodieren macht
den Import nicht ungültig: die Events sind schon gespeichert.

## Das Log

```
~/Library/Logs/Luxfamily/importers.log
```

Jede Zeile mit Zeitstempel, stdout und stderr in derselben Datei. Ein Lauf
sieht etwa so aus:

```
2026-10-01 09:12:03 INFO    run_importers: Start: events=1010, upcoming=698, without_coordinates=0
2026-10-01 09:12:31 INFO    lux-backend.crawler: no robots.txt for https://www.sanem.lu (HTTP 404) — everything allowed
2026-10-01 09:13:02 INFO    lux-backend.importers: [sitemap] Parc Merveilleux → 62 URLs, 15 event-like candidates
2026-10-01 09:18:19 INFO    importer_run: Geocoded 12 events (commune=9, locality=3)
2026-10-01 09:18:21 INFO    run_importers: Done in 6.3 min: events=1016 (+6), upcoming=704 (+6), without_coordinates=0 (±0)
```

`(±0)` ist auch eine Antwort: alle Quellen erreicht, nichts Neues gefunden.

**Die HTTP-Anfragen selbst stehen nicht drin.** `httpx` protokolliert jede
einzelne auf INFO, und ein vollständiger Crawl macht ungefähr tausend davon —
der erste Lauf hier schrieb 86 Zeilen in 45 Sekunden, 85 davon Anfragen. Darin
findet niemand die eine Zeile, auf die es ankommt. Sie sind auf WARNING
gesetzt, eine *fehlgeschlagene* Anfrage erscheint also weiterhin.

**Die Datei wächst und wird nicht rotiert.** Bei drei Läufen am Tag und ein
paar Zeilen pro Lauf dauert das Jahre, bis es stört — aber es ist nichts, was
sich von selbst aufräumt. Wenn es zu groß wird: löschen, launchd legt sie neu
an.

## Rückfahrkarte

Der Weg zurück zum Scheduler im Backend sind zwei Schritte:

```bash
ops/install-launchagent.sh --remove
# dann in backend/.env: DISABLE_SCHEDULER=0
```

Beide Wege nehmen dieselbe Sperre in der Datenbank, es kann also nichts doppelt
crawlen, falls beide einmal gleichzeitig an sind.

## Wenn Emergent dazukommt

Emergents Container läuft dauerhaft, dort ist der Scheduler im Prozess
sinnvoll. Die Sperre liegt in der gemeinsamen Datenbank, also braucht es keine
Absprache: wer zuerst kommt, nimmt sie. Ob das passiert, entscheidet Christoph
— es steht nicht im Emergent-Prompt.
