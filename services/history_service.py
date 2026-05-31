"""History and learning feature service."""

from __future__ import annotations

from database import Database
from models.task_result import Flashcard, TaskResult


class HistoryService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_result(self, result: TaskResult, source: str) -> int:
        history_id = self.database.insert_history(result, source)
        if result.flashcards:
            self.database.insert_flashcards(result.flashcards, result.subject, history_id)
        return history_id

    def save_flashcards_for_result(self, result: TaskResult) -> int:
        cards = result.flashcards
        if not cards and (result.detected_task or result.short_answer or result.full_answer):
            cards = [
                Flashcard(
                    front=result.detected_task or "Aufgabe",
                    back=result.full_answer or result.short_answer or result.explanation,
                )
            ]
        return self.database.insert_flashcards(cards, result.subject, result.id)

    def list_history(self, filter_name: str = "all") -> list[TaskResult]:
        return self.database.list_history(filter_name)

    def list_flashcards(self, filter_name: str = "all") -> list[dict]:
        return self.database.list_flashcards(filter_name)

    def set_favorite(self, history_id: int, favorite: bool) -> None:
        self.database.set_history_favorite(history_id, favorite)

    def set_wrong(self, history_id: int, marked_wrong: bool) -> None:
        self.database.set_history_wrong(history_id, marked_wrong)

    def delete_history(self, history_id: int) -> None:
        self.database.delete_history(history_id)

    def delete_all_history(self) -> None:
        self.database.delete_all_history()

    def reset_costs(self) -> None:
        self.database.reset_costs()

    def cost_summary(self) -> dict:
        return self.database.cost_summary()

    def record_quiz_attempt(self, correct: bool, flashcard_id: int | None = None, history_id: int | None = None) -> None:
        self.database.record_quiz_attempt(correct, flashcard_id=flashcard_id, history_id=history_id)
