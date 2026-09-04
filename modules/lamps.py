"""등불(선불 재화) 잔액·원장.

로드로그 사주 리포트를 여는 데 쓰는 사내 재화다. 등불 1개 = 100원.

설계 원칙
- **생년월일은 서버로 보내지 않는다.** 어떤 두 사람에 대한 리포트인지는
  브라우저가 만든 해시(`pair`)로만 구분한다. 서버는 그 해시가 무엇인지 모른다.
- 충전분마다 만료일을 둔다(기본 1년). 토스페이먼츠의 포인트 충전 입점 조건이
  「서비스 제공기간 1년 이내」라서다.
- 차감은 **만료가 임박한 것부터**(FIFO) 한다. 이용자에게 유리하다.
- 한 번 연 리포트는 같은 두 사람·같은 상품에 한해 12개월 동안 다시 열 수 있다.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR

LAMPS_JSON = Path(DATA_DIR) / "lamps.json"

LAMP_WON = 100          # 등불 1개 = 100원
EXPIRE_DAYS = 365       # 충전분 유효기간
OWNED_DAYS = 365        # 산 리포트 재열람 기간

# 충전 패키지 — 결제 금액으로 어느 패키지인지 판정한다 (프론트 값을 믿지 않는다)
PACKS = {
    1900: 20,
    4700: 50,
    9200: 100,
    26000: 300,
    56000: 700,
}

# 상품별 등불 값 — 프론트와 같은 값을 서버에도 둔다
PRICES = {
    "solo": 59,
    "week": 19,
    "dday": 69,
    "mind": 79,
    "full": 98,
    "bond": 89,
    "ox": 89,
}

_PAIR_RE = re.compile(r"^[0-9a-f]{16,64}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(s: str) -> datetime:
    try:
        d = datetime.fromisoformat(s)
    except Exception:
        return _now()
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _read() -> dict[str, Any]:
    if not LAMPS_JSON.exists():
        return {}
    try:
        with open(LAMPS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(data: dict[str, Any]) -> None:
    LAMPS_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAMPS_JSON.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(LAMPS_JSON)


def _account(data: dict, email: str) -> dict:
    return data.setdefault(
        email.strip().lower(),
        {"lots": [], "ledger": [], "owned": []},
    )


def _live_lots(acc: dict, now: datetime | None = None) -> list[dict]:
    now = now or _now()
    return [l for l in acc.get("lots", []) if l.get("remain", 0) > 0 and _parse(l["expires"]) > now]


def balance(email: str) -> int:
    acc = _account(_read(), email)
    return sum(l["remain"] for l in _live_lots(acc))


def _owned_live(acc: dict, now: datetime | None = None) -> list[dict]:
    now = now or _now()
    return [o for o in acc.get("owned", []) if _parse(o["expires"]) > now]


def status(email: str) -> dict:
    data = _read()
    acc = _account(data, email)
    now = _now()
    lots = _live_lots(acc, now)
    owned = _owned_live(acc, now)
    soonest = min((_parse(l["expires"]) for l in lots), default=None)
    return {
        "balance": sum(l["remain"] for l in lots),
        "lamp_won": LAMP_WON,
        "expires_soonest": _iso(soonest) if soonest else None,
        "expiring_lamps": sum(
            l["remain"] for l in lots
            if _parse(l["expires"]) < now + timedelta(days=30)
        ),
        "owned": [{"product": o["product"], "pair": o["pair"], "expires": o["expires"]} for o in owned],
        "prices": PRICES,
    }


def ledger(email: str, limit: int = 50) -> list[dict]:
    acc = _account(_read(), email)
    return list(reversed(acc.get("ledger", [])))[:limit]


def charge(email: str, lamps: int, *, payment_id: str, price: int, note: str = "") -> dict:
    """충전. 같은 payment_id 가 이미 있으면 거절한다(중복 지급 방지)."""
    if lamps <= 0:
        raise ValueError("등불 수가 올바르지 않습니다.")
    data = _read()
    acc = _account(data, email)
    if any(e.get("payment_id") == payment_id for e in acc.get("ledger", [])):
        raise ValueError("이미 처리된 결제입니다.")

    now = _now()
    expires = now + timedelta(days=EXPIRE_DAYS)
    acc["lots"].append({
        "lamps": lamps, "remain": lamps,
        "at": _iso(now), "expires": _iso(expires),
        "payment_id": payment_id, "price": price,
    })
    acc["ledger"].append({
        "at": _iso(now), "type": "charge", "lamps": lamps,
        "price": price, "payment_id": payment_id,
        "expires": _iso(expires), "note": note,
    })
    _write(data)
    return {"balance": sum(l["remain"] for l in _live_lots(acc, now)), "lamps": lamps, "expires": _iso(expires)}


def owns(email: str, product: str, pair: str) -> bool:
    acc = _account(_read(), email)
    return any(o["product"] == product and o["pair"] == pair for o in _owned_live(acc))


def spend(email: str, product: str, pair: str) -> dict:
    """리포트를 연다. 이미 산 것이면 등불을 쓰지 않는다."""
    if product not in PRICES:
        raise ValueError("없는 상품입니다.")
    if not _PAIR_RE.match(pair or ""):
        raise ValueError("잘못된 요청입니다.")

    data = _read()
    acc = _account(data, email)
    now = _now()

    if any(o["product"] == product and o["pair"] == pair for o in _owned_live(acc, now)):
        return {"ok": True, "spent": 0, "balance": sum(l["remain"] for l in _live_lots(acc, now)), "reopened": True}

    need = PRICES[product]
    lots = sorted(_live_lots(acc, now), key=lambda l: _parse(l["expires"]))
    have = sum(l["remain"] for l in lots)
    if have < need:
        raise ValueError(f"등불이 {need - have}개 모자랍니다.")

    left = need
    for lot in lots:
        if left <= 0:
            break
        take = min(lot["remain"], left)
        lot["remain"] -= take
        left -= take

    expires = now + timedelta(days=OWNED_DAYS)
    acc["owned"].append({"product": product, "pair": pair, "at": _iso(now), "expires": _iso(expires)})
    acc["ledger"].append({
        "at": _iso(now), "type": "spend", "lamps": -need,
        "product": product, "pair": pair,
    })
    _write(data)
    return {
        "ok": True, "spent": need, "reopened": False,
        "balance": sum(l["remain"] for l in _live_lots(acc, now)),
        "expires": _iso(expires),
    }


def grant(email: str, lamps: int, note: str) -> dict:
    """운영자가 주는 등불(사과·보상·체험). 결제와 구분해 원장에 남긴다."""
    data = _read()
    acc = _account(data, email)
    now = _now()
    expires = now + timedelta(days=EXPIRE_DAYS)
    acc["lots"].append({
        "lamps": lamps, "remain": lamps,
        "at": _iso(now), "expires": _iso(expires),
        "payment_id": None, "price": 0, "granted": True,
    })
    acc["ledger"].append({"at": _iso(now), "type": "grant", "lamps": lamps, "note": note})
    _write(data)
    return {"balance": sum(l["remain"] for l in _live_lots(acc, now))}


def pack_for_amount(amount: int) -> int | None:
    """결제 금액으로 지급할 등불 수를 정한다. 목록에 없는 금액은 지급하지 않는다."""
    return PACKS.get(int(amount))
