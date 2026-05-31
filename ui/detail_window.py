"""Detail result window."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from config import UI
from models.task_result import TaskResult


class DetailWindow:
    def __init__(
        self,
        master: tk.Tk,
        result: TaskResult,
        on_copy: Callable[[TaskResult], None],
        on_save_cards: Callable[[TaskResult], None],
        on_save_history: Callable[[TaskResult], None],
    ) -> None:
        self.master = master
        self.result = result
        self.on_copy = on_copy
        self.on_save_cards = on_save_cards
        self.on_save_history = on_save_history
        self.window = tk.Toplevel(master)
        self.window.title("Moodler Details")
        self.window.geometry("560x440+35+70")
        self.window.attributes("-topmost", True)
        self.window.configure(bg=UI["panel"])
        self._build()

    def _build(self) -> None:
        header = tk.Frame(self.window, bg=UI["panel"])
        header.pack(fill="x", padx=10, pady=(10, 4))

        title = f"{self.result.task_type} | {self.result.subject} | {self.result.confidence_percent}%"
        tk.Label(header, text=title, fg=UI["accent"], bg=UI["panel"], font=("Arial", 10, "bold"), anchor="w").pack(
            fill="x"
        )

        if self.result.warnings:
            warning_text = " | ".join(self.result.warnings)
            tk.Label(
                self.window,
                text=warning_text,
                fg=UI["warning"],
                bg=UI["panel"],
                font=("Arial", 8),
                wraplength=530,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 6))

        body = tk.Text(
            self.window,
            bg="#0d0f12",
            fg=UI["text"],
            insertbackground=UI["text"],
            relief="flat",
            borderwidth=0,
            wrap="word",
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        body.pack(fill="both", expand=True, padx=10, pady=6)
        body.insert("end", self._content())
        body.config(state="disabled")

        buttons = tk.Frame(self.window, bg=UI["panel"])
        buttons.pack(fill="x", padx=10, pady=(4, 10))
        self._button(buttons, "Kopieren", lambda: self.on_copy(self.result)).pack(side="left", padx=(0, 6))
        self._button(buttons, "Als Karteikarte speichern", lambda: self.on_save_cards(self.result)).pack(
            side="left", padx=6
        )
        self._button(buttons, "In Verlauf speichern", lambda: self.on_save_history(self.result)).pack(side="left", padx=6)
        self._button(buttons, "Schliessen", self.window.destroy).pack(side="right")

    def _content(self) -> str:
        parts = []
        if self.result.detected_task:
            parts.append(f"Erkannte Aufgabe:\n{self.result.detected_task}")
        if self.result.short_answer:
            parts.append(f"Kurzantwort:\n{self.result.short_answer}")
        if self.result.copied_value:
            parts.append(f"Kopierter Wert:\n{self.result.copied_value}")
        if self.result.full_answer:
            parts.append(f"Vollstaendige Antwort:\n{self.result.full_answer}")
        if self.result.explanation:
            parts.append(f"Erklaerung:\n{self.result.explanation}")
        if self.result.provider != "unknown" or self.result.total_tokens or self.result.estimated_cost_usd:
            fallback = "ja" if self.result.fallback_used else "nein"
            parts.append(
                "Kosten/Provider:\n"
                f"Provider: {self.result.provider or 'unknown'}\n"
                f"Modell: {self.result.model or '-'}\n"
                f"Modus: {self.result.provider_mode or '-'}\n"
                f"Tokens: {self.result.total_tokens} "
                f"(Input {self.result.input_tokens}, Output {self.result.output_tokens})\n"
                f"Kosten lokal geschaetzt: ${self.result.estimated_cost_usd:.6f}\n"
                f"Fallback genutzt: {fallback}"
            )
        if self.result.flashcards:
            cards = "\n".join(f"- {card.front} -> {card.back}" for card in self.result.flashcards)
            parts.append(f"Karteikarten:\n{cards}")
        if self.result.agent_summary:
            parts.append(f"Agenten-Vergleich:\n{self.result.agent_summary}")
        if self.result.agent_results:
            agent_parts = []
            for index, agent_result in enumerate(self.result.agent_results, start=1):
                answer = agent_result.full_answer or agent_result.short_answer or agent_result.explanation
                agent_parts.append(
                    f"Agent {index} ({agent_result.confidence_percent}%, "
                    f"{agent_result.provider}/{agent_result.model}, "
                    f"{agent_result.total_tokens} Tokens, ${agent_result.estimated_cost_usd:.6f}):\n"
                    f"{agent_result.short_answer}\n{answer}"
                )
            parts.append("Einzelne Agenten:\n" + "\n\n".join(agent_parts))
        return "\n\n".join(parts) or "Keine Details vorhanden."

    def _button(self, master: tk.Widget, text: str, command: Callable[[], None]) -> tk.Button:
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
            padx=8,
            pady=4,
        )
