"""Token and local cost estimation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import MODEL_PRICING_USD_PER_1M


@dataclass(frozen=True, slots=True)
class UsageEstimate:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "fallback_used": self.fallback_used,
        }


def estimate_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    table = MODEL_PRICING_USD_PER_1M.get(provider, {})
    price = table.get(model)
    if not price:
        return 0.0
    input_cost = max(0, int(input_tokens)) * float(price["input"]) / 1_000_000
    output_cost = max(0, int(output_tokens)) * float(price["output"]) / 1_000_000
    return round(input_cost + output_cost, 8)


def approx_token_count(text: str) -> int:
    value = text or ""
    if not value:
        return 0
    return max(1, int(len(value) / 4))


def build_usage_estimate(
    provider: str,
    model: str,
    usage: Any,
    prompt: str,
    raw_output: str,
    fallback_used: bool = False,
) -> UsageEstimate:
    input_tokens = _first_int(
        usage,
        "input_tokens",
        "prompt_tokens",
        "prompt_token_count",
    )
    output_tokens = _first_int(
        usage,
        "output_tokens",
        "completion_tokens",
        "candidates_token_count",
    )
    total_tokens = _first_int(usage, "total_tokens", "total_token_count")

    if input_tokens == 0:
        input_tokens = approx_token_count(prompt)
    if output_tokens == 0:
        output_tokens = approx_token_count(raw_output)
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    return UsageEstimate(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost_usd(provider, model, input_tokens, output_tokens),
        fallback_used=fallback_used,
    )


def _first_int(obj: Any, *names: str) -> int:
    if obj is None:
        return 0
    for name in names:
        value = _get_value(obj, name)
        try:
            if value is not None:
                return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return 0


def _get_value(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
