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
        Path(r"C:\Program Files\mpv\mpv.exe"),
        Path(r"C:\Program Files (x86)\mpv\mpv.exe"),
        Path(r"C:\mpv\mpv.exe"),
        Path.home() / "scoop" / "apps" / "mpv" / "current" / "mpv.exe",
        Path.home() / "scoop" / "shims" / "mpv.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "mpv" / "mpv.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "mpv.exe",
    ]
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget.is_dir():
        extra.extend(winget.glob("**/mpv.exe"))
    for p in extra:
        try:
            if p.is_file():
                return str(p)
        except OSError:
            continue
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

        self._warn = QLabel()
        self._warn.setWordWrap(True)
        self._warn.setStyleSheet(
            "background:#5c3b00;color:#ffe9b0;padding:8px 10px;font-size:13px;"
        )
        if self._mpv_path:
            self._warn.hide()
        else:
            self._warn.setText(
                "未检测到 mpv。当前用系统播放器，91zb 的 HEVC 直播会花屏或没声。\n"
                "请安装：winget install mpv    然后重新打开 CamWin。"
            )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._warn)
        lay.addWidget(self._stack, 1)

        if not self._mpv_path:
            self._qt = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._qt.setAudioOutput(self._audio)
            self._qt.setVideoOutput(self._video)
            self._qt.errorOccurred.connect(self._on_qt_error)
            self._qt.playbackStateChanged.connect(self._on_qt_state)

    def has_mpv(self) -> bool:
        return bool(self._mpv_path)

    def play(self, url: str) -> None:
        self.stop()
        self._stack.setCurrentWidget(self._video)
        if self._mpv_path:
            self._play_mpv(url)
        elif self._qt:
            self._qt.setSource(QUrl(url))
            self._qt.play()
        else:
            self.failed.emit("没有可用的播放器。请安装 mpv：winget install mpv")

    def _play_mpv(self, url: str) -> None:
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        wid = int(self._video.winId())
        args = [
            "--force-window=no",
            f"--wid={wid}",
            "--keep-open=no",
            "--cache=yes",
            "--demuxer-lavf-o=live_start_index=-1",
            "--demuxer-lavf-analyzeduration=2",
            "--hwdec=auto",
            "--vd-lavc-o=flags=+low_delay",
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
        return f"mpv ({self._mpv_path})" if self._mpv_path else "Qt Multimedia（画面会花，请装 mpv）"
