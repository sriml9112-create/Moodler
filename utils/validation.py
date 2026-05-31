"""Validation and parsing helpers."""

from __future__ import annotations

import json
import re
from typing import Any


def looks_like_api_key(api_key: str | None) -> bool:
    return bool(api_key and api_key.strip().startswith("sk-") and len(api_key.strip()) >= 12)


def looks_like_gemini_api_key(api_key: str | None) -> bool:
    key = (api_key or "").strip()
    return bool(key and len(key) >= 20 and not key.lower().startswith("sk-"))


def has_provider_key(provider: str, openai_key: str | None, gemini_key: str | None) -> bool:
    if provider == "openai":
        return looks_like_api_key(openai_key)
    if provider == "gemini":
        return looks_like_gemini_api_key(gemini_key)
    if provider in {"auto", "compare"}:
        return looks_like_api_key(openai_key) or looks_like_gemini_api_key(gemini_key)
    return False


def clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number > 1:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def safe_json_loads(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def compact_text(text: str, max_len: int = 42) -> str:
    value = " ".join(text.split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def extract_mc_letters(text: str) -> str:
    matches = re.findall(r"\b[A-H]\b", text.upper())
    if matches:
        ordered = []
        for match in matches:
            if match not in ordered:
                ordered.append(match)
        return " ".join(ordered)
    return compact_text(text, 20)
