"""
WordCounter app entry point.
Run with: python -m word_counter
"""

import logging
import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox

from .database import Database, get_app_data_dir
from .main_window import MainWindow


def setup_logging():
    """Set up file logging for crash diagnostics."""
    log_dir = get_app_data_dir()
    log_file = log_dir / "wordcounter.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    logger = logging.getLogger("word_counter")
    logger.info("Application starting")


def install_crash_handler(app: QApplication):
    """Install a global exception hook that logs crashes and shows a message."""
    logger = logging.getLogger("word_counter")

    def exception_hook(exc_type, exc_value, tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, tb))
        logger.error(f"Unhandled exception:\n{tb_text}")
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Word Counter — Unexpected Error")
            msg.setText(f"Something went wrong:\n\n{exc_value}\n\n"
                        f"An error log has been saved to:\n"
                        f"{get_app_data_dir() / 'wordcounter.log'}\n\n"
                        f"Please report this at:\n"
                        f"https://github.com/Adrian-Mag/word-counter/issues")
            msg.exec_()
        except Exception:
            pass  # Don't crash during crash handling
        sys.exit(1)

    sys.excepthook = exception_hook


def main():
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Word Counter")
    app.setOrganizationName("WordCounter")

    install_crash_handler(app)

    db = Database()
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
