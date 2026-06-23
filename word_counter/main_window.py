"""
Main window for WordCounter app.
Single window with QStackedWidget for navigation between Home, Project, Stats, and History pages.
"""

from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .history_window import HistoryPage
from .project_window import ProjectPage
from .stats_window import StatsPage
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


class NewProjectDialog(QDialog):
    """Dialog for creating a new project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(400)
        self.setStyleSheet("background-color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("📝 Create New Project")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Project name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., My Novel, Thesis, Short Stories...")
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

        layout.addWidget(QLabel("Current word count (baseline):"))
        baseline_help = QLabel("This is your starting point. It won't affect stats like averages or streaks, but you'll see a 'total including baseline' alongside your written words.")
        baseline_help.setStyleSheet("color: #999; font-size: 10px;")
        baseline_help.setWordWrap(True)
        layout.addWidget(baseline_help)

        self.baseline_input = QLineEdit()
        self.baseline_input.setPlaceholderText("e.g., 25000 (or leave at 0)")
        self.baseline_input.setText("0")
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

        create_btn = QPushButton("Create Project")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #5B9BD5; color: white;
                border: none; border-radius: 8px;
                padding: 10px 20px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4A8AC5; }
        """)
        create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

    def _on_create(self):
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


class ProjectCard(QFrame):
    """A clickable card showing a project summary."""

    def __init__(self, project: dict, on_click=None, parent=None):
        super().__init__()
        self.project = project
        self.on_click = on_click
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            ProjectCard {
                background-color: #f8f9fa;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
            }
            ProjectCard:hover {
                border-color: #5B9BD5;
                background-color: #f0f4f8;
            }
            QLabel {
                background: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Project name
        name_label = QLabel(f"📖 {project['name']}")
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; background: transparent;")
        layout.addWidget(name_label)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        total_written = project.get("total_written", 0)
        baseline = project.get("baseline_word_count", 0)
        total = baseline + total_written
        entry_count = project.get("entry_count", 0)

        written_label = QLabel(f"✍️ {total_written:,} written")
        written_label.setStyleSheet("color: #27AE60; font-size: 12px; font-weight: bold; background: transparent;")
        stats_row.addWidget(written_label)

        total_label = QLabel(f"📊 {total:,} total")
        total_label.setStyleSheet("color: #8E44AD; font-size: 12px; background: transparent;")
        stats_row.addWidget(total_label)

        entries_label = QLabel(f"📝 {entry_count} entries")
        entries_label.setStyleSheet("color: #999; font-size: 11px; background: transparent;")
        stats_row.addWidget(entries_label)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Last activity
        last_entry = project.get("last_entry")
        if last_entry:
            ts = datetime.fromisoformat(last_entry)
            time_str = ts.strftime("%b %d at %I:%M %p")
            activity_label = QLabel(f"Last: {time_str}")
        else:
            activity_label = QLabel("No entries yet")
        activity_label.setStyleSheet("color: #aaa; font-size: 10px; background: transparent;")
        layout.addWidget(activity_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click:
            self.on_click(self.project)


class HomePage(QWidget):
    """Home page showing all projects."""

    def __init__(self, db: Database, on_open_project=None, on_new_project=None):
        super().__init__()
        self.db = db
        self.on_open_project = on_open_project
        self.on_new_project = on_new_project
        self.setStyleSheet("background-color: #ffffff;")

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("✍️ Word Counter")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; background: transparent;")
        layout.addWidget(title)

        subtitle = QLabel("Your writing projects")
        subtitle.setStyleSheet("color: #999; font-size: 13px; background: transparent;")
        layout.addWidget(subtitle)

        # New project button
        new_btn = QPushButton("+ New Project")
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: #5B9BD5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4A8AC5; }
        """)
        new_btn.clicked.connect(lambda: self.on_new_project() if self.on_new_project else None)
        layout.addWidget(new_btn)

        # Export buttons row
        export_row = QHBoxLayout()
        export_row.setSpacing(8)

        export_json_btn = QPushButton("📥 Export JSON")
        export_json_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #666;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """)
        export_json_btn.clicked.connect(self._on_export_json)
        export_row.addWidget(export_json_btn)

        export_csv_btn = QPushButton("📥 Export CSV")
        export_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #666;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """)
        export_csv_btn.clicked.connect(self._on_export_csv)
        export_row.addWidget(export_csv_btn)

        export_row.addStretch()
        layout.addLayout(export_row)

        # Projects container in a scroll area
        self.projects_container = QWidget()
        self.projects_layout = QVBoxLayout(self.projects_container)
        self.projects_layout.setContentsMargins(0, 0, 0, 0)
        self.projects_layout.setSpacing(10)
        self.projects_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.projects_container)
        scroll.setStyleSheet("""
            QScrollArea { border: none; }
            QScrollBar:vertical { width: 8px; }
        """)
        layout.addWidget(scroll, stretch=1)

        # Version label
        version_label = QLabel(f"v{get_current_version()}")
        version_label.setStyleSheet("color: #ccc; font-size: 10px; background: transparent;")
        version_label.setAlignment(Qt.AlignRight)
        layout.addWidget(version_label)

    def on_show(self):
        """Called when this page is switched to."""
        self.refresh_projects()

    def refresh_projects(self):
        """Rebuild the project cards."""
        # Clear existing cards (keep the stretch)
        while self.projects_layout.count() > 1:
            item = self.projects_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        projects = self.db.get_all_projects()

        if not projects:
            empty_label = QLabel("No projects yet.\nClick '+ New Project' to get started! 🚀")
            empty_label.setStyleSheet("color: #ccc; font-size: 16px; padding: 40px; background: transparent;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.projects_layout.insertWidget(0, empty_label)
            return

        for project in projects:
            card = ProjectCard(project, on_click=self._open_project)
            self.projects_layout.insertWidget(self.projects_layout.count() - 1, card)

    def _open_project(self, project: dict):
        if self.on_open_project:
            self.on_open_project(project)

    def _on_export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to JSON", "wordcounter_export.json", "JSON files (*.json)"
        )
        if not path:
            return
        if self.db.export_to_json(path):
            QMessageBox.information(self, "Export Successful", f"Data exported to:\n{path}")
        else:
            QMessageBox.warning(self, "Export Failed", "Could not export data. Please try again.")

    def _on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "wordcounter_export.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        if self.db.export_to_csv(path):
            QMessageBox.information(self, "Export Successful", f"Data exported to:\n{path}")
        else:
            QMessageBox.warning(self, "Export Failed", "Could not export data. Please try again.")


class MainWindow(QMainWindow):
    """Single-window app with QStackedWidget for page navigation."""

    PAGE_HOME = 0
    PAGE_PROJECT = 1
    PAGE_STATS = 2
    PAGE_HISTORY = 3

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.current_project_id: int | None = None
        self.setWindowTitle("Word Counter ✍️")
        self.setMinimumSize(700, 650)
        self.setWindowIcon(create_app_icon())
        self.setStyleSheet("QMainWindow { background-color: #ffffff; }")

        self._build_ui()
        QTimer.singleShot(2000, self._check_for_updates)

    def _build_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Home page
        self.home_page = HomePage(
            self.db,
            on_open_project=self._open_project,
            on_new_project=self._on_new_project,
        )
        self.stack.addWidget(self.home_page)  # index 0

        # Placeholder for project page (created on demand)
        self.project_page: ProjectPage | None = None
        self.stack.addWidget(QWidget())  # index 1, placeholder

        # Placeholder for stats page
        self.stats_page: StatsPage | None = None
        self.stack.addWidget(QWidget())  # index 2, placeholder

        # Placeholder for history page
        self.history_page: HistoryPage | None = None
        self.stack.addWidget(QWidget())  # index 3, placeholder

        self.stack.setCurrentIndex(self.PAGE_HOME)
        self.home_page.refresh_projects()

    def _switch_to_page(self, index: int):
        widget = self.stack.widget(index)
        if hasattr(widget, "on_show"):
            widget.on_show()
        self.stack.setCurrentIndex(index)

    def _open_project(self, project: dict):
        self.current_project_id = project["id"]

        # Replace project page
        if self.project_page:
            self.stack.removeWidget(self.project_page)
            self.project_page.deleteLater()

        self.project_page = ProjectPage(
            self.db,
            project["id"],
            on_back=self._go_home,
            on_stats=self._go_stats,
            on_history=self._go_history,
            on_project_deleted=self._on_project_deleted,
        )
        self.stack.insertWidget(self.PAGE_PROJECT, self.project_page)
        self.stack.removeWidget(self.stack.widget(self.PAGE_PROJECT + 1))
        self._switch_to_page(self.PAGE_PROJECT)

    def _go_home(self):
        self.current_project_id = None
        self._switch_to_page(self.PAGE_HOME)

    def _go_stats(self):
        if self.current_project_id is None:
            return
        if self.stats_page:
            self.stack.removeWidget(self.stats_page)
            self.stats_page.deleteLater()

        self.stats_page = StatsPage(
            self.db,
            self.current_project_id,
            on_back=lambda: self._switch_to_page(self.PAGE_PROJECT),
        )
        self.stack.insertWidget(self.PAGE_STATS, self.stats_page)
        self.stack.removeWidget(self.stack.widget(self.PAGE_STATS + 1))
        self._switch_to_page(self.PAGE_STATS)

    def _go_history(self):
        if self.current_project_id is None:
            return
        if self.history_page:
            self.stack.removeWidget(self.history_page)
            self.history_page.deleteLater()

        self.history_page = HistoryPage(
            self.db,
            self.current_project_id,
            on_back=lambda: self._switch_to_page(self.PAGE_PROJECT),
            on_data_changed=lambda: self.project_page.refresh_summary() if self.project_page else None,
        )
        self.stack.insertWidget(self.PAGE_HISTORY, self.history_page)
        self.stack.removeWidget(self.stack.widget(self.PAGE_HISTORY + 1))
        self._switch_to_page(self.PAGE_HISTORY)

    def _on_new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, baseline = dialog.get_values()
            self.db.create_project(name, baseline)
            self.home_page.refresh_projects()

    def _on_project_deleted(self):
        self._go_home()

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
