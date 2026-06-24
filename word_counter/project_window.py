"""
Project page for WordCounter app.
Shows word entry, summary, and navigation to stats/history for a single project.
Designed as a page inside a QStackedWidget, not a separate window.
"""

from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .database import Database, load_settings
from .theme import get_theme, get_card_colors
from .update_checker import get_current_version


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

    def __init__(self, title: str, value: str, color: str = "#5B9BD5", dark: bool = False):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.color = color
        self.dark = dark
        bg, text_color = get_card_colors(color, dark)
        t = get_theme(dark)
        self.setStyleSheet(f"""
            SummaryCard {{
                background-color: {bg};
                border: 1px solid {color}40;
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {text_color}; font-size: 11px; font-weight: bold; background: transparent;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {t['text_primary']}; font-size: 22px; font-weight: bold; background: transparent;")
        layout.addWidget(self.value_label)

    def update_theme(self, dark: bool):
        self.dark = dark
        bg, text_color = get_card_colors(self.color, dark)
        t = get_theme(dark)
        self.setStyleSheet(f"""
            SummaryCard {{
                background-color: {bg};
                border: 1px solid {self.color}40;
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {text_color}; font-size: 11px; font-weight: bold; background: transparent;")
        self.value_label.setStyleSheet(f"color: {t['text_primary']}; font-size: 22px; font-weight: bold; background: transparent;")


class ProjectPage(QWidget):
    """Page for a single project — word entry, summary, navigation to stats/history."""

    def __init__(self, db: Database, project_id: int, on_back=None, on_stats=None, on_history=None, on_project_deleted=None, dark: bool = False):
        super().__init__()
        self.db = db
        self.project_id = project_id
        self.on_back = on_back
        self.on_stats = on_stats
        self.on_history = on_history
        self.on_project_deleted = on_project_deleted
        self.dark = dark

        project = db.get_project(project_id)
        self.project_name = project["name"] if project else "Project"
        t = get_theme(dark)
        self.setStyleSheet(f"background-color: {t['bg']};")

        self._build_ui()

    def _build_ui(self):
        t = get_theme(self.dark)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Top bar: back button + edit/delete
        top_bar = QHBoxLayout()
        back_btn = QPushButton("← All Projects")
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_bg']};
                color: {t['text_secondary']};
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {t['btn_bg_hover']}; }}
        """)
        back_btn.clicked.connect(self._go_back)
        top_bar.addWidget(back_btn)
        top_bar.addStretch()

        edit_btn = QPushButton("✏️ Edit Project")
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_outline_bg']};
                color: {t['accent']};
                border: 1px solid {t['accent']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {t['accent']}10; }}
        """)
        edit_btn.clicked.connect(self._on_edit_project)
        top_bar.addWidget(edit_btn)

        delete_btn = QPushButton("🗑 Delete Project")
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_outline_bg']};
                color: {t['danger']};
                border: 1px solid {t['danger']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {t['danger']}10; }}
        """)
        delete_btn.clicked.connect(self._on_delete_project)
        top_bar.addWidget(delete_btn)
        layout.addLayout(top_bar)

        # Title
        self.title_label = QLabel(f"✍️ {self.project_name}")
        self.title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {t['text']}; background: transparent;")
        layout.addWidget(self.title_label)

        # Input section
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t['bg_alt']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(20, 20, 20, 20)
        input_layout.setSpacing(10)

        input_label = QLabel("How many words did you write? (use negative for editing)")
        input_label.setStyleSheet(f"font-size: 13px; color: {t['text_secondary']}; background: transparent;")
        input_layout.addWidget(input_label)

        input_row = QHBoxLayout()
        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("Enter word count (e.g. 500 or -100 for editing)...")
        self.word_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px 14px;
                border: 2px solid {t['input_border']};
                border-radius: 8px;
                font-size: 16px;
                background-color: {t['input_bg']};
                color: {t['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {t['input_border_focus']};
            }}
        """)
        self.word_input.returnPressed.connect(self._on_add_entry)
        input_row.addWidget(self.word_input, stretch=1)

        add_btn = QPushButton("Log Words")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t['accent_hover']};
            }}
            QPushButton:pressed {{
                background-color: {t['accent_pressed']};
            }}
        """)
        add_btn.clicked.connect(self._on_add_entry)
        input_row.addWidget(add_btn)
        input_layout.addLayout(input_row)

        # Optional note
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional note (e.g., 'Chapter 3 draft')...")
        self.note_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 14px;
                border: 1px solid {t['input_border']};
                border-radius: 6px;
                font-size: 12px;
                color: {t['text_muted']};
                background-color: {t['input_bg']};
            }}
            QLineEdit:focus {{
                border-color: {t['border_light']};
            }}
        """)
        self.note_input.returnPressed.connect(self._on_add_entry)
        input_layout.addWidget(self.note_input)

        layout.addWidget(input_frame)

        # Summary cards
        cards_layout = QGridLayout()
        cards_layout.setSpacing(10)

        self.today_card = SummaryCard("TODAY'S WORDS", "0", "#5B9BD5", self.dark)
        self.streak_card = SummaryCard("CURRENT STREAK", "0 days", "#E8743B", self.dark)
        self.written_card = SummaryCard("WORDS WRITTEN", "0", "#27AE60", self.dark)
        self.total_card = SummaryCard("TOTAL (INCL. BASELINE)", "0", "#8E44AD", self.dark)

        cards_layout.addWidget(self.today_card, 0, 0)
        cards_layout.addWidget(self.streak_card, 0, 1)
        cards_layout.addWidget(self.written_card, 1, 0)
        cards_layout.addWidget(self.total_card, 1, 1)
        layout.addLayout(cards_layout)

        # Last entry info
        self.last_entry_label = QLabel("")
        self.last_entry_label.setStyleSheet(f"color: {t['text_muted']}; font-size: 11px; background: transparent;")
        self.last_entry_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.last_entry_label)

        # Recent additions summary
        self.recent_label = QLabel("")
        self.recent_label.setStyleSheet(f"color: {t['text_faint']}; font-size: 10px; background: transparent;")
        self.recent_label.setAlignment(Qt.AlignCenter)
        self.recent_label.setWordWrap(True)
        layout.addWidget(self.recent_label)

        layout.addStretch()

        # Stats button
        stats_btn = QPushButton("📊 View Statistics")
        stats_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_outline_bg']};
                color: {t['accent']};
                border: 2px solid {t['accent']};
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t['accent']}10;
            }}
        """)
        stats_btn.clicked.connect(lambda: self.on_stats() if self.on_stats else None)
        layout.addWidget(stats_btn)

        # History button
        history_btn = QPushButton("📋 View History")
        history_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_outline_bg']};
                color: #8E44AD;
                border: 2px solid #8E44AD;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #8E44AD10;
            }}
        """)
        history_btn.clicked.connect(lambda: self.on_history() if self.on_history else None)
        layout.addWidget(history_btn)

        # Version label
        version_label = QLabel(f"v{get_current_version()}")
        version_label.setStyleSheet(f"color: {t['text_disabled']}; font-size: 10px; background: transparent;")
        version_label.setAlignment(Qt.AlignRight)
        layout.addWidget(version_label)

    def on_show(self):
        """Called when this page is switched to."""
        self.refresh_summary()

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

        # Check if streak increased for animation
        old_streak_text = self.streak_card.value_label.text()
        new_streak_text = f"{streak} days"
        self.today_card.value_label.setText(f"{today_total:,}")
        self.streak_card.value_label.setText(new_streak_text)
        self.written_card.value_label.setText(f"{total_written:,}")
        self.total_card.value_label.setText(f"{total_with_baseline:,}")

        # Animate streak card if streak increased
        if old_streak_text != new_streak_text and old_streak_text != "0 days":
            try:
                old_val = int(old_streak_text.split()[0])
                new_val = int(new_streak_text.split()[0])
                if new_val > old_val:
                    self._animate_streak()
            except (ValueError, IndexError):
                pass

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

    def _animate_streak(self):
        """Pulse the streak card when streak increases."""
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        effect = QGraphicsDropShadowEffect(self.streak_card)
        effect.setBlurRadius(0)
        effect.setColor(QColor("#E8743B"))
        effect.setOffset(0, 0)
        self.streak_card.setGraphicsEffect(effect)

        # Animate blur radius: 0 -> 30 -> 0
        self._streak_anim = QPropertyAnimation(effect, b"blurRadius")
        self._streak_anim.setDuration(800)
        self._streak_anim.setStartValue(0)
        self._streak_anim.setKeyValueAt(0.5, 30)
        self._streak_anim.setEndValue(0)
        self._streak_anim.setEasingCurve(QEasingCurve.OutInQuad)
        self._streak_anim.start()
        QTimer.singleShot(900, lambda: self.streak_card.setGraphicsEffect(None))

    def _go_back(self):
        if self.on_back:
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
            self.title_label.setText(f"✍️ {name}")
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
        if self.on_project_deleted:
            self.on_project_deleted()
