# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for WordCounter.
Builds a single-file Windows executable with the app icon.
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['word_counter/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/icon.svg', 'assets'),
    ],
    hiddenimports=[
        'matplotlib.backends.backend_qt5agg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WordCounter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if Path('assets/icon.ico').exists() else None,
)
