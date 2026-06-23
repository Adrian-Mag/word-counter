"""
WordCounter app entry point.
Run with: python -m word_counter
"""

import sys

from PyQt5.QtWidgets import QApplication

from .database import Database
from .main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Word Counter")
    app.setOrganizationName("WordCounter")

    db = Database()
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
