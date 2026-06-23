"""
Project window for WordCounter app.
Shows word entry, summary, and navigation to stats/history for a single project.
"""

from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .history_window import HistoryWindow
from .stats_window import StatsWindow
from .update_checker import check_for_update, download_update, install_update, get_current_version


class EditProjectDialog(QDialog):
    """Dialog for editing a project's name and baseline."""

    def __init__(self, project: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Project")
        self.setMinimumWidth(400)
        self.setStyleSheet("background-color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("✏️ Edit Project")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Project name:"))
        self.name_input = QLineEdit(project["name"])
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus { border-color: #5B9BD5; }
        """)
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Baseline word count:"))
        baseline_help = QLabel("This is your starting point. It won't affect stats like averages or streaks, but you'll see a 'total including baseline' alongside your written words.")
        baseline_help.setStyleSheet("color: #999; font-size: 10px;")
        baseline_help.setWordWrap(True)
        layout.addWidget(baseline_help)

        self.baseline_input = QLineEdit(str(project.get("baseline_word_count", 0)))
        self.baseline_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus { border-color: #5B9BD5; }
        """)
        layout.addWidget(self.baseline_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px; border: 1px solid #ccc;
                border-radius: 8px; font-size: 13px;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #5B9BD5; color: white;
                border: none; border-radius: 8px;
                padding: 10px 20px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4A8AC5; }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a project name.")
            return
        try:
            baseline = int(self.baseline_input.text().strip() or "0")
            if baseline < 0:
                QMessageBox.warning(self, "Invalid", "Baseline cannot be negative.")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Please enter a valid number for the baseline.")
            return
        self.accept()

    def get_values(self) -> tuple[str, int]:
        return self.name_input.text().strip(), int(self.baseline_input.text().strip() or "0")


class SummaryCard(QFrame):
    """A card showing a summary statistic."""

    def __init__(self, title: str, value: str, color: str = "#5B9BD5"):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            SummaryCard {{
                background-color: {color}15;
                border: 1px solid {color}30;
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: #2c3e50; font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label)


class ProjectWindow(QMainWindow):
    """Main window when inside a project — word entry, summary, stats, history."""

    def __init__(self, db: Database, project_id: int, on_back=None):
        super().__init__()
        self.db = db
        self.project_id = project_id
        self.on_back = on_back
        self.stats_window: StatsWindow | None = None
        self.history_window: HistoryWindow | None = None

        project = db.get_project(project_id)
        self.project_name = project["name"] if project else "Project"
        self.setWindowTitle(f"Word Counter ✍️ — {self.project_name}")
        self.setMinimumSize(450, 580)
        self.setStyleSheet("QMainWindow { background-color: #ffffff; }")

        self._build_ui()
        self.refresh_summary()
        QTimer.singleShot(2000, self._check_for_updates)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Top bar: back button + project name
        top_bar = QHBoxLayout()
        back_btn = QPushButton("← All Projects")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #666;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        back_btn.clicked.connect(self._go_back)
        top_bar.addWidget(back_btn)
        top_bar.addStretch()

        delete_btn = QPushButton("🗑 Delete Project")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #e74c3c;
                border: 1px solid #e74c3c;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #e74c3c10; }
        """)
        edit_btn = QPushButton("✏️ Edit Project")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #5B9BD5;
                border: 1px solid #5B9BD5;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #5B9BD510; }
        """)
        edit_btn.clicked.connect(self._on_edit_project)
        top_bar.addWidget(edit_btn)

        delete_btn = QPushButton("🗑 Delete Project")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #e74c3c;
                border: 1px solid #e74c3c;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #e74c3c10; }
        """)
        delete_btn.clicked.connect(self._on_delete_project)
        top_bar.addWidget(delete_btn)
        layout.addLayout(top_bar)

        # Title
        title = QLabel(f"✍️ {self.project_name}")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        # Input section
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(20, 20, 20, 20)
        input_layout.setSpacing(10)

        input_label = QLabel("How many words did you write? (use negative for editing)")
        input_label.setStyleSheet("font-size: 13px; color: #666;")
        input_layout.addWidget(input_label)

        input_row = QHBoxLayout()
        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("Enter word count (e.g. 500 or -100 for editing)...")
        self.word_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
            }
            QLineEdit:focus {
                border-color: #5B9BD5;
            }
        """)
        self.word_input.returnPressed.connect(self._on_add_entry)
        input_row.addWidget(self.word_input, stretch=1)

        add_btn = QPushButton("Log Words")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #5B9BD5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4A8AC5;
            }
            QPushButton:pressed {
                background-color: #3A7AB5;
            }
        """)
        add_btn.clicked.connect(self._on_add_entry)
        input_row.addWidget(add_btn)
        input_layout.addLayout(input_row)

        # Optional note
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional note (e.g., 'Chapter 3 draft')...")
        self.note_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 14px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 12px;
                color: #888;
            }
            QLineEdit:focus {
                border-color: #bbb;
            }
        """)
        self.note_input.returnPressed.connect(self._on_add_entry)
        input_layout.addWidget(self.note_input)

        layout.addWidget(input_frame)

        # Summary cards
        cards_layout = QGridLayout()
        cards_layout.setSpacing(10)

        self.today_card = SummaryCard("TODAY'S WORDS", "0", "#5B9BD5")
        self.streak_card = SummaryCard("CURRENT STREAK", "0 days", "#E8743B")
        self.written_card = SummaryCard("WORDS WRITTEN", "0", "#27AE60")
        self.total_card = SummaryCard("TOTAL (INCL. BASELINE)", "0", "#8E44AD")

        cards_layout.addWidget(self.today_card, 0, 0)
        cards_layout.addWidget(self.streak_card, 0, 1)
        cards_layout.addWidget(self.written_card, 1, 0)
        cards_layout.addWidget(self.total_card, 1, 1)
        layout.addLayout(cards_layout)

        # Last entry info
        self.last_entry_label = QLabel("")
        self.last_entry_label.setStyleSheet("color: #999; font-size: 11px;")
        self.last_entry_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.last_entry_label)

        # Recent additions summary
        self.recent_label = QLabel("")
        self.recent_label.setStyleSheet("color: #aaa; font-size: 10px;")
        self.recent_label.setAlignment(Qt.AlignCenter)
        self.recent_label.setWordWrap(True)
        layout.addWidget(self.recent_label)

        layout.addStretch()

        # Stats button
        stats_btn = QPushButton("📊 View Statistics")
        stats_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #5B9BD5;
                border: 2px solid #5B9BD5;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5B9BD510;
            }
        """)
        stats_btn.clicked.connect(self._open_stats)
        layout.addWidget(stats_btn)

        # History button
        history_btn = QPushButton("📋 View History")
        history_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #8E44AD;
                border: 2px solid #8E44AD;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8E44AD10;
            }
        """)
        history_btn.clicked.connect(self._open_history)
        layout.addWidget(history_btn)

        # Version label
        version_label = QLabel(f"v{get_current_version()}")
        version_label.setStyleSheet("color: #ccc; font-size: 10px;")
        version_label.setAlignment(Qt.AlignRight)
        layout.addWidget(version_label)

    def _on_add_entry(self):
        text = self.word_input.text().strip()
        if not text:
            return
        try:
            word_count = int(text)
            if word_count == 0:
                QMessageBox.warning(self, "Invalid Input", "Please enter a non-zero number.")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")
            return

        note = self.note_input.text().strip()
        self.db.add_entry(self.project_id, word_count, note)
        self.word_input.clear()
        self.note_input.clear()
        self.word_input.setFocus()
        self.refresh_summary()

        if word_count > 0:
            self.last_entry_label.setText(f"✅ Logged +{word_count:,} words!")
        else:
            self.last_entry_label.setText(f"✏️ Logged {word_count:,} words (editing)")
        QTimer.singleShot(3000, lambda: self.refresh_summary())

    def refresh_summary(self):
        """Refresh the summary cards and last entry info."""
        today_entries = self.db.get_today_entries(self.project_id)
        today_total = sum(e["word_count"] for e in today_entries)

        all_entries = self.db.get_all_entries(self.project_id)
        total_written = sum(e["word_count"] for e in all_entries)

        project = self.db.get_project(self.project_id)
        baseline = project["baseline_word_count"] if project else 0
        total_with_baseline = baseline + total_written

        stats = self.db.get_stats(self.project_id, 7)
        streak = stats["current_streak"]

        self.today_card.layout().itemAt(1).widget().setText(f"{today_total:,}")
        self.streak_card.layout().itemAt(1).widget().setText(f"{streak} days")
        self.written_card.layout().itemAt(1).widget().setText(f"{total_written:,}")
        self.total_card.layout().itemAt(1).widget().setText(f"{total_with_baseline:,}")

        if all_entries:
            last = all_entries[-1]
            ts = datetime.fromisoformat(last["timestamp"])
            time_str = ts.strftime("%I:%M %p on %b %d")
            sign = "+" if last["word_count"] >= 0 else ""
            self.last_entry_label.setText(f"Last entry: {sign}{last['word_count']:,} words at {time_str}")
        else:
            self.last_entry_label.setText("No entries yet — start writing! 🚀")

        if len(all_entries) >= 1:
            recent = all_entries[-3:]
            parts = []
            for e in recent:
                ts = datetime.fromisoformat(e["timestamp"])
                time_str = ts.strftime("%I:%M %p")
                sign = "+" if e["word_count"] >= 0 else ""
                note_str = f" ({e['note']})" if e.get("note") else ""
                parts.append(f"{sign}{e['word_count']:,} at {time_str}{note_str}")
            self.recent_label.setText("Recent: " + "  |  ".join(parts))
        else:
            self.recent_label.setText("")

    def _go_back(self):
        if self.on_back:
            self.close()
            self.on_back()

    def _on_edit_project(self):
        project = self.db.get_project(self.project_id)
        if not project:
            return
        dialog = EditProjectDialog(project, self)
        if dialog.exec_() == QDialog.Accepted:
            name, baseline = dialog.get_values()
            self.db.update_project(self.project_id, name=name, baseline_word_count=baseline)
            self.project_name = name
            self.setWindowTitle(f"Word Counter ✍️ — {name}")
            # Update the title label in the UI
            title_label = self.centralWidget().layout().itemAt(1).widget()
            title_label.setText(f"✍️ {name}")
            self.refresh_summary()

    def _on_delete_project(self):
        entry_count = len(self.db.get_all_entries(self.project_id))
        # First confirmation
        reply = QMessageBox.warning(
            self,
            "⚠️ Delete Project?",
            f"Are you sure you want to delete '{self.project_name}'?\n\n"
            f"This will permanently delete:\n"
            f"  • The project\n"
            f"  • All {entry_count} entries\n\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Second confirmation
        reply2 = QMessageBox.warning(
            self,
            "⚠️ Final Confirmation",
            f"Last chance! '{self.project_name}' and all its data will be gone forever.\n\n"
            f"Click 'Yes' to permanently delete everything.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply2 != QMessageBox.Yes:
            return

        self.db.delete_project(self.project_id)
        QMessageBox.information(self, "Deleted", f"Project '{self.project_name}' has been deleted.\nA backup was saved.")
        if self.on_back:
            self.close()
            self.on_back()

    def _open_stats(self):
        if self.stats_window is None or not self.stats_window.isVisible():
            self.stats_window = StatsWindow(self.db, self.project_id)
            self.stats_window.show()
            self.stats_window.activateWindow()
        else:
            self.stats_window.refresh()
            self.stats_window.activateWindow()

    def _open_history(self):
        if self.history_window is None or not self.history_window.isVisible():
            self.history_window = HistoryWindow(self.db, self.project_id, on_data_changed=self.refresh_summary)
            self.history_window.show()
            self.history_window.activateWindow()
        else:
            self.history_window.refresh()
            self.history_window.activateWindow()

    def _check_for_updates(self):
        """Check GitHub for a newer release (runs silently 2s after startup)."""
        update_info = check_for_update()
        if update_info is None:
            return

        current = get_current_version()
        latest = update_info["version"]
        reply = QMessageBox.question(
            self,
            "Update Available!",
            f"A new version is available!\n\n"
            f"Current version: v{current}\n"
            f"New version: v{latest}\n\n"
            f"Your data will be preserved.\n\n"
            f"Would you like to update now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        expected_size = update_info.get("size", 0)
        size_mb = f"({expected_size / 1024 / 1024:.1f} MB)" if expected_size else ""
        from PyQt5.QtWidgets import QProgressDialog
        progress = QProgressDialog(f"Downloading update {size_mb}...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Updating WordCounter")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setMinimumWidth(350)

        def on_progress(downloaded, total):
            percent = int((downloaded / total) * 100)
            progress.setValue(percent)
            mb_done = downloaded / 1024 / 1024
            mb_total = total / 1024 / 1024
            progress.setLabelText(f"Downloading... {mb_done:.1f} / {mb_total:.1f} MB ({percent}%)")

        try:
            new_exe = download_update(update_info["url"], expected_size, on_progress)
            progress.close()
            QMessageBox.information(
                self,
                "Update Ready",
                "The app will now restart to complete the update.\n"
                "Your data is safe!",
            )
            install_update(new_exe)
        except Exception as e:
            progress.close()
            QMessageBox.warning(
                self,
                "Update Failed",
                f"Could not download the update.\n"
                f"Please download it manually from:\n"
                f"https://github.com/Adrian-Mag/word-counter/releases\n\n"
                f"Error: {e}",
            )

    def closeEvent(self, event):
        """Close child windows when main window closes."""
        if self.stats_window:
            self.stats_window.close()
        if self.history_window:
            self.history_window.close()
        event.accept()
