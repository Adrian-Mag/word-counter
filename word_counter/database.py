"""
Data layer for WordCounter app.
Handles SQLite storage and JSON backups.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def get_app_data_dir() -> Path:
    """Return the directory where app data is stored, creating it if needed."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / "WordCounter"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_backup_dir() -> Path:
    """Return the backup directory, creating it if needed."""
    backup_dir = get_app_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


class Database:
    """SQLite database for writing entries."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = get_app_data_dir() / "wordcounter.db"
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    note TEXT
                )
            """)
            conn.commit()

    def add_entry(self, word_count: int, note: str = "") -> dict:
        """Add a new entry and return it as a dict. Also triggers JSON backup."""
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO entries (timestamp, word_count, note) VALUES (?, ?, ?)",
                (timestamp, word_count, note),
            )
            entry_id = cursor.lastrowid
            conn.commit()
        entry = {"id": entry_id, "timestamp": timestamp, "word_count": word_count, "note": note}
        self._backup_to_json()
        return entry

    def get_all_entries(self) -> list[dict]:
        """Return all entries ordered by timestamp ascending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, timestamp, word_count, note FROM entries ORDER BY timestamp ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_entries_since(self, since: datetime) -> list[dict]:
        """Return entries since the given datetime, ordered ascending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, timestamp, word_count, note FROM entries WHERE timestamp >= ? ORDER BY timestamp ASC",
                (since.isoformat(),),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_today_entries(self) -> list[dict]:
        """Return today's entries."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_entries_since(today_start)

    def delete_entry(self, entry_id: int):
        """Delete an entry by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            conn.commit()
        self._backup_to_json()

    def _backup_to_json(self):
        """Export all entries to a JSON backup file."""
        entries = self.get_all_entries()
        backup_dir = get_backup_dir()
        # Keep a rolling backup: latest.json + timestamped backups (keep last 10)
        latest_path = backup_dir / "latest_backup.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

        timestamped_path = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(timestamped_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

        # Clean up old timestamped backups (keep last 10)
        backups = sorted(backup_dir.glob("backup_*.json"))
        if len(backups) > 10:
            for old in backups[:-10]:
                old.unlink()

    def restore_from_json(self, json_path: Path) -> int:
        """Restore entries from a JSON backup file. Returns count of restored entries."""
        with open(json_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM entries")
            for entry in entries:
                conn.execute(
                    "INSERT INTO entries (id, timestamp, word_count, note) VALUES (?, ?, ?, ?)",
                    (entry["id"], entry["timestamp"], entry["word_count"], entry.get("note", "")),
                )
            conn.commit()
        return len(entries)

    def get_daily_totals(self, days: int = 7) -> list[dict]:
        """Return daily word totals for the past N days (including today).
        Each dict has 'date' (YYYY-MM-DD) and 'total' (int)."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            day_end = day + timedelta(days=1)
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(word_count), 0) FROM entries WHERE timestamp >= ? AND timestamp < ?",
                    (day.isoformat(), day_end.isoformat()),
                ).fetchone()
            result.append({"date": day.strftime("%Y-%m-%d"), "total": row[0]})
        return result

    def get_stats(self, days: int = 7) -> dict:
        """Return summary statistics for the past N days."""
        daily = self.get_daily_totals(days)
        totals = [d["total"] for d in daily]
        all_entries = self.get_all_entries()
        total_words = sum(e["word_count"] for e in all_entries)

        # Compute streak (consecutive days with > 0 words, ending today or yesterday)
        streak = 0
        for d in reversed(daily):
            if d["total"] > 0:
                streak += 1
            else:
                break

        # Best day in this period
        best_day = max(daily, key=lambda x: x["total"]) if daily else None

        return {
            "period_days": days,
            "total_words_period": sum(totals),
            "avg_per_day": sum(totals) / days if days > 0 else 0,
            "best_day": best_day,
            "current_streak": streak,
            "total_words_all_time": total_words,
            "total_entries": len(all_entries),
            "daily_totals": daily,
        }
