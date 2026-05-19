"""Memory — SQLite-backed persistent storage for executions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


class MemoryStore:
    """Lightweight SQLite store for execution traces and reports."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path or settings.db_path or "trademind.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._migrate()
        return self._conn

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS executions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                query       TEXT NOT NULL,
                symbol      TEXT,
                intent      TEXT,
                report      TEXT,
                confidence  REAL,
                bias        TEXT,
                duration_ms REAL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS screenshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER REFERENCES executions(id),
                symbol      TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_exec_symbol
                ON executions(symbol);
            CREATE INDEX IF NOT EXISTS idx_exec_created
                ON executions(created_at DESC);
            """
        )
        self.conn.commit()

    def save_execution(
        self,
        query: str,
        symbol: str | None = None,
        intent: dict[str, Any] | None = None,
        report: dict[str, Any] | None = None,
        confidence: float = 0.0,
        bias: str = "neutral",
        duration_ms: float = 0.0,
    ) -> int:
        """Insert an execution record and return its ID."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO executions (query, symbol, intent, report, confidence, bias, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                symbol,
                json.dumps(intent) if intent else None,
                json.dumps(report) if report else None,
                confidence,
                bias,
                duration_ms,
                now,
            ),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent executions."""
        rows = self.conn.execute(
            "SELECT * FROM executions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_by_symbol(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return executions for a specific symbol."""
        rows = self.conn.execute(
            "SELECT * FROM executions WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
            (symbol.upper(), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
