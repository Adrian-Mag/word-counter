"""
Standalone entry point for PyInstaller.
Uses absolute imports so it works when bundled as an .exe.
"""
import logging
import os
import sys
import traceback
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox

from word_counter.database import Database, get_app_data_dir
from word_counter.main_window import MainWindow


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
    logger.info("Application starting (PyInstaller mode)")


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
            pass
        sys.exit(1)

    sys.excepthook = exception_hook


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running. Cross-platform."""
    if os.name == "nt":
        # On Windows, use ctypes to call OpenProcess
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        # On Unix, use os.kill with signal 0
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
        except OSError:
            return False


def check_single_instance():
    """Ensure only one instance of the app is running. Returns True if OK to proceed."""
    lock_file = get_app_data_dir() / "wordcounter.lock"
    try:
        # Try to create lock file exclusively
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        # Check if the PID in the lock file is still alive
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
            if _is_process_alive(old_pid):
                # Process is alive — show message and exit
                QMessageBox.warning(None, "Already Running",
                                    "Word Counter is already running.\n"
                                    "Please check your system tray or taskbar.")
                return False
            else:
                # Process is dead — steal the lock
                lock_file.unlink()
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return True
        except (ValueError, IOError, OSError):
            # Can't read lock file or other error — just overwrite it
            lock_file.unlink(missing_ok=True)
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True


def cleanup_lock():
    """Remove the lock file on exit."""
    lock_file = get_app_data_dir() / "wordcounter.lock"
    try:
        lock_file.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Word Counter")
    app.setOrganizationName("WordCounter")

    install_crash_handler(app)

    if not check_single_instance():
        sys.exit(0)

    try:
        db = Database()
        window = MainWindow(db)
        window.show()
        exit_code = app.exec_()
    finally:
        cleanup_lock()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
