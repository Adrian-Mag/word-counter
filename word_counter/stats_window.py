"""
Stats page for WordCounter app.
Shows charts and statistics using matplotlib.
Designed as a page inside a QStackedWidget, not a separate window.
"""

from datetime import datetime

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .database import Database


class StatsCard(QFrame):
    """A small card showing a single stat."""

    def __init__(self, title: str, value: str, subtitle: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            StatsCard {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("color: #2c3e50; font-size: 22px; font-weight: bold;")
        layout.addWidget(value_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet("color: #999; font-size: 10px;")
            layout.addWidget(sub_label)


class StatsPage(QWidget):
    """Page showing writing statistics and charts."""

    PERIOD_OPTIONS = [
        ("Past Week", 7),
        ("Past Month", 30),
        ("Past 6 Months", 180),
    ]

    def __init__(self, db: Database, project_id: int, on_back=None):
        super().__init__()
        self.db = db
        self.project_id = project_id
        self.on_back = on_back
        self.setStyleSheet("background-color: #ffffff;")

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Top bar with back button
        top_bar = QHBoxLayout()
        back_btn = QPushButton("← Back to Project")
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
        main_layout.addLayout(top_bar)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("📊 Writing Statistics")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        period_label = QLabel("Period:")
        period_label.setStyleSheet("font-size: 12px; color: #666;")
        header_layout.addWidget(period_label)

        self.period_combo = QComboBox()
        for label, days in self.PERIOD_OPTIONS:
            self.period_combo.addItem(label, days)
        self.period_combo.currentIndexChanged.connect(self.refresh)
        self.period_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 12px;
            }
        """)
        header_layout.addWidget(self.period_combo)
        main_layout.addLayout(header_layout)

        # Stats cards row
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(12)
        main_layout.addLayout(self.cards_layout)

        # Chart
        self.figure = Figure(figsize=(7, 4), facecolor="white")
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas, stretch=1)

        # Recent entries list
        entries_label = QLabel("📝 Recent Entries")
        entries_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50; margin-top: 8px;")
        main_layout.addWidget(entries_label)

        self.entries_container = QWidget()
        self.entries_layout = QVBoxLayout(self.entries_container)
        self.entries_layout.setContentsMargins(0, 0, 0, 0)
        self.entries_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.entries_container)
        scroll.setMaximumHeight(150)
        scroll.setStyleSheet("""
            QScrollArea { border: 1px solid #e0e0e0; border-radius: 8px; }
            QScrollBar:vertical { width: 8px; }
        """)
        main_layout.addWidget(scroll)

    def _go_back(self):
        if self.on_back:
            self.on_back()

    def on_show(self):
        """Called when this page is switched to."""
        self.refresh()

    def refresh(self):
        """Refresh all stats and charts."""
        days = self.period_combo.currentData()
        stats = self.db.get_stats(self.project_id, days)

        # Clear old cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build stat cards
        avg_str = f"{stats['avg_per_day']:.0f}"
        best = stats["best_day"]
        best_str = f"{best['total']:,}" if best and best["total"] > 0 else "0"
        best_sub = best["date"] if best and best["total"] > 0 else ""

        cards = [
            StatsCard("TOTAL (PERIOD)", f"{stats['total_words_period']:,}", f"Last {days} days"),
            StatsCard("AVG / DAY", avg_str, f"Over {days} days"),
            StatsCard("BEST DAY", best_str, best_sub),
            StatsCard("STREAK", f"{stats['current_streak']} days", "Consecutive days"),
            StatsCard("WORDS WRITTEN", f"{stats['total_written']:,}", f"{stats['total_entries']} entries"),
            StatsCard("TOTAL (INCL. BASELINE)", f"{stats['total_with_baseline']:,}", f"Baseline: {stats['baseline']:,}"),
        ]
        for card in cards:
            self.cards_layout.addWidget(card)

        # Draw chart
        self._draw_chart(stats["daily_totals"], days)

        # Populate recent entries
        self._populate_entries()

    def _draw_chart(self, daily_totals: list[dict], days: int):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        dates = [d["date"] for d in daily_totals]
        totals = [d["total"] for d in daily_totals]

        # Choose label format based on period length
        if days <= 7:
            labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%a\n%m/%d") for d in dates]
        elif days <= 30:
            labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d") for d in dates]
        else:
            # For long periods, show weekly markers
            labels = []
            for i, d in enumerate(dates):
                if i % 7 == 0:
                    labels.append(datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d"))
                else:
                    labels.append("")

        colors = ["#5B9BD5" if t > 0 else "#E8E8E8" for t in totals]
        ax.bar(range(len(dates)), totals, color=colors, edgecolor="none", width=0.7)
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(labels, fontsize=7, rotation=0 if days <= 30 else 0)

        ax.set_ylabel("Words Written", fontsize=9, color="#666")
        ax.set_title(f"Daily Word Count — Last {days} Days", fontsize=12, color="#2c3e50", pad=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#ddd")
        ax.spines["bottom"].set_color("#ddd")
        ax.tick_params(colors="#999", labelsize=8)
        ax.yaxis.get_offset_text().set_fontsize(8)

        # Add average line
        avg = sum(totals) / len(totals) if totals else 0
        if avg > 0:
            ax.axhline(y=avg, color="#E8743B", linestyle="--", linewidth=1, alpha=0.7)
            ax.text(len(dates) - 0.5, avg, f"  avg {avg:.0f}", fontsize=7, color="#E8743B", va="bottom")

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _populate_entries(self):
        # Clear old entries
        while self.entries_layout.count():
            item = self.entries_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self.db.get_all_entries(self.project_id)
        # Show last 20 entries, most recent first
        for entry in reversed(entries[-20:]):
            ts = datetime.fromisoformat(entry["timestamp"])
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 4, 8, 4)

            date_str = ts.strftime("%b %d, %Y — %I:%M %p")
            sign = "+" if entry["word_count"] >= 0 else ""
            words_str = f"{sign}{entry['word_count']:,} words"

            date_label = QLabel(date_str)
            date_label.setStyleSheet("color: #666; font-size: 11px;")
            row_layout.addWidget(date_label)
            row_layout.addStretch()

            words_label = QLabel(words_str)
            words_label.setStyleSheet("color: #5B9BD5; font-size: 12px; font-weight: bold;")
            row_layout.addWidget(words_label)

            if entry.get("note"):
                note_label = QLabel(f"  ({entry['note']})")
                note_label.setStyleSheet("color: #aaa; font-size: 10px; font-style: italic;")
                row_layout.addWidget(note_label)

            self.entries_layout.addWidget(row)

        if not entries:
            no_entries = QLabel("No entries yet. Start writing! ✍️")
            no_entries.setStyleSheet("color: #aaa; font-size: 12px; padding: 20px;")
            no_entries.setAlignment(Qt.AlignCenter)
            self.entries_layout.addWidget(no_entries)
