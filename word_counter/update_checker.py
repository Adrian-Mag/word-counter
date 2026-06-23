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

CURRENT_VERSION = "1.2.1"
GITHUB_API_URL = "https://api.github.com/repos/Adrian-Mag/word-counter/releases/latest"


def get_current_version() -> str:
    return CURRENT_VERSION


def check_for_update() -> dict | None:
    """Check GitHub for a newer release. Returns release info dict or None if up to date."""
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
                return {
                    "version": latest_tag,
                    "url": exe_url,
                    "size": exe_size,
                    "notes": data.get("body", ""),
                }
    except Exception:
        pass
    return None


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

    # Create updater batch script with copy verification
    updater_script = f"""@echo off
chcp 65001 >nul 2>nul
:wait
timeout /t 1 /nobreak >nul
del "{current_exe}" 2>nul
if exist "{current_exe}" goto wait
copy /y "{new_exe_path}" "{current_exe}"
if not exist "{current_exe}" goto wait
:verify
for %%A in ("{current_exe}") do set copied_size=%%~zA
if not "%copied_size%"=="{new_size}" (
    timeout /t 1 /nobreak >nul
    copy /y "{new_exe_path}" "{current_exe}"
    for %%A in ("{current_exe}") do set copied_size=%%~zA
    if not "%copied_size%"=="{new_size}" goto verify
)
timeout /t 2 /nobreak >nul
start "" "{current_exe}"
timeout /t 1 /nobreak >nul
del "%~f0"
"""

    updater_path = Path(tempfile.gettempdir()) / "wordcounter_updater.bat"
    with open(updater_path, "w", encoding="utf-8") as f:
        f.write(updater_script)

    # Launch the updater and exit
    if platform.system() == "Windows":
        subprocess.Popen(
            ["cmd", "/c", str(updater_path)],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        # Non-Windows: just copy
        shutil.copy2(new_exe_path, current_exe)

    sys.exit(0)
