"""
로드로그 (RoadLog) — 프리미엄 웹 서버
FastAPI + 정적 프론트엔드 + 기존 modules 재사용

실행:
  .venv\\Scripts\\python.exe -m uvicorn server:app --reload --port 8501
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import (
    Cookie,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import logging

log = logging.getLogger("roadlog")

from modules import db
from modules.config import (
    ALLOW_DEMO_BILLING_UPGRADE,
    APP_ENV,
    APP_FULL,
    APP_TITLE,
    CONTACT_EMAIL,
    DATA_DIR,
    FREE_TOTAL_LIMIT,
    MIN_PASSWORD_LENGTH,
    COST_MODE,
    assert_secure_for_production,
    cors_allow_origins,
    data_dir_is_external,
    is_free_cost_mode,
    is_production,
    llm_configured,
    resolve_llm_config,
    security_issues,
)
from modules import admin_ops
# 손님이 쓴 말이 봐 달라는 것인지 그냥 건네는 말인지 가른다 (2026-09-11 3단계)
from modules import intent as intent_ops
from modules import saju_writer
from modules import dream as dream_ops
from modules import pet as pet_ops
from modules import pet_hall as pet_hall_ops
from modules.rate_limit import (
    AUTH_LIMIT,
    AUTH_WINDOW,
    REGISTER_LIMIT,
    REGISTER_WINDOW,
    limiter,
)
from modules import inbox
from modules import feedback as feedback_ops
from modules import mailer
from modules import password_reset as reset_ops
from modules import lamps as lamps_ops
from modules import product_reviews as prev_ops
from modules import records as rec_ops
from modules import gwansang as gwansang_ops
from modules import stats as stats_ops
from modules import curse_shrine as curse_ops
from modules import marketing_os as marketing_ops
from modules import marketing_diagnostics as marketing_diag
from modules import marketing_attribution as marketing_attr
from modules.marketing_blog import BlogPublisher
from modules.marketing_core.repository import MarketingRepository

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

def _marketing_repo() -> MarketingRepository:
    return MarketingRepository(marketing_ops.DB,marketing_ops.TENANT_ID,legacy_tenant_id=marketing_ops.TENANT_ID)

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

@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    stop_marketing = threading.Event()

    def marketing_loop() -> None:
        while not stop_marketing.is_set():
            try:
                marketing_ops.run_due(WEB)
            except Exception as exc:
                log.error("marketing scheduler check failed: %s", type(exc).__name__)
            stop_marketing.wait(60)

    worker = threading.Thread(target=marketing_loop, name="roadlog-marketing-demo", daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop_marketing.set()
        worker.join(timeout=2)


app = FastAPI(title=APP_FULL, version="3.1", lifespan=app_lifespan)
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
_SESSIONS_RELOAD_AT = 0.0


def _token_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    token = authorization.removeprefix("Bearer ").strip()
    user = _sessions.get(token)
    if not user and len(token) <= 128:
        # 디스크에서 재로드 시도 (다른 워커/재시작 직후)
        # 🛑 **30초에 한 번만** (2026-09-14 전수 검사). 아무 토큰이나 보내면 요청마다 세션 파일과 회원 파일을
        #    통째로 다시 읽어, 가짜 토큰을 연달아 보내는 것만으로 서버를 느리게 할 수 있었다
        global _SESSIONS_RELOAD_AT
        now = time.monotonic()
        if now - _SESSIONS_RELOAD_AT > 30:
            _SESSIONS_RELOAD_AT = now
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
    # 🛑 **오늘 들어온 회원**을 남긴다 (2026-09-12 온해님 「기존 회원이 재방문하는건지
    #    궁금해서」). 하루에 한 사람당 한 번만 디스크를 만진다.
    # 🛑 **관리자는 세지 않는다** (2026-09-13 온해님 「오늘 들어온 회원이 계속
    #    1명으로 뜨는데 회원 유입이 없는 건가?」). 그 1명이 온해님 본인이었다 —
    #    관리자 화면을 열어 두면 매일 1명으로 찍혀서, 손님이 하나도 안 돌아와도
    #    「1명은 왔다」로 읽혔다. 여기는 **손님이 다시 왔나**를 보는 자리다.
    try:
        if not user.get("is_admin"):
            stats_ops.seen_member(user.get("email", ""))
    except Exception:
        pass
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


class MarketingTrialBody(BaseModel):
    product_id: str
    platform: str = "블로그"
    mode: str = "REAL"


class MarketingProviderTestBody(BaseModel):
    live: bool = False
    product_id: str = ""
    query: str = ""


class MarketingDecisionBody(BaseModel):
    note: str = ""


class MarketingInstagramPublishBody(BaseModel):
    image_url: str
    confirmed: bool = False


class MarketingAssetImportBody(BaseModel):
    kind: str
    mime: str
    data_base64: str


class MarketingBundleBody(BaseModel):
    product_id: str
    customer_question: str
    mode: str = "REAL"
    source_text: str = ""


class ForgotBody(BaseModel):
    email: str


class ResetBody(BaseModel):
    token: str
    password: str


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
    try:
        marketing_attr.attributed_signup(_marketing_repo(),body.email,request.cookies.get(marketing_attr.COOKIE,""))
    except Exception:
        log.exception("마케팅 가입 귀속 기록 실패")
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
    # 🛑 **데려오신 분께도 알린다** (2026-09-11 온해님 「각자 알림으로」).
    #    그전에는 등불만 조용히 들어가서, 친구가 들어온 줄도 모르고 넘어갔다.
    #    받은 줄 모르면 준 게 아니다 — 그러면 또 데려올 이유도 안 생긴다.
    try:
        who = (gift.get("inviter") or "").strip()
        if who:
            got = int(gift.get("inviterLamps") or 0)
            tk = int(gift.get("inviterTicket") or 0)
            inbox.push(
                who, "친구가 들어왔어요",
                "초대 링크로 한 분이 가입하셨어요. 등불 %d개%s를 드렸습니다. "
                "이용권은 리포트 한 편을 복채 없이 여는 데 쓰세요."
                % (got, " 와 무료 이용권 1장" if tk else ""),
                key="refer-in:%s" % body.email.strip().lower(),
            )
    except Exception as e:                      # noqa: BLE001
        log.error("초대 알림 실패: %s", e)
    return {"ok": True, "message": msg, "welcome": gift.get("given", 0), "referred": gift.get("referred", 0)}


def _welcome_inbox(email: str, gift: dict) -> None:
    """가입한 분께 무엇을 드렸는지 알림함에 남긴다."""
    given = gift.get("given", 0)
    if given:
        # 🛑 **이용권을 먼저 알린다** (2026-09-13). 전에는 등불만 알렸는데, 그 등불로는
        #    사주를 열 수 없어서(더 물어보기 전용) 받고도 쓸 데를 못 찾았다.
        inbox.push(
            email,
            "무료 이용권 한 장과 등불 %d개를 드렸어요" % given,
            "이용권으로 사주 한 편을 복채 없이 열어 보실 수 있어요. "
            "등불로도 열 수 있고, 읽다가 궁금한 걸 무냥이한테 물어볼 때도 써요.",
            key="welcome", icon="lamp",
        )
    if gift.get("referred"):
        inbox.push(
            email,
            "친구 따라 들어오셔서 등불 %d개를 더 드렸어요" % int(gift.get("referred") or 0),
            "데려오신 분께도 등불을 드렸어요. 고맙습니다. "
            "친구를 데려오시면 등불 120개를 받으실 수 있어요 — 사주를 여는 데도 써요.",
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


def _social_login(email: str, name: str, provider: str, provider_key: str = "", request: Request | None = None) -> str:
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
        if request is not None:
            try:
                marketing_attr.attributed_signup(_marketing_repo(),email,request.cookies.get(marketing_attr.COOKIE,""))
            except Exception:
                log.exception("마케팅 소셜 가입 귀속 기록 실패")
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
def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
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
    # 🛑 구글이 확인 안 된 주소라고 알려 주면 받지 않는다 (2026-09-14 전수 검사 · 남의 계정에 잇지 않게)
    if d.get("verified_email") is False:
        raise HTTPException(400, "구글 계정의 이메일 확인이 끝나지 않았어요. 구글에서 이메일을 확인한 뒤 다시 시도해 주세요.")
    return _social_redirect(_social_login(d.get("email", ""), d.get("name", ""), "구글", "google", request))


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
def kakao_callback(request: Request, code: str = "", state: str = "", error: str = ""):
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
    # 🛑 카카오가 **확인 안 된 주소라고 분명히 알려 준 경우** 그 주소로 기존 계정에 잇지 않는다 (2026-09-14 전수 검사).
    #    남의 주소를 카카오에 적어 두고 그 사람 계정으로 들어오는 것을 막는다. 값이 아예 없으면(동의 범위 밖) 예전대로 둔다
    if email and (acc.get("is_email_verified") is False or acc.get("is_email_valid") is False):
        email = ""
    if not email:
        # 이메일 동의를 안 했거나 카카오 계정에 이메일이 없는 경우.
        # 우리 쪽에서만 쓰는 주소를 만들어 계정을 잇는다.
        email = f"kakao{d.get('id')}@kakao.local"
    return _social_redirect(_social_login(email, name, "카카오", "kakao", request))


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


# ── 서식·말투 학습 ─────────────────────────────────────


# ── 관리자 운영 ───────────────────────────────────────


class FreePassBody(BaseModel):
    email: str
    on: bool = True


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
        # ── 지금 사이트에 있는 사람 (2026-09-12 온해님) ──────────────
        # 🛑 **API 요청까지 센다.** 화면이 SPA 라 손님이 사주를 보는 내내 HTML 요청이
        #    한 번도 안 간다. 아래 `hit()` 조건(HTML 만)으로는 「지금」을 못 센다.
        # 🛑 운영 화면(`admin`)은 빼고 센다 — 그건 손님이 아니다.
        try:
            ua0 = request.headers.get("user-agent", "") or ""
            low0 = ua0.lower()
            if ("mozilla" in low0 and not any(b in low0 for b in _BOT)
                    and not p.startswith("/assets") and "admin" not in p):
                # 🛑 **토큰이 살아 있을 때만 회원으로 센다** (2026-09-12 온해님
                #    「지금 접속중 회원이 4명으로 뜨는데?」). 헤더만 보고 세면
                #    **만료된 토큰이 남은 브라우저**까지 회원이 된다.
                #    서버가 401 을 돌려줬으면 그 토큰은 죽은 것이다.
                _tok = bool(request.headers.get("authorization"))
                stats_ops.live_touch(_client_ip(request), ua0,
                                     _tok and resp.status_code != 401)
        except Exception:
            pass
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
                if q.get("rl_campaign_id") and q.get("rl_publication_id"):
                    visitor_id = marketing_attr.valid_visitor(request.cookies.get(marketing_attr.COOKIE,"")) or marketing_attr.new_visitor()
                    if marketing_attr.tracked_visit(_marketing_repo(),visitor_id,dict(q),p):
                        resp.set_cookie(marketing_attr.COOKIE,marketing_attr.visitor_cookie(visitor_id),
                                        max_age=marketing_attr.WINDOW_DAYS*86400,httponly=True,
                                        secure=is_production(),samesite="lax",path="/")
    except Exception:
        pass          # 통계 때문에 화면이 막히면 안 된다
    return resp


@app.get("/api/admin/marketing/status")
def admin_marketing_status(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.status(WEB)


@app.get("/api/admin/marketing/insights")
def admin_marketing_insights(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.performance_snapshot()


@app.get("/api/admin/marketing/team")
def admin_marketing_team(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.team_dashboard()


@app.post("/api/admin/marketing/control/{action}")
def admin_marketing_control(action: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.control(action)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/admin/marketing/automation/{action}")
def admin_marketing_automation(action: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    if action not in ("enable", "disable"):
        raise HTTPException(400, "지원하지 않는 자동화 명령입니다.")
    try:
        return marketing_ops.set_auto_real(action == "enable")
    except PermissionError as exc:
        raise HTTPException(423, str(exc)) from exc


@app.post("/api/admin/marketing/jobs/{job_key}")
def admin_marketing_job(job_key: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.run_job(job_key)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/admin/marketing/products")
def admin_marketing_products(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.products(WEB)


@app.post("/api/admin/marketing/products/sync")
def admin_marketing_products_sync(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.products(WEB)


@app.get("/api/admin/marketing/usage")
def admin_marketing_usage(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.usage()


@app.get("/api/admin/marketing/safety")
def admin_marketing_safety(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules.marketing_safety import board
    return board()


@app.get("/api/admin/marketing/providers")
def admin_marketing_providers(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {"items": marketing_diag.provider_status(_marketing_repo(), WEB)}


@app.post("/api/admin/marketing/providers/{provider}/test")
def admin_marketing_provider_test(provider: str, body: MarketingProviderTestBody,
                                  authorization: str | None = Header(default=None)):
    administrator = _require_admin(authorization)
    if provider != "tavily":
        raise HTTPException(423, "이 공급자의 실제 진단 호출은 비활성화되어 있습니다.")
    try:
        return marketing_diag.test_tavily(_marketing_repo(), WEB, administrator["email"],
                                          body.product_id, body.query, live=body.live)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(423, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/admin/marketing/test-campaign")
def admin_marketing_test_campaign(body: dict, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.test_campaign(WEB, str(body.get("product_id", "")),
                                           body.get("use_search") is True, body.get("use_gemini") is True)
    except PermissionError as exc:
        raise HTTPException(423, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/admin/marketing/trial")
def admin_marketing_trial(body: MarketingTrialBody, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.trial(WEB, body.product_id, body.platform, body.mode)
    except PermissionError as exc:
        raise HTTPException(423, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/admin/marketing/approvals")
def admin_marketing_approvals(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {"items": marketing_ops.approvals()}


@app.get("/api/admin/marketing/approvals/{approval_id}/creative-brief")
def admin_marketing_creative_brief(approval_id: int, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.creative_brief(approval_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/admin/marketing/approvals/{approval_id}/creative-assets")
def admin_marketing_creative_import(approval_id: int, body: MarketingAssetImportBody, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.import_creative_asset(approval_id, body.kind, body.mime, body.data_base64)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/admin/marketing/creative-assets/{asset_id}")
def admin_marketing_creative_file(asset_id: int, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        path, mime = marketing_ops.creative_asset_file(asset_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/admin/marketing/instagram/status")
def admin_marketing_instagram_status(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return marketing_ops.instagram_status()


@app.post("/api/admin/marketing/approvals/{approval_id}/publish-instagram")
def admin_marketing_publish_instagram(approval_id: int, body: MarketingInstagramPublishBody,
                                      authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    if body.confirmed is not True:
        raise HTTPException(400, "게시 직전 확인이 필요합니다.")
    try:
        return marketing_ops.publish_instagram(approval_id,body.image_url)
    except PermissionError as exc:
        raise HTTPException(423,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502,str(exc)) from exc


@app.get("/api/admin/marketing/bundles")
def admin_marketing_bundles(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {"items": marketing_ops.bundles()}


@app.post("/api/admin/marketing/bundles")
def admin_marketing_create_bundle(body: MarketingBundleBody, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.create_bundle(WEB, body.product_id, body.customer_question, body.mode, body.source_text)
    except PermissionError as exc:
        raise HTTPException(423, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/admin/marketing/approvals/{approval_id}/{decision}")
def admin_marketing_decide(approval_id: int, decision: str, body: MarketingDecisionBody,
                           authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    try:
        return marketing_ops.decide(approval_id, decision, body.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        log.exception("마케팅 블로그 게시 실패")
        raise HTTPException(500, "블로그 게시물을 확인하지 못했습니다. 게시 실패 상태를 확인해 주세요.") from exc


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


@app.get("/api/ping")
def ping():
    """화면이 열려 있다는 신호. 접속 중을 세는 데만 쓴다 (2026-09-13 온해님).

    🛑 **몸통이 비어 있는 게 맞다.** 실제로 세는 것은 위 미들웨어의 `live_touch` 이고,
       이 주소는 **요청을 한 번 일으키려고** 있다. 화면이 SPA 라 손님이 사주를
       읽는 내내 요청이 한 번도 안 가서, 보고 있는 사람이 「접속 중」에서 사라졌다.
    🛑 방문(pv)에는 안 잡힌다 — 아래 `hit()` 은 HTML 요청만 센다.
    """
    return {"ok": True}


@app.get("/api/admin/live")
def admin_live(authorization: str | None = Header(default=None)):
    """지금 사이트에 있는 사람 + 오늘 들어온 회원 (2026-09-12 온해님).

    · live      최근 5분 안에 움직인 사람 — 전부 / 회원 / 비회원
    · seen      날짜별로 **로그인해서 들어온 회원** 수 (오늘·어제)

    🛑 `live` 는 메모리라 서버가 다시 뜨면 0부터다. 「지금」이라 그게 맞다.
    🛑 회원인지는 Authorization 헤더가 붙었는지로만 본다 — 세는 값이라 그 정도면 된다.
    """
    _require_admin(authorization)
    return {"live": stats_ops.live(), "seen": stats_ops.seen_days(2)}


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


class DcPromoDraft(BaseModel):
    gallery: str
    title: str = ""
    body: str = ""


class DcPromoDraftsBody(BaseModel):
    items: list[DcPromoDraft]


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


@app.get("/api/admin/dc-promos")
def admin_dc_promos(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules import dc_promos as dc_promos_ops
    try:
        return {"items": dc_promos_ops.listing()}
    except dc_promos_ops.PromoStoreError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.put("/api/admin/dc-promos")
def admin_dc_promos_save(
    body: DcPromoDraftsBody, authorization: str | None = Header(default=None)
):
    _require_admin(authorization)
    from modules import dc_promos as dc_promos_ops
    try:
        items = [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in body.items]
        return {"items": dc_promos_ops.save(items)}
    except dc_promos_ops.PromoStoreError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/admin/dc-promos/generate")
def admin_dc_promos_generate(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    from modules import dc_promos as dc_promos_ops
    try:
        return {"items": dc_promos_ops.generate()}
    except dc_promos_ops.PromoStoreError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/coupon/use")
def coupon_use(body: CouponUse, authorization: str | None = Header(default=None)):
    """손님이 코드를 넣어 한 편을 연다. 🛑 복채를 받지 않는다."""
    user = _token_user(authorization)
    from modules import coupons as coupons_ops

    product = (body.product or "").strip()[:24]
    pair = (body.pair or "").strip()
    if not lamps_ops.won_of(product) and product not in lamps_ops.PRICES:
        raise HTTPException(400, "없는 상품이에요.")
    if not lamps_ops._PAIR_RE.match(pair):
        raise HTTPException(400, "잘못된 요청입니다.")
    # 🛑 **자리를 먼저 잡고(use · 잠금 안에서 확인+기록) 연다** (2026-09-14 전수 검사).
    #    확인 → 열기 → 기록 순서면 같은 코드를 동시에 두 번 보내 두 편이 열리거나 자리보다 많이 나갔다
    try:
        got = coupons_ops.use(body.code, user["email"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        out = lamps_ops.gift_open(user["email"], product, pair, kind="coupon-open",
                                  note="쿠폰 %s" % (body.code or "").strip().upper())
    except ValueError as e:
        raise HTTPException(400, str(e))
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


class ApiCostBody(BaseModel):
    wonIn: float = 0        # 들어간 토큰 백만 개당 원
    wonOut: float = 0       # 나온 토큰 백만 개당 원
    start: float = 0        # 지금 잔액(원) — 충전할 때마다 적어 둔다


@app.get("/api/admin/apicost")
def admin_apicost(authorization: str | None = Header(default=None)):
    """제미나이에 얼마나 썼나 (2026-09-11 온해님).

    🛑 **구글은 잔액 API 를 안 준다.** 우리가 쓴 만큼을 세어 **추정**을 보여 준다.
       진짜 잔액은 aistudio.google.com/billing 에서 봐야 한다.
    """
    _require_admin(authorization)
    from modules import apicost
    return apicost.summary()


@app.post("/api/admin/apicost")
def admin_apicost_put(body: ApiCostBody, authorization: str | None = Header(default=None)):
    """단가와 지금 잔액을 적는다. 잔액을 새로 적으면 그날부터 다시 센다."""
    _require_admin(authorization)
    from modules import apicost
    apicost.put_settings(won_in=body.wonIn, won_out=body.wonOut, start=body.start)
    return apicost.summary()


@app.post("/api/admin/lamps/regift")
def admin_regift(body: RegiftBody, authorization: str | None = Header(default=None)):
    """등불 계단을 올렸을 때 **이미 복채를 내신 분께 차액을 드린다** (2026-09-11 온해님).

    🛑 두 번 눌러도 두 번 주지 않는다 — 원장에 준 표시를 남긴다.
    """
    _require_admin(authorization)
    # 🛑 **주인·VIP 는 대상에서 뺀다** (2026-09-11 온해님). 복채를 안 내고 다 보시는
    #    분들이라 드릴 차액이 없고, 목록에 줄줄이 뜨면 손님이 묻힌다.
    skip = set(_free_pass())
    try:
        for em in list(lamps_ops._read().keys()):
            try:
                u = db.get_user(em)
            except Exception:                            # noqa: BLE001
                u = None
            if u and _is_free(u):
                skip.add(str(em).strip().lower())
    except Exception:                                    # noqa: BLE001
        pass
    try:
        got = lamps_ops.regift(apply=bool(body.apply), skip=skip)
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


@app.post("/api/admin/lamps/welcome-again")
def admin_welcome_again(authorization: str | None = Header(default=None),
                        apply: bool = False):
    """이미 가입한 분들께 이용권 1장 + 등불 300개를 소급 (2026-09-13 온해님).

    🛑 `apply=false` 가 기본이다. **먼저 세어 보고** 넣는다.
    """
    _require_admin(authorization)
    out = lamps_ops.welcome_again(apply=apply)
    # 🛑 **넣기만 하면 아무도 모른다.** 다음에 들어오실 때 보시도록 알림함에 남긴다.
    if apply:
        for r in out.get("rows", []):
            try:
                inbox.push(
                    r["email"],
                    "무료 이용권 한 장과 등불을 더 드렸어요",
                    "이용권으로 사주 한 편을 복채 없이 열어 보실 수 있어요. "
                    "프리미엄만 빼고 어느 편이든 고르시면 돼요.",
                    key="welcome-again", icon="lamp",
                )
            except Exception as e:                        # noqa: BLE001
                log.error("소급 알림 실패 (%s): %s", r.get("email"), e)
    return out


@app.post("/api/admin/lamps/pay-regift")
def admin_pay_regift(authorization: str | None = Header(default=None),
                     apply: bool = False):
    """복채를 내신 분께 결제액 ÷ 50 만큼 등불을 맞춰 드린다 (2026-09-13 온해님).

    🛑 `apply=false` 가 기본이다. 먼저 세어 보고 넣는다.
    """
    _require_admin(authorization)
    out = lamps_ops.pay_regift(apply=apply)
    if apply:
        for r in out.get("rows", []):
            if not r.get("more"):
                continue
            try:
                inbox.push(
                    r["email"],
                    "등불 %d개를 더 드렸어요" % int(r["more"]),
                    "복채를 내 주신 만큼 등불을 다시 맞춰 드렸어요. "
                    "프리미엄만 빼고 사주를 등불로도 열어 보실 수 있어요.",
                    key="pay-regift", icon="lamp",
                )
            except Exception as e:                        # noqa: BLE001
                log.error("복채 소급 알림 실패 (%s): %s", r.get("email"), e)
    return out


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
    try:
        _marketing_repo().refund_attributed_purchase(marketing_attr.payment_key(pid),marketing_attr.stamp())
    except Exception:
        log.exception("마케팅 귀속 환불 반영 실패")

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


class CurseBody(BaseModel):
    ritual: str = ""
    pair: str = ""
    targetType: str = ""
    targetName: str = ""
    birthDate: str = ""
    reason: str = ""
    photo: str = ""
    card: str = ""
    free: dict = {}


def _curse_inputs(body: CurseBody) -> dict[str, str]:
    ritual = (body.ritual or "").strip().lower()
    pair = (body.pair or "").strip().lower()
    target_type = " ".join((body.targetType or "").split())[:30]
    target_name = " ".join((body.targetName or "").split())[:30]
    birth_date = (body.birthDate or "").strip()[:10]
    reason = " ".join((body.reason or "").split())[:240]
    photo = (body.photo or "").strip()
    card = " ".join((body.card or "").split())[:40]
    if ritual and not re.fullmatch(r"[0-9a-f]{24,64}", ritual):
        raise HTTPException(400, "의식 번호가 올바르지 않아요.")
    if pair and not lamps_ops._PAIR_RE.match(pair):
        raise HTTPException(400, "의식 표가 올바르지 않아요.")
    if target_type not in {"전애인", "썸", "친구", "직장동료", "기타"}:
        raise HTTPException(400, "저주 대상을 다시 골라 주세요.")
    if birth_date and not re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])", birth_date):
        raise HTTPException(400, "대상의 생년월일을 다시 확인해 주세요.")
    photo_data = ""
    if photo:
        match = re.fullmatch(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)", photo)
        if not match or len(match.group(2)) > 700_000:
            raise HTTPException(400, "대상 사진 형식이나 크기를 다시 확인해 주세요.")
        photo_data = match.group(2)
    if len(reason) < 2 or not card:
        raise HTTPException(400, "열받은 이유와 카드를 채워 주세요.")
    return {"ritual": ritual, "pair": pair, "targetType": target_type,
            "targetName": target_name, "birthDate": birth_date, "reason": reason,
            "photo": photo_data, "photoProvided": bool(photo_data), "card": card}


@app.post("/api/curse/free")
def curse_free(body: CurseBody, request: Request):
    """로그인 전에 한 장 보여 주는 무료 결과."""
    _rate_limit_or_429("curse-free:" + _client_ip(request), limit=8, window_sec=3600,
                       what="저주 신단 무료 결과")
    data = _curse_inputs(body)
    try:
        result = curse_ops.free_result(data["targetType"], data["targetName"], data["birthDate"],
                                       data["reason"], data["card"], data["photo"])
    except Exception as exc:
        log.exception("curse free generation failed")
        raise HTTPException(503, "무냥이가 촛불을 다시 켜고 있어요. 잠시 뒤 다시 뽑아 주세요.") from exc
    return {"ok": True, "result": result}


@app.post("/api/curse/detail")
def curse_detail(body: CurseBody, authorization: str | None = Header(default=None)):
    """결제 또는 등불 차감으로 소유권이 생긴 의식의 상세 결과."""
    user = _token_user(authorization)
    data = _curse_inputs(body)
    if not data["ritual"] or not data["pair"]:
        raise HTTPException(400, "의식 번호가 비어 있어요.")
    saved = curse_ops.get(user["email"], data["ritual"])
    if saved and int(saved.get("detailVersion", 0)) >= curse_ops.DETAIL_VERSION:
        return {"ok": True, "saved": True, **saved}
    if not (_is_free(user) or lamps_ops.owns(user["email"], curse_ops.PRODUCT_ID, data["pair"])):
        raise HTTPException(402, "상세 결과를 먼저 열어 주세요.")
    try:
        detail = curse_ops.detail_result(data["targetType"], data["targetName"], data["birthDate"],
                                         data["reason"], data["card"], data["photo"], body.free)
        row = curse_ops.save(user["email"], data["ritual"], data["pair"],
                             {k: data[k] for k in ("targetType", "targetName", "birthDate", "reason", "photoProvided", "card")},
                             body.free or {}, detail)
    except Exception as exc:
        log.exception("curse detail generation failed")
        raise HTTPException(503, "상세 결과를 적다가 촛불이 꺼졌어요. 잠시 뒤 다시 열어 주세요.") from exc
    return {"ok": True, "saved": False, **row}


@app.get("/api/curse/{ritual}")
def curse_saved(ritual: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    if not re.fullmatch(r"[0-9a-f]{24,64}", (ritual or "").lower()):
        raise HTTPException(400, "의식 번호가 올바르지 않아요.")
    row = curse_ops.get(user["email"], ritual.lower())
    if not row:
        raise HTTPException(404, "저장된 의식을 찾지 못했어요.")
    return {"ok": True, **row}


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
    # 🛑 **한 자리를 몇 자로 쓸지** (2026-09-12 온해님 「금액에 비해 해석 글자수가
    #    제대로 나오는지」). 앞단 `gwansang.js:gwanChars` 가 값에 따라 정해 보낸다.
    #    0 이면 `read_face` 기본값으로 떨어진다 — 옛 화면이 안 보내도 깨지지 않게.
    chars: int = 0
    product: str
    shots: list[str]          # data URL 또는 base64 jpeg. 「둘이 보는 관상」만 두 장
    name: str = ""


class HeicConvertBody(BaseModel):
    """갤럭시 HEIC 사진을 메모리에서만 JPEG로 바꾸는 요청."""
    image: str
    name: str = ""
    type: str = ""


_HEIC_MAX_BYTES = 20 * 1024 * 1024


@app.post("/api/photo/heic-to-jpeg")
def heic_to_jpeg(body: HeicConvertBody, request: Request):
    """HEIC/HEIF를 디스크에 쓰지 않고 관상용 JPEG로 줄인다."""
    ip = _client_ip(request)
    if not limiter.allow("heic-convert:" + ip, limit=8, window_sec=600):
        raise HTTPException(429, "사진 변환은 잠시 쉬었다가 다시 해 주세요.")
    raw = (body.image or "").split(",", 1)[-1]
    try:
        source = base64.b64decode(raw, validate=True)
    except Exception:
        raise HTTPException(400, "사진을 읽지 못했어요. 다시 골라 주세요.") from None
    if not source:
        raise HTTPException(400, "사진이 비어 있어요. 다시 골라 주세요.")
    if len(source) > _HEIC_MAX_BYTES:
        mb = len(source) / 1024 / 1024
        raise HTTPException(413, "사진 용량이 %.1fMB예요. 20MB보다 작은 사진으로 다시 올려 주세요." % mb)
    try:
        import pillow_heif
        from PIL import Image, ImageOps

        pillow_heif.register_heif_opener()
        with Image.open(io.BytesIO(source)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((768, 768), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=82, optimize=True)
        jpeg = out.getvalue()
    except Exception:
        raise HTTPException(400, "고효율 사진을 JPG로 바꾸지 못했어요. 다른 사진으로 다시 시도해 주세요.") from None
    return {"image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")}


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


class TicketBody(BaseModel):
    product: str
    pair: str


def _mask_name(name: str, email: str) -> str:
    """이름 가운데를 가린다. 🛑 공개 화면에 나가므로 누구인지 알 수 없어야 한다."""
    nm = " ".join(str(name or "").split())
    if len(nm) >= 3:
        return nm[0] + "○" * (len(nm) - 2) + nm[-1]
    if len(nm) == 2:
        return nm[0] + "○"
    if nm:
        return nm
    head = str(email or "").split("@")[0][:2] or "손님"
    return head + "○○"


@app.get("/api/refer/top")
def refer_top():
    """친구를 많이 데려온 분 셋 (2026-09-11 온해님).

    🛑 **로그인 없이 본다.** 홈에 걸리는 줄이라 손님도 봐야 초대할 마음이 생긴다.
    🛑 **이름을 가리고, 초대 수만 준다.** 이메일·등불은 내보내지 않는다 —
       등불로 겨루는 화면처럼 보이면 포인트 충전 업종으로 읽힌다 (카드사 심사 중).
    """
    # 🛑 **주인·VIP·테스트 계정은 순위에서 뺀다** (2026-09-11). 선착순 이벤트에서도
    #    같은 계정들을 뺐다 — 우리가 우리 화면에서 1등을 하면 손님이 겨룰 마음이
    #    안 생기고, 「관○자」가 메인에 걸린 꼴도 이상하다.
    #    그래서 넉넉히 받아 걸러 낸 뒤 앞에서 셋만 쓴다.
    out = []
    try:
        for b in lamps_ops.refer_board(20):
            em = b.get("email") or ""
            try:
                u = db.get_user(em) or {}
            except Exception:                            # noqa: BLE001
                u = {}
            if not u or _is_free(u):
                continue
            n = len(out) + 1
            key, nm = lamps_ops.RANK_BADGES[n - 1] if n <= len(lamps_ops.RANK_BADGES) else ("", "")
            out.append({"rank": n, "count": b["count"], "key": key, "name": nm,
                        "who": _mask_name(u.get("name") or "", em)})
            if len(out) >= 3:
                break
    except Exception:                                    # noqa: BLE001
        return {"top": []}
    return {"top": out}


@app.get("/api/tickets")
def tickets_left(authorization: str | None = Header(default=None)):
    """남은 무료 이용권. 친구를 데려오면 한 장씩 쌓인다 (2026-09-11 온해님)."""
    user = _token_user(authorization)
    return lamps_ops.tickets(user["email"])


@app.post("/api/tickets/use")
def ticket_use(body: TicketBody, authorization: str | None = Header(default=None)):
    """무료 이용권 한 장으로 리포트 한 편을 연다.

    🛑 **깎아 주는 것이 아니라 통째로 여는 것이다.** 결제 금액이 화면과 달라지면
       카드사 심사 「노출 금액 = 결제창 금액」에 걸린다 (`coupons.py` 와 같은 규칙).
    """
    user = _token_user(authorization)
    product = (body.product or "").strip()[:24]
    if not lamps_ops.won_of(product) and product not in lamps_ops.PRICES:
        raise HTTPException(400, "없는 상품이에요.")
    try:
        out = lamps_ops.use_ticket(user["email"], product, (body.pair or "").strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        inbox.push(user["email"], "무료 이용권을 쓰셨어요",
                   "리포트 한 편을 복채 없이 열었어요. 남은 이용권 %d장." % out.get("left", 0),
                   key="ticket-use:%s" % product)
    except Exception:                            # noqa: BLE001
        pass
    return out


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


@app.post("/api/lamps/daily")
def lamps_daily(authorization: str | None = Header(default=None)):
    """홈페이지에 로그인해 들어온 회원의 하루 한 번 접속 선물."""
    user = _token_user(authorization)
    gift = lamps_ops.claim_daily(user["email"])
    if gift["given"]:
        # 잔액만 바뀌면 받은 줄 모르고 지나가므로, 기존 편지함에도 남긴다.
        inbox.push(
            user["email"],
            "오늘 접속 선물로 등불 60개를 드렸어요",
            "오늘도 무냥이와 마음을 천천히 읽어 보세요. 내일 다시 오시면 등불을 또 드려요.",
            key="daily:%s" % gift["day"], icon="lamp",
        )
    return gift


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
        result = lamps_ops.charge(user["email"], lamps, payment_id=body.paymentId.strip(), price=amount)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        marketing_attr.attributed_purchase(_marketing_repo(),user["email"],body.paymentId.strip(),"lamps","charge",amount)
    except Exception:
        log.exception("마케팅 충전 귀속 기록 실패")
    return result


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
    try:
        moved = rec_ops.merge_in(user["email"], body.items)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(400, "옮길 기록의 모양이 올바르지 않아요.")   # 🛑 500 대신 (2026-09-14 전수 검사)
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
    # 🛑 **빈 답에는 등불을 받지 않는다** (2026-09-14 전수 검사). 모델이 글 없이 답하면 30개가 나가고 빈 말풍선만 떴다
    if not str(res.get("text") or "").strip():
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
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:   # 🛑 사주 값 모양이 틀리면 500 대신 (2026-09-14 전수 검사)
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
        result = lamps_ops.buy_premium(
            user["email"], body.product.strip(), body.pair.strip(),
            payment_id=body.paymentId.strip(), paid=amount,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        marketing_attr.attributed_purchase(_marketing_repo(),user["email"],body.paymentId.strip(),body.product.strip(),"premium",amount)
    except Exception:
        log.exception("마케팅 상품 결제 귀속 기록 실패")
    return result


# ── 관상 ────────────────────────────────────────────────
# 🛑 **사진을 저장하지 않는다.** 받은 그대로 Gemini 로 넘기고 그 자리에서 버린다.
#    파일을 만들지 않으므로 디스크에 남을 일이 없다.
# 🛑 아직 **만드는 중**이라 주인만 부를 수 있다. 상품이 열리면 결제를 붙인다.
GWAN_MAX_SHOTS = 2


# 🛑 **글의 얼개가 바뀌면 저장해 둔 것을 버린다** (2026-09-09 실측).
#    항목을 나눠 길게 쓰게 고쳤는데, 같은 사진으로 다시 열면 **예전 짧은 글**이 그대로 나왔다.
#    「배포했는데 그대로인데?」의 진짜 이유가 이것이었다.
#    얼개를 고치면 이 숫자를 올린다.
GWAN_VER = 4          # 🛑 4 (2026-09-18): 유머 팩폭 3~4줄 미리보기까지 구조화해 받는다

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


def _gwan_veil_blocks(blocks: list, paid: bool) -> list:
    """복채 전에는 각 자리의 3~4줄 후킹만 보낸다. 🛑 본문은 서버에서 자른다."""
    if paid:
        return blocks or []
    out = []
    for b in blocks or []:
        out.append({"title": b.get("title", ""), "hook": b.get("hook", ""),
                    "hooking_preview": b.get("hooking_preview", ""),
                    "folds": [{"title": f.get("title", ""), "tag": f.get("tag", ""), "body": ""} for f in b.get("folds") or []]})
    return out


def _saju_veil_blocks(blocks: list) -> list:
    """사주 미리보기도 각 항목의 3~4줄 후킹만 보낸다. 🛑 본문은 서버에서 자른다."""
    out = []
    for b in blocks or []:
        out.append({"title": b.get("title", ""), "hook": b.get("hook", ""),
                    "hooking_preview": b.get("hooking_preview", ""),
                    "folds": [{"title": f.get("title", ""), "tag": f.get("tag", ""), "body": ""} for f in b.get("folds") or []],
                    "rx": {}, "todos": [], "marks": []})
    return out


def _gwan_veil(text: str, paid: bool) -> str:
    """미결제 응답에는 평문 본문을 싣지 않는다. 후킹은 `blocks`에만 있다."""
    if paid:
        return text
    return ""


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
                "blocks": _gwan_veil_blocks(prev.get("blocks") or [], paid),
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
        # 🛑 **글 길이를 앞단이 정해 보낸다** (2026-09-12). 안 보내면 260자로 떨어져
        #    39,800원짜리가 2,900원짜리 사주의 3분의 1 분량으로 나갔다.
        #    상한을 두는 것은 값이 이상하게 와도 원가가 튀지 않게 하려는 것이다.
        _chars = max(260, min(int(body.chars or 0) or 260, 2200))
        out = gwansang_ops.read_face(product, clean, name=(body.name or "").strip(),
                                     sections=body.sections or [], chars=_chars)
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
        saju_writer.save(product, shot, {"text": out["text"], "card": card, "blocks": out.get("blocks") or [],
                                         "kind": "gwansang", "ver": GWAN_VER})
    except Exception:                                 # noqa: BLE001
        pass                                          # 저장을 못 해도 글은 나가야 한다
    if paid and not free:
        _gwan_use(user["email"], pair, shot)
    # 🛑 사진은 여기서 끝이다. `clean` 은 응답에 담지 않는다
    return {"ok": True, "text": _gwan_veil(out["text"], paid), "paid": paid,
            "blocks": _gwan_veil_blocks(out.get("blocks") or [], paid),
            "tokens": out.get("tokens"), "card": card if paid else {},
            "left": max(0, GWAN_TRIES - len(_gwan_seen(user["email"], pair)))}


# ── 꿈 해몽 (2026-09-13 온해님 기획) ─────────────────────
# 상품 정본은 앞단 `dream.js`. 여기는 **쓰고, 세고, 잘라서** 준다.
# 🛑 꿈 스캔은 사주 미리보기와 **다른 칸**으로 센다 — 같이 세면 꿈 한 번 본 손님이
#    사주 맛보기를 잃는다. 미끼가 미끼를 잡아먹는다 (FREE_DAILY_CAP 과 같은 이유).

DREAM_DAILY_CAP = 5         # 꿈 스캔을 하루에 새로 뽑는 횟수. 한 번에 1원 안쪽
DREAM_PRODUCT = "dream_saju"
# 🛑 **값을 아직 안 정했다** (2026-09-13 온해님 「가격 정하지 말고 만들어 봐」).
#    정하기 전에는 누구도 복채로 못 연다 — 주인·무료 이용권만 끝까지 본다.
#    정하면 `lamps.PREMIUM_WON` 에 값을 넣고 이것을 True 로 바꾼다.
DREAM_PRICE_SET = False


class DreamScanBody(BaseModel):
    keywords: list[str] = []
    text: str = ""
    name: str = ""


class DreamReadBody(BaseModel):
    text: str = ""
    keywords: list[str] = []
    # 사주 값 — 생년월일은 앞단이 계산해서 **여덟 글자와 개수만** 보낸다 (사주 상품과 같다)
    saju: dict = {}
    pair: str = ""
    sections: list[str] = []
    name: str = ""
    # 스캔에서 매긴 등급. 같은 꿈이 스캔과 리포트에서 다른 등급으로 나오지 않게 넘긴다
    grade: str = ""


_DREAM_FIELDS = ("grade", "label", "title", "punch", "read", "tip")


@app.get("/api/dream/quota")
def dream_quota(authorization: str | None = Header(default=None)):
    """오늘 꿈 스캔을 몇 번 더 할 수 있나 (2026-09-13 온해님 「오늘 무료 스캔 남은 횟수」).

    🛑 화면에 숫자를 박아 두지 않는다. 다섯 번 다 쓴 손님에게 「5회」가 보이면 거짓말이다.
    """
    user = _token_user(authorization)
    if _is_free(user):
        return {"cap": DREAM_DAILY_CAP, "left": DREAM_DAILY_CAP, "unlimited": True}
    used = _preview_used(user["email"], kind="dream")
    return {"cap": DREAM_DAILY_CAP, "left": max(0, DREAM_DAILY_CAP - used), "unlimited": False}


# ── 반려동물 관상 「내가 왕이 될 냥인가?」 (2026-09-14 온해님 기획) ─────────────────
# 🛑 **무료로 연다** (2026-09-14 온해님 「일단 무료로 풀자 유입을 위해서」). 꿈 스캔처럼 로그인한 분께 **하루 몇 번**.
#    같은 사진은 저장해 둔 결과를 주고 횟수를 안 깎는다 — 다시 눌러 S 등급을 뽑는 걸 막는다.
# 🛑 **사진은 저장하지 않는다** (관상과 같다). 결과 글만 사진 해시로 남긴다.
PET_DAILY_CAP = 3
PET_VER = 3          # 🛑 3 (2026-09-14): 멀티 스피시즈·SS~B+ 등급·집사 시너지로 칸이 바뀌었다 (2: character_design)


class PetReadBody(BaseModel):
    shot: str = ""          # 앞단이 만든 사진 해시 (저장 열쇠)
    shots: list[str] = []   # base64 jpeg 한 장


@app.get("/api/pet/quota")
def pet_quota(authorization: str | None = Header(default=None)):
    """오늘 반려동물 관상을 몇 번 더 볼 수 있나. 🛑 화면에 숫자를 박지 않는다 — 서버가 센 값만 쓴다."""
    user = _token_user(authorization)
    if _is_free(user):
        return {"cap": PET_DAILY_CAP, "left": PET_DAILY_CAP, "unlimited": True}
    used = _preview_used(user["email"], kind="pet")
    return {"cap": PET_DAILY_CAP, "left": max(0, PET_DAILY_CAP - used), "unlimited": False}


@app.post("/api/pet/read")
def pet_read(body: PetReadBody, authorization: str | None = Header(default=None)):
    """반려동물 사진 한 장 → 관상 보고서 + 공유 카드 칸."""
    user = _token_user(authorization)
    shots = body.shots or []
    if len(shots) != 1:
        raise HTTPException(400, "사진을 한 장 올려 주세요.")
    try:
        clean = gwansang_ops.check_jpeg(shots[0])
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 🛑 저장 열쇠는 **서버가 받은 사진으로 다시 센다** (2026-09-14 전수 검사).
    #    앞단이 보낸 해시를 그대로 쓰면, 개 사진으로 본 결과를 다른 사진 해시에 저장한 뒤
    #    그 사진(동물 아닌 것)을 명예의 전당에 올릴 수 있었다 — `pets_share` 는 해시만 맞춰 본다
    shot = _shot_hash_of(clean)
    try:
        prev = saju_writer.load("pet_read", shot)
    except ValueError:
        prev = None
    # 🛑 스탯이 전부 0 인 저장본은 주지 않고 새로 본다 (2026-09-14 「관상 스탯 수치가 안 나와」)
    if prev and prev.get("ver") == PET_VER and prev.get("title") and any((prev.get("stats") or {}).values()):
        return {"ok": True, "again": True, **{k: v for k, v in prev.items() if k not in ("ver", "kind")}}
    if not saju_writer.ready():
        raise HTTPException(503, "지금은 무냥이가 못 봐요. 잠시 뒤에 다시 해 주세요.")
    if not _is_free(user):
        _preview_quota(user["email"], kind="pet", cap=PET_DAILY_CAP,
                       msg="오늘 반려동물 관상은 여기까지예요. 내일 0시부터 다시 열려요.")
    counted = not _is_free(user)
    try:
        out = pet_ops.read_pet(clean)
    except ValueError as e:
        if counted:
            _preview_refund(user["email"], "pet")
        raise HTTPException(400, str(e))
    except Exception as e:                            # noqa: BLE001
        print("[pet/read] 실패:", repr(e)[:300])
        if counted:
            _preview_refund(user["email"], "pet")
        raise HTTPException(502, "사진을 읽다가 막혔어요. 잠시 뒤 다시 해 주세요.")
    # 🛑 동물이 아니거나 흐린 사진은 **저장하지 않고** 그대로 알려 준다 — 다음 사진으로 다시 보게.
    #    횟수도 되돌린다 (사진을 잘못 고른 것으로 오늘 기회를 잃지 않게)
    if out.get("error_code") != "NONE":
        if counted:
            _preview_refund(user["email"], "pet")
        return {"ok": False, **out}
    try:
        saju_writer.save("pet_read", shot, {**out, "ver": PET_VER, "kind": "pet"})
    except Exception:                                 # noqa: BLE001
        pass
    return {"ok": True, **out}


# ── 반려동물 관상 명예의 전당 (2026-09-14 온해님 기획) ─────────────────────
# 저장·순위·좋아요 셈은 `modules/pet_hall.py`. 여기는 누가 무엇을 할 수 있는지만 가른다.
PET_VOTER_COOKIE = "rl_pet_voter"


class PetShareBody(BaseModel):
    shot: str = ""
    shots: list[str] = []   # 관상 볼 때 보낸 그 사진 한 장 (base64 jpeg)
    pet_name: str = ""
    agree: bool = False     # 🛑 명예의 전당에 사진이 공개된다는 데 동의했는가


def _shot_hash_of(b64: str) -> str:
    """앞단(`pet.js`)이 만드는 사진 해시와 같은 셈. 앞단은 data URL 전체를 SHA-256 해 앞 16바이트를 쓴다."""
    import hashlib as _hl
    return _hl.sha256(("data:image/jpeg;base64," + (b64 or "")).encode("utf-8")).hexdigest()[:32]


@app.post("/api/pets/share")
def pets_share(body: PetShareBody, authorization: str | None = Header(default=None)):
    """관상 결과 카드를 명예의 전당에 올린다 (손님이 동의했을 때만)."""
    user = _token_user(authorization)
    if not body.agree:
        raise HTTPException(400, "명예의 전당에 사진이 보인다는 데 동의해 주셔야 올릴 수 있어요.")
    shots = body.shots or []
    if len(shots) != 1:
        raise HTTPException(400, "사진을 한 장 올려 주세요.")
    try:
        clean = gwansang_ops.check_jpeg(shots[0])
    except ValueError as e:
        raise HTTPException(400, str(e))
    shot = (body.shot or "").strip()
    # 🛑 **관상을 본 바로 그 사진인지** 맞춰 본다. 결과 없이 아무 사진이나 올리는 것을 막는다
    if not shot or _shot_hash_of(clean) != shot:
        raise HTTPException(400, "관상을 본 사진과 달라요. 관상 결과 화면에서 올려 주세요.")
    try:
        prev = saju_writer.load("pet_read", shot)
    except ValueError:
        prev = None
    if not prev or not prev.get("title"):
        raise HTTPException(404, "이 사진의 관상 결과를 못 찾았어요. 관상을 먼저 봐 주세요.")
    import base64 as _b64
    try:
        jpeg = _b64.b64decode(clean)
    except Exception:                                 # noqa: BLE001
        raise HTTPException(400, "사진을 읽지 못했어요.")
    try:
        row = pet_hall_ops.add(owner=user["email"], shot=shot, pet_name=body.pet_name, jpeg=jpeg, result=prev,
                               owner_label=_mask_name(user.get("name") or "", user.get("email") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(429, str(e))
    return {"ok": True, "item": row}


class PetCommentBody(BaseModel):
    nickname: str = ""
    content: str = ""
    password: str = ""      # 적으면 다른 기기에서도 이 비밀번호로 지울 수 있다


class PetCommentDeleteBody(BaseModel):
    password: str = ""


def _pet_voter(voter: str | None, response: Response) -> str:
    """이 브라우저를 가리키는 표. 없으면 만들어 쿠키로 준다(좋아요·댓글이 같이 쓴다)."""
    import uuid as _uuid
    if not voter or len(voter) > 64:
        voter = _uuid.uuid4().hex
        # 🛑 1년. 지우면 다시 누를 수 있지만 IP 칸이 한 번 더 막는다
        response.set_cookie(PET_VOTER_COOKIE, voter, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax", secure=True)
    return voter


def _pet_id_ok(pid: str) -> bool:
    import re as _re
    return bool(_re.fullmatch(r"[0-9a-f-]{36}", pid or ""))


@app.post("/api/pets/{pid}/like")
def pets_like(pid: str, request: Request, response: Response,
              voter: str | None = Cookie(default=None, alias=PET_VOTER_COOKIE)):
    """좋아요(투표) 1. 🛑 로그인 없이 누를 수 있다 — 퍼진 카드에서 들어온 사람도 누르게.
    중복은 브라우저 쿠키로 막고, 같은 IP 는 한 아이에게 5번까지만(`pet_hall.IP_LIKE_CAP`)."""
    voter = _pet_voter(voter, response)
    try:
        return pet_hall_ops.like(pid, voter=voter, ip=_client_ip(request))
    except KeyError:
        raise HTTPException(404, "명예의 전당에서 내려간 아이예요.")


@app.get("/api/pets/hall-of-fame")
def pets_hall(month: str | None = Query(default=None), limit: int = Query(default=30),
              sort: str = Query(default="likes")):
    """목록. `sort=likes`(실시간 랭킹순) · `latest`(최신순). 1위는 「이달의 관상왕」(is_monthly_winner). 로그인 없이 볼 수 있다."""
    if month and not (len(month) == 7 and month[4] == "-" and month.replace("-", "").isdigit()):
        raise HTTPException(400, "달은 2026-09 처럼 적어 주세요.")
    if sort not in {"likes", "latest"}:
        raise HTTPException(400, "정렬은 likes 또는 latest 예요.")
    # 갤러리 상세 조각이 없던 옛 줄을 관상 저장본으로 한 번 채운다 (2026-09-14 이전에 올린 것)
    pet_hall_ops.fill_missing(lambda shot: saju_writer.load("pet_read", shot))
    return pet_hall_ops.hall(month, limit, sort)


@app.get("/api/pets/{pid}/comments")
def pets_comments(pid: str, authorization: str | None = Header(default=None),
                  voter: str | None = Cookie(default=None, alias=PET_VOTER_COOKIE)):
    """댓글 목록 (오래된 것부터). `mine` 이면 이 브라우저·계정이 쓴 것이라 지우기 단추를 보인다."""
    if not _pet_id_ok(pid) or not pet_hall_ops.exists(pid):
        raise HTTPException(404, "명예의 전당에서 내려간 아이예요.")
    user = _maybe_user(authorization)
    return {"items": pet_hall_ops.comments(pid, voter=voter or "", user=(user or {}).get("email") or ""),
            "admin": bool(user and _is_owner(user))}


@app.post("/api/pets/{pid}/comments")
def pets_comment_add(pid: str, body: PetCommentBody, request: Request, response: Response,
                     authorization: str | None = Header(default=None),
                     voter: str | None = Cookie(default=None, alias=PET_VOTER_COOKIE)):
    """댓글 쓰기. 🛑 로그인 없이(기획서). 링크 금지 · IP 하루 30개 · 10초에 1개 (`pet_hall`)."""
    if not _pet_id_ok(pid):
        raise HTTPException(404, "명예의 전당에서 내려간 아이예요.")
    voter = _pet_voter(voter, response)
    user = _maybe_user(authorization)
    try:
        return {"ok": True, **pet_hall_ops.add_comment(pid, nickname=body.nickname, content=body.content,
                                                       password=body.password, voter=voter, ip=_client_ip(request),
                                                       user=(user or {}).get("email") or "")}
    except KeyError:
        raise HTTPException(404, "명예의 전당에서 내려간 아이예요.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(429, str(e))


@app.post("/api/pets/{pid}/comments/{cid}/delete")
def pets_comment_delete(pid: str, cid: str, body: PetCommentDeleteBody, request: Request,
                        authorization: str | None = Header(default=None),
                        voter: str | None = Cookie(default=None, alias=PET_VOTER_COOKIE)):
    """댓글 지우기(숨김). 쓴 브라우저 · 같은 계정 · 비밀번호 · 관리자."""
    if not _pet_id_ok(pid):
        raise HTTPException(404, "없는 댓글이에요.")
    # 🛑 비밀번호를 대입해 남의 댓글을 지우지 못하게 — 댓글 하나에 10분 10번, 한 곳에서 10분 30번 (2026-09-14 전수 검사)
    if body.password:
        _rate_limit_or_429("pet-cdel:%s" % cid, limit=10, window_sec=600, what="댓글 지우기")
        _rate_limit_or_429("pet-cdel-ip:%s" % _client_ip(request), limit=30, window_sec=600, what="댓글 지우기")
    user = _maybe_user(authorization)
    try:
        n = pet_hall_ops.delete_comment(pid, cid, voter=voter or "", user=(user or {}).get("email") or "",
                                        password=body.password, admin=bool(user and _is_owner(user)))
    except KeyError:
        raise HTTPException(404, "없는 댓글이에요.")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"ok": True, "comment_count": n}


@app.get("/hall-of-fame")
@app.get("/pets/hall-of-fame")
def hall_of_fame_page():
    """명예의 전당 주소. 🛑 이 사이트는 화면을 **해시로** 옮긴다(CLAUDE.md) — 주소로 들어오면 `#hall` 로 보낸다."""
    return RedirectResponse("/#hall", status_code=302)


@app.get("/api/pets/{pid}/image")
def pets_image(pid: str):
    """명예의 전당 사진. 🛑 숨긴 아이는 안 준다."""
    import re as _re
    if not _re.fullmatch(r"[0-9a-f-]{36}", pid or "") or not pet_hall_ops.exists(pid):
        raise HTTPException(404, "없는 사진이에요.")
    f = pet_hall_ops.image_path(pid)
    if not f.exists():
        raise HTTPException(404, "없는 사진이에요.")
    return FileResponse(str(f), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.delete("/api/pets/{pid}")
def pets_hide(pid: str, authorization: str | None = Header(default=None)):
    """주인이 명예의 전당에서 내린다 (지우지 않고 숨김)."""
    user = _token_user(authorization)
    if not _is_owner(user):
        raise HTTPException(403, "주인만 내릴 수 있어요.")
    return {"ok": pet_hall_ops.hide(pid)}


@app.post("/api/dream/scan")
def dream_scan(body: DreamScanBody, authorization: str | None = Header(default=None)):
    """꿈 스캔 — 무료. 등급·별명·한 줄 팩폭·짧은 풀이."""
    user = _token_user(authorization)
    try:
        kw, text = dream_ops.clean_input(body.keywords, body.text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    name = (body.name or "").strip()[:20]
    key = dream_ops.key_of("scan", ",".join(sorted(kw)), text, name)
    # 🛑 **같은 꿈은 같은 등급** — 저장분을 준다. 한도도 안 깎는다.
    #    안 그러면 S 가 나올 때까지 다시 누르고, 등급이 아무 뜻이 없어진다
    try:
        prev = saju_writer.load("dream_scan", key)
    except ValueError:
        prev = None
    if prev and prev.get("ver") == dream_ops.VER and prev.get("grade"):
        return {"ok": True, "again": True, **{k: prev.get(k, "") for k in _DREAM_FIELDS}}
    if not saju_writer.ready():
        raise HTTPException(503, "지금은 무냥이가 못 읽어요. 잠시 뒤에 다시 해 주세요.")
    if not _is_free(user):
        _preview_quota(user["email"], kind="dream", cap=DREAM_DAILY_CAP,
                       msg="오늘 꿈 스캔은 여기까지예요. 내일 0시부터 다시 열려요.")
    try:
        out = dream_ops.scan(kw, text, name=name)
    except Exception as e:                            # noqa: BLE001
        print("[dream/scan] 실패:", repr(e)[:300])
        # 🛑 서버가 못 읽은 것은 손님 탓이 아니다 — 센 한 번을 되돌린다 (2026-09-14 전수 검사 · 반려동물 관상과 같게)
        if not _is_free(user):
            _preview_refund(user["email"], "dream")
        raise HTTPException(502, "꿈을 읽다가 막혔어요. 잠시 뒤 다시 해 주세요.")
    try:
        saju_writer.save("dream_scan", key, {**out, "ver": dream_ops.VER, "kind": "dream"})
    except Exception:                                 # noqa: BLE001
        pass                                          # 저장을 못 해도 결과는 나가야 한다
    return {"ok": True, **{k: out[k] for k in _DREAM_FIELDS}}


@app.post("/api/dream/read")
def dream_read(body: DreamReadBody, authorization: str | None = Header(default=None)):
    """꿈 사주 리포트. 복채 전에는 첫 자리만 준다."""
    user = _token_user(authorization)
    pair = (body.pair or "").strip()
    if not pair or not body.saju:
        raise HTTPException(400, "사주 값이 필요합니다.")
    try:
        kw, text = dream_ops.clean_input(body.keywords, body.text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if len(text) < 10:
        raise HTTPException(400, "꿈 이야기를 한두 줄만 더 적어 주세요.")
    free = _is_free(user)
    paid = free or (DREAM_PRICE_SET and lamps_ops.owns(user["email"], DREAM_PRODUCT, pair))
    key = dream_ops.key_of("read", pair, ",".join(sorted(kw)), text, (body.grade or "").upper())
    try:
        prev = saju_writer.load(DREAM_PRODUCT, key)
    except ValueError:
        prev = None
    if prev and prev.get("ver") == dream_ops.REPORT_VER and prev.get("text"):
        g = prev.get("grade", "B")
        return {"ok": True, "again": True, "paid": paid, "priceSet": DREAM_PRICE_SET,
                "grade": g, "label": dream_ops.GRADES.get(g, ""),
                "text": dream_ops.veil(prev["text"], paid),
                "blocks": dream_ops.veil_blocks(prev.get("blocks"), paid)}
    if not saju_writer.ready():
        raise HTTPException(503, "지금은 무냥이가 못 읽어요. 잠시 뒤에 다시 해 주세요.")
    # 🛑 **복채 전 맛보기는 사주 미리보기와 같은 한도**를 쓴다 — 리포트 한 편 원가가 나가는 자리다
    if not paid:
        _preview_quota(user["email"])
    try:
        out = dream_ops.read(text, body.saju, body.sections, keywords=kw,
                             name=(body.name or "").strip(), grade=body.grade or "")
    except ValueError as e:
        if not paid:
            _preview_refund(user["email"], "preview")
        raise HTTPException(400, str(e))
    except Exception as e:                            # noqa: BLE001
        print("[dream/read] 실패:", repr(e)[:300])
        if not paid:
            _preview_refund(user["email"], "preview")
        raise HTTPException(502, "꿈을 읽다가 막혔어요. 잠시 뒤 다시 해 주세요.")
    try:
        saju_writer.save(DREAM_PRODUCT, key, {"text": out["text"], "grade": out["grade"],
                                              "blocks": out.get("blocks") or [],
                                              "ver": dream_ops.REPORT_VER, "kind": "dream"})
    except Exception:                                 # noqa: BLE001
        pass
    return {"ok": True, "paid": paid, "priceSet": DREAM_PRICE_SET,
            "grade": out["grade"], "label": dream_ops.GRADES[out["grade"]],
            "text": dream_ops.veil(out["text"], paid),
            "blocks": dream_ops.veil_blocks(out.get("blocks"), paid)}


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
    # 🛑 **프리미엄만 결제 전용이다** (2026-09-13 온해님). 전에는 `won_of()` 로 갈랐는데
    #    그 표(`PREMIUM_WON`)에 **일반 상품도 전부 들어 있어서** 결국 모든 상품이
    #    결제 전용이 됐다. 가입 선물 등불 300개를 쥐고도 결제창만 보던 까닭이다.
    prod = body.product.strip()
    if prod in lamps_ops.PREMIUM_ONLY:
        if lamps_ops.owns(user["email"], prod, body.pair.strip()):
            return {"ok": True, "spent": 0, "balance": lamps_ops.balance(user["email"]), "reopened": True}
        raise HTTPException(402, "이 상품은 등불이 아니라 결제로 열어요.")
    try:
        return lamps_ops.spend(user["email"], body.product.strip(), body.pair.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── 결과지 문장 — 모델이 매번 새로 쓴다 ──────────────────────
# 왜: 코드에 박아 둔 문장은 같은 십성인 사람에게 늘 같은 글을 준다.
# 계산은 프론트가 끝내서 보내고, 여기서는 그 값을 글로 옮기기만 시킨다.

# 🛑 **미리보기도 전 항목을 무냥이가 쓴다** (2026-09-13 온해님 「모든 상품에 결제
#    안 하고 미리 보는 해설에도 LLM 을 붙여」). 0 이면 「전부」다.
#    그전에는 1 이라 **첫 자리만 무냥이 글이고 나머지는 계산 문장**이 나갔다 —
#    손님이 보는 미리보기 대부분이 「일지(곁을 내주는 자리)는 술 이고」 같은 딱딱한
#    문장이었다. 2026-09-07 에 「미리보기도 무냥이가 쓴 문장으로」라고 하셨는데
#    그때 첫 자리만 하고 끝냈다.
# 🛑 **원가가 는다.** 미리보기 한 번이 리포트 한 편과 같아진다(23원).
#    막는 것은 `PREVIEW_DAILY_CAP`(하루 3번) 하나다.
PREVIEW_SECTIONS = 0        # 0 = 전부. 복채 전에 무냥이 글로 보여 주는 항목 수
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


import threading as _threading
# 🛑 하루 한도 파일은 **잠그고, 임시 파일에 쓴 뒤 바꿔 끼운다** (2026-09-14 전수 검사).
#    동시에 여러 요청이 오면 모두 0 을 읽고 한도를 넘어 LLM 을 불렀고, 쓰는 도중에 읽은 요청이
#    깨진 파일을 {} 로 보고 그대로 덮어써 **그날 모든 손님의 횟수가 지워질 수 있었다**
_QUOTA_LOCK = _threading.Lock()


def _quota_write(f, data: dict) -> None:
    import json as _j
    tmp = f.with_suffix(".tmp")
    tmp.write_text(_j.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def _quota_key(email: str, kind: str) -> str:
    """세는 칸 이름. 🛑 미리보기는 **옛 이름 그대로** 둔다 — 오늘 센 것이 날아간다."""
    return email if kind == "preview" else "%s:%s" % (kind, email)


def _preview_used(email: str, kind: str = "preview") -> int:
    """오늘 이 계정이 몇 번 뽑았나."""
    from pathlib import Path as _P
    import json as _j
    import datetime as _dt
    f = _P(DATA_DIR) / "saju_preview_count.json"
    # 🛑 **한국 날짜다** (2026-09-13). `date.today()` 는 서버 시간(UTC)이라
    #    한국 아침 9시 전에는 어제로 센다 — 하루 한도가 제때 안 풀린다.
    today = (_dt.datetime.now(_dt.timezone.utc)
             + _dt.timedelta(hours=9)).date().isoformat()
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
    # 🛑 **한국 날짜다** (2026-09-13). `date.today()` 는 서버 시간(UTC)이라
    #    한국 아침 9시 전에는 어제로 센다 — 하루 한도가 제때 안 풀린다.
    today = (_dt.datetime.now(_dt.timezone.utc)
             + _dt.timedelta(hours=9)).date().isoformat()
    key = _quota_key(email, kind)
    with _QUOTA_LOCK:
        try:
            data = _j.loads(f.read_text(encoding="utf-8"))
        except OSError:
            data = {}
        except ValueError:
            # 🛑 깨진 파일을 빈 것으로 덮어쓰면 모두의 횟수가 지워진다 — 옆에 남겨 두고 새로 센다
            try:
                f.replace(f.with_suffix(".broken"))
            except OSError:
                pass
            data = {}
        if data.get("day") != today:
            data = {"day": today, "by": {}}
        n = int(data["by"].get(key, 0))
        if n >= (cap or PREVIEW_DAILY_CAP):
            raise HTTPException(429, msg or "오늘 무료로 볼 수 있는 사주를 다 보셨어요. 내일 0시부터 다시 열려요.")
        data["by"][key] = n + 1
        try:
            _quota_write(f, data)
        except OSError:
            pass


def _preview_refund(email: str, kind: str) -> None:
    """방금 센 한 번을 되돌린다 — 손님 탓이 아닌데 횟수만 깎이지 않게 (2026-09-14 반려동물 관상).

    동물이 아닌 사진·흐린 사진·서버가 못 읽은 경우에 쓴다. 🛑 성공한 결과에는 쓰지 않는다.
    """
    from pathlib import Path as _P
    import json as _j
    f = _P(DATA_DIR) / "saju_preview_count.json"
    with _QUOTA_LOCK:
        try:
            data = _j.loads(f.read_text(encoding="utf-8"))
            key = _quota_key(email, kind)
            n = int((data.get("by") or {}).get(key, 0))
            if n > 0:
                data["by"][key] = n - 1
                _quota_write(f, data)
        except (OSError, ValueError, AttributeError):
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


# ── 운영자 피드백 ─────────────────────────────────────────
# 로그인하지 않은 손님도 오류를 알려야 하므로 접수는 공개한다. 대신 IP별로
# 한 시간에 네 번만 받으며, IP 주소 자체는 파일에 남기지 않는다.

class FeedbackBody(BaseModel):
    message: str
    page: str = ""


class FeedbackReadBody(BaseModel):
    ids: list[str] | None = None


@app.post("/api/feedback")
def feedback_submit(
    body: FeedbackBody,
    request: Request,
    authorization: str | None = Header(default=None),
):
    message = (body.message or "").strip()
    if len(message) < 2:
        raise HTTPException(400, "불편했던 내용을 두 글자 이상 적어 주세요.")
    if len(message) > 1200:
        raise HTTPException(400, "내용은 1,200자까지 적을 수 있어요.")
    page = (body.page or "").strip()[:300]
    _rate_limit_or_429(
        f"feedback:{_client_ip(request)}", limit=4, window_sec=3600, what="피드백 접수"
    )
    reporter = ""
    if authorization:
        try:
            reporter = (_token_user(authorization).get("email") or "").strip()
        except HTTPException:
            # 로그인 토큰이 오래됐어도 피드백 접수 자체는 막지 않는다.
            pass
    try:
        row = feedback_ops.submit(message=message, page=page, reporter=reporter)
    except feedback_ops.FeedbackStoreError:
        log.exception("feedback store is unavailable")
        raise HTTPException(503, "피드백 보관함을 잠시 열 수 없어요. 조금 뒤 다시 보내 주세요.")
    return {"ok": True, "id": row["id"]}


@app.get("/api/admin/feedback")
def admin_feedback(
    authorization: str | None = Header(default=None), limit: int = 100
):
    _require_admin(authorization)
    try:
        return feedback_ops.listing(limit=limit)
    except feedback_ops.FeedbackStoreError:
        log.exception("feedback store is unavailable")
        raise HTTPException(503, "피드백 보관함을 읽을 수 없어요.")


@app.post("/api/admin/feedback/read")
def admin_feedback_read(
    body: FeedbackReadBody, authorization: str | None = Header(default=None)
):
    _require_admin(authorization)
    try:
        return {"ok": True, "read": feedback_ops.mark_read(body.ids)}
    except feedback_ops.FeedbackStoreError:
        log.exception("feedback store is unavailable")
        raise HTTPException(503, "피드백 보관함을 읽을 수 없어요.")


@app.delete("/api/admin/feedback/{feedback_id}")
def admin_feedback_delete(
    feedback_id: str, authorization: str | None = Header(default=None)
):
    """읽음 처리한 피드백 한 건만 지운다. 전체 삭제 경로는 만들지 않는다."""
    _require_admin(authorization)
    try:
        deleted = feedback_ops.remove(feedback_id)
        if deleted is None:
            raise HTTPException(404, "이미 지워졌거나 찾을 수 없는 피드백이에요.")
        if not deleted:
            raise HTTPException(400, "먼저 읽음 처리한 뒤 지울 수 있어요.")
        return {"ok": True}
    except feedback_ops.FeedbackStoreError:
        log.exception("feedback store is unavailable")
        raise HTTPException(503, "피드백 보관함을 읽을 수 없어요.")


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
        # 🛑 0 이면 **전부** 쓴다 (2026-09-13). 자르면 안 된다
        if PREVIEW_SECTIONS:
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
            # 🛑 제미나이 원문 오류를 손님 화면에 내보내지 않는다 (2026-09-14 전수 검사) — 서버 기록에만 남긴다
            print("[saju/write] 실패:", repr(e)[:300])
            raise HTTPException(502, "글을 받아 오지 못했어요. 잠시 뒤 다시 해 주세요.")
        saju_writer.merge(product, pair, res["blocks"])
        for b in res["blocks"]:
            if b.get("text"):
                done[b["title"]] = b

    left = PREVIEW_DAILY_CAP if _is_free(user) else max(0, PREVIEW_DAILY_CAP - _preview_used(user["email"]))
    # 🛑🛑 **`hook`·`hooking_preview`·`mutter` 를 같이 보낸다**.
    #    여기서 `text` 만 담고 있었다. 그래서 LLM 이 쓴 **항목 제목과 혼잣말이
    #    전 상품에서 한 번도 화면에 안 나갔다** — 앞단은 `b.hook`·`b.mutter` 를
    #    받을 준비가 되어 있었는데 서버가 안 보냈다. 화면에는 표에서 고른 옛
    #    혼잣말과 본래 제목이 그대로 나왔고, 오류가 아니라서 아무도 못 봤다.
    #    저장은 처음부터 되고 있었으므로 **이미 써 둔 글도 이 줄 하나로 살아난다.**
    blocks = [{"title": s,
               "text": done.get(s, {}).get("text", ""),
               "hook": done.get(s, {}).get("hook", ""),
               "hooking_preview": done.get(s, {}).get("hooking_preview", ""),
               "mutter": done.get(s, {}).get("mutter", ""),
               # 🛑 카드 칸 (2026-09-14 · saju_writer.SECTION_SCHEMA). 옛 글엔 없어서 빈 값이 간다
               **{k: done.get(s, {}).get(k) or ([] if k in ("folds", "todos", "marks") else ({} if k == "rx" else ""))
                  for k in ("lead", "scene_line", "folds", "rx", "todos", "marks")}} for s in want]
    return {"ok": True, "paid": paid, "ownerSkip": owner_skip, "left": left,
            "blocks": blocks if paid else _saju_veil_blocks(blocks),
            "more": bool((not paid) and PREVIEW_SECTIONS
                         and len(body.sections or []) > PREVIEW_SECTIONS)}


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

    # 🛑 **옛 방식으로 쓴 요약은 다시 만든다** (2026-09-11). 재료를 앞 두 자리 +
    #    마지막만 주던 때에 쓴 글은 **물음의 답이 아니다** — 답이 든 자리를 LLM 이
    #    본 적이 없다. 저장된 것을 그대로 내보내면 그 카드가 계속 돌아다닌다.
    if data.get("summary") and int(data.get("summary_ver") or 0) >= saju_writer.SUM_VER:
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
        data["summary_ver"] = saju_writer.SUM_VER
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


@app.get("/blog/ai-{publication_id}.html")
def marketing_blog_page(publication_id: int):
    page = BlogPublisher(_marketing_repo(), WEB, SITE_ORIGIN).render(f"ai-{publication_id}")
    if page is None:
        raise HTTPException(404, "Not Found")
    return HTMLResponse(page, headers={"Cache-Control":"no-store"})


@app.get("/blog/")
@app.get("/blog/index.html")
def marketing_blog_index():
    return HTMLResponse(BlogPublisher(_marketing_repo(), WEB, SITE_ORIGIN).render_index(), headers={"Cache-Control":"no-store"})


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
