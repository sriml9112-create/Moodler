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

Kamera klicken, Bereich ziehen, loslassen. Der Bildschirm bleibt normal: kein Overlay, kein Rahmen, keine Texte und keine sichtbare Browser-Textmarkierung. `Esc`, Rechtsklick oder 20 Sekunden ohne Auswahl brechen ab. Danach kann sofort wieder ein Screenshot gestartet werden.

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

## Kosten und Budget

Moodler speichert pro Verlaufseintrag:

- Provider und Modell
- Input-, Output- und Gesamttokens
- geschätzte Kosten
- Provider-Modus (`openai`, `gemini`, `auto`, `compare`)
- ob ein Fallback genutzt wurde

Im Dashboard kannst du ein Startbudget setzen und die lokalen Kostenzähler zurücksetzen. Die Preise liegen in `config.py` und können bei geänderten Anbieterpreisen angepasst werden.

## Modelle und Fallbacks

OpenAI:

- `gpt-5.5` falls verfügbar
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
- `gemini-2.0-flash`
- `gemini-2.0-flash-lite` falls verfügbar

Gemini-Fallback: `gemini-2.5-flash` -> `gemini-2.0-flash`

Wenn ein Modell nicht verfügbar ist, bleibt Moodler bedienbar und schreibt den Fallback-Hinweis in Details und Verlauf.
Für Gemini-3-Preview setzt Moodler die lokale Kostenschätzung auf 0, solange kein belastbarer offizieller Preis in der Config hinterlegt ist.

## BW/HAK-Fokus

Der BW/HAK-Fokus ist intern immer aktiv und nicht als extra Tab sichtbar. Priorisiert werden Betriebswirtschaft, Rechnungswesen, Kaufvertrag, Lieferung, Zahlung, Skonto/Rabatt, Mängelrüge, Mahnung, Verzug, Kalkulation, Buchungssätze, Soll/Haben, USt und Zahlungsverkehr.

Mehrere Agenten sind nur Vergleichswerkzeuge. Moodler soll nicht per Mehrheit entscheiden. Der Verifier prüft fachlich: MC-Optionen einzeln, Mathe durch Einsetzen/Rechnen, BW/RW logisch und rechtlich/fachlich. Wenn keine Lösung sicher passt, zeigt die Bar `unsicher`.

## Schreibstil

Bei Briefen, E-Mails, Texten und Zusammenfassungen verlangt der Prompt kurze, natürliche Texte auf HAK-Schülerniveau: sauber, aber nicht künstlich perfekt; höflich bei Firma/Professor, sonst direkt.

## Automatisches Kopieren

Wenn Auto-Copy aktiv ist, kopiert Moodler Vollantworten direkt in die Zwischenablage für:

`gap_text`, `letter`, `email`, `generic_text`, `summary`, `explanation`, `grammar`, `translation`, `flashcards`.

Die Haupt-Bar bleibt kurz: `Brief kopiert`, `E-Mail kopiert`, `Lücken kopiert`, `Übersetzung kopiert` oder `Text kopiert`.

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
