"""
로드로그 · 개인정보처리방침
본문: docs/개인정보처리방침.md
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.styles import inject_global_css, render_footer, render_page_header

st.set_page_config(
    page_title="개인정보처리방침 · 로드로그",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_global_css()
render_page_header("개인정보처리방침", "Privacy Policy · RoadLog")

policy_path = Path(__file__).resolve().parent.parent / "docs" / "개인정보처리방침.md"
if policy_path.exists():
    st.markdown(policy_path.read_text(encoding="utf-8"))
else:
    st.warning("개인정보처리방침 문서를 찾을 수 없습니다. (`docs/개인정보처리방침.md`)")

render_footer()
