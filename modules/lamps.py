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

import hashlib
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
# 🛑 **등불이 있는 만큼 다 쓰게 한다** (2026-09-11 온해님 「무한으로 쓰게해도 돼 등불」).
#    그전에는 복채를 낸 적 없는 분을 **평생 한 번**으로 막았다(FREE_ASKS = 1).
#    가입 선물 300개는 열 번짜리인데 한 번 쓰면 270개가 남은 채로 계속 막혔고,
#    화면 어디에도 그 말이 없어서 「등불이 왜 있는지 모르겠다」가 됐다.
#    이제 막는 것은 **잔액 하나**다. 300개면 열 번이고, 다 쓰면 그때 멈춘다.
#    🛑 인사·잡담은 등불을 안 쓴다(`modules/intent.py`). 남용은 그쪽에서 하루 20번으로 막는다.
ASK_DAYS = 365          # 산 답을 다시 볼 수 있는 기간

# 🛑 결제가 열리는 날 True 로. 그때부터 리포트는 전부 단건 결제가 되고,
#    등불은 「무냥이에게 더 물어보기」 전용으로 남는다.
#    지금 켜면 결제가 안 되는 상태라 아무도 아무것도 못 연다.
PAY_PER_REPORT = False
WELCOME_DAYS = 30       # 지금 열어 보라고 주는 것이라 길게 두지 않는다

# 데려온 분·따라온 분 양쪽에 준다. 광고비 없이 손님이 오게 하는 유일한 장치다.
# 🛑 **친구를 데려오는 값을 올렸다** (2026-09-11 온해님 「30개는 효과 없을 것 같아」).
#    30개는 무냥이에게 **한 번** 묻는 값이라 친구를 부를 이유가 안 됐다.
#    데려온 분 120개(네 번) · 따라온 분 60개(두 번)로 나눈다 — 수고한 쪽이 더 받는다.
#    원가는 초대 한 건에 **6원**이다 (등불 30개가 질문 한 번, 한 번이 1원 안팎).
REFER_LAMPS = 120       # 데려온 분
REFER_IN_LAMPS = 60     # 따라 들어온 분
REFER_DAYS = 30

# ── 배지 — 친구를 많이 데려온 순 1·2·3위 (2026-09-11 온해님) ──────────
# 🛑 **등불 보유량으로 매기지 않는다.** 등불로 순위를 매기면 「모으는 재화」로 보여서
#    포인트 충전 업종으로 읽힌다 — KG이니시스가 그 이유로 거절했다. 그리고 등불은
#    결제만 해도 쌓여서, 정작 초대를 안 한 사람이 1등이 된다.
# 🛑 **동점이면 먼저 도달한 쪽이 앞선다.** 안 그러면 순위가 새로고침마다 흔들린다.
RANK_BADGES = [("gold", "금"), ("silver", "은"), ("bronze", "동")]


def _refer_board(data: dict) -> list[tuple[int, str, str]]:
    """(데려온 수, 마지막 시각, 이메일) 을 순위대로. 한 명도 안 데려온 계정은 뺀다."""
    rows = []
    for em, acc in data.items():
        if not isinstance(acc, dict) or not isinstance(acc.get("ledger"), list):
            continue
        got = [e for e in acc["ledger"] if e.get("type") == "refer"]
        if got:
            rows.append((len(got), str(got[-1].get("at") or ""), em))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows


def refer_board(limit: int = 3) -> list[dict[str, Any]]:
    """윗자리 몇 분. 🛑 이메일을 그대로 내보내지 않는다 — 부르는 쪽에서 가린다."""
    out = []
    for i, (n, _at, em) in enumerate(_refer_board(_read())[:limit]):
        key, name = RANK_BADGES[i] if i < len(RANK_BADGES) else ("", "")
        out.append({"rank": i + 1, "count": n, "email": em, "key": key, "name": name})
    return out


def badge_of(email: str, data: dict | None = None) -> dict[str, Any]:
    """내 순위와 배지. 윗자리 셋 밖이면 배지가 없다."""
    board = _refer_board(data if data is not None else _read())
    em = (email or "").strip().lower()
    for i, (n, _at, who) in enumerate(board):
        if who != em:
            continue
        key, name = RANK_BADGES[i] if i < len(RANK_BADGES) else ("", "")
        # 한 자리 위로 가려면 몇 명이 더 필요한가
        need = 0
        if i > 0:
            need = max(1, board[i - 1][0] - n + 1)
        return {"key": key, "name": name, "rank": i + 1, "count": n,
                "upNeed": need, "upTo": i}
    # 아직 한 명도 안 데려온 분. 셋째 자리에 들려면 몇 명이 필요한가
    third = board[2][0] if len(board) > 2 else 0
    return {"key": "", "name": "", "rank": 0, "count": 0,
            "upNeed": max(1, third + 1), "upTo": 3}


# ── 무료 이용권 (2026-09-11 온해님 「친구 초대하면 1회 무료 보기권」) ─────
# 🛑 **깎아 주는 쿠폰이 아니다.** 한 편을 통째로 열어 준다 — 결제 금액이 화면과
#    달라지면 카드사 심사 「노출 금액 = 결제창 금액」에 걸린다 (`coupons.py` 와 같은 규칙).
# 🛑 **장수를 따로 저장하지 않는다.** 원장에 받은 것(`ticket`)과 쓴 것(`ticket-use`)이
#    남으므로 그 차가 남은 장수다. 값을 따로 두면 둘이 어긋난다.
TICKET_DAYS = 90


def tickets(email: str) -> dict[str, int]:
    acc = _account(_read(), email)
    led = acc.get("ledger", [])
    got = sum(1 for e in led if e.get("type") == "ticket")
    used = sum(1 for e in led if e.get("type") == "ticket-use")
    return {"got": got, "used": used, "left": max(0, got - used)}


def use_ticket(email: str, product: str, pair: str) -> dict:
    """무료 이용권 한 장으로 한 편을 연다."""
    if not _PAIR_RE.match(pair or ""):
        raise ValueError("잘못된 요청입니다.")
    data = _read()
    acc = _account(data, email)
    led = acc.get("ledger", [])
    left = (sum(1 for e in led if e.get("type") == "ticket")
            - sum(1 for e in led if e.get("type") == "ticket-use"))
    if left <= 0:
        raise ValueError("무료 이용권이 없어요. 친구를 데려오시면 한 장 드려요.")
    now = _now()
    expires = now + timedelta(days=OWNED_DAYS)
    if not any(o["product"] == product and o["pair"] == pair for o in _owned_live(acc, now)):
        acc["owned"].append({"product": product, "pair": pair,
                             "at": _iso(now), "expires": _iso(expires)})
    acc["ledger"].append({
        "at": _iso(now), "type": "ticket-use", "product": product, "pair": pair,
        "lamps": 0, "price": 0, "note": "친구 초대 무료 이용권", "expires": _iso(expires),
    })
    _write(data)
    return {"ok": True, "product": product, "expires": _iso(expires), "left": left - 1}


GIFT_DAYS = 90          # 복채를 내신 분께 얹어 드리는 등불. 선물이라 넉넉히 둔다
REFER_MAX = 20          # 한 계정이 받을 수 있는 횟수. 장난을 막는 선이다

# 🛑 등불 유료 충전은 닫았다 (2026-09-07).
#    KG이니시스가 「충전 결제식이라서」 거절했다. 사이트에서 「돈을 받고 포인트를 파는」
#    자리를 전부 없앴고, 서버도 여기서 막는다 — PACKS 가 비면 pack_for_amount 가 None 을
#    돌려주고 /api/lamps/charge 가 거절한다.
#    등불은 가입 선물·친구 추천으로 **무상 지급만** 한다. 리포트는 전부 건별 결제다.
#    🛑 되살리려면 PG 에 판매 방식 변경을 신고하고 재심사를 받아야 한다. 몰래 켜지 말 것.
#       (승인 뒤 몰래 바꾸면 가맹 해지·정산 보류 사유다)
PACKS: dict[int, int] = {}

# 상품별 등불 값 — 프론트와 같은 값을 서버에도 둔다
# 🛑 **복채 없이 여는 상품** (2026-09-11 온해님). 여기 적힌 것만 무료다.
#    「값표에 없으면 무료」로 판정하면 상품 id 에 오타가 난 순간 전부 무료가 된다.
FREE_PRODUCTS = {"today"}

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
# 🛑 처음부터 최고가로 걸면 안 팔렸을 때 값 탓인지 물건 탓인지 못 가른다.
#    2026-09-07 에 대점을 29,000 → 12,900 으로 내렸다. 팔리는 것을 보고 올린다.
#
# 🛑 **프론트 products.js 의 premium:true 와 이 표가 반드시 같아야 한다.**
#    한쪽만 고치면 결제창은 뜨는데 서버가 값을 몰라 거절한다.
#    아래 8개는 폭스바니 상단 프리미엄 10개와 짝이 맞는 상품이다 (2026-09-07).
# 🛑🛑 **여기부터가 진짜 매출이다** (2026-09-10).
#    테스트 채널이 걸려 있던 동안 포트원이 PAID 를 돌려줘서 서버가 리포트를 열어 줬지만
#    **돈은 안 들어왔다.** 9,800원어치 두 건이 그렇게 나갔고, 그대로 두면 매출이
#    영원히 9,800원 부풀려진 채로 보인다.
#    🛑 **원장은 지우지 않는다.** 그 손님들은 실제로 리포트를 받았고 그 사실도 남아야 한다.
#       매출을 **세는 쪽**에서만 뺀다 (modules/stats.py · modules/admin_ops.py).
REAL_PAY_FROM = "2026-09-08"     # 실연동 채널(NHN KCP)로 바꾼 날

# 🛑 **묶음 상품** — 한 번 결제로 여러 편이 열린다 (2026-09-10 온해님).
#    「1,000원만 더 보태면 둘 다 보네?」로 객단가를 올리는 자리다.
#    🛑 묶음 자체는 **리포트가 없다.** 값을 받고 안에 든 상품들을 열어 줄 뿐이다.
#    🛑 값은 아래 PREMIUM_WON 에도 넣어야 한다 — 없으면 서버가 결제를 거절한다.
BUNDLE = {
    "duo": ["past", "god"],      # 전생 + 수호신 (따로 사면 5,800원)
}

PREMIUM_WON = {
    "duo": 3900,
    "god": 2900,
    "past": 2900,
    "solo": 12800,
    "week": 1800,
    "dday": 14800,
    "newlove": 19800,
    "think": 14800,
    "loop": 19800,
    "block": 14800,
    "hour": 12800,
    "first": 19800,
    "mind": 19800,
    "great": 59800,
    "full": 29800,
    "bond": 27800,
    "ox": 27800,
    "year": 9800,
    "charm": 9800,
    "luck": 12800,
    "money": 9800,
    "life": 19800,
    "cool": 9800,
    "again": 12800,
    "marry": 29800,
    "match": 19800,
    "bed": 14800,
    "divorce": 29800,
    "secret": 27800,
    "queer": 19800,
    "eros": 14800,

    # 관상 — 얼굴 사진으로 보는 것 (roadlog-saju/gwansang.js 와 같아야 한다).
    # 🛑 여기 없으면 결제창은 뜨는데 **서버가 값을 몰라 거절**한다.
    #    화면엔 아무 설명도 안 나오고 그냥 안 열린다.
    "face_first": 2980,
    "face_me": 5800,
    "face_you": 5800,
    "face_love": 5800,
    "face_money": 5800,
    "face_all": 19800,
    "face_pair": 29800,
    "face_king": 39800,
    "face_flag": 5980,
    "face_read": 4980,
    "face_fix": 3980,
    "face_luck": 2980,
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
        # 🛑 「내 사주」에서 언제 산 것인지 보여 준다 (2026-09-09)
        "owned": [{"product": o["product"], "pair": o["pair"], "at": o.get("at", ""),
                   "expires": o["expires"]} for o in owned],
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


def refer_code(email: str) -> str:
    """계정마다 정해지는 추천 코드. 값을 따로 저장하지 않으려고 이메일에서 만든다."""
    key = "roadlog.refer." + email.strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def _email_of_code(data: dict, code: str) -> str | None:
    code = (code or "").strip().lower()
    if len(code) != 8:
        return None
    for em in data:
        if refer_code(em) == code:
            return em
    return None


def _add_lot(acc: dict, lamps: int, days: int, now: datetime, kind: str, note: str) -> str:
    expires = now + timedelta(days=days)
    acc["lots"].append({
        "lamps": lamps, "remain": lamps,
        "at": _iso(now), "expires": _iso(expires),
        "payment_id": "", "price": 0,
    })
    acc["ledger"].append({
        "at": _iso(now), "type": kind, "lamps": lamps,
        "price": 0, "expires": _iso(expires), "note": note,
    })
    return _iso(expires)


def refer_stats(email: str) -> dict:
    """내 추천 코드와, 지금까지 데려온 사람 수."""
    data = _read()
    acc = _account(data, email)
    got = [e for e in acc.get("ledger", []) if e.get("type") == "refer"]
    return {
        "code": refer_code(email),
        "count": len(got),
        "lamps": sum(e.get("lamps", 0) for e in got),
        "per": REFER_LAMPS,
        "perIn": REFER_IN_LAMPS,
        "max": REFER_MAX,
        "badge": badge_of(email, data),
        "tickets": tickets(email),
    }


def claim_refer(email: str, code: str) -> dict:
    """추천 코드를 나중에 넣는 길.

    소셜 로그인은 구글·카카오를 다녀오는 사이에 코드가 날아가므로, 들어온 뒤에
    한 번 넣을 수 있게 열어 둔다. **한 계정에 한 번만** 받는다.
    """
    email = (email or "").strip().lower()
    data = _read()
    acc = _account(data, email)
    if any(e.get("type") == "refer_in" for e in acc.get("ledger", [])):
        return {"given": 0, "why": "이미 받으셨어요."}
    inviter = _email_of_code(data, code)
    if not inviter or inviter == email:
        return {"given": 0, "why": "그런 코드가 없어요."}
    iacc = data.get(inviter)
    if iacc is None:
        return {"given": 0, "why": "그런 코드가 없어요."}
    if sum(1 for e in iacc.get("ledger", []) if e.get("type") == "refer") >= REFER_MAX:
        return {"given": 0, "why": "이 코드는 다 쓰였어요."}
    now = _now()
    _add_lot(acc, REFER_LAMPS, REFER_DAYS, now, "refer_in", "친구 따라 들어온 선물")
    _add_lot(iacc, REFER_LAMPS, REFER_DAYS, now, "refer", "친구를 데려온 선물")
    _write(data)
    return {"given": REFER_LAMPS, "balance": sum(l["remain"] for l in _live_lots(acc, now))}


def welcome(email: str, ref: str = "", via: str = "") -> dict:
    """가입 선물. 한 계정에 한 번만 나간다.

    추천 코드를 달고 들어오면 **데려온 분과 따라온 분 양쪽에** 등불을 더 준다.
    코드는 이메일에서 만들어지므로 따로 저장하는 값이 없다.
    """
    data = _read()
    acc = _account(data, email)
    # 🛑 **어디서 오셨는지를 계정에 남긴다** (2026-09-11). 전에는 원장 메모에만 적어서
    #    「스레드에서 온 사람이 얼마 썼나」를 셀 수가 없었다. 유입까지만 알고
    #    결제까지 못 이으면 어느 글을 또 써야 할지 정할 수 없다.
    #    🛑 개인을 가리키는 값은 안 담는다 — 매체 이름과 어느 링크였는지까지다.
    if via and not acc.get("via"):
        acc["via"] = str(via)[:80]
        _write(data)
    if any(e.get("type") == "welcome" for e in acc.get("ledger", [])):
        return {"given": 0, "balance": sum(l["remain"] for l in _live_lots(acc))}
    now = _now()
    expires = _add_lot(acc, WELCOME_LAMPS, WELCOME_DAYS, now, "welcome",
                       f"가입 선물 · {via}" if via else "가입 선물")

    bonus = 0
    ticket = 0
    inviter = _email_of_code(data, ref) if ref else None
    # 내 코드로 내가 들어오는 것은 안 된다. 데려온 쪽도 이미 있는 계정이어야 한다.
    if inviter and inviter != email.strip().lower():
        iacc = data.get(inviter)
        if iacc is not None:
            done = sum(1 for e in iacc.get("ledger", []) if e.get("type") == "refer")
            if done < REFER_MAX:
                bonus = REFER_IN_LAMPS
                _add_lot(acc, REFER_IN_LAMPS, REFER_DAYS, now, "refer_in", "친구 따라 들어온 선물")
                _add_lot(iacc, REFER_LAMPS, REFER_DAYS, now, "refer", "친구를 데려온 선물")
                # 🛑 **무료 이용권 한 장도 같이** (2026-09-11 온해님). 등불은 더 묻는
                #    자리에만 쓰는데, 이용권은 **리포트 한 편**을 통째로 연다.
                #    데려온 쪽에만 준다 — 수고한 사람에게 가는 값이다.
                iacc.setdefault("ledger", []).append({
                    "at": _iso(now), "type": "ticket", "lamps": 0, "price": 0,
                    "note": "친구를 데려온 선물 · 무료 이용권",
                    "expires": _iso(now + timedelta(days=TICKET_DAYS)),
                })
                ticket = 1

    _write(data)
    return {
        "given": WELCOME_LAMPS + bonus,
        "referred": bonus,
        # 🛑 **누가 데려왔는지 돌려준다** (2026-09-11). 서버가 그분께도 알림을 보내야
        #    한다 — 받은 줄 모르면 준 게 아니다. 여기서 알림을 직접 보내지 않는 것은
        #    등불 모듈이 알림 모듈을 물면 서로 물려 돌아가기 때문이다.
        "inviter": inviter if bonus else "",
        "inviterLamps": REFER_LAMPS if bonus else 0,
        "inviterTicket": ticket,
        "balance": sum(l["remain"] for l in _live_lots(acc, now)),
        "expires": expires,
    }


def won_of(product: str) -> int:
    """단건 결제로 살 수 있는 값(원). 스위치를 켜면 모든 리포트가 여기에 들어온다."""
    if product in PREMIUM_WON:
        return PREMIUM_WON[product]
    if PAY_PER_REPORT and product in PRICES:
        return PRICES[product] * LAMP_WON
    return 0


def bonus_lamps(won: int) -> int:
    """복채를 내면 등불도 함께 드린다.

    🛑 **2026-09-11 온해님 지시로 넉넉하게 올렸다** (「가격별로 등불을 넉넉히 줘도
       될 것 같아」). 그전에는 30·60·150 이라 29,800원을 내고도 다섯 번밖에 못 물었다.
       1:1 채팅이 재미있어야 다시 오는데, 다섯 번이면 재미를 보기도 전에 끝난다.

    등불은 파는 물건이 아니라 **정해진 현금 가치가 없다.** 다만 한 번 물을 때마다
    LLM 원가가 1원쯤 나가므로, 실제로 드는 돈은 아래 「원가」 칸이다.

        복채            등불     몇 번    원가
        ~4,900원         90      3번      3원
        5,000~9,900     180      6번      6원
        10,000~19,900   300     10번     10원
        20,000~29,900   600     20번     20원
        30,000원~     1,200     40번     40원

    가장 비싼 59,800원 상품에서도 원가가 40원이라 원가율에 0.07%p 남짓 붙는다.

    🛑 **세 곳이 같아야 한다** — 여기 · `products.js:giftLamps` · `pay.html:giftFor`.
       한 곳만 고치면 화면에 적힌 수와 실제로 들어오는 수가 달라진다.
       → `node tools/check_gift.mjs`
    """
    if won >= 30000:
        return 1200
    if won >= 20000:
        return 600
    if won >= 10000:
        return 300
    if won >= 5000:
        return 180
    return 90


def buy_premium(email: str, product: str, pair: str, *, payment_id: str, paid: int) -> dict:
    """한 건 결제. 복채를 내신 분께는 등불을 얹어 드린다."""
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
    # 🛑 묶음이면 **안에 든 상품을 전부** 연다. 묶음 자체는 리포트가 없어서,
    #    묶음 이름만 적어 두면 복채를 내고도 아무것도 못 본다 (2026-09-10)
    for pid in (BUNDLE.get(product) or [product]):
        if not any(o["product"] == pid and o["pair"] == pair for o in _owned_live(acc, now)):
            acc["owned"].append({"product": pid, "pair": pair,
                                 "at": _iso(now), "expires": _iso(expires)})
    gift = bonus_lamps(won)
    if gift:
        _add_lot(acc, gift, GIFT_DAYS, now, "premium-gift", "%s 결제 선물" % product)
    acc["ledger"].append({
        "at": _iso(now), "type": "premium", "product": product, "pair": pair,
        "lamps": gift, "price": paid, "payment_id": payment_id, "expires": _iso(expires),
    })
    _write(data)
    return {"ok": True, "product": product, "expires": _iso(expires), "lamps": gift}


def regift(*, apply: bool = False, skip: set[str] | None = None) -> dict:
    """등불 계단을 올렸을 때 **이미 복채를 내신 분께 차액을 드린다** (2026-09-11 온해님).

    > 이미 결제한 사람도 그에 맞춰서 올려주고

    🛑 **멱등하다.** 원장의 그 결제 항목에 `regift` 표시를 남기므로 두 번 돌려도
       두 번 주지 않는다. 표시가 없고 새 계단이 더 클 때만 **차액**을 얹는다.
    🛑 **`apply=False` 면 세어만 본다.** 얼마가 나가는지 보고 나서 실행한다.
    🛑 **환불된 결제는 건너뛴다.** 돌려받은 결제에 선물을 더 얹을 이유가 없다.
    """
    data = _read()
    now = _now()
    rows = []
    total = 0
    # 🛑 계정은 **맨 위에 이메일을 열쇠로** 놓여 있다 (`_account` 참고).
    #    `data["accounts"]` 같은 칸은 없다 — 있는 줄 알고 짜면 조용히 0명이 나온다.
    # 🛑 **주인·VIP 는 뺀다** (2026-09-11 온해님 「내 관리자 계정은 빼야지」).
    #    이분들은 복채를 안 내고 다 보시므로 차액을 드릴 것이 없고, 목록에 줄줄이
    #    뜨면 정작 봐야 할 손님이 묻힌다. 누가 그 계정인지는 서버가 넘겨 준다 —
    #    등불 모듈은 관리자 여부를 모른다.
    skip = {str(x).strip().lower() for x in (skip or set())}
    for email, acc in list(data.items()):
        if not isinstance(acc, dict) or not isinstance(acc.get("ledger"), list):
            continue
        if str(email).strip().lower() in skip:
            continue
        led = acc["ledger"]
        # 환불된 결제 번호는 미리 모아 둔다
        back = {e.get("payment_id") for e in led if e.get("type") == "refund"}
        for e in led:
            if e.get("type") != "premium" or e.get("regift"):
                continue
            if e.get("payment_id") in back:
                continue
            want = bonus_lamps(won_of(e.get("product") or "") or int(e.get("price") or 0))
            had = int(e.get("lamps") or 0)
            if want <= had:
                continue
            more = want - had
            rows.append({"email": email, "product": e.get("product"),
                         "had": had, "want": want, "more": more})
            total += more
            if apply:
                _add_lot(acc, more, GIFT_DAYS, now, "premium-gift",
                         "%s 결제 선물 더하기" % e.get("product"))
                e["regift"] = _iso(now)
                e["lamps"] = want

        # 🛑 **친구 초대 보상도 소급한다** (2026-09-11 온해님 「등불 30개씩 생긴 회원
        #    있던데」). 옛 규칙은 양쪽 30개였다. 지금은 데려온 분 120·따라온 분 60이고
        #    데려온 분에게는 **무료 이용권 한 장**도 드린다.
        #    🛑 이용권은 그때 아예 없던 것이라 **차액이 아니라 한 장을 새로 드린다.**
        # 🛑 **돌면서 그 목록에 넣지 않는다.** 이용권 한 줄을 `led` 에 바로 붙였더니
        #    순회가 끝나지 않았다 (2026-09-11 실측 · 무한 루프). 모아 뒀다 밖에서 붙인다.
        add_later = []
        for e in list(led):
            if e.get("regift"):
                continue
            kind = e.get("type")
            if kind == "refer":
                want, tag = REFER_LAMPS, "친구를 데려온 선물 더하기"
            elif kind == "refer_in":
                want, tag = REFER_IN_LAMPS, "친구 따라 들어온 선물 더하기"
            else:
                continue
            had = int(e.get("lamps") or 0)
            more = want - had
            if more <= 0 and kind != "refer":
                continue
            rows.append({"email": email, "product": kind,
                         "had": had, "want": want, "more": max(0, more)})
            total += max(0, more)
            if apply:
                if more > 0:
                    # 🛑 **타입을 `-more` 로 둔다** (2026-09-11 실측). `refer` 로 넣었더니
                    #    ① 그 줄에 `regift` 표시가 없어 **두 번째 실행에서 또 걸렸고**
                    #    ② `refer` 를 세는 초대 횟수·순위가 **부풀려졌다.**
                    _add_lot(acc, more, REFER_DAYS, now, kind + "-more", tag)
                if kind == "refer":
                    # 그때는 이용권이 없었다. 한 장 드린다
                    add_later.append({
                        "at": _iso(now), "type": "ticket", "lamps": 0, "price": 0,
                        "note": "친구를 데려온 선물 · 무료 이용권 (소급)",
                        "expires": _iso(now + timedelta(days=TICKET_DAYS)),
                    })
                e["regift"] = _iso(now)
                e["lamps"] = want
        led.extend(add_later)
    if apply and rows:
        _write(data)
    return {"applied": bool(apply), "people": len({r["email"] for r in rows}),
            "count": len(rows), "lamps": total, "rows": rows[:50]}


def refund(email: str, payment_id: str, *, why: str = "") -> dict:
    """돌려준 것을 원장에 남기고, 열어 둔 리포트를 닫는다 (2026-09-11).

    🛑 **원장에서 지우지 않는다.** 지우면 무슨 일이 있었는지가 사라진다.
       `refund` 항목을 하나 더 얹어서 **금액을 음수로** 적는다 — 매출이 저절로 준다.
    """
    data = _read()
    acc = _account(data, email)
    got = None
    for e in acc.get("ledger", []):
        if e.get("payment_id") == payment_id and e.get("type") in ("charge", "premium"):
            got = e
            break
    if not got:
        raise ValueError("그 결제를 찾지 못했습니다.")
    if any(e.get("type") == "refund" and e.get("payment_id") == payment_id
           for e in acc.get("ledger", [])):
        raise ValueError("이미 환불한 결제입니다.")

    now = _now()
    price = int(got.get("price") or 0)
    product = str(got.get("product") or "")
    pair = str(got.get("pair") or "")
    # 🛑 **열어 둔 것을 닫는다.** 돈은 돌려주고 글은 그대로 두면 안 된다.
    #    묶음이면 안에 든 것까지 다 닫는다.
    close = set(BUNDLE.get(product) or [product])
    acc["owned"] = [o for o in acc.get("owned", [])
                    if not (o.get("pair") == pair and o.get("product") in close)]
    acc["ledger"].append({
        "at": _iso(now), "type": "refund", "product": product, "pair": pair,
        "lamps": 0, "price": -price, "payment_id": payment_id,
        "note": (why or "관리자 환불")[:200],
    })
    _write(data)
    return {"ok": True, "product": product, "price": price}


def gift_used(email: str) -> dict | None:
    """선착순 이벤트로 이미 한 편을 여셨나. 열었으면 그 기록을 준다."""
    acc = _account(_read(), email)
    for e in reversed(acc.get("ledger", [])):
        if e.get("type") == "gift-open":
            return {"product": e.get("product"), "pair": e.get("pair"), "at": e.get("at")}
    return None


def gift_open(email: str, product: str, pair: str, *, note: str = "") -> dict:
    """선착순 이벤트로 한 편을 복채 없이 열어 드린다.

    🛑 결제가 아니다. 원장에 type="gift-open" 으로 남기고, **한 계정에 한 번만** 받는다.
       이미 받으셨는지도 이 기록으로 본다 — 따로 파일을 두지 않는다.
    """
    if not _PAIR_RE.match(pair or ""):
        raise ValueError("잘못된 요청입니다.")
    data = _read()
    acc = _account(data, email)
    if any(e.get("type") == "gift-open" for e in acc.get("ledger", [])):
        raise ValueError("이 이벤트는 한 분께 한 편만 열어 드려요.")
    now = _now()
    expires = now + timedelta(days=OWNED_DAYS)
    if not any(o["product"] == product and o["pair"] == pair for o in _owned_live(acc, now)):
        acc["owned"].append({"product": product, "pair": pair, "at": _iso(now), "expires": _iso(expires)})
    acc["ledger"].append({
        "at": _iso(now), "type": "gift-open", "product": product, "pair": pair,
        "lamps": 0, "price": 0, "note": note or "선착순 이벤트", "expires": _iso(expires),
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

    # 🛑 **횟수로 막지 않는다** (2026-09-11 온해님). 막는 것은 잔액 하나다.
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
