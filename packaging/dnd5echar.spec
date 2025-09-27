# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

BASE_DIR = Path.cwd().resolve()
SCRIPT_PATH = BASE_DIR / 'main.py'
DATA_DIR = BASE_DIR / 'data' / '5e-database'

hiddenimports = collect_submodules('character_builder')

a = Analysis(
    [str(SCRIPT_PATH)],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=[
        (str(DATA_DIR), 'data/5e-database'),
        (str(BASE_DIR / 'README.md'), 'README.md'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dnd5e-character-builder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dnd5e-character-builder',
)
