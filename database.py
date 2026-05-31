"""SQLite persistence for Moodler history and learning data."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from config import APPDATA_DIR, DATABASE_PATH
from models.task_result import Flashcard, TaskResult


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    detected_task TEXT,
                    short_answer TEXT,
                    full_answer TEXT,
                    confidence REAL NOT NULL DEFAULT 0,
                    explanation TEXT,
                    warnings TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT 'unknown',
                    provider TEXT NOT NULL DEFAULT 'unknown',
                    model TEXT NOT NULL DEFAULT '',
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0,
                    provider_mode TEXT NOT NULL DEFAULT '',
                    fallback_used INTEGER NOT NULL DEFAULT 0,
                    copied_value TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    marked_wrong INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._ensure_history_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    history_id INTEGER,
                    front TEXT NOT NULL,
                    back TEXT NOT NULL,
                    subject TEXT NOT NULL DEFAULT 'unknown',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    marked_wrong INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(history_id) REFERENCES history(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    flashcard_id INTEGER,
                    history_id INTEGER,
                    correct INTEGER NOT NULL,
                    note TEXT,
                    FOREIGN KEY(flashcard_id) REFERENCES flashcards(id),
                    FOREIGN KEY(history_id) REFERENCES history(id)
                )
                """
            )

    def insert_history(self, result: TaskResult, source: str) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO history (
                    created_at, task_type, language, subject, detected_task,
                    short_answer, full_answer, confidence, explanation,
                    warnings, source, provider, model, input_tokens, output_tokens,
                    total_tokens, estimated_cost_usd, provider_mode, fallback_used,
                    copied_value, favorite, marked_wrong
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    result.task_type,
                    result.language,
                    result.subject,
                    result.detected_task,
                    result.short_answer,
                    result.full_answer,
                    result.confidence,
                    result.explanation,
                    json.dumps(result.warnings, ensure_ascii=False),
                    source,
                    result.provider,
                    result.model,
                    int(result.input_tokens),
                    int(result.output_tokens),
                    int(result.total_tokens),
                    float(result.estimated_cost_usd),
                    result.provider_mode,
                    int(result.fallback_used),
                    result.copied_value,
                    int(result.favorite),
                    int(result.marked_wrong),
                ),
            )
            history_id = int(cursor.lastrowid)
        result.id = history_id
        result.created_at = now
        return history_id

    def list_history(self, filter_name: str = "all", limit: int = 300) -> list[TaskResult]:
        where = ""
        params: list[Any] = []
        if filter_name == "favorites":
            where = "WHERE favorite = 1"
        elif filter_name == "uncertain":
            where = "WHERE confidence < ? OR warnings != '[]'"
            params.append(0.65)
        elif filter_name == "wrong":
            where = "WHERE marked_wrong = 1"

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM history {where} ORDER BY datetime(created_at) DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_history(self, history_id: int) -> TaskResult | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM history WHERE id = ?", (history_id,)).fetchone()
        return self._row_to_result(row) if row else None

    def set_history_favorite(self, history_id: int, favorite: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE history SET favorite = ? WHERE id = ?", (int(favorite), history_id))

    def set_history_wrong(self, history_id: int, marked_wrong: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE history SET marked_wrong = ? WHERE id = ?", (int(marked_wrong), history_id))

    def delete_history(self, history_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM quiz_attempts WHERE history_id = ?", (history_id,))
            conn.execute("DELETE FROM flashcards WHERE history_id = ?", (history_id,))
            conn.execute("DELETE FROM history WHERE id = ?", (history_id,))

    def delete_all_history(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM quiz_attempts")
            conn.execute("DELETE FROM flashcards")
            conn.execute("DELETE FROM history")

    def reset_costs(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE history
                SET input_tokens = 0,
                    output_tokens = 0,
                    total_tokens = 0,
                    estimated_cost_usd = 0,
                    fallback_used = 0
                """
            )

    def cost_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd,
                    COUNT(*) AS request_count
                FROM history
                """
            ).fetchone()
            last = conn.execute(
                """
                SELECT provider, model, input_tokens, output_tokens, total_tokens,
                       estimated_cost_usd, provider_mode, fallback_used, copied_value
                FROM history
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """
            ).fetchone()
        summary = dict(row) if row is not None else {}
        summary["last"] = dict(last) if last is not None else None
        return summary

    def insert_flashcards(self, cards: list[Flashcard], subject: str = "unknown", history_id: int | None = None) -> int:
        if not cards:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO flashcards (created_at, history_id, front, back, subject)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(now, history_id, card.front, card.back, subject) for card in cards],
            )
        return len(cards)

    def list_flashcards(self, filter_name: str = "all", limit: int = 500) -> list[dict[str, Any]]:
        where = ""
        if filter_name == "favorites":
            where = "WHERE favorite = 1"
        elif filter_name == "wrong":
            where = "WHERE marked_wrong = 1"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM flashcards {where} ORDER BY datetime(created_at) DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_flashcard_wrong(self, flashcard_id: int, marked_wrong: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE flashcards SET marked_wrong = ? WHERE id = ?", (int(marked_wrong), flashcard_id))

    def ping(self) -> bool:
        with self._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True

    def record_quiz_attempt(
        self,
        correct: bool,
        flashcard_id: int | None = None,
        history_id: int | None = None,
        note: str = "",
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO quiz_attempts (created_at, flashcard_id, history_id, correct, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, flashcard_id, history_id, int(correct), note),
            )

    @staticmethod
    def _row_to_result(row: sqlite3.Row) -> TaskResult:
        warnings = json.loads(row["warnings"] or "[]")
        result = TaskResult(
            task_type=row["task_type"],
            language=row["language"],
            subject=row["subject"],
            detected_task=row["detected_task"] or "",
            short_answer=row["short_answer"] or "",
            full_answer=row["full_answer"] or "",
            confidence=float(row["confidence"] or 0),
            explanation=row["explanation"] or "",
            warnings=warnings if isinstance(warnings, list) else [],
            source=row["source"] or "unknown",
            provider=row["provider"] or "unknown",
            model=row["model"] or "",
            input_tokens=int(row["input_tokens"] or 0),
            output_tokens=int(row["output_tokens"] or 0),
            total_tokens=int(row["total_tokens"] or 0),
            estimated_cost_usd=float(row["estimated_cost_usd"] or 0),
            provider_mode=row["provider_mode"] or "",
            fallback_used=bool(row["fallback_used"]),
            copied_value=row["copied_value"] or "",
            id=int(row["id"]),
            created_at=row["created_at"],
            favorite=bool(row["favorite"]),
            marked_wrong=bool(row["marked_wrong"]),
        )
        return result

    @staticmethod
    def _ensure_history_columns(conn: sqlite3.Connection) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(history)").fetchall()}
        columns = {
            "provider": "TEXT NOT NULL DEFAULT 'unknown'",
            "model": "TEXT NOT NULL DEFAULT ''",
            "input_tokens": "INTEGER NOT NULL DEFAULT 0",
            "output_tokens": "INTEGER NOT NULL DEFAULT 0",
            "total_tokens": "INTEGER NOT NULL DEFAULT 0",
            "estimated_cost_usd": "REAL NOT NULL DEFAULT 0",
            "provider_mode": "TEXT NOT NULL DEFAULT ''",
            "fallback_used": "INTEGER NOT NULL DEFAULT 0",
            "copied_value": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE history ADD COLUMN {name} {definition}")
