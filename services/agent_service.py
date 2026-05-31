"""Multi-agent answer orchestration."""

from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path

from models.task_result import TaskResult
from services.ai_provider import AIProvider

LOGGER = logging.getLogger(__name__)
MAX_UNCERTAIN_ATTEMPTS = 3
UNCERTAIN_THRESHOLD = 0.65


class AgentService:
    def __init__(self, ai_service: AIProvider) -> None:
        self.ai_service = ai_service

    def analyze_text(self, text: str, forced_mode: str, agent_count: int) -> TaskResult:
        return self._analyze_with_retry(lambda: self._analyze_once_text(text, forced_mode, agent_count), "text")

    def analyze_image(self, image_path: Path, forced_mode: str, agent_count: int) -> TaskResult:
        return self._analyze_with_retry(lambda: self._analyze_once_image(image_path, forced_mode, agent_count), "screenshot")

    def _analyze_once_text(self, text: str, forced_mode: str, agent_count: int) -> TaskResult:
        count = max(1, min(5, int(agent_count)))
        if count == 1:
            return self.ai_service.analyze_text(text, forced_mode)
        results = self._run_parallel(lambda: self.ai_service.analyze_text(text, forced_mode), count)
        return self.ai_service.judge_results(results, "text")

    def _analyze_once_image(self, image_path: Path, forced_mode: str, agent_count: int) -> TaskResult:
        count = max(1, min(5, int(agent_count)))
        if count == 1:
            return self.ai_service.analyze_image(image_path, forced_mode)
        results = self._run_parallel(lambda: self.ai_service.analyze_image(image_path, forced_mode), count)
        return self.ai_service.judge_results(results, "screenshot")

    def _analyze_with_retry(self, task, source: str) -> TaskResult:
        attempts: list[TaskResult] = []
        for attempt in range(1, MAX_UNCERTAIN_ATTEMPTS + 1):
            result = task()
            result.source = result.source or source
            attempts.append(result)
            if not self._is_uncertain(result):
                if attempt > 1:
                    result.warnings.append(f"Nach {attempt} Analyseversuchen fachlich akzeptiert.")
                    result.agent_results = [*result.agent_results, *attempts[:-1]]
                    result.agent_summary = self._retry_summary(attempts, result)
                return result
            if attempt < MAX_UNCERTAIN_ATTEMPTS:
                LOGGER.info("uncertain result, retrying attempt %s/%s", attempt + 1, MAX_UNCERTAIN_ATTEMPTS)

        try:
            final = self.ai_service.judge_results(attempts, source)
        except Exception as exc:
            LOGGER.warning("Retry verifier failed", exc_info=True)
            final = attempts[-1]
            final.warnings.append(f"Retry-Verifier fehlgeschlagen: {exc}")

        if self._is_uncertain(final):
            final.short_answer = "unsicher"
            final.confidence = min(final.confidence, 0.45)
            if "Nach 3 Versuchen nicht eindeutig. Keine Antwort geraten." not in final.warnings:
                final.warnings.append("Nach 3 Versuchen nicht eindeutig. Keine Antwort geraten.")
        final.agent_results = [*final.agent_results, *attempts]
        final.agent_summary = self._retry_summary(attempts, final)
        final.source = source
        return final

    def _run_parallel(self, task, count: int) -> list[TaskResult]:
        results: list[TaskResult] = []
        timeout = max(5, int(getattr(self.ai_service.settings, "timeout_seconds", 30)) + 5)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=count)
        futures = {executor.submit(task): index for index in range(1, count + 1)}
        try:
            done, pending = concurrent.futures.wait(futures, timeout=timeout)
            for future in pending:
                future.cancel()
                index = futures[future]
                results.append(TaskResult.error(f"Agent {index} Timeout nach {timeout} Sekunden."))
            for future in done:
                index = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    LOGGER.warning("Agent %s failed", index, exc_info=True)
                    result = TaskResult.error(f"Agent {index} Fehler: {exc}")
                results.append(result)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return results

    @staticmethod
    def _is_uncertain(result: TaskResult) -> bool:
        if result.short_answer == "Fehler":
            return False
        answer = (result.short_answer or "").strip().lower()
        if answer == "unsicher" or result.task_type in {"incomplete_task"}:
            return True
        if result.confidence < UNCERTAIN_THRESHOLD and result.task_type not in {"no_task"}:
            return True
        return any("unsicher" in warning.lower() or "unklar" in warning.lower() for warning in result.warnings)

    @staticmethod
    def _retry_summary(attempts: list[TaskResult], final_result: TaskResult) -> str:
        lines = [
            "Unsicherheits-Retry: maximal 3 Versuche.",
            "Verifier entscheidet fachlich, keine Mehrheitsentscheidung.",
            f"Versuche: {len(attempts)}",
            f"Finale Antwort: {final_result.short_answer or final_result.full_answer}",
        ]
        for index, attempt in enumerate(attempts, start=1):
            answer = attempt.short_answer or attempt.full_answer
            lines.append(f"Versuch {index}: {answer} ({attempt.confidence_percent}%)")
        return "\n".join(lines)
