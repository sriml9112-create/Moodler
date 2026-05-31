"""Safe Exam Browser compatibility status helpers.

This module only detects SEB presence. It does not bypass, hide from, or
modify SEB restrictions.
"""

from __future__ import annotations

import csv
import logging
import subprocess
from dataclasses import dataclass
from io import StringIO

LOGGER = logging.getLogger(__name__)

SEB_PROCESS_NAMES = {
    "safeexambrowser.exe",
    "sebwindowsclient.exe",
    "sebwinclient.exe",
    "sebservice.exe",
    "sebwindowsservice.exe",
    "sebwindowsconfig.exe",
}


@dataclass(frozen=True, slots=True)
class SEBStatus:
    detected: bool
    processes: tuple[str, ...] = ()
    error: str = ""

    @property
    def label(self) -> str:
        if self.error:
            return "unbekannt"
        return "Ja" if self.detected else "Nein"

    @property
    def details(self) -> str:
        if self.error:
            return self.error
        if self.processes:
            return ", ".join(self.processes)
        return "Kein SEB-Prozess erkannt."


class SEBService:
    """Detect whether Safe Exam Browser is currently running."""

    def status(self) -> SEBStatus:
        try:
            processes = self._running_process_names()
        except Exception as exc:
            LOGGER.debug("SEB process detection failed", exc_info=True)
            return SEBStatus(False, error=str(exc))
        matches = tuple(sorted({name for name in processes if name.lower() in SEB_PROCESS_NAMES}))
        return SEBStatus(bool(matches), matches)

    @staticmethod
    def _running_process_names() -> list[str]:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=3,
        )
        names: list[str] = []
        reader = csv.reader(StringIO(completed.stdout))
        for row in reader:
            if row:
                name = row[0].strip().strip('"')
                if name:
                    names.append(name)
        return names
