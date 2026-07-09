"""
로드로그 · About / 회사 소개
제품: 로드로그(RoadLog) · 운영: 코어랩스(CoreLabs)
"""

from __future__ import annotations

import streamlit as st

from modules.styles import inject_global_css, render_footer, render_page_header

st.set_page_config(
    page_title="About · 로드로그 · CoreLabs",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_global_css()
render_page_header("About", "RoadLog × CoreLabs")

st.markdown(
    """
<div style="
  max-width: 46rem;
  margin: 0.35rem 0 1.25rem;
  padding: 1.35rem 1.4rem 1.4rem;
  border-radius: 16px;
  border: 1px solid rgba(13,148,136,0.28);
  background: linear-gradient(165deg, #0f172a 0%, #0b1220 100%);
  color: #94a3b8;
  line-height: 1.7;
">
  <div style="
    display:inline-block;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;
    text-transform:uppercase;color:#5eead4;padding:0.25rem 0.55rem;border-radius:999px;
    border:1px solid rgba(45,212,191,0.3);background:rgba(45,212,191,0.08);margin-bottom:0.75rem;
  ">Technology Studio</div>
  <p style="margin:0 0 0.85rem;font-size:1.05rem;font-weight:700;color:#f1f5f9;letter-spacing:-0.02em;">
    로드로그(RoadLog) · 제품 &nbsp;|&nbsp; 코어랩스(CoreLabs) · 운영
  </p>
  <p style="margin:0;font-size:0.95rem;">
    로드로그(RoadLog)는 데이터의 본질을 연구하고 가치를 창출하는 기술 스튜디오,
    <strong style="color:#e2e8f0;">코어랩스(CoreLabs)</strong>에 의해 운영됩니다.
  </p>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0.75rem;margin-bottom:1.25rem;max-width:46rem;">
  <div style="padding:1rem 1.05rem;border-radius:14px;border:1px solid #e2e8f0;background:#fff;">
    <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.08em;color:#0d9488;text-transform:uppercase;">Product</div>
    <div style="margin-top:0.35rem;font-weight:750;color:#0f172a;">로드로그 · RoadLog</div>
    <p style="margin:0.4rem 0 0;font-size:0.86rem;color:#64748b;line-height:1.5;">
      AI 운행일지 생성·문서 변환·팀 승인 기능을 제공하는 SaaS 제품입니다.
    </p>
  </div>
  <div style="padding:1rem 1.05rem;border-radius:14px;border:1px solid rgba(13,148,136,0.35);background:linear-gradient(180deg,#f0fdfa,#fff);">
    <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.08em;color:#0d9488;text-transform:uppercase;">Studio</div>
    <div style="margin-top:0.35rem;font-weight:750;color:#0f172a;">코어랩스 · CoreLabs</div>
    <p style="margin:0.4rem 0 0;font-size:0.86rem;color:#64748b;line-height:1.5;">
      데이터와 업무 흐름을 설계하는 기술 스튜디오로, 로드로그를 연구·개발·운영합니다.
    </p>
  </div>
  <div style="padding:1rem 1.05rem;border-radius:14px;border:1px solid #e2e8f0;background:#fff;">
    <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.08em;color:#0d9488;text-transform:uppercase;">Trust</div>
    <div style="margin-top:0.35rem;font-weight:750;color:#0f172a;">검증된 운영 체계</div>
    <p style="margin:0.4rem 0 0;font-size:0.86rem;color:#64748b;line-height:1.5;">
      보안·약관·요금 체계까지 스튜디오 단위로 관리하는 전문 솔루션을 지향합니다.
    </p>
  </div>
</div>

<div style="
  max-width:46rem;margin:0.5rem 0 1rem;padding:1.25rem 1.25rem;border-radius:14px;
  border:1px solid rgba(13,148,136,0.28);background:linear-gradient(135deg,#f0fdfa,#fff);
">
  <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.1em;color:#0d9488;text-transform:uppercase;">
    Contact &amp; Feedback
  </div>
  <p style="margin:0.55rem 0 0.85rem;font-size:0.95rem;color:#0f172a;font-weight:650;line-height:1.55;">
    코어랩스는 사용자의 피드백을 기술적 자산으로 여깁니다. 어떤 의견이든 환영합니다.
  </p>
  <p style="margin:0 0 0.9rem;font-size:0.9rem;color:#475569;line-height:1.6;">
    서비스 관련 문의나 기술 협업 제안은
    <a href="mailto:corelabs.studio@gmail.com" style="color:#0f766e;font-weight:700;">
      corelabs.studio@gmail.com
    </a>
    으로 연락 주세요.
  </p>
  <a href="https://docs.google.com/forms/d/e/1FAIpQLScl9ZJD_crv1d6JPDzdNaYTDzUQXKkLNx_X6pmyEwsg_1DnGg/viewform?usp=sf_link"
     target="_blank" rel="noopener noreferrer"
     style="display:inline-block;padding:0.65rem 1rem;border-radius:10px;background:#0d9488;color:#fff;
            font-weight:700;font-size:0.9rem;text-decoration:none;">
    서비스 피드백 및 문의하기
  </a>
</div>

<p style="font-size:0.78rem;color:#94a3b8;letter-spacing:0.04em;margin:0 0 0.5rem;">
  Powered by <strong style="color:#0f766e;">CoreLabs</strong>
</p>
    """,
    unsafe_allow_html=True,
)

render_footer()
