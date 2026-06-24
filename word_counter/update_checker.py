"""
Update checker for WordCounter.
Checks GitHub releases for newer versions and auto-updates the .exe.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

CURRENT_VERSION = "1.4.1"
GITHUB_API_URL = "https://api.github.com/repos/Adrian-Mag/word-counter/releases/latest"
GITHUB_ALL_RELEASES_URL = "https://api.github.com/repos/Adrian-Mag/word-counter/releases"


def get_current_version() -> str:
    return CURRENT_VERSION


def check_for_update() -> dict | None:
    """Check GitHub for a newer release. Returns release info dict or None if up to date.

    The returned dict includes 'changelog' — release notes for all versions
    between the current version and the latest, concatenated in order.
    """
    try:
        req = urllib.request.Request(GITHUB_API_URL, headers={"User-Agent": "WordCounter"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "").lstrip("v")
        if _compare_versions(latest_tag, CURRENT_VERSION) > 0:
            # Find the .exe download URL and size
            exe_url = None
            exe_size = 0
            for asset in data.get("assets", []):
                if asset["name"].endswith(".exe"):
                    exe_url = asset["browser_download_url"]
                    exe_size = asset.get("size", 0)
                    break
            if exe_url:
                # Fetch changelog for all versions between current and latest
                changelog = _fetch_changelog(CURRENT_VERSION, latest_tag)
                return {
                    "version": latest_tag,
                    "url": exe_url,
                    "size": exe_size,
                    "notes": data.get("body", ""),
                    "changelog": changelog,
                }
    except Exception:
        pass
    return None


def _fetch_changelog(current_version: str, latest_version: str) -> list[dict]:
    """Fetch release notes for all versions between current and latest.

    Returns a list of {'version': '1.2.0', 'notes': '...'} sorted oldest-first.
    """
    try:
        req = urllib.request.Request(GITHUB_ALL_RELEASES_URL, headers={"User-Agent": "WordCounter"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read().decode("utf-8"))

        changelog = []
        for rel in releases:
            tag = rel.get("tag_name", "").lstrip("v")
            # Include versions newer than current, up to and including latest
            if _compare_versions(tag, current_version) > 0 and _compare_versions(tag, latest_version) <= 0:
                changelog.append({
                    "version": tag,
                    "notes": rel.get("body", ""),
                })

        # Sort oldest-first (so user reads in chronological order)
        changelog.sort(key=lambda c: [int(x) for x in c["version"].split(".") if x.isdigit()])
        return changelog
    except Exception:
        return []


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings like '1.0.4' vs '1.0.3'. Returns 1, 0, or -1."""
    parts1 = [int(x) for x in v1.split(".") if x.isdigit()]
    parts2 = [int(x) for x in v2.split(".") if x.isdigit()]
    for a, b in zip(parts1, parts2):
        if a > b:
            return 1
        elif a < b:
            return -1
    if len(parts1) > len(parts2):
        return 1
    elif len(parts1) < len(parts2):
        return -1
    return 0


def download_update(exe_url: str, expected_size: int = 0, progress_callback=None) -> Path:
    """Download the new .exe to a temp file. Returns the path.
    Raises RuntimeError if the download is incomplete or file size doesn't match."""
    tmp_dir = Path(tempfile.gettempdir())
    tmp_exe = tmp_dir / "WordCounter_update.exe"

    # If a previous download attempt left a partial file, remove it
    if tmp_exe.exists():
        tmp_exe.unlink()

    req = urllib.request.Request(exe_url, headers={"User-Agent": "WordCounter"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        if expected_size > 0 and total > 0 and total != expected_size:
            raise RuntimeError(f"Size mismatch: expected {expected_size}, got {total}")
        downloaded = 0
        chunk_size = 65536

        with open(tmp_exe, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(downloaded, total)

    # Verify the downloaded file size
    actual_size = tmp_exe.stat().st_size
    if total > 0 and actual_size != total:
        tmp_exe.unlink()
        raise RuntimeError(f"Download incomplete: got {actual_size} bytes, expected {total}")
    if expected_size > 0 and actual_size != expected_size:
        tmp_exe.unlink()
        raise RuntimeError(f"File size mismatch: got {actual_size}, expected {expected_size}")

    return tmp_exe


def install_update(new_exe_path: Path):
    """Replace the current .exe with the downloaded one and relaunch.

    Creates a batch script that:
    1. Waits for the current app to close
    2. Copies the new .exe over the old one
    3. Verifies the copy succeeded (file size matches)
    4. Relaunches the app
    5. Deletes itself
    """
    current_exe = Path(sys.executable).resolve()

    # If running from source (not frozen), just open the download location
    if not getattr(sys, "frozen", False):
        if platform.system() == "Windows":
            os.startfile(str(new_exe_path.parent))
        return

    new_size = new_exe_path.stat().st_size
    current_pid = os.getpid()

    # Determine log file path (app data dir)
    if platform.system() == "Windows":
        app_data = os.path.join(os.environ.get("APPDATA", ""), "WordCounter")
    else:
        app_data = os.path.join(os.path.expanduser("~"), ".local", "share", "WordCounter")
    log_path = os.path.join(app_data, "update.log")

    # Create updater batch script with full logging and launch retry
    updater_script = f"""@echo off
chcp 65001 >nul 2>nul
set "LOG={log_path}"
set "EXE={current_exe}"
set "NEW_EXE={new_exe_path}"
set "EXPECTED_SIZE={new_size}"

echo. >> "%LOG%"
echo ============================================ >> "%LOG%"
echo [%date% %time%] Update batch script started >> "%LOG%"
echo   Old exe: %EXE% >> "%LOG%"
echo   New exe: %NEW_EXE% >> "%LOG%"
echo   Expected size: %EXPECTED_SIZE% bytes >> "%LOG%"
echo   Log file: %LOG% >> "%LOG%"
echo ============================================ >> "%LOG%"

:wait
echo [%date% %time%] Step 1: Waiting for app to exit naturally (sys.exit was called) >> "%LOG%"
timeout /t 3 /nobreak >nul
echo [%date% %time%] Step 2: Attempting to delete old exe >> "%LOG%"
del "%EXE%" 2>nul
if exist "%EXE%" (
    echo [%date% %time%] Old exe still locked, waiting for PyInstaller cleanup >> "%LOG%"
    timeout /t 2 /nobreak >nul
    del "%EXE%" 2>nul
)
if exist "%EXE%" (
    echo [%date% %time%] Old exe still locked, retrying >> "%LOG%"
    goto wait
)
echo [%date% %time%] Step 2: Old exe deleted successfully >> "%LOG%"

echo [%date% %time%] Step 4: Copying new exe >> "%LOG%"
copy /y "%NEW_EXE%" "%EXE%" >> "%LOG%" 2>&1
if not exist "%EXE%" (
    echo [%date% %time%] ERROR: Copy failed, exe does not exist >> "%LOG%"
    goto wait
)
echo [%date% %time%] Step 4: Copy completed >> "%LOG%"

:verify
for %%A in ("%EXE%") do set copied_size=%%~zA
echo [%date% %time%] Step 5: Verifying size (got: %copied_size%, expected: %EXPECTED_SIZE%) >> "%LOG%"
if not "%copied_size%"=="%EXPECTED_SIZE%" (
    echo [%date% %time%] WARNING: Size mismatch, retrying copy >> "%LOG%"
    timeout /t 1 /nobreak >nul
    copy /y "%NEW_EXE%" "%EXE%" >> "%LOG%" 2>&1
    for %%A in ("%EXE%") do set copied_size=%%~zA
    if not "%copied_size%"=="%EXPECTED_SIZE%" goto verify
)
echo [%date% %time%] Step 5: Size verification passed >> "%LOG%"

echo [%date% %time%] Step 6: Waiting 5s for DLLs/handles to release >> "%LOG%"
timeout /t 5 /nobreak >nul
echo [%date% %time%] Step 6: Wait complete >> "%LOG%"

echo [%date% %time%] Step 6b: Cleaning up stale PyInstaller _MEI temp folders >> "%LOG%"
for /d %%D in ("%TEMP%\\_MEI*") do (
    echo [%date% %time%]   Removing stale: %%D >> "%LOG%"
    rmdir /s /q "%%D" 2>nul
)
echo [%date% %time%] Step 6b: _MEI cleanup done >> "%LOG%"

echo [%date% %time%] Step 7: Launching new exe (attempt 1) >> "%LOG%"
start "" "%EXE%"
timeout /t 5 /nobreak >nul

rem Check if the app started by looking for the lock file
if exist "{app_data}\\wordcounter.lock" (
    echo [%date% %time%] Step 7: App started successfully (lock file found) >> "%LOG%"
    goto cleanup
)

echo [%date% %time%] Step 7: App may not have started, waiting 5s and retrying (attempt 2) >> "%LOG%"
timeout /t 5 /nobreak >nul
start "" "%EXE%"
timeout /t 5 /nobreak >nul

if exist "{app_data}\\wordcounter.lock" (
    echo [%date% %time%] Step 7: App started successfully on attempt 2 >> "%LOG%"
    goto cleanup
)

echo [%date% %time%] Step 7: App may not have started, waiting 10s and retrying (attempt 3) >> "%LOG%"
timeout /t 10 /nobreak >nul
echo [%date% %time%] Step 7: Final launch attempt >> "%LOG%"
start "" "%EXE%"
timeout /t 5 /nobreak >nul

if exist "{app_data}\\wordcounter.lock" (
    echo [%date% %time%] Step 7: App started successfully on attempt 3 >> "%LOG%"
) else (
    echo [%date% %time%] Step 7: WARNING - App may not have started after 3 attempts >> "%LOG%"
    echo [%date% %time%]   Please launch WordCounter manually from: %EXE% >> "%LOG%"
)

:cleanup
echo [%date% %time%] Step 8: Cleaning up temp file >> "%LOG%"
del "%NEW_EXE%" 2>nul
echo [%date% %time%] Step 8: Deleting batch script >> "%LOG%"
echo ============================================ >> "%LOG%"
del "%~f0"
"""

    updater_path = Path(tempfile.gettempdir()) / "wordcounter_updater.bat"
    with open(updater_path, "w", encoding="utf-8") as f:
        f.write(updater_script)

    # Log that we're about to launch the updater
    try:
        import logging
        logger = logging.getLogger("word_counter")
        logger.info(f"Update: launching batch updater. PID={current_pid}, exe={current_exe}, new_size={new_size}, log={log_path}")
    except Exception:
        pass

    # Launch the updater and exit immediately
    # Use os._exit instead of sys.exit to bypass Qt event loop and tray icon closeEvent
    if platform.system() == "Windows":
        subprocess.Popen(
            ["cmd", "/c", str(updater_path)],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        # Non-Windows: just copy
        shutil.copy2(new_exe_path, current_exe)

    os._exit(0)
