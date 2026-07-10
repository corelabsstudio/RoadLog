"""
로드로그 (RoadLog) v2 — 메인 Streamlit 앱
회사 제출용 운행일지 SaaS

실행:
  streamlit run app.py
"""

from __future__ import annotations

import os
import sys

# 현재 디렉토리를 모듈 검색 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from modules.config import (
    ADSENSE_CLIENT,
    ADSENSE_SLOT,
    APP_FULL,
    FREE_MONTHLY_LIMIT,
    OPENAI_API_KEY,
    PRO_PAYMENT_URL,
)
from modules import db
from modules.auth import (
    can_generate,
    consume_usage,
    get_user_plan,
    init_session,
    is_logged_in,
    is_pro,
    render_auth_sidebar,
    require_login,
    show_limit_cta_if_needed,
    show_login_page,
    show_usage_widget,
)
from modules.config_manager import get_settings_for_current_user, render_settings_page
from modules.enterprise import render_enterprise_view
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


# ── AdSense (Free 결과 하단 전용) ──────────────────────


def render_adsense() -> None:
    """Free 사용자 결과 페이지 하단에만 가볍게 배치. Pro는 숨김."""
    if is_pro():
        return
    # 플레이스홀더 클라이언트면 데모 박스만 표시
    if "xxxx" in ADSENSE_CLIENT:
        st.markdown(
            """
<div style="margin-top:1.2rem;padding:1rem;border:1px dashed #CBD5E1;border-radius:12px;
            text-align:center;color:#64748B;font-size:0.85rem;background:#F8FAFC;">
  📢 광고 영역 (Free) · AdSense 클라이언트 ID 설정 시 실제 광고가 표시됩니다
</div>
            """,
            unsafe_allow_html=True,
        )
        return

    ad_html = f"""
<div style="margin-top:12px;text-align:center;">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}"
          crossorigin="anonymous"></script>
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{ADSENSE_CLIENT}"
       data-ad-slot="{ADSENSE_SLOT}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>
       (adsbygoogle = window.adsbygoogle || []).push({{}});
  </script>
</div>
"""
    st.components.v1.html(ad_html, height=120)


# ── 사이드바 네비게이션 ────────────────────────────────


def render_sidebar_nav() -> str:
    render_sidebar_brand()
    st.sidebar.markdown("---")

    render_auth_sidebar()
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "메뉴",
        options=["홈", "설정", "요금제", "관리자"],
        label_visibility="collapsed",
        key="main_nav",
    )
    st.sidebar.markdown("---")
    st.sidebar.caption(f"저장소: {db.supabase_status()}")
    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-xxxx"):
        st.sidebar.caption("OpenAI 연결됨")
    else:
        st.sidebar.caption("OpenAI 미설정 · 폴백")
    return page


# ── 홈 · 생성 ──────────────────────────────────────────


def render_home() -> None:
    render_page_header()  # 브랜드: 로드로그 + 큰 타이틀 + 로고
    render_hero()

    if is_logged_in():
        show_usage_widget()
        st.markdown("")
    else:
        st.info("왼쪽에서 로그인 후 생성할 수 있습니다. Free는 월 10회입니다.")

    # 입력 카드
    st.markdown("### 운행 내용")
    st.caption(
        "예: 오전 9시 본사 출발, 강남 고객사 미팅 후 3시 복귀. 왕복 약 40km"
    )

    default_example = (
        "오늘 09:00 본사 출발하여 10:00 강남 고객사 도착, 미팅 진행. "
        "점심 후 13:30 출발하여 14:20 본사 복귀. 차량은 설정값 사용. 왕복 약 37km."
    )
    raw = st.text_area(
        "운행 내용",
        value=st.session_state.get("last_raw_input") or "",
        height=150,
        placeholder=default_example,
        label_visibility="collapsed",
        key="raw_input_area",
    )

    col_a, col_b, col_c = st.columns([1.2, 1, 2])
    with col_a:
        gen_clicked = st.button(
            "일지 생성",
            type="primary",
            use_container_width=True,
        )
    with col_b:
        if st.button("예시 불러오기", use_container_width=True):
            st.session_state["last_raw_input"] = default_example
            st.rerun()

    if gen_clicked:
        if not require_login():
            st.stop()
        if show_limit_cta_if_needed():
            st.stop()

        settings = get_settings_for_current_user()
        with st.spinner("AI가 격식 있는 운행일지를 작성 중입니다..."):
            result = generate_driving_log(raw, settings)

        if result["success"] or result.get("log"):
            # 검증 경고가 있어도 log가 있으면 사용량 차감 (성공 생성으로 간주)
            if result.get("log") and result.get("log", {}).get("trips"):
                consume_usage()
            st.session_state["last_result"] = result
            st.session_state["last_raw_input"] = raw
        else:
            st.session_state["last_result"] = result
            for e in result.get("errors") or []:
                st.error(e)

    # 결과 표시
    result = st.session_state.get("last_result")
    if not result or not result.get("log"):
        _render_feature_cards()
        render_footer()
        return

    log = result["log"]
    st.markdown("---")
    st.markdown("### 생성 결과")

    if result.get("engine") == "fallback":
        title = result.get("engine_title") or "규칙 기반 초안"
        msg = result.get("message") or (
            "AI를 쓰지 못해 규칙 기반 초안으로 생성되었습니다. 구간·시간을 확인해 주세요."
        )
        st.warning(f"**{title}** — {msg}")
        if result.get("engine_detail"):
            st.caption(f"기술 정보: {result.get('engine_detail')}")
    elif result.get("engine") == "openai":
        st.success(result.get("message") or "AI로 일지를 생성했습니다. 시간·구간을 확인해 주세요.")

    if result.get("warnings"):
        for w in result["warnings"]:
            st.warning(w)
    if result.get("errors"):
        for e in result["errors"]:
            st.error(e)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("작성일", log.get("date", "-"))
    m2.metric("차량번호", log.get("vehicle") or "-")
    m3.metric("총 거리", f"{log.get('total_distance_km', 0)} km")
    m4.metric("순수 운행", format_minutes_kr(int(log.get("total_net_minutes") or 0)))

    if log.get("summary"):
        st.markdown(
            f"""
<div class="uil-card uil-card-accent">
  <strong>운행 요약</strong><br/>{log.get('summary')}
</div>
            """,
            unsafe_allow_html=True,
        )

    # 테이블
    trips = log.get("trips") or []
    if trips:
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "출발": t.get("depart_time"),
                    "도착": t.get("arrive_time"),
                    "출발지": t.get("from"),
                    "도착지": t.get("to"),
                    "목적": t.get("purpose"),
                    "거리(km)": t.get("distance_km"),
                    "순수운행": t.get("duration_display"),
                    "점심제외(분)": t.get("lunch_excluded_minutes", 0),
                    "비고": t.get("memo", ""),
                }
                for t in trips
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    # 편집 (간단)
    with st.expander("결과 직접 수정 (JSON)", expanded=False):
        import json

        edited = st.text_area(
            "JSON",
            value=json.dumps(log, ensure_ascii=False, indent=2),
            height=260,
            key="edit_json",
        )
        if st.button("수정 반영", key="apply_json"):
            try:
                new_log = json.loads(edited)
                from modules.validator import validate_log

                settings = get_settings_for_current_user()
                v = validate_log(new_log, settings)
                st.session_state["last_result"] = {
                    "success": v["ok"],
                    "log": v["enriched_log"],
                    "errors": v["errors"],
                    "warnings": v["warnings"],
                    "engine": result.get("engine"),
                    "message": "수정 반영",
                }
                st.success("반영되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"JSON 오류: {e}")

    # 다운로드 3종 — Free도 워터마크 없음
    render_download_buttons(log)

    # Free 한도 안내 + Pro CTA (여유 없을 때 강화)
    if is_logged_in() and not is_pro():
        used = db.get_usage(st.session_state["user"]["email"])
        remain = max(0, FREE_MONTHLY_LIMIT - used)
        if remain <= 2:
            st.markdown("")
            render_pro_cta(PRO_PAYMENT_URL)

    # AdSense — Free only, 결과 하단
    render_adsense()
    render_footer()


def _render_feature_cards() -> None:
    st.markdown("### 왜 로드로그인가요?")
    c1, c2, c3 = st.columns(3)
    cards = [
        ("클린 제출", "Excel · PDF · DOCX 워터마크 없음"),
        ("시간 검증", "점심 제외 · 거리 · 속도 자동 체크"),
        ("격식 문체", "업무용 톤으로 일지 초안 작성"),
    ]
    for col, (title, desc) in zip((c1, c2, c3), cards):
        with col:
            st.markdown(
                f"""
<div class="rl-card">
  <strong>{title}</strong>
  <p style="color:#6B7280;margin:0.5rem 0 0 0;font-size:0.92rem;">{desc}</p>
</div>
                """,
                unsafe_allow_html=True,
            )


# ── 요금제 ─────────────────────────────────────────────


def render_pricing() -> None:
    render_page_header("요금제", "가볍게 시작하고, 필요할 때 Pro로")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
<div class="rl-card">
  <span class="uil-badge uil-badge-free">Free</span>
  <h3 style="margin:0.6rem 0;">₩0 / 월</h3>
  <ul style="color:#6B7280;line-height:1.75;font-size:0.92rem;">
    <li>월 {FREE_MONTHLY_LIMIT}회 생성</li>
    <li>Excel · PDF · DOCX 클린 다운로드</li>
    <li>워터마크 없음</li>
    <li>개인 설정 저장</li>
  </ul>
</div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
<div class="rl-card" style="border:1px solid #0D9488;">
  <span class="uil-badge uil-badge-pro">Pro</span>
  <h3 style="margin:0.6rem 0;">₩9,900 / 월</h3>
  <ul style="color:#6B7280;line-height:1.75;font-size:0.92rem;">
    <li>무제한 생성</li>
    <li>문서 무제한 다운로드</li>
    <li>광고 제거</li>
    <li>우선 지원</li>
  </ul>
  <p style="margin-top:1rem;"><a href="{PRO_PAYMENT_URL}" target="_blank"
     style="background:#0D9488;color:#fff;padding:0.55rem 1.05rem;border-radius:10px;
            text-decoration:none;font-weight:650;font-size:0.9rem;">Pro 시작</a></p>
</div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("")
    render_pro_cta(PRO_PAYMENT_URL)
    render_footer()


# ── 엔트리 ─────────────────────────────────────────────


def main() -> None:
    # 로그인 전: 랜딩 + 로그인/가입
    if not is_logged_in():
        show_login_page()
        return

    # 기업용(plan_type=enterprise): 전용 대시보드
    if get_user_plan() == "enterprise":
        render_sidebar_brand()
        render_auth_sidebar()
        render_enterprise_view()
        return

    page = render_sidebar_nav()

    if page == "홈":
        render_home()
    elif page == "설정":
        render_page_header("설정", "차량·점심시간·자주 가는 곳")
        render_settings_page()
        render_footer()
    elif page == "요금제":
        render_pricing()
    elif page == "관리자":
        render_admin_dashboard()
    else:
        render_home()


if __name__ == "__main__":
    main()