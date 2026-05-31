"""Provider routing for OpenAI, Gemini, auto fallback, and comparison mode."""

from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path
from statistics import mean

from models.app_settings import AppSettings
from models.task_result import TaskResult
from services.gemini_service import GeminiService
from services.openai_service import OpenAIService
from services.task_detector import TaskDetector
from utils.validation import looks_like_api_key, looks_like_gemini_api_key

LOGGER = logging.getLogger(__name__)
HARD_TASK_TYPES = {"multiple_choice", "calculation", "accounting"}
HARD_TEXT_KEYWORDS = (
    "buchungssatz",
    "soll",
    "haben",
    "skonto",
    "rabatt",
    "kalkulation",
    "bezugskalkulation",
    "absatzkalkulation",
    "maengelruege",
    "mängelrüge",
    "mahnung",
    "verzug",
    "kaufvertrag",
    "prozent",
    "%",
    "gleichung",
)


class AIProviderRouter:
    def __init__(self, settings: AppSettings, detector: TaskDetector) -> None:
        self.settings = settings
        self.detector = detector
        self.openai = OpenAIService(settings, detector)
        self.gemini = GeminiService(settings, detector)

    def update_settings(self, settings: AppSettings) -> None:
        self.settings = settings
        self.openai.update_settings(settings)
        self.gemini.update_settings(settings)

    def analyze_task(
        self,
        input_text: str = "",
        image_path: Path | None = None,
        settings: AppSettings | None = None,
        forced_mode: str = "auto",
    ) -> TaskResult:
        if settings is not None and settings is not self.settings:
            self.update_settings(settings)
        if image_path is not None:
            return self.analyze_image(image_path, forced_mode)
        return self.analyze_text(input_text, forced_mode)

    def analyze_text(self, text: str, forced_mode: str = "auto") -> TaskResult:
        return self._route(input_text=text, image_path=None, forced_mode=forced_mode, source="text")

    def analyze_image(self, image_path: Path, forced_mode: str = "auto") -> TaskResult:
        return self._route(input_text="", image_path=image_path, forced_mode=forced_mode, source="screenshot")

    def judge_results(self, results: list[TaskResult], source: str) -> TaskResult:
        return self._judge(results, source)

    def should_prefer_provider_compare_for_text(self, text: str, forced_mode: str = "auto") -> bool:
        if self.settings.ai_provider == "compare":
            return True
        return self._can_compare() and self._looks_hard_text(text, forced_mode)

    def should_route_screenshot_once_for_hard_compare(self) -> bool:
        return self._can_compare() and self.settings.ai_provider != "compare"

    def has_usable_key(self) -> bool:
        provider = self.settings.ai_provider
        if provider == "openai":
            return self._has_openai_key()
        if provider == "gemini":
            return self._has_gemini_key()
        return self._has_openai_key() or self._has_gemini_key()

    def missing_key_message(self) -> str:
        provider = self.settings.ai_provider
        if provider == "gemini":
            return "Gemini API-Key fehlt. Bitte im Control Center eintragen."
        if provider == "compare" and not (self._has_openai_key() and self._has_gemini_key()):
            return "Vergleich braucht OpenAI- und Gemini-Key. Bitte im Control Center eintragen."
        return "API-Key fehlt. Bitte OpenAI- oder Gemini-Key im Control Center eintragen."

    def _route(self, input_text: str, image_path: Path | None, forced_mode: str, source: str) -> TaskResult:
        provider = self.settings.ai_provider
        if provider == "compare":
            return self._compare(input_text, image_path, forced_mode, source)
        if source == "text" and self._can_compare() and self._looks_hard_text(input_text, forced_mode):
            return self._compare_with_reason(
                input_text,
                image_path,
                forced_mode,
                source,
                "Schwierige Aufgabe vorab erkannt.",
            )
        if provider == "gemini":
            result = self._call_provider("gemini", input_text, image_path, forced_mode)
            return self._maybe_compare_after_primary(result, input_text, image_path, forced_mode, source)
        if provider == "auto":
            result = self._auto(input_text, image_path, forced_mode)
            return self._maybe_compare_after_primary(result, input_text, image_path, forced_mode, source)
        result = self._call_provider("openai", input_text, image_path, forced_mode)
        return self._maybe_compare_after_primary(result, input_text, image_path, forced_mode, source)

    def _auto(self, input_text: str, image_path: Path | None, forced_mode: str) -> TaskResult:
        ordered = self._auto_order()
        errors: list[str] = []
        for index, provider in enumerate(ordered):
            try:
                result = self._call_provider(provider, input_text, image_path, forced_mode)
                if index > 0:
                    notice = f"Fallback genutzt: {self._provider_label(provider)}"
                    if notice not in result.warnings:
                        result.warnings.append(notice)
                    result.fallback_used = True
                return result
            except Exception as exc:
                LOGGER.warning("%s provider failed in auto mode: %s", provider, exc)
                errors.append(f"{self._provider_label(provider)}: {exc}")
        raise RuntimeError("; ".join(errors) or "Kein KI-Anbieter verfuegbar.")

    def _compare(self, input_text: str, image_path: Path | None, forced_mode: str, source: str) -> TaskResult:
        providers = [provider for provider in ("openai", "gemini") if self._provider_has_key(provider)]
        if not providers:
            raise RuntimeError("Vergleich braucht mindestens einen API-Key.")
        if len(providers) == 1:
            result = self._call_provider(providers[0], input_text, image_path, forced_mode)
            result.warnings.append(f"Vergleich nur mit {self._provider_label(providers[0])}: zweiter API-Key fehlt.")
            return result

        timeout = max(5, int(self.settings.timeout_seconds) + 5)
        results: list[TaskResult] = []
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        futures = {
            executor.submit(self._call_provider, provider, input_text, image_path, forced_mode): provider
            for provider in providers
        }
        try:
            done, pending = concurrent.futures.wait(futures, timeout=timeout)
            for future in pending:
                future.cancel()
                provider = futures[future]
                results.append(TaskResult.error(f"{self._provider_label(provider)} Timeout nach {timeout} Sekunden.", source=source))
            for future in done:
                provider = futures[future]
                try:
                    result = future.result()
                    result.warnings.append(f"Anbieter: {self._provider_label(provider)}")
                except Exception as exc:
                    LOGGER.warning("%s failed in compare mode", provider, exc_info=True)
                    result = TaskResult.error(f"{self._provider_label(provider)} Fehler: {exc}", source=source)
                results.append(result)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if len([result for result in results if result.short_answer != "Fehler"]) == 1:
            winner = next(result for result in results if result.short_answer != "Fehler")
            winner.agent_results = results
            winner.agent_summary = self._compare_summary(results, winner, "Nur ein Anbieter lieferte eine nutzbare Antwort.")
            self._aggregate_usage(winner, results)
            return winner
        return self._judge(results, source)

    def _compare_with_reason(
        self,
        input_text: str,
        image_path: Path | None,
        forced_mode: str,
        source: str,
        reason: str,
    ) -> TaskResult:
        result = self._compare(input_text, image_path, forced_mode, source)
        notice = f"Schwierige Aufgabe: OpenAI und Gemini verglichen. {reason}"
        if notice not in result.warnings:
            result.warnings.append(notice)
        return result

    def _maybe_compare_after_primary(
        self,
        primary: TaskResult,
        input_text: str,
        image_path: Path | None,
        forced_mode: str,
        source: str,
    ) -> TaskResult:
        if not self._can_compare() or primary.provider == "compare":
            return primary
        if not self._result_needs_provider_compare(primary):
            return primary
        primary_provider = primary.provider if primary.provider in {"openai", "gemini"} else self._primary_provider_name()
        other_provider = "gemini" if primary_provider == "openai" else "openai"
        if not self._provider_has_key(other_provider):
            return primary
        results = [primary]
        try:
            other = self._call_provider(other_provider, input_text, image_path, forced_mode)
            other.warnings.append(f"Anbieter: {self._provider_label(other_provider)}")
            results.append(other)
        except Exception as exc:
            LOGGER.warning("%s failed in hard-task provider compare", other_provider, exc_info=True)
            results.append(TaskResult.error(f"{self._provider_label(other_provider)} Fehler: {exc}", source=source))
        judged = self._judge(results, source)
        notice = "Schwierige Aufgabe: OpenAI und Gemini verglichen. Verifier entscheidet fachlich."
        if notice not in judged.warnings:
            judged.warnings.append(notice)
        return judged

    def _judge(self, results: list[TaskResult], source: str) -> TaskResult:
        valid_results = [result for result in results if result.short_answer != "Fehler"]
        if not valid_results:
            return TaskResult.error("Alle Anbieter-/Agentenlaeufe sind fehlgeschlagen.", source=source)
        try:
            if self._has_openai_key():
                judged = self.openai.judge_results(valid_results, source)
            elif self._has_gemini_key():
                judged = self.gemini.judge_results(valid_results, source)
            else:
                judged = self._local_judge(valid_results, source)
        except Exception as exc:
            LOGGER.warning("Provider judge failed, using local fallback", exc_info=True)
            judged = self._local_judge(valid_results, source, str(exc))
        judged.agent_results = results
        judged.agent_summary = self._compare_summary(valid_results, judged, "")
        self._aggregate_usage(judged, results)
        return judged

    def _call_provider(self, provider: str, input_text: str, image_path: Path | None, forced_mode: str) -> TaskResult:
        service = self.openai if provider == "openai" else self.gemini
        result = service.analyze_task(
            input_text=input_text,
            image_path=image_path,
            settings=self.settings,
            forced_mode=forced_mode,
        )
        result.source = result.source or ("screenshot" if image_path is not None else "text")
        result.provider = result.provider if result.provider != "unknown" else provider
        result.provider_mode = self.settings.ai_provider
        return result

    def _auto_order(self) -> list[str]:
        if self._has_openai_key():
            ordered = ["openai"]
            if self._has_gemini_key():
                ordered.append("gemini")
            return ordered
        if self._has_gemini_key():
            return ["gemini"]
        return ["openai", "gemini"]

    def _provider_has_key(self, provider: str) -> bool:
        return self._has_openai_key() if provider == "openai" else self._has_gemini_key()

    def _can_compare(self) -> bool:
        return self._has_openai_key() and self._has_gemini_key()

    def _primary_provider_name(self) -> str:
        if self.settings.ai_provider in {"openai", "gemini"}:
            return self.settings.ai_provider
        return "openai" if self._has_openai_key() else "gemini"

    def _looks_hard_text(self, text: str, forced_mode: str = "auto") -> bool:
        if forced_mode in HARD_TASK_TYPES:
            return True
        value = (text or "").lower()
        detected = self.detector.quick_detect(text or "")
        if detected in HARD_TASK_TYPES:
            return True
        return any(keyword in value for keyword in HARD_TEXT_KEYWORDS)

    @staticmethod
    def _result_needs_provider_compare(result: TaskResult) -> bool:
        if result.short_answer == "Fehler":
            return False
        if result.task_type in HARD_TASK_TYPES:
            return True
        answer = (result.short_answer or "").strip().lower()
        if answer == "unsicher" or result.task_type == "incomplete_task":
            return True
        if result.confidence and result.confidence < 0.75 and result.task_type not in {"no_task"}:
            return True
        return any("unsicher" in warning.lower() or "unklar" in warning.lower() for warning in result.warnings)

    def _has_openai_key(self) -> bool:
        return looks_like_api_key(self.settings.openai_api_key or self.settings.api_key)

    def _has_gemini_key(self) -> bool:
        return looks_like_gemini_api_key(self.settings.gemini_api_key)

    @staticmethod
    def _provider_label(provider: str) -> str:
        return "OpenAI" if provider == "openai" else "Gemini"

    @staticmethod
    def _compare_summary(results: list[TaskResult], final_result: TaskResult, note: str) -> str:
        lines = [
            "Verifier/Judge: fachliche Pruefung, keine Mehrheitsentscheidung.",
            f"Antworten verglichen: {len(results)}",
            f"Finale Antwort: {final_result.short_answer or final_result.full_answer}",
        ]
        if note:
            lines.append(note)
        for index, result in enumerate(results, start=1):
            answer = result.short_answer or result.full_answer
            lines.append(f"Antwort {index}: {answer} ({result.confidence_percent}%)")
        return "\n".join(lines)

    @staticmethod
    def _local_judge(results: list[TaskResult], source: str, warning: str = "") -> TaskResult:
        best = max(results, key=lambda item: item.confidence)
        short_answers = {(item.short_answer or item.full_answer).strip().lower() for item in results}
        confidence = mean(item.confidence for item in results)
        if len(short_answers) == 1:
            confidence = min(0.85, confidence)
        else:
            confidence = min(0.45, best.confidence, confidence)
            best.short_answer = "unsicher"
            best.warnings.append("Antworten widersprechen sich; es wurde nicht nach Mehrheit entschieden.")
        if warning:
            best.warnings.append(f"Judge-Fallback ohne Provider: {warning}")
        best.confidence = confidence
        best.source = source
        return best

    def _aggregate_usage(self, result: TaskResult, compared_results: list[TaskResult]) -> None:
        all_results = [*compared_results]
        result_is_compared = any(item is result for item in all_results)
        own_input = 0 if result_is_compared else int(result.input_tokens or 0)
        own_output = 0 if result_is_compared else int(result.output_tokens or 0)
        own_total = 0 if result_is_compared else int(result.total_tokens or 0)
        own_cost = 0.0 if result_is_compared else float(result.estimated_cost_usd or 0)
        result.input_tokens = own_input + sum(int(item.input_tokens or 0) for item in all_results)
        result.output_tokens = own_output + sum(int(item.output_tokens or 0) for item in all_results)
        result.total_tokens = own_total + sum(int(item.total_tokens or 0) for item in all_results)
        result.estimated_cost_usd = round(
            own_cost + sum(float(item.estimated_cost_usd or 0) for item in all_results),
            8,
        )
        result.provider_mode = self.settings.ai_provider
        result.fallback_used = bool(result.fallback_used or any(item.fallback_used for item in all_results))
        providers = {item.provider for item in all_results if item.provider and item.provider != "unknown"}
        if len(providers) > 1 or self.settings.ai_provider == "compare":
            result.provider = "compare"
        elif providers and result.provider == "unknown":
            result.provider = next(iter(providers))
