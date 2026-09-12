# PyInstaller spec — onedir, collect Qt plugins so the exe does not silent-exit.
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas, binaries, hidden = [], [], []
for pkg in ("PySide6", "shiboken6", "Crypto"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
binaries += collect_dynamic_libs("PySide6")

a = Analysis(
    ["camwin/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + [("assets", "assets")],
    hiddenimports=hidden
    + [
        "camwin",
        "camwin.app",
        "camwin.engine",
        "camwin.crypto",
        "camwin.player",
        "camwin.proxy",
        "camwin.remux",
        "camwin.models",
        "camwin.store",
        "Crypto.Cipher.AES",
        "Crypto.Util.Padding",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["packaging/pyi_rth_camwin.py"],
    excludes=["tkinter", "matplotlib", "numpy", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CamWin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CamWin",
)
