"""
Theme management for Word Counter.
Provides light and dark color schemes that can be applied across all pages.
"""

LIGHT_THEME = {
    "bg": "#ffffff",
    "bg_alt": "#f8f9fa",
    "bg_hover": "#f0f4f8",
    "border": "#e0e0e0",
    "border_light": "#ddd",
    "text": "#2c3e50",
    "text_primary": "#1a1a1a",
    "text_secondary": "#666",
    "text_muted": "#999",
    "text_faint": "#aaa",
    "text_disabled": "#ccc",
    "accent": "#5B9BD5",
    "accent_hover": "#4A8AC5",
    "accent_pressed": "#3A7AB5",
    "danger": "#e74c3c",
    "card_bg": "#f8f9fa",
    "card_border": "#e0e0e0",
    "input_bg": "#ffffff",
    "input_border": "#ddd",
    "input_border_focus": "#5B9BD5",
    "btn_bg": "#f0f0f0",
    "btn_bg_hover": "#e0e0e0",
    "btn_outline_bg": "#ffffff",
    "scrollbar_bg": "transparent",
    "scrollbar_width": "8px",
    # Card color schemes: base_color -> (pastel_bg, punchy_text)
    "card_colors": {
        "#5B9BD5": ("#E3F0FB", "#1A6FAA"),
        "#E8743B": ("#FDEDE4", "#C25420"),
        "#27AE60": ("#E2F5EA", "#1A8C46"),
        "#8E44AD": ("#F0E4F5", "#7D2BA0"),
    },
}

DARK_THEME = {
    "bg": "#1e1e2e",
    "bg_alt": "#2a2a3c",
    "bg_hover": "#33334a",
    "border": "#3a3a4e",
    "border_light": "#444460",
    "text": "#e0e0e8",
    "text_primary": "#f0f0f5",
    "text_secondary": "#a0a0b0",
    "text_muted": "#707080",
    "text_faint": "#60606e",
    "text_disabled": "#50505a",
    "accent": "#6BAEDF",
    "accent_hover": "#7BBEEE",
    "accent_pressed": "#5A9ECE",
    "danger": "#e74c3c",
    "card_bg": "#2a2a3c",
    "card_border": "#3a3a4e",
    "input_bg": "#2a2a3c",
    "input_border": "#444460",
    "input_border_focus": "#6BAEDF",
    "btn_bg": "#33334a",
    "btn_bg_hover": "#3d3d56",
    "btn_outline_bg": "#2a2a3c",
    "scrollbar_bg": "transparent",
    "scrollbar_width": "8px",
    "card_colors": {
        "#5B9BD5": ("#1e2d3a", "#6BAEDF"),
        "#E8743B": ("#3a2820", "#E8985B"),
        "#27AE60": ("#1e3328", "#4ECC80"),
        "#8E44AD": ("#332838", "#B066CC"),
    },
}


def get_theme(dark: bool = False) -> dict:
    return DARK_THEME if dark else LIGHT_THEME


def get_stylesheet(dark: bool = False) -> str:
    """Return a QSS stylesheet string for the given theme."""
    t = get_theme(dark)
    return f"""
        * {{
            background-color: {t['bg']};
            color: {t['text']};
        }}
        QMainWindow, QWidget {{
            background-color: {t['bg']};
        }}
        QLabel {{
            background: transparent;
            color: {t['text']};
        }}
        QLineEdit {{
            background-color: {t['input_bg']};
            color: {t['text_primary']};
            border: 2px solid {t['input_border']};
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 14px;
        }}
        QLineEdit:focus {{
            border-color: {t['input_border_focus']};
        }}
        QPushButton {{
            background-color: {t['btn_bg']};
            color: {t['text_secondary']};
            border: 1px solid {t['border_light']};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {t['btn_bg_hover']};
        }}
        QFrame {{
            background-color: {t['bg']};
        }}
        QScrollArea {{
            border: none;
            background-color: {t['bg']};
        }}
        QScrollBar:vertical {{
            width: {t['scrollbar_width']};
            background: {t['scrollbar_bg']};
        }}
        QScrollBar::handle:vertical {{
            background: {t['border']};
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QTextBrowser {{
            background-color: {t['bg']};
            color: {t['text']};
            border: none;
        }}
        QComboBox {{
            background-color: {t['input_bg']};
            color: {t['text']};
            border: 1px solid {t['input_border']};
            border-radius: 6px;
            padding: 6px 12px;
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {t['input_bg']};
            color: {t['text']};
            selection-background-color: {t['accent']};
            selection-color: white;
        }}
        QProgressDialog {{
            background-color: {t['bg']};
        }}
        QProgressBar {{
            background-color: {t['bg_alt']};
            border: 1px solid {t['border']};
            border-radius: 4px;
            text-align: center;
            color: {t['text']};
        }}
        QProgressBar::chunk {{
            background-color: {t['accent']};
            border-radius: 3px;
        }}
        QMessageBox {{
            background-color: {t['bg']};
        }}
        QMessageBox QLabel {{
            color: {t['text']};
        }}
        QDialog {{
            background-color: {t['bg']};
        }}
    """


def get_card_colors(base_color: str, dark: bool = False) -> tuple[str, str]:
    """Return (background, text_color) for a card with the given base color."""
    t = get_theme(dark)
    return t["card_colors"].get(base_color, (t["card_bg"], base_color))
