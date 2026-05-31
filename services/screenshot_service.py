"""Screenshot capture service."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from PIL import ImageGrab

from config import TEMP_SCREENSHOT_PATH

LOGGER = logging.getLogger(__name__)


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
