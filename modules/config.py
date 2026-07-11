"""
앱 전역 설정 · 브랜딩 · 요금제 상수
환경변수(.env / Streamlit secrets)를 우선 로드합니다.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트
ROOT_DIR = Path(__file__).resolve().parent.parent


def _resolve_data_dir() -> Path:
    """
    쓰기 가능한 data 디렉터리.
    우선순위:
      1) DATA_DIR 환경변수 (Railway Volume 마운트 경로 권장: /data)
      2) RAILWAY_VOLUME_MOUNT_PATH
      3) 프로젝트 ./data → ~/.roadlog/data → /tmp
    """
    env_paths: list[Path] = []
    for key in ("DATA_DIR", "RAILWAY_VOLUME_MOUNT_PATH"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            env_paths.append(Path(raw))
    candidates = env_paths + [
        ROOT_DIR / "data",
        Path.home() / ".roadlog" / "data",
        Path("/tmp") / "roadlog" / "data",
    ]
    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return d
        except Exception:
            continue
    d = ROOT_DIR / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


# .env 를 먼저 로드한 뒤 DATA_DIR 을 결정 (로컬·배포 공통)
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = _resolve_data_dir()


def _clean_secret_value(val: object) -> str:
    """Secrets/환경값 정리 — 따옴표·공백 제거."""
    if val is None:
        return ""
    s = str(val).strip()
    # TOML/복사 실수로 감싼 따옴표 제거
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s


def _streamlit_secrets_map() -> dict:
    """st.secrets 를 dict 로 평탄화."""
    try:
        import streamlit as st

        sec = getattr(st, "secrets", None)
        if sec is None:
            return {}
        if hasattr(sec, "to_dict"):
            try:
                return dict(sec.to_dict())  # type: ignore[attr-defined]
            except Exception:
                pass
        out: dict = {}
        # 키 순회 시도
        try:
            for k in sec:  # type: ignore[attr-defined]
                try:
                    out[str(k)] = sec[k]
                except Exception:
                    pass
        except Exception:
            pass
        # 흔한 관리자 키 직접 조회
        for k in (
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD",
            "ADMIN_EMAIL",
            "APP_SECRET",
            "OPENAI_API_KEY",
        ):
            if k in out:
                continue
            try:
                out[k] = sec[k]
            except Exception:
                pass
        return out
    except Exception:
        return {}


def _get_secret(key: str, default: str = "") -> str:
    """
    환경변수 → Streamlit secrets 순으로 값을 조회합니다.
    Streamlit Cloud 는 Secrets 가 런타임에만 안정적으로 열리므로,
    관리자 인증 등에서는 이 함수를 호출 시점에 다시 읽으세요.
    """
    # 1) 환경변수
    val = _clean_secret_value(os.getenv(key, ""))
    if val:
        return val

    # 2) Streamlit secrets
    smap = _streamlit_secrets_map()
    if key in smap:
        v = _clean_secret_value(smap[key])
        if v:
            return v
    # 대소문자 무시
    for k, v in smap.items():
        if str(k).upper() == key.upper():
            vv = _clean_secret_value(v)
            if vv:
                return vv
    # 중첩 [admin] username / password
    admin_sec = smap.get("admin") or smap.get("ADMIN")
    if isinstance(admin_sec, dict) and key.upper().startswith("ADMIN_"):
        sub = key.split("_", 1)[-1].lower()  # username / password / email
        for sk, sv in admin_sec.items():
            if str(sk).lower() == sub:
                vv = _clean_secret_value(sv)
                if vv:
                    return vv

    return default


# 관리자 계정은 반드시 환경변수 / Streamlit Secrets 로만 주입합니다.
# (소스에 실계정·실비밀번호를 두지 않음 — 정식 런칭 보안 정책)


def get_admin_credentials() -> tuple[str, str, str]:
    """
    관리자 (username, password, email) — 항상 최신 secrets/env 를 읽음.
    우선순위: 환경변수 → Streamlit Secrets.
    미설정 시 빈 비밀번호 → 관리자 로그인 불가.
    """
    username = (_get_secret("ADMIN_USERNAME", "") or "").strip()
    password = _get_secret("ADMIN_PASSWORD", "")
    email = (_get_secret("ADMIN_EMAIL", "") or "").strip().lower()
    if not email and username:
        email = f"{username}@roadlog.local"
    return username, password, email


def admin_secrets_status() -> dict:
    """로그인 화면 안내용 — 비밀번호는 노출하지 않음."""
    u, p, e = get_admin_credentials()
    from_env = bool(os.getenv("ADMIN_USERNAME") or os.getenv("ADMIN_PASSWORD"))
    smap = _streamlit_secrets_map()
    from_secrets = any(
        k.upper() in {str(x).upper() for x in smap.keys()}
        for k in ("ADMIN_USERNAME", "ADMIN_PASSWORD")
    )
    source = (
        "env"
        if from_env
        else ("streamlit_secrets" if from_secrets else "unset")
    )
    return {
        "username": u or "(unset)",
        "email": e,
        "password_set": bool(p),
        "password_len": len(p) if p else 0,
        "source": source,
        "is_default": False,
        "configured": bool(u and p),
    }


# ── 브랜딩 ──────────────────────────────────────────────
APP_TITLE = "로드로그"
APP_SHORT = "ROADLOG"
APP_TAGLINE = "AI 운행일지 · 회사 제출용"
APP_FULL = f"{APP_TITLE} · RoadLog"
STUDIO_NAME = "코어랩스"
STUDIO_NAME_EN = "CoreLabs"
CONTACT_EMAIL = _get_secret("CONTACT_EMAIL", "corelabs.studio@gmail.com")
CONTACT_FORM_URL = _get_secret(
    "CONTACT_FORM_URL",
    "https://docs.google.com/forms/d/e/1FAIpQLScl9ZJD_crv1d6JPDzdNaYTDzUQXKkLNx_X6pmyEwsg_1DnGg/viewform?usp=sf_link",
)
# 푸터·사업자 고지 (비우면 UI에서 해당 줄 숨김)
BUSINESS_NAME = _get_secret("BUSINESS_NAME", STUDIO_NAME)
BUSINESS_OWNER = _get_secret("BUSINESS_OWNER", "")
BUSINESS_REG_NO = _get_secret("BUSINESS_REG_NO", "")
BUSINESS_ADDRESS = _get_secret("BUSINESS_ADDRESS", "")
MAIL_ORDER_REG_NO = _get_secret("MAIL_ORDER_REG_NO", "")

# 색상 팔레트
COLORS = {
    "navy": "#111827",
    "navy_light": "#1F2937",
    "teal": "#0D9488",
    "teal_dark": "#0F766E",
    "teal_soft": "#CCFBF1",
    "white": "#FFFFFF",
    "bg": "#F3F4F6",
    "bg_soft": "#E5E7EB",
    "card": "#FFFFFF",
    "text": "#111827",
    "muted": "#6B7280",
    "muted_light": "#9CA3AF",
    "border": "#E5E7EB",
    "border_strong": "#D1D5DB",
    "danger": "#DC2626",
    "success": "#059669",
    "warning": "#D97706",
}

# ── 요금제 (초기 런칭가 — 사용자 확보 후 단계적 인상) ──
FREE_MONTHLY_LIMIT = 15
PRO_PRICE_KRW = 2900
ENTERPRISE_PRICE_KRW = 19900
ENTERPRISE_BASE_SEATS = 5
ENTERPRISE_SEAT_PRICE_KRW = 2000
PRO_PAYMENT_URL = _get_secret("PRO_PAYMENT_URL", "https://your-payment-link.example.com")
ENTERPRISE_PAYMENT_URL = _get_secret(
    "ENTERPRISE_PAYMENT_URL",
    _get_secret("PRO_PAYMENT_URL", "https://your-payment-link.example.com"),
)
# 결제 없이 /api/billing/upgrade 로 plan 변경 허용 여부 (로컬 데모 전용)
# 운영/공개 배포에서는 반드시 false 유지. 관리자 화면의 수동 플랜 변경은 별도.
ALLOW_DEMO_BILLING_UPGRADE = _get_secret("ALLOW_DEMO_BILLING_UPGRADE", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# ── 실행 환경 ──────────────────────────────────────────
# development | production  (운영 공개 시 production)
APP_ENV = (_get_secret("APP_ENV", "development") or "development").strip().lower()

# hybrid (기본) | free | paid
# - hybrid: OpenAI 키가 있으면 호출(사용량 과금), 없거나 한도 초과 시 스마트 초안
# - free: LLM 호출 안 함 (완전 비용 0 실험용)
# - paid: LLM 필수에 가깝게 취급 (런칭 체크·경고 강화)
_COST_RAW = (_get_secret("COST_MODE", "hybrid") or "hybrid").strip().lower()
if _COST_RAW in {"paid", "full", "pro"}:
    COST_MODE = "paid"
elif _COST_RAW in {"free", "zero", "offline"}:
    COST_MODE = "free"
else:
    COST_MODE = "hybrid"


def is_free_cost_mode() -> bool:
    """완전 무료 실험 모드 (LLM API 호출 자체 차단)."""
    return COST_MODE == "free"


def is_hybrid_cost_mode() -> bool:
    """키가 있으면 AI 사용, 없으면/실패 시 초안 (권장 기본)."""
    return COST_MODE == "hybrid"


# CORS: 쉼표 구분 도메인. 운영은 실제 사이트만. 예: https://roadlog.example.com
ALLOWED_ORIGINS = _get_secret("ALLOWED_ORIGINS", "*")

# ── 인증 / 관리자 ──────────────────────────────────────
# 모듈 import 시점 값 (로그인 시에는 get_admin_credentials() 사용 권장)
_admin_u, _admin_p, _admin_e = get_admin_credentials()
ADMIN_USERNAME = _admin_u
ADMIN_PASSWORD = _admin_p
ADMIN_EMAIL = _admin_e
APP_SECRET = _get_secret("APP_SECRET", "roadlog-dev-secret-change-me")
# 회원가입 최소 비밀번호 길이 (정식 런칭)
MIN_PASSWORD_LENGTH = 8

# 알려진 약한/플레이스홀더 값 (프로덕션 차단·경고용)
_WEAK_APP_SECRETS = {
    "",
    "change-me-to-a-long-random-string",
    "roadlog-v2-secret-change-me",
    "roadlog-dev-secret-change-me",
    "secret",
    "changeme",
}
_WEAK_ADMIN_PASSWORDS = {
    "",
    "admin",
    "admin123",
    "password",
    "1234",
    "123456",
}


def is_production() -> bool:
    return APP_ENV in {"production", "prod", "live"}


def cors_allow_origins() -> list[str]:
    """ALLOWED_ORIGINS 파싱. 빈 값이면 *."""
    raw = (ALLOWED_ORIGINS or "*").strip()
    if not raw or raw == "*":
        return ["*"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or ["*"]


def security_issues() -> list[dict[str, str]]:
    """
    배포 보안 이슈 목록.
    level: critical | warn | info
    """
    issues: list[dict[str, str]] = []

    weak_secret = APP_SECRET in _WEAK_APP_SECRETS or len(APP_SECRET) < 16
    if weak_secret:
        issues.append(
            {
                "level": "critical" if is_production() else "warn",
                "code": "weak_app_secret",
                "message": "APP_SECRET 이 기본값이거나 너무 짧습니다. 32자 이상 난수로 설정하세요.",
            }
        )

    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        issues.append(
            {
                "level": "critical" if is_production() else "warn",
                "code": "admin_unset",
                "message": "ADMIN_USERNAME / ADMIN_PASSWORD 미설정. 환경변수로 관리자 계정을 설정하세요.",
            }
        )
    else:
        weak_admin = ADMIN_PASSWORD in _WEAK_ADMIN_PASSWORDS or len(ADMIN_PASSWORD) < 8
        if weak_admin:
            issues.append(
                {
                    "level": "critical" if is_production() else "warn",
                    "code": "weak_admin_password",
                    "message": "ADMIN_PASSWORD 가 약합니다. .env 에 강한 비밀번호를 설정하세요.",
                }
            )

    if ADMIN_USERNAME and ADMIN_USERNAME.lower() in {
        "admin",
        "administrator",
        "root",
    } and is_production():
        issues.append(
            {
                "level": "warn",
                "code": "generic_admin_username",
                "message": "운영 환경에서 관리자 ID 가 추측하기 쉬운 값입니다. 변경을 권장합니다.",
            }
        )

    if ALLOW_DEMO_BILLING_UPGRADE:
        issues.append(
            {
                "level": "critical" if is_production() else "warn",
                "code": "demo_billing_on",
                "message": "ALLOW_DEMO_BILLING_UPGRADE=true — 결제 없이 Pro/Enterprise 전환 가능. 운영에서는 false.",
            }
        )

    origins = cors_allow_origins()
    if origins == ["*"]:
        issues.append(
            {
                "level": "warn" if is_production() else "info",
                "code": "cors_wildcard",
                "message": "ALLOWED_ORIGINS=* (모든 출처 허용). 운영에서는 실제 도메인만 지정하세요.",
            }
        )

    if not llm_configured():
        # hybrid/free: 초안으로 운영 가능. paid 운영만 critical.
        level = "info"
        if COST_MODE == "paid" and is_production():
            level = "critical"
        elif COST_MODE == "paid":
            level = "warn"
        issues.append(
            {
                "level": level,
                "code": "no_openai_key",
                "message": (
                    "OPENAI_API_KEY 미설정 — 스마트 초안만 동작. 키를 넣으면 사용량만큼 AI 과금됩니다."
                    if COST_MODE != "free"
                    else "COST_MODE=free — LLM 없이 스마트 초안만 사용합니다."
                ),
            }
        )
    elif is_free_cost_mode() and llm_configured():
        issues.append(
            {
                "level": "info",
                "code": "llm_skipped_free_mode",
                "message": "COST_MODE=free — API 키가 있어도 LLM 호출을 하지 않습니다.",
            }
        )

    if is_production() and not data_dir_is_external():
        # Supabase 연결 시 local 디스크 의존이 줄어듦
        sb_ok = bool(
            SUPABASE_URL
            and SUPABASE_KEY
            and "xxxx" not in (SUPABASE_URL or "")
            and len(SUPABASE_KEY or "") > 40
        )
        if not sb_ok:
            issues.append(
                {
                    # hybrid/free: 유료 Volume 없이 가능 (재배포 시 초기화 안내)
                    "level": "info" if COST_MODE in {"free", "hybrid"} else "warn",
                    "code": "ephemeral_storage",
                    "message": (
                        "유료 Volume 없이 로컬 저장 중. 재배포 시 데이터가 초기화될 수 있습니다. "
                        "(비용 아끼는 기본 설정 — 나중에 /data 볼륨만 붙이면 영속화)"
                        if COST_MODE in {"free", "hybrid"}
                        else "DATA_DIR(볼륨) 미설정 + Supabase 미연결 — 재배포 시 회원/일지 유실 위험. Railway Volume을 /data 에 마운트하세요."
                    ),
                }
            )

    pay = (PRO_PAYMENT_URL or "").lower()
    if not pay or "example.com" in pay or "your-payment" in pay:
        issues.append(
            {
                "level": "warn" if is_production() else "info",
                "code": "placeholder_payment_url",
                "message": "PRO_PAYMENT_URL 이 플레이스홀더입니다. 결제 연동 전이면 문의 플로우로 안내하세요.",
            }
        )

    if is_production() and (not SUPABASE_URL or "xxxx" in (SUPABASE_URL or "")):
        issues.append(
            {
                "level": "info" if COST_MODE in {"free", "hybrid"} else "warn",
                "code": "local_json_storage",
                "message": (
                    "Supabase 없이 local_json 저장 (추가 DB 비용 없음). 재배포 시 초기화될 수 있습니다."
                    if COST_MODE in {"free", "hybrid"}
                    else "SUPABASE 미연결 — local_json 저장. Railway 재배포 시 데이터 유실 위험이 있습니다."
                ),
            }
        )

    if is_production() and not (ROOT_DIR / ".env").exists():
        # 호스팅이 환경변수로만 주입하는 경우는 정상일 수 있음
        issues.append(
            {
                "level": "info",
                "code": "no_dotenv_file",
                "message": ".env 파일이 없습니다. 호스팅 환경변수로 주입 중인지 확인하세요.",
            }
        )

    return issues


def assert_secure_for_production() -> None:
    """
    APP_ENV=production 일 때 critical 이슈 검사.
    기본: 경고만 출력하고 기동은 계속 (Railway 네트워크/헬스체크 실패 방지).
    STRICT_SECURITY=1 이면 RuntimeError 로 기동 중단.
    """
    if not is_production():
        return
    critical = [i for i in security_issues() if i["level"] == "critical"]
    if not critical:
        return
    lines = "\n".join(f"  - [{i['code']}] {i['message']}" for i in critical)
    msg = (
        "프로덕션 보안 경고 — 설정을 강화하세요.\n"
        f"{lines}\n"
        "안내: docs/ops/DEPLOY_SECURITY_CHECKLIST.md"
    )
    strict = (_get_secret("STRICT_SECURITY", "false") or "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if strict:
        raise RuntimeError(msg)
    print(f"[RoadLog security:critical-soft] {msg}", flush=True)


# ── 관리자 폰 알림 (결제 클레임 등) ─────────────────────
# ntfy: 폰에 ntfy 앱 설치 → 토픽 구독. 서버는 NTFY_TOPIC 만 설정.
NTFY_SERVER = _get_secret("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOPIC = _get_secret("NTFY_TOPIC", "")
NTFY_TOKEN = _get_secret("NTFY_TOKEN", "")
TELEGRAM_BOT_TOKEN = _get_secret("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _get_secret("TELEGRAM_CHAT_ID", "")

# ── LLM (OpenAI 호환: OpenAI / xAI 등) ─────────────────
OPENAI_API_KEY = _get_secret("OPENAI_API_KEY", "")
# xAI 등 OpenAI 호환 키 (OPENAI 가 없거나 한도 초과 시 폴백)
XAI_API_KEY = _get_secret("XAI_API_KEY", "")
OPENAI_MODEL = _get_secret("OPENAI_MODEL", "gpt-4o-mini")
# 비우면 OpenAI 공식. xAI: https://api.x.ai/v1
OPENAI_BASE_URL = _get_secret("OPENAI_BASE_URL", "").rstrip("/")
XAI_BASE_URL = (_get_secret("XAI_BASE_URL", "https://api.x.ai/v1") or "https://api.x.ai/v1").rstrip("/")
XAI_MODEL = _get_secret("XAI_MODEL", "grok-2-latest")


def resolve_llm_config() -> dict[str, str]:
    """
    실제 호출에 쓸 LLM 설정.
    1) OPENAI_API_KEY (+ optional OPENAI_BASE_URL)
    2) XAI_API_KEY → xAI Grok (OpenAI SDK 호환)
    """
    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-xxxx"):
        return {
            "provider": "openai" if not OPENAI_BASE_URL else "openai_compatible",
            "api_key": OPENAI_API_KEY,
            "base_url": OPENAI_BASE_URL or "",
            "model": OPENAI_MODEL or "gpt-4o-mini",
        }
    if XAI_API_KEY and not XAI_API_KEY.startswith("xai-xxxx"):
        return {
            "provider": "xai",
            "api_key": XAI_API_KEY,
            "base_url": XAI_BASE_URL,
            "model": XAI_MODEL or "grok-2-latest",
        }
    return {"provider": "", "api_key": "", "base_url": "", "model": ""}


def llm_configured() -> bool:
    return bool(resolve_llm_config().get("api_key"))


# ── Supabase ────────────────────────────────────────────
SUPABASE_URL = _get_secret("SUPABASE_URL", "")
SUPABASE_KEY = _get_secret("SUPABASE_KEY", "")


def data_dir_is_external() -> bool:
    """Railway Volume 등 컨테이너 외부 영속 경로 사용 여부."""
    raw = (os.getenv("DATA_DIR") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    if not raw:
        return False
    try:
        return Path(raw).resolve() == Path(DATA_DIR).resolve()
    except Exception:
        return False

# ── AdSense (Free 결과 하단 전용) ───────────────────────
ADSENSE_CLIENT = _get_secret("ADSENSE_CLIENT", "ca-pub-xxxxxxxxxxxxxxxx")
ADSENSE_SLOT = _get_secret("ADSENSE_SLOT", "xxxxxxxxxx")

# ── 로컬 저장 경로 (쓰기 가능한 DATA_DIR 기준) ──────────
USERS_JSON = DATA_DIR / "users.json"
USAGE_JSON = DATA_DIR / "usage.json"
PAYMENTS_JSON = DATA_DIR / "payments.json"
LOGS_DIR = DATA_DIR / "logs"
SETTINGS_DIR = DATA_DIR / "settings"
try:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# ── 기본 사용자 설정 ────────────────────────────────────
DEFAULT_USER_SETTINGS = {
    "vehicle_number": "",
    "driver_name": "",
    "company_name": "",
    "lunch_start": "12:00",
    "lunch_end": "13:00",
    "exclude_lunch": True,
    # 점심 장소(식당명·위치)는 근무시간 외 사생활 — 기본 비노출
    "omit_lunch_place": True,
    "frequent_places": [],
    "default_purpose": "업무 출장",
    "fuel_type": "휘발유",
}

# ── Few-shot 예시 (OpenAI 폴백/프롬프트) ────────────────
FEW_SHOT_EXAMPLES = [
    {
        "input": "오늘 아침 9시에 본사 출발해서 강남 고객사 미팅 갔다가 오후 2시에 복귀. 차량 12가3456",
        "output": {
            "date": "자동",
            "vehicle": "12가3456",
            "trips": [
                {
                    "depart_time": "09:00",
                    "arrive_time": "09:50",
                    "from": "본사",
                    "to": "강남 고객사",
                    "purpose": "고객 미팅",
                    "distance_km": 18.5,
                    "memo": "정기 미팅 참석",
                },
                {
                    "depart_time": "13:10",
                    "arrive_time": "14:00",
                    "from": "강남 고객사",
                    "to": "본사",
                    "purpose": "업무 복귀",
                    "distance_km": 18.5,
                    "memo": "",
                },
            ],
            "total_distance_km": 37.0,
            "summary": "강남 고객사 정기 미팅 참석 후 본사 복귀",
        },
    },
]
