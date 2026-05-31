"""Moodler application orchestration."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from database import Database
from models.app_settings import AppSettings
from models.task_result import TaskResult
from services.agent_service import AgentService
from services.ai_router import AIProviderRouter
from services.clipboard_service import ClipboardService
from services.config_service import ConfigService
from services.history_service import HistoryService
from services.result_formatter import ResultFormatter
from services.screenshot_service import ScreenshotService
from services.task_detector import TaskDetector
from ui.control_center import ControlCenter
from ui.detail_window import DetailWindow
from ui.history_window import HistoryWindow
from ui.selector import ScreenAreaSelector
from ui.toolbar import OldMoodlerToolbarStyle, Toolbar
from utils.logger import setup_logging
from utils.windows import ensure_dpi_awareness, get_screen_scale

LOGGER = logging.getLogger(__name__)


class MoodlerApp:
    """Small toolbar-centered learning assistant."""

    def __init__(self) -> None:
        setup_logging()
        ensure_dpi_awareness()
        self.config_service = ConfigService()
        self.settings = self.config_service.settings
        self.settings.toolbar_x = OldMoodlerToolbarStyle.default_x
        self.settings.toolbar_y = OldMoodlerToolbarStyle.default_y
        self.database = Database()
        self.history_service = HistoryService(self.database)
        self.detector = TaskDetector()
        self.ai_router = AIProviderRouter(self.settings, self.detector)
        self.agent_service = AgentService(self.ai_router)
        self.formatter = ResultFormatter()
        self.screenshot_service = ScreenshotService()
        self.clipboard = ClipboardService()

        self.current_mode = "auto"
        self.current_text = ""
        self.current_screenshot: Path | None = None
        self.current_screenshot_size: tuple[int, int] | None = None
        self.current_source = "unknown"
        self.current_result: TaskResult | None = None
        self.control_center: ControlCenter | None = None
        self.active_selector: ScreenAreaSelector | None = None
        self.busy = False
        self.last_copy_status = "-"
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()

        self.toolbar = Toolbar(
            callbacks={
                "agent": self.cycle_agent_count,
                "screenshot": self.start_screenshot,
                "send": self.send_current,
                "settings": self.open_control_center,
                "quit": self.quit,
            },
            initial_agent_count=self.settings.agent_count,
            initial_position=(OldMoodlerToolbarStyle.default_x, OldMoodlerToolbarStyle.default_y),
            on_position_change=None,
        )
        self.clipboard.set_root(self.toolbar.root)
        self._schedule_ui_queue()
        if not self.ai_router.has_usable_key():
            self.toolbar.set_status("API fehlt")

    def run(self) -> None:
        self.toolbar.run()

    def cycle_agent_count(self) -> None:
        self.settings.agent_count = 1 if self.settings.agent_count >= 5 else self.settings.agent_count + 1
        self.config_service.save(self.settings)
        self.toolbar.set_agent_count(self.settings.agent_count)
        self.toolbar.set_status(f"{self.settings.agent_count}x")

    def start_screenshot(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Bereich waehlen...")
        try:
            self.active_selector = ScreenAreaSelector(self.toolbar.root, self._on_selection_complete)
        except Exception as exc:
            LOGGER.exception("Screenshot selector failed")
            self._set_busy(False, "Error")
            self.current_result = TaskResult.error(f"Screenshot-Auswahl konnte nicht gestartet werden: {exc}", source="screenshot")
            if not self.settings.suppress_task_popups:
                self.open_details()

    def _on_selection_complete(self, coords: tuple[int, int, int, int] | None) -> None:
        self.active_selector = None
        if coords is None:
            self._set_busy(False, "Ready")
            return
        self.toolbar.set_status("Capture...")
        scale = get_screen_scale()
        screen_w = int(self.toolbar.root.winfo_screenwidth() * scale)
        screen_h = int(self.toolbar.root.winfo_screenheight() * scale)
        x1, y1, x2, y2 = coords
        bbox = (
            max(0, min(x1, screen_w - 1)),
            max(0, min(y1, screen_h - 1)),
            max(0, min(x2, screen_w)),
            max(0, min(y2, screen_h)),
        )
        thread = threading.Thread(target=self._capture_worker, args=(bbox,), daemon=True)
        thread.start()

    def _capture_worker(self, bbox: tuple[int, int, int, int]) -> None:
        try:
            LOGGER.info("capture started %s", bbox)
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                raise ValueError("Screenshot-Bereich ist zu klein.")
            path = self.screenshot_service.capture(bbox)
            LOGGER.info("capture finished %s", path)
            width = abs(bbox[2] - bbox[0])
            height = abs(bbox[3] - bbox[1])
            self._post_ui(lambda: self._capture_done(path, width, height))
        except Exception as exc:
            LOGGER.exception("Screenshot failed")
            self._post_ui(lambda exc=exc: self._capture_failed(exc))

    def _capture_done(self, path: Path, width: int, height: int) -> None:
        self.current_screenshot = path
        self.current_screenshot_size = (width, height)
        self.current_text = ""
        self.current_source = "screenshot"
        self.current_result = None
        self._set_busy(False, f"Ready ({width}x{height})")

    def _capture_failed(self, exc: Exception) -> None:
        self.current_screenshot = None
        self.current_screenshot_size = None
        self._set_busy(False, "Error")
        self.current_result = TaskResult.error(f"Screenshot Fehler: {exc}", source="screenshot")
        if not self.settings.suppress_task_popups:
            self.open_details()

    def open_text_input(self) -> None:
        if self.busy:
            return
        win = tk.Toplevel(self.toolbar.root)
        win.title("Moodler Text")
        win.geometry("520x310+40+70")
        win.attributes("-topmost", True)
        win.configure(bg="#111214")

        tk.Label(win, text="Aufgabe einfuegen oder eintippen", bg="#111214", fg="#d7dde7", font=("Arial", 10, "bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        text_box = tk.Text(
            win,
            bg="#0d0f12",
            fg="#d7dde7",
            insertbackground="#d7dde7",
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        text_box.pack(fill="both", expand=True, padx=10, pady=5)
        pasted = self.clipboard.paste().strip()
        if pasted:
            text_box.insert("end", pasted)

        buttons = tk.Frame(win, bg="#111214")
        buttons.pack(fill="x", padx=10, pady=10)

        def use_text(send_after: bool = False) -> None:
            value = text_box.get("1.0", "end").strip()
            if not value:
                self.toolbar.set_status("Kein Text")
                return
            self.current_text = value
            self.current_screenshot = None
            self.current_screenshot_size = None
            self.current_source = "text"
            self.current_result = None
            self.toolbar.set_status("Text bereit")
            win.destroy()
            if send_after:
                self.send_current()

        self._small_button(buttons, "Uebernehmen", lambda: use_text(False)).pack(side="left")
        self._small_button(buttons, "Senden", lambda: use_text(True)).pack(side="left", padx=6)
        self._small_button(buttons, "Clipboard", lambda: text_box.insert("insert", self.clipboard.paste())).pack(
            side="left", padx=6
        )
        self._small_button(buttons, "Schliessen", win.destroy).pack(side="right")
        text_box.focus_set()

    def send_current(self) -> None:
        if self.busy:
            return
        if not self.ai_router.has_usable_key():
            self.current_result = TaskResult.error(self.ai_router.missing_key_message(), source="settings")
            self.toolbar.set_status("API fehlt")
            self.open_control_center("API")
            return
        if self.current_source == "text" and self.current_text.strip():
            self._process_async("text")
            return
        if self.current_source == "screenshot" and self.current_screenshot is not None:
            self._process_async("screenshot")
            return
        if self.settings.default_mode == "text":
            self.open_text_input()
            return
        if self.settings.default_mode == "screenshot":
            self.start_screenshot()
            return
        self.toolbar.set_status("Keine Aufgabe")

    def _process_async(self, source: str) -> None:
        self._set_busy(True, "Working...")
        thread = threading.Thread(target=self._process_worker, args=(source,), daemon=True)
        thread.start()

    def _process_worker(self, source: str) -> None:
        try:
            if source == "text":
                result = self.agent_service.analyze_text(self.current_text, self.current_mode, self.settings.agent_count)
            else:
                if self.current_screenshot is None:
                    raise RuntimeError("Kein Screenshot vorhanden.")
                result = self.agent_service.analyze_image(
                    self.current_screenshot,
                    self.current_mode,
                    self.settings.agent_count,
                )
                if self._screenshot_looks_too_small():
                    result.confidence = min(result.confidence, 0.45)
                    if not any("Screenshot" in warning for warning in result.warnings):
                        result.warnings.append("Screenshot-Bereich wirkt sehr klein oder unvollstaendig.")
            result.source = source
        except Exception as exc:
            LOGGER.exception("Processing failed")
            result = TaskResult.error(str(exc), source=source)
        self._post_ui(lambda: self._handle_result(result))

    def _handle_result(self, result: TaskResult) -> None:
        self.current_result = result
        copy_failed = False
        copy_text = self.formatter.auto_copy_text(result, self.settings)
        result.copied_value = copy_text
        if copy_text:
            copy_failed = not self.clipboard.copy(copy_text)
            if copy_failed:
                result.warnings.append("Antwort konnte nicht automatisch in die Zwischenablage kopiert werden.")
                self.last_copy_status = "Fehler"
            else:
                self.last_copy_status = "kopiert"
        elif result.task_type in self.formatter.COPY_TYPES or result.task_type in self.formatter.VALUE_COPY_TYPES:
            self.last_copy_status = "aus"
        else:
            self.last_copy_status = "-"
        if self.settings.auto_save_history:
            self._save_history(result, quiet=True)
        toolbar_text = "Error" if result.short_answer == "Fehler" else self.formatter.toolbar_text(result, self.settings)
        if copy_failed:
            toolbar_text = "Copy Fehler"
        self._set_busy(False, toolbar_text, is_result=True)
        if self.control_center is not None:
            try:
                if self.control_center.window.winfo_exists():
                    self.control_center.refresh_dashboard()
                    self.control_center.refresh_history()
            except Exception:
                LOGGER.debug("Control Center refresh after result failed", exc_info=True)
        if self.formatter.should_open_details(result, self.settings) and not self.settings.suppress_task_popups:
            self.open_details()

    def open_details(self) -> None:
        if self.current_result is None:
            self.toolbar.set_status("Keine Details")
            return
        DetailWindow(
            self.toolbar.root,
            self.current_result,
            on_copy=self.copy_result,
            on_save_cards=self.save_cards,
            on_save_history=lambda result: self._save_history(result, quiet=False),
        )

    def open_history(self) -> None:
        HistoryWindow(self.toolbar.root, self.history_service, self._open_history_result)

    def _open_history_result(self, result: TaskResult) -> None:
        self.current_result = result
        self.open_details()

    def open_control_center(self, initial_tab: str | None = None) -> ControlCenter:
        if self.control_center is not None:
            try:
                if self.control_center.window.winfo_exists():
                    self.control_center.window.lift()
                    if initial_tab:
                        self.control_center.select_tab(initial_tab)
                    self.control_center.refresh_dashboard()
                    return self.control_center
            except Exception:
                self.control_center = None
        control = ControlCenter(
            self.toolbar.root,
            self.settings,
            self.history_service,
            self._save_settings,
            self._open_history_result,
            self._copy_text,
            self.open_text_input,
            self.open_details,
            self.open_history,
            self._overview_state,
        )
        self.control_center = control
        if initial_tab:
            control.select_tab(initial_tab)
        return control

    def _save_settings(self, settings: AppSettings) -> None:
        settings.toolbar_x = OldMoodlerToolbarStyle.default_x
        settings.toolbar_y = OldMoodlerToolbarStyle.default_y
        self.settings = settings
        self.config_service.save(settings)
        self.ai_router.update_settings(settings)
        self.agent_service = AgentService(self.ai_router)
        self.toolbar.set_agent_count(settings.agent_count)
        self.toolbar.set_status("Settings gespeichert")

    def save_toolbar_position(self, x: int, y: int) -> None:
        self.toolbar.position_x = int(x)
        self.toolbar.position_y = int(y)

    def copy_current(self) -> None:
        if self.current_result is None:
            self.toolbar.set_status("Nichts zu kopieren")
            return
        self.copy_result(self.current_result)

    def copy_result(self, result: TaskResult) -> None:
        text = self.formatter.clipboard_text(result)
        if self.clipboard.copy(text):
            self.toolbar.set_status("Kopiert")
        else:
            self.toolbar.set_status("Copy Fehler")

    def _copy_text(self, text: str) -> None:
        self.clipboard.copy(text)
        self.toolbar.set_status("Kopiert")

    def _overview_state(self) -> dict[str, object]:
        return {
            "mode": self.settings.default_mode,
            "provider": self.settings.ai_provider,
            "model": self.settings.openai_model if self.settings.ai_provider != "gemini" else self.settings.gemini_model,
            "openai_model": self.settings.openai_model,
            "gemini_model": self.settings.gemini_model,
            "agent_count": self.settings.agent_count,
            "api_key_ok": self.ai_router.has_usable_key(),
            "openai_key_ok": self.ai_router._has_openai_key(),
            "gemini_key_ok": self.ai_router._has_gemini_key(),
            "last_task": self.current_result.task_type if self.current_result else "-",
            "last_confidence": f"{self.current_result.confidence_percent}%" if self.current_result else "-",
            "last_answer_type": self.current_result.task_type if self.current_result else "-",
            "last_answer_text": self.formatter.clipboard_text(self.current_result) if self.current_result else "",
            "last_copied_value": self.current_result.copied_value if self.current_result else "",
            "last_cost": f"${self.current_result.estimated_cost_usd:.4f}" if self.current_result else "-",
            "copy_status": self.last_copy_status,
            "auto_detect": self.settings.auto_detect_tasks,
            "auto_copy": self.settings.auto_copy_long_results,
            "bw_focus": self.settings.bw_focus_enabled,
        }

    def save_cards(self, result: TaskResult) -> None:
        count = self.history_service.save_flashcards_for_result(result)
        self.toolbar.set_status(f"{count} Karten gespeichert")

    def _save_history(self, result: TaskResult, quiet: bool) -> None:
        if result.id is None:
            self.history_service.save_result(result, result.source or self.current_source)
            if not quiet:
                self.toolbar.set_status("Verlauf gespeichert")
        elif not quiet:
            self.toolbar.set_status("Schon im Verlauf")

    def _set_busy(self, busy: bool, status: str, is_result: bool = False) -> None:
        self.busy = busy
        self.toolbar.set_busy(busy)
        self.toolbar.set_status(status, is_result=is_result)

    def _post_ui(self, callback: Callable[[], None]) -> None:
        self.ui_queue.put(callback)

    def _schedule_ui_queue(self) -> None:
        try:
            self.toolbar.root.after(25, self._drain_ui_queue)
        except Exception:
            LOGGER.debug("UI queue scheduling failed", exc_info=True)

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                callback = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception:
                LOGGER.exception("UI callback failed")
        self._schedule_ui_queue()

    def _screenshot_looks_too_small(self) -> bool:
        if not self.settings.mark_bad_screenshots_uncertain or self.current_screenshot_size is None:
            return False
        width, height = self.current_screenshot_size
        return width < 140 or height < 45

    def quit(self) -> None:
        self.toolbar.close()

    @staticmethod
    def _small_button(master: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg="#24272b",
            fg="#d7dde7",
            activebackground="#34383e",
            activeforeground="#d7dde7",
            relief="flat",
            borderwidth=0,
            padx=9,
            pady=5,
        )
