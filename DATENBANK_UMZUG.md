# Eine Datenbank statt zwei

Heute gibt es zwei, die nichts voneinander wissen: eine lokale MongoDB auf dem
Mac und eine in Emergents Container. Deshalb steht in jedem Bericht eine andere
Zahl — 528 Events hier, 558 dort — und jede Aussage muss doppelt gelesen werden.

Ziel: eine gemeinsame Datenbank bei MongoDB Atlas, auf die beide zeigen.

**Die Reihenfolge unten ist der eigentliche Inhalt.** Sie ist so gebaut, dass
die laufende App zu keinem Zeitpunkt ohne Rückweg dasteht: Erst wird kopiert,
dann geprüft, und erst danach umgeschaltet. Die alte Datenbank bleibt dabei
unangetastet — wenn Schritt 4 schiefgeht, ist der Weg zurück eine Zeile in
`.env` und ein Neustart.

## Vorab: Was ich nicht tun kann und nicht tun darf

Konto anlegen und Passwörter eingeben sind Dinge, die du selbst machen musst.
Das ist keine Förmlichkeit — ich soll dein Passwort nie sehen, und was ich nie
gesehen habe, kann ich auch nicht versehentlich in eine Datei schreiben.

**Schick mir die Verbindungszeichenkette nicht.** Sie enthält das Passwort. Sie
gehört in zwei `.env`-Dateien und sonst nirgendwohin. Wenn ich sie zum Prüfen
brauche, sage ich dir stattdessen, welchen Befehl du ausführst.

## 1 — Cluster anlegen (machst du)

Bei [mongodb.com/atlas](https://www.mongodb.com/atlas) ein Konto anlegen und
einen Cluster erstellen:

| Einstellung | Wert | Warum |
|---|---|---|
| Stufe | **M0 (Free)** | 512 MB. Deine Daten sind 7,6 MB — das reicht auf Jahre. |
| Anbieter | AWS | Der Vorgabewert, tut es. |
| Region | **Frankfurt (eu-central-1)** | Nächstgelegen, und die Daten bleiben in der EU. Bei einer App mit Nutzerkonten ist das kein Detail. |
| Name | `luxfamily` | Frei wählbar. |

## 2 — Zugang einrichten (machst du)

**Datenbank-Benutzer** unter *Database Access*:

- Benutzername z. B. `luxfamily-app`
- Passwort **von Atlas erzeugen lassen** („Autogenerate Secure Password"), nicht
  selbst ausdenken. Einmal kopieren, in den Passwortmanager.
- Rolle: *Read and write to any database*

**Netzwerkzugang** unter *Network Access*. Hier ist eine Abwägung, die du kennen
solltest: Emergents Container hat vermutlich keine feste IP-Adresse, du wirst
also `0.0.0.0/0` eintragen müssen — erreichbar von überall.

Das heißt: **Das Passwort ist dann der einzige Schutz.** Deshalb der
Atlas-Generator und nicht etwas Ausgedachtes. Eine MongoDB, die offen im Netz
steht, wird binnen Stunden gefunden; eine mit einem 32-stelligen Zufallspasswort
ist trotzdem sicher.

Die Verbindungszeichenkette bekommst du unter *Connect → Drivers*. Sie sieht so
aus, mit deinem Passwort an der Stelle von `<password>`:

```
mongodb+srv://luxfamily-app:<password>@luxfamily.xxxxx.mongodb.net/
```

## 3 — Kopieren und prüfen (macht Emergent)

Emergents Datenbank ist die Wahrheit, nicht meine lokale: Dort laufen die
Crawler, dort steht der aktuelle Bestand. Also wird von dort kopiert.

Das Werkzeug dafür ist [`backend/copy_database.py`](backend/copy_database.py).
Es nimmt das Ziel aus Umgebungsvariablen und **nicht** aus einem Befehlsargument
— ein Passwort in der Kommandozeile landet in der Shell-History, in `ps` und in
jedem Log, das den Aufruf mitschreibt.

```bash
export TARGET_MONGO_URL='mongodb+srv://...'
export TARGET_DB_NAME='luxfamily'

python3 copy_database.py            # zeigt, was kopiert würde
python3 copy_database.py --write    # kopiert
python3 copy_database.py --verify   # zählt beide Seiten und vergleicht
```

`--verify` ist ein eigener Befehl und kein Teil des Kopierens. Das ist Absicht:
„Der Kopiervorgang meldet Erfolg" und „die Daten sind wirklich drüben" sind zwei
verschiedene Aussagen, und in diesem Projekt haben schon zwei Skripte das erste
gemeldet, ohne dass das zweite stimmte.

**Erst wenn `--verify` überall gleiche Zahlen zeigt, geht es weiter.**

## 4 — Umschalten (macht Emergent)

In Emergents `backend/.env` die `MONGO_URL` durch die Atlas-Zeichenkette
ersetzen und `DB_NAME` auf `luxfamily` setzen, dann `supervisorctl restart
backend`.

Danach die App im Browser öffnen und schauen, ob Events erscheinen.

**Der Rückweg**, falls etwas nicht stimmt: alte `MONGO_URL` zurück,
neu starten. Die alte Datenbank wurde nur gelesen, nie verändert — sie steht
vollständig da, als wäre nichts gewesen.

## 5 — Mein Rechner kommt dazu (machst du)

In `backend/.env` hier dieselben zwei Zeilen eintragen. `.env` ist in
`.gitignore` und war noch nie im Repository — das habe ich geprüft.

Danach sehe ich dieselben Daten wie Emergent, und Berichte müssen nicht mehr
gegeneinander gelesen werden.

**Ein Hinweis dazu:** Ab dann arbeite ich auf den echten Daten. Ich werde vor
jedem schreibenden Zugriff fragen, und die Skripte hier laufen ohnehin alle
zuerst im Trockenlauf. Deine lokale MongoDB kannst du behalten — sie ist dann
eine Spielwiese, auf der nichts kaputtgehen kann.

## Was danach besser ist

- Eine Zahl statt zwei. Kein „bei mir 528, bei dir 558" mehr.
- Die Daten überleben Emergents Container. Heute hängt der Bestand daran, dass
  diese Umgebung bestehen bleibt.
- Atlas legt automatische Sicherungen an. Heute gibt es keine.

## Was schlechter ist, ehrlichkeitshalber

- Eine Datenbank im Netz statt zwei in privaten Umgebungen. Das Passwort trägt
  ab dann die ganze Last.
- Etwas mehr Latenz als bei einer Datenbank im selben Container. Bei diesen
  Datenmengen nicht spürbar.
- Wenn Atlas ausfällt, ist die App ohne Daten. Bei M0 gibt es keine Zusage.
