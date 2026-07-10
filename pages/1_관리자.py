"""
Streamlit multi-page: /관리자
사이드바 '관리자' 페이지와 동일 대시보드를 제공합니다.
"""

from __future__ import annotations

import streamlit as st

from modules.auth import init_session
from modules.styles import inject_global_css
from modules.admin import render_admin_dashboard

try:
    st.set_page_config(
        page_title="관리자 · 로드로그",
        page_icon="🛣️",
        layout="wide",
    )
except Exception:
    # 이미 설정된 경우( multipage 전환) 무시
    pass

init_session()
inject_global_css()
render_admin_dashboard()
