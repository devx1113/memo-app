# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 設定: python -m PyInstaller --noconfirm --clean MemoReminder.spec
from PyInstaller.utils.hooks import collect_data_files

datas = [("assets/app.ico", "assets"), ("assets/app.png", "assets")]
datas += collect_data_files("sv_ttk")

a = Analysis(
    ["main.pyw"],
    pathex=["."],
    datas=datas,
    hiddenimports=["pystray._win32", "winotify", "sv_ttk"],
    excludes=["numpy", "matplotlib", "PyQt5", "PySide6", "unittest", "pydoc"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MemoReminder",
    icon="assets/app.ico",
    version="version_info.txt",
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
