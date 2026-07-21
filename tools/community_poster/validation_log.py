"""
성과 검증 로그 — 로컬 JSONL

판매 전 검증 지표:
- 시도 수 / 성공 수 / 채널별
- 메모(전환: 가입·문의 등) 수동 기록
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "data" / "validation_log.jsonl"
SUMMARY_PATH = ROOT / "data" / "validation_summary.json"


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_event(event: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    row.setdefault("ts", time.time())
    row.setdefault("at", _now_iso())
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    _refresh_summary()


def log_post_attempt(
    *,
    product_url: str,
    community_url: str,
    board_name: str,
    title: str,
    ok: bool,
    message: str,
    final_url: str = "",
    submit: bool = False,
    validation_mode: bool = True,
) -> None:
    append_event(
        {
            "type": "post_attempt",
            "product_url": product_url,
            "community_url": community_url,
            "board_name": board_name,
            "title": (title or "")[:120],
            "ok": ok,
            "message": (message or "")[:300],
            "final_url": final_url,
            "submit": submit,
            "validation_mode": validation_mode,
        }
    )


def log_note(note: str, *, kind: str = "memo") -> None:
    append_event({"type": kind, "note": (note or "")[:500]})


def log_conversion(note: str, source: str = "") -> None:
    """가입·문의 등 전환 메모."""
    append_event(
        {
            "type": "conversion",
            "note": (note or "")[:500],
            "source": (source or "")[:200],
        }
    )


def read_events(limit: int = 200) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows


def _refresh_summary() -> dict[str, Any]:
    events = read_events(5000)
    posts = [e for e in events if e.get("type") == "post_attempt"]
    ok = [e for e in posts if e.get("ok")]
    fail = [e for e in posts if not e.get("ok")]
    conv = [e for e in events if e.get("type") == "conversion"]
    by_site: dict[str, dict[str, int]] = {}
    for e in posts:
        key = (e.get("community_url") or "unknown")[:80]
        by_site.setdefault(key, {"ok": 0, "fail": 0})
        if e.get("ok"):
            by_site[key]["ok"] += 1
        else:
            by_site[key]["fail"] += 1

    rate = (len(ok) / len(posts) * 100.0) if posts else 0.0
    summary = {
        "updated_at": _now_iso(),
        "post_attempts": len(posts),
        "post_ok": len(ok),
        "post_fail": len(fail),
        "success_rate_pct": round(rate, 1),
        "conversions": len(conv),
        "by_community": by_site,
        "goal_success_rate_pct": 50.0,
        "goal_met": rate >= 50.0 and len(posts) >= 5,
    }
    try:
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return summary


def get_summary() -> dict[str, Any]:
    if SUMMARY_PATH.exists():
        try:
            return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _refresh_summary()


def summary_text() -> str:
    s = get_summary()
    lines = [
        f"홍보 결과 요약 (이 컴퓨터) · 마지막 갱신 {s.get('updated_at', '-')}",
        f"올린 시도: {s.get('post_attempts', 0)}번  ·  성공: {s.get('post_ok', 0)}  ·  실패: {s.get('post_fail', 0)}",
        f"성공률: {s.get('success_rate_pct', 0)}%  (목표: 50% 이상, 5번 이상 시도)",
        f"가입·문의 기록: {s.get('conversions', 0)}건",
        f"이번 주 목표: {'달성' if s.get('goal_met') else '아직 미달성'}",
    ]
    by = s.get("by_community") or {}
    if by:
        lines.append("올린 곳별:")
        for url, st in list(by.items())[:8]:
            lines.append(f"  · {url[:50]}  성공={st.get('ok', 0)} 실패={st.get('fail', 0)}")
    return "\n".join(lines)
