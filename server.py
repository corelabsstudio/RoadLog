"""
로드로그 (RoadLog) — 프리미엄 웹 서버
FastAPI + 정적 프론트엔드 + 기존 modules 재사용

실행:
  .venv\\Scripts\\python.exe -m uvicorn server:app --reload --port 8501
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Cookie, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import logging

log = logging.getLogger("roadlog")

from modules import db
from modules import visitors as visitors_ops
from modules.config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    ALLOW_DEMO_BILLING_UPGRADE,
    APP_ENV,
    APP_FULL,
    APP_TAGLINE,
    APP_TITLE,
    BUSINESS_ADDRESS,
    BUSINESS_NAME,
    BUSINESS_OWNER,
    BUSINESS_REG_NO,
    CONTACT_EMAIL,
    CONTACT_FORM_URL,
    CONTACT_HP,
    CONTACT_TEL,
    DATA_DIR,
    DEFAULT_USER_SETTINGS,
    ENTERPRISE_ANNUAL_MONTHLY_EQ_KRW,
    ENTERPRISE_ANNUAL_PAYMENT_URL,
    ENTERPRISE_ANNUAL_PRICE_KRW,
    ENTERPRISE_BASE_SEATS,
    ENTERPRISE_PAYMENT_URL,
    ENTERPRISE_PRICE_KRW,
    ENTERPRISE_SEAT_ANNUAL_PRICE_KRW,
    ENTERPRISE_SEAT_PRICE_KRW,
    FREE_MONTHLY_LIMIT,
    FREE_TOTAL_LIMIT,
    MAIL_ORDER_REG_NO,
    MIN_PASSWORD_LENGTH,
    COST_MODE,
    OPENAI_API_KEY,
    PRO_ANNUAL_MONTHLY_EQ_KRW,
    PRO_ANNUAL_PAYMENT_URL,
    PRO_ANNUAL_PRICE_KRW,
    PRO_PAYMENT_URL,
    PRO_PRICE_KRW,
    STUDIO_NAME,
    STUDIO_NAME_EN,
    assert_secure_for_production,
    cors_allow_origins,
    data_dir_is_external,
    is_free_cost_mode,
    is_production,
    llm_configured,
    resolve_llm_config,
    security_issues,
)
from modules.export import (
    export_docx,
    export_excel,
    export_pdf,
    export_summary_excel,
    export_summary_pdf,
)
from modules.generator import generate_driving_log, scrub_submission_log
from modules import style_learn
from modules import admin_ops
from modules import reviews as reviews_ops
# 손님이 쓴 말이 봐 달라는 것인지 그냥 건네는 말인지 가른다 (2026-09-11 3단계)
from modules import intent as intent_ops
from modules import saju_writer
from modules.rate_limit import (
    AUTH_LIMIT,
    AUTH_WINDOW,
    GENERATE_LIMIT,
    GENERATE_WINDOW,
    REGISTER_LIMIT,
    REGISTER_WINDOW,
    limiter,
)
from modules.validator import validate_log
from modules import notify as notify_ops
from modules import inbox
from modules import mailer
from modules import password_reset as reset_ops
from modules import lamps as lamps_ops
from modules import product_reviews as prev_ops
from modules import records as rec_ops
from modules import gwansang as gwansang_ops
from modules import stats as stats_ops

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

# 프로덕션: 약한 비밀키/데모 결제 등이 있으면 기동 자체를 막음
assert_secure_for_production()

# 개발: 경고만 출력
for _issue in security_issues():
    if _issue["level"] == "info" and not is_production():
        continue
    print(
        f"[RoadLog security:{_issue['level']}] {_issue['code']}: {_issue['message']}",
        flush=True,
    )

_cors_origins = cors_allow_origins()
# credentials + "*" 조합은 브라우저에서 거부되므로 와일드카드일 때 credentials 비활성
_cors_credentials = _cors_origins != ["*"]

app = FastAPI(title=APP_FULL, version="3.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    """기본 보안 헤더 + 응답 charset."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(self), microphone=(), camera=()"
    )
    if is_production():
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    # JSON 한글 깨짐 방지 (일부 프록시/클라이언트)
    ct = response.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct.lower():
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


def _client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_or_429(key: str, *, limit: int, window_sec: int, what: str) -> None:
    if not limiter.allow(key, limit=limit, window_sec=window_sec):
        raise HTTPException(
            429,
            f"요청이 너무 많습니다. 잠시 후 다시 시도해 주세요. ({what})",
        )

# 토큰 세션 — 메모리 + 디스크 영속화 (재접속 시 자동 로그인 유지)
_sessions: dict[str, dict] = {}
_SESSIONS_PATH = DATA_DIR / "sessions.json"


def _load_sessions_from_disk() -> None:
    """재시작 후에도 localStorage 토큰이 유효하도록 세션 복원."""
    if not _SESSIONS_PATH.exists():
        return
    try:
        raw = json.loads(_SESSIONS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        for token, meta in raw.items():
            if not token or not isinstance(meta, dict):
                continue
            email = (meta.get("email") or "").strip().lower()
            if not email:
                continue
            user = db.get_user(email)
            if user:
                _sessions[token] = admin_ops.enrich_user_flags(user) or user
    except Exception:
        pass


def _persist_sessions() -> None:
    try:
        payload = {}
        for token, user in _sessions.items():
            email = (user.get("email") or "").strip().lower()
            if email:
                payload[token] = {
                    "email": email,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
        _SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SESSIONS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# 관리자(소유자) 계정 자동 생성 — 회원가입 없이 admin 로그인 가능
try:
    db.ensure_admin_owner()
except Exception:
    pass

_load_sessions_from_disk()


def _token_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    token = authorization.removeprefix("Bearer ").strip()
    user = _sessions.get(token)
    if not user:
        # 디스크에서 재로드 시도 (다른 워커/재시작 직후)
        _load_sessions_from_disk()
        user = _sessions.get(token)
    if not user:
        raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인해 주세요.")
    # plan / VIP 최신화
    fresh = db.get_user(user["email"])
    if fresh:
        user = admin_ops.enrich_user_flags(fresh)
        _sessions[token] = user
    else:
        user = admin_ops.enrich_user_flags(user) or user
        _sessions[token] = user
    return user


def _require_admin(authorization: str | None) -> dict:
    user = _token_user(authorization)
    if not user.get("is_admin"):
        raise HTTPException(403, "관리자만 접근할 수 있습니다.")
    return user


# ── Models ────────────────────────────────────────────


class AuthBody(BaseModel):
    email: str
    password: str
    name: str = ""
    ref: str = ""      # 친구를 따라 들어온 분의 추천 코드
    via: str = ""      # 어느 길로 오셨는지 (utm / 들어온 사이트). 개인 식별값은 담지 않는다


class ForgotBody(BaseModel):
    email: str


class ResetBody(BaseModel):
    token: str
    password: str


class GenerateBody(BaseModel):
    """구조화 입력 우선. raw_text는 선택(추가 메모)."""
    raw_text: str = ""
    settings: dict[str, Any] | None = None
    # driving | field (외근·출장)
    report_type: str = "driving"
    # 구조화 필드 (권장) — 운행
    vehicle_number: str = ""
    odometer_start: float | None = None
    odometer_end: float | None = None
    lunch_restaurant: str = ""
    morning_places: str = ""
    afternoon_places: str = ""
    # 외근
    visits_text: str = ""
    work_summary: str = ""
    next_actions: str = ""
    department: str = ""
    form: dict[str, Any] | None = None


class SettingsBody(BaseModel):
    settings: dict[str, Any]


class ExportBody(BaseModel):
    log: dict[str, Any]
    # validate reuses this model; format only required for /api/export
    format: str = "excel"  # excel | pdf | docx


class StyleTextBody(BaseModel):
    title: str = "붙여넣기 일지"
    text: str


class SaveLogBody(BaseModel):
    """일지 저장 요청."""
    log: dict[str, Any]
    report_type: str = "driving"
    title: str = ""
    id: str | None = None


# ── API ───────────────────────────────────────────────


@app.get("/healthz")
@app.get("/health")
def healthz():
    """Railway / 로드밸런서용 초경량 헬스체크 (의존성 없음)."""
    return Response(content="ok", media_type="text/plain")


@app.get("/api/health")
def health():
    try:
        storage = db.supabase_status()
    except Exception:
        storage = "unknown"
    llm = resolve_llm_config()
    persistent = storage == "connected" or data_dir_is_external()
    free = is_free_cost_mode()
    # hybrid/free: 볼륨·LLM 없이도 서비스 가능. paid: 키+영속 권장.
    if COST_MODE in {"free", "hybrid"}:
        launch_ready = not ALLOW_DEMO_BILLING_UPGRADE
    else:
        launch_ready = bool(
            is_production()
            and llm_configured()
            and persistent
            and not ALLOW_DEMO_BILLING_UPGRADE
        )
    llm_on = (not free) and llm_configured()
    return {
        "ok": True,
        "app": APP_TITLE,
        "env": APP_ENV,
        "production": is_production(),
        "cost_mode": COST_MODE,
        "free_mode": free,
        "storage": storage,
        "data_dir": str(DATA_DIR),
        "storage_persistent": persistent,
        "openai": llm_on,
        "llm_provider": (llm.get("provider") or "") if llm_on else "",
        "demo_billing_upgrade": ALLOW_DEMO_BILLING_UPGRADE,
        "launch_ready": launch_ready,
    }


@app.get("/api/meta")
def meta():
    billing = admin_ops.load_billing_config()
    return {
        "title": APP_TITLE,
        "tagline": APP_TAGLINE,
        "full": APP_FULL,
        "studio": STUDIO_NAME,
        "studio_en": STUDIO_NAME_EN,
        "contact_email": CONTACT_EMAIL,
        "contact_form_url": CONTACT_FORM_URL or "",
        "free_limit": FREE_TOTAL_LIMIT,
        "free_limit_period": "lifetime",  # monthly 아님 · 가입 후 누적
        "pro_price": int(billing.get("pro_price_krw") or PRO_PRICE_KRW),
        "pro_annual_price": int(
            billing.get("pro_annual_price_krw") or PRO_ANNUAL_PRICE_KRW
        ),
        "pro_annual_monthly_eq": int(
            billing.get("pro_annual_monthly_eq_krw") or PRO_ANNUAL_MONTHLY_EQ_KRW
        ),
        "enterprise_price": int(
            billing.get("enterprise_price_krw") or ENTERPRISE_PRICE_KRW
        ),
        "enterprise_annual_price": int(
            billing.get("enterprise_annual_price_krw") or ENTERPRISE_ANNUAL_PRICE_KRW
        ),
        "enterprise_annual_monthly_eq": int(
            billing.get("enterprise_annual_monthly_eq_krw")
            or ENTERPRISE_ANNUAL_MONTHLY_EQ_KRW
        ),
        "enterprise_base_seats": int(
            billing.get("enterprise_base_seats") or ENTERPRISE_BASE_SEATS
        ),
        "enterprise_seat_price": int(
            billing.get("enterprise_seat_price_krw") or ENTERPRISE_SEAT_PRICE_KRW
        ),
        "enterprise_seat_annual_price": int(
            billing.get("enterprise_seat_annual_price_krw")
            or ENTERPRISE_SEAT_ANNUAL_PRICE_KRW
        ),
        "pro_url": PRO_PAYMENT_URL,
        "pro_annual_url": (PRO_ANNUAL_PAYMENT_URL or PRO_PAYMENT_URL or "").strip(),
        "enterprise_url": ENTERPRISE_PAYMENT_URL,
        "enterprise_annual_url": (
            ENTERPRISE_ANNUAL_PAYMENT_URL or ENTERPRISE_PAYMENT_URL or ""
        ).strip(),
        "demo_billing_upgrade": ALLOW_DEMO_BILLING_UPGRADE,
        "cost_mode": COST_MODE,
        "free_mode": is_free_cost_mode(),
        "payment_ready": not (
            (not PRO_PAYMENT_URL)
            or "example.com" in (PRO_PAYMENT_URL or "").lower()
            or "your-payment" in (PRO_PAYMENT_URL or "").lower()
        ),
        "pro_claim_path": "#pro-claim",
        "notify_ready": notify_ops.notify_configured(),
        "default_settings": DEFAULT_USER_SETTINGS,
        "default_templates_url": "/assets/templates/manifest.json",
        "business": {
            "name": BUSINESS_NAME or STUDIO_NAME,
            "owner": BUSINESS_OWNER or "",
            "reg_no": BUSINESS_REG_NO or "",
            "address": BUSINESS_ADDRESS or "",
            "mail_order_no": MAIL_ORDER_REG_NO or "",
            "contact_email": CONTACT_EMAIL,
            "tel": CONTACT_TEL,
            "hp": CONTACT_HP,
        },
    }


class UpgradeBody(BaseModel):
    plan: str  # pro | enterprise


class PaymentClaimBody(BaseModel):
    """스마트스토어 결제 후 Pro 반영 요청 → 관리자 폰 알림."""

    order_id: str
    email: str
    name: str = ""
    note: str = ""
    plan: str = "pro"
    billing_period: str = "monthly"  # monthly | annual


@app.post("/api/billing/claim")
def billing_claim(body: PaymentClaimBody, request: Request):
    """
    스마트스토어 결제 완료 고객이 주문번호·이메일을 남기면
    관리자 폰(ntfy/Telegram)으로 푸시합니다.
    """
    ip = _client_ip(request)
    _rate_limit_or_429(
        f"claim:{ip}",
        limit=8,
        window_sec=3600,
        what="결제 확인 요청",
    )
    order_id = (body.order_id or "").strip()
    email = (body.email or "").strip().lower()
    if len(order_id) < 4:
        raise HTTPException(400, "주문번호(또는 결제 확인 번호)를 입력해 주세요.")
    if not email or "@" not in email:
        raise HTTPException(400, "로드로그 가입 이메일을 올바르게 입력해 주세요.")

    period = (body.billing_period or "monthly").strip().lower()
    if period not in ("monthly", "annual", "year", "yearly"):
        period = "monthly"
    if period in ("year", "yearly"):
        period = "annual"
    claim = notify_ops.save_claim(
        order_id=order_id,
        email=email,
        name=body.name or "",
        note=body.note or "",
        plan=(body.plan or "pro").strip().lower() or "pro",
        billing_period=period,
    )
    period_label = "연 결제" if claim.get("billing_period") == "annual" else "월 결제"
    title = "로드로그 · 결제 확인 요청"
    msg = (
        f"plan={claim['plan']} ({period_label})\n"
        f"주문/결제번호: {claim['order_id']}\n"
        f"가입 이메일: {claim['email']}\n"
        f"이름: {claim.get('name') or '-'}\n"
        f"메모: {claim.get('note') or '-'}\n"
        f"시각: {claim['created_at']}\n"
        f"→ 관리자에서 {claim['plan']} 반영해 주세요."
    )
    push = notify_ops.send_admin_push(title, msg, priority=5)
    return {
        "ok": True,
        "message": "접수되었습니다. 확인 후 Pro가 반영됩니다. 조금만 기다려 주세요.",
        "claim_id": claim["id"],
        "notify": push,
    }


@app.get("/api/admin/claims")
def admin_claims(
    limit: int = Query(default=30, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    _require_admin(authorization)
    return {
        "ok": True,
        "items": notify_ops.list_claims(limit=limit),
        "notify_configured": notify_ops.notify_configured(),
    }


@app.post("/api/admin/notify-test")
def admin_notify_test(authorization: str | None = Header(default=None)):
    """관리자 폰 알림 테스트."""
    _require_admin(authorization)
    if not notify_ops.notify_configured():
        raise HTTPException(
            400,
            "NTFY_TOPIC 또는 TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID 를 Railway에 설정하세요.",
        )
    push = notify_ops.send_admin_push(
        "로드로그 · 알림 테스트",
        "푸시가 정상적으로 연결되었습니다.",
        priority=4,
    )
    if not push.get("ok"):
        raise HTTPException(502, f"알림 전송 실패: {push}")
    return {"ok": True, "notify": push}


@app.post("/api/billing/upgrade")
def billing_upgrade(body: UpgradeBody, authorization: str | None = Header(default=None)):
    """
    요금제 업그레이드.

    기본: 비활성 (복채 없이 plan 변경 불가).
    로컬 데모에서만 ALLOW_DEMO_BILLING_UPGRADE=true 로 허용.
    운영에서는 결제 웹훅/관리자 수동 등록으로 plan을 변경하세요.
    """
    user = _token_user(authorization)
    if not ALLOW_DEMO_BILLING_UPGRADE:
        raise HTTPException(
            403,
            "결제가 확인된 뒤 요금제가 적용됩니다. 아래 결제 링크로 진행하거나 문의해 주세요.",
        )

    plan = (body.plan or "").strip().lower()
    email = user["email"]
    if plan == "pro":
        ok = db.upgrade_to_pro(email, note="웹 요금제 Pro 업그레이드 (데모)")
    elif plan in ("enterprise", "ent"):
        ok = db.upgrade_to_enterprise(email, note="웹 요금제 Enterprise 업그레이드 (데모)")
    else:
        raise HTTPException(400, "plan은 pro 또는 enterprise 여야 합니다.")
    if not ok:
        raise HTTPException(500, "업그레이드 처리에 실패했습니다.")
    fresh = db.get_user(email) or user
    fresh = admin_ops.enrich_user_flags(fresh) or fresh
    # 세션 갱신
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token in _sessions:
            _sessions[token] = fresh
    return {
        "ok": True,
        "user": fresh,
        "message": "Enterprise로 전환되었습니다. (데모)"
        if plan in ("enterprise", "ent")
        else "Pro로 전환되었습니다. (데모)",
        "demo": True,
    }


@app.get("/api/templates/defaults")
def default_templates():
    """사이트 기본 제공 운행일지 서식 목록 (로그인 불필요)."""
    import json
    from pathlib import Path

    path = WEB / "assets" / "templates" / "manifest.json"
    if not path.exists():
        return {"templates": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"templates": data}
    except Exception:
        return {"templates": []}


@app.post("/api/auth/register")
def register(body: AuthBody, request: Request):
    ip = _client_ip(request)
    _rate_limit_or_429(
        f"register:{ip}",
        limit=REGISTER_LIMIT,
        window_sec=REGISTER_WINDOW,
        what="회원가입",
    )
    _rate_limit_or_429(
        f"auth:{ip}",
        limit=AUTH_LIMIT,
        window_sec=AUTH_WINDOW,
        what="인증",
    )
    ok, msg = db.register_user(body.email, body.password, body.name)
    if not ok:
        raise HTTPException(400, msg)
    # 가입 선물. 손에 쥐는 게 있어야 계정을 만든다.
    try:
        gift = lamps_ops.welcome(body.email, (body.ref or "").strip(), (body.via or "").strip()[:80])
    except Exception as e:                      # noqa: BLE001
        # 🛑 조용히 삼키면 「가입하면 등불 300개」라고 적어 놓고 안 준 것을 아무도 모른다.
        log.error("가입 선물 실패 (%s): %s", body.email, e)
        gift = {"given": 0}
    # 🛑 준 것을 **말해 줘야 준 것이다.** 전에는 등불만 조용히 들어가서
    #    내역을 열어 보지 않으면 받은 줄도 몰랐다 (2026-09-08).
    try:
        _welcome_inbox(body.email, gift)
    except Exception as e:                      # noqa: BLE001
        log.error("가입 알림 실패 (%s): %s", body.email, e)
    return {"ok": True, "message": msg, "welcome": gift.get("given", 0), "referred": gift.get("referred", 0)}


def _welcome_inbox(email: str, gift: dict) -> None:
    """가입한 분께 무엇을 드렸는지 알림함에 남긴다."""
    given = gift.get("given", 0)
    if given:
        inbox.push(
            email,
            "무냥이가 등불 %d개를 드렸어요" % given,
            "리포트를 보다가 궁금한 게 생기면 무냥이한테 물어보실 수 있어요. "
            "한 번 물을 때마다 등불이 조금씩 들어가요.",
            key="welcome", icon="lamp",
        )
    if gift.get("referred"):
        inbox.push(
            email,
            "친구 따라 들어오셔서 등불을 더 드렸어요",
            "데려오신 분께도 같이 드렸어요. 고맙습니다.",
            key="refer_in", icon="lamp",
        )
    # 선착순 자리를 받으셨는지
    try:
        st = _gift_state(db.get_user(email))
    except Exception:                           # noqa: BLE001
        return
    if st.get("eligible"):
        inbox.push(
            email,
            "선착순 %d번째로 무료 열람 1회권을 받으셨어요" % st.get("rank", 0),
            "값이 있는 사주 한 편을 그냥 보실 수 있어요. 어느 편이든 괜찮아요. "
            "다만 한 번 고르면 그 편으로 끝이라 천천히 고르셔도 돼요.",
            key="gift-ticket", icon="ticket",
        )


def _issue_session(user: dict, message: str) -> dict:
    user = admin_ops.enrich_user_flags(user) or user
    token = secrets.token_urlsafe(32)
    _sessions[token] = user
    _persist_sessions()
    used = db.get_usage_lifetime(user["email"])
    limit = FREE_TOTAL_LIMIT
    plan = (user.get("plan") or user.get("plan_type") or "free").lower()
    unlimited = (
        plan in ("pro", "enterprise")
        or user.get("is_admin")
        or user.get("is_vip")
    )
    return {
        "ok": True,
        "token": token,
        "user": user,
        "usage": used,
        "limit": limit,
        "unlimited": unlimited,
        "free_limit_period": "lifetime",
        "message": message,
    }


def _shorten_korean_address(display_name: str, raw: dict | None = None) -> str:
    """
    긴 Nominatim 주소를 일지용 짧은 표기로 축약.
    우선: 건물/시설명 + 동(洞) 단위.
    예) 한일유앤아이아파트, 후평2동
    """
    import re

    raw = raw or {}
    # 1) 구조화 필드 우선
    place_keys = (
        "building",
        "amenity",
        "tourism",
        "leisure",
        "shop",
        "office",
        "highway",  # 최후
        "road",
    )
    dong_keys = (
        "suburb",
        "neighbourhood",
        "neighborhood",
        "quarter",
        "city_district",
        "borough",
        "hamlet",
        "village",
    )
    place = ""
    for k in place_keys:
        v = (raw.get(k) or "").strip()
        if not v:
            continue
        # 도로명만 있는 경우 제외 (로/길 등) — 아래 문자열 파서로 넘김
        if k in ("highway", "road") and re.search(r"(로|길|대로|거리)$", v):
            continue
        place = v
        break
    dong = ""
    for k in dong_keys:
        v = (raw.get(k) or "").strip()
        if v and re.search(r"(동|가|리|읍|면)$", v):
            dong = v
            break
    if not dong:
        for k in dong_keys:
            v = (raw.get(k) or "").strip()
            if v:
                dong = v
                break

    if place and dong and place != dong:
        return f"{place}, {dong}"
    if place:
        return place
    if dong:
        return dong

    # 2) display_name 파싱 폴백
    text = (display_name or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"[,/|]", text) if p.strip()]
    if not parts:
        return text

    drop_exact = {
        "대한민국",
        "한국",
        "korea",
        "south korea",
        "republic of korea",
    }
    drop_re = re.compile(
        r"("
        r"특별자치도|광역시|특별시|자치시|"
        r"도$|시$|군$|"  # 광역/기초 행정구역
        r"^\d{4,6}$|"  # 우편번호
        r"^[A-Za-z\s]+$"  # 영문 국가명 등
        r")"
    )
    road_re = re.compile(r"(로|길|대로|거리|로\d*번길)$")
    dong_re = re.compile(r"(동|가|리|읍|면)$")
    building_hint = re.compile(
        r"(아파트|APT|빌라|타워|오피스텔|센터|빌딩|병원|학교|마트|역|터미널|공원|시장|교회|성당|사찰)"
    )

    kept: list[str] = []
    dongs: list[str] = []
    buildings: list[str] = []
    for p in parts:
        pl = p.lower()
        if pl in drop_exact:
            continue
        if re.fullmatch(r"\d{4,6}", p):
            continue
        if drop_re.search(p) and not dong_re.search(p) and not building_hint.search(p):
            # '춘천시', '강원특별자치도' 등 제거 (동 단위는 유지)
            if re.search(r"(시|군|도|특별|광역)$", p) and not dong_re.search(p):
                continue
        if road_re.search(p) and not building_hint.search(p):
            continue  # 후만로 등 도로명 제외
        if dong_re.search(p):
            dongs.append(p)
        elif building_hint.search(p) or len(p) >= 3:
            buildings.append(p)
        else:
            kept.append(p)

    short_parts: list[str] = []
    if buildings:
        short_parts.append(buildings[0])
    if dongs:
        short_parts.append(dongs[0])
    if not short_parts and kept:
        short_parts = kept[:2]
    if not short_parts and parts:
        # 최후: 앞쪽 의미 있는 1~2토큰 (국가/우편 제외 후)
        filtered = [
            p
            for p in parts
            if p.lower() not in drop_exact and not re.fullmatch(r"\d{4,6}", p)
        ]
        short_parts = filtered[:2] if filtered else parts[:1]
    return ", ".join(short_parts)


@app.get("/api/geo/reverse")
def geo_reverse(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """GPS 좌표 → 주소 문자열 (OpenStreetMap Nominatim). short_address 포함."""
    try:
        with httpx.Client(timeout=12.0) as client:
            res = client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "jsonv2",
                    "accept-language": "ko",
                    "zoom": 18,
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": "RoadLog/1.0 (CoreLabs; corelabs.studio@gmail.com)",
                    "Accept": "application/json",
                },
            )
        if res.status_code != 200:
            raise HTTPException(502, "주소 변환 서비스에 일시적으로 연결할 수 없습니다.")
        data = res.json()
        raw = data.get("address") or {}
        address = (data.get("display_name") or "").strip()
        if not address:
            address = f"{lat:.5f}, {lon:.5f}"
        short = _shorten_korean_address(address, raw if isinstance(raw, dict) else {})
        if not short:
            short = address
        return {
            "ok": True,
            "lat": lat,
            "lon": lon,
            "address": short,  # 일지·리스트 기본값 = 짧은 주소
            "address_full": address,
            "short_address": short,
            "raw": raw if isinstance(raw, dict) else {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"주소 변환 실패: {e}") from e


@app.post("/api/auth/login")
def login(body: AuthBody, request: Request):
    """일반 로그인. 관리자 ID/PW면 자동으로 관리자(Pro) 세션."""
    ip = _client_ip(request)
    _rate_limit_or_429(
        f"auth:{ip}",
        limit=AUTH_LIMIT,
        window_sec=AUTH_WINDOW,
        what="로그인",
    )
    ok, user, msg = db.authenticate(body.email, body.password)
    if not ok or not user:
        raise HTTPException(401, msg)
    return _issue_session(user, msg)


# ── 비밀번호 다시 정하기 ──────────────────────────────────
# 결제가 붙는 서비스라, 비밀번호를 잊는 순간 충전해 둔 등불까지 같이 묶인다.
# 되찾는 길을 열되 남의 계정으로 들어가는 문은 되지 않게 한다.
#
# 🛑 **어느 경우에도 같은 대답을 돌려준다.** 「가입된 계정이 없어요」라고 알려 주면
#    아무나 이메일을 넣어 보며 누가 우리 손님인지 캐낼 수 있다. 사주 서비스라
#    가입 사실 자체가 알려지면 안 되는 정보다. 그래서 갈라지는 안내는 전부
#    **본인만 여는 메일 안에** 둔다 (modules/mailer.py).

RESET_SENT_MSG = (
    "메일을 보냈어요. 받은 편지함을 확인해 주세요. "
    "가입된 계정일 때만 도착하고, 안 보이면 스팸함도 한 번 봐 주세요."
)


@app.post("/api/auth/password/forgot")
def password_forgot(body: ForgotBody, request: Request):
    """재설정 링크를 메일로 보낸다. 대답은 언제나 같다."""
    ip = _client_ip(request)
    _rate_limit_or_429(
        f"forgot:{ip}", limit=AUTH_LIMIT, window_sec=AUTH_WINDOW, what="비밀번호 찾기"
    )
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "올바른 이메일을 입력해 주세요.")

    # 메일을 보낼 수 없는 상태면 조용히 넘어가지 않는다. 손님이 기다리게 두면 안 된다
    if not mailer.mail_configured():
        raise HTTPException(
            503,
            "지금은 재설정 메일을 보낼 수 없어요. "
            f"{CONTACT_EMAIL} 로 알려 주시면 바로 도와드릴게요.",
        )

    user = db.get_user(email)
    if not user:
        return {"ok": True, "message": RESET_SENT_MSG}     # 있는지 없는지 알려 주지 않는다

    # 카카오·구글로만 들어오시는 분은 정해 둔 비밀번호가 없다.
    # 링크를 보내면 «없던 비밀번호»가 생겨 오히려 헷갈린다 → 들어오시는 방법을 안내한다
    prov = db.social_only_provider(email)
    if prov:
        try:
            mailer.send_social_only_notice(email, prov)
        except Exception as e:
            print(f"[reset] 소셜 안내 메일 실패 {email!r}: {e}", flush=True)
        return {"ok": True, "message": RESET_SENT_MSG}

    token, why = reset_ops.issue(email, ip=ip)
    if not token:
        raise HTTPException(429, why or "잠시 후 다시 시도해 주세요.")

    link = f"{SITE_ORIGIN}/reset.html?t={quote(token)}"
    try:
        sent = mailer.send_password_reset_link(email, link, minutes=reset_ops.TTL_MIN)
    except Exception as e:
        print(f"[reset] 메일 실패 {email!r}: {e}", flush=True)
        sent = False
    if not sent:
        raise HTTPException(
            502,
            "메일을 보내지 못했어요. 잠시 후 다시 시도하시거나 "
            f"{CONTACT_EMAIL} 로 알려 주세요.",
        )
    return {"ok": True, "message": RESET_SENT_MSG}


@app.get("/api/auth/password/check")
def password_reset_check(request: Request, t: str = ""):
    """링크가 아직 살아 있나. 화면이 폼을 그릴지 정할 때만 쓴다 (여기서 쓰지는 않는다)."""
    _rate_limit_or_429(
        f"resetcheck:{_client_ip(request)}",
        limit=AUTH_LIMIT, window_sec=AUTH_WINDOW, what="링크 확인",
    )
    ok, email, why = reset_ops.peek(t)
    if not ok:
        return {"ok": False, "message": why}
    # 어느 계정인지는 앞 두 글자만. 열려 있는 링크라도 주소 전체를 다시 뿌리지 않는다
    local = (email or "").split("@")[0]
    hint = (local[:2] + "•" * max(1, len(local) - 2)) + "@" + (email or "").split("@")[-1]
    return {"ok": True, "email_hint": hint, "min_length": MIN_PASSWORD_LENGTH}


@app.post("/api/auth/password/reset")
def password_reset(body: ResetBody, request: Request):
    """새 비밀번호를 저장한다. 링크는 여기서 닫힌다."""
    ip = _client_ip(request)
    _rate_limit_or_429(
        f"reset:{ip}", limit=AUTH_LIMIT, window_sec=AUTH_WINDOW, what="비밀번호 재설정"
    )
    if len(body.password or "") < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 해요.")

    # 먼저 닫고 바꾼다. 같은 링크로 두 번 들어오는 길을 막는다
    ok, email, why = reset_ops.consume(body.token)
    if not ok:
        raise HTTPException(400, why)

    saved, msg = db.set_password(email, body.password)
    if not saved:
        raise HTTPException(400, msg)

    # 남이 알아낸 비밀번호로 이미 들어와 있었다면 여기서 끊는다
    dropped = _drop_sessions_for_email(email)
    try:
        mailer.send_password_changed(email)
    except Exception as e:
        print(f"[reset] 변경 알림 메일 실패 {email!r}: {e}", flush=True)
    print(f"[reset] 비밀번호 변경 {email!r} · 끊은 세션 {dropped}개", flush=True)
    return {"ok": True, "message": "비밀번호를 새로 정했어요. 새 비밀번호로 로그인해 주세요."}


# ── 소셜 로그인 (구글 · 카카오) ────────────────────────────
# 열쇠는 전부 환경변수로 받는다. 없으면 그 제공자는 꺼진 것으로 본다.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "").strip()
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "").strip()
SITE_ORIGIN = (os.environ.get("SITE_ORIGIN", "https://roadlog.co.kr") or "").rstrip("/")

# state 는 CSRF 방지용. 짧게 살고 한 번 쓰면 버린다.
_oauth_states: dict[str, float] = {}


def _new_state() -> str:
    import time
    now = time.time()
    for k, born in list(_oauth_states.items()):
        if now - born > 600:
            _oauth_states.pop(k, None)
    st = secrets.token_urlsafe(24)
    _oauth_states[st] = now
    return st


def _use_state(st: str) -> bool:
    import time
    born = _oauth_states.pop(st or "", None)
    return bool(born) and (time.time() - born) <= 600


def _social_login(email: str, name: str, provider: str, provider_key: str = "") -> str:
    """이메일로 기존 회원을 찾고, 없으면 만든다. 우리 토큰을 돌려준다."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "이 계정에서 이메일을 받지 못했습니다.")
    user = db.get_user(email)
    if not user:
        # 소셜로만 들어온 회원이라 비밀번호는 쓰지 않는다. 아무도 모르는 값으로 채운다.
        ok, msg = db.register_user(email, secrets.token_urlsafe(24), name or email.split("@")[0])
        if not ok:
            raise HTTPException(400, msg)
        # 🛑 «비밀번호가 없는 계정»이라고 적어 둔다. 위에서 넣은 임의 문자열은
        #    본인도 모르는 값이라, 비밀번호 찾기에서 재설정 링크를 보내면 안 된다.
        #    이미 있는 계정에는 표시하지 않는다 — 메일로 가입한 뒤 소셜로도
        #    들어오시는 분은 정해 둔 비밀번호가 있다.
        try:
            db.mark_social(email, provider_key or provider)
        except Exception:
            pass
        try:
            lamps_ops.welcome(email)      # 소셜로 처음 들어온 분께도 같이
        except Exception as e:                  # noqa: BLE001
            log.error("소셜 가입 선물 실패 (%s): %s", email, e)
        user = db.get_user(email)
    if not user:
        raise HTTPException(500, "계정을 만들지 못했습니다.")
    sess = _issue_session(user, f"{provider} 로그인")
    return sess["token"]


def _social_redirect(token: str) -> RedirectResponse:
    # 토큰은 조각(#)으로 넘긴다. 물음표로 넘기면 서버 로그와 리퍼러에 남는다.
    return RedirectResponse(f"{SITE_ORIGIN}/#t={quote(token)}", status_code=302)


@app.get("/api/auth/social/ready")
def social_ready():
    """어떤 소셜 로그인이 켜져 있는지. 화면은 이걸 보고 버튼을 그린다."""
    return {
        "google": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "kakao": bool(KAKAO_REST_API_KEY),
    }


@app.get("/api/auth/google/start")
def google_start():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(503, "구글 로그인이 아직 설정되지 않았습니다.")
    st = _new_state()
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={quote(GOOGLE_CLIENT_ID)}"
        f"&redirect_uri={quote(SITE_ORIGIN + '/api/auth/google/callback', safe='')}"
        "&response_type=code&scope=openid%20email%20profile"
        f"&state={quote(st)}&prompt=select_account"
    )
    return RedirectResponse(url, status_code=302)


@app.get("/api/auth/google/callback")
def google_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"{SITE_ORIGIN}/#social_error={quote(error)}", status_code=302)
    if not _use_state(state):
        raise HTTPException(400, "로그인 요청이 만료되었습니다. 다시 시도해 주세요.")
    with httpx.Client(timeout=12.0) as client:
        tok = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": SITE_ORIGIN + "/api/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if tok.status_code != 200:
            raise HTTPException(400, "구글 인증에 실패했습니다.")
        access = tok.json().get("access_token", "")
        info = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access}"},
        )
        if info.status_code != 200:
            raise HTTPException(400, "구글에서 정보를 받지 못했습니다.")
        d = info.json()
    return _social_redirect(_social_login(d.get("email", ""), d.get("name", ""), "구글", "google"))


@app.get("/api/auth/kakao/start")
def kakao_start():
    if not KAKAO_REST_API_KEY:
        raise HTTPException(503, "카카오 로그인이 아직 설정되지 않았습니다.")
    st = _new_state()
    url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={quote(KAKAO_REST_API_KEY)}"
        f"&redirect_uri={quote(SITE_ORIGIN + '/api/auth/kakao/callback', safe='')}"
        f"&response_type=code&state={quote(st)}"
    )
    return RedirectResponse(url, status_code=302)


@app.get("/api/auth/kakao/callback")
def kakao_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"{SITE_ORIGIN}/#social_error={quote(error)}", status_code=302)
    if not _use_state(state):
        raise HTTPException(400, "로그인 요청이 만료되었습니다. 다시 시도해 주세요.")
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": SITE_ORIGIN + "/api/auth/kakao/callback",
        "code": code,
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET
    with httpx.Client(timeout=12.0) as client:
        tok = client.post("https://kauth.kakao.com/oauth/token", data=data)
        if tok.status_code != 200:
            raise HTTPException(400, "카카오 인증에 실패했습니다.")
        access = tok.json().get("access_token", "")
        info = client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access}"},
        )
        if info.status_code != 200:
            raise HTTPException(400, "카카오에서 정보를 받지 못했습니다.")
        d = info.json()
    acc = (d.get("kakao_account") or {})
    profile = (acc.get("profile") or {})
    email = acc.get("email") or ""
    name = profile.get("nickname") or ""
    if not email:
        # 이메일 동의를 안 했거나 카카오 계정에 이메일이 없는 경우.
        # 우리 쪽에서만 쓰는 주소를 만들어 계정을 잇는다.
        email = f"kakao{d.get('id')}@kakao.local"
    return _social_redirect(_social_login(email, name, "카카오", "kakao"))


@app.get("/api/me")
def me(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    used = db.get_usage_lifetime(user["email"])
    settings = db.load_settings(user["email"])
    plan = (user.get("plan") or user.get("plan_type") or "free").lower()
    unlimited = (
        plan in ("pro", "enterprise")
        or user.get("is_admin")
        or user.get("is_vip")
    )
    return {
        "user": user,
        "usage": used,
        "limit": FREE_TOTAL_LIMIT,
        "settings": settings,
        "unlimited": unlimited,
        "free_limit_period": "lifetime",
        "remain": None
        if unlimited
        else max(0, FREE_TOTAL_LIMIT - used),
    }


class NameBody(BaseModel):
    name: str


@app.put("/api/me/name")
def me_set_name(body: NameBody, authorization: str | None = Header(default=None)):
    """결과 화면에서 부를 이름을 바꾼다.

    🛑 계산에는 쓰지 않는다. 부르는 말일 뿐이라 아무렇게나 적으셔도 된다.
    """
    user = _token_user(authorization)
    name = (body.name or "").strip()[:20]
    if not name:
        raise HTTPException(400, "이름을 적어 주세요.")
    if not db.set_user_name(user["email"], name):
        raise HTTPException(400, "이름을 바꾸지 못했습니다.")
    return {"ok": True, "name": name}


@app.get("/api/settings")
def get_settings(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return {"settings": db.load_settings(user["email"])}


@app.put("/api/settings")
def put_settings(body: SettingsBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    ok = db.save_settings(user["email"], body.settings)
    if not ok:
        raise HTTPException(500, "설정 저장 실패")
    return {"ok": True, "settings": db.load_settings(user["email"])}


@app.post("/api/generate")
def generate(
    body: GenerateBody,
    request: Request,
    authorization: str | None = Header(default=None),
):
    user = _token_user(authorization)
    ip = _client_ip(request)
    email_key = (user.get("email") or "anon").lower()
    _rate_limit_or_429(
        f"generate:{email_key}",
        limit=GENERATE_LIMIT,
        window_sec=GENERATE_WINDOW,
        what="일지 생성",
    )
    _rate_limit_or_429(
        f"generate-ip:{ip}",
        limit=GENERATE_LIMIT * 2,
        window_sec=GENERATE_WINDOW,
        what="일지 생성",
    )
    plan = (user.get("plan") or user.get("plan_type") or "free").lower()
    used = db.get_usage_lifetime(user["email"])
    unlimited = (
        plan in ("pro", "enterprise")
        or user.get("is_admin")
        or user.get("is_vip")
    )

    if not unlimited and used >= FREE_TOTAL_LIMIT:
        raise HTTPException(
            403,
            f"무료 체험 한도({FREE_TOTAL_LIMIT}회)를 모두 사용했습니다. "
            "Pro로 업그레이드하면 무제한 이용할 수 있습니다.",
        )

    settings = body.settings or db.load_settings(user["email"])
    report_type = (body.report_type or "driving").lower().strip()
    if report_type in ("field", "field_visit", "outing", "외근"):
        report_type = "field"
    else:
        report_type = "driving"

    if body.form:
        form = body.form
    elif report_type == "field":
        form = {
            "visits_text": body.visits_text,
            "work_summary": body.work_summary,
            "next_actions": body.next_actions,
            "department": body.department,
            "extra_note": body.raw_text,
            "author_name": (body.settings or {}).get("driver_name")
            if isinstance(body.settings, dict)
            else "",
        }
    else:
        form = {
            "vehicle_number": body.vehicle_number,
            "odometer_start": body.odometer_start,
            "odometer_end": body.odometer_end,
            "lunch_restaurant": body.lunch_restaurant,
            "morning_places": body.morning_places,
            "afternoon_places": body.afternoon_places,
            "extra_note": body.raw_text,
            "fuel_refueled": False,
            "fuel_amount_krw": None,
            "fuel_liters": None,
        }
    result = generate_driving_log(
        body.raw_text or "",
        settings,
        form=form,
        user_email=user["email"],
        report_type=report_type,
    )

    log = scrub_submission_log(result.get("log") or {})
    result = {**result, "log": log}
    has_content = bool(log.get("trips") or log.get("visits"))
    saved = None
    if log and has_content:
        used = db.increment_usage(user["email"], 1)
        # 생성 성공 시 서버에 자동 저장 (이력)
        try:
            saved = db.save_user_log(
                user["email"],
                log,
                report_type=report_type,
            )
            # 클라이언트 동기화용 id (제출 본문 필드와 분리)
            if isinstance(result.get("log"), dict) and saved.get("id"):
                result = {**result, "log": {**result["log"], "_saved_id": saved["id"]}}
        except Exception as e:
            print(f"[RoadLog] auto-save log failed: {e}", flush=True)

    # 생성 실패·빈 결과면 증가 없음 → 누적 재조회
    if not (log and has_content):
        used = db.get_usage_lifetime(user["email"])
    return {
        **result,
        "usage": used,
        "limit": FREE_TOTAL_LIMIT,
        "free_limit_period": "lifetime",
        "plan": plan,
        "saved": saved,
    }


@app.get("/api/logs")
def api_list_logs(
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    """내 일지 이력 목록."""
    user = _token_user(authorization)
    items = db.list_user_logs(user["email"], limit=limit)
    return {"ok": True, "items": items, "count": len(items)}


@app.get("/api/logs/summary")
def api_logs_summary(
    period: str = Query(default="month", description="week | month | custom"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    """
    주간/월간 업무 요약.
    총 km · 운행/외근 건수 · 방문 Top3 · 복붙용 report_text
    """
    user = _token_user(authorization)
    p = (period or "month").lower().strip()
    if p not in ("week", "month", "custom", "주간", "월간", "7d"):
        p = "month"
    try:
        data = db.summarize_user_logs(
            user["email"],
            period=p,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as e:
        raise HTTPException(500, f"요약 생성 실패: {e}") from e
    return {"ok": True, **data}


@app.get("/api/logs/summary/export")
def api_logs_summary_export(
    period: str = Query(default="month"),
    format: str = Query(default="pdf", description="pdf | xlsx | excel"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    """업무 요약 PDF/Excel 다운로드 (워터마크 없음)."""
    user = _token_user(authorization)
    p = (period or "month").lower().strip()
    if p not in ("week", "month", "custom", "주간", "월간", "7d"):
        p = "month"
    try:
        summary = db.summarize_user_logs(
            user["email"],
            period=p,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as e:
        raise HTTPException(500, f"요약 생성 실패: {e}") from e

    fmt = (format or "pdf").lower().strip()
    try:
        if fmt in ("xlsx", "excel", "xls"):
            data, name = export_summary_excel(summary)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            data, name = export_summary_pdf(summary)
            media = "application/pdf"
    except Exception as e:
        raise HTTPException(500, f"내보내기 실패: {e}") from e

    from urllib.parse import quote

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"
    }
    return Response(content=data, media_type=media, headers=headers)


@app.get("/api/logs/{log_id}")
def api_get_log(log_id: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    item = db.get_user_log(user["email"], log_id)
    if not item:
        raise HTTPException(404, "일지를 찾을 수 없습니다.")
    return {"ok": True, "item": item}


@app.post("/api/logs")
def api_save_log(body: SaveLogBody, authorization: str | None = Header(default=None)):
    """일지 수동 저장·업데이트."""
    user = _token_user(authorization)
    try:
        entry = db.save_user_log(
            user["email"],
            body.log,
            report_type=body.report_type,
            title=body.title,
            log_id=body.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "item": entry}


@app.delete("/api/logs/{log_id}")
def api_delete_log(log_id: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    ok = db.delete_user_log(user["email"], log_id)
    if not ok:
        raise HTTPException(404, "일지를 찾을 수 없습니다.")
    return {"ok": True}


@app.post("/api/validate")
def validate(body: ExportBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    settings = db.load_settings(user["email"])
    v = validate_log(body.log, settings)
    return {
        "ok": v["ok"],
        "log": v["enriched_log"],
        "errors": v["errors"],
        "warnings": v["warnings"],
    }


@app.post("/api/export")
def export(body: ExportBody, authorization: str | None = Header(default=None)):
    _token_user(authorization)
    fmt = (body.format or "").lower().strip()
    clean_log = scrub_submission_log(body.log or {})
    try:
        if fmt in ("excel", "xlsx", "xls"):
            data, name = export_excel(clean_log)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif fmt == "pdf":
            data, name = export_pdf(clean_log)
            media = "application/pdf"
        elif fmt == "docx":
            data, name = export_docx(clean_log)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise HTTPException(400, "format은 excel | xlsx | pdf | docx 중 하나여야 합니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"문서 생성 오류: {e}") from e

    # 한글 파일명은 latin-1 HTTP 헤더에 못 들어가 Content-Disposition 500 유발
    # → ASCII fallback + RFC 5987 filename* (UTF-8)
    safe_ascii = re.sub(r"[^\w.\-]+", "_", name, flags=re.ASCII).strip("._") or "roadlog.bin"
    if not re.search(r"\.\w+$", safe_ascii):
        # 확장자 보존
        ext = Path(name).suffix or ""
        safe_ascii = f"roadlog{ext}" if ext else "roadlog.bin"
    cd = f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{quote(name)}"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": cd},
    )


# ── 서식·말투 학습 ─────────────────────────────────────


@app.get("/api/style")
def style_status(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return style_learn.list_style_status(user["email"])


@app.post("/api/style/upload")
async def style_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = _token_user(authorization)
    data = await file.read()
    try:
        return style_learn.add_sample_from_upload(
            user["email"],
            file.filename or "upload.bin",
            data,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"업로드 처리 오류: {e}") from e


@app.post("/api/style/paste")
def style_paste(body: StyleTextBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        return style_learn.add_sample_from_text(user["email"], body.title, body.text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/style/learn")
def style_learn_now(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        result = style_learn.learn_style(user["email"])
        status = style_learn.list_style_status(user["email"])
        status["learn"] = result
        return status
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/style/samples/{sample_id}")
def style_delete(sample_id: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        return style_learn.delete_sample(user["email"], sample_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/style/samples/{sample_id}/activate")
def style_activate(sample_id: str, authorization: str | None = Header(default=None)):
    """주 사용 회사 서식으로 지정."""
    user = _token_user(authorization)
    try:
        return style_learn.set_active_sample(user["email"], sample_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ── 관리자 운영 ───────────────────────────────────────


class BillingBody(BaseModel):
    pro_price_krw: int
    enterprise_price_krw: int
    pro_annual_price_krw: int | None = None
    pro_annual_monthly_eq_krw: int | None = None
    enterprise_annual_price_krw: int | None = None
    enterprise_annual_monthly_eq_krw: int | None = None
    enterprise_base_seats: int | None = None
    enterprise_seat_price_krw: int | None = None
    enterprise_seat_annual_price_krw: int | None = None


class FreePassBody(BaseModel):
    email: str
    on: bool = True


class VipBody(BaseModel):
    id: str
    email: str = ""
    note: str = ""


class ReviewBody(BaseModel):
    text: str
    text_en: str = ""
    name: str
    name_en: str = ""
    role: str = ""
    role_en: str = ""
    initial: str = ""
    stars: int = 5
    published: bool = True
    sort_order: int | None = None


class ReviewPublishBody(BaseModel):
    published: bool


@app.get("/api/reviews")
def public_reviews():
    """비로그인 랜딩용 공개 후기."""
    items = reviews_ops.list_public_reviews()
    return {"reviews": items, "count": len(items)}


@app.get("/api/stats/visitors")
def stats_visitors(
    response: Response,
    request: Request,
    rl_vid: str | None = Cookie(default=None, alias=visitors_ops.COOKIE_NAME),
    hit: int = Query(default=1, ge=0, le=1),
):
    """
    총 방문자 수 (브라우저 쿠키 기준 1회 카운트).
    hit=0 이면 조회만, hit=1(기본) 이면 신규 방문자 시 +1.
    localhost / webdriver 는 프론트에서 hit=0 권장.
    """
    if hit == 0:
        return {"total": visitors_ops.get_total(), "counted": False}
    total, vid, is_new = visitors_ops.touch_visitor(rl_vid)
    response.set_cookie(
        key=visitors_ops.COOKIE_NAME,
        value=vid,
        max_age=visitors_ops.COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=bool(is_production()),
        path="/",
    )
    return {"total": total, "counted": is_new}


@app.get("/api/admin/reviews")
def admin_reviews_list(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    items = reviews_ops.list_admin_reviews()
    return {"reviews": items, "count": len(items)}


@app.post("/api/admin/reviews")
def admin_reviews_create(
    body: ReviewBody, authorization: str | None = Header(default=None)
):
    _require_admin(authorization)
    try:
        row = reviews_ops.create_review(body.model_dump())
        return {
            "ok": True,
            "review": row,
            "reviews": reviews_ops.list_admin_reviews(),
        }
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.put("/api/admin/reviews/{review_id}")
def admin_reviews_update(
    review_id: str,
    body: ReviewBody,
    authorization: str | None = Header(default=None),
):
    _require_admin(authorization)
    try:
        row = reviews_ops.update_review(review_id, body.model_dump())
        return {
            "ok": True,
            "review": row,
            "reviews": reviews_ops.list_admin_reviews(),
        }
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.patch("/api/admin/reviews/{review_id}/publish")
def admin_reviews_publish(
    review_id: str,
    body: ReviewPublishBody,
    authorization: str | None = Header(default=None),
):
    _require_admin(authorization)
    try:
        row = reviews_ops.set_review_published(review_id, body.published)
        return {
            "ok": True,
            "review": row,
            "reviews": reviews_ops.list_admin_reviews(),
        }
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@app.delete("/api/admin/reviews/{review_id}")
def admin_reviews_delete(
    review_id: str, authorization: str | None = Header(default=None)
):
    _require_admin(authorization)
    ok = reviews_ops.delete_review(review_id)
    if not ok:
        raise HTTPException(404, "후기를 찾을 수 없습니다.")
    return {"ok": True, "reviews": reviews_ops.list_admin_reviews()}


# ── 방문자 세기 ──────────────────────────────────────────
# 화면(HTML)이 열릴 때만 센다. 자산·API·검색봇은 세지 않는다.
# 링크를 붙여 넣기만 해도 긁어 가는 미리보기 크롤러들이 있다.
# 이들은 UA 에 「bot」이 없고 IP 도 매번 달라서, 안 막으면 방문자 수가 부풀려진다.
_BOT = ("bot", "crawler", "spider", "slurp", "headless", "preview",
        "monitor", "curl", "wget", "python-requests", "httpx", "lighthouse",
        "facebookexternalhit", "meta-externalagent", "meta-externalfetcher",
        "whatsapp", "telegram", "discord", "slack", "embedly", "quora link",
        "skypeuripreview", "applebot", "yeti", "daum", "kakaotalk-scrap",
        "naver", "petalbot", "ahrefs", "semrush", "dataprovider", "linkedinbot")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


@app.middleware("http")
async def _count_visit(request: Request, call_next):
    resp = await call_next(request)
    try:
        p = request.url.path
        # 내가 보는 것은 안 센다. roadlog.co.kr/?nocount=1 을 한 번 열면
        # 이 브라우저에 표시가 남아서 그다음부터 계속 빠진다.
        if request.query_params.get("nocount") in ("1", "on"):
            resp.set_cookie("rl_nocount", "1", max_age=400 * 86400,
                            samesite="lax", path="/")
            return resp
        if request.query_params.get("nocount") == "0":
            resp.delete_cookie("rl_nocount", path="/")
            return resp
        if request.cookies.get("rl_nocount") == "1":
            return resp
        if (
            request.method == "GET"
            and resp.status_code == 200
            and not p.startswith("/api")
            and not p.startswith("/assets")
            and (p == "/" or p.endswith(".html"))
            and "admin" not in p
        ):
            ua = request.headers.get("user-agent", "") or ""
            low = ua.lower()
            # 진짜 브라우저는 UA 에 Mozilla 가 들어 있다. 크롤러 대부분은 없다.
            looks_browser = "mozilla" in low
            if ua and looks_browser and not any(b in low for b in _BOT):
                # 🛑 **링크에 붙여 보낸 utm 이 referrer 보다 정확하다** (2026-09-11).
                #    카카오톡·인스타는 referrer 를 안 주거나 뭉갠다.
                q = request.query_params
                stats_ops.hit(
                    _client_ip(request), ua, p,
                    request.headers.get("referer", "") or "",
                    request.url.hostname or "",
                    utm=q.get("utm_source", "") or "",
                    campaign=q.get("utm_campaign", "") or "",
                )
    except Exception:
        pass          # 통계 때문에 화면이 막히면 안 된다
    return resp


@app.delete("/api/admin/stats/visits")
def admin_stats_reset(authorization: str | None = Header(default=None),
                      day: str = ""):
    """방문 기록 지우기. day 를 주면 그 하루만, 안 주면 전부."""
    _require_admin(authorization)
    return {"ok": True, "removed": stats_ops.forget_visits(day or None)}


@app.get("/api/admin/stats")
def admin_stats(authorization: str | None = Header(default=None), days: int = 30):
    """매출·가입·방문자·유입경로를 한 번에."""
    _require_admin(authorization)
    return stats_ops.overview(days=max(1, min(days, 90)))


@app.get("/api/admin/dashboard")
def admin_dashboard(
    authorization: str | None = Header(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
):
    """매출 대시보드. date_from / date_to = YYYY-MM-DD (기간 합산·날짜별)."""
    _require_admin(authorization)
    return admin_ops.revenue_dashboard(date_from=date_from, date_to=date_to)


@app.get("/api/admin/usage")
def admin_usage(
    authorization: str | None = Header(default=None),
    month: str | None = None,
):
    """무료/유료 회원 이번 달 생성 횟수 집계."""
    _require_admin(authorization)
    return admin_ops.usage_dashboard(month=month)


@app.put("/api/admin/billing")
def admin_billing(body: BillingBody, authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    try:
        cfg = admin_ops.save_billing_config(
            body.pro_price_krw,
            body.enterprise_price_krw,
            updated_by=admin.get("email") or "",
            pro_annual_price=body.pro_annual_price_krw,
            pro_annual_monthly_eq=body.pro_annual_monthly_eq_krw,
            enterprise_annual_price=body.enterprise_annual_price_krw,
            enterprise_annual_monthly_eq=body.enterprise_annual_monthly_eq_krw,
            enterprise_base_seats=body.enterprise_base_seats,
            enterprise_seat_price=body.enterprise_seat_price_krw,
            enterprise_seat_annual_price=body.enterprise_seat_annual_price_krw,
        )
        return {"ok": True, "billing": cfg}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ── 쿠폰 ──────────────────────────────────────────────
# 🛑 **깎아 주는 쿠폰은 만들지 않는다.** 결제 금액이 화면과 달라지면 카드사 심사의
#    「노출 금액 = 결제창 금액」에 걸린다. 대신 **한 편을 열어 주는** 방식이다 —
#    선착순 이벤트가 이미 같은 방식으로 돌고 있다.


class CouponMake(BaseModel):
    code: str
    cap: int = 50
    note: str = ""


class CouponUse(BaseModel):
    code: str
    product: str
    pair: str


@app.get("/api/admin/coupons")
def admin_coupons(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules import coupons as coupons_ops
    return {"items": coupons_ops.listing()}


@app.post("/api/admin/coupons")
def admin_coupon_make(body: CouponMake, authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    from modules import coupons as coupons_ops
    try:
        got = coupons_ops.make(body.code, cap=body.cap, note=body.note,
                               by=admin.get("email") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "coupon": got}


@app.delete("/api/admin/coupons/{code}")
def admin_coupon_drop(code: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules import coupons as coupons_ops
    coupons_ops.drop(code)
    return {"ok": True}


@app.post("/api/coupon/use")
def coupon_use(body: CouponUse, authorization: str | None = Header(default=None)):
    """손님이 코드를 넣어 한 편을 연다. 🛑 복채를 받지 않는다."""
    user = _token_user(authorization)
    from modules import coupons as coupons_ops

    product = (body.product or "").strip()[:24]
    pair = (body.pair or "").strip()
    if not lamps_ops.won_of(product) and product not in lamps_ops.PRICES:
        raise HTTPException(400, "없는 상품이에요.")
    try:
        coupons_ops.check(body.code, user["email"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        out = lamps_ops.gift_open(user["email"], product, pair,
                                  note="쿠폰 %s" % (body.code or "").strip().upper())
    except ValueError as e:
        raise HTTPException(400, str(e))
    got = coupons_ops.use(body.code, user["email"])
    return {"ok": True, **out, **got}


# ── 공유 눌림 세기 ────────────────────────────────────
# 🛑 카드가 퍼져야 손님이 온다. 몇 번 저장하고 몇 번 공유했는지가 **바이럴의 온도**다.
#    로그인 없이도 받는다 — 누가 눌렀는지는 안 남긴다.


class TapBody(BaseModel):
    what: str
    product: str = ""


@app.post("/api/tap")
def tap_event(body: TapBody):
    try:
        stats_ops.tap(body.what or "", body.product or "")
    except Exception:                                    # noqa: BLE001
        pass                                             # 통계 때문에 화면이 막히면 안 된다
    return {"ok": True}


# ── 환불 ──────────────────────────────────────────────
# 🛑 **되돌릴 수 없는 일이다.** 주인만 부를 수 있고, 까닭을 반드시 적게 한다.
#    포트원에 취소를 넣고 → 원장에 남기고 → **열어 둔 리포트를 닫는다.**
#    셋 중 하나라도 빠지면 돈만 나가거나 글만 사라진다.


class RefundBody(BaseModel):
    email: str
    paymentId: str
    why: str = ""


class RegiftBody(BaseModel):
    # 🛑 기본은 **세어만 본다.** 얼마가 나가는지 보고 나서 켠다
    apply: bool = False


@app.post("/api/admin/lamps/regift")
def admin_regift(body: RegiftBody, authorization: str | None = Header(default=None)):
    """등불 계단을 올렸을 때 **이미 복채를 내신 분께 차액을 드린다** (2026-09-11 온해님).

    🛑 두 번 눌러도 두 번 주지 않는다 — 원장에 준 표시를 남긴다.
    """
    _require_admin(authorization)
    try:
        got = lamps_ops.regift(apply=bool(body.apply))
    except Exception as e:                              # noqa: BLE001
        raise HTTPException(500, "차액을 드리다 막혔어요: %s" % str(e)[:120])
    # 🛑 **받은 줄 모르면 준 게 아니다.** 알림함에 한 줄 남긴다 (`modules/inbox.py`)
    if body.apply:
        for r in got.get("rows", []):
            try:
                inbox.push(
                    r["email"], "등불을 더 드렸어요",
                    "복채를 내신 분께 드리는 등불을 늘렸어요. 이미 결제하신 분께도 "
                    "차액 %d개를 얹어 드렸습니다. 무냥이에게 더 물어보실 때 쓰시면 돼요."
                    % r["more"],
                    key="regift-%s-%s" % (r.get("product") or "", r["more"]),
                )
            except Exception:                           # noqa: BLE001
                pass                                    # 알림이 막혀도 등불은 이미 나갔다
    return got


@app.post("/api/admin/refund")
def admin_refund(body: RefundBody, authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    pid = (body.paymentId or "").strip()
    email = (body.email or "").strip().lower()
    why = (body.why or "").strip()
    if not pid or not email:
        raise HTTPException(400, "결제번호와 이메일이 필요합니다.")
    if len(why) < 2:
        raise HTTPException(400, "환불 까닭을 적어 주세요. 나중에 왜 돌려줬는지 알아야 합니다.")
    if not PORTONE_API_SECRET:
        raise HTTPException(503, "결제 설정이 안 되어 있어 취소를 넣을 수 없어요.")

    # ① 포트원에 취소를 넣는다
    try:
        r = httpx.post(
            f"https://api.portone.io/payments/{quote(pid, safe='')}/cancel",
            headers={"Authorization": f"PortOne {PORTONE_API_SECRET}",
                     "Content-Type": "application/json"},
            json={"reason": why[:200]},
            timeout=20.0,
        )
    except Exception:                                    # noqa: BLE001
        raise HTTPException(502, "포트원에 닿지 못했습니다. 잠시 뒤 다시 해 주세요.")
    if r.status_code not in (200, 201):
        # 🛑 이미 취소된 건은 그냥 넘어간다 — 원장 정리는 해야 하기 때문이다
        msg = str(r.text)[:200]
        if "ALREADY_CANCELLED" not in msg.upper().replace("_", "").replace(" ", ""):
            raise HTTPException(400, "취소하지 못했습니다: %s" % msg)

    # ② 원장에 남기고 열어 둔 것을 닫는다
    try:
        got = lamps_ops.refund(email, pid, why=why)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # ③ 손님에게 알린다 — 말없이 닫으면 「글이 사라졌다」가 된다
    try:
        inbox.push(
            email, "복채를 돌려드렸어요",
            "%s원 결제를 취소했어요. 카드사에 따라 며칠 걸릴 수 있어요. "
            "열어 두었던 글은 닫혔습니다." % format(int(got.get("price") or 0), ","),
            key="refund:%s" % pid)
    except Exception:                                    # noqa: BLE001
        pass

    return {"ok": True, "by": admin.get("email") or "", **got}


# ── 프롬프트 관리 ──────────────────────────────────────
# 🛑 **말투를 코드 배포 없이 고친다** (2026-09-11 온해님 명세).
#    무냥이·관멍이가 쓰는 글의 결을 관리자 화면에서 고치고 그 자리에서 시험해 본다.
#    저장은 `DATA_DIR/prompts.json` — 이 서비스는 DB 없이 JSON 으로 돈다.
#
# 🛑 **이미 써 둔 글은 안 바뀐다.** 리포트는 한 번 쓰면 저장하고 다시 안 쓰기 때문이다.
#    고친 말투는 **그 뒤에 새로 쓰는 글부터** 나온다.


class PromptBody(BaseModel):
    text: str


@app.get("/api/admin/prompts")
def admin_prompts(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules import prompts as prompts_ops
    return {"items": prompts_ops.listing()}


@app.put("/api/admin/prompts/{key}")
def admin_prompt_put(key: str, body: PromptBody,
                     authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    from modules import prompts as prompts_ops
    try:
        got = prompts_ops.put(key, body.text, who=admin.get("email") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "saved": got}


@app.delete("/api/admin/prompts/{key}")
def admin_prompt_reset(key: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules import prompts as prompts_ops
    prompts_ops.reset(key)
    return {"ok": True}


@app.post("/api/admin/prompts/{key}/try")
def admin_prompt_try(key: str, body: PromptBody,
                     authorization: str | None = Header(default=None)):
    """🛑 **진짜로 한 번 돌려 본다.** 저장하지 않고, 준 글로만 시험한다.

    값이 든다(한 번에 1원 안팎). 저장 전에 결과를 보고 정하시라고 둔 자리다.
    """
    _require_admin(authorization)
    from modules import prompts as prompts_ops
    from modules import saju_writer

    text = str(body.text or "").strip()
    if len(text) < 40:
        raise HTTPException(400, "프롬프트가 너무 짧습니다.")
    if not saju_writer.ready():
        raise HTTPException(503, "Gemini 키가 없어 시험할 수 없어요.")

    # 시험용 재료 — 실제 손님 자료를 쓰지 않는다
    SAMPLE = {
        "saju": "[사주]\n나를 뜻하는 글자: 무쇠(경금)\n곁을 내주는 자리: 술토\n"
                "넘치는 것: 흙\n비어 있는 것: 물\n\n[이 항목] 연애에서 넘치는 것과 비는 것\n"
                "[길이] 300자 안팎",
        "card": "[무엇에 대한 카드인가] 내 연애 사주\n[받은 재료]\n"
                "  손님이 물은 것 : 나는 왜 늘 같은 이별을 할까?\n"
                "  무냥이가 쓴 글 : 먼저 다가서고 먼저 지치는 자리가 뚜렷해요.",
        "past": "[무엇에 대한 카드인가] 전생\n[받은 재료]\n"
                "  전생의 일 : 나루터에서 짐을 나르던 사람\n  그때의 결 : 부탁을 못 거절했어요\n"
                "  어떻게 마쳤나 : 빚을 남기고 떠났다\n  못다 한 것 : 제 몫의 삯\n"
                "  남은 버릇 : 남 먼저 챙기는 편",
        "god": "[무엇에 대한 카드인가] 수호신\n[받은 재료]\n"
               "  정해진 등급 : A급\n  이 등급이 뜻하는 것 : A급 — 똥차·사기꾼을 걸러 주는 팩폭형\n"
               "  정해진 이름 : 대신할머니\n  왼쪽에 서는 이 : 바리공주\n"
               "  오른쪽에 서는 이 : 선녀\n  짐승 : 돼지",
        "summary": "[결과지]\n먼저 다가서고 먼저 지치는 자리가 뚜렷해요. 마음을 다 준 뒤에야 "
                   "상대의 온도를 확인하는 편이라, 끝날 때마다 혼자 남은 기분이 들어요.",
        "gwan": "[손님이 물은 것] 금사빠일까, 팍 식어서 덤덤해지는 스타일일까?\n"
                "[볼 자리] 연애할 때 나오는 얼굴 / 가까워질 때의 속도\n"
                "(사진 없이 말투만 시험합니다. 자리 이름에 맞춰 두 문단만 써 주세요.)",
        # 🛑 대화 둘은 **손님이 실제로 묻는 모양**으로 시험한다. 밋밋한 재료로 돌리면
        #    말투가 좋은지 나쁜지 가릴 수가 없다 (2026-09-11 온해님)
        "ask": "손님 이름: 지현\n\n[사주]\n나를 뜻하는 글자: 무쇠(경금)\n"
               "곁을 내주는 자리: 술토\n넘치는 것: 흙\n비어 있는 것: 물\n\n"
               "[손님이 묻는 것]\n헤어진 지 두 달인데 아직 연락이 없어요. 먼저 해도 될까요?",
        "gwan_ask": "손님 이름: 지현\n\n[관멍이가 본 것]\n"
                    "## 연애할 때 나오는 얼굴\n눈꼬리가 부드럽게 내려앉아서 처음 보는 사람도 "
                    "쉽게 말을 붙여요. 다만 입꼬리가 야무지게 다물려 있어서, 정작 마음은 "
                    "천천히 여는 편이에요.\n\n## 가까워질 때의 속도\n한 번 마음을 열면 "
                    "빠르게 기울어요.\n\n[손님이 묻는 것]\n제가 금사빠라는 건가요?",
    }
    user = SAMPLE.get(key) or "시험 삼아 두 문단만 써 주세요."
    try:
        res = saju_writer._call(text, user, temperature=1.0, max_tokens=700)
    except Exception as e:                               # noqa: BLE001
        raise HTTPException(502, "돌려 보지 못했어요: %s" % str(e)[:160])
    out = str(res.get("text") or "").strip()
    return {"ok": True, "text": out,
            "in": res.get("in", 0), "out": res.get("out", 0),
            "note": "저장하지 않았습니다. 마음에 들면 「저장」을 눌러 주세요."}


@app.get("/api/admin/freepass")
def admin_freepass_list(authorization: str | None = Header(default=None)):
    """복채를 내지 않고 다 보시는 분들. 관리자 화면은 열리지 않는다."""
    _require_admin(authorization)
    return {"emails": sorted(_free_pass())}


@app.post("/api/admin/freepass")
def admin_freepass_set(body: FreePassBody, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return {"ok": True, "emails": _free_pass_set(body.email, body.on)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/admin/vip")
def admin_vip_list(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {"vip_members": admin_ops.load_vip_members()}


@app.post("/api/admin/vip")
def admin_vip_add(body: VipBody, authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    try:
        row = admin_ops.add_vip(
            body.id,
            email=body.email,
            note=body.note,
            added_by=admin.get("email") or "",
        )
        return {"ok": True, "member": row, "vip_members": admin_ops.load_vip_members()}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/admin/vip/{member_id}")
def admin_vip_remove(member_id: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    ok = admin_ops.remove_vip(member_id)
    if not ok:
        raise HTTPException(404, "VIP 회원을 찾을 수 없습니다.")
    return {"ok": True, "vip_members": admin_ops.load_vip_members()}


def _drop_sessions_for_email(email: str) -> int:
    """메모리·디스크 세션에서 해당 회원 토큰 제거."""
    email = (email or "").strip().lower()
    if not email:
        return 0
    drop = [tok for tok, u in list(_sessions.items()) if (u.get("email") or "").lower() == email]
    for tok in drop:
        _sessions.pop(tok, None)
    if drop:
        _persist_sessions()
    return len(drop)


@app.delete("/api/admin/users/{email}")
def admin_delete_user(email: str, authorization: str | None = Header(default=None)):
    """단일 회원 삭제 (관리자 제외)."""
    _require_admin(authorization)
    result = db.delete_user(email)
    if not result.get("ok"):
        reason = result.get("reason") or "failed"
        if reason == "not_found":
            raise HTTPException(404, "회원을 찾을 수 없습니다.")
        if reason == "admin_protected":
            raise HTTPException(400, "관리자 계정은 삭제할 수 없습니다.")
        raise HTTPException(400, reason)
    n = _drop_sessions_for_email(email)
    result["sessions_dropped"] = n
    return result


@app.post("/api/admin/users/purge-testers")
def admin_purge_testers(authorization: str | None = Header(default=None)):
    """테스터·QA 계정 일괄 삭제. 관리자·실사용 패턴은 유지."""
    _require_admin(authorization)
    result = db.purge_tester_users()
    dropped = 0
    for row in result.get("deleted") or []:
        dropped += _drop_sessions_for_email(row.get("email") or "")
    result["sessions_dropped"] = dropped
    return result


# ── 정적 파일 ─────────────────────────────────────────

_TEXT_MEDIA = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


def _file_response(path: Path, status_code: int = 200) -> FileResponse:
    """UTF-8 charset을 붙여 한글 UI 깨짐을 방지. SW·앱 셸은 캐시 재검증 강제."""
    media = _TEXT_MEDIA.get(path.suffix.lower())
    name = path.name.lower()
    # 설치 앱(PWA)이 옛 sw.js/HTML/JS에 묶이지 않도록
    no_store_names = {
        "sw.js",
        "index.html",
        "app.js",
        "styles.css",
        "manifest.webmanifest",
        "update.html",
        "build.json",
    }
    headers: dict[str, str] = {}
    if name in no_store_names or path.suffix.lower() in {".json"} and "locales" in str(path).replace("\\", "/"):
        headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        headers["Pragma"] = "no-cache"
    elif path.suffix.lower() in {".js", ".css", ".html", ".webmanifest"}:
        headers["Cache-Control"] = "no-cache, must-revalidate"
    if media:
        return FileResponse(path, media_type=media, headers=headers or None, status_code=status_code)
    return FileResponse(path, headers=headers or None, status_code=status_code)



# ── 등불(선불 재화) ────────────────────────────────────
# 사주 리포트를 여는 데 쓰는 사내 재화. 등불 1개 = 100원.
# 생년월일은 서버로 오지 않는다 — 어떤 두 사람인지는 브라우저가 만든 해시로만 구분한다.

PORTONE_API_SECRET = (os.environ.get("PORTONE_API_SECRET") or "").strip()


class ChargeBody(BaseModel):
    paymentId: str


class OpenBody(BaseModel):
    product: str
    pair: str


class PremiumBody(BaseModel):
    product: str
    pair: str
    paymentId: str


class GwansangBody(BaseModel):
    """관상 — 얼굴 사진으로 본다.

    🛑 사진은 **저장하지 않는다.** 받은 그대로 Gemini 로 넘기고 버린다.
       그래서 multipart(UploadFile) 가 아니라 base64 본문으로 받는다 —
       multipart 는 크면 임시 파일로 디스크에 떨어진다.
    """
    # 🛑 사진으로 만든 해시. 사주쌍 자리에 쓴다 (관상은 생년월일이 없다)
    pair: str = ""
    # 사진 해시. 같은 표(pair) 로 사진 셋까지 본다
    shot: str = ""
    # 볼 자리. 정본은 `gwansang.js` 의 `sections` 다
    sections: list[str] = []
    # 🛑 상품의 질문. 카드 제목이 이것이라 **문구도 이 물음에 답해야** 한다 (2026-09-10)
    q: str = ""
    product: str
    shots: list[str]          # data URL 또는 base64 jpeg. 「둘이 보는 관상」만 두 장
    name: str = ""


class AskBody(BaseModel):
    qid: str
    pair: str


def _verify_payment(payment_id: str) -> dict:
    """포트원 V2 로 결제를 다시 확인한다. 프론트가 보낸 금액은 믿지 않는다."""
    if not PORTONE_API_SECRET:
        raise HTTPException(503, "결제 확인 설정이 아직 되어 있지 않습니다. 잠시 뒤 다시 시도해 주세요.")
    try:
        r = httpx.get(
            f"https://api.portone.io/payments/{quote(payment_id, safe='')}",
            headers={"Authorization": f"PortOne {PORTONE_API_SECRET}"},
            timeout=10.0,
        )
    except Exception:
        raise HTTPException(502, "결제 확인 중 통신 오류가 났습니다.")
    if r.status_code != 200:
        raise HTTPException(400, "결제 내역을 찾지 못했습니다.")
    data = r.json()
    if data.get("status") != "PAID":
        raise HTTPException(400, "결제가 완료되지 않았습니다.")
    return data


@app.get("/api/lamps/ready")
def lamps_ready():
    """결제 확인용 시크릿이 서버에 들어와 있는지만 알려 준다. 값은 내보내지 않는다.

    🛑 **글이 안 써지면 복채를 받지 않는다** (2026-09-10 온해님). 무냥이 글은
       Gemini 가 쓰는데, 잔액이 0이 되면 그 키가 통째로 멈춘다. 그래도 계산 글은
       나가기 때문에 **복채를 내고 무냥이 글이 빠진 리포트**를 받게 된다.
       그게 안 파는 것보다 나쁘다. 그래서 막히면 스스로 닫는다.
    🛑 충전하시면 **저절로 다시 열린다** — 다음 호출이 성공하는 순간 풀린다.
    """
    busy = saju_writer.down()
    return {"portone_secret_set": bool(PORTONE_API_SECRET),
            "pay_open": PAY_OPEN and not busy,
            "busy": busy,
            "sale_until": SALE_UNTIL}


def _is_owner(user: dict) -> bool:
    """관리자(사이트 주인)인가. 주인은 등불을 쓰지 않는다."""
    return bool(user.get("is_admin"))


# ── 무료 이용권 ────────────────────────────────────────
# 지인처럼 복채를 내지 않고 다 보시는 분들. 관리자와 달리 **운영 화면은 못 본다.**
# 🛑 이메일을 코드에 박지 않는다. DATA_DIR 에 두고 관리자 API 로 넣고 뺀다.
# 🛑 결제가 실제로 돈을 받는가. 기본은 **닫힘**이다 (2026-09-07).
#    테스트 채널이 걸린 동안에는 결제창이 PAID 를 돌려주기 때문에, 열어 두면
#    돈은 안 들어오는데 리포트만 나간다. 실제로 9,800원어치가 그렇게 열렸다.
#    PG 승인이 나고 pay.html 의 CHANNEL_KEY 를 실채널로 바꾼 뒤에
#    Railway 에 PAY_OPEN=1 을 넣어 연다.
PAY_OPEN = os.getenv("PAY_OPEN", "").strip() in ("1", "true", "TRUE", "yes")

# 오픈 기념 할인 마감일 (YYYY-MM-DD). 비어 있으면 화면에 아무것도 안 뜬다.
# 🛑 적어 둔 날이 오면 **실제로 값을 올리거나 마감을 다시 밝힌다.** 지나고도 그대로 두면
#    거짓 할인이고, 전자상거래법이 금지하는 과장 광고다. 새로고침마다 시간이 되살아나는
#    「1시간 남음」 류를 쓰지 않는 이유도 같다 (2026-09-07).
SALE_UNTIL = (os.getenv("SALE_UNTIL", "") or "").strip()[:10]

_FREE_PASS_PATH = DATA_DIR / "free_pass.json"


def _free_pass() -> set[str]:
    try:
        return {str(e).strip().lower() for e in json.loads(_FREE_PASS_PATH.read_text("utf-8")) if str(e).strip()}
    except Exception:
        return set()


def _free_pass_set(email: str, on: bool) -> list[str]:
    """무료 이용권 명단에 넣거나 뺀다. 관리자만 부른다."""
    e = (email or "").strip().lower()
    if not e or "@" not in e:
        raise ValueError("이메일이 아닙니다.")
    cur = _free_pass()
    cur.add(e) if on else cur.discard(e)
    _FREE_PASS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FREE_PASS_PATH.write_text(json.dumps(sorted(cur), ensure_ascii=False, indent=1), "utf-8")
    return sorted(cur)


def _is_free(user: dict) -> bool:
    """복채를 내지 않고 다 볼 수 있는 분인가. 주인 + 무료 이용권 명단.

    🛑 관리자 전용 기능(운영 화면·회원 삭제)에는 쓰지 않는다. 그건 _is_owner 그대로다.
    """
    return _is_owner(user) or (user.get("email") or "").strip().lower() in _free_pass()


# ── 선착순 100분 · 한 편 무료 ────────────────────────────
# 왜: 결제가 아직 안 열려서 복채가 있는 리포트를 아무도 못 연다. 그동안 먼저 들러
#     가입해 주신 분들께 **아무 상품이나 한 편**을 복채 없이 열어 드린다
#     (2026-09-08 온해님 지시 · 스레드에 이미 알렸다).
#
# 🛑 세는 사람에서 빠지는 계정: 관리자 · 테스트 계정 · 무료 이용권(VIP).
#    이분들은 어차피 다 열리니 자리를 차지하면 진짜 손님 몫이 줄어든다.
# 🛑 순번은 **가입 시각 순**이다. 자리가 다 차면 그 뒤로 가입한 분은 대상이 아니다.
# 🛑 한 계정에 한 편. 어느 편을 여셨는지는 lamps 원장(type="gift-open")에 남는다.
EVENT_FREE_N = int(os.getenv("EVENT_FREE_N", "100") or 100)
EVENT_FREE_ON = os.getenv("EVENT_FREE_ON", "1").strip() not in ("0", "false", "FALSE", "no")


def _gift_line() -> list[str]:
    """이벤트 자리를 차지하는 계정만 가입 순으로 늘어놓는다."""
    free = _free_pass()
    out = []
    for u in db.list_users():
        email = (u.get("email") or "").strip().lower()
        if not email or "@" not in email:
            continue
        if u.get("is_admin") or email in free:
            continue
        if db.is_tester_account(u):
            continue
        out.append((u.get("created_at") or "9999", email))
    out.sort()
    return [e for _, e in out]


def _gift_state(user: dict | None) -> dict:
    line = _gift_line()
    taken = min(len(line), EVENT_FREE_N)
    st = {
        "on": EVENT_FREE_ON,
        "cap": EVENT_FREE_N,
        "taken": taken,
        "left": max(0, EVENT_FREE_N - len(line)),
        "eligible": False,
        "rank": 0,
        "used": None,
    }
    if not user:
        return st
    email = (user.get("email") or "").strip().lower()
    if email in line:
        st["rank"] = line.index(email) + 1
        st["eligible"] = EVENT_FREE_ON and st["rank"] <= EVENT_FREE_N
    st["used"] = lamps_ops.gift_used(email)
    return st


@app.get("/api/gift")
def gift_state(authorization: str | None = Header(default=None)):
    """선착순 이벤트 상태. 비회원도 남은 자리는 본다."""
    return _gift_state(_maybe_user(authorization))


class GiftBody(BaseModel):
    product: str
    pair: str


@app.post("/api/gift/open")
def gift_open(body: GiftBody, authorization: str | None = Header(default=None)):
    """이벤트로 한 편을 연다. 한 계정에 한 번만."""
    user = _token_user(authorization)
    st = _gift_state(user)
    if st["used"]:
        raise HTTPException(400, "이 이벤트는 한 분께 한 편만 열어 드려요.")
    if not st["eligible"]:
        raise HTTPException(403, "선착순 100분 이벤트가 마감됐어요.")
    product = (body.product or "").strip()[:24]
    if not lamps_ops.won_of(product) and product not in lamps_ops.PRICES:
        raise HTTPException(400, "없는 상품이에요.")
    try:
        out = lamps_ops.gift_open(user["email"], product, (body.pair or "").strip(),
                                  note="선착순 %d분 이벤트 · %d번" % (EVENT_FREE_N, st["rank"]))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return out


@app.get("/api/lamps")
def lamps_status(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    st = lamps_ops.status(user["email"])
    if _is_free(user):
        # 주인은 무제한. 화면이 잔액을 그대로 보여 주므로 큰 수를 넣어 둔다.
        st["balance"] = 999999
        st["unlimited"] = True
        st["expiring_lamps"] = 0
        st["expires_soonest"] = None
    return st


@app.get("/api/lamps/ledger")
def lamps_ledger(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return {"items": lamps_ops.ledger(user["email"])}


@app.post("/api/lamps/charge")
def lamps_charge(body: ChargeBody, authorization: str | None = Header(default=None), request: Request = None):
    user = _token_user(authorization)
    if request is not None:
        _rate_limit_or_429(f"charge:{_client_ip(request)}", limit=20, window_sec=600, what="충전")
    paid = _verify_payment(body.paymentId.strip())
    amount = int((paid.get("amount") or {}).get("total") or 0)
    lamps = lamps_ops.pack_for_amount(amount)
    if not lamps:
        raise HTTPException(400, "충전 패키지와 결제 금액이 맞지 않습니다. 고객센터로 문의해 주세요.")
    try:
        return lamps_ops.charge(user["email"], lamps, payment_id=body.paymentId.strip(), price=amount)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── 상품별 손님 후기 ──────────────────────────────────────
class ReviewBody(BaseModel):
    rating: int = 5
    text: str = ""
    stem: str = ""          # 일간 한 글자. 후기에 붙일 표시를 정한다 (없어도 된다)


def _maybe_user(authorization: str | None) -> dict | None:
    """로그인했으면 사용자, 아니면 None. 후기 목록은 비회원도 본다."""
    if not authorization:
        return None
    try:
        return _token_user(authorization)
    except Exception:
        return None


def _can_review(email: str, product: str) -> bool:
    """그 상품을 실제로 연 사람만 후기를 쓴다."""
    try:
        acc = lamps_ops.status(email)
    except Exception:
        return False
    return any(o.get("product") == product for o in acc.get("owned", []))


@app.get("/api/products/{product}/reviews")
def product_reviews(product: str, authorization: str | None = Header(default=None)):
    product = product.strip()[:24]
    user = _maybe_user(authorization)
    out = {
        "items": prev_ops.list_public(product),
        **prev_ops.summary(product),
        "canWrite": False,
        "mine": None,
    }
    if user:
        out["canWrite"] = _can_review(user["email"], product)
        out["mine"] = prev_ops.mine(product, user["email"])
    return out


@app.post("/api/products/{product}/reviews")
def product_review_write(
    product: str, body: ReviewBody, authorization: str | None = Header(default=None)
):
    product = product.strip()[:24]
    user = _token_user(authorization)
    if not _can_review(user["email"], product):
        raise HTTPException(403, "이 사주를 먼저 열어 보셔야 후기를 남길 수 있습니다.")
    try:
        prev_ops.upsert(product, user["email"], user.get("name") or "", body.rating, body.text,
                        stem=(body.stem or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "ok": True,
        "items": prev_ops.list_public(product),
        **prev_ops.summary(product),
        "canWrite": True,
        "mine": prev_ops.mine(product, user["email"]),
    }


@app.delete("/api/products/{product}/reviews")
def product_review_delete(product: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    prev_ops.remove(product.strip()[:24], user["email"])
    return {"ok": True}


# ── 내 기록 ──────────────────────────────────────────────
# 생년월일·이름은 여기 오지 않는다. 고른 항목, 한 줄 메모, 본 사주 이름뿐이다.
class RecordBody(BaseModel):
    choice: str = ""
    memo: str = ""
    product: str = ""


class FollowUpBody(BaseModel):
    followup: str = ""


class RecordMergeBody(BaseModel):
    items: list[dict] = []


@app.get("/api/records")
def records_list(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return rec_ops.listing(user["email"])


@app.post("/api/records")
def records_add(body: RecordBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        item = rec_ops.add(user["email"], body.choice, body.memo, body.product)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "item": item, **rec_ops.listing(user["email"])}


@app.post("/api/records/{rid}/followup")
def records_followup(
    rid: str, body: FollowUpBody, authorization: str | None = Header(default=None)
):
    user = _token_user(authorization)
    try:
        rec_ops.follow_up(user["email"], rid, body.followup)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, **rec_ops.listing(user["email"])}


@app.delete("/api/records/{rid}")
def records_delete(rid: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    rec_ops.remove(user["email"], rid)
    return {"ok": True, **rec_ops.listing(user["email"])}


@app.post("/api/records/merge")
def records_merge(body: RecordMergeBody, authorization: str | None = Header(default=None)):
    """브라우저에만 있던 옛 기록을 계정으로 옮긴다. 로그인 직후 한 번."""
    user = _token_user(authorization)
    moved = rec_ops.merge_in(user["email"], body.items)
    return {"ok": True, "moved": moved, **rec_ops.listing(user["email"])}


@app.post("/api/ask")
def ask_open(body: AskBody, authorization: str | None = Header(default=None)):
    """무냥이에게 한 번 더 묻기. 등불을 쓴다."""
    user = _token_user(authorization)
    if _is_free(user):
        return {"ok": True, "spent": 0, "balance": 999999, "reopened": False, "unlimited": True}
    try:
        return lamps_ops.ask(user["email"], body.qid.strip(), body.pair.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))


class GwanAskBody(BaseModel):
    question: str
    shot: str = ""
    product: str = ""
    name: str = ""
    # 사주 쪽과 같다 (2026-09-11 4단계). 카드를 붙일 차례일 때만 주제를 고른다
    asked: list[str] = []
    wantReco: bool = False


@app.post("/api/gwan/ask")
def gwan_ask(body: GwanAskBody, authorization: str | None = Header(default=None)):
    """관멍이에게 더 묻는다. 🛑 **써 둔 결과지**를 재료로 쓴다 — 사진은 안 남긴다.

    등불 규칙은 사주 쪽과 같다 (한 번에 ASK_LAMPS).
    """
    user = _token_user(authorization)
    q = (body.question or "").strip()
    shot = (body.shot or "").strip()
    if not q:
        raise HTTPException(400, "무엇이 궁금한지 적어 주세요.")
    if len(q) > 300:
        raise HTTPException(400, "질문이 너무 길어요. 300자 안으로 적어 주세요.")
    if not shot:
        raise HTTPException(400, "먼저 관상을 봐 주세요.")
    if not saju_writer.ready():
        raise HTTPException(503, "지금은 답을 못 드려요. 잠시 뒤에 다시 여쭤 주세요.")

    # 🛑 그 사진으로 써 둔 글을 꺼낸다. 없으면 답할 재료가 없다
    try:
        data = saju_writer.load((body.product or "").strip(), shot) or {}
    except ValueError:
        data = {}
    seen = str(data.get("text") or "").strip()
    if not seen:
        raise HTTPException(400, "그 관상 결과를 찾지 못했어요. 다시 봐 주세요.")

    free = _is_free(user)
    # 🛑 사주 쪽과 **같은 규칙**이다 (2026-09-11 3단계). 인사에는 등불을 안 받는다 —
    #    한쪽만 공짜로 두면 손님이 어느 쪽에서 값이 나가는지 못 외운다.
    if intent_ops.kind(q) == intent_ops.TALK:
        _small_quota(user["email"], free)
        try:
            res = intent_ops.small_talk("관멍이", body.name or "", q)
        except (RuntimeError, ValueError) as e:
            raise HTTPException(503, "답을 쓰다가 막혔어요. 다시 여쭤 주세요.") from e
        return {"ok": True, "text": res.get("text", ""), "spent": 0, "kind": "talk",
                "balance": 999999 if free else lamps_ops.balance(user["email"])}

    if not free and lamps_ops.balance(user["email"]) < lamps_ops.ASK_LAMPS:
        raise HTTPException(402, "등불이 모자라요.")

    from modules import gwansang as gwan_ops
    try:
        res = gwan_ops.answer(body.name or "", seen, q)
    except (RuntimeError, ValueError):
        raise HTTPException(503, "답을 쓰다가 막혔어요. 다시 여쭤 주세요.")

    spent, balance = 0, 999999
    if not free:
        qid = "gwan-" + hashlib.sha1(q.encode("utf-8")).hexdigest()[:20]
        try:
            r = lamps_ops.ask(user["email"], qid, shot)
            spent = r.get("spent", 0)
            balance = r.get("balance", 0)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"ok": True, "text": res.get("text", ""), "spent": spent, "balance": balance,
            "kind": "read", "topic": _topic_if_wanted(body.wantReco, body.asked, q)}


class AskFreeBody(BaseModel):
    question: str
    pair: str
    saju: dict = {}
    name: str = ""
    # 🛑 여태 물어본 것들 (2026-09-11 4단계). **무슨 고민인지 고르는 데만** 쓴다 —
    #    답을 쓸 때는 안 넘긴다. 넘기면 물음마다 입력 토큰이 계속 불어난다.
    asked: list[str] = []
    # 이번 답 아래에 상품 카드를 붙일 차례인가. 몇 번째인지는 화면이 센다
    wantReco: bool = False


@app.post("/api/ask/free")
def ask_free(body: AskFreeBody, authorization: str | None = Header(default=None)):
    """무냥이에게 **아무거나** 묻는다. 정해진 질문이 아니라 손님이 쓴 문장에 답한다.

    왜: 「더 물어보기」가 열 개 중 고르는 방식이라 진짜 묻고 싶은 것을 못 물었다
    (2026-09-09 온해님 지시). 폭스바니처럼 1:1 대화로 바꾼다.

    🛑 **차감을 뒤에 한다.** 글을 못 받았는데 등불만 빠지면 손님이 손해다.
       대신 부르기 전에 잔액을 먼저 보고, 모자라면 아예 부르지 않는다.
    """
    user = _token_user(authorization)
    q = (body.question or "").strip()
    pair = (body.pair or "").strip()
    if not q:
        raise HTTPException(400, "무엇이 궁금한지 적어 주세요.")
    if len(q) > 300:
        raise HTTPException(400, "질문이 너무 길어요. 300자 안으로 적어 주세요.")
    if not pair:
        raise HTTPException(400, "사주 값이 필요합니다.")
    if not saju_writer.ready():
        raise HTTPException(503, "지금은 답을 못 드려요. 잠시 뒤에 다시 여쭤 주세요.")

    free = _is_free(user)
    # 🛑 **인사에는 등불을 안 받는다** (2026-09-11 온해님 3단계). 「안녕하세요」에
    #    30개를 받으면 손님은 두 번째 말을 안 건다 — 대화가 아니라 자판기가 된다.
    #    가르는 일은 **서버가 한다.** 화면에서 정하면 개발자 도구로 우회된다.
    if intent_ops.kind(q) == intent_ops.TALK:
        _small_quota(user["email"], free)
        try:
            res = intent_ops.small_talk("무냥이", body.name or "", q)
        except (RuntimeError, ValueError) as e:
            raise HTTPException(503, "답을 쓰다가 막혔어요. 다시 여쭤 주세요.") from e
        return {"ok": True, "text": res.get("text", ""), "spent": 0, "kind": "talk",
                "balance": 999999 if free else lamps_ops.balance(user["email"])}

    # 같은 질문을 다시 열면 등불을 안 쓴다 — 기존 ask 와 같은 규칙이라 키만 맞춘다
    qid = "free-" + hashlib.sha1(q.encode("utf-8")).hexdigest()[:20]
    if not free:
        if lamps_ops.balance(user["email"]) < lamps_ops.ASK_LAMPS:
            raise HTTPException(402, "등불이 모자라요.")

    try:
        res = saju_writer.answer(body.name or "", body.saju or {}, q)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(503, "답을 쓰다가 막혔어요. 다시 여쭤 주세요.") from e

    spent = 0
    balance = 999999
    if not free:
        try:
            r = lamps_ops.ask(user["email"], qid, pair)
            spent = r.get("spent", 0)
            balance = r.get("balance", 0)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"ok": True, "text": res.get("text", ""), "spent": spent, "balance": balance,
            "kind": "read", "topic": _topic_if_wanted(body.wantReco, body.asked, q)}


@app.post("/api/premium/buy")
def premium_buy(body: PremiumBody, authorization: str | None = Header(default=None)):
    """프리미엄 한 건 결제. 등불을 거치지 않고 그 자리에서 사서 연다."""
    if not PAY_OPEN:
        # 🛑 앞단만 막으면 우회된다. 서버가 마지막으로 거절한다.
        raise HTTPException(503, "결제를 준비하고 있어요. 열리면 알려 드릴게요.")
    # 🛑 글이 안 써지는 동안은 받지 않는다. 받아 두고 못 써 드리면 환불 사태가 된다
    if saju_writer.down():
        raise HTTPException(503, "지금은 주문이 몰려서 잠시 닫았어요. 곧 다시 열려요.")
    user = _token_user(authorization)
    paid = _verify_payment(body.paymentId.strip())
    amount = int((paid.get("amount") or {}).get("total") or 0)
    try:
        return lamps_ops.buy_premium(
            user["email"], body.product.strip(), body.pair.strip(),
            payment_id=body.paymentId.strip(), paid=amount,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── 관상 ────────────────────────────────────────────────
# 🛑 **사진을 저장하지 않는다.** 받은 그대로 Gemini 로 넘기고 그 자리에서 버린다.
#    파일을 만들지 않으므로 디스크에 남을 일이 없다.
# 🛑 아직 **만드는 중**이라 주인만 부를 수 있다. 상품이 열리면 결제를 붙인다.
GWAN_MAX_SHOTS = 2


# 🛑 **글의 얼개가 바뀌면 저장해 둔 것을 버린다** (2026-09-09 실측).
#    항목을 나눠 길게 쓰게 고쳤는데, 같은 사진으로 다시 열면 **예전 짧은 글**이 그대로 나왔다.
#    「배포했는데 그대로인데?」의 진짜 이유가 이것이었다.
#    얼개를 고치면 이 숫자를 올린다.
GWAN_VER = 2

GWAN_TRIES = 3          # 🛑 한 번 결제로 **서로 다른 사진 셋**까지. 사진을 잘못 올릴 수 있어서다
                        #    (2026-09-09 온해님). 같은 사진을 다시 보는 건 안 깎는다.


def _gwan_seen(email: str, ticket: str) -> list[str]:
    """이 구매 표로 이미 읽은 사진 해시들."""
    from pathlib import Path as _P
    import json as _j
    f = _P(DATA_DIR) / "gwansang_tries.json"
    try:
        data = _j.loads(f.read_text(encoding="utf-8"))
    except Exception:                                 # noqa: BLE001
        data = {}
    return list(data.get("%s|%s" % (email, ticket)) or [])


def _gwan_use(email: str, ticket: str, shot: str) -> None:
    """이 사진을 이 표에 적어 둔다. 같은 사진이면 두 번 안 적는다."""
    from pathlib import Path as _P
    import json as _j
    f = _P(DATA_DIR) / "gwansang_tries.json"
    try:
        data = _j.loads(f.read_text(encoding="utf-8"))
    except Exception:                                 # noqa: BLE001
        data = {}
    k = "%s|%s" % (email, ticket)
    got = list(data.get(k) or [])
    if shot not in got:
        got.append(shot)
    data[k] = got[-GWAN_TRIES:]
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_j.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:                                 # noqa: BLE001
        pass


def _gwan_veil(text: str, paid: bool) -> str:
    """복채를 안 내셨으면 **앞 문단 하나만** 준다.

    🛑 **서버에서 자른다.** 화면에서만 흐리면 개발자 도구로 다 보인다 —
       사주 미리보기의 한계를 여기서는 되풀이하지 않는다 (2026-09-09).
    """
    if paid:
        return text
    paras = [p for p in str(text or "").split("\n\n") if p.strip()]
    return paras[0] if paras else ""


class GwanCheckBody(BaseModel):
    """사진 점검 — 해석 전에 **무엇이 안 보이는지**만 본다."""
    shots: list[str] = []


@app.post("/api/gwansang/check")
def gwansang_check(body: GwanCheckBody, authorization: str | None = Header(default=None)):
    """사진이 관상을 보기에 괜찮은지 훑는다.

    🛑 **여기서 해석하지 않는다.** 가려진 데를 말해 주고, 손님이 그걸 알고도
       계속 볼지 정하게 한다. 그래야 「돈 냈는데 엉뚱한 소리」가 안 나온다.
    🛑 로그인만 하면 쓸 수 있다. 출력이 짧아 한 번에 1원 안팎이다.
    """
    _token_user(authorization)
    shots = body.shots or []
    if not shots or len(shots) > GWAN_MAX_SHOTS:
        raise HTTPException(400, "사진을 %d장까지 보낼 수 있어요." % GWAN_MAX_SHOTS)
    try:
        clean = [gwansang_ops.check_jpeg(x) for x in shots]
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        out = gwansang_ops.look_shot(clean)
    except Exception as e:                            # noqa: BLE001
        print("[gwansang/check] 실패:", repr(e)[:300])
        # 🛑 점검을 못 했다고 막지 않는다. 그냥 통과시킨다 — 손님이 기다리는 자리다
        return {"ok": True, "good": True, "miss": [], "say": ""}
    return {"ok": True, **out}


@app.post("/api/gwansang")
def gwansang_read(body: GwansangBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    product = (body.product or "").strip()
    pair = (body.pair or "").strip()
    if not product or not pair:
        raise HTTPException(400, "상품과 사진 값이 필요합니다.")
    # 🛑 **복채를 낸 분만.** 한 건에 7원이 나가므로 열어 두면 잔액이 그대로 샌다
    #    (잔액이 0 이 되면 사주 글·더 물어보기까지 같이 죽는다).
    # `pair` 는 **구매 표**다. `shot` 은 사진 해시다 — 표 하나로 사진 셋까지 본다.
    shot = (body.shot or "").strip() or pair
    free = _is_free(user)
    paid = free or lamps_ops.owns(user["email"], product, pair)
    # 🛑 **복채 전에도 앞부분은 보여 준다** (2026-09-09 온해님 「미리보기 둔다」).
    #    다만 이건 돈이 나가는 자리라 사주와 **같은 하루 한도**를 쓴다 —
    #    따로 두면 관상으로 한도를 우회할 수 있다.
    if not paid:
        _preview_quota(user["email"])

    # 🛑 **한 번 읽은 사진은 다시 읽지 않는다.** 저장한 것을 그대로 준다 —
    #    안 그러면 새로고침할 때마다 새로 뽑혀 돈이 계속 나간다. 횟수도 안 깎는다.
    try:
        prev = saju_writer.load(product, shot)
    except ValueError:
        prev = None
    if prev and prev.get("text") and prev.get("ver") == GWAN_VER:
        return {"ok": True, "text": _gwan_veil(prev["text"], paid), "paid": paid,
                "tokens": None, "card": (prev.get("card") or {}) if paid else {},
                "again": True,
                "left": max(0, GWAN_TRIES - len(_gwan_seen(user["email"], pair)))}

    # 🛑 **기회는 셋.** 사진을 잘못 올렸을 때를 위한 것이지 무제한이 아니다
    if paid and not free:
        used = _gwan_seen(user["email"], pair)
        if shot not in used and len(used) >= GWAN_TRIES:
            raise HTTPException(409,
                "이 복채로는 사진 %d장까지 봐 드렸어요. 새로 보시려면 한 번 더 내셔야 해요."
                % GWAN_TRIES)

    shots = body.shots or []
    if not shots or len(shots) > GWAN_MAX_SHOTS:
        raise HTTPException(400, "사진을 %d장까지 보낼 수 있어요." % GWAN_MAX_SHOTS)
    try:
        clean = [gwansang_ops.check_jpeg(x) for x in shots]
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        out = gwansang_ops.read_face(product, clean, name=(body.name or "").strip(),
                                     sections=body.sections or [])
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:                            # noqa: BLE001
        # 🛑 **이유를 삼키지 않는다** (2026-09-09). 그전에는 「잠시 뒤 다시 해 주세요」만
        #    돌려주고 진짜 이유를 어디에도 안 남겨서, 실패했을 때 무엇을 고쳐야 할지
        #    알 길이 없었다. 서버 로그에 남기고, **아직 주인만 쓰는 기능이라** 화면에도 적는다.
        # 🛑 이유는 **서버 로그에만** 남긴다. 손님 화면에 내부 사정을 적지 않는다
        #    (2026-09-09 손님에게 열면서 되돌렸다).
        print("[gwansang] 실패:", repr(e)[:400])
        raise HTTPException(502, "관상을 읽지 못했어요. 잠시 뒤 다시 해 주세요.")
    # 🛑 **공유 카드 문구는 따로 쓴다** (2026-09-09 온해님 「모든 공유카드는 LLM으로」).
    #    전에는 관상 글의 앞 두 문장을 **잘라서** 카드에 박았다. 자른 문장은 문맥이
    #    끊겨서 카드에서만 읽으면 무슨 말인지 모른다.
    #    🛑 못 쓰면 빈 값을 준다 — 그때 화면은 지금처럼 잘라 쓴다.
    card = {}
    try:
        # 🛑 **앞 600자만 주면 안 된다** (2026-09-10). 그건 첫 자리(첫인상)라
        #    연애·재물 같은 상품의 답이 아직 안 나온다. 자리마다 앞을 조금씩
        #    걷어서 글 전체를 훑게 한다.
        parts = [x.strip() for x in str(out["text"]).split("##") if x.strip()]
        head = " ".join(" ".join(x.split())[:180] for x in parts)[:1800]
        if not head:
            head = " ".join(str(out["text"]).split())[:900]
        card = saju_writer.write_card("관상", {
            "손님이 물은 것": (body.q or "").strip(),
            "무엇을 본 것인가": product,
            "관멍이가 쓴 글": head,
        })
    except Exception:                                 # noqa: BLE001
        card = {}
    # 🛑 **글은 남기고 사진은 안 남긴다.** 다시 볼 때 돈이 또 나가지 않게 글만 저장한다.
    try:
        saju_writer.save(product, shot, {"text": out["text"], "card": card,
                                         "kind": "gwansang", "ver": GWAN_VER})
    except Exception:                                 # noqa: BLE001
        pass                                          # 저장을 못 해도 글은 나가야 한다
    if paid and not free:
        _gwan_use(user["email"], pair, shot)
    # 🛑 사진은 여기서 끝이다. `clean` 은 응답에 담지 않는다
    return {"ok": True, "text": _gwan_veil(out["text"], paid), "paid": paid,
            "tokens": out.get("tokens"), "card": card if paid else {},
            "left": max(0, GWAN_TRIES - len(_gwan_seen(user["email"], pair)))}


class ReferBody(BaseModel):
    code: str


@app.get("/api/refer")
def refer_mine(authorization: str | None = Header(default=None)):
    """내 추천 코드와 지금까지 데려온 사람 수."""
    user = _token_user(authorization)
    return lamps_ops.refer_stats(user["email"])


@app.post("/api/refer/claim")
def refer_claim(body: ReferBody, authorization: str | None = Header(default=None)):
    """추천 코드를 넣는다. 한 계정에 한 번만 받는다."""
    user = _token_user(authorization)
    return lamps_ops.claim_refer(user["email"], (body.code or "").strip())


@app.get("/api/premium/price")
def premium_price():
    """프리미엄 값표. 프론트가 결제창에 넣을 금액을 서버에서 받아 간다."""
    prices = dict(lamps_ops.PREMIUM_WON)
    if lamps_ops.PAY_PER_REPORT:
        prices.update({k: v * lamps_ops.LAMP_WON for k, v in lamps_ops.PRICES.items()})
    return {"prices": prices, "payPerReport": lamps_ops.PAY_PER_REPORT}


@app.post("/api/reports/open")
def report_open(body: OpenBody, authorization: str | None = Header(default=None)):
    """리포트 열기. 이미 산 것이면 등불을 쓰지 않고 다시 열어 준다."""
    user = _token_user(authorization)
    if _is_free(user):
        # 주인은 등불을 깎지 않고 바로 연다. 사서 여는 손님과 같은 화면을 보기 위해서다.
        return {"ok": True, "spent": 0, "balance": 999999, "reopened": False, "unlimited": True}
    # 단건 결제 상품은 등불로 사는 물건이 아니다. 결제로 이미 샀는지만 본다.
    if lamps_ops.won_of(body.product.strip()):
        if lamps_ops.owns(user["email"], body.product.strip(), body.pair.strip()):
            return {"ok": True, "spent": 0, "balance": lamps_ops.balance(user["email"]), "reopened": True}
        raise HTTPException(402, "이 상품은 등불이 아니라 결제로 열어요.")
    try:
        return lamps_ops.spend(user["email"], body.product.strip(), body.pair.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── 결과지 문장 — 모델이 매번 새로 쓴다 ──────────────────────
# 왜: 코드에 박아 둔 문장은 같은 십성인 사람에게 늘 같은 글을 준다.
# 계산은 프론트가 끝내서 보내고, 여기서는 그 값을 글로 옮기기만 시킨다.

PREVIEW_SECTIONS = 1        # 복채를 내기 전에 무냥이 글로 보여 주는 항목 수
#   🛑 첫 자리 하나만이다 (2026-09-07 지시). 셋이면 상품에 따라 2장까지 열려 버렸다.
#   🛑 main.js:PREVIEW_ITEMS 와 같아야 한다 — 화면이 그 수만큼 자리를 잡아 둔다.
PREVIEW_DAILY_CAP = 3       # 한 계정이 하루에 뽑을 수 있는 미리보기
                            # 🛑 폭스바니는 2회다. 헐렁하게 두면 원가만 나가고
                            #    「몇 번 안 남았다」는 압박도 사라진다
SMALL_DAILY_CAP = 20        # 등불을 안 받는 가벼운 말에 답하는 하루 횟수
                            # 🛑 공짜라고 열어 두면 로그인만 해서 계속 말을 걸 수 있다.
                            #    한 번에 0.2원이라 스무 번이면 4원 — 그쯤에서 끊는다.
                            #    🛑 여기 걸려도 **봐 달라는 물음은 그대로 열려 있다.**
                            #       등불을 내는 손님을 막으면 안 된다
FREE_DAILY_CAP = 3          # 무료 상품(오늘의 운세)을 하루에 새로 뽑는 횟수
                            # 🛑 미리보기 한도와 **따로 센다.** 같이 세면 오늘 운세를
                            #    한 번 본 것만으로 값 있는 상품 맛보기가 한 번 준다 —
                            #    미끼가 미끼를 잡아먹는다.
                            # 🛑 같은 사주·같은 날은 저장분을 그대로 쓰므로 여기 안 센다.
                            #    이 한도는 **사주를 바꿔 가며 뽑는 것**만 막는다


class WriteBody(BaseModel):
    product: str
    pair: str
    sections: list[str] = []
    saju: dict = {}
    name: str = ""
    preview: bool = False
    chars: int = 0          # 항목 하나를 몇 자로 쓸지. 프론트가 상품마다 정해서 보낸다
    force: bool = False     # 주인이 일부러 새로 뽑을 때만 참


def _quota_key(email: str, kind: str) -> str:
    """세는 칸 이름. 🛑 미리보기는 **옛 이름 그대로** 둔다 — 오늘 센 것이 날아간다."""
    return email if kind == "preview" else "%s:%s" % (kind, email)


def _preview_used(email: str, kind: str = "preview") -> int:
    """오늘 이 계정이 몇 번 뽑았나."""
    from pathlib import Path as _P
    import json as _j
    import datetime as _dt
    f = _P(DATA_DIR) / "saju_preview_count.json"
    today = _dt.date.today().isoformat()
    try:
        data = _j.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    if data.get("day") != today:
        return 0
    return int(data.get("by", {}).get(_quota_key(email, kind), 0))


def _preview_quota(email: str, kind: str = "preview", cap: int = 0,
                   msg: str = "") -> None:
    """복채를 내기 전에 나가는 원가에 하루 한도를 둔다."""
    from pathlib import Path as _P
    import json as _j
    import datetime as _dt
    f = _P(DATA_DIR) / "saju_preview_count.json"
    today = _dt.date.today().isoformat()
    key = _quota_key(email, kind)
    try:
        data = _j.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("day") != today:
        data = {"day": today, "by": {}}
    n = int(data["by"].get(key, 0))
    if n >= (cap or PREVIEW_DAILY_CAP):
        raise HTTPException(429, msg or "오늘 무료로 볼 수 있는 사주를 다 보셨어요. 내일 0시부터 다시 열려요.")
    data["by"][key] = n + 1
    try:
        f.write_text(_j.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _topic_if_wanted(want: bool, asked: list[str] | None, now_q: str) -> list[str]:
    """카드를 붙일 차례일 때만 무슨 고민인지 고른다 (2026-09-11 온해님 4단계).

    🛑 **매번 고르지 않는다.** 한 번에 0.1원이고, 무엇보다 답마다 상품이 붙으면
       대화가 아니라 광고가 된다. 화면이 세 번에 한 번만 청한다.
    🛑 **여기서 상품을 고르지 않는다.** 상품 정본은 앞단에 있다 — 주제만 준다.
    """
    if not want:
        return []
    qs = [x for x in (asked or []) if isinstance(x, str)][-5:]
    if now_q:
        qs.append(now_q)
    try:
        return intent_ops.topic(qs)
    except Exception:                                   # noqa: BLE001
        return []                                       # 못 골라도 답은 나가야 한다


def _small_quota(email: str, free: bool) -> None:
    """가벼운 말은 등불을 안 받는다. 그래서 하루 횟수로만 막는다 (2026-09-11)."""
    if free:
        return
    _preview_quota(email, kind="small", cap=SMALL_DAILY_CAP,
                   msg="가벼운 얘기는 오늘 여기까지만 받을게요. 사주로 물으시면 바로 답해 드려요.")


@app.get("/api/saju/quota")
def saju_quota(authorization: str | None = Header(default=None)):
    """오늘 무료로 몇 번 더 볼 수 있나. 「몇 번 안 남았다」가 보여야 압박이 된다."""
    user = _token_user(authorization)
    if _is_free(user):
        return {"cap": PREVIEW_DAILY_CAP, "left": PREVIEW_DAILY_CAP, "unlimited": True}
    used = _preview_used(user["email"])
    return {"cap": PREVIEW_DAILY_CAP, "left": max(0, PREVIEW_DAILY_CAP - used), "unlimited": False}


# ── 알림함 ────────────────────────────────────────────────
# 🛑 받은 줄 모르면 준 게 아니다. 가입 선물·1회권·공지를 여기로 알린다.

@app.get("/api/inbox")
def inbox_list(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return inbox.listing(user["email"])


class InboxReadBody(BaseModel):
    ids: list[str] | None = None


@app.post("/api/inbox/read")
def inbox_read(body: InboxReadBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    n = inbox.mark_read(user["email"], body.ids)
    return {"ok": True, "read": n}


class InboxNoticeBody(BaseModel):
    title: str
    body: str = ""
    key: str = ""
    link: str = ""


@app.post("/api/admin/inbox/notice")
def inbox_notice(body: InboxNoticeBody, authorization: str | None = Header(default=None)):
    """전체 공지. 결제가 열렸을 때 같은 소식을 한 번에 보낸다. 주인만."""
    user = _token_user(authorization)
    if not _is_owner(user):
        raise HTTPException(403, "권한이 없습니다.")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "제목이 필요합니다.")
    emails = [(u.get("email") or "").strip().lower() for u in db.list_users()]
    n = inbox.push_all([e for e in emails if e and "@" in e],
                       title, (body.body or "").strip(),
                       key=(body.key or "").strip(), link=(body.link or "").strip(),
                       icon="notice")
    return {"ok": True, "sent": n}


@app.get("/api/saju/ready")
def saju_ready():
    """모델 키가 서버에 들어와 있는지만 알려 준다. 값은 내보내지 않는다."""
    return {"ready": saju_writer.ready(), "model": saju_writer.MODEL,
            "preview": PREVIEW_SECTIONS}


@app.post("/api/saju/write")
def saju_write(body: WriteBody, authorization: str | None = Header(default=None)):
    """항목별 문장을 받아 온다. 한 번 쓴 항목은 남겨 두고 다시 쓰지 않는다."""
    user = _token_user(authorization)
    product = (body.product or "").strip()
    pair = (body.pair or "").strip()
    if not product or not pair:
        raise HTTPException(400, "상품과 사주 값이 필요합니다.")
    if not saju_writer.ready():
        raise HTTPException(503, "글쓰기 준비가 아직 안 됐어요.")

    want = [s for s in (body.sections or []) if isinstance(s, str) and s.strip()][:20]
    if not want:
        raise HTTPException(400, "쓸 항목이 없습니다.")

    # 복채를 낸 사람인가. 아니면 앞 몇 항목만 준다.
    # 🛑 **무료 상품은 산 사람이 없다** (2026-09-11 온해님이 잡으심). 결제를 안 거치니
    #    `owned` 에 아무것도 안 담기고, 그래서 `owns()` 가 영원히 거짓이었다. 앞단은
    #    글을 정상적으로 청했는데 여기서 402 로 튕겨 냈고, 화면은 조용히 「쓰는 중」만
    #    지웠다 — 오늘의 운세가 **계산 문장만으로** 나가고 있었다. 미끼 상품인데.
    free_product = product in lamps_ops.FREE_PRODUCTS
    paid = free_product or _is_free(user) or lamps_ops.owns(user["email"], product, pair)
    if not body.preview and not paid:
        raise HTTPException(402, "이 리포트는 아직 열려 있지 않아요.")
    if not paid:
        want = want[:PREVIEW_SECTIONS]

    try:
        have = saju_writer.load(product, pair) or {"blocks": []}
    except ValueError:
        raise HTTPException(400, "사주 값이 올바르지 않습니다.")
    # 🛑 **글의 결이 바뀌었으면 저장해 둔 것을 버린다** (saju_writer.WRITE_VER 참고).
    #    관상은 GWAN_VER 로 이미 하고 있었는데 사주 본문에만 없어서, 말투를 갈아도
    #    이미 열어 본 리포트는 옛 글이 그대로 나왔다 (2026-09-10 온해님이 잡으심).
    stale = int(have.get("ver") or 0) < saju_writer.WRITE_VER
    if stale:
        have = {"blocks": []}
    done = {b["title"]: b for b in have.get("blocks", []) if b.get("text")}
    todo = [s for s in want if s not in done]

    # 🛑 주인(관리자)은 화면을 보려고 수없이 열어 본다. 그때마다 새로 뽑으면
    #    파는 것도 없이 돈만 나간다. 이미 써 둔 것만 보여 주고, 새로 뽑지 않는다.
    #    정말 새로 뽑아야 할 때만 주소에 ?write=1 을 붙인다.
    #    🛑 다만 **글의 결이 바뀐 경우(stale)에는 주인에게도 새로 쓴다.** 안 그러면
    #       말투를 갈아 놓고 정작 확인하는 사람만 옛 글을 본다.
    owner_skip = False
    if todo and _is_owner(user) and not body.force and not stale:
        todo = []
        owner_skip = True

    if todo:
        if not paid:
            _preview_quota(user["email"])
        elif free_product and not _is_free(user):
            # 🛑 무료 상품도 뽑을 때마다 원가가 나간다. 사주를 바꿔 가며 긁는 것만 막는다
            _preview_quota(user["email"], kind="free", cap=FREE_DAILY_CAP,
                           msg="오늘 무료로 볼 수 있는 만큼 다 보셨어요. 내일 0시부터 다시 열려요.")
        try:
            chars = min(max(int(body.chars or 420), 300), 1600)   # 프론트 값을 그대로 믿지 않는다
            res = saju_writer.write_report(
                (body.name or "손님").strip()[:12], body.saju or {}, todo,
                product=product, chars=chars, pair=pair)
        except Exception as e:                      # noqa: BLE001
            raise HTTPException(502, "글을 받아 오지 못했어요: %s" % str(e)[:120])
        saju_writer.merge(product, pair, res["blocks"])
        for b in res["blocks"]:
            if b.get("text"):
                done[b["title"]] = b

    left = PREVIEW_DAILY_CAP if _is_free(user) else max(0, PREVIEW_DAILY_CAP - _preview_used(user["email"]))
    # 🛑🛑 **`hook` 과 `mutter` 를 같이 보낸다** (2026-09-11 온해님이 잡으심).
    #    여기서 `text` 만 담고 있었다. 그래서 LLM 이 쓴 **항목 제목과 혼잣말이
    #    전 상품에서 한 번도 화면에 안 나갔다** — 앞단은 `b.hook`·`b.mutter` 를
    #    받을 준비가 되어 있었는데 서버가 안 보냈다. 화면에는 표에서 고른 옛
    #    혼잣말과 본래 제목이 그대로 나왔고, 오류가 아니라서 아무도 못 봤다.
    #    저장은 처음부터 되고 있었으므로 **이미 써 둔 글도 이 줄 하나로 살아난다.**
    return {"ok": True, "paid": paid, "ownerSkip": owner_skip, "left": left,
            "blocks": [{"title": s,
                        "text": done.get(s, {}).get("text", ""),
                        "hook": done.get(s, {}).get("hook", ""),
                        "mutter": done.get(s, {}).get("mutter", "")} for s in want],
            "more": (not paid) and len(body.sections or []) > PREVIEW_SECTIONS}


class SummaryBody(BaseModel):
    product: str
    pair: str
    # 🛑 공유 카드 문구용 **재료**. 계산은 앞단이 하고 서버는 말만 다듬는다 (2026-09-09).
    #    없으면 카드 문구를 만들지 않는다 — 그때 화면은 표로 떨어진다.
    kind: str | None = None
    facts: dict[str, str] | None = None
    # 🛑 상품의 질문. 카드 제목이 이것이라 **문구도 이 물음에 답해야** 한다 (2026-09-10)
    q: str = ""


@app.post("/api/saju/summary")
def saju_summary(body: SummaryBody, authorization: str | None = Header(default=None)):
    """공유 카드에 넣을 두 줄. 이미 써 둔 결과지에서 뽑는다.

    새로 글을 쓰지 않으므로 결과지가 없으면 빈 값을 준다.
    한 번 뽑은 요약은 결과지 옆에 남겨 두고 다시 뽑지 않는다."""
    user = _token_user(authorization)
    product = (body.product or "").strip()
    pair = (body.pair or "").strip()
    if not product or not pair:
        raise HTTPException(400, "상품과 사주 값이 필요합니다.")
    # 🛑 복채를 낸 사람만 본다. 미리보기 3항목만 있는 사람에게는 주지 않는다.
    # 🛑 **무료 상품은 예외다** (2026-09-11). 여기도 `owns()` 로만 봐서 오늘의 운세는
    #    공유 카드 두 줄이 늘 비어 있었다. 퍼뜨리라고 만든 카드인데 알맹이가 없었다.
    if not (product in lamps_ops.FREE_PRODUCTS
            or _is_free(user) or lamps_ops.owns(user["email"], product, pair)):
        return {"ok": True, "summary": "", "paid": False}
    try:
        data = saju_writer.load(product, pair)
    except ValueError:
        raise HTTPException(400, "사주 값이 올바르지 않습니다.")
    if not data or not data.get("blocks"):
        return {"ok": True, "summary": ""}
    # 🛑 카드 문구는 **한 번만** 만들고 저장한다. 다시 열 때 이름이 바뀌면
    #    「내 전생은 ○○이었다」가 흔들려서 손님이 이상하게 본다.
    def _card() -> dict:
        if not body.facts:
            return {}
        # 🛑 **규격 판이 낮으면 다시 만든다** (2026-09-10). 그러지 않으면 카드
        #    규격을 갈아도 이미 열어 본 사주는 영원히 옛 문구가 나온다.
        saved = data.get("card")
        if (isinstance(saved, dict) and saved.get("name")
                and int(saved.get("ver") or 0) >= saju_writer.CARD_VER):
            return saved
        if not saju_writer.ready():
            return {}
        try:
            made = saju_writer.write_card(body.kind or product, body.facts)
        except Exception:                   # noqa: BLE001
            return {}
        if made:
            data["card"] = made
            saju_writer.save(product, pair, data)
        return made

    if data.get("summary"):
        # 🛑 **이미 저장된 요약도 다듬어 내보낸다** (2026-09-10). 예전에 90자로
        #    무조건 잘라 저장한 것들이 있어서, 그대로 주면 카드에 「…했어요. 나라」
        #    같은 조각이 계속 나간다. 다시 만드는 게 아니라 끝만 자르는 것이라 값이 안 든다.
        return {"ok": True,
                "summary": saju_writer._cut_sentence(data["summary"], 90),
                "card": _card()}
    if not saju_writer.ready():
        return {"ok": True, "summary": ""}
    # 🛑 **두 줄 요약이 실패해도 카드 문구는 준다** (2026-09-10).
    #    전에는 여기서 그냥 돌아가 버려서 `card` 가 통째로 빠졌고, 그러면 카드가
    #    이름·한 줄·이야기를 전부 **계산값**으로 그린다 — 무냥이가 쓴 글이 하나도
    #    안 들어간 카드가 나온다. 온해님이 「똑같이 나오는데?」로 잡으신 화면이 이것이다.
    try:
        line = saju_writer.summarize(data["blocks"], question=(body.q or "").strip())
    except Exception:                       # noqa: BLE001
        line = ""
    if line:
        data["summary"] = line
        saju_writer.save(product, pair, data)
    return {"ok": True, "summary": line, "card": _card()}


@app.post("/api/admin/lamps/backfill")
def admin_lamps_backfill(authorization: str | None = Header(default=None)):
    """가입 선물을 못 받은 분들께 소급해서 드린다. 주인만 부를 수 있다.

    「가입하면 등불 300개」라고 적어 두고 못 준 사람이 있었다 (2026-09-07).
    welcome() 이 원장을 보고 이미 받은 분은 건너뛰므로 두 번 나가지 않는다.
    """
    user = _token_user(authorization)
    if not _is_owner(user):
        raise HTTPException(403, "권한이 없습니다.")
    given, skipped, failed = [], 0, []
    for u in db.list_users():
        email = (u or {}).get("email") or ""
        if "@" not in email:
            continue
        name, _, dom = email.partition("@")
        who = name[:2] + "***@" + dom
        try:
            r = lamps_ops.welcome(email, "", "소급 지급")
        except Exception as e:                  # noqa: BLE001
            log.error("소급 지급 실패 (%s): %s", email, e)
            failed.append(who)
            continue
        if r.get("given"):
            given.append(who)
        else:
            skipped += 1
    log.info("가입 선물 소급: 지급 %d · 이미받음 %d · 실패 %d", len(given), skipped, len(failed))
    return {"given": len(given), "skipped": skipped, "failed": failed, "who": given}


@app.get("/api/admin/lamps")
def admin_lamps(authorization: str | None = Header(default=None)):
    """계정마다 등불이 실제로 들어갔는지 본다. 주인만 볼 수 있다.

    「가입하면 등불 300개」라고 적어 놓고 안 나가면 표시와 사실이 어긋난다.
    이메일은 앞 두 글자만 남긴다 — 화면에 띄우거나 기록에 남길 것이라서."""
    user = _token_user(authorization)
    if not _is_owner(user):
        raise HTTPException(403, "권한이 없습니다.")
    try:
        data = lamps_ops._read()
    except Exception as e:                      # noqa: BLE001
        raise HTTPException(500, "등불 장부를 읽지 못했습니다: %s" % str(e)[:120])

    # 🛑 등불 장부만 보면 안 된다. 가입 선물이 실패하면 장부에 계정 자체가 안 생겨서,
    #    못 받은 사람만 골라 목록에서 빠진다 (2026-09-07 실제로 이렇게 놓쳤다).
    #    회원 명부를 기준으로 돌면서 장부를 대조한다.
    emails = []
    for u in db.list_users():
        em = ((u or {}).get("email") or "").strip().lower()
        if "@" in em:
            emails.append(em)
    for em in (data or {}):
        if "@" in str(em) and str(em) not in emails:
            emails.append(str(em))

    out = []
    for email in emails:
        acc = (data or {}).get(email) or {}
        led = acc.get("ledger", [])
        name, _, dom = str(email).partition("@")
        if not isinstance(acc, dict):
            acc, led = {}, []
        kinds = {}
        for e in led:
            k = str(e.get("type") or "?")
            kinds[k] = kinds.get(k, 0) + 1
        out.append({
            "who": (name[:2] + "***@" + dom),
            "balance": lamps_ops.balance(email),
            "welcomeGiven": any(e.get("type") == "welcome" for e in led),
            "entries": len(led),
            "kinds": kinds,
            # 무엇에 썼는지. 값·계정은 담지 않는다
            "recent": [{"type": e.get("type"), "product": e.get("product"),
                        "lamps": e.get("lamps"), "price": e.get("price"),
                        "pay": bool(e.get("payment_id")), "at": str(e.get("at"))[:16]}
                       for e in led[-12:]],
            "lots": [{"remain": l.get("remain"), "expires": str(l.get("expires"))[:10]}
                     for l in (acc.get("lots") or [])][-6:],
        })
    out.sort(key=lambda x: -x["balance"])
    return {"count": len(out),
            "noWelcome": [a["who"] for a in out if not a["welcomeGiven"]],
            "accounts": out[:50]}


class _HashedAssets(StaticFiles):
    """파일명에 내용 해시가 붙은 자산은 내용이 바뀌면 이름이 바뀐다.
    그래서 오래 캐시해도 안전하고, 매 방문 재검증 왕복을 없앨 수 있다."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        import re as _re
        if resp.status_code == 200 and _re.search(r"-[A-Za-z0-9_-]{8,}\.(js|css|png|jpg|webp|woff2?)$", path):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


if WEB.exists():
    app.mount("/assets", _HashedAssets(directory=WEB / "assets"), name="assets")


@app.get("/")
def index():
    return _file_response(WEB / "index.html")


def _safe_web_file(rel_path: str) -> Path | None:
    """
    web/ 하위 파일만 허용. .. 경로 탈출로 서버 소스·/etc 노출 방지.
    """
    if not rel_path or rel_path.startswith(("/", "\\")):
        return None
    # URL 디코딩 전·후 모두 차단
    if ".." in rel_path.replace("\\", "/").split("/"):
        return None
    if "\x00" in rel_path:
        return None
    try:
        root = WEB.resolve()
        candidate = (WEB / rel_path).resolve()
        # Python 3.9+: is_relative_to
        if hasattr(candidate, "is_relative_to"):
            if not candidate.is_relative_to(root):
                return None
        else:
            root_s = str(root)
            cand_s = str(candidate)
            if not (cand_s == root_s or cand_s.startswith(root_s + "/") or cand_s.startswith(root_s + "\\")):
                return None
        if candidate.is_file():
            return candidate
    except Exception:
        return None
    return None


# 운행일지 시절 URL 정리 (2026-09-04 사주 서비스로 교체).
# 색인돼 있던 옛 주소는 404 대신 홈으로 영구 이동시킨다.
_GONE_PREFIXES = ("blog", "resources", "app", "guide", "update.html", "legal/business.html")


# 카드 한 장을 보여 주는 쪽. 그림 하나와 「나도 보기」 한 줄이면 된다.
# 🛑 배경 사주 글자는 여기에도 깐다 (CLAUDE.md 규칙).
CARD_HTML = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>%(title)s · 로드로그</title>
<meta name="description" content="%(line)s" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="로드로그" />
<meta property="og:locale" content="ko_KR" />
<meta property="og:url" content="%(url)s" />
<meta property="og:title" content="%(title)s" />
<meta property="og:description" content="%(line)s" />
<meta property="og:image" content="%(img)s" />
<meta property="og:image:width" content="1080" />
<meta property="og:image:height" content="1350" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="%(title)s" />
<meta name="twitter:description" content="%(line)s" />
<meta name="twitter:image" content="%(img)s" />
<link rel="icon" href="/assets/character/face.png" />
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.min.css" />
<link href="https://fonts.googleapis.com/css2?family=Gugi&display=swap" rel="stylesheet" />
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{--bg:#100e15;--paper:#171523;--ink:#efeaf7;--muted:#a79fbb;--line:#2b2740;--go:#c8b6ff;
    --seal:url("data:image/svg+xml;utf8,%%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%%3E%%3Ctext x='20' y='60' font-size='46' fill='%%23ffffff' fill-opacity='0.048'%%3E甲%%3C/text%%3E%%3Ctext x='150' y='130' font-size='46' fill='%%23ffffff' fill-opacity='0.048'%%3E丙%%3C/text%%3E%%3Ctext x='60' y='210' font-size='46' fill='%%23ffffff' fill-opacity='0.048'%%3E壬%%3C/text%%3E%%3Ctext x='210' y='270' font-size='46' fill='%%23ffffff' fill-opacity='0.048'%%3E子%%3C/text%%3E%%3C/svg%%3E")}
  body{background:var(--bg);background-image:var(--seal);background-size:300px 300px;
    color:var(--ink);font-family:"Pretendard",-apple-system,system-ui,sans-serif;
    word-break:keep-all;min-height:100vh;display:flex;flex-direction:column;align-items:center;
    justify-content:center;padding:28px 18px;gap:20px}
  .top{font-family:"Gugi",serif;font-size:1.3rem;letter-spacing:-.01em}
  .card{width:100%%;max-width:420px;border-radius:16px;overflow:hidden;display:block;
    box-shadow:0 18px 50px rgba(0,0,0,.45)}
  .card img{width:100%%;display:block}
  .lede{color:var(--muted);font-size:.95rem;line-height:1.7;text-align:center;max-width:420px}
  .go{display:block;width:100%%;max-width:420px;padding:15px;border-radius:12px;
    background:var(--go);color:#231d3a;font-weight:800;text-align:center;text-decoration:none}
  .foot{color:#6f6885;font-size:.8rem;text-align:center;line-height:1.7}
</style></head><body>
  <p class="top">로드로그</p>
  <a class="card" href="%(go)s"><img src="%(img)s" alt="%(title)s" /></a>
  <p class="lede">%(line)s</p>
  <a class="go" href="%(go)s">나도 내 사주 보러 가기</a>
  <p class="foot">사주로 길을 보고, 기록으로 남겨요<br />오늘의 운세는 복채 없이 보실 수 있어요</p>
</body></html>"""


# ── 공유 카드 ──────────────────────────────────────────
# 🛑 카드는 브라우저 캔버스가 그린 그림이라 링크에 실리지 않는다. 스레드·X 에 주소만
#    붙이면 사이트 대표 그림이 뜨고 정작 그 사람의 카드는 안 보인다 (2026-09-07 지적).
#    그래서 카드마다 주소를 하나씩 내주고, 그 주소의 og:image 를 그 카드로 둔다.
# 🛑 카드에는 이름도 생년월일도 들어가지 않는다(화면에도 그렇게 적어 뒀다).
#    그래도 주소를 아는 사람은 누구나 보므로 id 는 추측할 수 없게 만든다.
CARD_DIR = DATA_DIR / "cards"
CARD_KEEP_DAYS = 90          # 오래된 카드는 지운다. 저장 공간이 무한하지 않다
CARD_MAX_BYTES = 3_000_000


class CardBody(BaseModel):
    image: str                # data:image/jpeg;base64,...
    title: str = ""
    line: str = ""
    ref: str = ""             # 데려온 분 코드. 카드로 들어온 친구가 보면 양쪽 다 등불을 받는다


def _card_sweep() -> None:
    """오래된 카드를 지운다. 새 카드를 올릴 때마다 슬쩍 훑는다."""
    try:
        cut = time.time() - CARD_KEEP_DAYS * 86400
        for f in CARD_DIR.glob("*.jpg"):
            if f.stat().st_mtime < cut:
                f.unlink(missing_ok=True)
                CARD_DIR.joinpath(f.stem + ".json").unlink(missing_ok=True)
    except Exception:
        pass


@app.post("/api/card")
def card_put(body: CardBody, authorization: str | None = Header(default=None)):
    """카드 그림을 받아 두고 나눌 주소를 내준다."""
    _token_user(authorization)
    raw = body.image or ""
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:
        raise HTTPException(400, "그림을 읽지 못했습니다.")
    if not data or len(data) > CARD_MAX_BYTES:
        raise HTTPException(400, "그림이 너무 큽니다.")
    if data[:3] != bytes((0xFF, 0xD8, 0xFF)):        # JPEG 만 받는다
        raise HTTPException(400, "jpg 만 올릴 수 있습니다.")
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    cid = secrets.token_urlsafe(9)
    (CARD_DIR / f"{cid}.jpg").write_bytes(data)
    (CARD_DIR / f"{cid}.json").write_text(json.dumps(
        {"title": (body.title or "")[:60], "line": (body.line or "")[:120],
         "ref": re.sub(r"[^A-Za-z0-9_-]", "", (body.ref or ""))[:24]},
        ensure_ascii=False), "utf-8")
    _card_sweep()
    return {"id": cid, "url": f"{SITE_ORIGIN}/card/{cid}"}


_CARD_ID = re.compile(r"^[A-Za-z0-9_-]{6,24}$")


@app.get("/card/{cid}.jpg")
def card_image(cid: str):
    if not _CARD_ID.match(cid):
        raise HTTPException(404, "Not Found")
    f = CARD_DIR / f"{cid}.jpg"
    if not f.is_file():
        raise HTTPException(404, "Not Found")
    return FileResponse(f, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})


@app.get("/card/{cid}")
def card_page(cid: str):
    """카드 한 장을 보여 주는 쪽. 링크를 붙이면 이 그림이 뜬다."""
    if not _CARD_ID.match(cid) or not (CARD_DIR / f"{cid}.jpg").is_file():
        nf = _safe_web_file("404.html")
        if nf is not None:
            return _file_response(nf, status_code=404)
        raise HTTPException(404, "Not Found")
    meta = {}
    try:
        meta = json.loads((CARD_DIR / f"{cid}.json").read_text("utf-8"))
    except Exception:
        pass
    esc = lambda s: (s or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    title = esc(meta.get("title") or "로드로그 사주")
    line = esc(meta.get("line") or "사주로 길을 보고, 기록으로 남겨요.")
    img = f"{SITE_ORIGIN}/card/{cid}.jpg"
    url = f"{SITE_ORIGIN}/card/{cid}"
    ref = re.sub(r"[^A-Za-z0-9_-]", "", str(meta.get("ref") or ""))[:24]
    go = f"{SITE_ORIGIN}/?ref={ref}" if ref else f"{SITE_ORIGIN}/"
    html = CARD_HTML % {"title": title, "line": line, "img": img, "url": url, "go": go}
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=3600"})



@app.get("/{path:path}")
def spa_fallback(path: str):
    # API·헬스 경로가 정적 폴백에 먹히지 않게
    if path.startswith("api/") or path in {"health", "healthz"}:
        raise HTTPException(404, "Not Found")

    # 🛑 **운영 화면은 끝에 슬래시가 있어야 한다** (2026-09-11 온해님
    #    「관리자 앱을 일반 유저 앱으로 연동 안 되게」).
    #    손님 앱의 manifest 는 `scope: "/"` 라 **사이트 전체를 덮는다.** 그래서
    #    `/admin` 을 홈 화면에 담아도 이미 깔린 손님 앱이 그 주소를 가로챘다.
    #    운영 앱은 `scope: "/admin/"` 으로 **더 좁게** 잡아 두었다 — 크롬은 겹치면
    #    **더 긴 scope** 를 쓰므로 그때만 운영 앱이 이긴다.
    #    그러려면 문서 주소가 반드시 `/admin/` 이어야 한다. `/admin` 은 그 밖이다.
    if path in {"admin", "admin.html"}:
        return RedirectResponse("/admin/", status_code=308)

    # 🛑 옛 주소 정리보다 **실제 파일이 먼저다.** 2026-09-07 에 사주 블로그를
    #    /blog 아래에 냈는데, 운행일지 시절 규칙이 그걸 통째로 홈으로 보냈다.
    safe = _safe_web_file(path)
    if safe is not None:
        return _file_response(safe)
    cleaned = path.strip("/")
    for rel in (f"{cleaned}/index.html", f"{cleaned}.html"):
        if cleaned and ".." not in cleaned.replace("\\", "/").split("/"):
            hit = _safe_web_file(rel)
            if hit is not None:
                return _file_response(hit)

    cleaned_head = cleaned
    if cleaned_head and any(
        cleaned_head == pre or cleaned_head.startswith(pre + "/") or cleaned_head.startswith(pre + ".")
        for pre in _GONE_PREFIXES
    ):
        return RedirectResponse("/", status_code=301)
    if cleaned and ".." not in cleaned.replace("\\", "/").split("/"):
        for rel in (f"{cleaned}/index.html", f"{cleaned}.html"):
            safe_idx = _safe_web_file(rel)
            if safe_idx is not None:
                return _file_response(safe_idx)
    # 🛑 없는 주소에 홈을 200 으로 돌려주지 않는다 (2026-09-07).
    #    그전에는 여기서 index.html 을 200 으로 줬다. 검색엔진은 그것을 홈의
    #    복사본으로 읽어(soft 404) 색인에 불리하고, 손님은 주소를 잘못 눌러
    #    놓고 홈을 보게 되니 무엇이 잘못됐는지 모른다.
    #    로드로그는 화면 이동을 전부 해시(#p/…)로 하므로 경로 폴백이 필요 없다.
    nf = _safe_web_file("404.html")
    if nf is not None:
        return _file_response(nf, status_code=404)
    raise HTTPException(404, "Not Found")
