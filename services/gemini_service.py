"""Google Gemini integration with Moodler's shared JSON result format."""

from __future__ import annotations

import concurrent.futures
import logging
import mimetypes
import threading
from pathlib import Path
from statistics import mean
from typing import Any

from config import GEMINI_MODEL_FALLBACKS, SYSTEM_PROMPT
from models.app_settings import AppSettings
from models.task_result import TaskResult
from services.cost_service import UsageEstimate, build_usage_estimate
from services.prompt_builder import build_judge_prompt, build_task_prompt
from services.task_detector import TaskDetector
from utils.validation import looks_like_gemini_api_key, safe_json_loads

LOGGER = logging.getLogger(__name__)


class GeminiServiceError(RuntimeError):
    pass


class GeminiService:
    provider_name = "gemini"

    def __init__(self, settings: AppSettings, detector: TaskDetector) -> None:
        self.settings = settings
        self.detector = detector
        self._client: Any | None = None
        self._types: Any | None = None
        self._client_lock = threading.Lock()
        self.last_model_notice = ""

    def update_settings(self, settings: AppSettings) -> None:
        old_key = self.settings.gemini_api_key
        old_model = self.settings.gemini_model
        old_timeout = self.settings.timeout_seconds
        self.settings = settings
        if (
            settings.gemini_api_key != old_key
            or settings.gemini_model != old_model
            or settings.timeout_seconds != old_timeout
        ):
            self._client = None
            self._types = None

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
        if not text.strip():
            return TaskResult(
                task_type="no_task",
                short_answer="nichts erkannt",
                full_answer="Es wurde kein Text eingegeben.",
                confidence=1.0,
                source="text",
            )
        hint = self.detector.quick_detect(text) if forced_mode == "auto" and self.settings.auto_detect_tasks else forced_mode
        if hint == "auto" and not self.settings.auto_detect_tasks:
            hint = "generic_text"
        exam_context = self.detector.detect_exam_context(text)
        prompt = build_task_prompt(self.settings, "text", hint, text, exam_context)
        raw, usage = self._send(prompt, image_path=None)
        result = self._parse_result(raw, "text")
        self._apply_usage(result, usage)
        self._apply_service_warnings(result)
        if exam_context and self.settings.enable_learning_guardrails:
            result.confidence = min(result.confidence, 0.45)
            if not any("Pruefung" in warning or "Test" in warning for warning in result.warnings):
                result.warnings.append("Moeglicher Pruefungs-/Testkontext erkannt: Nutze die Antwort nur zum Lernen.")
        return result

    def analyze_image(self, image_path: Path, forced_mode: str = "auto") -> TaskResult:
        hint = forced_mode if forced_mode != "auto" else ("auto" if self.settings.auto_detect_tasks else "generic_text")
        prompt = build_task_prompt(self.settings, "screenshot", hint, "", False)
        raw, usage = self._send(prompt, image_path=image_path)
        result = self._parse_result(raw, "screenshot")
        self._apply_usage(result, usage)
        self._apply_service_warnings(result)
        return result

    def judge_results(self, results: list[TaskResult], source: str) -> TaskResult:
        valid_results = [result for result in results if result.task_type != "no_task" or result.full_answer]
        if not valid_results:
            return TaskResult.error("Alle Anbieter-/Agentenlaeufe sind fehlgeschlagen.", source=source)
        prompt = build_judge_prompt(valid_results)
        try:
            raw, usage = self._send(prompt, image_path=None)
            judged = self._parse_result(raw, source)
            self._apply_usage(judged, usage)
        except Exception as exc:
            LOGGER.warning("Gemini judge failed, using local fallback", exc_info=True)
            judged = self._local_judge(valid_results, source, str(exc))
        judged.agent_results = results
        judged.agent_summary = self._agent_summary(valid_results, judged)
        return judged

    def _get_client(self) -> tuple[Any, Any]:
        if self._client is not None and self._types is not None:
            return self._client, self._types
        with self._client_lock:
            if self._client is not None and self._types is not None:
                return self._client, self._types
            if not looks_like_gemini_api_key(self.settings.gemini_api_key):
                raise GeminiServiceError("Gemini API-Key fehlt. Bitte im Control Center oder in .env eintragen.")
            try:
                from google import genai
                from google.genai import types
            except Exception as exc:
                raise GeminiServiceError("Google Gen AI SDK fehlt. Installiere die requirements.txt.") from exc
            try:
                self._client = genai.Client(api_key=self.settings.gemini_api_key)
            except Exception as exc:
                raise GeminiServiceError(f"Gemini Client konnte nicht erstellt werden: {exc}") from exc
            self._types = types
            return self._client, self._types

    def _send(self, prompt: str, image_path: Path | None) -> tuple[str, UsageEstimate]:
        self.last_model_notice = ""
        errors: list[str] = []
        candidates = self._candidate_models()
        for index, model in enumerate(candidates, start=1):
            try:
                return self._send_with_timeout(prompt, image_path, model, index > 1)
            except Exception as exc:
                friendly = self._friendly_api_error(exc)
                errors.append(f"{model}: {friendly}")
                if self._model_unavailable(exc) and index < len(candidates):
                    fallback = candidates[index]
                    self.last_model_notice = f"Gemini-Modell {model} nicht verfuegbar, Fallback {fallback} genutzt."
                    LOGGER.warning(self.last_model_notice)
                    continue
                raise GeminiServiceError(friendly) from exc
        raise GeminiServiceError("; ".join(errors) or "Gemini-Fehler ohne Detail.")

    def _send_with_timeout(
        self,
        prompt: str,
        image_path: Path | None,
        model: str,
        fallback_used: bool,
    ) -> tuple[str, UsageEstimate]:
        timeout = max(5, int(self.settings.timeout_seconds))
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._call_model, prompt, image_path, model, fallback_used)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise GeminiServiceError(f"Gemini/API-Timeout nach {timeout} Sekunden.") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _call_model(
        self,
        prompt: str,
        image_path: Path | None,
        model: str,
        fallback_used: bool,
    ) -> tuple[str, UsageEstimate]:
        client, types = self._get_client()
        contents: list[Any] = [prompt]
        if image_path is not None:
            mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
            image_bytes = image_path.read_bytes()
            try:
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
            except TypeError:
                contents.append(types.Part.from_bytes(image_bytes, mime_type=mime_type))

        config = None
        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            )
        except Exception:
            config = {"system_instruction": SYSTEM_PROMPT, "response_mime_type": "application/json"}

        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
        except TypeError:
            fallback_contents = [f"{SYSTEM_PROMPT}\n\n{prompt}", *contents[1:]]
            response = client.models.generate_content(model=model, contents=fallback_contents)
        raw = self._response_text(response)
        usage = build_usage_estimate(
            "gemini",
            model,
            getattr(response, "usage_metadata", None),
            prompt,
            raw,
            fallback_used,
        )
        return raw, usage

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text:
            return str(text)
        candidates = getattr(response, "candidates", None) or []
        parts: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                value = getattr(part, "text", None)
                if value:
                    parts.append(str(value))
        return "\n".join(parts) if parts else str(response)

    def _parse_result(self, raw: str, source: str) -> TaskResult:
        data = safe_json_loads(raw)
        if data is None:
            return TaskResult.error(
                "Die Gemini-Antwort war kein gueltiges JSON. Oeffne Details, pruefe die Eingabe und versuche es erneut.",
                source=source,
            )
        return TaskResult.from_dict(data, raw_response=raw, source=source)

    def _candidate_models(self) -> list[str]:
        candidates = [self.settings.gemini_model, *GEMINI_MODEL_FALLBACKS]
        unique: list[str] = []
        for model in candidates:
            if model and model not in unique:
                unique.append(model)
        return unique

    @staticmethod
    def _friendly_api_error(exc: Exception) -> str:
        text = str(exc).strip() or exc.__class__.__name__
        lowered = text.lower()
        if "timeout" in lowered or "timed out" in lowered:
            return "Gemini/API-Timeout. Internet pruefen oder Timeout im Control Center erhoehen."
        if "api key" in lowered or "apikey" in lowered or "401" in lowered:
            return "Gemini API-Key fehlt oder ist ungueltig. Bitte im Control Center pruefen."
        if GeminiService._model_unavailable(exc):
            return "Gemini-Modell nicht verfuegbar. Moodler versucht einen Fallback."
        if "connection" in lowered or "network" in lowered or "unavailable" in lowered:
            return "Gemini/API nicht erreichbar. Internetverbindung pruefen."
        return f"Gemini-Fehler: {text[:220]}"

    @staticmethod
    def _model_unavailable(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(token in text for token in ["model", "not found", "does not exist", "404", "unsupported"])

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
            best.warnings.append(f"Gemini-Judge-Fallback: {warning}")
        best.confidence = confidence
        best.source = source
        return best

    @staticmethod
    def _agent_summary(results: list[TaskResult], final_result: TaskResult) -> str:
        lines = [
            f"Antworten verglichen: {len(results)}",
            f"Finale Antwort: {final_result.short_answer or final_result.full_answer}",
        ]
        return "\n".join(lines)

    def _apply_service_warnings(self, result: TaskResult) -> None:
        if self.last_model_notice and self.last_model_notice not in result.warnings:
            result.warnings.append(self.last_model_notice)

    def _apply_usage(self, result: TaskResult, usage: UsageEstimate) -> None:
        result.provider = usage.provider
        result.model = usage.model
        result.input_tokens = usage.input_tokens
        result.output_tokens = usage.output_tokens
        result.total_tokens = usage.total_tokens
        result.estimated_cost_usd = usage.estimated_cost_usd
        result.provider_mode = self.settings.ai_provider
        result.fallback_used = usage.fallback_used
