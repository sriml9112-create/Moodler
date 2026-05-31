"""History, flashcards and quiz UI."""

from __future__ import annotations

import random
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from config import UI
from models.task_result import TaskResult
from services.history_service import HistoryService


class HistoryWindow:
    def __init__(
        self,
        master: tk.Tk,
        history_service: HistoryService,
        on_open_result: Callable[[TaskResult], None],
    ) -> None:
        self.master = master
        self.history_service = history_service
        self.on_open_result = on_open_result
        self.current_history: list[TaskResult] = []
        self.current_cards: list[dict] = []

        self.window = tk.Toplevel(master)
        self.window.title("Moodler Verlauf")
        self.window.geometry("780x500+50+80")
        self.window.attributes("-topmost", True)
        self.window.configure(bg=UI["panel"])
        self.filter_var = tk.StringVar(value="all")
        self._build()
        self.refresh()

    def _build(self) -> None:
        self._style_tree()
        top = tk.Frame(self.window, bg=UI["panel"])
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="Verlauf", bg=UI["panel"], fg=UI["accent"], font=("Arial", 11, "bold")).pack(side="left")
        filters = ["all", "favorites", "uncertain", "wrong", "flashcards"]
        menu = tk.OptionMenu(top, self.filter_var, *filters, command=lambda _value: self.refresh())
        menu.config(bg=UI["button"], fg=UI["text"], activebackground=UI["button_active"], relief="flat")
        menu.pack(side="right")

        self.tree = ttk.Treeview(
            self.window,
            columns=("date", "type", "subject", "short", "confidence", "provider", "cost"),
            show="headings",
            height=12,
        )
        self.tree.heading("date", text="Datum")
        self.tree.heading("type", text="Typ")
        self.tree.heading("subject", text="Fach")
        self.tree.heading("short", text="Kurzantwort")
        self.tree.heading("confidence", text="Conf.")
        self.tree.heading("provider", text="Provider")
        self.tree.heading("cost", text="Kosten")
        self.tree.column("date", width=135, anchor="w")
        self.tree.column("type", width=120, anchor="w")
        self.tree.column("subject", width=110, anchor="w")
        self.tree.column("short", width=235, anchor="w")
        self.tree.column("confidence", width=60, anchor="center")
        self.tree.column("provider", width=70, anchor="w")
        self.tree.column("cost", width=70, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _event: self.open_selected())

        self.preview = tk.Text(
            self.window,
            height=5,
            bg="#0d0f12",
            fg=UI["text"],
            relief="flat",
            wrap="word",
            font=("Consolas", 8),
        )
        self.preview.pack(fill="x", padx=10, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._update_preview())

        buttons = tk.Frame(self.window, bg=UI["panel"])
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        self._button(buttons, "Details", self.open_selected).pack(side="left", padx=(0, 6))
        self._button(buttons, "Favorit", self.toggle_favorite).pack(side="left", padx=6)
        self._button(buttons, "Falsch markieren", self.mark_wrong).pack(side="left", padx=6)
        self._button(buttons, "Loeschen", self.delete_selected).pack(side="left", padx=6)
        self._button(buttons, "Quiz", self.open_quiz).pack(side="left", padx=6)
        self._button(buttons, "Aktualisieren", self.refresh).pack(side="left", padx=6)
        self._button(buttons, "Schliessen", self.window.destroy).pack(side="right")

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        filter_name = self.filter_var.get()
        if filter_name == "flashcards":
            self.current_cards = self.history_service.list_flashcards()
            self.current_history = []
            for card in self.current_cards:
                self.tree.insert(
                    "",
                    "end",
                    iid=f"card:{card['id']}",
                    values=(
                        card["created_at"],
                        "flashcard",
                        card["subject"],
                        card["front"][:80],
                        "",
                        "",
                        "",
                    ),
                )
            return

        self.current_history = self.history_service.list_history(filter_name)
        self.current_cards = []
        for result in self.current_history:
            self.tree.insert(
                "",
                "end",
                iid=f"hist:{result.id}",
                values=(
                    result.created_at or "",
                    result.task_type,
                    result.subject,
                    (result.short_answer or result.full_answer)[:90],
                    f"{result.confidence_percent}%",
                    result.provider,
                    f"${result.estimated_cost_usd:.4f}",
                ),
            )
        self._update_preview()

    def open_selected(self) -> None:
        result = self._selected_result()
        if result is not None:
            self.on_open_result(result)

    def toggle_favorite(self) -> None:
        result = self._selected_result()
        if result is None or result.id is None:
            return
        self.history_service.set_favorite(result.id, not result.favorite)
        self.refresh()

    def delete_selected(self) -> None:
        result = self._selected_result()
        if result is None or result.id is None:
            return
        self.history_service.delete_history(result.id)
        self.refresh()

    def mark_wrong(self) -> None:
        selected = self._selected_iid()
        if not selected:
            return
        kind, raw_id = selected.split(":", 1)
        item_id = int(raw_id)
        if kind == "hist":
            result = self._selected_result()
            if result is not None:
                self.history_service.set_wrong(item_id, not result.marked_wrong)
        else:
            for card in self.current_cards:
                if int(card["id"]) == item_id:
                    self.history_service.database.set_flashcard_wrong(item_id, not bool(card["marked_wrong"]))
                    break
        self.refresh()

    def open_quiz(self) -> None:
        cards = self.history_service.list_flashcards("wrong" if self.filter_var.get() == "wrong" else "all")
        if not cards:
            histories = self.history_service.list_history("wrong" if self.filter_var.get() == "wrong" else "all")
            cards = [
                {
                    "id": None,
                    "history_id": item.id,
                    "front": item.detected_task or item.short_answer,
                    "back": item.full_answer or item.explanation or item.short_answer,
                    "subject": item.subject,
                }
                for item in histories
                if item.full_answer or item.explanation or item.short_answer
            ]
        if cards:
            QuizWindow(self.window, cards, self.history_service)

    def _selected_iid(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _selected_result(self) -> TaskResult | None:
        selected = self._selected_iid()
        if not selected or not selected.startswith("hist:"):
            return None
        item_id = int(selected.split(":", 1)[1])
        for result in self.current_history:
            if result.id == item_id:
                return result
        return None

    def _update_preview(self) -> None:
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        selected = self._selected_iid()
        if not selected:
            self.preview.config(state="disabled")
            return
        kind, raw_id = selected.split(":", 1)
        if kind == "hist":
            result = self._selected_result()
            if result is not None:
                self.preview.insert("end", result.full_answer or result.explanation or result.short_answer)
        else:
            for card in self.current_cards:
                if int(card["id"]) == int(raw_id):
                    self.preview.insert("end", f"{card['front']}\n\n{card['back']}")
                    break
        self.preview.config(state="disabled")

    def _button(self, master: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=UI["button"],
            fg=UI["text"],
            activebackground=UI["button_active"],
            activeforeground=UI["text"],
            relief="flat",
            borderwidth=0,
            font=("Arial", 8),
            padx=9,
            pady=5,
        )

    @staticmethod
    def _style_tree() -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background="#0d0f12", foreground=UI["text"], fieldbackground="#0d0f12")
        style.configure("Treeview.Heading", background=UI["button"], foreground=UI["text"])


class QuizWindow:
    def __init__(self, master: tk.Toplevel, cards: list[dict], history_service: HistoryService) -> None:
        self.cards = list(cards)
        random.shuffle(self.cards)
        self.history_service = history_service
        self.index = 0
        self.answer_visible = False

        self.window = tk.Toplevel(master)
        self.window.title("Moodler Quiz")
        self.window.geometry("520x330+75+105")
        self.window.attributes("-topmost", True)
        self.window.configure(bg=UI["panel"])

        self.counter = tk.Label(self.window, bg=UI["panel"], fg=UI["muted"], font=("Arial", 8))
        self.counter.pack(anchor="w", padx=12, pady=(12, 4))
        self.question = tk.Text(self.window, height=7, bg="#0d0f12", fg=UI["text"], relief="flat", wrap="word")
        self.question.pack(fill="both", expand=True, padx=12, pady=4)
        self.answer = tk.Text(self.window, height=6, bg="#11161b", fg=UI["accent"], relief="flat", wrap="word")
        self.answer.pack(fill="both", expand=True, padx=12, pady=4)

        buttons = tk.Frame(self.window, bg=UI["panel"])
        buttons.pack(fill="x", padx=12, pady=10)
        self._button(buttons, "Antwort zeigen", self.show_answer).pack(side="left")
        self._button(buttons, "Richtig", lambda: self.grade(True)).pack(side="left", padx=6)
        self._button(buttons, "Falsch", lambda: self.grade(False)).pack(side="left", padx=6)
        self._button(buttons, "Weiter", self.next_card).pack(side="left", padx=6)
        self._button(buttons, "Schliessen", self.window.destroy).pack(side="right")
        self._render()

    def _render(self) -> None:
        if self.index >= len(self.cards):
            self.counter.config(text="Quiz fertig")
            self._set_text(self.question, "Fertig. Falsch markierte Karten findest du im Fehlertraining.")
            self._set_text(self.answer, "")
            return
        card = self.cards[self.index]
        self.answer_visible = False
        self.counter.config(text=f"Karte {self.index + 1}/{len(self.cards)} | {card.get('subject', 'unknown')}")
        self._set_text(self.question, card.get("front", ""))
        self._set_text(self.answer, "")

    def show_answer(self) -> None:
        if self.index >= len(self.cards):
            return
        self.answer_visible = True
        self._set_text(self.answer, self.cards[self.index].get("back", ""))

    def grade(self, correct: bool) -> None:
        if self.index >= len(self.cards):
            return
        card = self.cards[self.index]
        flashcard_id = card.get("id")
        history_id = card.get("history_id")
        self.history_service.record_quiz_attempt(correct, flashcard_id=flashcard_id, history_id=history_id)
        if flashcard_id:
            self.history_service.database.set_flashcard_wrong(int(flashcard_id), not correct)
        if history_id:
            self.history_service.set_wrong(int(history_id), not correct)
        self.next_card()

    def next_card(self) -> None:
        self.index += 1
        self._render()

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.config(state="disabled")

    def _button(self, master: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=UI["button"],
            fg=UI["text"],
            activebackground=UI["button_active"],
            activeforeground=UI["text"],
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=5,
        )
