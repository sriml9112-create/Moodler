"""Clipboard helpers with tkinter fallback."""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class ClipboardService:
    def __init__(self, root: Any | None = None) -> None:
        self.root = root

    def set_root(self, root: Any) -> None:
        self.root = root

    def copy(self, text: str) -> bool:
        if not text:
            return False
        try:
            import pyperclip

            pyperclip.copy(text)
            return True
        except Exception:
            pass
        if self.root is None:
            return False
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            return True
        except Exception:
            LOGGER.warning("Could not copy to clipboard", exc_info=True)
            return False

    def paste(self) -> str:
        try:
            import pyperclip

            value = pyperclip.paste()
            return value if isinstance(value, str) else ""
        except Exception:
            pass
        if self.root is None:
            return ""
        try:
            return str(self.root.clipboard_get())
        except Exception:
            return ""

    def works(self) -> bool:
        marker = "moodler-clipboard-check"
        original = self.paste()
        if not self.copy(marker):
            return False
        ok = self.paste() == marker
        if original:
            self.copy(original)
        return ok
