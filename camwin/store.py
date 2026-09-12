from __future__ import annotations

import json
from pathlib import Path

from camwin.models import BUNDLED_91ZB, Script, parse_iplayer_import


def _path() -> Path:
    root = Path.home() / "AppData" / "Local" / "CamWin"
    root.mkdir(parents=True, exist_ok=True)
    return root / "scripts.json"


class ScriptStore:
    def __init__(self) -> None:
        self.scripts: list[Script] = []
        self.load()

    def load(self) -> None:
        p = _path()
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                self.scripts = [Script.from_dict(x) for x in raw if isinstance(x, dict)]
            except Exception:
                self.scripts = []
        if not self.scripts:
            self.scripts = [BUNDLED_91ZB]
            self.save()

    def save(self) -> None:
        _path().write_text(
            json.dumps([s.to_dict() for s in self.scripts], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, script: Script) -> Script:
        for i, s in enumerate(self.scripts):
            if s.url == script.url:
                script.id = s.id
                self.scripts[i] = script
                self.save()
                return script
        self.scripts.insert(0, script)
        self.save()
        return script

    def remove(self, script: Script) -> None:
        self.scripts = [s for s in self.scripts if s.id != script.id]
        if not self.scripts:
            self.scripts = [BUNDLED_91ZB]
        self.save()

    def import_text(self, text: str) -> Script | None:
        s = parse_iplayer_import(text)
        if not s:
            return None
        return self.add(s)
