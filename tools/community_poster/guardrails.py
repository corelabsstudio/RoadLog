"""
도배 방지 · 안전 제한

- 하루 게시 시도 한도
- 성공 후 대기 시간
- 동일 본문 반복 경고
- 올리기 자동 클릭 재확인
- 최소 제목/본문 길이
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from product_config import (
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MAX_POSTS_PER_DAY,
    MIN_BODY_LEN,
    MIN_TITLE_LEN,
)

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data" / "guardrails_state.json"


@dataclass
class GuardResult:
    ok: bool
    message: str
    level: str = "info"  # info | warn | block


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"attempts": [], "last_body_hash": "", "last_attempt_ts": 0}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"attempts": [], "last_body_hash": "", "last_attempt_ts": 0}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def body_hash(title: str, body: str) -> str:
    raw = (title or "").strip() + "\n" + (body or "").strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def check_before_post(
    *,
    title: str,
    body: str,
    submit: bool,
    max_per_day: int = DEFAULT_MAX_POSTS_PER_DAY,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
    allow_duplicate: bool = False,
) -> GuardResult:
    title = (title or "").strip()
    body = (body or "").strip()

    if len(title) < MIN_TITLE_LEN:
        return GuardResult(False, f"제목이 너무 짧습니다. (최소 {MIN_TITLE_LEN}자)", "block")
    if len(body) < MIN_BODY_LEN:
        return GuardResult(
            False,
            f"본문이 너무 짧습니다. (최소 {MIN_BODY_LEN}자)\n"
            "「사이트 보고 홍보글 만들기」로 초안을 만든 뒤 수정해 주세요.",
            "block",
        )

    state = _load_state()
    now = time.time()
    day_ago = now - 86400
    attempts = [a for a in state.get("attempts", []) if a.get("ts", 0) >= day_ago]
    state["attempts"] = attempts

    if len(attempts) >= max_per_day:
        return GuardResult(
            False,
            f"오늘은 이미 {max_per_day}번 올리는 시도를 했습니다.\n"
            "계정이 막히지 않게 하루 횟수를 제한하고 있습니다.\n"
            "내일 다시 시도해 주세요.",
            "block",
        )

    # 대기는 '성공' 기준 — 실패 직후 재시도 가능
    last_ok_ts = float(state.get("last_ok_ts") or 0)
    cool_sec = max(0, int(cooldown_minutes) * 60)
    if last_ok_ts and cool_sec and (now - last_ok_ts) < cool_sec:
        left = int(cool_sec - (now - last_ok_ts))
        mins = max(1, (left + 59) // 60)
        return GuardResult(
            False,
            f"잠시 쉬어 주세요. 약 {mins}분 뒤에 다시 시도할 수 있습니다.\n"
            f"(글을 올린 뒤 {cooldown_minutes}분 대기 — 도배 방지)",
            "block",
        )

    h = body_hash(title, body)
    # 직전에 '성공'한 글과 동일할 때만 차단 (실패 후 같은 본문 재시도 허용)
    if not allow_duplicate and h and h == state.get("last_ok_body_hash"):
        return GuardResult(
            False,
            "직전에 올린 글과 제목·본문이 같습니다.\n"
            "「다른 버전 만들기」로 문장을 바꾼 뒤 올려 주세요.\n"
            "(같은 글을 여러 곳에 올리면 스팸으로 보일 수 있습니다)",
            "block",
        )

    if submit:
        return GuardResult(
            True,
            "「올리기」버튼까지 자동으로 누르도록 켜져 있습니다.\n"
            "내용·게시판·사이트 규칙을 확인한 뒤에만 진행하세요.",
            "warn",
        )

    return GuardResult(True, "안전 확인 통과", "info")


def record_attempt(
    *,
    title: str,
    body: str,
    site_url: str,
    ok: bool,
    action: str = "post",
) -> None:
    state = _load_state()
    now = time.time()
    attempts = [a for a in state.get("attempts", []) if a.get("ts", 0) >= now - 86400]
    attempts.append(
        {
            "ts": now,
            "site": (site_url or "")[:200],
            "ok": bool(ok),
            "action": action,
            "hash": body_hash(title, body),
        }
    )
    state["attempts"] = attempts
    state["last_attempt_ts"] = now
    # 하위 호환: last_body_hash는 유지하되, 성공 시에만 ok 해시/시각 갱신
    state["last_body_hash"] = body_hash(title, body)
    if ok:
        state["last_ok_ts"] = now
        state["last_ok_body_hash"] = body_hash(title, body)
    _save_state(state)


def today_stats() -> dict[str, int]:
    state = _load_state()
    now = time.time()
    attempts = [a for a in state.get("attempts", []) if a.get("ts", 0) >= now - 86400]
    return {
        "attempts": len(attempts),
        "ok": sum(1 for a in attempts if a.get("ok")),
        "fail": sum(1 for a in attempts if not a.get("ok")),
        "max_per_day": DEFAULT_MAX_POSTS_PER_DAY,
        "cooldown_minutes": DEFAULT_COOLDOWN_MINUTES,
    }
