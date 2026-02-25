from __future__ import annotations
from pathlib import Path
import json
import time

def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def load_json(path: Path) -> dict:
    _ensure_parent(path)

    if not path.exists():
        path.write_text("{}", encoding="utf-8")
        return {}

    txt = path.read_text(encoding="utf-8").strip()
    if not txt:
        # empty file guard
        path.write_text("{}", encoding="utf-8")
        return {}

    try:
        data = json.loads(txt)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        # corruption guard: backup then reset
        backup = path.with_suffix(f".corrupt-{int(time.time())}.json")
        backup.write_text(txt, encoding="utf-8")
        path.write_text("{}", encoding="utf-8")
        return {}

def save_json(path: Path, data: dict) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
