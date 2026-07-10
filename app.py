"""
로드로그 (RoadLog) v2 — 메인 Streamlit 앱
회사 제출용 운행일지 SaaS

실행:
  streamlit run app.py
"""
# 1. 이 구문은 파일의 가장 처음에 있어야만 합니다.
from __future__ import annotations

# 2. 경로 설정을 여기서 합니다.
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 3. 그다음 일반 import를 수행합니다.
import streamlit as st

from modules.config import (
    ADSENSE_CLIENT,
    ADSENSE_SLOT,
    APP_FULL,
    APP_TITLE,
    FREE_MONTHLY_LIMIT,
    OPENAI_API_KEY,
    PRO_PAYMENT_URL,
)
from modules import db
from modules.auth import (
    can_generate,
    consume_usage,
    init_session,
    is_logged_in,
    is_pro,
    render_auth_sidebar,
    require_login,
    show_limit_cta_if_needed,
    show_usage_widget,
)
from modules.config_manager import get_settings_for_current_user, render_settings_page
from modules.export import render_download_buttons
from modules.generator import generate_driving_log
from modules.styles import (
    inject_global_css,
    render_footer,
    render_hero,
    render_page_header,
    render_pro_cta,
    render_sidebar_brand,
)
from modules.admin import render_admin_dashboard
from modules.validator import format_minutes_kr

# ── 페이지 설정 ────────────────────────────────────────
st.set_page_config(
    page_title=APP_FULL,
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session()
inject_global_css()

# ... (나머지 코드는 그대로 두시면 됩니다)