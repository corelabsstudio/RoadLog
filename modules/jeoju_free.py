"""가입 없는 저주 보관함과 무료 생성량 제한. 기존 구매 기록과 분리한다."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request, Response
from modules.config import DATA_DIR

COOKIE = "rl_jeoju_guest"
COOKIE_AGE = 365 * 86400
DAILY_CAP = max(1, int(os.getenv("JEOJU_FREE_DAILY_CAP", "1000")))
_USAGE = DATA_DIR / "jeoju_free_usage.json"
_LOCK = threading.Lock()
_STRIPES = [threading.Lock() for _ in range(64)]
_SLOTS = threading.BoundedSemaphore(4)


def owner(request: Request, response: Response | None = None) -> str | None:
    value = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        if response is None:
            return None
        value = secrets.token_hex(32)
    if response is not None:
        response.set_cookie(COOKIE, value, max_age=COOKIE_AGE, httponly=True,
                            secure=request.url.scheme == "https", samesite="lax", path="/")
    return "guest:" + hashlib.sha256(value.encode()).hexdigest()


def lock_for(visitor: str):
    return _STRIPES[int(visitor[-4:], 16) % len(_STRIPES)]


def budget(change: int) -> None:
    """서버 전체 일일 호출 예약. 실패는 돌려주며 재시작 후에도 합계를 유지한다."""
    day = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    with _LOCK:
        state = json.loads(_USAGE.read_text("utf-8")) if _USAGE.exists() else {}
        used = int(state.get("used", 0)) if state.get("day") == day else 0
        if change > 0 and used >= DAILY_CAP:
            raise HTTPException(429, "오늘은 무냥이가 주문을 많이 받았어요. 내일 다시 와 주세요.")
        _USAGE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _USAGE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"day": day, "used": max(0, used + change)}), "utf-8")
        tmp.replace(_USAGE)


def ads_config() -> dict:
    # 2026-10-13 실제 애드센스 계정 화면에서 확인한 공개 게시자 번호.
    client = os.getenv("ADSENSE_CLIENT", "ca-pub-2523025753289844").strip()
    if not re.fullmatch(r"ca-pub-\d{16}", client):
        client = "ca-pub-2523025753289844"
    slot = os.getenv("ADSENSE_SLOT", "1812158500").strip()
    if not re.fullmatch(r"\d{10}", slot):
        slot = "1812158500"  # RoadLog K-Curse Result, created in the real AdSense account.
    enabled = os.getenv("JEOJU_ADS_ENABLED", "1") == "1"
    return {"enabled": enabled, "client": client, "slot": slot if enabled else ""}


# Google-certified consent is not yet configured for these jurisdictions.
# Do not send an ad request there merely because non-personalized ads were selected.
CONSENT_COUNTRIES = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IS IE IT LV LI LT LU MT NL NO PL PT RO SK SI ES SE GB CH".split())
