"""
Main window for WordCounter app.
Provides word count entry and today's summary.
"""

from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .history_window import HistoryWindow
from .stats_window import StatsWindow
from .update_checker import check_for_update, download_update, install_update, get_current_version


def create_app_icon() -> QIcon:
    """Create a cute book-and-pen icon programmatically."""
    from PyQt5.QtGui import QPainter, QBrush, QPen, QColor, QPainterPath
    from PyQt5.QtCore import QRectF, QPointF

    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Background circle
    painter.setBrush(QBrush(QColor("#5B9BD5")))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(4, 4, 120, 120))

    # Book shape (white)
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.setPen(QPen(QColor("#E8E8E8"), 1))
    book_path = QPainterPath()
    book_path.moveTo(30, 35)
    book_path.lineTo(64, 30)
    book_path.lineTo(64, 95)
    book_path.lineTo(30, 100)
    book_path.closeSubpath()
    painter.drawPath(book_path)

    # Book pages (right side)
    painter.setBrush(QBrush(QColor("#F0F4F8")))
    book_path2 = QPainterPath()
    book_path2.moveTo(64, 30)
    book_path2.lineTo(98, 35)
    book_path2.lineTo(98, 100)
    book_path2.lineTo(64, 95)
    book_path2.closeSubpath()
    painter.drawPath(book_path2)

    # Lines on book
    painter.setPen(QPen(QColor("#CCCCCC"), 1.5))
    for y in range(42, 92, 10):
        painter.drawLine(36, y, 58, y - 2)
        painter.drawLine(70, y - 2, 92, y)

    # Pen / quill
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor("#E8743B")))
    pen_path = QPainterPath()
    pen_path.moveTo(95, 20)
    pen_path.lineTo(110, 35)
    pen_path.lineTo(105, 40)
    pen_path.lineTo(90, 25)
    pen_path.closeSubpath()
    painter.drawPath(pen_path)

    # Pen tip
    painter.setBrush(QBrush(QColor("#2c3e50")))
    painter.drawEllipse(QRectF(87, 22, 6, 6))

    painter.end()
    return QIcon(pixmap)


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


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.stats_window: StatsWindow | None = None
        self.history_window: HistoryWindow | None = None
        self.setWindowTitle("Word Counter ✍️")
        self.setMinimumSize(450, 520)
        self.setWindowIcon(create_app_icon())
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

        # Title
        title = QLabel("✍️ Word Counter")
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
        self.alltime_card = SummaryCard("ALL-TIME TOTAL", "0", "#27AE60")
        self.entries_card = SummaryCard("TOTAL ENTRIES", "0", "#8E44AD")

        cards_layout.addWidget(self.today_card, 0, 0)
        cards_layout.addWidget(self.streak_card, 0, 1)
        cards_layout.addWidget(self.alltime_card, 1, 0)
        cards_layout.addWidget(self.entries_card, 1, 1)
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

        # Version label in bottom margin
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
        self.db.add_entry(word_count, note)
        self.word_input.clear()
        self.note_input.clear()
        self.word_input.setFocus()
        self.refresh_summary()

        # Brief confirmation with sign-aware formatting
        if word_count > 0:
            self.last_entry_label.setText(f"✅ Logged +{word_count:,} words!")
        else:
            self.last_entry_label.setText(f"✏️ Logged {word_count:,} words (editing)")
        QTimer.singleShot(3000, lambda: self.refresh_summary())

    def refresh_summary(self):
        """Refresh the summary cards and last entry info."""
        today_entries = self.db.get_today_entries()
        today_total = sum(e["word_count"] for e in today_entries)

        all_entries = self.db.get_all_entries()
        all_time = sum(e["word_count"] for e in all_entries)

        stats = self.db.get_stats(7)
        streak = stats["current_streak"]

        # Update cards
        self.today_card.layout().itemAt(1).widget().setText(f"{today_total:,}")
        self.streak_card.layout().itemAt(1).widget().setText(f"{streak} days")
        self.alltime_card.layout().itemAt(1).widget().setText(f"{all_time:,}")
        self.entries_card.layout().itemAt(1).widget().setText(f"{len(all_entries)}")

        # Last entry info
        if all_entries:
            last = all_entries[-1]
            ts = datetime.fromisoformat(last["timestamp"])
            time_str = ts.strftime("%I:%M %p on %b %d")
            sign = "+" if last["word_count"] >= 0 else ""
            self.last_entry_label.setText(f"Last entry: {sign}{last['word_count']:,} words at {time_str}")
        else:
            self.last_entry_label.setText("No entries yet — start writing! 🚀")

        # Recent additions summary (last 3 entries)
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

    def _open_stats(self):
        if self.stats_window is None or not self.stats_window.isVisible():
            self.stats_window = StatsWindow(self.db)
            self.stats_window.show()
            self.stats_window.activateWindow()
        else:
            self.stats_window.refresh()
            self.stats_window.activateWindow()

    def _open_history(self):
        if self.history_window is None or not self.history_window.isVisible():
            self.history_window = HistoryWindow(self.db, on_data_changed=self.refresh_summary)
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

        # Download with progress bar
        expected_size = update_info.get("size", 0)
        size_mb = f"({expected_size / 1024 / 1024:.1f} MB)" if expected_size else ""
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
