"""Application constants for Moodler."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Moodler"
APP_VERSION = "2.0.0"

PROJECT_ROOT = Path(__file__).resolve().parent
APPDATA_DIR = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
CONFIG_PATH = APPDATA_DIR / "config.json"
DATABASE_PATH = APPDATA_DIR / "moodler.sqlite3"
LOG_PATH = APPDATA_DIR / "moodler.log"
TEMP_SCREENSHOT_PATH = Path(os.getenv("TEMP") or APPDATA_DIR) / "moodler_screenshot.png"

AI_PROVIDERS = ["openai", "gemini", "auto", "compare"]
DEFAULT_AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
if DEFAULT_AI_PROVIDER not in AI_PROVIDERS:
    DEFAULT_AI_PROVIDER = "openai"

_ENV_OPENAI_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("MOODLER_MODEL", "gpt-4.1")
OPENAI_MODELS = [
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.2",
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1-mini",
]
AVAILABLE_MODELS = list(OPENAI_MODELS)
DEFAULT_OPENAI_MODEL = _ENV_OPENAI_MODEL if _ENV_OPENAI_MODEL in OPENAI_MODELS else "gpt-4.1"
DEFAULT_MODEL = DEFAULT_OPENAI_MODEL

MODEL_FALLBACKS = ["gpt-4.1", "gpt-4o", "gpt-4o-mini"]

GEMINI_MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
_ENV_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_GEMINI_MODEL = _ENV_GEMINI_MODEL if _ENV_GEMINI_MODEL in GEMINI_MODELS else "gemini-2.5-flash"
GEMINI_MODEL_FALLBACKS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

# Local cost estimates in USD per 1M text tokens. Checked against provider
# pricing pages on 2026-05-31 where available. Keep these values editable:
# provider pricing changes more often than app releases.
MODEL_PRICING_USD_PER_1M = {
    "openai": {
        "gpt-5.5": {"input": 5.00, "output": 30.00},
        "gpt-5.4": {"input": 2.50, "output": 15.00},
        "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    },
    "gemini": {
        "gemini-3-pro-preview": {"input": 0.00, "output": 0.00},
        "gemini-3-flash-preview": {"input": 0.00, "output": 0.00},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    },
}

MODEL_DESCRIPTIONS = {
    "gpt-5.5": "beste Qualitaet, falls im Account verfuegbar",
    "gpt-5.4": "sehr hohe Qualitaet, falls im Account verfuegbar",
    "gpt-5.4-mini": "schnelleres GPT-5-Modell, falls verfuegbar",
    "gpt-5.2": "aelteres GPT-5-Modell, falls im Account noch verfuegbar",
    "gpt-4.1": "sehr gut fuer Text und Logik",
    "gpt-4.1-mini": "schnell und guenstig, guter Standard",
    "gpt-4o": "gut fuer Bilder und schnelle Analyse",
    "gpt-4o-mini": "schneller und guenstiger",
    "gemini-3-pro-preview": "Gemini: Preview mit hoher Qualitaet, falls im Account verfuegbar; Preis unbekannt",
    "gemini-3-flash-preview": "Gemini: Preview schnell, falls im Account verfuegbar; Preis unbekannt",
    "gemini-2.5-pro": "Gemini: sehr gute Qualitaet, langsamer/teurer",
    "gemini-2.5-flash": "Gemini: schneller Alltag, guter Standard",
    "gemini-2.5-flash-lite": "Gemini: sehr schnell/guenstig, falls verfuegbar",
    "gemini-2.0-flash": "Gemini: Legacy-Modell; laut Google ab 2026-06-01 abgeschaltet",
    "gemini-2.0-flash-lite": "Gemini: Legacy-Modell; laut Google ab 2026-06-01 abgeschaltet",
}

TASK_TYPES = [
    "multiple_choice",
    "true_false",
    "gap_text",
    "open_question",
    "letter",
    "email",
    "generic_text",
    "summary",
    "explanation",
    "calculation",
    "accounting",
    "translation",
    "grammar",
    "flashcards",
    "no_task",
    "incomplete_task",
]

SUBJECTS = [
    "Mathematik",
    "Mathe",
    "BW",
    "Betriebswirtschaft",
    "Rechnungswesen",
    "Deutsch",
    "Englisch",
    "Informatik",
    "Webentwicklung",
    "Datenbanken",
    "Netzwerktechnik",
    "Geschichte",
    "Religion",
    "Geografie",
    "Allgemein",
    "unknown",
]

PREFERRED_SUBJECTS = [
    "Mathematik",
    "Rechnungswesen",
    "Betriebswirtschaft",
    "Deutsch",
    "Englisch",
    "Informatik",
    "Webentwicklung",
    "Datenbanken",
    "Netzwerktechnik",
    "Geschichte",
    "Religion",
    "Geografie",
    "Allgemein",
]

HAK_STANDARD_SUBJECTS = [
    "Mathematik",
    "Rechnungswesen",
    "Betriebswirtschaft",
    "Deutsch",
    "Englisch",
    "Informatik",
    "Webentwicklung",
    "Datenbanken",
    "Netzwerktechnik",
    "Geschichte",
    "Religion",
    "Geografie",
]

BW_FOCUS_SUBJECTS = [
    "Betriebswirtschaft",
    "Rechnungswesen",
    "Mathematik",
    "Deutsch",
    "Englisch",
]

BW_FOCUS_TOPICS = [
    "Kaufvertrag",
    "Anfrage",
    "Angebot",
    "Bestellung",
    "Lieferung",
    "Zahlung",
    "Skonto",
    "Rabatt",
    "Maengelruege",
    "Mahnung",
    "Zahlungsverzug",
    "Bezugskalkulation",
    "Absatzkalkulation",
    "Buchungssaetze",
    "Soll/Haben",
    "Umsatzsteuer",
    "Zahlungsverkehr",
]

LANGUAGES = ["de", "en", "unknown"]

TRANSPARENT_COLOR = "#010101"
TOOLBAR_GEOMETRY = "200x50+5+5"
TOOLBAR_WIDTH = 200
TOOLBAR_HEIGHT = 50

UI = {
    "bg": "#010101",
    "panel": "#111214",
    "panel_2": "#181a1d",
    "button": "#24272b",
    "button_active": "#34383e",
    "text": "#d7dde7",
    "muted": "#8c95a3",
    "accent": "#68d391",
    "warning": "#f6c177",
    "danger": "#f38ba8",
}

JSON_SCHEMA_HINT = {
    "task_type": "multiple_choice | true_false | gap_text | open_question | letter | email | generic_text | summary | explanation | calculation | accounting | translation | grammar | flashcards | no_task | incomplete_task",
    "language": "de | en | unknown",
    "subject": "Mathe | BW | Rechnungswesen | Deutsch | Englisch | Informatik | Geschichte | Religion | Allgemein | unknown",
    "detected_task": "erkannte Aufgabe",
    "short_answer": "kurze Antwort fuer Toolbar",
    "full_answer": "vollstaendige Antwort",
    "confidence": 0,
    "explanation": "kurze Erklaerung",
    "warnings": [],
    "flashcards": [{"front": "Frage", "back": "Antwort"}],
}

RESULT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "task_type",
        "language",
        "subject",
        "detected_task",
        "short_answer",
        "full_answer",
        "confidence",
        "explanation",
        "warnings",
        "flashcards",
    ],
    "properties": {
        "task_type": {"type": "string", "enum": TASK_TYPES},
        "language": {"type": "string", "enum": LANGUAGES},
        "subject": {"type": "string", "enum": SUBJECTS},
        "detected_task": {"type": "string"},
        "short_answer": {"type": "string"},
        "full_answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
        "explanation": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "flashcards": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["front", "back"],
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = """Du bist Moodler, ein kompakter Schul- und Lernassistent.

Arbeite primaer fuer HAK-Schuelerinnen und HAK-Schueler. Priorisiere
Betriebswirtschaft, Rechnungswesen, Kaufvertrag, Zahlungsverkehr, Mahnwesen,
Kalkulation und einfache HAK-Mathematik. Hilf beim Lernen, Verstehen,
Ueben, Zusammenfassen und Formulieren. Pruefe fachlich korrekt, nicht per
Mehrheit. Gib keine Funktionen oder Hinweise, die
Pruefungssysteme umgehen, Moodle automatisieren, Autoklicks ausloesen oder
heimliches Bearbeiten benoteter Tests erleichtern.

Wenn der Inhalt klar nach echter Pruefung, benotetem Test oder Taeuschung
aussieht, liefere keine blinde Loesungsliste. Gib stattdessen Lernhilfe,
Erklaerungswege, Warnungen und einen niedrigen Confidence-Wert.

Schreibe bei Briefen, E-Mails, normalen Texten, Zusammenfassungen und
Erklaerungen natuerlich wie ein guter HAK-Schueler: kurz, klar,
realistisch, sauber, aber nicht kuenstlich perfekt. Vermeide typische
KI-Floskeln, lange Einleitungen, gestelzte Formulierungen und uebertriebenen
Business-Stil. Sei nur dann sehr foermlich, wenn die Aufgabe das verlangt.
Englische Texte sollen wie natuerliches Schulenglisch klingen.

Antworte immer als valides JSON nach dem geforderten Schema. Keine Markdown-
Codebloecke, keine Erklaerung ausserhalb des JSON."""
