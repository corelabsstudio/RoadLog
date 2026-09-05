# -*- coding: utf-8 -*-
"""상품별 손님 후기.

옛 랜딩용 reviews.py 는 관리자가 직접 써 넣는 것이라 이것과 다르다.
여기는 손님이 자기가 연 상품에 대해 남기는 후기다.

- 저장: DATA_DIR/reviews_products.json
- 자격: 그 상품을 실제로 연 사람만 (lamps.owns)
- 한 사람이 한 상품에 한 건. 다시 쓰면 덮어쓴다.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

PATH = DATA_DIR / "reviews_products.json"
_LOCK = threading.Lock()

MAX_TEXT = 300
MIN_TEXT = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> dict[str, list[dict[str, Any]]]:
    if not PATH.exists():
        return {}
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict[str, list[dict[str, Any]]]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(PATH)


def mask(nick: str, email: str) -> str:
    """이름은 첫 글자만 남긴다. 이름이 없으면 메일 앞 두 글자."""
    n = (nick or "").strip()
    if not n:
        n = (email or "").split("@")[0][:2]
    if len(n) <= 1:
        return n or "손님"
    return n[0] + "○" * (len(n) - 1)


def _public(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "nick": r.get("nick_masked") or "손님",
        "rating": r.get("rating", 5),
        "text": r.get("text", ""),
        "at": r.get("at", ""),
    }


def list_public(product: str, limit: int = 30) -> list[dict[str, Any]]:
    rows = [r for r in _read().get(product, []) if not r.get("hidden")]
    rows.sort(key=lambda r: r.get("at", ""), reverse=True)
    return [_public(r) for r in rows[:limit]]


def summary(product: str) -> dict[str, Any]:
    rows = [r for r in _read().get(product, []) if not r.get("hidden")]
    if not rows:
        return {"count": 0, "avg": 0}
    avg = sum(int(r.get("rating", 5)) for r in rows) / len(rows)
    return {"count": len(rows), "avg": round(avg, 1)}


def mine(product: str, email: str) -> dict[str, Any] | None:
    for r in _read().get(product, []):
        if r.get("email") == email:
            return {"rating": r.get("rating", 5), "text": r.get("text", "")}
    return None


def upsert(product: str, email: str, nick: str, rating: int, text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if len(text) < MIN_TEXT:
        raise ValueError(f"후기는 {MIN_TEXT}자 이상 써 주세요.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"후기는 {MAX_TEXT}자까지 쓸 수 있습니다.")
    try:
        rating = int(rating)
    except Exception:
        raise ValueError("별점이 올바르지 않습니다.")
    if not 1 <= rating <= 5:
        raise ValueError("별점은 1에서 5 사이입니다.")

    with _LOCK:
        data = _read()
        rows = data.setdefault(product, [])
        for r in rows:
            if r.get("email") == email:
                r.update({
                    "rating": rating, "text": text,
                    "nick_masked": mask(nick, email), "at": _now(),
                })
                _write(data)
                return _public(r)
        row = {
            "id": secrets.token_urlsafe(9),
            "email": email,
            "nick_masked": mask(nick, email),
            "rating": rating,
            "text": text,
            "at": _now(),
            "hidden": False,
        }
        rows.append(row)
        _write(data)
        return _public(row)


def remove(product: str, email: str) -> bool:
    with _LOCK:
        data = _read()
        rows = data.get(product, [])
        left = [r for r in rows if r.get("email") != email]
        if len(left) == len(rows):
            return False
        data[product] = left
        _write(data)
        return True


def set_hidden(product: str, review_id: str, hidden: bool) -> bool:
    """관리자용 — 신고된 후기를 가린다."""
    with _LOCK:
        data = _read()
        for r in data.get(product, []):
            if r.get("id") == review_id:
                r["hidden"] = bool(hidden)
                _write(data)
                return True
    return False
