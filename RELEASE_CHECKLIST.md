# Moodler Release Checklist

Vor GitHub-Release:

- [ ] Keine `.env` im Projekt committen.
- [ ] Keine lokalen Datenbanken, Logs, `build`, `dist`, `.venv` oder `__pycache__` committen.
- [ ] `python -m compileall .` erfolgreich.
- [ ] `MOODLER_SMOKE_TEST=1 python main.py` erfolgreich.
- [ ] Auto-Copy geprüft: Rechenergebnis, Buchungssatz, Brief/E-Mail.
- [ ] Verlauf zeigt Provider, Modell, Tokens, Kosten, Fallback und kopierten Wert.
- [ ] Unsicherheits-Retry geprüft: maximal 3 Versuche, danach `unsicher`.
- [ ] `build_portable.bat` ausführen.
- [ ] `dist\Moodler-portable.zip` prüfen.
- [ ] ZIP enthält `Moodler.exe`, `README.md`, `.env.example`.
- [ ] ZIP enthält keine `.env`, DBs, Logs, `__pycache__`, Build-Arbeitsdateien oder alte ZIPs.
- [ ] GitHub Release erstellen und `Moodler-portable.zip` als Asset hochladen.

Release-Text kurz:

```text
ZIP herunterladen, entpacken, Moodler.exe starten, Zahnrad öffnen und API-Key eintragen.
Moodler zeigt nur die kleine Bar links oben. Details, Verlauf und Export liegen im Control Center.
```
