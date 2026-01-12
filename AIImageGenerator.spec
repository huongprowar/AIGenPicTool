# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'openai', 'google.generativeai', 'httpx', 'pydantic', 'ui', 'ui.main_window', 'ui.create_tab', 'ui.settings_tab', 'ui.image_item', 'services', 'services.config_service', 'services.chatgpt_service', 'services.gemini_service', 'utils', 'utils.prompt_parser', 'utils.image_downloader', 'UnlimitedAPI', 'UnlimitedAPI.providers', 'UnlimitedAPI.providers.google_flow'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AIImageGenerator',
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
)
