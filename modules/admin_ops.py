"""
사이트 소유자(관리자) 전용 운영 기능
- 일/월 매출 집계
- 구독 요금 변경
- VIP(평생 무료) 회원 관리
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from modules.config import (
    DATA_DIR,
    ENTERPRISE_PRICE_KRW,
    FREE_MONTHLY_LIMIT,
    PRO_PRICE_KRW,
)
from modules import db

ADMIN_DIR = DATA_DIR / "admin"
ADMIN_DIR.mkdir(parents=True, exist_ok=True)

BILLING_CONFIG_PATH = ADMIN_DIR / "billing_config.json"
VIP_MEMBERS_PATH = ADMIN_DIR / "vip_members.json"


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 요금 설정 ─────────────────────────────────────────


def default_billing_config() -> dict[str, Any]:
    return {
        "pro_price_krw": PRO_PRICE_KRW,
        "enterprise_price_krw": ENTERPRISE_PRICE_KRW,
        "updated_at": None,
        "updated_by": None,
    }


def load_billing_config() -> dict[str, Any]:
    data = _read_json(BILLING_CONFIG_PATH, {})
    base = default_billing_config()
    if not data:
        _write_json(BILLING_CONFIG_PATH, base)
        return base
    merged = {**base, **data}
    # 초기 시드 가격(9,900 / 89,000 등)이고 관리자가 직접 저장한 적 없으면
    # 현재 config 런칭가로 한 번 맞춘다. (배포 서버 data 볼륨 대응)
    pro = int(merged.get("pro_price_krw") or 0)
    ent = int(merged.get("enterprise_price_krw") or 0)
    seed_prices = {8900, 9900, 89000, 99000}
    if not merged.get("updated_by") and (pro in seed_prices or ent in seed_prices):
        merged = {
            **merged,
            "pro_price_krw": PRO_PRICE_KRW,
            "enterprise_price_krw": ENTERPRISE_PRICE_KRW,
            "updated_at": _now_iso(),
            "updated_by": "launch_price_migration",
        }
        _write_json(BILLING_CONFIG_PATH, merged)
    return merged


def save_billing_config(
    pro_price: int,
    enterprise_price: int,
    updated_by: str = "",
) -> dict[str, Any]:
    if pro_price < 0 or enterprise_price < 0:
        raise ValueError("금액은 0 이상이어야 합니다.")
    cfg = {
        "pro_price_krw": int(pro_price),
        "enterprise_price_krw": int(enterprise_price),
        "updated_at": _now_iso(),
        "updated_by": updated_by,
    }
    _write_json(BILLING_CONFIG_PATH, cfg)
    return cfg


def get_pro_price() -> int:
    return int(load_billing_config().get("pro_price_krw") or PRO_PRICE_KRW)


def get_enterprise_price() -> int:
    return int(load_billing_config().get("enterprise_price_krw") or ENTERPRISE_PRICE_KRW)


# ── VIP (평생 무료) ───────────────────────────────────


def load_vip_members() -> list[dict[str, Any]]:
    data = _read_json(VIP_MEMBERS_PATH, [])
    if not isinstance(data, list):
        return []
    return data


def save_vip_members(members: list[dict[str, Any]]) -> None:
    _write_json(VIP_MEMBERS_PATH, members)


def _norm_id(s: str) -> str:
    return (s or "").strip().lower()


def is_vip(login_id_or_email: str) -> bool:
    key = _norm_id(login_id_or_email)
    if not key:
        return False
    for m in load_vip_members():
        if _norm_id(m.get("id") or "") == key:
            return True
        if _norm_id(m.get("email") or "") == key:
            return True
    return False


def add_vip(
    member_id: str,
    email: str = "",
    note: str = "",
    added_by: str = "",
) -> dict[str, Any]:
    mid = _norm_id(member_id)
    if not mid:
        raise ValueError("VIP 아이디(또는 이메일)를 입력해 주세요.")
    members = load_vip_members()
    for m in members:
        if _norm_id(m.get("id")) == mid or _norm_id(m.get("email")) == mid:
            raise ValueError("이미 VIP로 등록된 계정입니다.")
    row = {
        "id": mid,
        "email": _norm_id(email) if email else (mid if "@" in mid else ""),
        "note": (note or "").strip(),
        "added_at": _now_iso(),
        "added_by": added_by,
        "lifetime_free": True,
    }
    members.append(row)
    save_vip_members(members)
    # 존재 시 plan pro 로 맞춰 한도 해제
    target_email = row["email"] or mid
    if "@" in target_email:
        try:
            db.set_user_plan(target_email, "pro")
        except Exception:
            pass
    return row


def remove_vip(member_id: str) -> bool:
    mid = _norm_id(member_id)
    members = load_vip_members()
    new_list = [
        m
        for m in members
        if _norm_id(m.get("id")) != mid and _norm_id(m.get("email")) != mid
    ]
    if len(new_list) == len(members):
        return False
    save_vip_members(new_list)
    return True


def enrich_user_flags(user: dict | None) -> dict | None:
    """로그인 유저에 VIP/관리자 플래그 보강."""
    if not user:
        return user
    email = user.get("email") or ""
    uid = email.split("@")[0] if email else ""
    vip = is_vip(email) or is_vip(uid)
    user = {**user, "is_vip": vip}
    if vip:
        user["plan"] = "pro"
        user["lifetime_free"] = True
    return user


# ── 매출 집계 ─────────────────────────────────────────


def _parse_day(paid_at: str) -> str:
    """YYYY-MM-DD"""
    if not paid_at:
        return ""
    s = str(paid_at)
    if "T" in s:
        return s.split("T")[0][:10]
    return s[:10]


def _parse_ymd(s: str | None) -> str:
    """유효한 YYYY-MM-DD 만 반환, 아니면 빈 문자열."""
    if not s:
        return ""
    s = str(s).strip()[:10]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return ""


def revenue_dashboard(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    일매출 · 월매출 + 기간별 날짜 합산.

    date_from / date_to: YYYY-MM-DD (포함 구간)
    미지정 시 기본 = 이번 달 1일 ~ 오늘
    """
    all_p = db.get_all_payments()
    now = datetime.now()
    month_key = now.strftime("%Y-%m")
    today = now.strftime("%Y-%m-%d")
    month_start = now.strftime("%Y-%m-01")

    d_from = _parse_ymd(date_from) or month_start
    d_to = _parse_ymd(date_to) or today
    if d_from > d_to:
        d_from, d_to = d_to, d_from

    by_day: dict[str, int] = {}
    by_day_count: dict[str, int] = {}
    by_month: dict[str, int] = {}
    month_payments = []
    day_payments = []
    range_payments = []

    for p in all_p:
        amt = int(p.get("amount") or 0)
        m = p.get("month") or ""
        if not m and p.get("paid_at"):
            m = str(p.get("paid_at"))[:7]
        day = _parse_day(p.get("paid_at") or "")
        if m:
            by_month[m] = by_month.get(m, 0) + amt
        if day:
            by_day[day] = by_day.get(day, 0) + amt
            by_day_count[day] = by_day_count.get(day, 0) + 1
        if m == month_key:
            month_payments.append(p)
        if day == today:
            day_payments.append(p)
        if day and d_from <= day <= d_to:
            range_payments.append(p)

    range_revenue = sum(int(p.get("amount") or 0) for p in range_payments)
    range_count = len(range_payments)

    # 선택 기간 날짜별 매출 (빈 날 포함)
    daily_breakdown = []
    try:
        start_dt = datetime.strptime(d_from, "%Y-%m-%d")
        end_dt = datetime.strptime(d_to, "%Y-%m-%d")
    except ValueError:
        start_dt = now.replace(day=1)
        end_dt = now
    cur = start_dt
    # 기간이 너무 길면(예: 400일+) 빈 날 채우기 생략하고 매출 있는 날만
    span_days = (end_dt - start_dt).days + 1
    if span_days <= 120:
        while cur <= end_dt:
            key = cur.strftime("%Y-%m-%d")
            daily_breakdown.append(
                {
                    "date": key,
                    "revenue": by_day.get(key, 0),
                    "count": by_day_count.get(key, 0),
                }
            )
            cur += timedelta(days=1)
    else:
        for key in sorted(k for k in by_day if d_from <= k <= d_to):
            daily_breakdown.append(
                {
                    "date": key,
                    "revenue": by_day.get(key, 0),
                    "count": by_day_count.get(key, 0),
                }
            )

    # 최근 14일 (참고용 트렌드)
    daily_trend = []
    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_trend.append(
            {
                "date": d,
                "revenue": by_day.get(d, 0),
                "count": by_day_count.get(d, 0),
            }
        )

    # 최근 6개월
    monthly_trend = []
    for i in range(5, -1, -1):
        y, m = now.year, now.month - i
        while m <= 0:
            m += 12
            y -= 1
        key = f"{y:04d}-{m:02d}"
        monthly_trend.append({"month": key, "revenue": by_month.get(key, 0)})

    users = db.list_users()
    pro_count = sum(1 for u in users if u.get("plan") == "pro")
    vip_list = load_vip_members()

    # 결제일 기준 정렬 (최신순)
    range_payments_sorted = sorted(
        range_payments,
        key=lambda x: str(x.get("paid_at") or ""),
        reverse=True,
    )

    usage_stats = usage_dashboard(month=month_key)

    return {
        "today": today,
        "month": month_key,
        "date_from": d_from,
        "date_to": d_to,
        "day_revenue": by_day.get(today, 0),
        "month_revenue": by_month.get(month_key, 0),
        "day_payment_count": len(day_payments),
        "month_payment_count": len(month_payments),
        "range_revenue": range_revenue,
        "range_payment_count": range_count,
        "range_payments": range_payments_sorted,
        "daily_breakdown": daily_breakdown,
        "day_payments": day_payments,
        "month_payments": month_payments,
        "daily_trend": daily_trend,
        "monthly_trend": monthly_trend,
        "total_users": len(users),
        "pro_users": pro_count,
        "vip_count": len(vip_list),
        "billing": load_billing_config(),
        "vip_members": vip_list,
        "usage": usage_stats,
    }


def usage_dashboard(month: str | None = None) -> dict[str, Any]:
    """
    이번 달(또는 지정 월) 무료/유료 회원 생성 횟수 집계.

    - free: plan=free 이고 VIP 아님 (관리자 제외)
    - paid: plan=pro 또는 VIP (관리자는 paid_unlimited 로 분리)
    """
    month_key = month or datetime.now().strftime("%Y-%m")
    users = db.list_users()
    usage_map = db.get_all_usage_map(month_key)
    vip_list = load_vip_members()

    def _is_vip_email(email: str) -> bool:
        em = (email or "").strip().lower()
        if not em:
            return False
        uid = em.split("@")[0]
        return is_vip(em) or is_vip(uid)

    # email -> user row
    by_email: dict[str, dict] = {}
    for u in users:
        em = (u.get("email") or "").strip().lower()
        if em:
            by_email[em] = u

    # usage only emails not in users
    for em in usage_map:
        if em not in by_email:
            by_email[em] = {
                "email": em,
                "name": "",
                "plan": "free",
                "is_admin": False,
            }

    free_gens = 0
    paid_gens = 0
    admin_gens = 0
    free_users_with_use = 0
    paid_users_with_use = 0
    free_user_count = 0
    paid_user_count = 0
    admin_user_count = 0
    rows: list[dict[str, Any]] = []

    for em, u in by_email.items():
        plan = (u.get("plan") or "free").lower()
        is_admin = bool(u.get("is_admin"))
        vip = _is_vip_email(em) or bool(u.get("is_vip"))
        used = int(usage_map.get(em, 0) or 0)

        if is_admin:
            tier = "admin"
            unlimited = True
            admin_user_count += 1
            admin_gens += used
        elif vip or plan == "pro":
            tier = "paid"
            unlimited = True
            paid_user_count += 1
            paid_gens += used
            if used > 0:
                paid_users_with_use += 1
        else:
            tier = "free"
            unlimited = False
            free_user_count += 1
            free_gens += used
            if used > 0:
                free_users_with_use += 1

        rows.append(
            {
                "email": em,
                "name": u.get("name") or "",
                "plan": "pro" if (vip and plan != "pro") else plan,
                "tier": tier,
                "is_admin": is_admin,
                "is_vip": vip,
                "usage": used,
                "limit": None if unlimited else FREE_MONTHLY_LIMIT,
                "remaining": None
                if unlimited
                else max(0, FREE_MONTHLY_LIMIT - used),
            }
        )

    # 사용 많은 순
    rows.sort(key=lambda r: (-int(r.get("usage") or 0), r.get("email") or ""))

    return {
        "month": month_key,
        "free_limit": FREE_MONTHLY_LIMIT,
        "summary": {
            "free_users": free_user_count,
            "paid_users": paid_user_count,
            "admin_users": admin_user_count,
            "free_generations": free_gens,
            "paid_generations": paid_gens,
            "admin_generations": admin_gens,
            "total_generations": free_gens + paid_gens + admin_gens,
            "free_users_with_usage": free_users_with_use,
            "paid_users_with_usage": paid_users_with_use,
        },
        "users": rows,
    }
