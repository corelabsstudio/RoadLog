# -*- coding: utf-8 -*-
"""Site visitor counter (unique browser via cookie, persisted under DATA_DIR)."""
from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

_LOCK = threading.Lock()
_FILE = Path(DATA_DIR) / "site_visitors.json"
COOKIE_NAME = "rl_vid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 400  # ~400 days


def _default() -> dict[str, Any]:
    return {
        "total": 0,
        "ids": {},  # id -> last_seen_ts (cap growth by pruning)
        "updated_at": 0,
    }


def _load() -> dict[str, Any]:
    try:
        if _FILE.is_file():
            data = json.loads(_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "total" in data:
                data.setdefault("ids", {})
                return data
    except Exception:
        pass
    return _default()


def _save(data: dict[str, Any]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(_FILE)


def _prune_ids(ids: dict[str, Any], keep: int = 50000) -> dict[str, Any]:
    """Keep newest entries if map grows too large (total count stays)."""
    if len(ids) <= keep:
        return ids
    items = sorted(ids.items(), key=lambda kv: float(kv[1] or 0), reverse=True)
    return {k: v for k, v in items[:keep]}


def get_total() -> int:
    with _LOCK:
        data = _load()
        return int(data.get("total") or 0)


def touch_visitor(visitor_id: str | None) -> tuple[int, str, bool]:
    """
    Register a visitor. Returns (total, visitor_id, is_new).
    New unique id increments total by 1.
    """
    now = time.time()
    with _LOCK:
        data = _load()
        ids: dict[str, Any] = dict(data.get("ids") or {})
        is_new = False
        vid = (visitor_id or "").strip()
        if not vid or vid not in ids:
            if not vid:
                vid = secrets.token_urlsafe(16)
            if vid not in ids:
                is_new = True
                data["total"] = int(data.get("total") or 0) + 1
            ids[vid] = now
        else:
            ids[vid] = now
        data["ids"] = _prune_ids(ids)
        data["updated_at"] = now
        _save(data)
        return int(data["total"]), vid, is_new
