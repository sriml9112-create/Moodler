"""Stable non-hook screenshot area selector.

This is intentionally boring: no low-level mouse hook, no global grab, no
blocking Tk wait. It is the default Gabll/old-Moodler style selector.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable

from utils.windows import get_virtual_screen_bounds, hide_from_taskbar, keep_topmost

LOGGER = logging.getLogger(__name__)

MIN_SELECTION_SIZE = 10
DEFAULT_TIMEOUT_SECONDS = 20
KEEP_TOPMOST_MS = 750
STABLE_BG = "#f3f3f3"
EXPERIMENTAL_BG = "#010101"
STABLE_ALPHA = 0.08
EXPERIMENTAL_ALPHA = 0.01
OUTLINE_COLOR = "#777777"


class ScreenAreaSelector:
    """Normal Tk selector with optional minimal neutral outline and hard timeout."""

    def __init__(
        self,
        master: tk.Tk,
        on_complete: Callable[[tuple[int, int, int, int] | None], None],
        timeout_seconds: int | None = None,
        show_outline: bool = True,
    ) -> None:
        self.master = master
        self.on_complete = on_complete
        self.timeout_seconds = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        self.show_outline = show_outline
        self.start: tuple[int, int] | None = None
        self.current: tuple[int, int] | None = None
        self.final_coords: tuple[int, int, int, int] | None = None
        self.completed = False
        self.rect_id: int | None = None
        self.timeout_after_id: str | None = None
        self.keep_after_id: str | None = None
        self.focus_after_id: str | None = None

        LOGGER.info("selector started")
        self.window = tk.Toplevel(master)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        left, top, right, bottom = get_virtual_screen_bounds(master)
        self.screen_left = left
        self.screen_top = top
        self.screen_width = max(1, right - left)
        self.screen_height = max(1, bottom - top)
        self.window.geometry(f"{self.screen_width}x{self.screen_height}{left:+d}{top:+d}")

        # Gabll mode must receive mouse events reliably. Color-key transparency
        # can become click-through on some Windows setups, so the default uses
        # a barely visible alpha window instead of a color-key layer.
        bg = STABLE_BG if show_outline else EXPERIMENTAL_BG
        alpha = STABLE_ALPHA if show_outline else EXPERIMENTAL_ALPHA
        self.window.configure(bg=bg)
        self.window.attributes("-alpha", alpha)

        self.canvas = tk.Canvas(
            self.window,
            bg=bg,
            width=self.screen_width,
            height=self.screen_height,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self._bind_events()
        self.window.deiconify()
        self.window.lift()
        self.window.update_idletasks()
        self.window.focus_force()
        self.canvas.focus_set()
        LOGGER.info("window shown")
        LOGGER.info("canvas ready %sx%s", self.screen_width, self.screen_height)
        hide_from_taskbar(self.window)
        self.timeout_after_id = self.master.after(int(self.timeout_seconds * 1000), self._timeout)
        self.keep_after_id = self.master.after(KEEP_TOPMOST_MS, self._keep_topmost)
        self.focus_after_id = self.master.after(50, self._refresh_focus)

    def _bind_events(self) -> None:
        for widget in (self.window, self.canvas):
            widget.bind("<ButtonPress-1>", self._on_press, add="+")
            widget.bind("<B1-Motion>", self._on_drag, add="+")
            widget.bind("<ButtonRelease-1>", self._on_release, add="+")
            widget.bind("<ButtonPress-3>", self._cancel, add="+")
            widget.bind("<ButtonRelease-3>", self._cancel, add="+")
            widget.bind("<Escape>", self._cancel, add="+")
            widget.bind("<KeyPress-Escape>", self._cancel, add="+")

    def _on_press(self, event: tk.Event) -> None:
        if self.completed:
            return
        self.start = (int(event.x_root), int(event.y_root))
        self.current = self.start
        LOGGER.info("mouse down %s,%s", self.start[0], self.start[1])

    def _on_drag(self, event: tk.Event) -> None:
        if self.completed or self.start is None:
            return
        self.current = (int(event.x_root), int(event.y_root))
        LOGGER.info("mouse move %s,%s", self.current[0], self.current[1])
        if not self.show_outline:
            return
        x1, y1 = self.start
        x2, y2 = self.current
        cx1 = min(x1, x2) - self.window.winfo_rootx()
        cy1 = min(y1, y2) - self.window.winfo_rooty()
        cx2 = max(x1, x2) - self.window.winfo_rootx()
        cy2 = max(y1, y2) - self.window.winfo_rooty()
        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=OUTLINE_COLOR, width=1)
        else:
            self.canvas.coords(self.rect_id, cx1, cy1, cx2, cy2)

    def _on_release(self, event: tk.Event) -> None:
        if self.completed:
            return
        if self.start is None:
            self._cancel()
            return
        x2, y2 = int(event.x_root), int(event.y_root)
        LOGGER.info("mouse up %s,%s", x2, y2)
        self._finish_selection(x2, y2)

    def _finish_selection(self, x2: int, y2: int) -> None:
        if self.start is None:
            self._cancel()
            return
        x1, y1 = self.start
        if abs(x2 - x1) < MIN_SELECTION_SIZE or abs(y2 - y1) < MIN_SELECTION_SIZE:
            LOGGER.info("bbox too small")
            self._cancel()
            return
        self.final_coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        LOGGER.info("bbox selected %s", self.final_coords)
        self.completed = True
        coords = self.final_coords
        self._destroy()
        self._safe_callback(coords)

    def _cancel(self, _event: tk.Event | None = None) -> None:
        if self.completed:
            return
        self.completed = True
        self.final_coords = None
        LOGGER.info("selector cancelled")
        self._destroy()
        self._safe_callback(None)

    def _timeout(self) -> None:
        if self.completed:
            return
        self.completed = True
        self.final_coords = None
        LOGGER.info("selector timeout")
        self._destroy()
        self._safe_callback(None)

    def _destroy(self) -> None:
        for attr in ("timeout_after_id", "keep_after_id", "focus_after_id"):
            after_id = getattr(self, attr)
            if after_id is not None:
                try:
                    self.master.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            LOGGER.debug("selector destroy failed", exc_info=True)
        LOGGER.info("selector destroyed")

    def _refresh_focus(self) -> None:
        if self.completed:
            return
        try:
            if self.window.winfo_exists():
                self.window.focus_force()
                self.canvas.focus_set()
        except Exception:
            LOGGER.debug("selector focus refresh failed", exc_info=True)

    def _keep_topmost(self) -> None:
        if self.completed:
            return
        try:
            if self.window.winfo_exists():
                keep_topmost(self.window)
                self.keep_after_id = self.master.after(KEEP_TOPMOST_MS, self._keep_topmost)
        except Exception:
            LOGGER.debug("selector topmost refresh failed", exc_info=True)

    def _safe_callback(self, coords: tuple[int, int, int, int] | None) -> None:
        try:
            self.on_complete(coords)
        except Exception:
            LOGGER.exception("selector callback failed")
