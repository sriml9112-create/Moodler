"""Nearly invisible Tkinter screenshot area selector."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable

from utils.windows import get_screen_scale, hide_from_taskbar, keep_topmost

MIN_SELECTION_SIZE = 10
SELECTOR_ALPHA = 0.01
FINISH_DELAY_MS = 150

LOGGER = logging.getLogger(__name__)


class ScreenAreaSelector:
    """Old Moodler-style fullscreen selector using normal Tk events."""

    def __init__(
        self,
        master: tk.Tk,
        on_complete: Callable[[tuple[int, int, int, int] | None], None],
        timeout_seconds: int | None = None,
    ) -> None:
        self.master = master
        self.on_complete = on_complete
        self.start: tuple[int, int] | None = None
        self.final_coords: tuple[int, int, int, int] | None = None
        self.completed = False
        self.keep_topmost_after_id: str | None = None
        self.timeout_seconds = timeout_seconds

        LOGGER.info("selector created")
        self.window = tk.Toplevel(master)
        self.window.withdraw()
        self.window.attributes("-fullscreen", True)
        self.window.configure(bg="black")
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", SELECTOR_ALPHA)
        self.window.overrideredirect(True)
        self.window.update_idletasks()
        hide_from_taskbar(self.window)

        self.canvas = tk.Canvas(self.window, highlightthickness=0, bg="black", bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.canvas.focus_set()

        try:
            self.scale_factor = get_screen_scale(self.window.winfo_id())
        except Exception:
            self.scale_factor = 1.0

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>", self._cancel)
        self.canvas.bind("<ButtonRelease-3>", self._cancel)
        self.window.bind("<Escape>", self._cancel)
        self.canvas.bind("<Escape>", self._cancel)
        self.window.bind("<KeyPress-Escape>", self._cancel)

        self.master.after(10, lambda: hide_from_taskbar(self.window))
        self._keep_on_top()

    def _on_press(self, event: tk.Event) -> None:
        if self.completed:
            return
        self.start = (int(event.x_root), int(event.y_root))
        LOGGER.info("mouse down %s,%s", self.start[0], self.start[1])

    def _on_drag(self, _event: tk.Event) -> None:
        # Intentionally no drawing: no rectangle, no colored frame, no text.
        return

    def _on_release(self, event: tk.Event) -> None:
        if self.completed:
            return
        if self.start is None:
            self._cancel()
            return

        x1, y1 = self.start
        x2, y2 = int(event.x_root), int(event.y_root)
        LOGGER.info("mouse up %s,%s", x2, y2)

        if abs(x2 - x1) < MIN_SELECTION_SIZE or abs(y2 - y1) < MIN_SELECTION_SIZE:
            self._cancel()
            return

        scale = float(self.scale_factor or 1.0)
        self.final_coords = (
            int(round(min(x1, x2) * scale)),
            int(round(min(y1, y2) * scale)),
            int(round(max(x1, x2) * scale)),
            int(round(max(y1, y2) * scale)),
        )
        LOGGER.info("bbox selected %s", self.final_coords)
        self.completed = True
        self._hide_before_finish()
        self.master.after(FINISH_DELAY_MS, self._complete)

    def _complete(self) -> None:
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

    def _hide_before_finish(self) -> None:
        try:
            self.window.withdraw()
            self.window.update_idletasks()
        except Exception:
            LOGGER.debug("selector withdraw before finish failed", exc_info=True)

    def _destroy(self) -> None:
        if self.keep_topmost_after_id is not None:
            try:
                self.window.after_cancel(self.keep_topmost_after_id)
            except Exception:
                pass
            self.keep_topmost_after_id = None
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            LOGGER.debug("selector destroy failed", exc_info=True)
        LOGGER.info("selector destroyed")

    def _safe_callback(self, coords: tuple[int, int, int, int] | None) -> None:
        try:
            self.on_complete(coords)
        except Exception:
            LOGGER.exception("selector callback failed")

    def _keep_on_top(self) -> None:
        if self.completed:
            return
        try:
            if not self.window.winfo_exists():
                return
            keep_topmost(self.window)
            self.keep_topmost_after_id = self.window.after(50, self._keep_on_top)
        except Exception:
            LOGGER.debug("selector keep-on-top failed", exc_info=True)
