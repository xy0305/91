from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from camwin import __app_name__, __version__
from camwin.engine import EngineError, download_script, fetch_91zb, run_script
from camwin.models import Page, Room, Script
from camwin.player import PlayerWidget
from camwin.proxy import PROXY
from camwin.store import ScriptStore


class WorkerSignals(QObject):
    ok = Signal(object)
    err = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.ok.emit(self.fn(*self.args))
        except Exception as e:
            self.signals.err.emit(f"{e}\n{traceback.format_exc(limit=2)}")


def decode_cover(data: bytes) -> QPixmap | None:
    img = QImage.fromData(data)
    if img.isNull():
        jpeg = data.find(b"\xff\xd8\xff")
        png = data.find(b"\x89PNG")
        off = jpeg if jpeg >= 0 else png
        if off > 0:
            img = QImage.fromData(data[off:])
    if img.isNull():
        return None
    return QPixmap.fromImage(img)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(1280, 800)
        self.store = ScriptStore()
        self.pool = QThreadPool.globalInstance()
        self.net = QNetworkAccessManager(self)
        self.page: Page | None = None
        self.current_script: Script | None = None

        try:
            PROXY.start()
        except Exception:
            pass

        root = QSplitter()
        self.setCentralWidget(root)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("脚本"))
        self.script_list = QListWidget()
        self.script_list.currentRowChanged.connect(self._on_script)
        ll.addWidget(self.script_list, 1)
        row = QHBoxLayout()
        b_imp = QPushButton("导入")
        b_imp.clicked.connect(self._import)
        b_del = QPushButton("删除")
        b_del.clicked.connect(self._delete)
        row.addWidget(b_imp)
        row.addWidget(b_del)
        ll.addLayout(row)
        root.addWidget(left)

        mid = QWidget()
        ml = QVBoxLayout(mid)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("筛选房间…")
        self.search.textChanged.connect(self._filter)
        b_ref = QPushButton("刷新")
        b_ref.clicked.connect(self._reload)
        top.addWidget(self.search)
        top.addWidget(b_ref)
        ml.addLayout(top)
        self.room_list = QListWidget()
        self.room_list.itemDoubleClicked.connect(self._play_item)
        self.room_list.itemClicked.connect(self._play_item)
        ml.addWidget(self.room_list, 1)
        root.addWidget(mid)

        right = QWidget()
        rl = QVBoxLayout(right)
        self.info = QLabel("未选择房间")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("font-size:15px;")
        rl.addWidget(self.info)
        self.player = PlayerWidget()
        self.player.failed.connect(lambda m: self.statusBar().showMessage(m, 8000))
        self.player.started.connect(lambda: self.statusBar().showMessage("播放中", 2000))
        rl.addWidget(self.player, 1)
        stop = QPushButton("停止")
        stop.clicked.connect(self.player.stop)
        rl.addWidget(stop)
        root.addWidget(right)
        root.setSizes([220, 380, 680])

        bar = QStatusBar()
        self.setStatusBar(bar)
        bar.showMessage(f"播放后端: {self.player.backend_name()}")

        self._fill_scripts()
        if self.script_list.count():
            self.script_list.setCurrentRow(0)

    def _fill_scripts(self):
        self.script_list.clear()
        for s in self.store.scripts:
            it = QListWidgetItem(f"{s.name}\n{s.platform or s.url}")
            it.setData(Qt.ItemDataRole.UserRole, s)
            self.script_list.addItem(it)

    def _on_script(self, row: int):
        it = self.script_list.item(row)
        if not it:
            return
        self.current_script = it.data(Qt.ItemDataRole.UserRole)
        self._reload()

    def _reload(self):
        s = self.current_script
        if not s:
            return
        self.statusBar().showMessage(f"加载 {s.name}…")
        w = Worker(self._load, s)
        w.signals.ok.connect(self._on_page)
        w.signals.err.connect(lambda e: self.statusBar().showMessage(e, 8000))
        self.pool.start(w)

    def _load(self, s: Script) -> Page:
        if "91zb" in s.url.lower() or "91" in s.name:
            try:
                src = download_script(s.url)
                return run_script(src)
            except Exception:
                return fetch_91zb()
        src = download_script(s.url)
        return run_script(src)

    def _on_page(self, page: Page):
        self.page = page
        self.statusBar().showMessage(f"{page.title or '脚本'} · {len(page.items)} 个房间")
        self._filter()

    def _filter(self):
        q = self.search.text().strip().lower()
        self.room_list.clear()
        if not self.page:
            return
        for r in self.page.items:
            blob = " ".join(filter(None, [r.name, r.room_name, r.plat, r.hot]))
            if q and q not in blob.lower():
                continue
            it = QListWidgetItem(f"{r.title}    🔥 {r.viewers}\n{r.room_name or r.plat or ''}")
            it.setData(Qt.ItemDataRole.UserRole, r)
            self.room_list.addItem(it)
            if r.image:
                self._fetch_cover(it, r.image)

    def _fetch_cover(self, item: QListWidgetItem, url: str):
        from PySide6.QtCore import QUrl

        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", b"CamWin/1.0")
        reply = self.net.get(req)

        def done():
            data = reply.readAll().data()
            reply.deleteLater()
            pix = decode_cover(data)
            if pix:
                item.setIcon(pix.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

        reply.finished.connect(done)

    def _play_item(self, item: QListWidgetItem):
        room: Room = item.data(Qt.ItemDataRole.UserRole)
        if not room or not room.address:
            return
        self.info.setText(f"{room.title}\n{room.room_name or ''}\n{room.plat or ''}  🔥 {room.viewers}")
        if self.player.has_mpv():
            play = room.address
            self.statusBar().showMessage(f"mpv 直连 {room.title}")
        else:
            play = PROXY.play_url(room.address)
            self.statusBar().showMessage(f"系统播放器（易花屏，请装 mpv） {room.title}")
        self.player.play(play)

    def _import(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "导入脚本", "粘贴 iplayer2://import?payload=… 或 .js 地址"
        )
        if not ok or not text.strip():
            return
        s = self.store.import_text(text)
        if not s:
            QMessageBox.warning(self, "导入失败", "无法解析")
            return
        self._fill_scripts()
        self.statusBar().showMessage(f"已导入 {s.name}")

    def _delete(self):
        it = self.script_list.currentItem()
        if not it:
            return
        s: Script = it.data(Qt.ItemDataRole.UserRole)
        self.store.remove(s)
        self._fill_scripts()

    def closeEvent(self, e):
        self.player.stop()
        super().closeEvent(e)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setQuitOnLastWindowClosed(True)
    try:
        w = MainWindow()
        w.show()
    except Exception:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, "CamWin 启动失败", traceback.format_exc()[-2000:])
        return 1
    return app.exec()
