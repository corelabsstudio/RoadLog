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
FIRST_BONUS = 0.2       # 처음 충전하시는 분께 20% 더 (실제로 지급한다)
WELCOME_LAMPS = 300     # 가입 선물. 질문 열 번을 할 수 있는 양
ASK_LAMPS = 30          # 무냥이에게 한 번 더 물어보기 (askmenu.js 와 같은 값)
ASK_DAYS = 365          # 산 답을 다시 볼 수 있는 기간

# 🛑 결제가 열리는 날 True 로. 그때부터 리포트는 전부 단건 결제가 되고,
#    등불은 「무냥이에게 더 물어보기」 전용으로 남는다.
#    지금 켜면 결제가 안 되는 상태라 아무도 아무것도 못 연다.
PAY_PER_REPORT = False
WELCOME_DAYS = 30       # 지금 열어 보라고 주는 것이라 길게 두지 않는다

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
    # 혼자 보는 것
    "solo": 59,
    "god": 9,
    "year": 49,
    "charm": 49,
    "luck": 59,
    "money": 49,
    "life": 79,
    # 두 사람 — 시기
    "week": 19,
    "dday": 69,
    # 두 사람 — 재회
    "mind": 79,
    "full": 98,
    "bond": 89,
    "again": 59,
    "match": 79,
    # 두 사람 — 결정
    "ox": 89,
    "cool": 49,
    "marry": 95,
}

# 프리미엄 — 등불로 사지 않는다. 그 자리에서 결제하고 연다.
# 값은 원 단위다(등불 개수가 아니다). 프론트 products.js 와 같은 값이어야 한다.
PREMIUM_WON = {
    "great": 29000,
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
        "first_charge": not any(e.get("type") == "charge" for e in acc.get("ledger", [])),
        "first_bonus": int(FIRST_BONUS * 100),
    }


def ledger(email: str, limit: int = 50) -> list[dict]:
    acc = _account(_read(), email)
    return list(reversed(acc.get("ledger", [])))[:limit]


def is_first_charge(email: str) -> bool:
    """아직 한 번도 충전한 적이 없는가."""
    acc = _account(_read(), email)
    return not any(e.get("type") == "charge" for e in acc.get("ledger", []))


def charge(email: str, lamps: int, *, payment_id: str, price: int, note: str = "") -> dict:
    """충전. 같은 payment_id 가 이미 있으면 거절한다(중복 지급 방지)."""
    if lamps <= 0:
        raise ValueError("등불 수가 올바르지 않습니다.")
    data = _read()
    acc = _account(data, email)
    if any(e.get("payment_id") == payment_id for e in acc.get("ledger", [])):
        raise ValueError("이미 처리된 결제입니다.")

    # 첫 충전이면 더 얹어 준다. 정가를 부풀려 할인처럼 보이게 하지 않는다.
    first = not any(e.get("type") == "charge" for e in acc.get("ledger", []))
    bonus = int(lamps * FIRST_BONUS) if first else 0
    lamps += bonus

    now = _now()
    expires = now + timedelta(days=EXPIRE_DAYS)
    acc["lots"].append({
        "lamps": lamps, "remain": lamps,
        "at": _iso(now), "expires": _iso(expires),
        "payment_id": payment_id, "price": price,
    })
    acc["ledger"].append({
        "at": _iso(now), "type": "charge", "lamps": lamps,
        "price": price, "payment_id": payment_id, "bonus": bonus,
        "expires": _iso(expires), "note": note,
    })
    _write(data)
    return {
        "balance": sum(l["remain"] for l in _live_lots(acc, now)),
        "lamps": lamps, "bonus": bonus, "expires": _iso(expires),
    }


def welcome(email: str) -> dict:
    """가입 선물. 한 계정에 한 번만 나간다."""
    data = _read()
    acc = _account(data, email)
    if any(e.get("type") == "welcome" for e in acc.get("ledger", [])):
        return {"given": 0, "balance": sum(l["remain"] for l in _live_lots(acc))}
    now = _now()
    expires = now + timedelta(days=WELCOME_DAYS)
    acc["lots"].append({
        "lamps": WELCOME_LAMPS, "remain": WELCOME_LAMPS,
        "at": _iso(now), "expires": _iso(expires),
        "payment_id": "", "price": 0,
    })
    acc["ledger"].append({
        "at": _iso(now), "type": "welcome", "lamps": WELCOME_LAMPS,
        "price": 0, "expires": _iso(expires), "note": "가입 선물",
    })
    _write(data)
    return {
        "given": WELCOME_LAMPS,
        "balance": sum(l["remain"] for l in _live_lots(acc, now)),
        "expires": _iso(expires),
    }


def won_of(product: str) -> int:
    """단건 결제로 살 수 있는 값(원). 스위치를 켜면 모든 리포트가 여기에 들어온다."""
    if product in PREMIUM_WON:
        return PREMIUM_WON[product]
    if PAY_PER_REPORT and product in PRICES:
        return PRICES[product] * LAMP_WON
    return 0


def buy_premium(email: str, product: str, pair: str, *, payment_id: str, paid: int) -> dict:
    """한 건 결제. 등불은 건드리지 않는다."""
    won = won_of(product)
    if not won:
        raise ValueError("프리미엄 상품이 아닙니다.")
    if not _PAIR_RE.match(pair or ""):
        raise ValueError("잘못된 요청입니다.")
    if paid < won:
        raise ValueError("결제 금액이 상품 값보다 적습니다.")
    data = _read()
    acc = _account(data, email)
    if any(e.get("payment_id") == payment_id for e in acc.get("ledger", [])):
        raise ValueError("이미 처리된 결제입니다.")
    now = _now()
    expires = now + timedelta(days=OWNED_DAYS)
    if not any(o["product"] == product and o["pair"] == pair for o in _owned_live(acc, now)):
        acc["owned"].append({"product": product, "pair": pair, "at": _iso(now), "expires": _iso(expires)})
    acc["ledger"].append({
        "at": _iso(now), "type": "premium", "product": product, "pair": pair,
        "lamps": 0, "price": paid, "payment_id": payment_id, "expires": _iso(expires),
    })
    _write(data)
    return {"ok": True, "product": product, "expires": _iso(expires)}


def ask(email: str, qid: str, pair: str) -> dict:
    """무냥이에게 한 번 더 묻는다. 같은 질문을 다시 열면 등불을 안 쓴다.

    답은 서버가 만들지 않는다 — 브라우저에 있는 계산 블록이 그린다. 여기서는
    등불만 센다. 그래서 물어볼 때마다 바깥에 나가는 돈이 없다.
    """
    if not qid or len(qid) > 40:
        raise ValueError("잘못된 질문입니다.")
    if not _PAIR_RE.match(pair or ""):
        raise ValueError("잘못된 요청입니다.")
    key = f"ask:{qid}"
    data = _read()
    acc = _account(data, email)
    now = _now()
    if any(o["product"] == key and o["pair"] == pair for o in _owned_live(acc, now)):
        return {"ok": True, "spent": 0, "balance": sum(l["remain"] for l in _live_lots(acc, now)), "reopened": True}
    live = _live_lots(acc, now)
    have = sum(l["remain"] for l in live)
    if have < ASK_LAMPS:
        raise ValueError(f"등불이 모자랍니다. {ASK_LAMPS - have}개가 더 필요해요.")
    left = ASK_LAMPS
    for lot in sorted(live, key=lambda l: _parse(l["expires"])):
        take = min(left, lot["remain"])
        lot["remain"] -= take
        left -= take
        if not left:
            break
    acc["owned"].append({
        "product": key, "pair": pair, "at": _iso(now),
        "expires": _iso(now + timedelta(days=ASK_DAYS)),
    })
    acc["ledger"].append({
        "at": _iso(now), "type": "ask", "qid": qid, "pair": pair,
        "lamps": -ASK_LAMPS, "price": 0,
    })
    _write(data)
    return {"ok": True, "spent": ASK_LAMPS, "balance": sum(l["remain"] for l in _live_lots(acc, now)), "reopened": False}


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
