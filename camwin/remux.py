"""Chinese HEVC-in-FLV (codec 12/13) + AAC → MPEG-TS."""
from __future__ import annotations

import struct
from typing import Iterator

PID_PAT, PID_PMT, PID_V, PID_A = 0x0000, 0x1000, 0x0100, 0x0101
HEVC, AAC = 0x24, 0x0F
AUD = b"\x00\x00\x00\x01\x46\x01\x50"
START = b"\x00\x00\x00\x01"


class _CC:
    def __init__(self) -> None:
        self.n: dict[int, int] = {}

    def next(self, pid: int) -> int:
        v = self.n.get(pid, 0)
        self.n[pid] = (v + 1) & 0xF
        return v


def _crc32(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= (b << 24) & 0xFFFFFFFF
        for _ in range(8):
            crc = (((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else (crc << 1)) & 0xFFFFFFFF
    return crc & 0xFFFFFFFF


def _pcr(pts90: int) -> bytes:
    b = pts90 & 0x1FFFFFFFF
    return bytes(
        [
            (b >> 25) & 0xFF,
            (b >> 17) & 0xFF,
            (b >> 9) & 0xFF,
            (b >> 1) & 0xFF,
            ((b & 1) << 7) | 0x7E,
            0x00,
        ]
    )


def _ts_write(cc: _CC, pid: int, payload: bytes, pusi: bool = True, pcr90: int | None = None) -> bytes:
    out = bytearray()
    data = payload
    first = True
    while data or (first and pcr90 is not None):
        pusi_bit = 1 if (pusi and first) else 0
        use_pcr = first and pcr90 is not None
        first = False
        adapt = bytearray()
        if use_pcr and pcr90 is not None:
            adapt = bytearray([0x10]) + _pcr(pcr90)
        if adapt or len(data) < 184:
            header_adapt = 1 + len(adapt)
            room = 184 - header_adapt
            take = min(len(data), max(room, 0))
            stuff = room - take
            if stuff > 0:
                if not adapt:
                    if stuff == 1:
                        body = bytes([0]) + data[: min(len(data), 183)]
                        take = min(len(data), 183)
                        data = data[take:]
                        ctrl = 3 if take else 2
                        hdr = bytes(
                            [0x47, (pusi_bit << 6) | ((pid >> 8) & 0x1F), pid & 0xFF, (ctrl << 4) | cc.next(pid)]
                        )
                        pkt = hdr + body
                        if len(pkt) < 188:
                            pkt += b"\xff" * (188 - len(pkt))
                        out += pkt[:188]
                        if not data:
                            break
                        continue
                    adapt = bytearray([0x00]) + b"\xff" * (stuff - 1)
                else:
                    adapt += b"\xff" * stuff
                take = min(len(data), 184 - 1 - len(adapt))
            field = bytes([len(adapt)]) + bytes(adapt)
            body = field + data[:take]
            data = data[take:]
            ctrl = 3 if take else 2
        else:
            take = 184
            body = data[:take]
            data = data[take:]
            ctrl = 1
        if len(body) < 184:
            body += b"\xff" * (184 - len(body))
        body = body[:184]
        hdr = bytes([0x47, (pusi_bit << 6) | ((pid >> 8) & 0x1F), pid & 0xFF, (ctrl << 4) | cc.next(pid)])
        out += hdr + body
        if not data:
            break
    return bytes(out)


def _pat() -> bytes:
    t = bytearray(b"\x00\xb0\x00\x00\x01\xc1\x00\x00")
    t += b"\x00\x01"
    t += bytes([0xE0 | ((PID_PMT >> 8) & 0x1F), PID_PMT & 0xFF])
    sl = len(t) - 3 + 4
    t[1] = 0xB0 | ((sl >> 8) & 0x0F)
    t[2] = sl & 0xFF
    t += struct.pack(">I", _crc32(t))
    return b"\x00" + bytes(t)


def _pmt() -> bytes:
    t = bytearray(b"\x02\xb0\x00\x00\x01\xc1\x00\x00")
    t += bytes([0xE0 | ((PID_V >> 8) & 0x1F), PID_V & 0xFF])
    t += b"\xf0\x00"
    t += bytes([HEVC, 0xE0 | ((PID_V >> 8) & 0x1F), PID_V & 0xFF, 0xF0, 0x00])
    t += bytes([AAC, 0xE0 | ((PID_A >> 8) & 0x1F), PID_A & 0xFF, 0xF0, 0x00])
    sl = len(t) - 3 + 4
    t[1] = 0xB0 | ((sl >> 8) & 0x0F)
    t[2] = sl & 0xFF
    t += struct.pack(">I", _crc32(t))
    return b"\x00" + bytes(t)


def _pes(sid: int, pts90: int, payload: bytes) -> bytes:
    pts90 &= 0x1FFFFFFFF
    pts = bytes(
        [
            0x20 | (((pts90 >> 30) & 7) << 1) | 1,
            (pts90 >> 22) & 0xFF,
            (((pts90 >> 15) & 0x7F) << 1) | 1,
            (pts90 >> 7) & 0xFF,
            ((pts90 & 0x7F) << 1) | 1,
        ]
    )
    h = bytes([0x00, 0x00, 0x01, sid, 0x00, 0x00, 0x80, 0x80, 5]) + pts + payload
    if sid != 0xE0:
        ln = len(h) - 6
        h = h[:4] + struct.pack(">H", ln & 0xFFFF) + h[6:]
    return h


def hvcc_to_annexb(hvcc: bytes) -> bytes:
    if len(hvcc) < 23:
        return b""
    i = 22
    n = hvcc[i]
    i += 1
    out = b""
    for _ in range(n):
        if i + 3 > len(hvcc):
            break
        i += 1
        cnt = struct.unpack(">H", hvcc[i : i + 2])[0]
        i += 2
        for _ in range(cnt):
            if i + 2 > len(hvcc):
                return out
            ln = struct.unpack(">H", hvcc[i : i + 2])[0]
            i += 2
            if i + ln > len(hvcc):
                return out
            out += START + hvcc[i : i + ln]
            i += ln
    return out


def length_to_annexb(data: bytes) -> bytes:
    out = b""
    i = 0
    while i + 4 <= len(data):
        ln = struct.unpack(">I", data[i : i + 4])[0]
        i += 4
        if ln <= 0 or i + ln > len(data):
            break
        out += START + data[i : i + ln]
        i += ln
    return out


def extract_nals(data: bytes) -> bytes:
    prefixed = length_to_annexb(data)
    if prefixed:
        return prefixed
    out = b""
    i = 0
    while i + 6 <= len(data):
        n = struct.unpack(">I", data[i : i + 4])[0]
        if 2 <= n <= len(data) - i - 4:
            nal = data[i + 4 : i + 4 + n]
            nuh = (nal[0] >> 1) & 0x3F
            if nal[0] & 0x80 == 0 and nuh <= 40:
                out += START + nal
                i += 4 + n
                continue
        i += 1
    return out


def aac_adts(asc: bytes, frame: bytes) -> bytes:
    if len(asc) < 2:
        return b""
    obj = (asc[0] >> 3) & 0x1F
    freq = ((asc[0] & 7) << 1) | ((asc[1] >> 7) & 1)
    ch = (asc[1] >> 3) & 0x0F
    profile = min(max(obj - 1, 0), 3)
    fl = 7 + len(frame)
    return (
        bytes(
            [
                0xFF,
                0xF1,
                ((profile & 3) << 6) | ((freq & 0xF) << 2) | ((ch >> 2) & 1),
                ((ch & 3) << 6) | ((fl >> 11) & 3),
                (fl >> 3) & 0xFF,
                ((fl & 7) << 5) | 0x1F,
                0xFC,
            ]
        )
        + frame
    )


class FLVToTS:
    def __init__(self) -> None:
        self.cc = _CC()
        self.vps = b""
        self.asc = b""
        self.header_done = False
        self.buf = b""
        self.nvideo = 0

    def psi(self) -> bytes:
        return _ts_write(self.cc, PID_PAT, _pat()) + _ts_write(self.cc, PID_PMT, _pmt())

    def feed(self, chunk: bytes) -> bytes:
        self.buf += chunk
        out = bytearray()
        if not self.header_done:
            if len(self.buf) < 13:
                return b""
            if self.buf[:3] != b"FLV":
                raise ValueError("not FLV")
            self.buf = self.buf[9:]
            self.header_done = True
            out += self.psi()
        while len(self.buf) >= 15:
            size = (self.buf[5] << 16) | (self.buf[6] << 8) | self.buf[7]
            need = 15 + size
            if len(self.buf) < need:
                break
            tag = self.buf[4]
            ts = (self.buf[8] << 16) | (self.buf[9] << 8) | self.buf[10] | (self.buf[11] << 24)
            payload = self.buf[15:need]
            self.buf = self.buf[need:]
            pts = ts * 90
            if tag == 9 and len(payload) >= 5:
                codec = payload[0] & 0x0F
                frame = (payload[0] >> 4) & 0x0F
                if codec in (12, 13):
                    pkt = payload[1]
                    data = payload[5:]
                    if codec == 12 and pkt == 0:
                        self.vps = hvcc_to_annexb(data)
                    elif pkt == 1 or codec == 13:
                        nal = extract_nals(data)
                        if not nal:
                            continue
                        if frame == 1 and self.vps:
                            nal = self.vps + nal
                        nal = AUD + nal
                        out += _ts_write(self.cc, PID_V, _pes(0xE0, pts, nal), True, pts)
                        self.nvideo += 1
                        if self.nvideo % 40 == 0:
                            out += self.psi()
            elif tag == 8 and len(payload) >= 2 and (payload[0] >> 4) == 10:
                if payload[1] == 0:
                    self.asc = payload[2:]
                elif payload[1] == 1 and self.asc:
                    adts = aac_adts(self.asc, payload[2:])
                    if adts:
                        out += _ts_write(self.cc, PID_A, _pes(0xC0, pts, adts), True)
        return bytes(out)


def iter_ts_from_http(url: str, headers: dict[str, str] | None = None) -> Iterator[bytes]:
    import urllib.request

    req = urllib.request.Request(url, headers=headers or {"User-Agent": "iPlayer/2.0.5", "Accept": "*/*"})
    mux = FLVToTS()
    with urllib.request.urlopen(req, timeout=20) as r:
        while True:
            chunk = r.read(32 * 1024)
            if not chunk:
                break
            ts = mux.feed(chunk)
            if ts:
                yield ts
