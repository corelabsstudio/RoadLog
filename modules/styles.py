"""
로드로그 (RoadLog) — Premium SaaS UI
Linear / Stripe 느낌의 클린 디자인 + 한글 타이포
"""

from __future__ import annotations

import html
import streamlit as st

from modules.config import APP_SHORT, APP_TAGLINE, APP_TITLE, COLORS, FREE_MONTHLY_LIMIT


# ── 로고 SVG (웹 /icons/logo.svg 와 동일 디자인) ──────

LOGO_SVG = """
<svg width="36" height="36" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <linearGradient id="rlGrad" x1="6" y1="4" x2="58" y2="60" gradientUnits="userSpaceOnUse">
      <stop stop-color="#67E8F9"/><stop offset="0.45" stop-color="#22D3EE"/><stop offset="1" stop-color="#0891B2"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="16" fill="url(#rlGrad)"/>
  <rect x="3" y="3" width="58" height="28" rx="13" fill="#fff" fill-opacity="0.12"/>
  <path d="M13 46c7.5-15 15.5-22.5 26.5-22.5 4.2 0 7.4 1.6 9.5 4.2" stroke="#041016" stroke-width="4.2" stroke-linecap="round"/>
  <circle cx="48.5" cy="25" r="5.2" fill="#041016"/>
  <circle cx="48.5" cy="25" r="2.1" fill="#67E8F9"/>
  <path d="M13 46h28" stroke="#041016" stroke-opacity="0.4" stroke-width="3.2" stroke-linecap="round"/>
  <circle cx="18" cy="46" r="3.6" fill="#041016"/><circle cx="37" cy="46" r="3.6" fill="#041016"/>
  <circle cx="18" cy="46" r="1.3" fill="#67E8F9"/><circle cx="37" cy="46" r="1.3" fill="#67E8F9"/>
</svg>
"""

LOGO_SVG_LG = """
<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <linearGradient id="rlGradLg" x1="6" y1="4" x2="58" y2="60" gradientUnits="userSpaceOnUse">
      <stop stop-color="#67E8F9"/><stop offset="0.45" stop-color="#22D3EE"/><stop offset="1" stop-color="#0891B2"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="16" fill="url(#rlGradLg)"/>
  <rect x="3" y="3" width="58" height="28" rx="13" fill="#fff" fill-opacity="0.12"/>
  <path d="M13 46c7.5-15 15.5-22.5 26.5-22.5 4.2 0 7.4 1.6 9.5 4.2" stroke="#041016" stroke-width="4.2" stroke-linecap="round"/>
  <circle cx="48.5" cy="25" r="5.2" fill="#041016"/>
  <circle cx="48.5" cy="25" r="2.1" fill="#67E8F9"/>
  <path d="M13 46h28" stroke="#041016" stroke-opacity="0.4" stroke-width="3.2" stroke-linecap="round"/>
  <circle cx="18" cy="46" r="3.6" fill="#041016"/><circle cx="37" cy="46" r="3.6" fill="#041016"/>
  <circle cx="18" cy="46" r="1.3" fill="#67E8F9"/><circle cx="37" cy="46" r="1.3" fill="#67E8F9"/>
</svg>
"""


def inject_global_css() -> None:
    c = COLORS
    st.markdown(
        f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

:root {{
  --font: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  --font-en: 'Plus Jakarta Sans', var(--font);
  --ink: #0B1220;
  --ink-2: #1E293B;
  --muted: #64748B;
  --muted-2: #94A3B8;
  --line: #E2E8F0;
  --line-2: #F1F5F9;
  --bg: #F8FAFC;
  --card: #FFFFFF;
  --teal: #0D9488;
  --teal-2: #14B8A6;
  --teal-soft: #CCFBF1;
  --teal-glow: rgba(13,148,136,0.14);
  --shadow-sm: 0 1px 2px rgba(15,23,42,0.04);
  --shadow: 0 4px 16px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04);
  --shadow-lg: 0 20px 50px -12px rgba(15,23,42,0.12), 0 8px 20px -8px rgba(15,23,42,0.08);
  --radius: 16px;
  --radius-sm: 12px;
}}

html, body, [class*="css"], .stApp, .stMarkdown, p, span, label, div,
input, textarea, button, select {{
  font-family: var(--font) !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  letter-spacing: -0.02em;
}}

/* 전체 배경 — soft mesh */
.stApp {{
  background:
    radial-gradient(900px 420px at 8% -8%, rgba(20,184,166,0.10), transparent 55%),
    radial-gradient(700px 360px at 96% 4%, rgba(99,102,241,0.06), transparent 50%),
    radial-gradient(600px 300px at 50% 100%, rgba(13,148,136,0.05), transparent 45%),
    var(--bg) !important;
  color: var(--ink);
}}

/* Streamlit chrome 정리 */
header[data-testid="stHeader"] {{
  background: transparent !important;
  height: 2.5rem;
}}
[data-testid="stToolbar"] {{ visibility: hidden; height: 0; }}
#MainMenu, footer, [data-testid="stStatusWidget"] {{ visibility: hidden; }}
div[data-testid="stDecoration"] {{ display: none; }}

.block-container {{
  padding-top: 1.25rem !important;
  padding-bottom: 4rem !important;
  max-width: 1040px !important;
}}

/* 터치·가독성 기본 */
.stButton > button {{
  min-height: 2.75rem !important;
}}
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {{
  font-size: 1rem !important;
}}

/* ── 사이드바 ── */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #0B1220 0%, #111827 55%, #0F172A 100%) !important;
  border-right: 1px solid rgba(148,163,184,0.12) !important;
}}
section[data-testid="stSidebar"] > div {{
  padding-top: 1.25rem !important;
}}
section[data-testid="stSidebar"] * {{
  color: #CBD5E1 !important;
}}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3,
section[data-testid="stSidebar"] .stMarkdown p strong {{
  color: #F8FAFC !important;
}}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] .stCaption {{
  color: #64748B !important;
  font-size: 0.78rem !important;
}}
section[data-testid="stSidebar"] .stButton > button {{
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(148,163,184,0.18) !important;
  color: #F1F5F9 !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  transition: all .15s ease !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
  background: rgba(13,148,136,0.25) !important;
  border-color: rgba(45,212,191,0.4) !important;
  color: #fff !important;
}}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {{
  background: linear-gradient(135deg, #14B8A6, #0D9488) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 4px 14px rgba(13,148,136,0.35) !important;
}}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-baseweb="input"] > div,
section[data-testid="stSidebar"] [data-baseweb="base-input"] {{
  background: rgba(15,23,42,0.6) !important;
  color: #F8FAFC !important;
  border-color: rgba(148,163,184,0.2) !important;
  border-radius: 10px !important;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
  background: rgba(255,255,255,0.03) !important;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  padding: 0.55rem 0.75rem !important;
  margin-bottom: 0.3rem !important;
  font-weight: 550 !important;
  font-size: 0.9rem !important;
  transition: all .15s ease !important;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{
  background: rgba(255,255,255,0.06) !important;
  border-color: rgba(148,163,184,0.15) !important;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
  background: rgba(13,148,136,0.18) !important;
  border-color: rgba(45,212,191,0.35) !important;
  color: #5EEAD4 !important;
}}
section[data-testid="stSidebar"] [data-baseweb="tab-list"] {{
  background: rgba(255,255,255,0.04) !important;
  border-radius: 10px !important;
  padding: 3px !important;
  gap: 2px !important;
}}
section[data-testid="stSidebar"] [data-baseweb="tab"] {{
  color: #94A3B8 !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-size: 0.84rem !important;
}}
section[data-testid="stSidebar"] [aria-selected="true"] {{
  background: rgba(13,148,136,0.25) !important;
  color: #5EEAD4 !important;
}}
section[data-testid="stSidebar"] hr {{
  border-color: rgba(148,163,184,0.12) !important;
  margin: 0.9rem 0 !important;
}}
section[data-testid="stSidebar"] [data-testid="stAlert"] {{
  background: rgba(13,148,136,0.12) !important;
  border: 1px solid rgba(45,212,191,0.25) !important;
  border-radius: 10px !important;
}}

/* ── 타이포 ── */
h1, .stApp h1 {{
  color: var(--ink) !important;
  font-weight: 800 !important;
  letter-spacing: -0.04em !important;
  line-height: 1.15 !important;
}}
h2, .stApp h2 {{
  color: var(--ink) !important;
  font-weight: 700 !important;
  font-size: 1.2rem !important;
  letter-spacing: -0.03em !important;
}}
h3, .stApp h3 {{
  color: var(--ink-2) !important;
  font-weight: 700 !important;
  font-size: 1.05rem !important;
}}
p, li, label, .stMarkdown p {{
  font-size: 0.95rem !important;
  line-height: 1.65 !important;
  color: var(--muted);
  font-weight: 400 !important;
}}
.stCaption, [data-testid="stCaptionContainer"] {{
  font-size: 0.82rem !important;
  color: var(--muted) !important;
}}

/* ── 사이드바 브랜드 ── */
.rl-brand {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0.15rem 0.15rem 0.5rem;
}}
.rl-brand svg {{ flex-shrink: 0; display: block; }}
.rl-brand-text {{ display: flex; flex-direction: column; gap: 2px; }}
.rl-brand-name {{
  font-family: var(--font) !important;
  font-size: 1.15rem !important;
  font-weight: 800 !important;
  color: #F8FAFC !important;
  letter-spacing: -0.03em !important;
  line-height: 1.15 !important;
}}
.rl-brand-en {{
  font-family: var(--font-en) !important;
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  color: #5EEAD4 !important;
  letter-spacing: 0.16em !important;
  text-transform: uppercase;
}}

/* ── 히어로 ── */
.rl-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 2.4rem 2.2rem 2.2rem;
  margin-bottom: 1.5rem;
  background:
    linear-gradient(145deg, #0B1220 0%, #111827 48%, #0F766E 130%);
  box-shadow: var(--shadow-lg);
  border: 1px solid rgba(255,255,255,0.06);
}}
.rl-hero::before {{
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(500px 220px at 85% 20%, rgba(45,212,191,0.22), transparent 60%),
    radial-gradient(400px 180px at 10% 90%, rgba(99,102,241,0.12), transparent 55%);
  pointer-events: none;
}}
.rl-hero-inner {{ position: relative; z-index: 1; }}
.rl-hero-top {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 1.1rem;
}}
.rl-hero-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  background: rgba(45,212,191,0.12);
  border: 1px solid rgba(45,212,191,0.28);
  color: #5EEAD4 !important;
  font-size: 0.75rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.04em;
}}
.rl-hero h1 {{
  margin: 0 !important;
  font-size: 2.55rem !important;
  font-weight: 800 !important;
  color: #F8FAFC !important;
  letter-spacing: -0.045em !important;
  line-height: 1.12 !important;
  max-width: 16ch;
}}
.rl-hero .rl-hero-sub {{
  margin: 0.85rem 0 0 !important;
  font-size: 1.05rem !important;
  color: #94A3B8 !important;
  line-height: 1.55 !important;
  max-width: 42ch;
  font-weight: 400 !important;
}}
.rl-hero-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 1.35rem;
}}
.rl-pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.4rem 0.75rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: #E2E8F0 !important;
  font-size: 0.8rem !important;
  font-weight: 550 !important;
}}
.rl-pill span {{ opacity: 0.7; }}

/* 페이지 헤더 (설정/요금제 등) */
.rl-page-head {{
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 1.5rem;
  padding: 1.4rem 1.5rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}}
.rl-page-head .rl-logo-wrap {{ flex-shrink: 0; }}
.rl-page-head .rl-title {{
  margin: 0 !important;
  font-size: 1.75rem !important;
  font-weight: 800 !important;
  color: var(--ink) !important;
  letter-spacing: -0.04em !important;
}}
.rl-page-head .rl-sub {{
  margin: 0.35rem 0 0 !important;
  font-size: 0.95rem !important;
  color: var(--muted) !important;
}}
.rl-page-head .rl-en {{
  display: inline-block;
  margin-top: 0.45rem;
  font-family: var(--font-en) !important;
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  color: var(--teal) !important;
  letter-spacing: 0.14em !important;
  text-transform: uppercase;
}}

/* 스텝 가이드 */
.rl-steps {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}}
.rl-step {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 1rem 1.05rem;
  box-shadow: var(--shadow-sm);
  transition: transform .15s ease, box-shadow .15s ease;
}}
.rl-step:hover {{
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}}
.rl-step-num {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border-radius: 8px;
  background: var(--teal-soft);
  color: #0F766E !important;
  font-size: 0.78rem !important;
  font-weight: 800 !important;
  margin-bottom: 0.55rem;
}}
.rl-step strong {{
  display: block;
  color: var(--ink) !important;
  font-size: 0.92rem !important;
  font-weight: 700 !important;
  margin-bottom: 0.2rem;
}}
.rl-step p {{
  margin: 0 !important;
  font-size: 0.8rem !important;
  color: var(--muted) !important;
  line-height: 1.45 !important;
}}

/* 섹션 라벨 */
.rl-section-label {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.5rem 0 0.75rem;
}}
.rl-section-label h2 {{
  margin: 0 !important;
  font-size: 1.05rem !important;
  font-weight: 750 !important;
  color: var(--ink) !important;
}}
.rl-section-label .rl-dot {{
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 4px var(--teal-glow);
}}

/* 컴포저 카드 */
.rl-composer {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1.35rem 1.4rem 1.2rem;
  box-shadow: var(--shadow);
  margin-bottom: 1.25rem;
  position: relative;
}}
.rl-composer::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(45,212,191,0.35), transparent 40%, transparent 60%, rgba(99,102,241,0.15));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}}
.rl-composer-hint {{
  font-size: 0.84rem !important;
  color: var(--muted) !important;
  margin: 0 0 0.75rem !important;
  line-height: 1.5 !important;
}}

/* 기능 카드 그리드 */
.rl-features {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem;
  margin: 1.5rem 0 0.5rem;
}}
.rl-feature {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.2rem;
  box-shadow: var(--shadow-sm);
  transition: all .18s ease;
}}
.rl-feature:hover {{
  border-color: rgba(13,148,136,0.35);
  box-shadow: 0 8px 24px rgba(13,148,136,0.08);
  transform: translateY(-2px);
}}
.rl-feature-icon {{
  width: 40px; height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  background: linear-gradient(135deg, #F0FDFA, #CCFBF1);
  border: 1px solid rgba(13,148,136,0.12);
  margin-bottom: 0.75rem;
}}
.rl-feature strong {{
  display: block;
  color: var(--ink) !important;
  font-size: 0.98rem !important;
  font-weight: 750 !important;
  margin-bottom: 0.35rem;
}}
.rl-feature p {{
  margin: 0 !important;
  font-size: 0.85rem !important;
  color: var(--muted) !important;
  line-height: 1.5 !important;
}}

/* 일반 카드 */
.rl-card, .uil-card {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.3rem 1.4rem;
  box-shadow: var(--shadow-sm);
  margin-bottom: 1rem;
}}
.rl-card-accent, .uil-card-accent {{
  border-left: 3px solid var(--teal);
  background: linear-gradient(90deg, #F0FDFA 0%, #FFFFFF 45%);
}}
.rl-card strong, .uil-card strong {{
  font-weight: 700 !important;
  color: var(--ink);
}}

/* 요약 박스 */
.rl-summary {{
  background: linear-gradient(135deg, #F0FDFA 0%, #FFFFFF 60%);
  border: 1px solid rgba(13,148,136,0.2);
  border-radius: var(--radius);
  padding: 1.15rem 1.3rem;
  margin: 1rem 0;
}}
.rl-summary-label {{
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0F766E !important;
  margin: 0 0 0.35rem !important;
}}
.rl-summary p {{
  margin: 0 !important;
  color: var(--ink-2) !important;
  font-size: 1rem !important;
  font-weight: 550 !important;
  line-height: 1.55 !important;
}}

/* 여정 카드 */
.rl-trips {{
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin: 0.75rem 0 1.25rem;
}}
.rl-trip {{
  display: grid;
  grid-template-columns: 72px 1fr auto;
  gap: 0.85rem;
  align-items: center;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0.95rem 1.1rem;
  box-shadow: var(--shadow-sm);
}}
.rl-trip-time {{
  font-family: var(--font-en) !important;
  font-weight: 700 !important;
  font-size: 0.88rem !important;
  color: var(--teal) !important;
  line-height: 1.35 !important;
}}
.rl-trip-time small {{
  display: block;
  color: var(--muted-2) !important;
  font-weight: 500 !important;
  font-size: 0.75rem !important;
}}
.rl-trip-route {{
  min-width: 0;
}}
.rl-trip-route strong {{
  display: block;
  color: var(--ink) !important;
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.rl-trip-route span {{
  display: block;
  margin-top: 0.2rem;
  color: var(--muted) !important;
  font-size: 0.8rem !important;
}}
.rl-trip-meta {{
  text-align: right;
  font-size: 0.8rem !important;
  color: var(--muted) !important;
  white-space: nowrap;
}}
.rl-trip-meta b {{
  display: block;
  color: var(--ink) !important;
  font-size: 0.95rem !important;
  font-weight: 750 !important;
}}

/* 배지 */
.uil-badge, .rl-badge {{
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem !important;
  font-weight: 750 !important;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}}
.uil-badge-free {{ background: #F1F5F9; color: #475569; }}
.uil-badge-pro {{
  background: linear-gradient(135deg, #CCFBF1, #99F6E4);
  color: #0F766E;
}}

/* 사용량 */
.uil-usage {{
  background: var(--card);
  border-radius: var(--radius-sm);
  padding: 1rem 1.1rem;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-sm);
  margin-bottom: 0.5rem;
}}
.uil-usage-bar {{
  height: 6px;
  background: #E2E8F0;
  border-radius: 999px;
  overflow: hidden;
  margin-top: 0.6rem;
}}
.uil-usage-fill {{
  height: 100%;
  background: linear-gradient(90deg, #14B8A6, #0D9488);
  border-radius: 999px;
  transition: width .3s ease;
}}
.uil-usage-fill.danger {{
  background: linear-gradient(90deg, #F59E0B, #EF4444);
}}

/* Pro CTA */
.uil-cta {{
  position: relative;
  overflow: hidden;
  background: linear-gradient(145deg, #0B1220 0%, #1E293B 55%, #0F766E 140%);
  color: #fff;
  border-radius: 20px;
  padding: 1.75rem 1.6rem;
  text-align: center;
  margin: 1.1rem 0 1.3rem;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: var(--shadow-lg);
}}
.uil-cta::before {{
  content: '';
  position: absolute;
  width: 200px; height: 200px;
  right: -40px; top: -60px;
  background: radial-gradient(circle, rgba(45,212,191,0.25), transparent 70%);
  pointer-events: none;
}}
.uil-cta h3 {{
  position: relative;
  color: #F8FAFC !important;
  margin: 0 0 0.4rem !important;
  font-size: 1.25rem !important;
  font-weight: 800 !important;
}}
.uil-cta p {{
  position: relative;
  color: #94A3B8 !important;
  margin: 0 0 1.1rem !important;
  font-size: 0.92rem !important;
}}
.uil-cta a {{
  position: relative;
  display: inline-block;
  background: linear-gradient(135deg, #2DD4BF, #0D9488);
  color: #fff !important;
  font-weight: 750 !important;
  font-size: 0.92rem !important;
  padding: 0.7rem 1.4rem;
  border-radius: 12px;
  text-decoration: none;
  box-shadow: 0 6px 18px rgba(13,148,136,0.4);
}}
.uil-cta a:hover {{ filter: brightness(1.06); }}

/* 요금제 카드 */
.rl-price-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}}
.rl-price {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1.6rem 1.5rem;
  box-shadow: var(--shadow-sm);
  position: relative;
}}
.rl-price.is-pro {{
  border: 1px solid rgba(13,148,136,0.45);
  box-shadow: 0 12px 36px rgba(13,148,136,0.12);
  background: linear-gradient(180deg, #F0FDFA 0%, #FFFFFF 40%);
}}
.rl-price.is-pro::after {{
  content: '추천';
  position: absolute;
  top: 14px; right: 14px;
  background: linear-gradient(135deg, #14B8A6, #0D9488);
  color: #fff;
  font-size: 0.68rem;
  font-weight: 750;
  padding: 0.22rem 0.55rem;
  border-radius: 999px;
  letter-spacing: 0.04em;
}}
.rl-price h3 {{
  margin: 0.55rem 0 0.15rem !important;
  font-size: 1.85rem !important;
  font-weight: 800 !important;
  color: var(--ink) !important;
  letter-spacing: -0.03em !important;
}}
.rl-price h3 small {{
  font-size: 0.9rem !important;
  font-weight: 500 !important;
  color: var(--muted) !important;
}}
.rl-price ul {{
  list-style: none;
  padding: 0;
  margin: 1.1rem 0 0;
}}
.rl-price li {{
  position: relative;
  padding: 0.35rem 0 0.35rem 1.5rem;
  color: var(--muted) !important;
  font-size: 0.9rem !important;
  line-height: 1.45 !important;
}}
.rl-price li::before {{
  content: '✓';
  position: absolute;
  left: 0;
  color: #0D9488;
  font-weight: 800;
}}
.rl-price-cta {{
  display: inline-block;
  margin-top: 1.2rem;
  background: linear-gradient(135deg, #14B8A6, #0D9488);
  color: #fff !important;
  padding: 0.65rem 1.2rem;
  border-radius: 12px;
  text-decoration: none;
  font-weight: 700 !important;
  font-size: 0.9rem !important;
  box-shadow: 0 6px 16px rgba(13,148,136,0.3);
}}

/* 다운로드 존 */
.rl-download-zone {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.35rem;
  margin: 1rem 0;
  box-shadow: var(--shadow-sm);
}}
.rl-download-zone .rl-dz-title {{
  margin: 0 0 0.2rem !important;
  font-size: 1rem !important;
  font-weight: 750 !important;
  color: var(--ink) !important;
}}
.rl-download-zone .rl-dz-cap {{
  margin: 0 0 0.9rem !important;
  font-size: 0.84rem !important;
  color: var(--muted) !important;
}}

/* 메트릭 */
div[data-testid="stMetric"] {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0.95rem 1rem;
  box-shadow: var(--shadow-sm);
}}
div[data-testid="stMetric"] label {{
  color: var(--muted) !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
  font-weight: 800 !important;
  font-size: 1.35rem !important;
  color: var(--ink) !important;
  letter-spacing: -0.03em;
}}

/* 버튼 */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
  background: linear-gradient(135deg, #14B8A6 0%, #0D9488 100%) !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  font-size: 0.95rem !important;
  padding: 0.65rem 1.2rem !important;
  box-shadow: 0 6px 16px rgba(13,148,136,0.28) !important;
  transition: all .15s ease !important;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {{
  filter: brightness(1.05);
  box-shadow: 0 8px 22px rgba(13,148,136,0.38) !important;
  transform: translateY(-1px);
}}
.stButton > button {{
  border-radius: 12px !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  border: 1px solid var(--line) !important;
  background: #FFFFFF !important;
  color: #334155 !important;
  transition: all .15s ease !important;
}}
.stButton > button:hover {{
  border-color: #CBD5E1 !important;
  background: #F8FAFC !important;
}}
.stDownloadButton > button {{
  background: linear-gradient(135deg, #0F172A, #1E293B) !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 12px !important;
  font-weight: 650 !important;
  font-size: 0.9rem !important;
  width: 100%;
  box-shadow: 0 4px 12px rgba(15,23,42,0.18) !important;
  padding: 0.7rem 1rem !important;
}}
.stDownloadButton > button:hover {{
  filter: brightness(1.08);
}}

/* 입력 필드 */
.stTextInput > div > div,
.stTextArea > div > div,
.stSelectbox > div > div {{
  border-radius: 12px !important;
  border-color: var(--line) !important;
  transition: border-color .15s, box-shadow .15s !important;
}}
.stTextArea textarea {{
  font-size: 0.95rem !important;
  line-height: 1.6 !important;
  min-height: 140px !important;
}}
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within {{
  border-color: rgba(13,148,136,0.55) !important;
  box-shadow: 0 0 0 3px var(--teal-glow) !important;
}}

/* 데이터프레임 */
div[data-testid="stDataFrame"] {{
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}}

/* expander */
[data-testid="stExpander"] {{
  background: var(--card);
  border: 1px solid var(--line) !important;
  border-radius: var(--radius-sm) !important;
  box-shadow: var(--shadow-sm);
}}

/* alerts */
[data-testid="stAlert"] {{
  border-radius: 12px !important;
}}

hr {{
  border: none;
  border-top: 1px solid var(--line);
  margin: 1.5rem 0;
}}

/* ── Footer (다크 톤 · 얇은 구분선) ── */
.rl-footer, .uil-footer {{
  margin-top: 2.75rem;
  padding: 1.35rem 0 1.6rem;
  border-top: 1px solid rgba(148, 163, 184, 0.22);
  background: transparent;
  letter-spacing: 0.01em;
}}
.rl-footer-inner {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.55rem 1.1rem;
  max-width: 100%;
}}
.rl-footer-copy {{
  margin: 0 !important;
  color: #94a3b8 !important;
  font-size: 0.8125rem !important; /* 13px */
  font-weight: 500 !important;
  line-height: 1.5 !important;
  white-space: normal;
}}
.rl-footer-copy strong {{
  color: #cbd5e1 !important;
  font-weight: 650 !important;
}}
.rl-footer-links {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.85rem;
  margin: 0;
  padding: 0;
  list-style: none;
}}
.rl-footer-links a {{
  color: #94a3b8 !important;
  font-size: 0.8125rem !important; /* 13px */
  font-weight: 600 !important;
  text-decoration: none !important;
  border-bottom: 1px solid transparent;
  transition: color 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
}}
.rl-footer-links a:hover {{
  color: #22d3ee !important;
  border-bottom-color: rgba(34, 211, 238, 0.45);
}}
.rl-footer-sep {{
  display: inline-block;
  width: 1px;
  height: 0.75rem;
  background: rgba(148, 163, 184, 0.35);
  flex-shrink: 0;
}}
.rl-footer-contact {{
  margin: 0.55rem 0 0 !important;
  font-size: 0.8rem !important;
  color: #64748b !important;
}}
.rl-footer-contact a {{
  color: #0d9488 !important;
  font-weight: 700 !important;
  text-decoration: none !important;
}}
.rl-footer-contact a:hover {{
  text-decoration: underline !important;
}}
.rl-footer-about {{
  margin: 0.55rem 0 0 !important;
  max-width: 46rem;
  font-size: 0.78rem !important;
  line-height: 1.55 !important;
  color: #64748b !important;
}}
.rl-footer-about strong {{
  color: #0f766e !important;
  font-weight: 700 !important;
}}
@media (max-width: 640px) {{
  .rl-footer, .uil-footer {{
    margin-top: 2rem;
    padding: 1.1rem 0 1.35rem;
  }}
  .rl-footer-inner {{
    flex-direction: column;
    align-items: flex-start;
    gap: 0.65rem;
  }}
  .rl-footer-copy {{
    font-size: 0.75rem !important; /* 12px */
  }}
  .rl-footer-links a {{
    font-size: 0.75rem !important;
  }}
  .rl-footer-sep {{
    display: none;
  }}
  .rl-footer-about {{
    font-size: 0.72rem !important;
  }}
}}

/* 로그인 유도 배너 */
.rl-login-nudge {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0.95rem 1.15rem;
  background: linear-gradient(90deg, #F0FDFA, #F8FAFC);
  border: 1px solid rgba(13,148,136,0.2);
  border-radius: var(--radius-sm);
  margin-bottom: 1.15rem;
}}
.rl-login-nudge strong {{
  color: var(--ink) !important;
  font-size: 0.92rem !important;
}}
.rl-login-nudge span {{
  color: var(--muted) !important;
  font-size: 0.85rem !important;
}}

/* 결과 헤더 */
.rl-result-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin: 1.5rem 0 1rem;
  flex-wrap: wrap;
}}
.rl-result-head h2 {{
  margin: 0 !important;
  font-size: 1.2rem !important;
}}
.rl-engine {{
  font-size: 0.75rem !important;
  font-weight: 700 !important;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  background: #F1F5F9;
  color: #475569 !important;
}}
.rl-engine.ai {{
  background: #CCFBF1;
  color: #0F766E !important;
}}

/* ── Mobile responsive (Streamlit) ── */
@media (max-width: 768px) {{
  html {{
    -webkit-text-size-adjust: 100%;
  }}

  .block-container {{
    padding-top: 0.75rem !important;
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    padding-bottom: 6.5rem !important; /* sticky CTA 여유 */
    max-width: 100% !important;
  }}

  /* 가로 컬럼 스택 — Streamlit columns */
  div[data-testid="stHorizontalBlock"] {{
    flex-direction: column !important;
    gap: 0.5rem !important;
  }}
  div[data-testid="stHorizontalBlock"] > div {{
    width: 100% !important;
    flex: 1 1 100% !important;
    min-width: 0 !important;
  }}

  .rl-hero {{
    padding: 1.25rem 1rem !important;
    border-radius: 16px !important;
  }}
  .rl-hero h1 {{
    font-size: 1.65rem !important;
    line-height: 1.25 !important;
  }}
  .rl-hero-sub {{
    font-size: 0.92rem !important;
  }}
  .rl-steps, .rl-features, .rl-price-grid {{
    grid-template-columns: 1fr !important;
  }}
  .rl-feature, .rl-step, .rl-card, .uil-card {{
    width: 100% !important;
    max-width: 100% !important;
  }}
  .rl-trip {{
    grid-template-columns: 1fr !important;
    gap: 0.4rem !important;
  }}
  .rl-trip-meta {{ text-align: left !important; }}

  /* 터치 타깃 */
  .stButton > button,
  .stDownloadButton > button,
  .stFormSubmitButton > button {{
    min-height: 3rem !important;
    width: 100% !important;
    font-size: 1rem !important;
    border-radius: 12px !important;
    padding: 0.75rem 1rem !important;
  }}
  .stTextInput input,
  .stNumberInput input,
  .stTextArea textarea,
  .stSelectbox div[data-baseweb="select"] > div {{
    min-height: 3rem !important;
    font-size: 16px !important; /* iOS 자동 줌 방지 */
  }}
  .stTextArea textarea {{
    min-height: 7rem !important;
  }}

  /* 사이드바 좁은 화면 */
  section[data-testid="stSidebar"] {{
    min-width: 0 !important;
  }}
  section[data-testid="stSidebar"] .stButton > button {{
    min-height: 2.85rem !important;
  }}

  /* 메트릭 카드 스택 여백 */
  div[data-testid="stMetric"] {{
    padding: 0.75rem !important;
  }}

  /* 모바일 하단 고정: 일지 작성 버튼 (primary) */
  div[data-testid="stAppViewContainer"] {{
    padding-bottom: 0 !important;
  }}
  /* 작성 화면 primary 버튼을 sticky처럼 — 마지막 primary 강조 */
  .stButton > button[kind="primary"],
  .stButton > button[data-testid="baseButton-primary"] {{
    position: sticky !important;
    bottom: 0.75rem !important;
    z-index: 100 !important;
    box-shadow: 0 8px 24px rgba(13, 148, 136, 0.45) !important;
  }}
}}

@media (max-width: 480px) {{
  .rl-hero h1 {{ font-size: 1.45rem !important; }}
  .block-container {{
    padding-left: 0.6rem !important;
    padding-right: 0.6rem !important;
  }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        f"""
<div class="rl-brand">
  {LOGO_SVG}
  <div class="rl-brand-text">
    <span class="rl-brand-name">{APP_TITLE}</span>
    <span class="rl-brand-en">{APP_SHORT}</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str | None = None, subtitle: str | None = None) -> None:
    """내부 페이지용 헤더 (홈 외)."""
    t = html.escape(title or APP_TITLE)
    sub = html.escape(subtitle or APP_TAGLINE)
    st.markdown(
        f"""
<div class="rl-page-head">
  <div class="rl-logo-wrap">{LOGO_SVG_LG}</div>
  <div>
    <h1 class="rl-title">{t}</h1>
    <p class="rl-sub">{sub}</p>
    <div class="rl-en">{APP_SHORT}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_landing_hero() -> None:
    """홈 상단 다크 프리미엄 히어로."""
    st.markdown(
        f"""
<div class="rl-hero">
  <div class="rl-hero-inner">
    <div class="rl-hero-top">
      {LOGO_SVG_LG}
      <span class="rl-hero-badge">✦ 회사 제출용 · 워터마크 0</span>
    </div>
    <h1>{APP_TITLE}<br/>한 줄 입력으로 끝.</h1>
    <p class="rl-hero-sub">{html.escape(APP_TAGLINE)} — 자연어로 쓰고, AI가 격식 있는 운행일지로 정리합니다.</p>
    <div class="rl-hero-pills">
      <div class="rl-pill"><span>✓</span> Excel · PDF · DOCX</div>
      <div class="rl-pill"><span>✓</span> 점심시간 자동 제외</div>
      <div class="rl-pill"><span>✓</span> Free 월 {FREE_MONTHLY_LIMIT}회</div>
      <div class="rl-pill"><span>✓</span> 업무용 격식 문체</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_steps() -> None:
    st.markdown(
        """
<div class="rl-steps">
  <div class="rl-step">
    <div class="rl-step-num">1</div>
    <strong>운행 내용 입력</strong>
    <p>출발·도착·목적지를 평소 말하듯 적습니다.</p>
  </div>
  <div class="rl-step">
    <div class="rl-step-num">2</div>
    <strong>AI 일지 생성</strong>
    <p>시간·거리·점심 제외까지 자동 검증합니다.</p>
  </div>
  <div class="rl-step">
    <div class="rl-step-num">3</div>
    <strong>문서 다운로드</strong>
    <p>워터마크 없는 제출용 파일로 바로 받습니다.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(subtitle: str | None = None) -> None:
    """하위 호환 — 홈에서는 랜딩 히어로 사용."""
    render_landing_hero()
    render_steps()


def render_section_label(text: str) -> None:
    st.markdown(
        f"""
<div class="rl-section-label">
  <span class="rl-dot"></span>
  <h2>{html.escape(text)}</h2>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_feature_cards() -> None:
    st.markdown(
        """
<div class="rl-features">
  <div class="rl-feature">
    <div class="rl-feature-icon">📄</div>
    <strong>클린 제출 문서</strong>
    <p>Excel · PDF · DOCX 모두 워터마크 없이 회사 제출용으로 바로 사용.</p>
  </div>
  <div class="rl-feature">
    <div class="rl-feature-icon">⏱</div>
    <strong>스마트 시간 검증</strong>
    <p>점심 제외 · 거리 · 평균 속도까지 자동으로 크로스체크.</p>
  </div>
  <div class="rl-feature">
    <div class="rl-feature-icon">✍️</div>
    <strong>업무용 격식 문체</strong>
    <p>구어체 입력을 공식 운행일지 톤으로 다듬어 드립니다.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_usage_bar(used: int, limit: int, is_pro: bool) -> None:
    if is_pro:
        st.markdown(
            """
<div class="uil-usage">
  <span class="uil-badge uil-badge-pro">Pro</span>
  &nbsp; 무제한 생성 · 광고 없음
</div>
            """,
            unsafe_allow_html=True,
        )
        return

    pct = min(100, int((used / max(limit, 1)) * 100))
    danger = " danger" if used >= limit else ""
    remain = max(0, limit - used)
    st.markdown(
        f"""
<div class="uil-usage">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span><span class="uil-badge uil-badge-free">Free</span>
    &nbsp; 이번 달 <strong style="color:#0B1220;">{used}/{limit}</strong>회</span>
    <span style="color:#94A3B8;font-size:0.82rem;">잔여 {remain}회</span>
  </div>
  <div class="uil-usage-bar">
    <div class="uil-usage-fill{danger}" style="width:{pct}%;"></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_pro_cta(payment_url: str) -> None:
    url = html.escape(payment_url, quote=True)
    st.markdown(
        f"""
<div class="uil-cta">
  <h3>Pro로 업그레이드</h3>
  <p>월 10회 제한 해제 · 광고 제거 · 무제한 생성</p>
  <a href="{url}" target="_blank" rel="noopener">월 9,900원으로 시작</a>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_pricing_cards(payment_url: str, free_limit: int = FREE_MONTHLY_LIMIT) -> None:
    url = html.escape(payment_url, quote=True)
    st.markdown(
        f"""
<div class="rl-price-grid">
  <div class="rl-price">
    <span class="uil-badge uil-badge-free">Free</span>
    <h3>₩0 <small>/ 월</small></h3>
    <ul>
      <li>월 {free_limit}회 생성</li>
      <li>Excel · PDF · DOCX 클린 다운로드</li>
      <li>워터마크 없음</li>
      <li>개인 설정 저장</li>
    </ul>
  </div>
  <div class="rl-price is-pro">
    <span class="uil-badge uil-badge-pro">Pro</span>
    <h3>₩9,900 <small>/ 월</small></h3>
    <ul>
      <li>무제한 생성</li>
      <li>문서 무제한 다운로드</li>
      <li>광고 완전 제거</li>
      <li>우선 지원</li>
    </ul>
    <a class="rl-price-cta" href="{url}" target="_blank" rel="noopener">Pro 시작하기</a>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_trip_cards(trips: list[dict]) -> None:
    if not trips:
        return
    parts = ['<div class="rl-trips">']
    for t in trips:
        dep = html.escape(str(t.get("depart_time") or "—"))
        arr = html.escape(str(t.get("arrive_time") or "—"))
        fr = html.escape(str(t.get("from") or "—"))
        to = html.escape(str(t.get("to") or "—"))
        purpose = html.escape(str(t.get("purpose") or ""))
        dist = t.get("distance_km", "—")
        dur = html.escape(str(t.get("duration_display") or "—"))
        parts.append(
            f"""
<div class="rl-trip">
  <div class="rl-trip-time">{dep}<small>→ {arr}</small></div>
  <div class="rl-trip-route">
    <strong>{fr} → {to}</strong>
    <span>{purpose or '업무 운행'}</span>
  </div>
  <div class="rl-trip-meta">
    <b>{dist} km</b>
    {dur}
  </div>
</div>
            """
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_summary_box(text: str) -> None:
    st.markdown(
        f"""
<div class="rl-summary">
  <p class="rl-summary-label">운행 요약</p>
  <p>{html.escape(text)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_login_nudge() -> None:
    st.markdown(
        f"""
<div class="rl-login-nudge">
  <div style="font-size:1.25rem;">🔐</div>
  <div>
    <strong>왼쪽에서 로그인하면 바로 생성할 수 있어요</strong><br/>
    <span>Free 요금제는 월 {FREE_MONTHLY_LIMIT}회 · 가입 1분이면 충분합니다</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """사이트 하단 푸터 — CoreLabs 저작권 · 법적 링크 · About."""
    st.markdown(
        f"""
<div class="rl-footer" role="contentinfo">
  <div class="rl-footer-inner">
    <p class="rl-footer-copy">
      © 2026 CoreLabs. All rights reserved.
      <span style="opacity:0.55"> · </span>
      <strong>{APP_TITLE}</strong>
      <span style="opacity:0.55">({APP_SHORT})</span>
      <span style="opacity:0.45"> · Powered by CoreLabs</span>
    </p>
    <span class="rl-footer-sep" aria-hidden="true"></span>
    <nav class="rl-footer-links" aria-label="법적 고지">
      <a href="/회사소개" target="_self">About</a>
      <a href="/이용약관" target="_self">이용약관</a>
      <a href="/개인정보처리방침" target="_self">개인정보처리방침</a>
      <a href="mailto:corelabs.studio@gmail.com">문의</a>
    </nav>
  </div>
  <p class="rl-footer-contact">
    ✉ 문의:
    <a href="mailto:corelabs.studio@gmail.com">corelabs.studio@gmail.com</a>
  </p>
  <p class="rl-footer-about">
    로드로그(RoadLog)는 데이터의 본질을 연구하고 가치를 창출하는 기술 스튜디오,
    <strong>코어랩스(CoreLabs)</strong>에 의해 운영됩니다.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )
