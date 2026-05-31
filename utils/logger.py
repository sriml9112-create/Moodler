"""Logging setup."""

from __future__ import annotations

import logging

from config import APPDATA_DIR, LOG_PATH


def setup_logging() -> None:
    if logging.getLogger().handlers:
        return
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        handlers.insert(0, logging.FileHandler(LOG_PATH, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
