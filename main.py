"""Moodler entry point."""

from __future__ import annotations

import os
import sys

from app import MoodlerApp
from config import APP_NAME
from database import Database
from services.config_service import ConfigService
from utils.logger import setup_logging
from utils.windows import check_single_instance


def main() -> int:
    setup_logging()
    if os.getenv("MOODLER_SMOKE_TEST") == "1":
        ConfigService()
        Database()
        print("Moodler smoke test ok")
        return 0

    if not check_single_instance(APP_NAME):
        return 0

    app = MoodlerApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
