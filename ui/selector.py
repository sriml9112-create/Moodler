"""Non-blocking screenshot area selector."""

from __future__ import annotations

import ctypes
import logging
import time
import tkinter as tk
from collections.abc import Callable
from ctypes import wintypes

MIN_SELECTION_SIZE = 10
POLL_MS = 16
DEFAULT_TIMEOUT_SECONDS = 20

LOGGER = logging.getLogger(__name__)

HC_ACTION = 0
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002

HOOKPROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    wintypes.LPARAM,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
ULONG_PTR = getattr(wintypes, "ULONG_PTR", wintypes.WPARAM)


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", _Point),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class ScreenAreaSelector:
    """Track a drag selection through non-blocking Windows input polling."""

    def __init__(
        self,
        master: tk.Tk,
        on_complete: Callable[[tuple[int, int, int, int] | None], None],
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.master = master
        self.on_complete = on_complete
        self.timeout_seconds = max(3, int(timeout_seconds))
        self.start_time = time.monotonic()
        self.start: tuple[int, int] | None = None
        self.final_coords: tuple[int, int, int, int] | None = None
        self.completed = False
        self.finishing = False
        self.dragging = False
        self.after_id: str | None = None
        self.mouse_hook = None
        self.hook_proc = None
        self.await_initial_release = self._left_down()

        LOGGER.info("selector created")
        self._install_mouse_hook()
        self._schedule_poll()

    def _schedule_poll(self) -> None:
        if self.completed or self.finishing:
            return
        try:
            self.after_id = self.master.after(POLL_MS, self._poll)
        except Exception:
            LOGGER.exception("selector poll could not be scheduled")
            self._cancel("schedule error")

    def _poll(self) -> None:
        if self.completed or self.finishing:
            return
        try:
            if time.monotonic() - self.start_time >= self.timeout_seconds:
                LOGGER.info("selector timeout")
                self._cancel("timeout")
                return

            if self._escape_down():
                self._cancel("escape")
                return

            if self._right_down():
                self._cancel("right click")
                return

            if self.mouse_hook:
                self._schedule_poll()
                return

            left_down = self._left_down()
            pos = self._cursor_pos()

            if self.await_initial_release:
                if not left_down:
                    self.await_initial_release = False
                self._schedule_poll()
                return

            if not self.dragging:
                if left_down:
                    self.dragging = True
                    self.start = pos
                    LOGGER.info("mouse down %s,%s", pos[0], pos[1])
                self._schedule_poll()
                return

            if left_down:
                self._schedule_poll()
                return

            self._finish_at(pos)
        except Exception:
            LOGGER.exception("selector error")
            self._cancel("error")

    def _finish_at(self, pos: tuple[int, int]) -> None:
        LOGGER.info("mouse up %s,%s", pos[0], pos[1])
        if self.start is None:
            self._cancel("missing start")
            return
        x1, y1 = self.start
        x2, y2 = pos
        if abs(x2 - x1) < MIN_SELECTION_SIZE or abs(y2 - y1) < MIN_SELECTION_SIZE:
            self._cancel("selection too small")
            return
        self.final_coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        LOGGER.info("bbox selected %s", self.final_coords)
        coords = self.final_coords
        self.completed = True
        self._destroy()
        self._complete(coords)

    def _mouse_hook_callback(self, n_code: int, w_param, l_param) -> int:
        try:
            if n_code == HC_ACTION and not self.completed:
                msg = int(w_param)
                info = ctypes.cast(l_param, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                pos = (int(info.pt.x), int(info.pt.y))
                if msg == WM_LBUTTONDOWN and not self.await_initial_release:
                    self.dragging = True
                    self.start = pos
                    LOGGER.info("mouse down %s,%s", pos[0], pos[1])
                    return 1
                if msg == WM_MOUSEMOVE and self.dragging:
                    return 1
                if msg == WM_LBUTTONUP:
                    if self.await_initial_release:
                        self.await_initial_release = False
                        return self._call_next_hook(n_code, w_param, l_param)
                    if self.dragging:
                        self._defer_finish(pos)
                        return 1
                if msg in {WM_RBUTTONDOWN, WM_RBUTTONUP}:
                    self._defer_cancel("right click")
                    return 1
        except Exception:
            LOGGER.exception("selector mouse hook error")
            self._defer_cancel("hook error")
            return 1
        return self._call_next_hook(n_code, w_param, l_param)

    def _defer_finish(self, pos: tuple[int, int]) -> None:
        if self.completed or self.finishing:
            return
        self.finishing = True
        try:
            self.master.after(0, lambda: self._finish_at(pos))
        except Exception:
            LOGGER.exception("selector finish could not be deferred")
            self._cancel("defer finish error")

    def _defer_cancel(self, reason: str) -> None:
        if self.completed or self.finishing:
            return
        self.finishing = True
        try:
            self.master.after(0, lambda: self._cancel(reason))
        except Exception:
            LOGGER.exception("selector cancel could not be deferred")
            self._cancel(reason)

    def _install_mouse_hook(self) -> None:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = wintypes.HANDLE
            user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = wintypes.LPARAM
            user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            user32.UnhookWindowsHookEx.restype = wintypes.BOOL
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE
            self.hook_proc = HOOKPROC(self._mouse_hook_callback)
            module_handle = kernel32.GetModuleHandleW(None)
            self.mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self.hook_proc, module_handle, 0)
            if self.mouse_hook:
                LOGGER.info("selector mouse hook installed")
            else:
                self.mouse_hook = None
                LOGGER.warning("selector mouse hook unavailable, falling back to passive polling")
        except Exception:
            self.mouse_hook = None
            self.hook_proc = None
            LOGGER.warning("selector mouse hook install failed, falling back to passive polling", exc_info=True)

    def _uninstall_mouse_hook(self) -> None:
        if not self.mouse_hook:
            return
        try:
            ctypes.windll.user32.UnhookWindowsHookEx(self.mouse_hook)
            LOGGER.info("selector mouse hook removed")
        except Exception:
            LOGGER.debug("selector mouse hook removal failed", exc_info=True)
        finally:
            self.mouse_hook = None
            self.hook_proc = None

    def _call_next_hook(self, n_code: int, w_param, l_param) -> int:
        try:
            return int(ctypes.windll.user32.CallNextHookEx(self.mouse_hook, n_code, w_param, l_param))
        except Exception:
            return 0

    def _complete(self, coords: tuple[int, int, int, int] | None) -> None:
        try:
            self.master.after(0, lambda: self.on_complete(coords))
        except Exception:
            LOGGER.exception("selector callback failed")

    def _cancel(self, reason: str = "cancelled") -> None:
        if self.completed:
            return
        self.completed = True
        LOGGER.info("selector cancelled: %s", reason)
        self._destroy()
        self._complete(None)

    def _destroy(self) -> None:
        self._uninstall_mouse_hook()
        if self.after_id is not None:
            try:
                self.master.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self._clear_text_selection()
        LOGGER.info("selector destroyed")

    @staticmethod
    def _cursor_pos() -> tuple[int, int]:
        point = _Point()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            raise RuntimeError("Cursorposition konnte nicht gelesen werden.")
        return int(point.x), int(point.y)

    @staticmethod
    def _key_down(vk_code: int) -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)

    def _left_down(self) -> bool:
        return self._key_down(0x01)

    def _right_down(self) -> bool:
        return self._key_down(0x02)

    def _escape_down(self) -> bool:
        return self._key_down(0x1B)

    @staticmethod
    def _clear_text_selection() -> None:
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(VK_ESCAPE, 0, 0, 0)
            user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            LOGGER.debug("text selection cleanup failed", exc_info=True)
