"""Configuration loading and saving."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from config import (
    AI_PROVIDERS,
    APPDATA_DIR,
    CONFIG_PATH,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    GEMINI_MODELS,
    OPENAI_MODELS,
    PROJECT_ROOT,
)
from models.app_settings import AppSettings

LOGGER = logging.getLogger(__name__)


class ConfigService:
    def __init__(self, config_path: Path = CONFIG_PATH, env_path: Path | None = None) -> None:
        self.config_path = config_path
        self.env_path = env_path or PROJECT_ROOT / ".env"
        self._env = self._load_env()
        self.settings = self.load()

    def _load_env(self) -> dict[str, str]:
        try:
            from dotenv import dotenv_values

            return {k: v for k, v in dotenv_values(self.env_path).items() if k and v}
        except Exception:
            return self._load_env_fallback()

    def _load_env_fallback(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        values: dict[str, str] = {}
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def load(self) -> AppSettings:
        data: dict[str, Any] = {}
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                LOGGER.warning("Could not read config file", exc_info=True)
        settings = AppSettings.from_dict(data)
        env_provider = (os.getenv("AI_PROVIDER") or self._env.get("AI_PROVIDER") or "").strip().lower()
        env_openai_key = os.getenv("OPENAI_API_KEY") or self._env.get("OPENAI_API_KEY")
        env_gemini_key = os.getenv("GEMINI_API_KEY") or self._env.get("GEMINI_API_KEY")
        env_openai_model = os.getenv("OPENAI_MODEL") or self._env.get("OPENAI_MODEL") or os.getenv("MOODLER_MODEL") or self._env.get("MOODLER_MODEL")
        env_gemini_model = os.getenv("GEMINI_MODEL") or self._env.get("GEMINI_MODEL")
        env_budget = os.getenv("COST_BUDGET_USD") or self._env.get("COST_BUDGET_USD")
        if env_provider:
            settings.ai_provider = env_provider if env_provider in AI_PROVIDERS else "openai"
        if env_openai_key:
            settings.openai_api_key = env_openai_key
        if env_gemini_key:
            settings.gemini_api_key = env_gemini_key
        if env_openai_model:
            settings.openai_model = env_openai_model if env_openai_model in OPENAI_MODELS else DEFAULT_OPENAI_MODEL
        if env_gemini_model:
            settings.gemini_model = env_gemini_model if env_gemini_model in GEMINI_MODELS else DEFAULT_GEMINI_MODEL
        if env_budget:
            try:
                settings.cost_budget_usd = max(0.0, float(env_budget.replace(",", ".")))
            except ValueError:
                LOGGER.warning("Invalid COST_BUDGET_USD ignored")
        return AppSettings.from_dict(settings.to_dict())

    def save(self, settings: AppSettings | None = None) -> None:
        if settings is not None:
            self.settings = settings
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.settings.to_dict(), indent=2), encoding="utf-8")

    def reload(self) -> AppSettings:
        self._env = self._load_env()
        self.settings = self.load()
        return self.settings
