"""Local HTTP proxy: HEVC-FLV → MPEG-TS for Windows players."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from camwin.remux import iter_ts_from_http

UA = "iPlayer/2.0.5"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A003
        return

    def do_GET(self):  # noqa: N802
        q = parse_qs(urlparse(self.path).query)
        origin = (q.get("u") or [None])[0]
        if not origin:
            self.send_error(400, "missing u")
            return
        origin = unquote(origin)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp2t")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for chunk in iter_ts_from_http(origin, {"User-Agent": UA, "Accept": "*/*"}):
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
        except Exception:
            try:
                self.send_error(502, "upstream")
            except Exception:
                pass


class TSProxy:
    def __init__(self) -> None:
        self._httpd: ThreadingHTTPServer | None = None
        self.port = 0
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        if self._httpd:
            return self.port
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd = httpd
        self.port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        self._thread = t
        return self.port

    def play_url(self, origin: str) -> str:
        self.start()
        from urllib.parse import quote
        return f"http://127.0.0.1:{self.port}/live.ts?u={quote(origin, safe='')}"

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None


PROXY = TSProxy()
