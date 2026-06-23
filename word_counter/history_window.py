"""
History window for WordCounter app.
Shows all entries with edit, delete, and clear-all functionality.
"""

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import Database


class EditEntryDialog(QDialog):
    """Dialog for editing an existing entry."""

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Entry")
        self.setMinimumWidth(350)
        self.setStyleSheet("background-color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        ts = datetime.fromisoformat(entry["timestamp"])
        date_label = QLabel(f"📅 {ts.strftime('%B %d, %Y at %I:%M %p')}")
        date_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(date_label)

        layout.addWidget(QLabel("Word count:"))
        self.words_input = QLineEdit(str(entry["word_count"]))
        self.words_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus { border-color: #5B9BD5; }
        """)
        layout.addWidget(self.words_input)

        layout.addWidget(QLabel("Note:"))
        self.note_input = QLineEdit(entry.get("note", ""))
        self.note_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #bbb; }
        """)
        layout.addWidget(self.note_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px; border: 1px solid #ccc;
                border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #5B9BD5; color: white;
                border: none; border-radius: 6px;
                padding: 8px 20px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4A8AC5; }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        try:
            words = int(self.words_input.text().strip())
            if words == 0:
                QMessageBox.warning(self, "Invalid", "Please enter a non-zero number.")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Please enter a valid number.")
            return
        self.accept()

    def get_values(self) -> tuple[int, str]:
        return int(self.words_input.text().strip()), self.note_input.text().strip()


class HistoryWindow(QWidget):
    """Window showing all entries with edit/delete/clear-all functionality."""

    def __init__(self, db: Database, on_data_changed=None):
        super().__init__()
        self.db = db
        self.on_data_changed = on_data_changed
        self.setWindowTitle("Entry History")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("background-color: #ffffff;")

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("📋 Entry History")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header_row.addWidget(title)
        header_row.addStretch()

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #999; font-size: 12px;")
        header_row.addWidget(self.count_label)
        layout.addLayout(header_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date & Time", "Words", "Note", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                gridline-color: #f0f0f0;
                alternate-background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #f0f4f8;
                color: #666;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        clear_btn = QPushButton("🗑 Clear All Data")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #e74c3c;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e74c3c10;
            }
        """)
        clear_btn.clicked.connect(self._on_clear_all)
        bottom_row.addWidget(clear_btn)
        layout.addLayout(bottom_row)

    def refresh(self):
        """Rebuild the table from the database."""
        entries = self.db.get_all_entries()
        entries = list(reversed(entries))  # most recent first

        self.count_label.setText(f"{len(entries)} entries")
        self.table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            ts = datetime.fromisoformat(entry["timestamp"])
            date_str = ts.strftime("%b %d, %Y\n%I:%M %p")

            date_item = QTableWidgetItem(date_str)
            date_item.setData(Qt.UserRole, entry["id"])
            self.table.setItem(row, 0, date_item)

            sign = "+" if entry["word_count"] >= 0 else ""
            words_item = QTableWidgetItem(f"{sign}{entry['word_count']:,}")
            words_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, words_item)

            note_str = entry.get("note", "") or "—"
            note_item = QTableWidgetItem(note_str)
            note_item.setForeground(Qt.gray if not entry.get("note") else Qt.black)
            self.table.setItem(row, 2, note_item)

            # Action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5B9BD5; color: white;
                    border: none; border-radius: 4px;
                    padding: 4px 12px; font-size: 11px;
                }
                QPushButton:hover { background-color: #4A8AC5; }
            """)
            edit_btn.clicked.connect(lambda _, e=entry: self._on_edit(e))
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c; color: white;
                    border: none; border-radius: 4px;
                    padding: 4px 12px; font-size: 11px;
                }
                QPushButton:hover { background-color: #c0392b; }
            """)
            delete_btn.clicked.connect(lambda _, e=entry: self._on_delete(e))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 3, actions_widget)

        self.table.resizeRowsToContents()

    def _on_edit(self, entry: dict):
        dialog = EditEntryDialog(entry, self)
        if dialog.exec_() == QDialog.Accepted:
            words, note = dialog.get_values()
            self.db.update_entry(entry["id"], words, note)
            self.refresh()
            self._notify_data_changed()

    def _on_delete(self, entry: dict):
        ts = datetime.fromisoformat(entry["timestamp"])
        reply = QMessageBox.question(
            self,
            "Delete Entry?",
            f"Are you sure you want to delete this entry?\n\n"
            f"📅 {ts.strftime('%B %d, %Y at %I:%M %p')}\n"
            f"✍️ +{entry['word_count']:,} words\n"
            f"📝 {entry.get('note', '—') or '—'}\n\n"
            f"This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_entry(entry["id"])
            self.refresh()
            self._notify_data_changed()

    def _on_clear_all(self):
        # First confirmation
        total = len(self.db.get_all_entries())
        if total == 0:
            QMessageBox.information(self, "Nothing to Clear", "There are no entries to delete.")
            return

        reply = QMessageBox.warning(
            self,
            "⚠️ Clear ALL Data?",
            f"This will permanently delete ALL {total} entries.\n\n"
            f"This action cannot be undone.\n\n"
            f"Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Second confirmation — type to confirm
        reply2 = QMessageBox.warning(
            self,
            "⚠️ Final Confirmation",
            f"Last chance! All {total} entries will be gone forever.\n\n"
            f"Click 'Yes' to permanently delete everything.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply2 != QMessageBox.Yes:
            return

        self.db.clear_all()
        self.refresh()
        self._notify_data_changed()
        QMessageBox.information(self, "Cleared", "All entries have been deleted.\nA backup was saved before clearing.")

    def _notify_data_changed(self):
        if self.on_data_changed:
            self.on_data_changed()
