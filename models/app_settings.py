"""Application settings model."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from config import (
    AI_PROVIDERS,
    BW_FOCUS_SUBJECTS,
    DEFAULT_AI_PROVIDER,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MODEL,
    DEFAULT_OPENAI_MODEL,
    GEMINI_MODELS,
    OPENAI_MODELS,
)


@dataclass(slots=True)
class AppSettings:
    ai_provider: str = DEFAULT_AI_PROVIDER
    openai_model: str = DEFAULT_OPENAI_MODEL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    openai_api_key: str = ""
    gemini_api_key: str = ""
    openai_key_exists: bool = False
    gemini_key_exists: bool = False
    model: str = DEFAULT_MODEL
    api_key: str = ""
    default_mode: str = "auto"
    language: str = "auto"
    timeout_seconds: int = 30
    agent_count: int = 2
    addon_theme: str = "dark"
    confidence_warning_threshold: float = 0.65
    auto_detect_tasks: bool = True
    auto_copy_long_results: bool = True
    auto_save_history: bool = True
    open_details_for_long: bool = True
    mark_bad_screenshots_uncertain: bool = True
    enable_learning_guardrails: bool = True
    bw_focus_enabled: bool = True
    suppress_task_popups: bool = True
    preferred_subjects: list[str] | None = None
    cost_budget_usd: float = 0.0
    toolbar_x: int = 5
    toolbar_y: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        settings = cls()
        for field_name in asdict(settings):
            if field_name in data:
                setattr(settings, field_name, data[field_name])
        if "openai_model" not in data and "model" in data:
            settings.openai_model = str(data.get("model", ""))
        if "openai_api_key" not in data and "api_key" in data:
            settings.openai_api_key = str(data.get("api_key", ""))
        if not settings.openai_api_key and settings.api_key:
            settings.openai_api_key = str(settings.api_key)
        if not settings.api_key and settings.openai_api_key:
            settings.api_key = str(settings.openai_api_key)
        if not settings.openai_model and settings.model:
            settings.openai_model = str(settings.model)
        if not settings.model and settings.openai_model:
            settings.model = str(settings.openai_model)
        if settings.ai_provider not in AI_PROVIDERS:
            settings.ai_provider = DEFAULT_AI_PROVIDER
        if settings.openai_model not in OPENAI_MODELS:
            settings.openai_model = DEFAULT_OPENAI_MODEL
        if settings.model not in OPENAI_MODELS:
            settings.model = settings.openai_model
        if settings.gemini_model not in GEMINI_MODELS:
            settings.gemini_model = DEFAULT_GEMINI_MODEL
        settings.api_key = settings.openai_api_key
        settings.model = settings.openai_model
        settings.openai_key_exists = bool(settings.openai_api_key)
        settings.gemini_key_exists = bool(settings.gemini_api_key)
        if settings.default_mode not in {"auto", "screenshot", "text"}:
            settings.default_mode = "auto"
        if settings.language not in {"auto", "de", "en"}:
            settings.language = "auto"
        if settings.addon_theme not in {"dark", "contrast"}:
            settings.addon_theme = "dark"
        settings.timeout_seconds = int(settings.timeout_seconds)
        if settings.timeout_seconds not in {15, 30, 60}:
            settings.timeout_seconds = 30
        settings.agent_count = int(settings.agent_count)
        settings.agent_count = max(1, min(5, settings.agent_count))
        settings.confidence_warning_threshold = float(settings.confidence_warning_threshold)
        settings.confidence_warning_threshold = max(0.0, min(1.0, settings.confidence_warning_threshold))
        settings.enable_learning_guardrails = True
        settings.bw_focus_enabled = True
        settings.suppress_task_popups = True
        settings.preferred_subjects = list(BW_FOCUS_SUBJECTS)
        settings.cost_budget_usd = cls._safe_money(settings.cost_budget_usd)
        settings.toolbar_x = cls._safe_position_value(settings.toolbar_x)
        settings.toolbar_y = cls._safe_position_value(settings.toolbar_y)
        return settings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _safe_position_value(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 5
        return number if -100000 <= number <= 100000 else 5

    @staticmethod
    def _safe_money(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(number, 1_000_000.0))
