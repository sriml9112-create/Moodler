"""Prompt helpers shared by AI providers."""

from __future__ import annotations

import json

from config import BW_FOCUS_SUBJECTS, BW_FOCUS_TOPICS, JSON_SCHEMA_HINT
from models.app_settings import AppSettings
from models.task_result import TaskResult


def preferred_subjects_text(settings: AppSettings) -> str:
    subjects = settings.preferred_subjects or list(BW_FOCUS_SUBJECTS)
    return ", ".join(subjects) if subjects else "Betriebswirtschaft, Rechnungswesen, Mathematik"


def bw_context_text() -> str:
    topics = ", ".join(BW_FOCUS_TOPICS)
    return (
        "Der Nutzer ist HAK-Schueler. Priorisiere BW/Rechnungswesen/"
        "Kaufvertrag/Zahlungsverkehr/Mahnwesen. Pruefe fachlich korrekt, "
        "nicht per Mehrheit. HAK-BW-Themen: "
        f"{topics}."
    )


def build_task_prompt(
    settings: AppSettings,
    source_type: str,
    mode_hint: str,
    text: str,
    exam_context: bool,
) -> str:
    mode_line = "auto erkennen" if mode_hint == "auto" else mode_hint
    schema_text = json.dumps(JSON_SCHEMA_HINT, ensure_ascii=False, indent=2)
    task_source = (
        "Analysiere den Screenshot. Lies sichtbaren Text/OCR selbst aus dem Bild."
        if source_type == "screenshot"
        else f"Analysiere diesen Text:\n{text}"
    )
    exam_note = (
        "Lokaler Hinweis: Der Text enthaelt moegliche Pruefungs-/Testbegriffe."
        if exam_context
        else "Kein lokaler Pruefungshinweis erkannt."
    )
    return f"""Aufgabe:
{task_source}

Gewuenschter Modus: {mode_line}
Bevorzugte Spracheinstellung: {settings.language}
Bevorzugte Faecher des Nutzers: {preferred_subjects_text(settings)}
{bw_context_text()}
{exam_note}

Erkenne einen dieser task_type-Werte:
multiple_choice, true_false, gap_text, open_question, letter, email,
generic_text, summary, explanation, calculation, accounting, translation,
grammar, flashcards, no_task, incomplete_task.

Antwortlogik:
- multiple_choice: short_answer nur Buchstaben, z.B. "A C"; mehrere richtige Antworten sind erlaubt.
- MC-Richtigkeit: pruefe jede Option einzeln, begruende falsche Optionen in full_answer, short_answer nur bei eindeutiger Fachpruefung.
- true_false: short_answer nur "richtig" oder "falsch".
- gap_text: short_answer "Luecken ergaenzt", full_answer mit ausgefuelltem Text und Alternativen bei Unsicherheit.
- letter/email/generic_text/grammar: kopierbereiten Text in full_answer.
- summary: kurze Stichpunkte, wichtige Begriffe, keine unnoetigen Details.
- explanation: einfache HAK-Erklaerung, mit Beispiel wenn sinnvoll.
- calculation: Formel, Rechenweg, Ergebnis. short_answer ist das Endergebnis.
- Mathe-MC/calculation: Antwortoptionen einzeln einsetzen und rechnerisch pruefen; nicht raten.
- accounting: Buchungssatz/Kalkulation/BW-Loesung mit kurzer HAK-Erklaerung.
- BW/RW: Kaufvertrag, Lieferung, Zahlung, Maengelruege, Mahnung, Verzug, Skonto, Rabatt, Kalkulation, Buchungssaetze, Soll/Haben, Umsatzsteuer und Zahlungsverkehr streng fachlich pruefen.
- flashcards: sinnvolle Karteikarten in flashcards.
- no_task/incomplete_task: ehrlich melden, keine erfundene Aufgabe.

Menschlicher Schreibstil fuer letter/email/generic_text/summary/explanation/grammar/translation:
- Schreibe natuerlich wie ein guter HAK-Schueler, nicht wie ein KI-Text.
- Kurz, klar, glaubwuerdig, schulisch sauber, aber nicht uebertrieben perfekt.
- Keine langen Einleitungen und keine Floskeln wie "hiermit moechte ich Ihnen mitteilen", wenn sie nicht noetig sind.
- Bei Firma, Professor oder Amt hoeflich und sachlich; sonst direkt und menschlich.
- Briefe/E-Mails: sinnvoller Betreff, passende Anrede, kurzer Hauptteil, normale Schlussformel.
- Englisch: natuerliches Schulenglisch, einfache Woerter bevorzugen.

Confidence:
Nutze 0 bis 1. Senke confidence bei abgeschnittenen Screenshots, schlechter Lesbarkeit,
fehlendem Kontext, unklaren Antwortoptionen oder moeglichem Pruefungs-/Testkontext.
Fuege konkrete warnings hinzu, wenn etwas unsicher ist.

JSON-Schema:
{schema_text}

Gib ausschliesslich valides JSON zurueck."""


def build_judge_prompt(results: list[TaskResult]) -> str:
    packed = json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2)
    schema_text = json.dumps(JSON_SCHEMA_HINT, ensure_ascii=False, indent=2)
    return f"""Mehrere Anbieter oder Agenten haben dieselbe Lernaufgabe beantwortet.

Entscheide niemals nach Mehrheit allein. Die Reihenfolge ist:
1. Aufgabe exakt erkennen.
2. Fachlich pruefen.
3. Antwortmoeglichkeiten einzeln verifizieren.
4. Erst danach Antworten vergleichen.

Wenn Antworten widersprechen, entscheidet fachliche Richtigkeit, nicht Stimmenzahl.
Wenn keine Loesung sicher passt, setze short_answer auf "unsicher", senke confidence
und erklaere die Unsicherheit in warnings/full_answer.

MC:
- alle Optionen einzeln pruefen
- falsche Optionen kurz begruenden
- richtige Option fachlich nachweisen
- nur bei Eindeutigkeit Buchstaben in short_answer

Mathe:
- Gleichung, Brueche und Klammern streng lesen
- Antwortoptionen einsetzen
- rechnerisch verifizieren
- keine Abstimmung

BW/RW:
- Kaufvertrag, Lieferung, Zahlung, Maengelruege, Mahnung, Verzug, Skonto,
  Rabatt, Bezugskalkulation, Absatzkalkulation, Buchungssaetze, Soll/Haben,
  Umsatzsteuer und Zahlungsverkehr fachlich/logisch pruefen.

Antworten:
{packed}

Gib wieder ausschliesslich JSON nach diesem Schema zurueck:
{schema_text}"""
