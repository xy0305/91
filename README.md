# CamWin

Windows 11 桌面端，用来跑 **iPlayer 2.0.5 脚本**（`91zb.js` 那条链路）。

- 导入 `iplayer2://import?payload=…` 或 `.js` 地址
- JavaScript 约定：`iPlayerMain` + `iNetwork.get` + `iUI.reloadData`
- `{sign, data}` 用 AES-128-CBC 解密（key = `sign` 16 字节）
- 91zb 的 HTTPS FLV 是 **HEVC（FLV codec 12/13）**，本机先转成 MPEG-TS 再播

预置脚本：https://cdn.jsdelivr.net/gh/he1pu/iPlayerJS/91zb.js

## 环境

- Windows 11
- Python 3.10+（安装时勾选 Add to PATH）
- **强烈建议安装 [mpv](https://mpv.io/installation/)**（解 HEVC 最稳）
  - 或 winget：`winget install mpv`
  - 或 scoop：`scoop install mpv`
- 若用系统播放器：Microsoft Store 搜索 **HEVC Video Extensions**

## 运行

```bat
run.bat
```

第一次会 `pip install -r requirements.txt`（PySide6 + pycryptodome）。

或手动：

```bat
py -3 -m pip install -r requirements.txt
py -3 -m camwin
```

## 用法

1. 左侧已有「91直播」。点它会拉房间列表（封面、热度）。
2. 点房间即播放。本地 `127.0.0.1` 代理把 HEVC-FLV 转成 MPEG-TS。
3. 「导入」可粘贴原来的 `iplayer2://import?payload=…`。

## 播放后端

| 后端 | 何时用 |
|---|---|
| **mpv** | PATH 或常见安装目录里找到 `mpv.exe` 时优先 |
| Qt Multimedia | 没有 mpv 时兜底（需系统 HEVC 解码器） |

## 下载 exe

仓库：https://github.com/xy0305/91

GitHub Actions 在 `windows-latest` 上用 PyInstaller **onedir** 打包（不是 onefile，避免无控制台闪退）。

- Actions 产物：`CamWin-windows.zip`
- Release：https://github.com/xy0305/91/releases

解压后运行 `CamWin.exe`。出错不会默默退出：弹窗 + `%LOCALAPPDATA%\CamWin\crash.log`。

本地打包：

```bat
build.bat
```

或：

```bat
py -3 -m pip install -r requirements.txt pyinstaller
py -3 -m PyInstaller --noconfirm --clean CamWin.spec
```

## 目录

```
CamWin/
  run.bat
  requirements.txt
  camwin/
    app.py        主窗口
    engine.py     iPlayer 脚本 / 91zb AES
    crypto.py     AES-128-CBC
    remux.py      HEVC-FLV → MPEG-TS
    proxy.py      本地 TS 代理
    player.py     mpv / Qt 播放
    models.py     房间 / 导入 payload
    store.py      脚本列表（%LOCALAPPDATA%\CamWin）
```
