"""Multi-agent answer orchestration."""

from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path

from models.task_result import TaskResult
from services.ai_provider import AIProvider

LOGGER = logging.getLogger(__name__)


class AgentService:
    def __init__(self, ai_service: AIProvider) -> None:
        self.ai_service = ai_service

    def analyze_text(self, text: str, forced_mode: str, agent_count: int) -> TaskResult:
        count = max(1, min(5, int(agent_count)))
        if count == 1:
            return self.ai_service.analyze_text(text, forced_mode)
        results = self._run_parallel(lambda: self.ai_service.analyze_text(text, forced_mode), count)
        return self.ai_service.judge_results(results, "text")

    def analyze_image(self, image_path: Path, forced_mode: str, agent_count: int) -> TaskResult:
        count = max(1, min(5, int(agent_count)))
        if count == 1:
            return self.ai_service.analyze_image(image_path, forced_mode)
        results = self._run_parallel(lambda: self.ai_service.analyze_image(image_path, forced_mode), count)
        return self.ai_service.judge_results(results, "screenshot")

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
