"""손님이 운영자에게 남기는 피드백 보관함.

접수 내용은 운영 화면에서만 읽는다. IP 같은 접속 정보는 저장하지 않고,
로그인한 손님이 보낸 경우에만 계정 이메일을 함께 남겨 답변이 필요할 때 찾을 수 있다.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import threading
import uuid
from pathlib import Path
from typing import Any

MAX_ITEMS = 500


class FeedbackStoreError(RuntimeError):
    """기존 접수 파일이 손상돼 덮어쓰면 안 되는 경우."""


def _path() -> Path:
    from modules.config import DATA_DIR

    root = Path(DATA_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root / "feedback.json"


_LOCK = threading.RLock()


def _locked(fn):
    @functools.wraps(fn)
    def wrap(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)
    return wrap


def _read() -> list[dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FeedbackStoreError("피드백 보관함 파일을 읽지 못했습니다.") from exc
    if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
        raise FeedbackStoreError("피드백 보관함 형식이 올바르지 않습니다.")
    return raw


def _write(rows: list[dict[str, Any]]) -> None:
    path = _path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _kst_now() -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


@_locked
def submit(message: str, page: str = "", reporter: str = "") -> dict[str, Any]:
    rows = _read()
    row = {
        "id": uuid.uuid4().hex,
        "message": message,
        "page": page,
        "reporter": reporter.strip().lower(),
        "at": _kst_now(),
        "read": False,
    }
    rows.append(row)
    _write(rows[-MAX_ITEMS:])
    return row


@_locked
def listing(limit: int = 100) -> dict[str, Any]:
    rows = sorted(_read(), key=lambda row: str(row.get("at") or ""), reverse=True)
    return {
        "items": rows[:max(1, min(int(limit), MAX_ITEMS))],
        "unread": sum(1 for row in rows if not row.get("read")),
        "total": len(rows),
    }


@_locked
def mark_read(ids: list[str] | None = None) -> int:
    rows = _read()
    wanted = set(ids or [])
    changed = 0
    for row in rows:
        if row.get("read") or (wanted and row.get("id") not in wanted):
            continue
        row["read"] = True
        changed += 1
    if changed:
        _write(rows)
    return changed
