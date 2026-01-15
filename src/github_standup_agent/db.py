"""SQLite database for storing standup history."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from github_standup_agent.config import CONFIG_DIR, DB_FILE


class StandupDatabase:
    """SQLite database for persisting standup history."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS standups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                summary TEXT NOT NULL,
                raw_data TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def save(
        self,
        summary: str,
        raw_data: Optional[dict[str, Any]] = None,
        date: Optional[str] = None,
    ) -> None:
        """Save a standup to the database."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Upsert - update if exists, insert if not
        cursor.execute("""
            INSERT INTO standups (date, summary, raw_data, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                summary = excluded.summary,
                raw_data = excluded.raw_data,
                created_at = excluded.created_at
        """, (
            date,
            summary,
            json.dumps(raw_data) if raw_data else None,
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_by_date(self, date: str) -> Optional[dict[str, Any]]:
        """Get a standup by date."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM standups WHERE date = ?",
            (date,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row["id"],
                "date": row["date"],
                "summary": row["summary"],
                "raw_data": json.loads(row["raw_data"]) if row["raw_data"] else None,
                "created_at": row["created_at"],
            }
        return None

    def get_recent(self, limit: int = 7) -> list[dict[str, Any]]:
        """Get recent standups."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM standups ORDER BY date DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row["id"],
                "date": row["date"],
                "summary": row["summary"],
                "raw_data": json.loads(row["raw_data"]) if row["raw_data"] else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def clear_old(self, days_to_keep: int = 30) -> int:
        """Clear standups older than the specified number of days."""
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM standups WHERE date < ?", (cutoff,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted

    def clear_all(self) -> None:
        """Clear all standups."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM standups")
        conn.commit()
        conn.close()
