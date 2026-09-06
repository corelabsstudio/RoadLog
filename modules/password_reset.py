"""비밀번호 재설정 토큰 — 발급 · 만료 · 1회용.

결제가 붙는 서비스라 계정을 잃으면 충전해 둔 등불까지 같이 잃는다.
그래서 되찾는 길을 열어 두되, 그 길이 남의 계정으로 들어가는 문이 되면 안 된다.

지켜야 하는 것
- 🛑 **토큰 원본은 저장하지 않는다.** 파일이 새어도 그것만으로는 못 쓰게
  sha256 만 남긴다. 등불 잔액이 들어 있는 계정이라 이 값이 곧 돈이다.
- **한 번 쓰면 닫는다.** 메일함이 나중에 털려도 이미 쓴 링크는 안 열린다.
- **새로 발급하면 앞의 것은 죽는다.** 살아 있는 링크가 여러 개 떠다니지 않게.
- 30분이면 닫는다. 메일이 늦게 도착하는 경우를 감안한 선이다.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR

RESETS_JSON = Path(DATA_DIR) / "password_resets.json"

TTL_MIN = 30            # 링크가 열려 있는 시간
KEEP_HOURS = 24         # 쓴 것·만료된 것을 이만큼만 두고 치운다 (재사용 시도를 보려고)
MAX_LIVE_PER_DAY = 5    # 한 계정에 하루 몇 통까지. 메일 폭탄으로 쓰이지 않게


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(s: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _digest(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _read() -> dict[str, Any]:
    if not RESETS_JSON.exists():
        return {}
    try:
        raw = json.loads(RESETS_JSON.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _write(data: dict[str, Any]) -> None:
    RESETS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESETS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _purge(data: dict[str, Any]) -> dict[str, Any]:
    """다 쓴 것·오래된 것을 치운다. 파일이 무한정 자라지 않게."""
    cutoff = _now() - timedelta(hours=KEEP_HOURS)
    out = {}
    for h, rec in data.items():
        if not isinstance(rec, dict):
            continue
        born = _parse(rec.get("created_at") or "")
        if born and born < cutoff:
            continue
        out[h] = rec
    return out


def issue(email: str, *, ip: str = "") -> tuple[str, str]:
    """새 토큰. (토큰, 사유) — 토큰이 빈 문자열이면 사유를 본다."""
    email = (email or "").strip().lower()
    if not email:
        return "", "이메일이 없습니다."

    data = _purge(_read())

    # 하루에 몇 통까지. 남의 메일함을 두드리는 데 쓰이지 않게 막는다
    day_ago = _now() - timedelta(days=1)
    recent = 0
    for h, rec in list(data.items()):
        if (rec.get("email") or "") != email:
            continue
        born = _parse(rec.get("created_at") or "")
        if born and born >= day_ago:
            recent += 1
        # 이 계정의 살아 있는 앞선 토큰은 죽인다 — 링크는 늘 한 개만
        if not rec.get("used_at"):
            rec["used_at"] = _iso(_now())
            rec["voided"] = True
    if recent >= MAX_LIVE_PER_DAY:
        _write(data)
        return "", "오늘은 재설정 메일을 너무 많이 보냈습니다. 내일 다시 시도해 주세요."

    token = secrets.token_urlsafe(32)
    data[_digest(token)] = {
        "email": email,
        "created_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(minutes=TTL_MIN)),
        "used_at": "",
        "ip": (ip or "")[:45],
    }
    _write(data)
    return token, ""


def _look(token: str) -> tuple[bool, str, str]:
    """(쓸 수 있나, 이메일, 사유)"""
    if not token:
        return False, "", "링크가 올바르지 않아요."
    rec = _read().get(_digest(token))
    if not isinstance(rec, dict):
        return False, "", "이미 쓰였거나 만료된 링크예요. 다시 요청해 주세요."
    if rec.get("used_at"):
        return False, "", "이미 쓰인 링크예요. 다시 요청해 주세요."
    exp = _parse(rec.get("expires_at") or "")
    if not exp or exp < _now():
        return False, "", f"{TTL_MIN}분이 지나 닫힌 링크예요. 다시 요청해 주세요."
    return True, (rec.get("email") or ""), ""


def peek(token: str) -> tuple[bool, str, str]:
    """쓰지 않고 확인만. 화면이 폼을 그릴지 말지 정할 때."""
    return _look(token)


def consume(token: str) -> tuple[bool, str, str]:
    """확인하고 바로 닫는다. 비밀번호를 실제로 바꾸기 직전에 부른다."""
    ok, email, why = _look(token)
    if not ok:
        return False, "", why
    data = _read()
    rec = data.get(_digest(token))
    if not isinstance(rec, dict) or rec.get("used_at"):
        # 같은 순간에 두 번 눌린 경우. 먼저 온 쪽만 통과시킨다
        return False, "", "이미 쓰인 링크예요. 다시 요청해 주세요."
    rec["used_at"] = _iso(_now())
    data[_digest(token)] = rec
    _write(data)
    return True, email, ""
