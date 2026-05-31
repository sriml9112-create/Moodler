"""Screenshot capture service."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
import subprocess
import time
from collections.abc import Callable
from typing import Any, Literal
import ctypes

from PIL import Image, ImageGrab

from config import TEMP_SCREENSHOT_PATH

LOGGER = logging.getLogger(__name__)
ClipboardWaitResult = tuple[Path, int, int] | Literal["cancelled"] | None


class ScreenshotService:
    def __init__(self, output_path: Path = TEMP_SCREENSHOT_PATH) -> None:
        self.output_path = output_path

    def capture(self, bbox: tuple[int, int, int, int]) -> Path:
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Invalid screenshot area")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        image = ImageGrab.grab(bbox=bbox)
        image.save(self.output_path)
        LOGGER.info("Screenshot saved to %s", self.output_path)
        return self.output_path

    def capture_clipboard_image(self) -> tuple[Path, int, int] | None:
        image = self._clipboard_image()
        if image is None:
            return None
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(self.output_path)
        LOGGER.info("Clipboard screenshot saved to %s", self.output_path)
        return self.output_path, image.width, image.height

    def clipboard_image_signature(self) -> str:
        image = self._clipboard_image()
        if image is None:
            return ""
        return self._image_signature(image)

    def wait_for_clipboard_image(
        self,
        baseline_signature: str,
        timeout_seconds: int = 20,
        poll_interval: float = 0.35,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ClipboardWaitResult:
        deadline = time.monotonic() + max(1, timeout_seconds)
        while time.monotonic() < deadline:
            if cancel_check is not None and cancel_check():
                return "cancelled"
            image = self._clipboard_image()
            if image is not None:
                signature = self._image_signature(image)
                if signature and signature != baseline_signature:
                    self.output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(self.output_path)
                    LOGGER.info("Clipboard screenshot saved to %s", self.output_path)
                    return self.output_path, image.width, image.height
            time.sleep(max(0.05, poll_interval))
        return None

    @staticmethod
    def screenclip_cancel_requested() -> bool:
        return _key_pressed(0x1B) or _key_pressed(0x02)

    @staticmethod
    def launch_system_snipping() -> bool:
        try:
            os.startfile("ms-screenclip:")  # type: ignore[attr-defined]
            return True
        except Exception:
            LOGGER.debug("ms-screenclip URI failed; trying explorer fallback", exc_info=True)
        try:
            subprocess.Popen(["explorer.exe", "ms-screenclip:"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            LOGGER.warning("System snipping could not be started", exc_info=True)
            return False

    @staticmethod
    def encode_base64(path: Path | str) -> str:
        data = Path(path).read_bytes()
        return base64.b64encode(data).decode("utf-8")

    @staticmethod
    def clamp_bbox(root: Any, bbox: tuple[int, int, int, int], scale: float = 1.0) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        width = int(root.winfo_screenwidth() * scale)
        height = int(root.winfo_screenheight() * scale)
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(0, min(x2, width))
        y2 = max(0, min(y2, height))
        return (x1, y1, max(x2, x1 + 10), max(y2, y1 + 10))

    @staticmethod
    def _clipboard_image() -> Image.Image | None:
        try:
            data = ImageGrab.grabclipboard()
        except Exception:
            LOGGER.debug("Clipboard image read failed", exc_info=True)
            return None
        if isinstance(data, Image.Image):
            return data.convert("RGB")
        if isinstance(data, list):
            for item in data:
                try:
                    path = Path(item)
                    if path.is_file():
                        return Image.open(path).convert("RGB")
                except Exception:
                    continue
        return None

    @staticmethod
    def _image_signature(image: Image.Image) -> str:
        try:
            sample = image.copy()
            sample.thumbnail((96, 96))
            digest = hashlib.sha256()
            digest.update(str(image.size).encode("ascii", "ignore"))
            digest.update(sample.tobytes())
            return digest.hexdigest()
        except Exception:
            LOGGER.debug("Clipboard image signature failed", exc_info=True)
            return ""


def _key_pressed(vk_code: int) -> bool:
    try:
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False
        return bool(windll.user32.GetAsyncKeyState(vk_code) & 0x8000)
    except Exception:
        return False
