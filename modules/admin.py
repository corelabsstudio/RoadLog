"""
관리자 전용 대시보드 로직 + UI
- 이번 달 결제자 수 / 총 수익
- Plotly 매출 추이 차트
- 결제 수동 등록 · 사용자 plan 변경
"""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import pandas as pd

from modules import db
from modules.auth import admin_login_form, is_admin, logout_admin
from modules.config import PRO_PRICE_KRW, COLORS
from modules.styles import render_page_header


def render_admin_dashboard() -> None:
    """관리자 페이지 전체 렌더."""
    render_page_header("관리자", "매출 · 사용자 · 결제 관리 · 고객 문의 메일")

    if not admin_login_form():
        return

    # 메일 확인 — Gmail 수신함 (API 없이 바로 열기)
    m1, m2, m3 = st.columns([1.2, 1.2, 2])
    with m1:
        st.link_button(
            "✉ 메일 확인 (수신함)",
            "https://mail.google.com/mail/u/0/#inbox",
            use_container_width=True,
            type="primary",
        )
    with m2:
        st.link_button(
            "빠른 회신 작성",
            "https://mail.google.com/mail/u/0/?view=cm&fs=1&to=corelabs.studio@gmail.com&tf=1",
            use_container_width=True,
        )
    with m3:
        st.caption("문의 채널 · corelabs.studio@gmail.com · 새 탭에서 Gmail 열림")

    stats = db.admin_stats()
    c_top1, c_top2, c_top3, c_top4 = st.columns(4)
    c_top1.metric("이번 달 결제자", f"{stats['payer_count']}명")
    c_top2.metric("이번 달 총 수익", f"{stats['revenue']:,}원")
    c_top3.metric("전체 사용자", f"{stats['total_users']}명")
    c_top4.metric("Pro 회원", f"{stats['pro_users']}명")

    st.markdown("---")

    # 매출 추이 차트
    st.markdown("### 매출 추이")
    trend_df = pd.DataFrame(stats["trend"])
    if trend_df.empty:
        trend_df = pd.DataFrame([{"month": stats["month"], "revenue": 0}])

    fig = px.bar(
        trend_df,
        x="month",
        y="revenue",
        labels={"month": "월", "revenue": "매출 (원)"},
        text="revenue",
    )
    fig.update_traces(
        marker_color=COLORS["teal"],
        texttemplate="%{text:,.0f}",
        textposition="outside",
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="SUIT, Pretendard, sans-serif", color=COLORS["navy"]),
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(gridcolor="#E2E8F0", title="매출 (원)"),
        xaxis=dict(title="월"),
        height=380,
    )
    # 라인 오버레이
    fig2 = px.line(trend_df, x="month", y="revenue")
    fig2.update_traces(line_color=COLORS["navy"], line_width=2, name="추이")
    for tr in fig2.data:
        fig.add_trace(tr)

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("### 이번 달 결제")
        pays = stats.get("payments") or []
        if pays:
            pdf = pd.DataFrame(pays)
            cols = [c for c in ["paid_at", "email", "amount", "plan", "note"] if c in pdf.columns]
            st.dataframe(pdf[cols], use_container_width=True, hide_index=True)
        else:
            st.info("이번 달 결제 기록이 없습니다. 우측에서 수동 등록할 수 있습니다.")

    with right:
        st.markdown("### 결제 등록")
        with st.form("admin_add_payment"):
            email = st.text_input("사용자 이메일")
            amount = st.number_input(
                "결제 금액 (원)", min_value=0, value=PRO_PRICE_KRW, step=1000
            )
            plan = st.selectbox("플랜", ["pro", "free"])
            note = st.text_input("메모", value="수동 등록")
            if st.form_submit_button("등록", type="primary", use_container_width=True):
                if not email or "@" not in email:
                    st.error("이메일을 확인해 주세요.")
                else:
                    # 사용자가 없으면 안내
                    u = db.get_user(email)
                    if not u:
                        st.warning("미가입 이메일이지만 결제 기록은 저장합니다.")
                    ok = db.record_payment(email.strip().lower(), int(amount), plan, note)
                    if ok:
                        st.success("결제 기록이 등록되었습니다.")
                        st.rerun()
                    else:
                        st.error("등록 실패")

        st.markdown("### 플랜 변경")
        users = db.list_users()
        if users:
            emails = [u["email"] for u in users]
            with st.form("admin_plan_form"):
                sel = st.selectbox("사용자", emails)
                new_plan = st.selectbox("변경 플랜", ["free", "pro"], key="plan_change")
                if st.form_submit_button("플랜 저장", use_container_width=True):
                    if db.set_user_plan(sel, new_plan):
                        st.success(f"{sel} → {new_plan}")
                        st.rerun()
                    else:
                        st.error("변경 실패")
            st.dataframe(
                pd.DataFrame(users)[["email", "name", "plan", "created_at"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("등록된 사용자가 없습니다.")

    st.markdown("---")
    st.caption(f"저장소 모드: **{db.supabase_status()}** · 월 키: {stats['month']}")
    if st.button("관리자 로그아웃", key="admin_logout"):
        logout_admin()
        st.rerun()
