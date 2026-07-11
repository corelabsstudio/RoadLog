"""
랜딩 페이지 사용자 후기(리뷰) 관리.
- 로컬 JSON 저장 (data/admin/reviews.json)
- 공개 목록 / 관리자 CRUD
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

ADMIN_DIR = DATA_DIR / "admin"
ADMIN_DIR.mkdir(parents=True, exist_ok=True)
REVIEWS_PATH = ADMIN_DIR / "reviews.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def default_reviews() -> list[dict[str, Any]]:
    """초기 시드 — 관리자가 수정·삭제 가능."""
    now = _now_iso()
    return [
        {
            "id": "seed-r1",
            "text": "방문지만 찍고 메모 몇 줄 남기면 제출용 문서로 정리돼서, 차 안에서 엑셀 붙잡고 있을 일이 줄었어요.",
            "text_en": "I stamp visits, leave a few notes, and get a submission-ready log. Less time wrestling Excel in the car.",
            "name": "김지훈",
            "name_en": "Jihun K.",
            "role": "영업 · 제조업",
            "role_en": "Sales · Manufacturing",
            "initial": "김",
            "stars": 5,
            "published": True,
            "sort_order": 10,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "seed-r2",
            "text": "법인차 일지를 매주 모으는데, 형식이 들쭉날쭉하지 않아서 팀 취합이 훨씬 편해졌습니다.",
            "text_en": "We collect company-vehicle logs weekly. Formats stay consistent, so team roll-up is much easier.",
            "name": "박서연",
            "name_en": "Seoyeon P.",
            "role": "총무 · 건설 현장",
            "role_en": "Admin · Construction sites",
            "initial": "박",
            "stars": 5,
            "published": True,
            "sort_order": 20,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "seed-r3",
            "text": "외근 동선이 많은 날에도 집에서 이어서 고칠 수 있어서, 퇴근 전에 급하게 쓰다 마는 일이 줄었어요.",
            "text_en": "On heavy field days I can finish at home. Fewer half-written logs right before clock-out.",
            "name": "이준호",
            "name_en": "Junho L.",
            "role": "외근 매니저 · 서비스",
            "role_en": "Field manager · Services",
            "initial": "이",
            "stars": 5,
            "published": True,
            "sort_order": 30,
            "created_at": now,
            "updated_at": now,
        },
    ]


def load_all_reviews() -> list[dict[str, Any]]:
    data = _read_json(REVIEWS_PATH, None)
    if data is None:
        seeded = default_reviews()
        _write_json(REVIEWS_PATH, seeded)
        return seeded
    if not isinstance(data, list):
        return []
    return data


def save_all_reviews(reviews: list[dict[str, Any]]) -> None:
    _write_json(REVIEWS_PATH, reviews)


def _sort_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        reviews,
        key=lambda r: (
            int(r.get("sort_order") or 0),
            str(r.get("created_at") or ""),
            str(r.get("id") or ""),
        ),
    )


def _public_review_view(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("id"),
        "text": r.get("text") or "",
        "text_en": r.get("text_en") or "",
        "name": r.get("name") or "",
        "name_en": r.get("name_en") or "",
        "role": r.get("role") or "",
        "role_en": r.get("role_en") or "",
        "initial": r.get("initial") or "",
        "stars": max(1, min(5, int(r.get("stars") or 5))),
        "sort_order": int(r.get("sort_order") or 0),
    }


def list_public_reviews() -> list[dict[str, Any]]:
    """공개 랜딩용 — published 만, 정렬."""
    out = []
    for r in _sort_reviews(load_all_reviews()):
        if not r.get("published", True):
            continue
        out.append(_public_review_view(r))
    return out


def list_admin_reviews() -> list[dict[str, Any]]:
    return _sort_reviews(load_all_reviews())


def _normalize_review_payload(
    payload: dict[str, Any],
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("후기 내용을 입력해 주세요.")
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("이름을 입력해 주세요.")
    role = (payload.get("role") or "").strip()
    initial = (payload.get("initial") or "").strip()
    if not initial:
        initial = name[0]
    try:
        stars = int(payload.get("stars") if payload.get("stars") is not None else 5)
    except (TypeError, ValueError) as e:
        raise ValueError("별점은 1~5 숫자여야 합니다.") from e
    stars = max(1, min(5, stars))
    try:
        sort_order = int(
            payload.get("sort_order")
            if payload.get("sort_order") is not None
            else (existing or {}).get("sort_order")
            or 0
        )
    except (TypeError, ValueError):
        sort_order = 0
    published = payload.get("published")
    if published is None:
        published = (existing or {}).get("published", True)
    published = bool(published)

    now = _now_iso()
    base = dict(existing or {})
    base.update(
        {
            "text": text,
            "text_en": (payload.get("text_en") or "").strip(),
            "name": name,
            "name_en": (payload.get("name_en") or "").strip(),
            "role": role,
            "role_en": (payload.get("role_en") or "").strip(),
            "initial": initial[:2],
            "stars": stars,
            "published": published,
            "sort_order": sort_order,
            "updated_at": now,
        }
    )
    if not base.get("id"):
        base["id"] = secrets.token_hex(8)
    if not base.get("created_at"):
        base["created_at"] = now
    return base


def create_review(payload: dict[str, Any]) -> dict[str, Any]:
    reviews = load_all_reviews()
    row = _normalize_review_payload(payload)
    if payload.get("sort_order") is None:
        max_ord = max((int(r.get("sort_order") or 0) for r in reviews), default=0)
        row["sort_order"] = max_ord + 10
    reviews.append(row)
    save_all_reviews(reviews)
    return row


def update_review(review_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rid = (review_id or "").strip()
    reviews = load_all_reviews()
    idx = next((i for i, r in enumerate(reviews) if str(r.get("id")) == rid), -1)
    if idx < 0:
        raise KeyError("후기를 찾을 수 없습니다.")
    row = _normalize_review_payload(payload, existing=reviews[idx])
    row["id"] = rid
    reviews[idx] = row
    save_all_reviews(reviews)
    return row


def delete_review(review_id: str) -> bool:
    rid = (review_id or "").strip()
    reviews = load_all_reviews()
    new_list = [r for r in reviews if str(r.get("id")) != rid]
    if len(new_list) == len(reviews):
        return False
    save_all_reviews(new_list)
    return True


def set_review_published(review_id: str, published: bool) -> dict[str, Any]:
    rid = (review_id or "").strip()
    reviews = load_all_reviews()
    for i, r in enumerate(reviews):
        if str(r.get("id")) == rid:
            r = {**r, "published": bool(published), "updated_at": _now_iso()}
            reviews[i] = r
            save_all_reviews(reviews)
            return r
    raise KeyError("후기를 찾을 수 없습니다.")
