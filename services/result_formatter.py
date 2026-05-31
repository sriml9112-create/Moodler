"""Format AI results for the compact toolbar."""

from __future__ import annotations

import re

from models.app_settings import AppSettings
from models.task_result import TaskResult
from utils.validation import compact_text, extract_mc_letters


class ResultFormatter:
    COPY_TYPES = {
        "gap_text",
        "letter",
        "email",
        "generic_text",
        "summary",
        "explanation",
        "grammar",
        "translation",
        "flashcards",
    }
    VALUE_COPY_TYPES = {"calculation", "accounting"}
    ACCOUNTING_KEYWORDS = (
        "buchung",
        "buchungssatz",
        "soll",
        "haben",
        "ust",
        "umsatzsteuer",
        "vorsteuer",
        "erloes",
        "erlös",
        "bank",
        "kassa",
        "lieferant",
        "kunde",
    )
    MONEY_RE = re.compile(
        r"(?<![\w])(?:-?\d{1,3}(?:[.\s]\d{3})*|-?\d+)(?:,\d{1,4})?\s?(?:\u20ac|eur|euro)?",
        re.IGNORECASE,
    )
    EURO_RE = re.compile(
        r"(?<![\w])(?:-?\d{1,3}(?:[.\s]\d{3})*|-?\d+)(?:,\d{1,4})?\s?(?:\u20ac|eur\b|euro\b)",
        re.IGNORECASE,
    )

    def toolbar_text(self, result: TaskResult, settings: AppSettings) -> str:
        if result.confidence < settings.confidence_warning_threshold and result.task_type not in {"no_task", "incomplete_task"}:
            return "unsicher"
        if result.task_type == "multiple_choice":
            return extract_mc_letters(result.short_answer or result.full_answer)
        if result.task_type == "true_false":
            value = (result.short_answer or result.full_answer).strip().lower()
            if "falsch" in value or value == "false":
                return "falsch"
            if "richtig" in value or value == "true":
                return "richtig"
            return compact_text(value, 18)
        if result.task_type == "gap_text":
            return "Luecken kopiert" if settings.auto_copy_long_results else "Luecken ergaenzt"
        if result.task_type == "letter":
            return "Brief kopiert" if settings.auto_copy_long_results else "Details offen"
        if result.task_type == "email":
            return "E-Mail kopiert" if settings.auto_copy_long_results else "Details offen"
        if result.task_type in {"generic_text", "grammar"}:
            return "Text kopiert" if settings.auto_copy_long_results else "Details offen"
        if result.task_type == "summary":
            return "Zusammenfassung kopiert" if settings.auto_copy_long_results else compact_text(result.short_answer or result.full_answer, 42)
        if result.task_type == "explanation":
            return "Erklaerung kopiert" if settings.auto_copy_long_results else compact_text(result.short_answer or result.full_answer, 42)
        if result.task_type == "calculation":
            if settings.auto_copy_long_results and result.copied_value:
                return "Ergebnis kopiert"
            return compact_text(result.short_answer or result.full_answer, 28)
        if result.task_type == "accounting":
            if settings.auto_copy_long_results and result.copied_value:
                return "Buchung kopiert" if self.is_booking_value(result.copied_value) else "Ergebnis kopiert"
            return compact_text(result.short_answer or result.full_answer, 34)
        if result.task_type == "translation":
            return "Uebersetzung kopiert" if settings.auto_copy_long_results else compact_text(result.short_answer or "Uebersetzt", 34)
        if result.task_type == "flashcards":
            return "Karten kopiert" if settings.auto_copy_long_results else f"{len(result.flashcards)} Karten"
        if result.task_type == "incomplete_task":
            return "unsicher"
        if result.task_type == "no_task":
            return "nichts erkannt"
        return compact_text(result.short_answer or result.full_answer or "fertig", 42)

    def should_copy_full_answer(self, result: TaskResult, settings: AppSettings) -> bool:
        return bool(self.auto_copy_text(result, settings))

    def auto_copy_text(self, result: TaskResult, settings: AppSettings) -> str:
        if not settings.auto_copy_long_results or self._is_uncertain(result, settings):
            return ""
        if result.task_type in self.COPY_TYPES:
            return self.clipboard_text(result).strip()
        if result.task_type in self.VALUE_COPY_TYPES:
            return self.extract_copied_value(result).strip()
        return ""

    def clipboard_text(self, result: TaskResult) -> str:
        if result.copied_value and result.task_type in self.VALUE_COPY_TYPES:
            return result.copied_value
        if result.full_answer:
            return result.full_answer
        if result.flashcards:
            return "\n\n".join(f"{card.front}\n{card.back}" for card in result.flashcards)
        return result.explanation or result.short_answer

    def should_open_details(self, result: TaskResult, settings: AppSettings) -> bool:
        if not settings.open_details_for_long:
            return False
        return (
            result.task_type in self.COPY_TYPES
            or result.task_type in self.VALUE_COPY_TYPES
            or bool(result.warnings)
            or result.confidence < settings.confidence_warning_threshold
        )

    def extract_copied_value(self, result: TaskResult) -> str:
        source = "\n".join(
            part for part in [result.short_answer, result.full_answer, result.explanation] if part
        ).strip()
        if not source:
            return ""
        if result.task_type == "accounting":
            booking = self._extract_booking_entry(source)
            if booking:
                return booking
        return self._extract_final_number_or_result(source)

    def is_booking_value(self, value: str) -> bool:
        lowered = value.lower()
        if " an " in lowered:
            return True
        if "/" in lowered and any(keyword in lowered for keyword in self.ACCOUNTING_KEYWORDS):
            return True
        return any(keyword in lowered for keyword in ("buchungssatz", "soll", "haben"))

    def _extract_booking_entry(self, text: str) -> str:
        lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
        candidates: list[str] = []
        for line in lines:
            lowered = line.lower()
            if "buchungssatz" in lowered and ":" in line:
                line = line.split(":", 1)[1].strip()
                lowered = line.lower()
            has_booking_separator = " an " in lowered or (" / " in lowered and any(k in lowered for k in self.ACCOUNTING_KEYWORDS))
            has_accounting_terms = any(keyword in lowered for keyword in self.ACCOUNTING_KEYWORDS)
            if has_booking_separator and has_accounting_terms:
                candidates.append(line)
        if candidates:
            return candidates[0]
        for line in lines:
            lowered = line.lower()
            if "soll" in lowered and "haben" in lowered:
                return line
        return ""

    def _extract_final_number_or_result(self, text: str) -> str:
        labelled = self._extract_labelled_result(text)
        if labelled:
            return labelled
        numbers = [match.group(0).strip() for match in self.MONEY_RE.finditer(text)]
        numbers = [number for number in numbers if any(char.isdigit() for char in number)]
        if not numbers:
            return compact_text(text, 42)
        money_numbers = [number for number in numbers if "€" in number or "eur" in number.lower() or "euro" in number.lower()]
        value = (money_numbers or numbers)[-1].strip()
        value = re.sub(r"\s*(?:eur|euro)\b", " €", value, flags=re.IGNORECASE)
        return value.strip()

    def _extract_labelled_result(self, text: str) -> str:
        result_lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip(" -•\t")
            lowered = line.lower()
            if not line:
                continue
            if any(marker in lowered for marker in ("ergebnis", "endbetrag", "endpreis", "listenverkaufspreis", "verkaufspreis", "zahlung", "skonto", "rabatt")):
                result_lines.append(line)
        for line in reversed(result_lines):
            if "=" in line:
                right = line.rsplit("=", 1)[1].strip()
                if right:
                    number_match = list(self.EURO_RE.finditer(right)) or list(self.MONEY_RE.finditer(right))
                    if number_match:
                        return number_match[-1].group(0).strip()
                    return compact_text(right, 42)
        return ""

    @staticmethod
    def _is_uncertain(result: TaskResult, settings: AppSettings) -> bool:
        answer = (result.short_answer or "").strip().lower()
        if answer == "unsicher" or result.task_type in {"no_task", "incomplete_task"}:
            return True
        return result.confidence < settings.confidence_warning_threshold
