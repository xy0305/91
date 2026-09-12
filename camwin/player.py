"""Play 91zb HEVC. Prefer mpv on the original FLV; Qt Multimedia is a last resort."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, QUrl, Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget


def find_mpv() -> str | None:
    for name in ("mpv", "mpv.exe"):
        exe = shutil.which(name)
        if exe:
            return exe
    extra: list[Path] = [
        Path(r"C:\Program Files\MPV Player\mpv.exe"),
        Path(r"C:\Program Files\mpv\mpv.exe"),
        Path(r"C:\Program Files (x86)\MPV Player\mpv.exe"),
        Path(r"C:\Program Files (x86)\mpv\mpv.exe"),
        Path(r"C:\mpv\mpv.exe"),
        Path.home() / "scoop" / "apps" / "mpv" / "current" / "mpv.exe",
        Path.home() / "scoop" / "shims" / "mpv.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "mpv" / "mpv.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "MPV Player" / "mpv.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "mpv.exe",
    ]
    for root in (
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path.home() / "AppData" / "Local" / "Programs",
    ):
        try:
            extra.extend(root.glob("**/mpv.exe"))
        except OSError:
            pass
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget.is_dir():
        extra.extend(winget.glob("**/mpv.exe"))
    seen: set[str] = set()
    for p in extra:
        try:
            if p.is_file():
                key = str(p).lower()
                if key not in seen:
                    seen.add(key)
                    return str(p)
        except OSError:
            continue
    return None


class PlayerWidget(QWidget):
    started = Signal()
    failed = Signal(str)
    status_changed = Signal(str)  # 新增:状态变化信号

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mpv_path = find_mpv()
        self._proc: QProcess | None = None
        self._qt: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None
        self._current_url = ""

        self._stack = QStackedWidget()
        self._placeholder = QLabel("选择房间开始播放")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color:#aaa;font-size:16px;background:#111;")
        self._video = QVideoWidget()
        self._video.setStyleSheet("background:#000;")
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._video)

        # 状态栏:始终显示,不只是警告
        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "background:#1a4d2e;color:#a8e6cf;padding:6px 10px;font-size:12px;"
        )
        self._update_status("就绪")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._status)
        lay.addWidget(self._stack, 1)

        if not self._mpv_path:
            self._qt = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._qt.setAudioOutput(self._audio)
            self._qt.setVideoOutput(self._video)
            self._qt.errorOccurred.connect(self._on_qt_error)
            self._qt.playbackStateChanged.connect(self._on_qt_state)

    def _update_status(self, msg: str, warn: bool = False) -> None:
        """更新状态栏显示"""
        self._status.setText(msg)
        if warn:
            self._status.setStyleSheet(
                "background:#5c3b00;color:#ffe9b0;padding:6px 10px;font-size:12px;"
            )
        else:
            self._status.setStyleSheet(
                "background:#1a4d2e;color:#a8e6cf;padding:6px 10px;font-size:12px;"
            )
        self.status_changed.emit(msg)

    def has_mpv(self) -> bool:
        return bool(self._mpv_path)

    def play(self, url: str) -> None:
        self.stop()
        self._current_url = url
        self._stack.setCurrentWidget(self._video)
        
        if self._mpv_path:
            short_url = url[:80] + "..." if len(url) > 80 else url
            self._update_status(f"mpv 播放中: {short_url}")
            self._play_mpv(url)
        elif self._qt:
            self._update_status(f"Qt 播放器(HEVC 会花屏): {url[:60]}...", warn=True)
            self._qt.setSource(QUrl(url))
            self._qt.play()
        else:
            msg = "❌ 没有可用播放器。请安装 mpv: winget install mpv"
            self._update_status(msg, warn=True)
            self.failed.emit(msg)

    def _play_mpv(self, url: str) -> None:
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyRead.connect(self._on_mpv_output)
        self._proc.finished.connect(self._on_mpv_finished)
        
        wid = int(self._video.winId())
        args = [
            "--no-config",
            "--force-window=yes",
            f"--wid={wid}",
            "--keep-open=no",
            "--cache=yes",
            "--demuxer-lavf-analyzeduration=2",
            "--hwdec=auto",
            "--msg-level=all=info",
            url,
        ]
        self._proc.start(self._mpv_path, args)

    def _on_mpv_output(self) -> None:
        """捕获 mpv 输出(调试用)"""
        if self._proc:
            out = bytes(self._proc.readAll()).decode("utf-8", errors="replace")
            if "error" in out.lower() or "failed" in out.lower():
                self._update_status(f"⚠️ mpv: {out[:100]}", warn=True)

    def _on_mpv_finished(self, exit_code: int, exit_status) -> None:
        """mpv 退出时更新状态"""
        if exit_code != 0:
            self._update_status(f"❌ mpv 退出(code {exit_code})", warn=True)
            self.failed.emit(f"mpv 退出,代码 {exit_code}")

    def stop(self) -> None:
        if self._proc:
            self._proc.kill()
            self._proc.waitForFinished(1500)
            self._proc = None
        if self._qt:
            self._qt.stop()
        self._stack.setCurrentWidget(self._placeholder)
        self._current_url = ""
        self._update_status("已停止")

    def _on_qt_error(self, *_):
        if self._qt:
            err = self._qt.errorString() or "播放失败"
            self._update_status(f"❌ Qt: {err}", warn=True)
            self.failed.emit(err)

    def _on_qt_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.started.emit()

    def backend_name(self) -> str:
        if self._mpv_path:
            return f"mpv ({self._mpv_path})"
        return "⚠️ Qt Multimedia(HEVC 会花屏,请装 mpv)"
