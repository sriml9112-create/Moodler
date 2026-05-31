"""Old Moodler-style compact toolbar."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from config import TRANSPARENT_COLOR
from utils.windows import apply_transparent_toolwindow, get_virtual_screen_bounds, keep_topmost


class OldMoodlerToolbarStyle:
    geometry = "200x50+5+5"
    answer_max_width = 600
    transparent_color = "#010101"
    frame_height = 50
    default_x = 5
    default_y = 5
    normal_width = 200
    normal_height = 50
    frame_pack = {"fill": "x", "expand": False, "padx": 1, "pady": 1}
    status = {
        "fg": "#2a2a2a",
        "bg": transparent_color,
        "font": ("Arial", 7),
        "anchor": "w",
        "justify": "left",
        "height": 1,
    }
    status_grid = {"row": 0, "column": 0, "sticky": "ew", "padx": 2}
    button_style = {
        "bg": "#2a2a2a",
        "fg": "#4a4a4a",
        "activebackground": "#3a3a3a",
        "activeforeground": "#5a5a5a",
        "relief": "flat",
        "borderwidth": 0,
        "font": ("Arial", 6),
        "padx": 3,
        "pady": 1,
    }


class Toolbar:
    def __init__(
        self,
        callbacks: dict[str, Callable[[], None]],
        initial_agent_count: int = 1,
        initial_position: tuple[int, int] = (OldMoodlerToolbarStyle.default_x, OldMoodlerToolbarStyle.default_y),
        on_position_change: Callable[[int, int], None] | None = None,
    ) -> None:
        self.callbacks = callbacks
        self.busy = False
        self.on_position_change = on_position_change
        self.position_x, self.position_y = initial_position
        self.move_mode = False
        self.drag_start: tuple[int, int] | None = None
        self.window_start: tuple[int, int] | None = None
        self.move_bindings: list[tuple[tk.Widget, str, str]] = []

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.position_x, self.position_y = self._validated_position(self.position_x, self.position_y)
        self.root.geometry(self._geometry(OldMoodlerToolbarStyle.normal_width))
        self.root.resizable(False, False)

        self.frame = tk.Frame(
            self.root,
            bg=TRANSPARENT_COLOR,
            height=OldMoodlerToolbarStyle.frame_height,
        )
        self.frame.pack(**OldMoodlerToolbarStyle.frame_pack)
        self.frame.pack_propagate(False)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=0, minsize=25)
        self.frame.rowconfigure(1, weight=0, minsize=25)

        self.status = tk.Label(
            self.frame,
            text="Ready",
            **OldMoodlerToolbarStyle.status,
        )
        self.status.grid(**OldMoodlerToolbarStyle.status_grid)

        self.buttons_frame = tk.Frame(self.frame, bg=TRANSPARENT_COLOR)
        self.buttons_frame.grid(row=1, column=0, sticky="w", padx=1)

        self.buttons: dict[str, tk.Button] = {}
        self._add_button("agent", f"{initial_agent_count}x", callbacks["agent"])
        self._add_button("screenshot", "\U0001f4f7", callbacks["screenshot"])
        self._add_button("send", "\u27a4", callbacks["send"])
        self._add_button("settings", "\u2699", callbacks["settings"])
        self._add_button("reset", "\u21bb", self.activate_move_mode)
        self._add_button("quit", "\u2715", callbacks["quit"])

        self.root.bind("<Return>", lambda _event: callbacks["send"]())

        self.root.update_idletasks()
        apply_transparent_toolwindow(self.root, TRANSPARENT_COLOR)
        self._keep_topmost_loop()
        self.set_status("Ready")

    def _add_button(self, key: str, text: str, command: Callable[[], None]) -> None:
        button = tk.Button(
            self.buttons_frame,
            text=text,
            command=command,
            disabledforeground="#4b5563",
            highlightthickness=0,
            takefocus=False,
            **OldMoodlerToolbarStyle.button_style,
        )
        button.pack(side="left", padx=1)
        self.buttons[key] = button

    def set_status(self, text: str, is_result: bool = False) -> None:
        def update() -> None:
            value = text or "Ready"
            if is_result and value:
                text_width = min(max(len(value) * 6 + 20, 200), OldMoodlerToolbarStyle.answer_max_width)
                self.status.config(
                    text=value,
                    font=("Arial", 10),
                    fg="#2a2a2a",
                    wraplength=0,
                    anchor="w",
                    justify="left",
                    height=1,
                )
                self.status.update_idletasks()
                self.root.geometry(self._geometry(text_width))
                self.frame.config(height=50)
            else:
                self.status.config(
                    text=value,
                    font=("Arial", 7),
                    fg="#2a2a2a",
                    wraplength=0,
                    anchor="w",
                )
                self.root.geometry(self._geometry(OldMoodlerToolbarStyle.normal_width))
            self.root.update_idletasks()

        self.root.after(0, update)

    def set_busy(self, busy: bool) -> None:
        def update() -> None:
            self.busy = busy
            for key, button in self.buttons.items():
                if key == "quit":
                    continue
                button.config(state="disabled" if busy else "normal")

        self.root.after(0, update)

    def set_agent_count(self, count: int) -> None:
        safe_count = max(1, min(5, int(count)))
        self.buttons["agent"].config(text=f"{safe_count}x")

    def activate_move_mode(self) -> None:
        if self.busy:
            return
        if self.move_mode:
            return
        self.move_mode = True
        self.drag_start = None
        self.window_start = None
        self.set_status("Move")
        self._bind_move_widgets()

    def _bind_move_widgets(self) -> None:
        widgets: list[tk.Widget] = [self.root, self.frame, self.status, self.buttons_frame, *self.buttons.values()]
        for widget in widgets:
            for sequence, handler in [
                ("<ButtonPress-1>", self._move_press),
                ("<B1-Motion>", self._move_drag),
                ("<ButtonRelease-1>", self._move_release),
            ]:
                func_id = widget.bind(sequence, handler, add="+")
                self.move_bindings.append((widget, sequence, func_id))
        self.move_bindings.append((self.root, "<Escape>", self.root.bind("<Escape>", self._move_cancel, add="+")))

    def _unbind_move_widgets(self) -> None:
        for widget, sequence, func_id in self.move_bindings:
            try:
                widget.unbind(sequence, func_id)
            except Exception:
                pass
        self.move_bindings.clear()

    def _move_press(self, event) -> str:
        if not self.move_mode:
            return ""
        self.drag_start = (int(event.x_root), int(event.y_root))
        self.window_start = (int(self.root.winfo_x()), int(self.root.winfo_y()))
        self.set_status("Move")
        return "break"

    def _move_drag(self, event) -> str:
        if not self.move_mode or self.drag_start is None or self.window_start is None:
            return "break"
        dx = int(event.x_root) - self.drag_start[0]
        dy = int(event.y_root) - self.drag_start[1]
        self._apply_position(self.window_start[0] + dx, self.window_start[1] + dy)
        return "break"

    def _move_release(self, _event=None) -> str:
        if not self.move_mode:
            return ""
        x, y = self._validated_position(self.position_x, self.position_y)
        self._apply_position(x, y)
        self.position_x = x
        self.position_y = y
        self.move_mode = False
        self.drag_start = None
        self.window_start = None
        self._unbind_move_widgets()
        if self.on_position_change is not None:
            self.on_position_change(x, y)
        self.set_status("Ready")
        return "break"

    def _move_cancel(self, _event=None) -> str:
        if not self.move_mode:
            return ""
        self.move_mode = False
        self.drag_start = None
        self.window_start = None
        self._unbind_move_widgets()
        self.set_status("Ready")
        return "break"

    def _apply_position(self, x: int, y: int) -> None:
        width = max(int(self.root.winfo_width()), OldMoodlerToolbarStyle.normal_width)
        self.position_x = int(x)
        self.position_y = int(y)
        self.root.geometry(self._geometry(width))

    def _geometry(self, width: int) -> str:
        return f"{int(width)}x{OldMoodlerToolbarStyle.normal_height}+{self.position_x}+{self.position_y}"

    def _validated_position(self, x: int, y: int) -> tuple[int, int]:
        x = self._safe_int(x)
        y = self._safe_int(y)
        if self._position_visible(x, y):
            return x, y
        return OldMoodlerToolbarStyle.default_x, OldMoodlerToolbarStyle.default_y

    def _position_visible(self, x: int, y: int) -> bool:
        left, top, right, bottom = get_virtual_screen_bounds(self.root)
        width = OldMoodlerToolbarStyle.normal_width
        height = OldMoodlerToolbarStyle.normal_height
        margin = 20
        return x < right - margin and y < bottom - margin and x + width > left + margin and y + height > top + margin

    @staticmethod
    def _safe_int(value: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return OldMoodlerToolbarStyle.default_x
        return number if -100000 <= number <= 100000 else OldMoodlerToolbarStyle.default_x

    def _keep_topmost_loop(self) -> None:
        keep_topmost(self.root)
        self.root.after(2000, self._keep_topmost_loop)

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
