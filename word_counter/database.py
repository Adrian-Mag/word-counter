"""
Data layer for WordCounter app.
Handles SQLite storage and JSON backups.
Supports multiple projects with per-project entries and baselines.
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
    """SQLite database for writing entries with multi-project support."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = get_app_data_dir() / "wordcounter.db"
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Create projects table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    baseline_word_count INTEGER NOT NULL DEFAULT 0
                )
            """)

            # Create entries table (with project_id)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    note TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

            # Migration: if entries table exists without project_id, add it
            columns = [row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()]
            if "project_id" not in columns:
                # Create a default project for existing entries
                cursor = conn.execute(
                    "INSERT INTO projects (name, created_at, baseline_word_count) VALUES (?, ?, ?)",
                    ("My Writing Project", datetime.now().isoformat(), 0),
                )
                default_project_id = cursor.lastrowid
                conn.execute(f"ALTER TABLE entries ADD COLUMN project_id INTEGER DEFAULT {default_project_id}")
                conn.execute("UPDATE entries SET project_id = ?", (default_project_id,))

            conn.commit()

    # ── Project CRUD ──────────────────────────────────────────

    def create_project(self, name: str, baseline_word_count: int = 0) -> dict:
        """Create a new project and return it as a dict."""
        created_at = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO projects (name, created_at, baseline_word_count) VALUES (?, ?, ?)",
                (name, created_at, baseline_word_count),
            )
            project_id = cursor.lastrowid
            conn.commit()
        self._backup_to_json()
        return {"id": project_id, "name": name, "created_at": created_at, "baseline_word_count": baseline_word_count}

    def get_all_projects(self) -> list[dict]:
        """Return all projects ordered by most recently active."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT p.id, p.name, p.created_at, p.baseline_word_count,
                       (SELECT MAX(timestamp) FROM entries WHERE project_id = p.id) as last_entry,
                       (SELECT COALESCE(SUM(word_count), 0) FROM entries WHERE project_id = p.id) as total_written,
                       (SELECT COUNT(*) FROM entries WHERE project_id = p.id) as entry_count
                FROM projects p
                ORDER BY last_entry DESC, p.created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_project(self, project_id: int) -> dict | None:
        """Return a single project by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, name, created_at, baseline_word_count FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            return dict(row) if row else None

    def delete_project(self, project_id: int):
        """Delete a project and all its entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM entries WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
        self._backup_to_json()

    def update_project(self, project_id: int, name: str = None, baseline_word_count: int = None):
        """Update a project's name and/or baseline."""
        with sqlite3.connect(self.db_path) as conn:
            if name is not None:
                conn.execute("UPDATE projects SET name = ? WHERE id = ?", (name, project_id))
            if baseline_word_count is not None:
                conn.execute(
                    "UPDATE projects SET baseline_word_count = ? WHERE id = ?",
                    (baseline_word_count, project_id),
                )
            conn.commit()
        self._backup_to_json()

    # ── Entry CRUD (scoped to project) ────────────────────────

    def add_entry(self, project_id: int, word_count: int, note: str = "") -> dict:
        """Add a new entry to a project and return it as a dict."""
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO entries (project_id, timestamp, word_count, note) VALUES (?, ?, ?, ?)",
                (project_id, timestamp, word_count, note),
            )
            entry_id = cursor.lastrowid
            conn.commit()
        entry = {"id": entry_id, "project_id": project_id, "timestamp": timestamp, "word_count": word_count, "note": note}
        self._backup_to_json()
        return entry

    def get_all_entries(self, project_id: int) -> list[dict]:
        """Return all entries for a project ordered by timestamp ascending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, timestamp, word_count, note FROM entries WHERE project_id = ? ORDER BY timestamp ASC",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_entries_since(self, project_id: int, since: datetime) -> list[dict]:
        """Return entries for a project since the given datetime, ordered ascending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, timestamp, word_count, note FROM entries WHERE project_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (project_id, since.isoformat()),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_today_entries(self, project_id: int) -> list[dict]:
        """Return today's entries for a project."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_entries_since(project_id, today_start)

    def delete_entry(self, entry_id: int):
        """Delete an entry by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            conn.commit()
        self._backup_to_json()

    def update_entry(self, entry_id: int, word_count: int, note: str = ""):
        """Update an existing entry's word count and note."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE entries SET word_count = ?, note = ? WHERE id = ?",
                (word_count, note, entry_id),
            )
            conn.commit()
        self._backup_to_json()

    def clear_all(self, project_id: int):
        """Delete all entries for a project (keeps the project itself)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM entries WHERE project_id = ?", (project_id,))
            conn.commit()
        self._backup_to_json()

    # ── Backup ────────────────────────────────────────────────

    def _backup_to_json(self):
        """Export all data to a JSON backup file."""
        projects = self.get_all_projects()
        backup_dir = get_backup_dir()
        latest_path = backup_dir / "latest_backup.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)

        timestamped_path = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(timestamped_path, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)

        backups = sorted(backup_dir.glob("backup_*.json"))
        if len(backups) > 10:
            for old in backups[:-10]:
                old.unlink()

    # ── Stats (scoped to project) ─────────────────────────────

    def get_daily_totals(self, project_id: int, days: int = 7) -> list[dict]:
        """Return daily word totals for the past N days for a project."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            day_end = day + timedelta(days=1)
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(word_count), 0) FROM entries WHERE project_id = ? AND timestamp >= ? AND timestamp < ?",
                    (project_id, day.isoformat(), day_end.isoformat()),
                ).fetchone()
            result.append({"date": day.strftime("%Y-%m-%d"), "total": row[0]})
        return result

    def get_stats(self, project_id: int, days: int = 7) -> dict:
        """Return summary statistics for the past N days for a project."""
        daily = self.get_daily_totals(project_id, days)
        totals = [d["total"] for d in daily]
        all_entries = self.get_all_entries(project_id)
        total_written = sum(e["word_count"] for e in all_entries)

        project = self.get_project(project_id)
        baseline = project["baseline_word_count"] if project else 0
        total_with_baseline = baseline + total_written

        streak = 0
        for d in reversed(daily):
            if d["total"] > 0:
                streak += 1
            else:
                break

        best_day = max(daily, key=lambda x: x["total"]) if daily else None

        return {
            "period_days": days,
            "total_words_period": sum(totals),
            "avg_per_day": sum(totals) / days if days > 0 else 0,
            "best_day": best_day,
            "current_streak": streak,
            "total_written": total_written,
            "total_with_baseline": total_with_baseline,
            "baseline": baseline,
            "total_entries": len(all_entries),
            "daily_totals": daily,
        }
