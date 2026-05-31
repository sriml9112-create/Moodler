# Moodler

Moodler ist ein kompakter HAK/BW-Lernassistent für Windows. Für den Nutzer bleibt die App bewusst simpel: links oben erscheint nur die alte kleine Moodler-Bar. Keine breite Haupt-App, keine Modus-Auswahl, keine Hover-Texte und keine Popups während Aufgaben.

Moodler ist zum Lernen, Üben, Wiederholen und Formulieren gedacht. Es gibt keine Moodle-Automatisierung, keinen Autoklick und kein Versprechen perfekter Antworten.

## Start

Für normalen Python-Start:

```bat
python main.py
```

Ohne sichtbare Konsole:

```bat
START_HIER.bat
```

Beim Start erscheint nur die kleine Bar bei `200x50+5+5`. Das Control Center öffnet sich erst nach Klick auf das Zahnrad oder beim ersten Senden ohne API-Key.

## Installation

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## API und Anbieter

Option 1: `.env.example` zu `.env` kopieren und Keys eintragen:

```env
OPENAI_API_KEY=
GEMINI_API_KEY=
AI_PROVIDER=openai
OPENAI_MODEL=gpt-4.1
GEMINI_MODEL=gemini-2.5-flash
COST_BUDGET_USD=0
```

Option 2: Moodler starten, Zahnrad klicken, Tab `API` öffnen und Keys eintragen. Keys werden nur maskiert angezeigt.

Anbieter:

- `openai`: nur OpenAI
- `gemini`: nur Gemini
- `auto`: erster verfügbarer Anbieter, leiser Fallback
- `compare`: OpenAI und Gemini antworten, der Verifier entscheidet fachlich

## Alte Haupt-Bar

Die Haupt-Bar bleibt im alten Moodler-Stil:

- `1x`/`2x`: Agenten-Anzahl umschalten
- Kamera: Screenshot-Bereich auswählen
- Pfeil: Aufgabe senden
- Zahnrad: Control Center öffnen
- Reset-Symbol links neben X: Bar nur in der aktuellen Sitzung verschieben
- X: beenden

Die Bar zeigt nur kurze Antworten: MC-Buchstaben, `richtig/falsch`, `Lücken kopiert`, `Text kopiert`, Ergebnis, `unsicher` oder `Error`.

## Screenshot

Standard ist `Gabll-Modus empfohlen`: Kamera klicken, Bereich ziehen, loslassen, Screenshot ist geladen, dann Pfeil/Send drücken. Der Selector ist wieder eine einfache Tkinter-Auswahl wie beim alten Moodler/Gabll: minimale neutrale Alpha-Fläche, dünner neutraler Rahmen, kein Low-Level-Mouse-Hook, kein `grab_set`, kein `wait_window`, kein `wait_variable`, kein blockierender UI-Thread. Mausbewegung bricht nie ab; nur `Esc`, Rechtsklick, Timeout nach 20 Sekunden oder eine zu kleine Auswahl brechen ab.

Im Control Center > Automatik gibt es außerdem `Windows Snipping` als Fallback/Option und `Experimentell unsichtbar` ohne sichtbaren Rahmen. Standard bleibt Gabll.

## Control Center

Das Zahnrad öffnet genau acht Bereiche:

1. Dashboard
2. API
3. Modelle
4. Genauigkeit
5. Automatik
6. Verlauf
7. Hilfe
8. Export

Dashboard zeigt API-Status, Provider, Modell, Agenten, letzte Aufgabe, Copy-Status, letzte Kosten, Gesamtkosten und Restbudget. Live-Balance vom Anbieter wird nicht behauptet; Kosten sind lokal geschätzt.
Zusätzlich siehst du den zuletzt kopierten Wert, z. B. ein Rechenergebnis oder einen Buchungssatz.
Dashboard und Systemcheck zeigen außerdem `SEB erkannt: Ja/Nein`.

## SEB-Kompatibilität

Moodler darf in Safe Exam Browser nur genutzt werden, wenn Schule, Lehrperson oder Prüfungsleitung es ausdrücklich erlauben und die SEB-Konfiguration Moodler als erlaubte Anwendung zulässt.

Moodler versucht nicht, SEB zu umgehen, sich vor SEB zu verstecken oder SEB-Regeln zu verändern. Die SEB-Funktion erkennt nur, ob ein SEB-Prozess läuft, und zeigt diesen Status im Control Center an.

## Kosten und Budget

Moodler speichert pro Verlaufseintrag:

- Provider und Modell
- Input-, Output- und Gesamttokens
- geschätzte Kosten
- Provider-Modus (`openai`, `gemini`, `auto`, `compare`)
- ob ein Fallback genutzt wurde
- den automatisch kopierten Wert

Im Dashboard kannst du ein Startbudget setzen und die lokalen Kostenzähler zurücksetzen. Die Preise liegen in `config.py` und können bei geänderten Anbieterpreisen angepasst werden.

## Modelle und Fallbacks

Die Modellliste ist lokal in `config.py` gepflegt. Nicht freigegebene oder abgeschaltete Modelle führen nicht zum Crash; Moodler versucht automatisch den nächsten Fallback.

OpenAI:

- `gpt-5.5` falls verfügbar
- `gpt-5.4` falls verfügbar
- `gpt-5.4-mini` falls verfügbar
- `gpt-5.2` falls verfügbar
- `gpt-4.1`
- `gpt-4o`
- `gpt-4o-mini`
- `gpt-4.1-mini` falls verfügbar

OpenAI-Fallback: `gpt-4.1` -> `gpt-4o` -> `gpt-4o-mini`

Gemini:

- `gemini-3-pro-preview` falls verfügbar
- `gemini-3-flash-preview` falls verfügbar
- `gemini-2.5-pro`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite` falls verfügbar
- `gemini-2.0-flash` nur Legacy, laut Google ab 2026-06-01 abgeschaltet
- `gemini-2.0-flash-lite` nur Legacy

Gemini-Fallback: `gemini-2.5-flash` -> `gemini-2.5-flash-lite`

Wenn ein Modell nicht verfügbar ist, bleibt Moodler bedienbar und schreibt den Fallback-Hinweis in Details und Verlauf. Die lokale Kostenschätzung nutzt Preise aus `config.py`; Live-Balance vom Anbieter wird nicht behauptet.
Für Preview-Modelle ohne belastbaren lokalen Preis setzt Moodler die Kostenschätzung auf 0, bis die Config aktualisiert wird.

## BW/HAK-Fokus

Der BW/HAK-Fokus ist intern immer aktiv und nicht als extra Tab sichtbar. Priorisiert werden Betriebswirtschaft, Rechnungswesen, Kaufvertrag, Lieferung, Zahlung, Skonto/Rabatt, Mängelrüge, Mahnung, Verzug, Kalkulation, Buchungssätze, Soll/Haben, USt und Zahlungsverkehr.

Mehrere Agenten sind nur Vergleichswerkzeuge. Moodler soll nicht per Mehrheit entscheiden. Der Verifier prüft fachlich: MC-Optionen einzeln, Mathe durch Einsetzen/Rechnen, BW/RW logisch und rechtlich/fachlich. Wenn keine Lösung sicher passt, zeigt die Bar `unsicher`.

Wenn OpenAI- und Gemini-Key vorhanden sind, nutzt Moodler bei schwierigeren Aufgaben automatisch beide Anbieter: MC, Rechnungen, Prozentrechnung, Skonto/Rabatt, Kalkulation, BW/RW, Buchungssätze und unsichere Screenshots werden verglichen. Der Verifier entscheidet fachlich, nicht nach Mehrheit.

## Schreibstil

Bei Briefen, E-Mails, Texten und Zusammenfassungen verlangt der Prompt kurze, natürliche Texte auf HAK-Schülerniveau: sauber, aber nicht künstlich perfekt; höflich bei Firma/Professor, sonst direkt.

## Automatisches Kopieren

Wenn Auto-Copy aktiv ist, kopiert Moodler Vollantworten direkt in die Zwischenablage für:

`gap_text`, `letter`, `email`, `generic_text`, `summary`, `explanation`, `grammar`, `translation`, `flashcards`.

Die Haupt-Bar bleibt kurz: `Brief kopiert`, `E-Mail kopiert`, `Lücken kopiert`, `Übersetzung kopiert` oder `Text kopiert`.

Bei Rechnungen, Prozentrechnung, Skonto/Rabatt, Kalkulationen und BW/RW kopiert Moodler nur das finale Ergebnis, z. B. `2.152,14 €`. Bei Buchungssätzen wird der ganze Buchungssatz kopiert. Die Bar zeigt dafür `Ergebnis kopiert` oder `Buchung kopiert`; der Rechenweg bleibt in Details und Verlauf.

Bei Briefen und E-Mails liest Moodler Empfänger, Ansprechpartner, Betreff, Nummern, Datum, Frist, Ware, Menge, Mangel/Grund und gewünschte Handlung aus der Aufgabe. Fehlende Daten werden nicht erfunden; wenn kein Name vorhanden ist, nutzt Moodler `Sehr geehrte Damen und Herren`.

## App weitergeben

Portable ZIP bauen:

```bat
build_portable.bat
```

Das Ergebnis liegt in:

```text
dist\Moodler-portable.zip
```

Die ZIP enthält keine `.env`, keine lokalen Datenbanken, keine Logs, keine `__pycache__`-Ordner und keine Build-Arbeitsdateien.
In der ZIP kannst du direkt `Moodler.exe` oder `START_HIER.bat` starten. `create_shortcut.bat` erstellt eine Desktop-Verknüpfung aus dem entpackten Ordner.

EXE bauen:

```bat
build_app.bat
```

Desktop-Verknüpfung erstellen:

```bat
create_shortcut.bat
```

Taskleiste: Rechtsklick auf die Desktop-Verknüpfung -> `An Taskleiste anheften`.

## GitHub Release

Für ein Release geeignet:

1. Projekt ohne `.env`, Datenbank, Logs, `build`, `dist` und `.venv` committen.
2. `build_portable.bat` ausführen.
3. `dist\Moodler-portable.zip` als Release-Asset hochladen.
4. In der Release-Beschreibung kurz schreiben: ZIP entpacken, `Moodler.exe` starten, API-Key im Zahnrad eintragen.

`.gitignore` ist dafür vorbereitet.

Optional kann später eine einfache Download-Seite, z. B. auf Vercel, auf das GitHub-Release verlinken. API-Keys gehören dabei niemals ins Frontend; sie bleiben lokal in Moodler bzw. in `.env`.

## Troubleshooting

- API-Key fehlt: Zahnrad -> `API`.
- App wirkt langsam: Agenten senken oder Timeout erhöhen.
- Screenshot abbrechen: `Esc` oder Rechtsklick.
- Antwort unsicher: Details oder Verlauf öffnen.
- Clipboard geht nicht: `pip install -r requirements.txt` erneut ausführen.
- Kosten wirken falsch: lokale Preise in `config.py` prüfen.

## Visual-Check Alte Moodler-Bar

- [x] `200x50+5+5`
- [x] `transparent_color #010101`
- [x] `overrideredirect(True)`
- [x] `topmost`
- [x] Status oben
- [x] Buttons unten
- [x] kleine dunkle Buttons
- [x] keine breite Haupt-Bar
- [x] keine Modus-Auswahl
- [x] keine Tooltips oder Hover-Texte
- [x] Zahnrad ist der einzige sichtbare Zugang zu neuen Features
