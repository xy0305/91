from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse
from base64 import b64decode
import json
import uuid


def _s(d: dict, *keys: str) -> str | None:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            return v
        return str(v)
    return None


@dataclass
class Room:
    name: str
    address: str | None = None
    image: str | None = None
    plat: str | None = None
    room_id: str | None = None
    room_name: str | None = None
    anchor_id: str | None = None
    hot: str | None = None
    type_info: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Room":
        return cls(
            name=_s(d, "name", "title") or "未命名",
            address=_s(d, "address", "url"),
            image=_s(d, "image", "coverImage"),
            plat=_s(d, "plat", "platform"),
            room_id=_s(d, "roomId"),
            room_name=_s(d, "roomName"),
            anchor_id=_s(d, "anchorId"),
            hot=_s(d, "hot"),
            type_info=_s(d, "typeInfo"),
        )

    @property
    def title(self) -> str:
        return self.name or self.room_name or "未命名"

    @property
    def viewers(self) -> str:
        return self.hot or "0"


@dataclass
class Page:
    title: str = ""
    can_play: bool = True
    items: list[Room] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Page":
        raw = d.get("data") or []
        items = [Room.from_dict(x) for x in raw if isinstance(x, dict)]
        return cls(
            title=str(d.get("title") or ""),
            can_play=bool(d.get("canPlay", True)),
            items=items,
        )


@dataclass
class Script:
    id: str
    name: str
    url: str
    platform: str = ""
    cover: str | None = None
    added_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "platform": self.platform,
            "cover": self.cover,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        return cls(
            id=str(d.get("id") or ""),
            name=str(d.get("name") or "未命名"),
            url=str(d.get("url") or ""),
            platform=str(d.get("platform") or ""),
            cover=d.get("cover"),
            added_at=str(d.get("added_at") or ""),
        )


def parse_iplayer_import(text: str) -> Script | None:
    text = text.strip()
    payload = None
    if "payload=" in text:
        payload = text.split("payload=", 1)[1]
        if "&" in payload:
            payload = payload.split("&", 1)[0]
        payload = unquote(payload)
    elif text.startswith("ey"):
        payload = text
    elif text.lower().endswith(".js") or ".js?" in text.lower():
        name = urlparse(text).path.rsplit("/", 1)[-1].removesuffix(".js")
        return Script(id=uuid.uuid4().hex[:12], name=name or "脚本", url=text)
    if not payload:
        return None
    b64 = payload.replace("-", "+").replace("_", "/")
    b64 += "=" * ((4 - len(b64) % 4) % 4)
    try:
        obj = json.loads(b64decode(b64))
    except Exception:
        return None
    if not isinstance(obj, dict) or not obj.get("url"):
        return None
    name = obj.get("roomName") or obj.get("name") or obj.get("platform") or "脚本"
    return Script(
        id=uuid.uuid4().hex[:12],
        name=str(name),
        url=str(obj["url"]),
        platform=str(obj.get("platform") or ""),
        cover=obj.get("coverImage"),
    )


BUNDLED_91ZB = Script(
    id="bundled-91zb",
    name="91直播",
    url="https://cdn.jsdelivr.net/gh/he1pu/iPlayerJS/91zb.js",
    platform="tg@ishared",
    cover="https://cdn.jsdelivr.net/gh/he1pu/iPlayerJS/images/91zb.png",
)
