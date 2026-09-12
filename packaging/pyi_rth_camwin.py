# Runtime hook: keep Qt plugin discovery working in a frozen tree.
import os
import sys

if getattr(sys, "frozen", False):
    root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ.setdefault("QT_PLUGIN_PATH", os.path.join(root, "PySide6", "plugins"))
    os.environ.setdefault("QML2_IMPORT_PATH", os.path.join(root, "PySide6", "qml"))
