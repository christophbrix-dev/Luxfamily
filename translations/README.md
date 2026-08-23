# Übersetzungen

## `lb.csv` — Lëtzebuergesch

Alle Texte der App mit ihrer luxemburgischen Fassung. Erzeugt aus
`frontend/src/i18n/strings.ts` und `frontend/src/data/places.ts`.

### Die Spalte `Status`

| Wert | Bedeutung |
|---|---|
| `OFFEN` | noch keine Übersetzung — **hier ist die Arbeit** |
| `PRÜFEN` | vorhanden, aber wortgleich mit dem Deutschen. Kann korrekt sein (Eigennamen, „Filter"), lohnt aber ein zweites Auge |
| `fertig` | vorhanden und vom Deutschen verschieden |

Die Datei ist so sortiert, dass `OFFEN` oben steht.

### So füllst du sie aus

In Numbers, Excel oder Google Sheets öffnen. Nur die letzte Spalte
**`Lëtzebuergesch`** bearbeiten. Alles andere unverändert lassen, besonders
`Schlüssel` — daran wird die Zeile beim Einspielen wiedererkannt.

Zeilen dürfen leer bleiben; dort zeigt die App weiterhin Deutsch. Die Liste
lässt sich also über mehrere Sitzungen füllen.

### Hinweise

- `Wat Elo?` ist der App-Name und bleibt in allen Sprachen gleich.
- Platzhalter wie `{count}` unverändert übernehmen — sie werden zur Laufzeit
  ersetzt.
- Satzzeichen am Ende möglichst übernehmen.

### Zurück in den Code

```bash
python3 translations/apply_lb.py            # zeigt nur an, was passieren würde
python3 translations/apply_lb.py --write    # schreibt tatsächlich
```

Mehrfaches Ausführen ist unschädlich: vorhandene Werte werden ersetzt, nicht
verdoppelt. Findet das Skript einen Schlüssel nicht mehr im Code, schreibt es
**gar nichts** und meldet ihn — lieber ein Abbruch als halb eingespielte Arbeit.

Wichtig zu wissen, warum es zwei Ziele gibt: Oberflächentexte landen in
`LB_OVERRIDES`, weil `t()` für Luxemburgisch ausschließlich dort nachsieht.
Ortsdaten landen dagegen als `lb:` direkt im Datensatz, weil `pickLang()` genau
dort liest. Ein Wert am jeweils falschen Ort würde stillschweigend ignoriert.
