"""Windows-specific helpers with safe fallbacks."""

from __future__ import annotations

import ctypes
import logging
from typing import Any

try:
    import win32api
    import win32con
    import win32gui
except Exception:  # pragma: no cover - optional on non-Windows/dev hosts
    win32api = None
    win32con = None
    win32gui = None

LOGGER = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
LWA_COLORKEY = 0x00000001
HWND_TOPMOST = -1
HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def ensure_dpi_awareness() -> None:
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except Exception:
            pass
    except Exception:
        LOGGER.debug("DPI awareness could not be set", exc_info=True)


def get_screen_scale(hwnd: int | None = None) -> float:
    try:
        if hwnd and hasattr(ctypes.windll.user32, "GetDpiForWindow"):
            return float(ctypes.windll.user32.GetDpiForWindow(hwnd)) / 96.0
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return float(dpi) / 96.0
    except Exception:
        return 1.0


def get_virtual_screen_bounds(window: Any | None = None) -> tuple[int, int, int, int]:
    try:
        user32 = ctypes.windll.user32
        left = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
        top = int(user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
        width = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
        height = int(user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
        if width > 0 and height > 0:
            return left, top, left + width, top + height
    except Exception:
        pass
    try:
        if window is not None:
            return 0, 0, int(window.winfo_screenwidth()), int(window.winfo_screenheight())
    except Exception:
        pass
    return 0, 0, 1920, 1080


def apply_color_key_toolwindow(window: Any, transparent_color: str, no_activate: bool = False) -> None:
    try:
        hwnd = window.winfo_id()
        rgb = tuple(int(transparent_color[i : i + 2], 16) for i in (1, 3, 5))
        if win32api and win32con and win32gui:
            exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            exstyle |= win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW
            if no_activate:
                exstyle |= WS_EX_NOACTIVATE
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle)
            win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*rgb), 0, win32con.LWA_COLORKEY)
            return
        user32 = ctypes.windll.user32
        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_long.restype = ctypes.c_longlong
        set_long.restype = ctypes.c_longlong
        exstyle = int(get_long(hwnd, GWL_EXSTYLE))
        exstyle |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        if no_activate:
            exstyle |= WS_EX_NOACTIVATE
        set_long(hwnd, GWL_EXSTYLE, exstyle)
        colorref = int(rgb[0]) | (int(rgb[1]) << 8) | (int(rgb[2]) << 16)
        user32.SetLayeredWindowAttributes(hwnd, colorref, 0, LWA_COLORKEY)
    except Exception:
        LOGGER.debug("Window transparency styling failed", exc_info=True)


def apply_transparent_toolwindow(window: Any, transparent_color: str) -> None:
    apply_color_key_toolwindow(window, transparent_color, no_activate=True)


def keep_topmost(window: Any) -> None:
    try:
        hwnd = window.winfo_id()
        if win32con and win32gui:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
            return
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except Exception:
        LOGGER.debug("Could not keep window topmost", exc_info=True)


def hide_from_taskbar(window: Any) -> None:
    try:
        hwnd = window.winfo_id()
        if win32con and win32gui:
            exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            exstyle &= ~win32con.WS_EX_APPWINDOW
            exstyle |= win32con.WS_EX_TOOLWINDOW
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED,
            )
            return
        user32 = ctypes.windll.user32
        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_long.restype = ctypes.c_longlong
        set_long.restype = ctypes.c_longlong
        exstyle = int(get_long(hwnd, GWL_EXSTYLE))
        exstyle &= ~WS_EX_APPWINDOW
        exstyle |= WS_EX_TOOLWINDOW
        set_long(hwnd, GWL_EXSTYLE, exstyle)
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        LOGGER.debug("Could not hide window from taskbar", exc_info=True)


def check_single_instance(app_name: str) -> bool:
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, True, f"Global\\{app_name}_SingleInstance")
        if not mutex:
            return True
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True
