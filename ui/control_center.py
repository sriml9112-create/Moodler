"""Simple Control Center for all non-toolbar Moodler features."""

from __future__ import annotations

import importlib.util
import platform
import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from config import (
    AI_PROVIDERS,
    AVAILABLE_MODELS,
    CONFIG_PATH,
    GEMINI_MODELS,
    MODEL_DESCRIPTIONS,
    MODEL_FALLBACKS,
    GEMINI_MODEL_FALLBACKS,
    OPENAI_MODELS,
    PROJECT_ROOT,
    TASK_TYPES,
    UI,
)
from models.app_settings import AppSettings
from models.task_result import TaskResult
from services.history_service import HistoryService
from utils.validation import looks_like_api_key, looks_like_gemini_api_key


class ControlCenter:
    def __init__(
        self,
        master: tk.Tk,
        settings: AppSettings,
        history_service: HistoryService,
        on_save_settings: Callable[[AppSettings], None],
        on_open_result: Callable[[TaskResult], None],
        on_copy_text: Callable[[str], None],
        on_text_task: Callable[[], None],
        on_open_last: Callable[[], None],
        on_open_history_window: Callable[[], None],
        get_overview_state: Callable[[], dict[str, object]],
    ) -> None:
        self.master = master
        self.settings = AppSettings.from_dict(settings.to_dict())
        self.history_service = history_service
        self.on_save_settings = on_save_settings
        self.on_open_result = on_open_result
        self.on_copy_text = on_copy_text
        self.on_text_task = on_text_task
        self.on_open_last = on_open_last
        self.on_open_history_window = on_open_history_window
        self.get_overview_state = get_overview_state
        self.history_rows: list[TaskResult] = []

        self.window = tk.Toplevel(master)
        self.window.title("Moodler Control Center")
        self.window.geometry("860x560+35+70")
        self.window.attributes("-topmost", True)
        self.window.configure(bg=UI["panel"])
        self._style()

        self.tabs = ttk.Notebook(self.window)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_dashboard_tab()
        self._build_api_tab()
        self._build_models_tab()
        self._build_accuracy_tab()
        self._build_automation_tab()
        self._build_history_tab()
        self._build_help_tab()
        self._build_export_tab()
        self.refresh_dashboard()

    def select_tab(self, name: str) -> None:
        wanted = name.lower()
        aliases = {
            "settings": "api",
            "einstellungen": "api",
            "agenten": "genauigkeit",
            "tutorials": "hilfe",
            "diagnose": "dashboard",
        }
        wanted = aliases.get(wanted, wanted)
        for index in range(self.tabs.index("end")):
            text = str(self.tabs.tab(index, "text")).lower()
            if text.startswith(wanted) or wanted in text:
                self.tabs.select(index)
                return

    def _build_dashboard_tab(self) -> None:
        tab = self._tab("Dashboard")
        self._heading(tab, "Dashboard", "Alles Wichtige auf einen Blick.")
        grid = tk.Frame(tab, bg=UI["panel"])
        grid.pack(fill="x", padx=16, pady=8)
        self.dashboard_labels: dict[str, tk.Label] = {}
        for index, key in enumerate(
            [
                "Anbieter",
                "API-Key",
                "SEB erkannt",
                "Modell",
                "Agenten",
                "Letzter Task",
                "Confidence",
                "Letzte Kosten",
                "Gesamtkosten",
                "Restbudget",
                "Kopierter Wert",
                "Copy-Status",
            ]
        ):
            row, col = divmod(index, 2)
            box = tk.Frame(grid, bg=UI["panel_2"], padx=10, pady=8)
            box.grid(row=row, column=col, sticky="ew", padx=6, pady=6)
            tk.Label(box, text=key.upper(), bg=UI["panel_2"], fg=UI["muted"], font=("Arial", 7, "bold")).pack(anchor="w")
            label = tk.Label(box, text="-", bg=UI["panel_2"], fg=UI["text"], font=("Arial", 11, "bold"), anchor="w")
            label.pack(fill="x")
            self.dashboard_labels[key] = label
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        buttons = tk.Frame(tab, bg=UI["panel"])
        buttons.pack(fill="x", padx=16, pady=8)
        self._button(buttons, "Letzte Antwort öffnen", self.on_open_last).pack(side="left", padx=(0, 8))
        self._button(buttons, "Letzte Antwort kopieren", self._copy_last_answer).pack(side="left", padx=8)
        self._button(buttons, "Textaufgabe eingeben", self.on_text_task).pack(side="left", padx=8)
        self._button(buttons, "Kosten zurücksetzen", self._reset_costs).pack(side="left", padx=8)
        self._button(buttons, "System prüfen", self._run_dashboard_diagnostics).pack(side="right")

        budget = tk.Frame(tab, bg=UI["panel"])
        budget.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(budget, text="Startbudget USD", bg=UI["panel"], fg=UI["muted"]).pack(side="left")
        self.budget_var = tk.StringVar(value=f"{self.settings.cost_budget_usd:.2f}")
        tk.Entry(budget, textvariable=self.budget_var, bg="#0d0f12", fg=UI["text"], relief="flat", width=10).pack(
            side="left", padx=6
        )
        self._button(budget, "Budget setzen", self._save_budget).pack(side="left", padx=6)
        tk.Label(
            budget,
            text="Live-Balance ist nicht verfügbar; Moodler zeigt lokale Schätzungen.",
            bg=UI["panel"],
            fg=UI["muted"],
        ).pack(side="left", padx=10)

        self.dashboard_diagnostics = self._text(tab, "", height=10)
        self.dashboard_diagnostics.pack(fill="both", expand=True, padx=16, pady=10)
        self._set_text(self.dashboard_diagnostics, "Systemcheck nur bei Bedarf: Button 'System prüfen' klicken.")

    def _build_api_tab(self) -> None:
        tab = self._tab("API")
        self._heading(tab, "API", "Anbieter wählen und Keys getrennt speichern. Keys werden nie vollständig angezeigt.")
        form = tk.Frame(tab, bg=UI["panel"])
        form.pack(fill="x", padx=16, pady=12)
        self.provider_var = tk.StringVar(value=self.settings.ai_provider)
        self.openai_key_var = tk.StringVar(value=self.settings.openai_api_key or self.settings.api_key)
        self.gemini_key_var = tk.StringVar(value=self.settings.gemini_api_key)
        self.api_key_var = self.openai_key_var

        self._field(form, "API-Anbieter", 0)
        provider_menu = tk.OptionMenu(form, self.provider_var, *AI_PROVIDERS)
        provider_menu.config(bg=UI["button"], fg=UI["text"], activebackground=UI["button_active"], relief="flat", highlightthickness=0)
        provider_menu.grid(row=0, column=1, sticky="ew", pady=5)

        self._field(form, "OpenAI-Key", 1)
        tk.Entry(form, textvariable=self.openai_key_var, show="*", bg="#0d0f12", fg=UI["text"], relief="flat").grid(
            row=1, column=1, sticky="ew", pady=5
        )
        self._button(form, "OpenAI testen", self._test_openai_key).grid(row=1, column=2, padx=(8, 0))
        self._button(form, "Löschen", self._clear_openai_key).grid(row=1, column=3, padx=(8, 0))

        self._field(form, "Gemini-Key", 2)
        tk.Entry(form, textvariable=self.gemini_key_var, show="*", bg="#0d0f12", fg=UI["text"], relief="flat").grid(
            row=2, column=1, sticky="ew", pady=5
        )
        self._button(form, "Gemini testen", self._test_gemini_key).grid(row=2, column=2, padx=(8, 0))
        self._button(form, "Löschen", self._clear_gemini_key).grid(row=2, column=3, padx=(8, 0))

        form.columnconfigure(1, weight=1)
        self._button(form, "Speichern", self._save_settings).grid(row=0, column=2, columnspan=2, sticky="ew", padx=(8, 0))

        self.api_mask_label = tk.Label(tab, text="", bg=UI["panel"], fg=UI["text"], font=("Arial", 10, "bold"), anchor="w")
        self.api_mask_label.pack(fill="x", padx=16, pady=(4, 2))
        self.api_status = tk.Label(tab, text="", bg=UI["panel"], fg=UI["muted"], anchor="w")
        self.api_status.pack(fill="x", padx=16, pady=(2, 10))
        chip_row = tk.Frame(tab, bg=UI["panel"])
        chip_row.pack(fill="x", padx=16, pady=(0, 8))
        self.api_chips: dict[str, tk.Label] = {}
        for name in ["Provider", "OpenAI", "Gemini", "Compare"]:
            chip = self._chip(chip_row, f"{name}: -", "warn")
            chip.pack(side="left", padx=(0, 6))
            self.api_chips[name] = chip
        self._text(
            tab,
            "Du kannst Keys auch in .env speichern:\n"
            "OPENAI_API_KEY=sk-...\n"
            "GEMINI_API_KEY=...\n"
            "AI_PROVIDER=openai | gemini | auto | compare\n\n"
            "Auto nutzt zuerst einen verfügbaren Anbieter und fällt leise auf den anderen zurück. Compare lässt OpenAI und Gemini antworten und verifiziert fachlich.",
            height=8,
        ).pack(fill="x", padx=16, pady=10)
        self._refresh_api_status()

    def _build_models_tab(self) -> None:
        tab = self._tab("Modelle")
        self._heading(tab, "Modelle", "OpenAI- und Gemini-Modelle getrennt auswählen. Ungültige Modelle crashen nicht.")
        tk.Label(
            tab,
            text="Alltag: gpt-4.1 | Vision: gpt-4o | Gemini Standard: gemini-2.5-flash | Preview-Modelle nur falls verfügbar",
            bg=UI["panel"],
            fg=UI["warning"],
            font=("Arial", 9, "bold"),
            wraplength=800,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        body = tk.Frame(tab, bg=UI["panel"])
        body.pack(fill="both", expand=True, padx=16, pady=8)
        openai_box = tk.Frame(body, bg=UI["panel"])
        openai_box.pack(side="left", fill="y")
        tk.Label(openai_box, text="OpenAI", bg=UI["panel"], fg=UI["text"], font=("Arial", 9, "bold")).pack(anchor="w")
        self.model_list = tk.Listbox(openai_box, bg="#0d0f12", fg=UI["text"], relief="flat", height=9, exportselection=False)
        self.model_list.pack(fill="y")
        for model in self._visible_models():
            self.model_list.insert("end", model)
            if model == self.settings.openai_model:
                self.model_list.selection_set("end")
        gemini_box = tk.Frame(body, bg=UI["panel"])
        gemini_box.pack(side="left", fill="y", padx=(12, 0))
        tk.Label(gemini_box, text="Gemini", bg=UI["panel"], fg=UI["text"], font=("Arial", 9, "bold")).pack(anchor="w")
        self.gemini_model_list = tk.Listbox(gemini_box, bg="#0d0f12", fg=UI["text"], relief="flat", height=9, exportselection=False)
        self.gemini_model_list.pack(fill="y")
        for model in self._visible_gemini_models():
            self.gemini_model_list.insert("end", model)
            if model == self.settings.gemini_model:
                self.gemini_model_list.selection_set("end")
        desc = self._text(body, self._model_description_text(), height=14)
        desc.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.model_chip = self._chip(tab, "", "ok")
        self.model_chip.pack(anchor="w", padx=16, pady=(0, 4))
        self._button(tab, "Modelle speichern", self._save_selected_model).pack(anchor="w", padx=16, pady=12)
        self._refresh_model_chip()

    def _build_accuracy_tab(self) -> None:
        tab = self._tab("Genauigkeit")
        self._heading(tab, "Genauigkeit", "Agenten vergleichen nur. Der Verifier entscheidet fachlich, nicht nach Mehrheit.")
        self.agent_count_var = tk.IntVar(value=self.settings.agent_count)
        self.agent_label = tk.Label(tab, text=f"Agenten: {self.settings.agent_count}", bg=UI["panel"], fg=UI["accent"], font=("Arial", 12, "bold"))
        self.agent_label.pack(anchor="w", padx=16)
        tk.Scale(
            tab,
            from_=1,
            to=5,
            orient="horizontal",
            variable=self.agent_count_var,
            command=lambda _value: self.agent_label.config(text=f"Agenten: {self.agent_count_var.get()}"),
            bg=UI["panel"],
            fg=UI["text"],
            troughcolor="#0d0f12",
            highlightthickness=0,
        ).pack(fill="x", padx=16, pady=8)
        self._text(
            tab,
            "Standard: 2 Agenten.\n\n"
            "Mehr Agenten kosten mehr Zeit und API-Geld.\n"
            "Verifier ist immer aktiv.\n"
            "Keine Entscheidung nach Mehrheit.\n"
            "Mathe/BW werden fachlich geprüft.\n"
            "Schwierige Aufgaben nutzen automatisch OpenAI + Gemini, wenn beide Keys vorhanden sind.",
            height=10,
        ).pack(fill="both", expand=True, padx=16, pady=8)
        self._button(tab, "Agenten speichern", self._save_agents).pack(anchor="w", padx=16, pady=12)

    def _build_automation_tab(self) -> None:
        tab = self._tab("Automatik")
        self._heading(tab, "Automatik", "Wenig einstellen, viel automatisch machen.")
        self.auto_detect_var = tk.BooleanVar(value=self.settings.auto_detect_tasks)
        self.auto_copy_var = tk.BooleanVar(value=self.settings.auto_copy_long_results)
        self.auto_history_var = tk.BooleanVar(value=self.settings.auto_save_history)
        self.open_details_var = tk.BooleanVar(value=self.settings.open_details_for_long)
        self.language_var = tk.StringVar(value=self.settings.language)
        self.timeout_var = tk.IntVar(value=self.settings.timeout_seconds)

        form = tk.Frame(tab, bg=UI["panel"])
        form.pack(fill="x", padx=16, pady=12)
        self._check(form, "Aufgaben automatisch erkennen", self.auto_detect_var)
        self._check(form, "Lange Antworten automatisch kopieren", self.auto_copy_var)
        self._check(form, "Verlauf automatisch speichern", self.auto_history_var)
        self._check(form, "Detailfenster automatisch öffnen", self.open_details_var)
        self._option(form, "Sprache", self.language_var, ["auto", "de", "en"])
        self._option(form, "Timeout", self.timeout_var, [15, 30, 60])
        self._button(tab, "Automatik speichern", self._save_settings).pack(anchor="w", padx=16, pady=12)

    def _build_history_tab(self) -> None:
        tab = self._tab("Verlauf")
        self._heading(tab, "Verlauf", "Suchen, filtern, kopieren und löschen.")
        controls = tk.Frame(tab, bg=UI["panel"])
        controls.pack(fill="x", padx=16, pady=(6, 8))
        self.search_var = tk.StringVar()
        self.task_filter_var = tk.StringVar(value="all")
        self.favorite_filter_var = tk.BooleanVar(value=False)
        tk.Label(controls, text="Suche", bg=UI["panel"], fg=UI["muted"]).pack(side="left")
        tk.Entry(controls, textvariable=self.search_var, bg="#0d0f12", fg=UI["text"], relief="flat", width=24).pack(side="left", padx=6)
        self._mini_option(controls, self.task_filter_var, ["all", *TASK_TYPES]).pack(side="left", padx=6)
        tk.Checkbutton(
            controls,
            text="Favoriten",
            variable=self.favorite_filter_var,
            bg=UI["panel"],
            fg=UI["text"],
            selectcolor=UI["panel_2"],
            command=self.refresh_history,
        ).pack(side="left", padx=6)
        self._button(controls, "Suchen", self.refresh_history).pack(side="right")

        self.history_tree = ttk.Treeview(
            tab,
            columns=("date", "type", "short", "copied", "confidence", "provider", "model", "mode", "tokens", "cost", "fb", "fav"),
            show="headings",
        )
        for col, label, width in [
            ("date", "Datum", 110),
            ("type", "Typ", 86),
            ("short", "Kurzantwort", 170),
            ("copied", "Kopiert", 120),
            ("confidence", "Conf.", 52),
            ("provider", "Provider", 66),
            ("model", "Modell", 96),
            ("mode", "Modus", 60),
            ("tokens", "Tokens", 62),
            ("cost", "Kosten", 72),
            ("fb", "FB", 34),
            ("fav", "Fav", 36),
        ]:
            self.history_tree.heading(col, text=label)
            self.history_tree.column(col, width=width, anchor="w")
        self.history_tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.history_tree.bind("<Double-1>", lambda _event: self._history_details())
        buttons = tk.Frame(tab, bg=UI["panel"])
        buttons.pack(fill="x", padx=16, pady=(0, 14))
        self._button(buttons, "Details", self._history_details).pack(side="left")
        self._button(buttons, "Kopieren", self._history_copy).pack(side="left", padx=6)
        self._button(buttons, "Löschen", self._history_delete).pack(side="left", padx=6)
        self._button(buttons, "Alle löschen", self._history_delete_all).pack(side="left", padx=6)
        self._button(buttons, "Favorit", self._history_favorite).pack(side="left", padx=6)
        self._button(buttons, "Aktualisieren", self.refresh_history).pack(side="right")
        self.search_var.trace_add("write", lambda *_args: self.refresh_history())
        self.refresh_history()

    def _build_help_tab(self) -> None:
        tab = self._tab("Hilfe")
        self._heading(tab, "Hilfe", "Kurz und brauchbar.")
        tutorials = [
            ("Screenshot benutzen", ["Kamera klicken.", "Bereich ziehen.", "Pfeil klicken."], "20% Rabatt auf 250 Euro."),
            ("Antwort senden", ["Screenshot oder Text vorbereiten.", "Pfeil klicken.", "Kurzantwort lesen."], "Welche Option ist richtig?"),
            ("BW-Frage lösen", ["Kaufvertrag/Zahlung/Mahnung erfassen.", "Pfeil klicken.", "Details bei Unsicherheit lesen."], "Mangelhafte Lieferung: Rechte?"),
            ("E-Mail/Brief kopieren", ["Aufgabe erfassen.", "Pfeil klicken.", "Text ist in der Zwischenablage."], "Formelle E-Mail an Lieferanten."),
            ("Agenten verstehen", ["1 schnell.", "2 Standard.", "Mehr = langsamer/teurer."], "Schwierige BW-MC-Frage."),
            ("API-Key eingeben", ["Zahnrad.", "API.", "Key speichern."], "OPENAI_API_KEY=sk-..."),
            ("App exportieren", ["Export Tab.", "build_portable.bat.", "ZIP weitergeben."], "Moodler-portable.zip"),
        ]
        box = self._text(tab, "", height=24)
        box.pack(fill="both", expand=True, padx=16, pady=12)
        lines: list[str] = []
        for title, steps, example in tutorials:
            lines.append(title.upper())
            lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
            lines.append(f"Beispiel: {example}")
            lines.append("")
        self._set_text(box, "\n".join(lines))

    def _build_export_tab(self) -> None:
        tab = self._tab("Export")
        self._heading(tab, "Export", "So einfach wie möglich.")
        text = (
            "Portable ZIP erstellen:\n"
            "1. Doppelklick auf build_portable.bat\n"
            "2. ZIP liegt danach in dist/Moodler-portable.zip\n\n"
            "Desktop-Verknüpfung erstellen:\n"
            "1. Doppelklick auf create_shortcut.bat\n"
            "2. Verknüpfung erscheint am Desktop\n\n"
            "Taskleiste:\n"
            "Rechtsklick auf die Desktop-Verknüpfung -> An Taskleiste anheften.\n\n"
            "Beim Laufen zeigt Moodler nur die kleine Toolbar. Das Control Center erscheint nur nach Klick auf Zahnrad."
        )
        self._text(tab, text, height=20).pack(fill="both", expand=True, padx=16, pady=12)
        buttons = tk.Frame(tab, bg=UI["panel"])
        buttons.pack(fill="x", padx=16, pady=12)
        self._button(buttons, "Portable-Befehl kopieren", lambda: self.on_copy_text("build_portable.bat")).pack(side="left", padx=(0, 8))
        self._button(buttons, "Shortcut-Befehl kopieren", lambda: self.on_copy_text("create_shortcut.bat")).pack(side="left", padx=8)

    def refresh_dashboard(self) -> None:
        state = self.get_overview_state()
        cost = self.history_service.cost_summary()
        last_cost = cost.get("last") or {}
        total_cost = float(cost.get("estimated_cost_usd") or 0)
        budget = float(self.settings.cost_budget_usd or 0)
        remaining = max(0.0, budget - total_cost) if budget else 0.0
        values = {
            "Anbieter": str(state.get("provider", "openai")),
            "API-Key": "vorhanden" if state.get("api_key_ok") else "fehlt",
            "SEB erkannt": str(state.get("seb_detected", "unbekannt")),
            "Modell": str(state.get("model", "-")),
            "Agenten": str(state.get("agent_count", "-")),
            "Letzter Task": str(state.get("last_task", "-")),
            "Confidence": str(state.get("last_confidence", "-")),
            "Letzte Kosten": self._format_money(float(last_cost.get("estimated_cost_usd") or 0)),
            "Gesamtkosten": self._format_money(total_cost),
            "Restbudget": self._format_money(remaining) if budget else "kein Budget",
            "Kopierter Wert": str(state.get("last_copied_value", "") or last_cost.get("copied_value") or "-"),
            "Copy-Status": str(state.get("copy_status", "-")),
        }
        for key, value in values.items():
            self.dashboard_labels[key].config(text=value)
        self._refresh_api_status()

    def refresh_history(self) -> None:
        self.history_tree.delete(*self.history_tree.get_children())
        query = self.search_var.get().strip().lower()
        task_filter = self.task_filter_var.get()
        only_favorites = bool(self.favorite_filter_var.get())
        rows = self.history_service.list_history("favorites" if only_favorites else "all")
        self.history_rows = []
        for result in rows:
            haystack = " ".join(
                [
                    result.task_type,
                    result.subject,
                    result.detected_task,
                    result.short_answer,
                    result.full_answer,
                    result.copied_value,
                ]
            ).lower()
            if query and query not in haystack:
                continue
            if task_filter != "all" and result.task_type != task_filter:
                continue
            self.history_rows.append(result)
        for result in self.history_rows:
            if result.id is None:
                continue
            self.history_tree.insert(
                "",
                "end",
                iid=str(result.id),
                values=(
                    result.created_at or "",
                    result.task_type,
                    (result.short_answer or result.full_answer)[:100],
                    result.copied_value[:80],
                    f"{result.confidence_percent}%",
                    result.provider,
                    result.model,
                    result.provider_mode,
                    result.total_tokens,
                    f"${result.estimated_cost_usd:.4f}",
                    "ja" if result.fallback_used else "",
                    "ja" if result.favorite else "",
                ),
            )

    def _save_settings(self) -> None:
        if hasattr(self, "provider_var"):
            provider = self.provider_var.get().strip().lower()
            self.settings.ai_provider = provider if provider in AI_PROVIDERS else "openai"
        if hasattr(self, "openai_key_var"):
            self.settings.openai_api_key = self.openai_key_var.get().strip()
            self.settings.api_key = self.settings.openai_api_key
        if hasattr(self, "gemini_key_var"):
            self.settings.gemini_api_key = self.gemini_key_var.get().strip()
        if hasattr(self, "language_var"):
            self.settings.language = self.language_var.get()
            self.settings.timeout_seconds = int(self.timeout_var.get())
            self.settings.auto_detect_tasks = bool(self.auto_detect_var.get())
            self.settings.auto_copy_long_results = bool(self.auto_copy_var.get())
            self.settings.open_details_for_long = bool(self.open_details_var.get())
            self.settings.auto_save_history = bool(self.auto_history_var.get())
        if hasattr(self, "agent_count_var"):
            self.settings.agent_count = int(self.agent_count_var.get())
        if hasattr(self, "budget_var"):
            self.settings.cost_budget_usd = self._parse_money(self.budget_var.get())
        self.settings.enable_learning_guardrails = True
        self.settings.bw_focus_enabled = True
        self.settings.suppress_task_popups = True
        self.settings.preferred_subjects = None
        self.settings = AppSettings.from_dict(self.settings.to_dict())
        self.on_save_settings(AppSettings.from_dict(self.settings.to_dict()))
        self.refresh_dashboard()
        self._refresh_api_status()
        self._refresh_model_chip()
        self._status("Gespeichert.")

    def _save_budget(self) -> None:
        self.settings.cost_budget_usd = self._parse_money(self.budget_var.get())
        self.on_save_settings(AppSettings.from_dict(self.settings.to_dict()))
        self.refresh_dashboard()
        self._status("Budget gesetzt.")

    def _reset_costs(self) -> None:
        self.history_service.reset_costs()
        self.refresh_dashboard()
        self.refresh_history()
        self._status("Kosten zurückgesetzt.")

    def _save_agents(self) -> None:
        self.settings.agent_count = int(self.agent_count_var.get())
        self._save_settings()

    def _save_selected_model(self) -> None:
        openai_selection = self.model_list.curselection()
        if openai_selection:
            model = self._visible_models()[openai_selection[0]]
            if model not in OPENAI_MODELS:
                self._status("Ungültiges OpenAI-Modell.")
                return
            self.settings.openai_model = model
            self.settings.model = model
        gemini_selection = self.gemini_model_list.curselection()
        if gemini_selection:
            gemini_model = self._visible_gemini_models()[gemini_selection[0]]
            if gemini_model not in GEMINI_MODELS:
                self._status("Ungültiges Gemini-Modell.")
                return
            self.settings.gemini_model = gemini_model
        if not openai_selection and not gemini_selection:
            self._status("Kein Modell ausgewählt.")
            return
        self._save_settings()
        self._status("Modelle gespeichert.")
        self._refresh_model_chip()

    def _visible_models(self) -> list[str]:
        visible = ["gpt-5.5", "gpt-5.2", "gpt-4.1", "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"]
        return [model for model in visible if model in OPENAI_MODELS]

    def _visible_gemini_models(self) -> list[str]:
        visible = [
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ]
        return [model for model in visible if model in GEMINI_MODELS]

    def _model_description_text(self) -> str:
        lines = []
        for model in self._visible_models():
            lines.append(f"{model}\n{MODEL_DESCRIPTIONS.get(model, 'keine Beschreibung')}")
        lines.append("\nGemini")
        for model in self._visible_gemini_models():
            lines.append(f"{model}\n{MODEL_DESCRIPTIONS.get(model, 'keine Beschreibung')}")
        lines.append("\nOpenAI-Fallback automatisch: " + " -> ".join(MODEL_FALLBACKS))
        lines.append("Gemini-Fallback automatisch: " + " -> ".join(GEMINI_MODEL_FALLBACKS))
        lines.append("gpt-5.5 wird nur genutzt, wenn es in deiner Config/API verfügbar ist; sonst nimmt Moodler automatisch einen Fallback.")
        return "\n\n".join(lines)

    def _run_dashboard_diagnostics(self) -> None:
        lines = []
        for status, check, detail, fix in self._diagnostic_rows():
            lines.append(f"{status}: {check} - {detail} ({fix})")
        self._set_text(self.dashboard_diagnostics, "\n".join(lines))

    def _diagnostic_rows(self) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        rows.append(("OK", "Python", sys.version.split()[0], "Keine Aktion"))
        rows.append(self._package_row("openai", "openai", "pip install -r requirements.txt"))
        rows.append(self._package_row("google.genai", "google-genai", "pip install -r requirements.txt"))
        rows.append(self._package_row("PIL", "pillow", "pip install pillow"))
        rows.append(self._package_row("win32api", "pywin32", "pip install pywin32"))
        rows.append(self._package_row("pyperclip", "pyperclip", "pip install pyperclip"))
        rows.append(("OK" if self.settings.openai_api_key else "WARNUNG", "OpenAI-Key", "vorhanden" if self.settings.openai_api_key else "fehlt", "API Tab"))
        rows.append(("OK" if self.settings.gemini_api_key else "WARNUNG", "Gemini-Key", "vorhanden" if self.settings.gemini_api_key else "fehlt", "API Tab"))
        state = self.get_overview_state()
        seb_label = str(state.get("seb_detected", "unbekannt"))
        seb_details = str(state.get("seb_details", ""))
        seb_status = "WARNUNG" if seb_label == "Ja" else "OK" if seb_label == "Nein" else "WARNUNG"
        rows.append((
            seb_status,
            "SEB",
            f"erkannt: {seb_label}; {seb_details}",
            "Nur nutzen, wenn Schule und SEB-Konfiguration Moodler erlauben.",
        ))
        rows.append(("OK" if (PROJECT_ROOT / ".env").exists() else "WARNUNG", ".env", str((PROJECT_ROOT / ".env").exists()), ".env.example kopieren"))
        rows.append(("OK" if CONFIG_PATH.parent.exists() else "WARNUNG", "Config", str(CONFIG_PATH), "AppData prüfen"))
        try:
            self.history_service.database.ping()
            rows.append(("OK", "DB", "ok", "Keine Aktion"))
        except Exception as exc:
            rows.append(("FEHLER", "DB", str(exc), "AppData prüfen"))
        rows.append(("OK", "System", platform.platform(), "Keine Aktion"))
        return rows

    def _package_row(self, module_name: str, label: str, fix: str) -> tuple[str, str, str, str]:
        try:
            ok = importlib.util.find_spec(module_name) is not None
        except ModuleNotFoundError:
            ok = False
        return ("OK" if ok else "FEHLER", label, "installiert" if ok else "fehlt", fix)

    def _selected_history(self) -> TaskResult | None:
        selection = self.history_tree.selection()
        if not selection:
            return None
        history_id = int(selection[0])
        return next((row for row in self.history_rows if row.id == history_id), None)

    def _history_details(self) -> None:
        result = self._selected_history()
        if result is not None:
            self.on_open_result(result)

    def _history_copy(self) -> None:
        result = self._selected_history()
        if result is not None:
            self.on_copy_text(result.copied_value or result.full_answer or result.short_answer)

    def _history_delete(self) -> None:
        result = self._selected_history()
        if result is not None and result.id is not None:
            self.history_service.delete_history(result.id)
            self.refresh_history()

    def _history_delete_all(self) -> None:
        if messagebox.askyesno("Moodler Verlauf", "Wirklich alle Verlaufseinträge löschen?", parent=self.window):
            self.history_service.delete_all_history()
            self.refresh_history()

    def _history_favorite(self) -> None:
        result = self._selected_history()
        if result is not None and result.id is not None:
            self.history_service.set_favorite(result.id, not result.favorite)
            self.refresh_history()

    def _copy_last_answer(self) -> None:
        state = self.get_overview_state()
        text = str(state.get("last_copied_value") or state.get("last_answer_text", ""))
        if text:
            self.on_copy_text(text)
            self._status("Letzte Antwort kopiert.")
        else:
            self._status("Keine letzte Antwort vorhanden.")

    def _clear_api_key(self) -> None:
        self._clear_openai_key()

    def _clear_openai_key(self) -> None:
        self.openai_key_var.set("")
        self.settings.openai_api_key = ""
        self.settings.api_key = ""
        self._save_settings()

    def _clear_gemini_key(self) -> None:
        self.gemini_key_var.set("")
        self.settings.gemini_api_key = ""
        self._save_settings()

    def _test_api_key(self) -> None:
        self._test_openai_key()

    def _test_openai_key(self) -> None:
        self._refresh_api_status()
        if looks_like_api_key(self.openai_key_var.get().strip()):
            self.api_status.config(text="OK: OpenAI-Key wirkt gültig.", fg="#68d391")
        else:
            self.api_status.config(text="WARNUNG: OpenAI-Key fehlt oder sieht ungültig aus.", fg="#f6c177")

    def _test_gemini_key(self) -> None:
        self._refresh_api_status()
        if looks_like_gemini_api_key(self.gemini_key_var.get().strip()):
            self.api_status.config(text="OK: Gemini-Key wirkt gültig.", fg="#68d391")
        else:
            self.api_status.config(text="WARNUNG: Gemini-Key fehlt oder sieht ungültig aus.", fg="#f6c177")

    def _refresh_api_status(self) -> None:
        if not hasattr(self, "openai_key_var"):
            return
        openai_key = self.openai_key_var.get().strip()
        gemini_key = self.gemini_key_var.get().strip()
        provider = self.provider_var.get().strip().lower() if hasattr(self, "provider_var") else self.settings.ai_provider
        self.api_mask_label.config(
            text=(
                f"Anbieter: {provider} | OpenAI: {self._mask_key(openai_key)} | "
                f"Gemini: {self._mask_key(gemini_key, prefix='gemini')}"
            )
        )
        provider_ok = self._provider_keys_ok(provider, openai_key, gemini_key)
        color = "#68d391" if provider_ok else "#f6c177"
        text = "OK: Anbieter hat passenden Key." if provider_ok else "WARNUNG: Für diesen Anbieter fehlt ein passender Key."
        self.api_status.config(text=text, fg=color)
        if hasattr(self, "api_chips"):
            self._set_chip(self.api_chips["Provider"], f"Provider: {provider}", "ok")
            self._set_chip(self.api_chips["OpenAI"], "OpenAI: OK" if looks_like_api_key(openai_key) else "OpenAI: fehlt", "ok" if looks_like_api_key(openai_key) else "warn")
            self._set_chip(self.api_chips["Gemini"], "Gemini: OK" if looks_like_gemini_api_key(gemini_key) else "Gemini: fehlt", "ok" if looks_like_gemini_api_key(gemini_key) else "warn")
            self._set_chip(self.api_chips["Compare"], "Compare: bereit" if self._provider_keys_ok("compare", openai_key, gemini_key) else "Compare: 2 Keys", "ok" if self._provider_keys_ok("compare", openai_key, gemini_key) else "warn")

    def _refresh_model_chip(self) -> None:
        if not hasattr(self, "model_chip"):
            return
        self._set_chip(
            self.model_chip,
            f"OpenAI: {self.settings.openai_model} | Gemini: {self.settings.gemini_model} | Fallbacks aktiv",
            "ok",
        )

    @staticmethod
    def _mask_key(key: str, prefix: str = "openai") -> str:
        if not key:
            return "kein Key"
        return f"{key[:5]}...{key[-4:]}" if len(key) > 10 else ("..." if prefix == "gemini" else "sk-...")

    @staticmethod
    def _provider_keys_ok(provider: str, openai_key: str, gemini_key: str) -> bool:
        if provider == "openai":
            return looks_like_api_key(openai_key)
        if provider == "gemini":
            return looks_like_gemini_api_key(gemini_key)
        if provider == "compare":
            return looks_like_api_key(openai_key) and looks_like_gemini_api_key(gemini_key)
        return looks_like_api_key(openai_key) or looks_like_gemini_api_key(gemini_key)

    def _status(self, text: str) -> None:
        self.window.title(f"Moodler Control Center - {text}")

    @staticmethod
    def _format_money(value: float) -> str:
        return f"${max(0.0, value):.4f} lokal"

    @staticmethod
    def _parse_money(value: str) -> float:
        try:
            return max(0.0, float(str(value).strip().replace(",", ".")))
        except (TypeError, ValueError):
            return 0.0

    def _tab(self, title: str) -> tk.Frame:
        frame = tk.Frame(self.tabs, bg=UI["panel"])
        self.tabs.add(frame, text=title)
        return frame

    def _heading(self, master: tk.Widget, title: str, subtitle: str) -> None:
        tk.Label(master, text=title.upper(), bg=UI["panel"], fg=UI["accent"], font=("Arial", 13, "bold")).pack(
            anchor="w", padx=16, pady=(16, 2)
        )
        tk.Label(master, text=subtitle, bg=UI["panel"], fg=UI["muted"], font=("Arial", 9), wraplength=780, justify="left").pack(
            anchor="w", padx=16, pady=(0, 10)
        )

    def _field(self, master: tk.Widget, label: str, row: int) -> None:
        tk.Label(master, text=label, bg=UI["panel"], fg=UI["text"]).grid(row=row, column=0, sticky="w", pady=5)

    def _option(self, master: tk.Widget, label: str, variable, options: list) -> None:
        row = tk.Frame(master, bg=UI["panel"])
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, bg=UI["panel"], fg=UI["text"], width=18, anchor="w").pack(side="left")
        menu = tk.OptionMenu(row, variable, *options)
        menu.config(bg=UI["button"], fg=UI["text"], activebackground=UI["button_active"], relief="flat", highlightthickness=0)
        menu.pack(side="left", fill="x", expand=True)

    def _mini_option(self, master: tk.Widget, variable, options: list) -> tk.OptionMenu:
        menu = tk.OptionMenu(master, variable, *options, command=lambda _value: self.refresh_history())
        menu.config(bg=UI["button"], fg=UI["text"], activebackground=UI["button_active"], relief="flat", highlightthickness=0)
        return menu

    def _check(self, master: tk.Widget, text: str, variable: tk.BooleanVar) -> None:
        tk.Checkbutton(
            master,
            text=text,
            variable=variable,
            bg=UI["panel"],
            fg=UI["text"],
            activebackground=UI["panel"],
            activeforeground=UI["text"],
            selectcolor=UI["panel_2"],
        ).pack(anchor="w", pady=4)

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
            padx=10,
            pady=6,
        )

    def _chip(self, master: tk.Widget, text: str, state: str) -> tk.Label:
        label = tk.Label(
            master,
            text=text,
            bg=self._chip_color(state)[0],
            fg=self._chip_color(state)[1],
            font=("Arial", 8, "bold"),
            padx=8,
            pady=3,
        )
        return label

    def _set_chip(self, label: tk.Label, text: str, state: str) -> None:
        bg, fg = self._chip_color(state)
        label.config(text=text, bg=bg, fg=fg)

    @staticmethod
    def _chip_color(state: str) -> tuple[str, str]:
        if state == "ok":
            return "#173524", "#68d391"
        if state == "error":
            return "#3a1820", "#f38ba8"
        return "#3a2d17", "#f6c177"

    def _text(self, master: tk.Widget, text: str, height: int) -> tk.Text:
        widget = tk.Text(master, bg="#0d0f12", fg=UI["text"], relief="flat", wrap="word", height=height, padx=9, pady=8)
        widget.insert("end", text)
        widget.config(state="disabled")
        return widget

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.config(state="disabled")

    @staticmethod
    def _style() -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=UI["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background=UI["button"], foreground=UI["text"], padding=(9, 5))
        style.configure("Treeview", background="#0d0f12", foreground=UI["text"], fieldbackground="#0d0f12")
        style.configure("Treeview.Heading", background=UI["button"], foreground=UI["text"])
