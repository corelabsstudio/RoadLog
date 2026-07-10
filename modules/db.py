"""
데이터 계층: Supabase 우선, 실패/미설정 시 로컬 JSON 폴백.
사용자 · 설정 · 사용량 · 결제 기록을 통일된 API로 제공합니다.
"""

from __future__ import annotations

import json
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.config import (
    ENTERPRISE_PRICE_KRW,
    PAYMENTS_JSON,
    SETTINGS_DIR,
    SUPABASE_KEY,
    SUPABASE_URL,
    USAGE_JSON,
    USERS_JSON,
    DEFAULT_USER_SETTINGS,
    PRO_PRICE_KRW,
    get_admin_credentials,
)


# ── 유틸 ───────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month_key(dt: datetime | None = None) -> str:
    d = dt or datetime.now()
    return d.strftime("%Y-%m")


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """간단한 PBKDF2 해시 (로컬 폴백용). Supabase Auth 사용 시 대체 가능."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return dk.hex(), salt


def _verify_password(password: str, password_hash: str, salt: str) -> bool:
    h, _ = _hash_password(password, salt)
    return secrets.compare_digest(h, password_hash)


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


# ── Supabase 클라이언트 ────────────────────────────────


class SupabaseClient:
    """thin wrapper — 연결 불가 시 None 반환."""

    def __init__(self) -> None:
        self.client = None
        if SUPABASE_URL and SUPABASE_KEY and "xxxx" not in SUPABASE_URL:
            try:
                from supabase import create_client

                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception:
                self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None


_sb = SupabaseClient()


def supabase_status() -> str:
    return "connected" if _sb.enabled else "local_json"


# ── 사용자 ─────────────────────────────────────────────


def register_user(email: str, password: str, name: str = "") -> tuple[bool, str]:
    """회원가입. (성공여부, 메시지)"""
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "올바른 이메일을 입력해 주세요."
    if len(password) < 4:
        return False, "비밀번호는 4자 이상이어야 합니다."

    if _sb.enabled:
        try:
            # profiles 테이블 사용 (id, email, name, plan, password_hash, salt, created_at)
            existing = (
                _sb.client.table("profiles")
                .select("email")
                .eq("email", email)
                .execute()
            )
            if existing.data:
                return False, "이미 등록된 이메일입니다."
            pw_hash, salt = _hash_password(password)
            _sb.client.table("profiles").insert(
                {
                    "email": email,
                    "name": name or email.split("@")[0],
                    "plan": "free",
                    "password_hash": pw_hash,
                    "salt": salt,
                    "created_at": _now_iso(),
                }
            ).execute()
            return True, "가입이 완료되었습니다. 로그인해 주세요."
        except Exception as e:
            return False, f"가입 실패: {e}"

    # 로컬 JSON
    users = _read_json(USERS_JSON, {})
    if email in users:
        return False, "이미 등록된 이메일입니다."
    pw_hash, salt = _hash_password(password)
    users[email] = {
        "email": email,
        "name": name or email.split("@")[0],
        "plan": "free",
        "password_hash": pw_hash,
        "salt": salt,
        "created_at": _now_iso(),
    }
    _write_json(USERS_JSON, users)
    return True, "가입이 완료되었습니다. 로그인해 주세요."


def ensure_admin_owner() -> dict:
    """
    사이트 관리자(소유자) 계정을 보장합니다.
    회원가입 없이 ADMIN_USERNAME / ADMIN_PASSWORD 로 일반 로그인 가능.
    plan=pro, is_admin=True
    """
    admin_user, admin_password, admin_email = get_admin_credentials()
    email = (admin_email or f"{admin_user}@roadlog.local").strip().lower()
    users = _read_json(USERS_JSON, {})

    # 예전 admin@roadlog.local 계정이 있으면 정리하고 새 관리자 이메일로 통일
    legacy = "admin@roadlog.local"
    if legacy in users and legacy != email:
        users.pop(legacy, None)

    existing = users.get(email)
    pw_hash, salt = _hash_password(admin_password)
    if existing:
        existing["plan"] = "pro"
        existing["is_admin"] = True
        existing["name"] = existing.get("name") or "관리자"
        existing["password_hash"] = pw_hash
        existing["salt"] = salt
        users[email] = existing
        _write_json(USERS_JSON, users)
        return _normalize_user(existing)

    users[email] = {
        "email": email,
        "name": "관리자",
        "plan": "pro",
        "is_admin": True,
        "password_hash": pw_hash,
        "salt": salt,
        "created_at": _now_iso(),
    }
    _write_json(USERS_JSON, users)
    return _normalize_user(users[email])


def authenticate_admin_credentials(login_id: str, password: str) -> tuple[bool, dict | None, str]:
    """
    관리자 자격 확인 (UI 탭 없음 — 일반 로그인 폼에서 동일 입력).
    login_id: ADMIN_USERNAME 또는 ADMIN_EMAIL
    password: ADMIN_PASSWORD
    secrets/env 는 호출 시점마다 다시 읽음 (Streamlit Cloud 대응).
    """
    admin_user, admin_password, admin_email = get_admin_credentials()
    lid = (login_id or "").strip().lower()
    admin_email = (admin_email or f"{admin_user}@roadlog.local").strip().lower()
    admin_user = (admin_user or "admin").strip().lower()

    # 대소문자 무시 비교 (ID)
    id_ok = lid in {admin_user, admin_email}
    # 비밀번호는 설정된 값과 정확히 일치 (앞뒤 공백 제거)
    pw_ok = (password or "") == admin_password or (password or "").strip() == admin_password
    if not id_ok or not pw_ok:
        return False, None, "관리자 계정 정보가 올바르지 않습니다."

    try:
        user = ensure_admin_owner()
    except Exception as e:
        return False, None, f"관리자 계정 준비 실패(저장소 권한?): {e}"

    # 비밀번호가 설정에서 바뀌었을 수 있으므로 해시 동기화
    users = _read_json(USERS_JSON, {})
    u = users.get(user["email"])
    if u:
        pw_hash, salt = _hash_password(admin_password)
        u["password_hash"] = pw_hash
        u["salt"] = salt
        u["plan"] = "pro"
        u["is_admin"] = True
        u["name"] = u.get("name") or "관리자"
        users[user["email"]] = u
        try:
            _write_json(USERS_JSON, users)
        except Exception as e:
            return False, None, f"로그인 저장 실패: {e}"
        user = _normalize_user(u)
    return True, user, "로그인 성공"


def authenticate(email: str, password: str) -> tuple[bool, dict | None, str]:
    """로그인. (성공, user_dict, 메시지)"""
    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        return False, None, "이메일(또는 관리자 ID)과 비밀번호를 입력해 주세요."

    # 관리자 자격으로 먼저 시도 (회원가입 불필요)
    admin_user, admin_password, admin_email = get_admin_credentials()
    lid = email  # already lowercased
    is_admin_id = lid in {
        (admin_user or "").strip().lower(),
        (admin_email or "").strip().lower(),
    }

    ok_a, user_a, msg_a = authenticate_admin_credentials(email, password)
    if ok_a and user_a:
        from modules.admin_ops import enrich_user_flags

        return True, enrich_user_flags(user_a), msg_a

    # 관리자 ID인데 비밀번호만 틀린 경우 — 일반 회원 메시지로 넘어가지 않음
    if is_admin_id:
        return (
            False,
            None,
            f"관리자 비밀번호가 올바르지 않습니다. (ID: {admin_user}) "
            "Secrets의 ADMIN_PASSWORD 와 같은지 확인하세요.",
        )

    if _sb.enabled:
        try:
            res = (
                _sb.client.table("profiles")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            if not res.data:
                return (
                    False,
                    None,
                    "가입된 계정이 없습니다. 클라우드에서는 로컬 계정이 공유되지 않으니 여기서 회원가입 해 주세요.",
                )
            u = res.data[0]
            if not _verify_password(password, u["password_hash"], u["salt"]):
                return False, None, "비밀번호가 올바르지 않습니다."
            from modules.admin_ops import enrich_user_flags

            return True, enrich_user_flags(_normalize_user(u)), "로그인 성공"
        except Exception as e:
            return False, None, f"로그인 오류: {e}"

    users = _read_json(USERS_JSON, {})
    u = users.get(email)
    if not u:
        # 관리자 ID를 이메일처럼 친 경우 안내
        admin_user, _, admin_email = get_admin_credentials()
        hint = ""
        if email not in {(admin_user or "").lower(), (admin_email or "").lower()}:
            hint = (
                " 클라우드·로컬 회원 DB는 서로 다릅니다. "
                "이 사이트에서 회원가입을 다시 하거나, 관리자는 Secrets의 ADMIN_USERNAME으로 로그인해 주세요."
            )
        return False, None, "가입된 계정이 없습니다." + hint
    if not _verify_password(password, u["password_hash"], u["salt"]):
        return False, None, "비밀번호가 올바르지 않습니다."
    from modules.admin_ops import enrich_user_flags

    return True, enrich_user_flags(_normalize_user(u)), "로그인 성공"


def _normalize_user(u: dict) -> dict:
    return {
        "email": u.get("email", ""),
        "name": u.get("name", ""),
        "plan": u.get("plan", "free"),
        "is_admin": bool(u.get("is_admin")),
        "created_at": u.get("created_at", ""),
    }


def get_user(email: str) -> dict | None:
    email = email.strip().lower()
    from modules.admin_ops import enrich_user_flags

    if _sb.enabled:
        try:
            res = (
                _sb.client.table("profiles")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            if res.data:
                return enrich_user_flags(_normalize_user(res.data[0]))
        except Exception:
            pass
        return None
    users = _read_json(USERS_JSON, {})
    u = users.get(email)
    return enrich_user_flags(_normalize_user(u)) if u else None


def set_user_plan(email: str, plan: str) -> bool:
    """plan: free | pro"""
    email = email.strip().lower()
    if _sb.enabled:
        try:
            _sb.client.table("profiles").update({"plan": plan}).eq(
                "email", email
            ).execute()
            return True
        except Exception:
            return False
    users = _read_json(USERS_JSON, {})
    if email not in users:
        return False
    users[email]["plan"] = plan
    _write_json(USERS_JSON, users)
    return True


def list_users() -> list[dict]:
    if _sb.enabled:
        try:
            res = _sb.client.table("profiles").select("*").execute()
            return [_normalize_user(u) for u in (res.data or [])]
        except Exception:
            return []
    users = _read_json(USERS_JSON, {})
    return [_normalize_user(u) for u in users.values()]


# ── 사용자 설정 ────────────────────────────────────────


def load_settings(email: str) -> dict:
    email = email.strip().lower()
    if _sb.enabled:
        try:
            res = (
                _sb.client.table("user_settings")
                .select("settings")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            if res.data and res.data[0].get("settings"):
                merged = {**DEFAULT_USER_SETTINGS, **res.data[0]["settings"]}
                return merged
        except Exception:
            pass

    path = SETTINGS_DIR / f"{_safe_filename(email)}.json"
    data = _read_json(path, {})
    return {**DEFAULT_USER_SETTINGS, **data}


def save_settings(email: str, settings: dict) -> bool:
    email = email.strip().lower()
    clean = {**DEFAULT_USER_SETTINGS, **settings}

    if _sb.enabled:
        try:
            # upsert
            existing = (
                _sb.client.table("user_settings")
                .select("email")
                .eq("email", email)
                .execute()
            )
            payload = {"email": email, "settings": clean, "updated_at": _now_iso()}
            if existing.data:
                _sb.client.table("user_settings").update(payload).eq(
                    "email", email
                ).execute()
            else:
                _sb.client.table("user_settings").insert(payload).execute()
            return True
        except Exception:
            pass  # 로컬 폴백

    path = SETTINGS_DIR / f"{_safe_filename(email)}.json"
    _write_json(path, clean)
    return True


def _safe_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in "._-@" else "_" for c in s)


# ── 월간 사용량 (매월 1일 자동 리셋 구조) ─────────────


def get_usage(email: str, month: str | None = None) -> int:
    """해당 월 생성 횟수. month 미지정 시 이번 달."""
    email = email.strip().lower()
    month = month or _month_key()

    if _sb.enabled:
        try:
            res = (
                _sb.client.table("usage")
                .select("count")
                .eq("email", email)
                .eq("month", month)
                .limit(1)
                .execute()
            )
            if res.data:
                return int(res.data[0].get("count", 0))
            return 0
        except Exception:
            pass

    usage = _read_json(USAGE_JSON, {})
    return int(usage.get(email, {}).get(month, 0))


def increment_usage(email: str, amount: int = 1) -> int:
    """사용량 +1 후 현재 값 반환. 월 키 기준으로 분리 → 매월 1일 자연 리셋."""
    email = email.strip().lower()
    month = _month_key()

    if _sb.enabled:
        try:
            current = get_usage(email, month)
            new_val = current + amount
            existing = (
                _sb.client.table("usage")
                .select("email")
                .eq("email", email)
                .eq("month", month)
                .execute()
            )
            if existing.data:
                _sb.client.table("usage").update(
                    {"count": new_val, "updated_at": _now_iso()}
                ).eq("email", email).eq("month", month).execute()
            else:
                _sb.client.table("usage").insert(
                    {
                        "email": email,
                        "month": month,
                        "count": new_val,
                        "updated_at": _now_iso(),
                    }
                ).execute()
            return new_val
        except Exception:
            pass

    usage = _read_json(USAGE_JSON, {})
    usage.setdefault(email, {})
    usage[email][month] = int(usage[email].get(month, 0)) + amount
    _write_json(USAGE_JSON, usage)
    return usage[email][month]


# ── 결제 / 수익 (관리자 대시보드) ─────────────────────


def record_payment(
    email: str,
    amount: int = PRO_PRICE_KRW,
    plan: str = "pro",
    note: str = "",
) -> bool:
    """결제 기록 추가 + 사용자 plan 갱신. plan=enterprise 시 plan_type도 전환."""
    email = email.strip().lower()
    # DB plan 필드: free | pro (enterprise는 pro + plan_type)
    db_plan = "pro" if plan in ("pro", "enterprise") else plan
    row = {
        "email": email,
        "amount": amount,
        "plan": plan,  # 결제 기록에는 enterprise 표기 유지
        "note": note,
        "paid_at": _now_iso(),
        "month": _month_key(),
    }

    if _sb.enabled:
        try:
            _sb.client.table("payments").insert(row).execute()
            set_user_plan(email, db_plan)
            if plan == "enterprise":
                _apply_enterprise_config(email)
            return True
        except Exception:
            pass

    payments = _read_json(PAYMENTS_JSON, [])
    payments.append(row)
    _write_json(PAYMENTS_JSON, payments)
    set_user_plan(email, db_plan)
    if plan == "enterprise":
        _apply_enterprise_config(email)
    return True


def _apply_enterprise_config(email: str) -> None:
    """기업용 결제 완료 → config plan_type=enterprise."""
    try:
        from modules.user_config import set_plan_type

        set_plan_type(email, "enterprise")
    except Exception:
        pass


def upgrade_to_pro(email: str, note: str = "Pro 결제 업그레이드") -> bool:
    try:
        from modules.admin_ops import get_pro_price

        price = get_pro_price()
    except Exception:
        price = PRO_PRICE_KRW
    return record_payment(email, price, "pro", note)


def upgrade_to_enterprise(
    email: str,
    note: str = "Enterprise 결제 업그레이드",
    amount: int | None = None,
) -> bool:
    """
    기업용 유료 업그레이드.
    - payments 기록
    - users.plan = pro
    - config_{user}.json plan_type = enterprise
    """
    if amount is None:
        try:
            from modules.admin_ops import get_enterprise_price

            amount = get_enterprise_price()
        except Exception:
            amount = ENTERPRISE_PRICE_KRW
    return record_payment(email, amount, "enterprise", note)


def get_payments(month: str | None = None) -> list[dict]:
    month = month or _month_key()
    if _sb.enabled:
        try:
            res = (
                _sb.client.table("payments")
                .select("*")
                .eq("month", month)
                .execute()
            )
            return res.data or []
        except Exception:
            pass
    payments = _read_json(PAYMENTS_JSON, [])
    return [p for p in payments if p.get("month") == month]


def get_all_payments() -> list[dict]:
    if _sb.enabled:
        try:
            res = (
                _sb.client.table("payments")
                .select("*")
                .order("paid_at")
                .execute()
            )
            return res.data or []
        except Exception:
            pass
    return _read_json(PAYMENTS_JSON, [])


def admin_stats(month: str | None = None) -> dict:
    """이번 달 결제자 수 · 총 수익 · 월별 추이 데이터."""
    month = month or _month_key()
    month_payments = get_payments(month)
    payers = {p.get("email") for p in month_payments if p.get("email")}
    revenue = sum(int(p.get("amount", 0)) for p in month_payments)

    # 최근 6개월 추이
    all_p = get_all_payments()
    by_month: dict[str, int] = {}
    for p in all_p:
        m = p.get("month") or ""
        if m:
            by_month[m] = by_month.get(m, 0) + int(p.get("amount", 0))

    # 빈 월 채우기 (현재 기준 6개월)
    trend = []
    now = datetime.now()
    for i in range(5, -1, -1):
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        key = f"{y:04d}-{m:02d}"
        trend.append({"month": key, "revenue": by_month.get(key, 0)})

    users = list_users()
    pro_users = [u for u in users if u.get("plan") == "pro"]

    return {
        "month": month,
        "payer_count": len(payers),
        "revenue": revenue,
        "total_users": len(users),
        "pro_users": len(pro_users),
        "trend": trend,
        "payments": month_payments,
    }


def seed_demo_payments_if_empty() -> None:
    """로컬 데모용: 결제 데이터가 없으면 샘플 생성 (관리자 차트 확인용)."""
    if get_all_payments():
        return
    # 의도적으로 비움 — 관리자가 수동 등록. 데모 시드 원하면 주석 해제.
    pass
