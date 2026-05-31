"""Lightweight local task hints before the AI analysis."""

from __future__ import annotations

import re


class TaskDetector:
    EXAM_PATTERNS = [
        r"\bpruefung\b",
        r"\btest\b",
        r"\bnoten?\b",
        r"\bbenotet\b",
        r"\bmoodle-?test\b",
        r"\bquiz\b",
        r"\bexam\b",
    ]

    def quick_detect(self, text: str) -> str:
        value = text.lower()
        if not value.strip():
            return "no_task"
        if re.search(r"\b(a|b|c|d|e)\)", value) or re.search(r"\b[a-e]\s*[:.]\s+", value):
            return "multiple_choice"
        if "richtig" in value and "falsch" in value:
            return "true_false"
        if "___" in value or "..." in value or "luecke" in value or "fill in the blank" in value:
            return "gap_text"
        if any(
            word in value
            for word in [
                "buchungssatz",
                "soll",
                "haben",
                "kalkulation",
                "mahnung",
                "kaufvertrag",
                "lieferung",
                "zahlung",
                "maengel",
                "mängel",
                "ruege",
                "rüge",
                "verzug",
                "skonto",
                "rabatt",
                "umsatzsteuer",
                "ust",
                "zahlungsverkehr",
            ]
        ):
            return "accounting"
        if re.search(r"\d+\s*[%+\-*/=]", value) or "berechne" in value or "solve" in value:
            return "calculation"
        if "zusammenf" in value or "summary" in value:
            return "summary"
        if "karteikarte" in value or "flashcard" in value:
            return "flashcards"
        if "translate" in value or "uebersetze" in value or "uebersetzen" in value:
            return "translation"
        if "email" in value or "e-mail" in value:
            return "email"
        if "brief" in value or "letter" in value:
            return "letter"
        if "korrigiere" in value or "grammar" in value or "rechtschreibung" in value:
            return "grammar"
        if "erklaer" in value or "explain" in value:
            return "explanation"
        return "open_question" if "?" in value else "generic_text"

    def detect_exam_context(self, text: str) -> bool:
        value = text.lower()
        return any(re.search(pattern, value) for pattern in self.EXAM_PATTERNS)
