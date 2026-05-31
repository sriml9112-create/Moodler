"""Shared AI provider interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from models.app_settings import AppSettings
from models.task_result import TaskResult


class AIProviderError(RuntimeError):
    """Raised when a provider cannot complete a task."""


class AIProvider(Protocol):
    provider_name: str
    settings: AppSettings

    def update_settings(self, settings: AppSettings) -> None:
        ...

    def analyze_task(
        self,
        input_text: str = "",
        image_path: Path | None = None,
        settings: AppSettings | None = None,
        forced_mode: str = "auto",
    ) -> TaskResult:
        ...

    def analyze_text(self, text: str, forced_mode: str = "auto") -> TaskResult:
        ...

    def analyze_image(self, image_path: Path, forced_mode: str = "auto") -> TaskResult:
        ...

    def judge_results(self, results: list[TaskResult], source: str) -> TaskResult:
        ...
