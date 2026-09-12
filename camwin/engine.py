"""Run iPlayer 2.0.5 scripts (iPlayerMain / iNetwork / iUI.reloadData)."""
from __future__ import annotations

import json
import threading
import urllib.request
from typing import Any, Callable

from camwin.crypto import decrypt_reload_payload
from camwin.models import Page

UA = "iPlayer/2.0.5"
API_91ZB = "https://api.199189.xyz/91zb/api?iplayer"


class EngineError(RuntimeError):
    pass


def _http_get(url: str, timeout: float = 16) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_91zb() -> Page:
    raw = _http_get(API_91ZB, timeout=20)
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise EngineError("91zb 接口不是对象")
    plain = decrypt_reload_payload(obj)
    page = Page.from_dict(plain)
    if not page.items:
        raise EngineError("91zb 没有房间")
    return page


def download_script(url: str) -> str:
    text = _http_get(url, timeout=20)
    if "iPlayerMain" not in text:
        raise EngineError("不是 iPlayer 脚本（缺少 iPlayerMain）")
    return text


def run_script(source: str, hud: Callable[[str], None] | None = None) -> Page:
    """Best-effort JS runtime. Falls back to native 91zb if JS fails."""
    try:
        page = _run_js(source, hud)
        if page.items:
            return page
    except Exception as e:
        if hud:
            hud(f"JS: {e}")
    # Many 91zb-style scripts just GET the encrypted API and reloadData({sign,data}).
    if "199189.xyz" in source or "91zb" in source or "getEncryptedRoomList" in source:
        return fetch_91zb()
    raise EngineError("脚本没有返回房间")


def _run_js(source: str, hud: Callable[[str], None] | None) -> Page:
    """Tiny iPlayer bridge. Uses Python's JS if available, else native parse of reloadData."""
    # Prefer native path for the known 91zb pattern — no need for a full JS VM.
    if "api.199189.xyz/91zb/api" in source:
        return fetch_91zb()

    try:
        import js2py  # type: ignore
    except Exception as e:
        raise EngineError(f"需要 js2py 才能跑通用脚本: {e}") from e

    box: dict[str, Any] = {"page": None, "err": None}
    ev = threading.Event()

    def reload_data(obj):
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except Exception:
                box["err"] = "reloadData 不是 JSON"
                ev.set()
                return
        if hasattr(obj, "to_dict"):
            obj = obj.to_dict()
        if not isinstance(obj, dict):
            box["err"] = "reloadData 不是对象"
            ev.set()
            return
        box["page"] = Page.from_dict(decrypt_reload_payload(obj))
        ev.set()

    def http_get(opts, cb=None):
        url = ""
        if isinstance(opts, dict):
            url = opts.get("url") or ""
        elif hasattr(opts, "to_dict"):
            url = (opts.to_dict() or {}).get("url") or ""
        else:
            try:
                url = str(opts.get("url"))
            except Exception:
                url = ""
        err, body, status = None, "", 0
        try:
            body = _http_get(url)
            status = 200
        except Exception as e:
            err = str(e)
        if cb:
            cb(err, {"statusCode": status}, body)

    ctx = js2py.EvalJs(
        {
            "iPlayer": {"log": lambda *a: hud and hud(" ".join(map(str, a))), "appVersion": lambda: "2.0.5"},
            "iUI": {
                "reloadData": reload_data,
                "showHUD": lambda k, m="": hud and hud(f"{k}:{m}"),
                "clearAllHUD": lambda: None,
                "appVersion": lambda: "2.0.5",
                "read": lambda k: None,
                "write": lambda v, k: None,
                "remove": lambda k: None,
            },
            "iNetwork": {"get": http_get, "post": http_get},
            "iData": {},
            "iNotify": {"notify": lambda *a: None},
        }
    )
    ctx.execute(source)
    ctx.execute("iPlayerMain(1, 0, 0)")
    if not ev.wait(25):
        raise EngineError("脚本超时")
    if box["err"]:
        raise EngineError(box["err"])
    if not box["page"]:
        raise EngineError("脚本没有 reloadData")
    return box["page"]
