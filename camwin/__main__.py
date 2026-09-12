from __future__ import annotations

import multiprocessing
import sys
import traceback
from pathlib import Path


def _crash_log() -> Path:
    root = Path.home() / "AppData" / "Local" / "CamWin"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        root = Path.cwd()
    return root / "crash.log"


def _hook(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        _crash_log().write_text(text, encoding="utf-8")
    except Exception:
        pass
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "CamWin 出错",
            f"程序遇到错误，没有退出窗口。\n日志：{_crash_log()}\n\n{text[-1800:]}",
        )
    except Exception:
        pass


def main() -> int:
    multiprocessing.freeze_support()
    sys.excepthook = _hook
    from camwin.app import main as app_main

    try:
        return app_main()
    except Exception:
        _hook(*sys.exc_info())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
