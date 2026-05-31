"""Task result models returned by the AI service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LANGUAGES, SUBJECTS, TASK_TYPES
from utils.validation import clamp_confidence


@dataclass(slots=True)
class Flashcard:
    front: str
    back: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Flashcard":
        return cls(front=str(data.get("front", "")).strip(), back=str(data.get("back", "")).strip())

    def to_dict(self) -> dict[str, str]:
        return {"front": self.front, "back": self.back}


@dataclass(slots=True)
class TaskResult:
    task_type: str = "no_task"
    language: str = "unknown"
    subject: str = "unknown"
    detected_task: str = ""
    short_answer: str = ""
    full_answer: str = ""
    confidence: float = 0.0
    explanation: str = ""
    warnings: list[str] = field(default_factory=list)
    flashcards: list[Flashcard] = field(default_factory=list)
    source: str = "unknown"
    raw_response: str = ""
    agent_results: list["TaskResult"] = field(default_factory=list)
    agent_summary: str = ""
    provider: str = "unknown"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider_mode: str = ""
    fallback_used: bool = False
    copied_value: str = ""
    id: int | None = None
    created_at: str | None = None
    favorite: bool = False
    marked_wrong: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], raw_response: str = "", source: str = "unknown") -> "TaskResult":
        task_type = str(data.get("task_type", "no_task")).strip()
        if task_type not in TASK_TYPES:
            task_type = "no_task"

        language = str(data.get("language", "unknown")).strip()
        if language not in LANGUAGES:
            language = "unknown"

        subject = str(data.get("subject", "unknown")).strip()
        if subject not in SUBJECTS:
            subject = "unknown"

        warnings = data.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = [str(warnings)]

        cards: list[Flashcard] = []
        raw_cards = data.get("flashcards", [])
        if isinstance(raw_cards, list):
            for item in raw_cards:
                if isinstance(item, dict):
                    card = Flashcard.from_dict(item)
                    if card.front and card.back:
                        cards.append(card)

        return cls(
            task_type=task_type,
            language=language,
            subject=subject,
            detected_task=str(data.get("detected_task", "")).strip(),
            short_answer=str(data.get("short_answer", "")).strip(),
            full_answer=str(data.get("full_answer", "")).strip(),
            confidence=clamp_confidence(data.get("confidence", 0)),
            explanation=str(data.get("explanation", "")).strip(),
            warnings=[str(item).strip() for item in warnings if str(item).strip()],
            flashcards=cards,
            source=source,
            raw_response=raw_response,
            copied_value=str(data.get("copied_value", "")).strip(),
        )

    @classmethod
    def error(cls, message: str, source: str = "unknown") -> "TaskResult":
        return cls(
            task_type="no_task",
            short_answer="Fehler",
            full_answer=message,
            confidence=0.0,
            warnings=[message],
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "language": self.language,
            "subject": self.subject,
            "detected_task": self.detected_task,
            "short_answer": self.short_answer,
            "full_answer": self.full_answer,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "warnings": list(self.warnings),
            "flashcards": [card.to_dict() for card in self.flashcards],
            "source": self.source,
            "raw_response": self.raw_response,
            "agent_summary": self.agent_summary,
            "agent_results": [result.to_dict() for result in self.agent_results],
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "provider_mode": self.provider_mode,
            "fallback_used": self.fallback_used,
            "copied_value": self.copied_value,
        }

    @property
    def confidence_percent(self) -> int:
        return int(round(self.confidence * 100))
