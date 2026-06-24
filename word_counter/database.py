"""
Data layer for WordCounter app.
Handles SQLite storage and JSON backups.
Supports multiple projects with per-project entries and baselines.
"""

import csv
import json
import logging
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


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


def get_settings_path() -> Path:
    """Return the path to the settings JSON file."""
    return get_app_data_dir() / "settings.json"


def load_settings() -> dict:
    """Load settings from the settings file. Returns empty dict if not found."""
    try:
        path = get_settings_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
    return {}


def save_settings(settings: dict):
    """Save settings to the settings file."""
    try:
        path = get_settings_path()
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        os.replace(str(tmp), str(path))
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")


class Database:
    """SQLite database for writing entries with multi-project support."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = get_app_data_dir() / "wordcounter.db"
        self.db_path = db_path
        self._init_db()
        self._backup_to_json()

    def _connect(self) -> sqlite3.Connection:
        """Create a connection with foreign keys and WAL mode enabled."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self):
        try:
            with self._connect() as conn:
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
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    # ── Project CRUD ──────────────────────────────────────────

    def create_project(self, name: str, baseline_word_count: int = 0) -> dict:
        """Create a new project and return it as a dict."""
        created_at = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO projects (name, created_at, baseline_word_count) VALUES (?, ?, ?)",
                    (name, created_at, baseline_word_count),
                )
                project_id = cursor.lastrowid
                conn.commit()
            self._backup_to_json()
            return {"id": project_id, "name": name, "created_at": created_at, "baseline_word_count": baseline_word_count}
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise

    def get_all_projects(self) -> list[dict]:
        """Return all projects ordered by most recently active."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT p.id, p.name, p.created_at, p.baseline_word_count,
                           (SELECT MAX(timestamp) FROM entries WHERE project_id = p.id) as last_entry,
                           (SELECT COALESCE(SUM(word_count), 0) FROM entries WHERE project_id = p.id) as total_written,
                           (SELECT COUNT(*) FROM entries WHERE project_id = p.id) as entry_count,
                           (SELECT COALESCE(SUM(word_count), 0) FROM entries WHERE project_id = p.id AND date(timestamp) = date('now')) as today_words
                    FROM projects p
                    ORDER BY last_entry DESC, p.created_at DESC
                """).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            return []

    def get_project(self, project_id: int) -> dict | None:
        """Return a single project by ID."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT id, name, created_at, baseline_word_count FROM projects WHERE id = ?",
                    (project_id,),
                ).fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            return None

    def delete_project(self, project_id: int):
        """Delete a project and all its entries."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM entries WHERE project_id = ?", (project_id,))
                conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                conn.commit()
            self._backup_to_json()
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            raise

    def update_project(self, project_id: int, name: str = None, baseline_word_count: int = None):
        """Update a project's name and/or baseline."""
        try:
            with self._connect() as conn:
                if name is not None:
                    conn.execute("UPDATE projects SET name = ? WHERE id = ?", (name, project_id))
                if baseline_word_count is not None:
                    conn.execute(
                        "UPDATE projects SET baseline_word_count = ? WHERE id = ?",
                        (baseline_word_count, project_id),
                    )
                conn.commit()
            self._backup_to_json()
        except Exception as e:
            logger.error(f"Failed to update project {project_id}: {e}")
            raise

    # ── Entry CRUD (scoped to project) ────────────────────────

    def add_entry(self, project_id: int, word_count: int, note: str = "") -> dict:
        """Add a new entry to a project and return it as a dict."""
        timestamp = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO entries (project_id, timestamp, word_count, note) VALUES (?, ?, ?, ?)",
                    (project_id, timestamp, word_count, note),
                )
                entry_id = cursor.lastrowid
                conn.commit()
            entry = {"id": entry_id, "project_id": project_id, "timestamp": timestamp, "word_count": word_count, "note": note}
            self._backup_to_json()
            return entry
        except Exception as e:
            logger.error(f"Failed to add entry: {e}")
            raise

    def get_all_entries(self, project_id: int) -> list[dict]:
        """Return all entries for a project ordered by timestamp ascending."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, timestamp, word_count, note FROM entries WHERE project_id = ? ORDER BY timestamp ASC",
                    (project_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get entries for project {project_id}: {e}")
            return []

    def get_entries_since(self, project_id: int, since: datetime) -> list[dict]:
        """Return entries for a project since the given datetime, ordered ascending."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, timestamp, word_count, note FROM entries WHERE project_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                    (project_id, since.isoformat()),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get entries since {since}: {e}")
            return []

    def get_today_entries(self, project_id: int) -> list[dict]:
        """Return today's entries for a project."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_entries_since(project_id, today_start)

    def delete_entry(self, entry_id: int):
        """Delete an entry by ID."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
                conn.commit()
            self._backup_to_json()
        except Exception as e:
            logger.error(f"Failed to delete entry {entry_id}: {e}")
            raise

    def update_entry(self, entry_id: int, word_count: int, note: str = ""):
        """Update an existing entry's word count and note."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE entries SET word_count = ?, note = ? WHERE id = ?",
                    (word_count, note, entry_id),
                )
                conn.commit()
            self._backup_to_json()
        except Exception as e:
            logger.error(f"Failed to update entry {entry_id}: {e}")
            raise

    def clear_all(self, project_id: int):
        """Delete all entries for a project (keeps the project itself)."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM entries WHERE project_id = ?", (project_id,))
                conn.commit()
            self._backup_to_json()
        except Exception as e:
            logger.error(f"Failed to clear entries for project {project_id}: {e}")
            raise

    # ── Backup ────────────────────────────────────────────────

    def _backup_to_json(self):
        """Export all data (projects + entries) to JSON backup files.

        Backs up to the default backup directory and, if a custom backup
        location is configured in settings, also copies there.
        """
        try:
            projects = self.get_all_projects()
            all_data = []
            for p in projects:
                entries = self.get_all_entries(p["id"])
                all_data.append({
                    "id": p["id"],
                    "name": p["name"],
                    "created_at": p["created_at"],
                    "baseline_word_count": p["baseline_word_count"],
                    "entries": [
                        {"id": e["id"], "timestamp": e["timestamp"], "word_count": e["word_count"], "note": e.get("note", "")}
                        for e in entries
                    ],
                })

            backup_dir = get_backup_dir()

            # Write to temp file first, then rename (atomic on same filesystem)
            latest_path = backup_dir / "latest_backup.json"
            tmp_path = backup_dir / "latest_backup.json.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            os.replace(str(tmp_path), str(latest_path))

            timestamped_path = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            tmp_ts = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.tmp"
            with open(tmp_ts, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            os.replace(str(tmp_ts), str(timestamped_path))

            backups = sorted(backup_dir.glob("backup_*.json"))
            if len(backups) > 10:
                for old in backups[:-10]:
                    old.unlink()

            # Also copy to custom backup location if configured
            settings = load_settings()
            custom_dir = settings.get("custom_backup_dir")
            if custom_dir:
                custom_path = Path(custom_dir)
                custom_path.mkdir(parents=True, exist_ok=True)
                custom_latest = custom_path / "wordcounter_latest_backup.json"
                with open(custom_latest, "w", encoding="utf-8") as f:
                    json.dump(all_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Backup failed: {e}")

    def export_to_json(self, file_path: str) -> bool:
        """Export all data to a user-chosen JSON file. Returns True on success."""
        try:
            projects = self.get_all_projects()
            all_data = []
            for p in projects:
                entries = self.get_all_entries(p["id"])
                all_data.append({
                    "name": p["name"],
                    "created_at": p["created_at"],
                    "baseline_word_count": p["baseline_word_count"],
                    "entries": [
                        {"timestamp": e["timestamp"], "word_count": e["word_count"], "note": e.get("note", "")}
                        for e in entries
                    ],
                })
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False

    def export_to_csv(self, file_path: str) -> bool:
        """Export all entries across all projects to a CSV file. Returns True on success."""
        try:
            projects = self.get_all_projects()
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Project", "Timestamp", "Word Count", "Note"])
                for p in projects:
                    entries = self.get_all_entries(p["id"])
                    for e in entries:
                        writer.writerow([
                            p["name"],
                            e["timestamp"],
                            e["word_count"],
                            e.get("note", ""),
                        ])
            return True
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False

    def import_from_json(self, file_path: str, replace: bool = False) -> tuple[bool, str]:
        """Import data from a JSON file.

        If replace=True, all existing data is wiped first.
        If replace=False, imported projects are merged (matched by name).

        Returns (success, message describing what happened).
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                return False, "Invalid file format: expected a list of projects."

            if replace:
                # Wipe all existing data
                with self._connect() as conn:
                    conn.execute("DELETE FROM entries")
                    conn.execute("DELETE FROM projects")
                    conn.commit()

            existing_projects = {p["name"]: p["id"] for p in self.get_all_projects()}
            projects_added = 0
            projects_merged = 0
            entries_added = 0

            for proj_data in data:
                name = proj_data.get("name", "Imported Project")
                baseline = proj_data.get("baseline_word_count", 0)
                created_at = proj_data.get("created_at", datetime.now().isoformat())
                entries = proj_data.get("entries", [])

                if name in existing_projects and not replace:
                    # Merge: add entries to existing project
                    project_id = existing_projects[name]
                    projects_merged += 1
                else:
                    # Create new project
                    with self._connect() as conn:
                        cursor = conn.execute(
                            "INSERT INTO projects (name, created_at, baseline_word_count) VALUES (?, ?, ?)",
                            (name, created_at, baseline),
                        )
                        project_id = cursor.lastrowid
                        conn.commit()
                    existing_projects[name] = project_id
                    projects_added += 1

                # Import entries (skip duplicates by timestamp)
                existing_entries = self.get_all_entries(project_id)
                existing_timestamps = {e["timestamp"] for e in existing_entries}

                for entry in entries:
                    ts = entry.get("timestamp", "")
                    wc = entry.get("word_count", 0)
                    note = entry.get("note", "")
                    if ts and ts not in existing_timestamps:
                        with self._connect() as conn:
                            conn.execute(
                                "INSERT INTO entries (project_id, timestamp, word_count, note) VALUES (?, ?, ?, ?)",
                                (project_id, ts, wc, note),
                            )
                            conn.commit()
                        entries_added += 1
                        existing_timestamps.add(ts)

            self._backup_to_json()

            parts = []
            if projects_added:
                parts.append(f"{projects_added} new project(s)")
            if projects_merged:
                parts.append(f"{projects_merged} project(s) merged")
            parts.append(f"{entries_added} entries imported")
            msg = ", ".join(parts)
            if not entries_added and not projects_added:
                msg = "No new data to import (everything already exists)."
            return True, msg
        except json.JSONDecodeError:
            return False, "Invalid JSON file. Could not parse."
        except Exception as e:
            logger.error(f"JSON import failed: {e}")
            return False, f"Import failed: {e}"

    # ── Stats (scoped to project) ─────────────────────────────

    def get_daily_totals(self, project_id: int, days: int = 7) -> list[dict]:
        """Return daily word totals for the past N days for a project."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=days - 1)
        result = []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT timestamp, word_count FROM entries WHERE project_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                    (project_id, start.isoformat()),
                ).fetchall()
            # Build a dict of date -> total
            daily_map = {}
            for ts_str, wc in rows:
                try:
                    dt = datetime.fromisoformat(ts_str)
                    date_key = dt.strftime("%Y-%m-%d")
                    daily_map[date_key] = daily_map.get(date_key, 0) + wc
                except (ValueError, TypeError):
                    continue
            for i in range(days - 1, -1, -1):
                day = today - timedelta(days=i)
                date_key = day.strftime("%Y-%m-%d")
                result.append({"date": date_key, "total": daily_map.get(date_key, 0)})
        except Exception as e:
            logger.error(f"Failed to get daily totals: {e}")
            for i in range(days - 1, -1, -1):
                day = today - timedelta(days=i)
                result.append({"date": day.strftime("%Y-%m-%d"), "total": 0})
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
