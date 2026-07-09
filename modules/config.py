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
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT_DIR / ".env")


def _get_secret(key: str, default: str = "") -> str:
    """환경변수 → Streamlit secrets 순으로 값을 조회합니다."""
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default


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

# ── 요금제 ──────────────────────────────────────────────
FREE_MONTHLY_LIMIT = 10
PRO_PRICE_KRW = 9900
ENTERPRISE_PRICE_KRW = 89000
ENTERPRISE_BASE_SEATS = 5
ENTERPRISE_SEAT_PRICE_KRW = 5000
PRO_PAYMENT_URL = _get_secret("PRO_PAYMENT_URL", "https://your-payment-link.example.com")
ENTERPRISE_PAYMENT_URL = _get_secret(
    "ENTERPRISE_PAYMENT_URL",
    _get_secret("PRO_PAYMENT_URL", "https://your-payment-link.example.com"),
)

# ── 인증 / 관리자 ──────────────────────────────────────
ADMIN_USERNAME = _get_secret("ADMIN_USERNAME", "hhs126")
ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD", "hh921544hh@1013")
ADMIN_EMAIL = _get_secret("ADMIN_EMAIL", "hhs126@roadlog.local")
APP_SECRET = _get_secret("APP_SECRET", "roadlog-v2-secret-change-me")

# ── OpenAI / Supabase / AdSense ... (나머지 코드 생략, 동일하게 유지)
OPENAI_API_KEY = _get_secret("OPENAI_API_KEY", "")
OPENAI_MODEL = _get_secret("OPENAI_MODEL", "gpt-4o-mini")
SUPABASE_URL = _get_secret("SUPABASE_URL", "")
SUPABASE_KEY = _get_secret("SUPABASE_KEY", "")
ADSENSE_CLIENT = _get_secret("ADSENSE_CLIENT", "ca-pub-xxxxxxxxxxxxxxxx")
ADSENSE_SLOT = _get_secret("ADSENSE_SLOT", "xxxxxxxxxx")