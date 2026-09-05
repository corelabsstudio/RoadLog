# -*- coding: utf-8 -*-
"""내 기록 — 사주를 본 뒤 어떻게 하기로 했는지, 30일 뒤 실제로 어떻게 됐는지.

**생년월일과 이름은 여기 오지 않는다.** 사이트가 「생년월일은 이 화면을 벗어나지
않습니다」라고 약속했고, 그 약속은 계정에 저장할 때도 그대로다. 서버에 남는 것은
이용자가 고른 항목, 직접 쓴 한 줄 메모, 어떤 사주를 봤는지 이름뿐이다.

브라우저에만 두던 것을 계정으로 옮긴 이유는 하나다 — 폰을 바꾸면 사라졌다.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

RECORDS_JSON = Path(DATA_DIR) / "records.json"
_LOCK = threading.Lock()

CHOICES = {"sent", "wait", "stop"}
FOLLOWUPS = {"met", "talk", "none", "quiet"}

MEMO_MAX = 200
PRODUCT_MAX = 40
PER_USER_MAX = 200
DUE_MS = 30 * 86_400_000        # 30일


def _now() -> int:
    return int(time.time() * 1000)


def _read() -> dict[str, list[dict[str, Any]]]:
    if not RECORDS_JSON.exists():
        return {}
    try:
        with open(RECORDS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict[str, Any]) -> None:
    RECORDS_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = RECORDS_JSON.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(RECORDS_JSON)


def _clean(r: dict[str, Any]) -> dict[str, Any]:
    """밖으로 나가는 모양. 저장한 것 말고는 아무것도 만들어 내지 않는다."""
    at = int(r.get("at") or 0)
    return {
        "id": str(r.get("id") or ""),
        "at": at,
        "choice": r.get("choice") or "",
        "memo": r.get("memo") or "",
        "product": r.get("product") or "",
        "followup": r.get("followup") or "",
        "followupAt": int(r.get("followupAt") or 0) or None,
        # 30일이 지났고 아직 결과를 안 고른 것
        "due": (not r.get("followup")) and at > 0 and (_now() - at) >= DUE_MS,
    }


def listing(email: str) -> dict[str, Any]:
    rows = [_clean(r) for r in _read().get(email, [])]
    rows.sort(key=lambda r: r["at"], reverse=True)
    return {"items": rows, "due": len([r for r in rows if r["due"]])}


def add(email: str, choice: str, memo: str = "", product: str = "") -> dict[str, Any]:
    if choice not in CHOICES:
        raise ValueError("고른 항목이 올바르지 않습니다.")
    row = {
        "id": uuid.uuid4().hex[:12],
        "at": _now(),
        "choice": choice,
        "memo": (memo or "").strip()[:MEMO_MAX],
        "product": (product or "").strip()[:PRODUCT_MAX],
        "followup": "",
        "followupAt": 0,
    }
    with _LOCK:
        data = _read()
        rows = data.setdefault(email, [])
        rows.append(row)
        if len(rows) > PER_USER_MAX:            # 오래된 것부터 버린다
            del rows[:len(rows) - PER_USER_MAX]
        _write(data)
    return _clean(row)


def follow_up(email: str, rid: str, value: str) -> dict[str, Any]:
    if value not in FOLLOWUPS:
        raise ValueError("고른 항목이 올바르지 않습니다.")
    with _LOCK:
        data = _read()
        for r in data.get(email, []):
            if str(r.get("id")) == str(rid):
                r["followup"] = value
                r["followupAt"] = _now()
                _write(data)
                return _clean(r)
    raise KeyError("그 기록을 찾을 수 없습니다.")


def remove(email: str, rid: str) -> bool:
    with _LOCK:
        data = _read()
        rows = data.get(email, [])
        left = [r for r in rows if str(r.get("id")) != str(rid)]
        if len(left) == len(rows):
            return False
        data[email] = left
        _write(data)
        return True


def merge_in(email: str, items: list[dict[str, Any]]) -> int:
    """브라우저에만 있던 옛 기록을 계정으로 옮긴다. 로그인할 때 한 번 부른다.

    같은 시각·같은 선택이 이미 있으면 건너뛴다 — 두 번 눌러도 안 겹치게.
    """
    if not isinstance(items, list):
        return 0
    moved = 0
    with _LOCK:
        data = _read()
        rows = data.setdefault(email, [])
        seen = {(int(r.get("at") or 0), r.get("choice")) for r in rows}
        for it in items[:PER_USER_MAX]:
            if not isinstance(it, dict):
                continue
            choice = it.get("choice")
            at = int(it.get("at") or 0)
            if choice not in CHOICES or at <= 0 or (at, choice) in seen:
                continue
            fu = it.get("followup") if it.get("followup") in FOLLOWUPS else ""
            rows.append({
                "id": uuid.uuid4().hex[:12],
                "at": at,
                "choice": choice,
                # 생년월일은 옮기지 않는다 — 애초에 서버에 둘 값이 아니다
                "memo": str(it.get("memo") or "").strip()[:MEMO_MAX],
                "product": str(it.get("product") or "").strip()[:PRODUCT_MAX],
                "followup": fu,
                "followupAt": int(it.get("followupAt") or 0),
            })
            seen.add((at, choice))
            moved += 1
        if moved:
            if len(rows) > PER_USER_MAX:
                del rows[:len(rows) - PER_USER_MAX]
            _write(data)
    return moved
