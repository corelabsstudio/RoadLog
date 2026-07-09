"""
로드로그 · 이용약관
본문: docs/이용약관.md
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.styles import inject_global_css, render_footer, render_page_header

st.set_page_config(
    page_title="이용약관 · 로드로그",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_global_css()
render_page_header("이용약관", "Terms of Service · RoadLog")

terms_path = Path(__file__).resolve().parent.parent / "docs" / "이용약관.md"
if terms_path.exists():
    st.markdown(terms_path.read_text(encoding="utf-8"))
else:
    st.warning("이용약관 문서를 찾을 수 없습니다. (`docs/이용약관.md`)")

render_footer()
