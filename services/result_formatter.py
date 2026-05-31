"""Format AI results for the compact toolbar."""

from __future__ import annotations

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
            return compact_text(result.short_answer or result.full_answer, 28)
        if result.task_type == "accounting":
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
        return settings.auto_copy_long_results and result.task_type in self.COPY_TYPES and bool(self.clipboard_text(result))

    def clipboard_text(self, result: TaskResult) -> str:
        if result.full_answer:
            return result.full_answer
        if result.flashcards:
            return "\n\n".join(f"{card.front}\n{card.back}" for card in result.flashcards)
        return result.explanation or result.short_answer

    def should_open_details(self, result: TaskResult, settings: AppSettings) -> bool:
        if not settings.open_details_for_long:
            return False
        return result.task_type in self.COPY_TYPES or bool(result.warnings) or result.confidence < settings.confidence_warning_threshold
