"""
Standalone entry point for PyInstaller.
Uses absolute imports so it works when bundled as an .exe.
"""
import sys

from PyQt5.QtWidgets import QApplication

from word_counter.database import Database
from word_counter.main_window import MainWindow


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
