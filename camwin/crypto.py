"""iPlayer 2.0.5 {sign, data} AES-128-CBC."""
from __future__ import annotations

import json
import subprocess
import tempfile
from base64 import b64decode
from pathlib import Path


def _decrypt_pycrypto(key: bytes, iv: bytes, cipher: bytes) -> bytes | None:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError:
        return None
    try:
        plain = AES.new(key, AES.MODE_CBC, iv).decrypt(cipher)
        try:
            plain = unpad(plain, 16)
        except ValueError:
            pass
        return plain
    except Exception:
        return None


def _decrypt_openssl(key: bytes, iv: bytes, cipher: bytes) -> bytes | None:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(cipher)
            path = f.name
        p = subprocess.run(
            ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", iv.hex(), "-in", path],
            capture_output=True,
            timeout=8,
        )
        Path(path).unlink(missing_ok=True)
        return p.stdout or None
    except Exception:
        return None


def decrypt_reload_payload(obj: dict) -> dict:
    sign = obj.get("sign")
    data = obj.get("data")
    if not isinstance(sign, str) or not isinstance(data, str) or len(sign.encode()) < 16:
        return obj
    try:
        cipher = b64decode(data)
    except Exception:
        return obj
    if len(cipher) < 16 or len(cipher) % 16:
        return obj
    key = sign.encode("utf-8")[:16]
    for iv in (key, b"\x00" * 16):
        plain = _decrypt_pycrypto(key, iv, cipher) or _decrypt_openssl(key, iv, cipher)
        if not plain:
            continue
        parsed = parse_possibly_corrupt_json(plain)
        if parsed:
            return parsed
    return obj


def parse_possibly_corrupt_json(raw: bytes) -> dict | None:
    try:
        obj = json.loads(raw.decode("utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    text = raw.decode("utf-8", "replace")
    for marker in ('"canPlay"', '"data"', '"mutableDuty"'):
        i = text.find(marker)
        if i >= 0:
            try:
                obj = json.loads("{" + text[i:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    return None
