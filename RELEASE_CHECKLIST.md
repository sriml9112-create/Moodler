# Moodler Release Checklist

Vor GitHub-Release:

- [ ] Keine `.env` im Projekt committen.
- [ ] Keine lokalen Datenbanken, Logs, `build`, `dist`, `.venv` oder `__pycache__` committen.
- [ ] `python -m compileall .` erfolgreich.
- [ ] `MOODLER_SMOKE_TEST=1 python main.py` erfolgreich.
- [ ] Auto-Copy geprüft: Rechenergebnis, Buchungssatz, Brief/E-Mail.
- [ ] Verlauf zeigt Provider, Modell, Tokens, Kosten, Fallback und kopierten Wert.
- [ ] Unsicherheits-Retry geprüft: maximal 3 Versuche, danach `unsicher`.
- [ ] Screenshot geprüft: Gabll-Modus ist Standard, kein Hook, kein Windows Snipping als Standard, Bewegung friert nicht ein, `Esc`/Rechtsklick/20s Timeout brechen sicher ab.
- [ ] Control Center hat genau 8 Tabs: Dashboard, API, Modelle, Genauigkeit, Automatik, Verlauf, Hilfe, Export.
- [ ] `build_portable.bat` ausführen.
- [ ] `dist\Moodler-portable.zip` prüfen.
- [ ] ZIP enthält `Moodler.exe`, `START_HIER.bat`, `create_shortcut.bat`, `README.md`, `.env.example`.
- [ ] ZIP enthält keine `.env`, DBs, Logs, `__pycache__`, Build-Arbeitsdateien oder alte ZIPs.
- [ ] Optional: Vercel-Downloadseite verlinkt nur auf GitHub-Release und enthält keine API-Keys.
- [ ] GitHub Release erstellen und `Moodler-portable.zip` als Asset hochladen.

Release-Text kurz:

```text
ZIP herunterladen, entpacken, Moodler.exe starten, Zahnrad öffnen und API-Key eintragen.
Moodler zeigt nur die kleine Bar links oben. Details, Verlauf und Export liegen im Control Center.
```
