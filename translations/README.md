# Übersetzungen

## `lb.csv` — Lëtzebuergesch

Alle Texte der App, die eine luxemburgische Fassung brauchen. Erzeugt aus
`frontend/src/i18n/strings.ts` und `frontend/src/data/places.ts`.

**So füllst du sie aus**

Öffne die Datei in Numbers, Excel oder Google Sheets. Trage die Übersetzung
ausschließlich in die letzte Spalte **`Lëtzebuergesch`** ein. Alle anderen
Spalten unverändert lassen — besonders `Schlüssel`, daran wird die Zeile
später wiedererkannt.

Zeilen dürfen leer bleiben. Wo nichts steht, zeigt die App weiterhin Deutsch.

**Reihenfolge**

`1 Oberfläche` zuerst: 156 Knöpfe, Titel und Menüpunkte. Die entscheiden, ob
sich die App luxemburgisch anfühlt, und sind meist ein bis drei Wörter.

`2 Orte` danach: 56 längere Texte zu den einzelnen Ausflugszielen.

**Hinweise**

- `Wat Elo?` ist der App-Name und bleibt in allen Sprachen gleich.
- Platzhalter wie `{count}` oder `{name}` unverändert übernehmen — sie werden
  zur Laufzeit ersetzt.
- Steht am Ende ein Ausrufe- oder Fragezeichen, sollte es das auch in der
  Übersetzung.

Wenn die Datei fertig ist, wird sie zurück in `strings.ts` und `places.ts`
eingespielt. Nicht direkt im Code übersetzen — die Liste ist die Quelle.
