"""Play remuxed MPEG-TS. Prefer mpv (HEVC), else Qt Multimedia."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess, QUrl, Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget


def find_mpv() -> str | None:
    exe = shutil.which("mpv")
    if exe:
        return exe
    for p in (
        Path(r"C:\Program Files\mpv\mpv.exe"),
        Path(r"C:\mpv\mpv.exe"),
        Path.home() / "scoop" / "apps" / "mpv" / "current" / "mpv.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "mpv" / "mpv.exe",
    ):
        if p.exists():
            return str(p)
    return None


class PlayerWidget(QWidget):
    started = Signal()
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mpv_path = find_mpv()
        self._proc: QProcess | None = None
        self._qt: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None

        self._stack = QStackedWidget()
        self._placeholder = QLabel("选择房间开始播放")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color:#aaa;font-size:16px;background:#111;")
        self._video = QVideoWidget()
        self._video.setStyleSheet("background:#000;")
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._video)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._stack)

        if not self._mpv_path:
            self._qt = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._qt.setAudioOutput(self._audio)
            self._qt.setVideoOutput(self._video)
            self._qt.errorOccurred.connect(self._on_qt_error)
            self._qt.playbackStateChanged.connect(self._on_qt_state)

    def play(self, url: str) -> None:
        self.stop()
        self._stack.setCurrentWidget(self._video)
        if self._mpv_path:
            self._play_mpv(url)
        elif self._qt:
            self._qt.setSource(QUrl(url))
            self._qt.play()
        else:
            self.failed.emit("没有可用的播放器。请安装 mpv。")

    def _play_mpv(self, url: str) -> None:
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        wid = int(self._video.winId())
        args = [
            "--force-window=no",
            f"--wid={wid}",
            "--keep-open=no",
            "--cache=yes",
            "--demuxer-lavf-analyzeduration=3",
            "--demuxer-lavf-probesize=1000000",
            "--hwdec=auto-safe",
            url,
        ]
        self._proc.start(self._mpv_path, args)
        self.started.emit()

    def stop(self) -> None:
        if self._proc:
            self._proc.kill()
            self._proc.waitForFinished(1500)
            self._proc = None
        if self._qt:
            self._qt.stop()
        self._stack.setCurrentWidget(self._placeholder)

    def _on_qt_error(self, *_):
        if self._qt:
            self.failed.emit(self._qt.errorString() or "播放失败")

    def _on_qt_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.started.emit()

    def backend_name(self) -> str:
        return f"mpv ({self._mpv_path})" if self._mpv_path else "Qt Multimedia"
