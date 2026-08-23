# Quellen

## `candidates.csv` — Vorschläge, keine aktivierten Quellen

Erzeugt von `backend/discover_sources.py`. Die Datei **aktiviert nichts**. Sie
sammelt, was auf den Webseiten der 100 luxemburgischen Gemeinden tatsächlich
beobachtet wurde, damit du entscheiden kannst.

### Spalte `Status`

| Wert | Bedeutung |
|---|---|
| `KANDIDAT` | Veranstaltungsseiten gefunden — **hier lohnt ein Blick** |
| `NICHTS GEFUNDEN` | erreichbar, aber keine Veranstaltungsseiten entdeckt |
| `GESPERRT` | die `robots.txt` untersagt uns das Crawlen. **Nicht aufnehmen.** |
| `FEHLER` | nicht erreichbar oder unbrauchbare Adresse |

### Die übrigen Spalten

- **Crawl-Delay** — Pause, um die die Seite bittet. Wird beim Crawlen automatisch
  eingehalten; hier steht sie nur zur Information.
- **Sitemap** — welche Sitemap ausgewertet wurde. Leer heißt: keine gefunden,
  stattdessen wurden übliche Pfade probiert.
- **Veranstaltungsseiten** — wie viele veranstaltungsartige Adressen gefunden
  wurden. Eine hohe Zahl heißt nicht automatisch „gute Quelle".
- **JSON-LD** — `ja` bedeutet strukturierte Veranstaltungsdaten nach
  schema.org. Solche Quellen sind mit Abstand am saubersten einzulesen und
  sollten zuerst aufgenommen werden.

### So gehst du damit um

1. Nach `Status = KANDIDAT` filtern, dann nach `JSON-LD = ja` sortieren.
2. Die **Beispiel-URL** im Browser öffnen und schauen, ob dort wirklich
   Familienveranstaltungen stehen. Eine Gemeinde-Nachrichtenseite ist oft keine.
3. Was taugt, im Admin-Bereich unter *Quellen* anlegen — Art `json_ld` wenn die
   Spalte `ja` sagt, sonst `sitemap` oder `html_scraper`.

Nichts wird automatisch aufgenommen. Das ist Absicht: eine Quelle, die niemand
angesehen hat, liefert Daten, die niemand geprüft hat.

## Erneut ausführen

```bash
cd backend && python discover_sources.py
```

Zwischenergebnisse werden gespeichert, ein Abbruch ist also unschädlich. Ein
voller Durchlauf dauert lange — jede Seite bekommt die Pause, um die sie bittet.
