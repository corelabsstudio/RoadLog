"""
기업용 모드 (Enterprise Mode)
- 팀원·좌석(Seat) 관리 (session_state 시뮬레이션)
- 팀원 통합 통계 (Plotly)
- 팀 일지 취합 · 승인/반려
- 공통 거점 · 정책 (Global Config)
데이터:
  data/admin/company_config.json
  data/team_logs.csv
  st.session_state (팀원·좌석 — DB 연동 전 가상 상태)
"""

from __future__ import annotations

import csv
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.config import (
    COLORS,
    DATA_DIR,
    ENTERPRISE_BASE_SEATS,
    ENTERPRISE_PRICE_KRW,
    ENTERPRISE_SEAT_PRICE_KRW,
)
from modules.styles import render_footer, render_page_header

ADMIN_DIR = DATA_DIR / "admin"
ADMIN_DIR.mkdir(parents=True, exist_ok=True)
COMPANY_CONFIG_PATH = ADMIN_DIR / "company_config.json"
TEAM_LOGS_CSV = DATA_DIR / "team_logs.csv"

# ── 좌석·팀원 세션 키 ──────────────────────────────────
SK_MEMBERS = "ent_team_members"
SK_EXTRA_SEATS = "ent_extra_seats"
SK_SEAT_FLASH = "ent_seat_flash"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEFAULT_COMPANY_CONFIG: dict[str, Any] = {
    "company_name": "",
    "policy_note": "업무 운행만 기록하며, 사적 이용은 제외합니다.",
    "require_approval": True,
    "lunch_start": "12:00",
    "lunch_end": "13:00",
    "exclude_lunch": True,
    "hubs": [
        {"name": "본사", "address": ""},
    ],
    "allowed_purposes": ["업무 출장", "고객 미팅", "납품", "현장 점검", "업무 복귀", "중식"],
    "updated_at": None,
}

TEAM_LOG_FIELDS = [
    "id",
    "created_at",
    "member_email",
    "member_name",
    "date",
    "vehicle",
    "total_distance_km",
    "summary",
    "status",  # pending | approved | rejected
    "reviewer_note",
    "reviewed_at",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_company_config() -> dict[str, Any]:
    if not COMPANY_CONFIG_PATH.exists():
        cfg = {**DEFAULT_COMPANY_CONFIG, "updated_at": _now()}
        save_company_config(cfg)
        return cfg
    try:
        with open(COMPANY_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_COMPANY_CONFIG, **data}
    except Exception:
        return {**DEFAULT_COMPANY_CONFIG}


def save_company_config(cfg: dict[str, Any]) -> dict[str, Any]:
    clean = {**DEFAULT_COMPANY_CONFIG, **cfg, "updated_at": _now()}
    COMPANY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPANY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    return clean


def _ensure_team_logs_csv() -> None:
    if TEAM_LOGS_CSV.exists():
        return
    TEAM_LOGS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(TEAM_LOGS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TEAM_LOG_FIELDS)
        w.writeheader()
    # 데모 시드 (비어 있으면 차트/테이블 확인용)
    seed = [
        {
            "id": "demo1",
            "created_at": _now(),
            "member_email": "kim@company.com",
            "member_name": "김대리",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "vehicle": "12가3456",
            "total_distance_km": "37.0",
            "summary": "강남 고객사 미팅 후 복귀",
            "status": "pending",
            "reviewer_note": "",
            "reviewed_at": "",
        },
        {
            "id": "demo2",
            "created_at": _now(),
            "member_email": "lee@company.com",
            "member_name": "이과장",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "vehicle": "34나7890",
            "total_distance_km": "52.5",
            "summary": "판교 협력사 현장 점검",
            "status": "approved",
            "reviewer_note": "확인",
            "reviewed_at": _now(),
        },
        {
            "id": "demo3",
            "created_at": _now(),
            "member_email": "park@company.com",
            "member_name": "박사원",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "vehicle": "12가3456",
            "total_distance_km": "18.0",
            "summary": "송파 거래처 방문",
            "status": "rejected",
            "reviewer_note": "거리 재확인 필요",
            "reviewed_at": _now(),
        },
    ]
    append_team_logs(seed)


def load_team_logs_df() -> pd.DataFrame:
    _ensure_team_logs_csv()
    try:
        df = pd.read_csv(TEAM_LOGS_CSV, encoding="utf-8-sig")
    except Exception:
        df = pd.DataFrame(columns=TEAM_LOG_FIELDS)
    for col in TEAM_LOG_FIELDS:
        if col not in df.columns:
            df[col] = ""
    return df


def save_team_logs_df(df: pd.DataFrame) -> None:
    TEAM_LOGS_CSV.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for col in TEAM_LOG_FIELDS:
        if col not in out.columns:
            out[col] = ""
    out[TEAM_LOG_FIELDS].to_csv(TEAM_LOGS_CSV, index=False, encoding="utf-8-sig")


def append_team_logs(rows: list[dict]) -> None:
    _ensure_team_logs_csv()
    df = load_team_logs_df()
    add = pd.DataFrame(rows)
    for col in TEAM_LOG_FIELDS:
        if col not in add.columns:
            add[col] = ""
    df = pd.concat([df, add[TEAM_LOG_FIELDS]], ignore_index=True)
    save_team_logs_df(df)


def update_log_status(log_id: str, status: str, note: str = "") -> bool:
    df = load_team_logs_df()
    if df.empty or "id" not in df.columns:
        return False
    mask = df["id"].astype(str) == str(log_id)
    if not mask.any():
        return False
    df.loc[mask, "status"] = status
    df.loc[mask, "reviewer_note"] = note
    df.loc[mask, "reviewed_at"] = _now()
    save_team_logs_df(df)
    return True


# ── 팀원·좌석 (session_state 시뮬레이션) ──────────────


def _seed_demo_members() -> list[dict[str, str]]:
    """데모용 가상 팀원 3명 (기본 5석 중 3석 사용)."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "id": "m-admin",
            "name": "홍길동",
            "email": "admin@company.com",
            "joined_at": today,
            "role": "관리자",
        },
        {
            "id": "m-kim",
            "name": "김대리",
            "email": "kim@company.com",
            "joined_at": today,
            "role": "멤버",
        },
        {
            "id": "m-lee",
            "name": "이과장",
            "email": "lee@company.com",
            "joined_at": today,
            "role": "멤버",
        },
    ]


def init_team_seat_state() -> None:
    """팀원 목록·추가 좌석 수를 session_state에 초기화."""
    if SK_MEMBERS not in st.session_state:
        st.session_state[SK_MEMBERS] = _seed_demo_members()
    if SK_EXTRA_SEATS not in st.session_state:
        st.session_state[SK_EXTRA_SEATS] = 0


def get_members() -> list[dict[str, str]]:
    init_team_seat_state()
    return list(st.session_state[SK_MEMBERS])


def get_seat_snapshot() -> dict[str, Any]:
    """좌석 현황 요약 계산."""
    init_team_seat_state()
    members = st.session_state[SK_MEMBERS]
    used = len(members)
    extra = int(st.session_state[SK_EXTRA_SEATS] or 0)
    total_seats = ENTERPRISE_BASE_SEATS + extra
    free = max(0, total_seats - used)
    over = max(0, used - total_seats)
    monthly_base = ENTERPRISE_PRICE_KRW
    monthly_extra = extra * ENTERPRISE_SEAT_PRICE_KRW
    monthly_total = monthly_base + monthly_extra
    return {
        "used": used,
        "extra_seats": extra,
        "base_seats": ENTERPRISE_BASE_SEATS,
        "total_seats": total_seats,
        "free_seats": free,
        "over_capacity": over,
        "is_full": free == 0 and over == 0,
        "needs_seats": used >= total_seats,
        "monthly_base": monthly_base,
        "monthly_extra": monthly_extra,
        "monthly_total": monthly_total,
        "seat_unit_price": ENTERPRISE_SEAT_PRICE_KRW,
    }


def invite_member(email: str, name: str = "", role: str = "멤버") -> tuple[bool, str]:
    """이메일로 팀원 초대. 좌석이 부족하면 실패."""
    init_team_seat_state()
    email = (email or "").strip().lower()
    if not email or not _EMAIL_RE.match(email):
        return False, "올바른 이메일 주소를 입력해 주세요."
    members = st.session_state[SK_MEMBERS]
    if any(m.get("email", "").lower() == email for m in members):
        return False, "이미 팀에 등록된 이메일입니다."
    snap = get_seat_snapshot()
    if snap["used"] >= snap["total_seats"]:
        return (
            False,
            "좌석이 부족합니다. 아래에서 좌석을 추가한 뒤 다시 초대해 주세요.",
        )
    display_name = (name or "").strip() or email.split("@")[0]
    members.append(
        {
            "id": f"m-{uuid.uuid4().hex[:8]}",
            "name": display_name,
            "email": email,
            "joined_at": datetime.now().strftime("%Y-%m-%d"),
            "role": role or "멤버",
        }
    )
    st.session_state[SK_MEMBERS] = members
    return True, f"{display_name}({email}) 님을 초대했습니다. 좌석 1석이 사용 처리됩니다."


def remove_member(member_id: str) -> tuple[bool, str]:
    """팀원 제명. 관리자 계정은 보호."""
    init_team_seat_state()
    members = st.session_state[SK_MEMBERS]
    target = next((m for m in members if m.get("id") == member_id), None)
    if not target:
        return False, "해당 팀원을 찾을 수 없습니다."
    if target.get("role") == "관리자":
        return False, "관리자 계정은 제명할 수 없습니다."
    st.session_state[SK_MEMBERS] = [m for m in members if m.get("id") != member_id]
    return True, f"{target.get('name')} 님을 팀에서 제외했습니다. 좌석 1석이 확보되었습니다."


def purchase_extra_seats(count: int = 1) -> tuple[bool, str]:
    """추가 좌석 결제 시뮬레이션."""
    init_team_seat_state()
    count = max(1, int(count or 1))
    st.session_state[SK_EXTRA_SEATS] = int(st.session_state[SK_EXTRA_SEATS] or 0) + count
    fee = count * ENTERPRISE_SEAT_PRICE_KRW
    snap = get_seat_snapshot()
    st.session_state[SK_SEAT_FLASH] = (
        f"좌석 {count}석이 추가되었습니다. "
        f"월 +₩{fee:,} · 총 좌석 {snap['total_seats']}석 · 월 합계 ₩{snap['monthly_total']:,}"
    )
    return True, st.session_state[SK_SEAT_FLASH]


def _fmt_won(n: int) -> str:
    return f"₩{int(n):,}"


def _render_seat_overview_cards(snap: dict[str, Any]) -> None:
    """상단 좌석·요금 현황 카드 (다크 + 시안 톤)."""
    used, total = snap["used"], snap["total_seats"]
    free = snap["free_seats"]
    pct = min(100, int(round((used / total) * 100))) if total else 0
    bar_color = "#22d3ee" if free > 0 else ("#f59e0b" if snap["over_capacity"] == 0 else "#f87171")
    if free == 0 and not snap["over_capacity"]:
        status_label = "좌석 가득 참"
        status_color = "#fbbf24"
    elif snap["over_capacity"] > 0:
        status_label = "좌석 초과"
        status_color = "#f87171"
    else:
        status_label = "정상 운영"
        status_color = "#34d399"

    base_label = f"기본 {snap['base_seats']}인"
    extra_label = (
        f" + 추가 {snap['extra_seats']}석" if snap["extra_seats"] else ""
    )

    html_block = f"""
<div style="
  display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;
  margin:0 0 1.1rem 0;">
  <div style="
    background:linear-gradient(165deg,#0b1220 0%,#0f172a 100%);
    border:1px solid rgba(34,211,238,0.28);border-radius:16px;padding:1.05rem 1.15rem;
    box-shadow:0 0 0 1px rgba(34,211,238,0.06),0 12px 32px rgba(2,6,23,0.35);">
    <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.06em;color:#67e8f9;
      text-transform:uppercase;margin-bottom:0.45rem;">현재 좌석 사용 현황</div>
    <div style="font-size:1.65rem;font-weight:800;color:#f8fafc;letter-spacing:-0.03em;line-height:1.15;">
      {used}<span style="font-size:1rem;font-weight:600;color:#94a3b8;"> / {total}명</span>
    </div>
    <div style="margin-top:0.35rem;font-size:0.8rem;color:#94a3b8;">
      {html.escape(base_label)}{html.escape(extra_label)}
    </div>
    <div style="margin-top:0.75rem;height:6px;background:rgba(148,163,184,0.18);
      border-radius:999px;overflow:hidden;">
      <div style="height:100%;width:{pct}%;background:{bar_color};border-radius:999px;"></div>
    </div>
    <div style="margin-top:0.55rem;font-size:0.78rem;color:{status_color};font-weight:700;">
      ● {status_label} · 여유 {free}석
    </div>
  </div>

  <div style="
    background:linear-gradient(165deg,#0b1220 0%,#0f172a 100%);
    border:1px solid rgba(148,163,184,0.16);border-radius:16px;padding:1.05rem 1.15rem;">
    <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.06em;color:#94a3b8;
      text-transform:uppercase;margin-bottom:0.45rem;">월 예상 요금</div>
    <div style="font-size:1.65rem;font-weight:800;color:#f8fafc;letter-spacing:-0.03em;">
      {_fmt_won(snap['monthly_total'])}
    </div>
    <div style="margin-top:0.45rem;font-size:0.8rem;color:#94a3b8;line-height:1.45;">
      기본 패키지 {_fmt_won(snap['monthly_base'])}<br/>
      추가 좌석 {_fmt_won(snap['monthly_extra'])}
      <span style="color:#64748b;"> (석당 {_fmt_won(snap['seat_unit_price'])})</span>
    </div>
  </div>

  <div style="
    background:linear-gradient(165deg,#0b1220 0%,#0f172a 100%);
    border:1px solid rgba(148,163,184,0.16);border-radius:16px;padding:1.05rem 1.15rem;">
    <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.06em;color:#94a3b8;
      text-transform:uppercase;margin-bottom:0.45rem;">확장 가이드</div>
    <div style="font-size:0.9rem;color:#e2e8f0;line-height:1.5;font-weight:600;">
      기본 {snap['base_seats']}인 포함<br/>
      <span style="color:#67e8f9;">추가 1인 = {_fmt_won(snap['seat_unit_price'])}/월</span>
    </div>
    <div style="margin-top:0.55rem;font-size:0.78rem;color:#94a3b8;line-height:1.4;">
      인원 초대 시 좌석이 자동 차감됩니다.<br/>
      세금계산서 발행 가능
    </div>
  </div>
</div>
"""
    st.markdown(html_block, unsafe_allow_html=True)


def _render_team_seats() -> None:
    """팀원 관리 + 좌석 확장 UI."""
    init_team_seat_state()
    snap = get_seat_snapshot()

    st.markdown("### 팀원 · 좌석 관리")
    st.caption(
        "Enterprise는 기본 5인 패키지입니다. 팀원을 초대하면 좌석이 사용되며, "
        "기본 인원을 초과하면 좌석을 추가해야 합니다."
    )

    flash = st.session_state.pop(SK_SEAT_FLASH, None)
    if flash:
        st.success(flash)

    _render_seat_overview_cards(snap)

    # Streamlit metric 보조 요약
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("사용 중", f"{snap['used']}명", help="현재 팀에 속한 인원")
    m2.metric("보유 좌석", f"{snap['total_seats']}석", delta=f"기본 {snap['base_seats']}")
    m3.metric("여유 좌석", f"{snap['free_seats']}석")
    m4.metric("월 합계", _fmt_won(snap["monthly_total"]))

    # 좌석 부족 경고
    if snap["needs_seats"] or snap["over_capacity"] > 0:
        st.warning(
            "**좌석이 부족합니다.** 새 팀원을 초대하려면 아래에서 좌석을 추가해 주세요. "
            f"(추가 1석 = {_fmt_won(snap['seat_unit_price'])}/월)"
        )

    st.markdown("---")

    # ── 초대 + 좌석 추가 ──────────────────────────────
    col_invite, col_seat = st.columns([1.35, 1], gap="large")

    with col_invite:
        st.markdown("#### 팀원 초대")
        st.caption("이메일로 초대하면 즉시 좌석 1석이 사용됩니다. (시뮬레이션)")
        with st.form("ent_invite_form", clear_on_submit=True):
            inv_email = st.text_input(
                "이메일",
                placeholder="colleague@company.com",
                key="ent_invite_email",
            )
            ic1, ic2 = st.columns(2)
            with ic1:
                inv_name = st.text_input("이름 (선택)", placeholder="홍길동")
            with ic2:
                inv_role = st.selectbox("역할", options=["멤버", "매니저"], index=0)
            can_invite = snap["free_seats"] > 0
            submitted = st.form_submit_button(
                "초대하기" if can_invite else "좌석 부족 · 초대 불가",
                type="primary",
                disabled=not can_invite,
                use_container_width=True,
            )
            if submitted:
                ok, msg = invite_member(inv_email, inv_name, inv_role)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        if not can_invite:
            st.info("여유 좌석이 없습니다. 오른쪽에서 좌석을 추가한 뒤 초대해 주세요.")

    with col_seat:
        st.markdown("#### 좌석 추가 결제")
        st.caption(
            f"기본 {ENTERPRISE_BASE_SEATS}인 초과 시 · "
            f"석당 {_fmt_won(ENTERPRISE_SEAT_PRICE_KRW)}/월"
        )
        add_n = st.number_input(
            "추가할 좌석 수",
            min_value=1,
            max_value=50,
            value=1,
            step=1,
            key="ent_add_seat_n",
        )
        est = int(add_n) * ENTERPRISE_SEAT_PRICE_KRW
        st.markdown(
            f"""
<div style="
  background:rgba(15,23,42,0.92);border:1px solid rgba(34,211,238,0.22);
  border-radius:12px;padding:0.85rem 1rem;margin:0.4rem 0 0.75rem;">
  <div style="font-size:0.78rem;color:#94a3b8;">결제 예상 (월 추가)</div>
  <div style="font-size:1.35rem;font-weight:800;color:#67e8f9;margin-top:0.15rem;">
    +{_fmt_won(est)}
  </div>
  <div style="font-size:0.78rem;color:#94a3b8;margin-top:0.25rem;">
    추가 후 총 좌석 {snap['total_seats'] + int(add_n)}석 ·
    월 합계 {_fmt_won(snap['monthly_total'] + est)}
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
        # 좌석 부족 시에만 primary 강조, 그 외에도 확장 가능
        seat_btn_label = (
            "좌석 추가 결제"
            if snap["needs_seats"]
            else "좌석 추가하기"
        )
        if st.button(
            seat_btn_label,
            type="primary" if snap["needs_seats"] else "secondary",
            use_container_width=True,
            key="btn_buy_seats",
        ):
            ok, msg = purchase_extra_seats(int(add_n))
            if ok:
                st.rerun()
            else:
                st.error(msg)

    st.markdown("---")
    st.markdown("#### 팀원 목록")

    members = get_members()
    if not members:
        st.info("등록된 팀원이 없습니다. 위 양식으로 초대하세요.")
        return

    # 표시용 테이블
    table_df = pd.DataFrame(
        [
            {
                "이름": m.get("name", ""),
                "이메일": m.get("email", ""),
                "가입일": m.get("joined_at", ""),
                "역할": m.get("role", "멤버"),
            }
            for m in members
        ]
    )
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "이름": st.column_config.TextColumn("이름", width="medium"),
            "이메일": st.column_config.TextColumn("이메일", width="large"),
            "가입일": st.column_config.TextColumn("가입일", width="small"),
            "역할": st.column_config.TextColumn("역할", width="small"),
        },
    )

    st.markdown("##### 멤버 제명")
    st.caption("제명 시 해당 좌석이 즉시 확보됩니다. 관리자 계정은 보호됩니다.")
    for m in members:
        mid = m.get("id", "")
        is_admin_role = m.get("role") == "관리자"
        r1, r2, r3, r4 = st.columns([1.2, 1.8, 0.8, 0.9])
        r1.write(m.get("name", ""))
        r2.write(m.get("email", ""))
        r3.write(m.get("role", ""))
        with r4:
            if is_admin_role:
                st.caption("보호됨")
            else:
                if st.button(
                    "삭제",
                    key=f"rm_{mid}",
                    type="secondary",
                    use_container_width=True,
                ):
                    ok, msg = remove_member(mid)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # 디버그/리셋 (개발용, 접힘)
    with st.expander("시뮬레이션 초기화", expanded=False):
        st.caption("DB 연동 전 가상 데이터입니다. 초기화하면 데모 팀원 3명·추가 좌석 0으로 돌아갑니다.")
        if st.button("팀원·좌석 초기화", key="ent_reset_seats"):
            st.session_state[SK_MEMBERS] = _seed_demo_members()
            st.session_state[SK_EXTRA_SEATS] = 0
            st.success("초기화되었습니다.")
            st.rerun()


# ── UI ────────────────────────────────────────────────


def render_enterprise_view() -> None:
    """기업용 관리자 대시보드 (plan_type=enterprise 전용)."""
    render_page_header(
        "기업용 관리자",
        "팀원·좌석 관리 · 팀 통계 · 일지 승인 · 공통 정책",
    )

    tab_seats, tab_stats, tab_approve, tab_policy = st.tabs(
        ["👥 팀원·좌석", "📊 팀 통계", "✅ 일지 승인", "⚙️ 공통 정책"]
    )

    with tab_seats:
        _render_team_seats()
    with tab_stats:
        _render_team_stats()
    with tab_approve:
        _render_approval_table()
    with tab_policy:
        _render_global_config()

    render_footer()


def _render_team_stats() -> None:
    st.markdown("### 팀원 통합 통계")
    df = load_team_logs_df()
    if df.empty:
        st.info("아직 팀 일지 데이터가 없습니다. (`data/team_logs.csv`)")
        return

    # 숫자 변환
    dist = pd.to_numeric(df.get("total_distance_km"), errors="coerce").fillna(0)
    df = df.copy()
    df["_dist"] = dist

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 일지", f"{len(df)}건")
    c2.metric("승인 대기", f"{(df['status'] == 'pending').sum()}건")
    c3.metric("승인 완료", f"{(df['status'] == 'approved').sum()}건")
    c4.metric("총 주행거리", f"{df['_dist'].sum():,.1f} km")

    st.markdown("#### 팀원별 주행거리")
    by_member = (
        df.groupby(df["member_name"].fillna(df["member_email"]), dropna=False)["_dist"]
        .sum()
        .reset_index()
    )
    by_member.columns = ["member", "distance_km"]
    fig = px.bar(
        by_member,
        x="member",
        y="distance_km",
        labels={"member": "팀원", "distance_km": "거리 (km)"},
        text="distance_km",
        color_discrete_sequence=[COLORS.get("teal", "#0D9488")],
    )
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=360,
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(color=COLORS.get("navy", "#111827")),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 상태 분포")
    status_df = df["status"].fillna("pending").value_counts().reset_index()
    status_df.columns = ["status", "count"]
    fig2 = px.pie(
        status_df,
        names="status",
        values="count",
        color="status",
        color_discrete_map={
            "pending": "#F59E0B",
            "approved": "#0D9488",
            "rejected": "#DC2626",
        },
    )
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig2, use_container_width=True)


def _render_approval_table() -> None:
    st.markdown("### 팀원 일지 취합 · 승인/반려")
    df = load_team_logs_df()
    if df.empty:
        st.info("취합된 일지가 없습니다.")
        return

    filter_status = st.selectbox(
        "상태 필터",
        options=["전체", "pending", "approved", "rejected"],
        format_func=lambda x: {
            "전체": "전체",
            "pending": "승인 대기",
            "approved": "승인",
            "rejected": "반려",
        }.get(x, x),
    )
    view = df.copy()
    if filter_status != "전체":
        view = view[view["status"] == filter_status]

    show_cols = [
        c
        for c in [
            "id",
            "date",
            "member_name",
            "member_email",
            "vehicle",
            "total_distance_km",
            "summary",
            "status",
            "reviewer_note",
        ]
        if c in view.columns
    ]
    st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

    st.markdown("#### 승인 처리")
    ids = view["id"].astype(str).tolist() if "id" in view.columns else []
    if not ids:
        return
    c1, c2 = st.columns(2)
    with c1:
        log_id = st.selectbox("일지 ID", options=ids)
    with c2:
        action = st.selectbox("처리", options=["approved", "rejected", "pending"], format_func=lambda x: {
            "approved": "승인",
            "rejected": "반려",
            "pending": "대기 복귀",
        }.get(x, x))
    note = st.text_input("검토 메모", placeholder="반려 사유 등")
    if st.button("적용", type="primary", key="btn_apply_status"):
        if update_log_status(log_id, action, note):
            st.success(f"{log_id} → {action}")
            st.rerun()
        else:
            st.error("처리에 실패했습니다.")


def _render_global_config() -> None:
    st.markdown("### 공통 거점 및 정책 (Global Config)")
    st.caption(f"저장 위치: `{COMPANY_CONFIG_PATH}`")
    cfg = load_company_config()

    with st.form("company_global_config"):
        company_name = st.text_input("회사명", value=cfg.get("company_name") or "")
        policy_note = st.text_area(
            "운행 정책 안내",
            value=cfg.get("policy_note") or "",
            height=100,
        )
        require_approval = st.checkbox(
            "팀원 일지 관리자 승인 필수",
            value=bool(cfg.get("require_approval", True)),
        )
        lc1, lc2 = st.columns(2)
        with lc1:
            lunch_start = st.text_input("공통 점심 시작", value=cfg.get("lunch_start") or "12:00")
        with lc2:
            lunch_end = st.text_input("공통 점심 종료", value=cfg.get("lunch_end") or "13:00")
        exclude_lunch = st.checkbox(
            "점심 구간 운행시간 제외",
            value=bool(cfg.get("exclude_lunch", True)),
        )

        st.markdown("#### 공통 거점 (한 줄에 하나: 이름 | 주소)")
        hubs = cfg.get("hubs") or []
        hubs_text = "\n".join(
            f"{h.get('name', '')} | {h.get('address', '')}".rstrip(" |")
            for h in hubs
            if h.get("name")
        )
        hubs_raw = st.text_area("거점 목록", value=hubs_text, height=120)

        purposes = cfg.get("allowed_purposes") or []
        purposes_raw = st.text_input(
            "허용 운행 목적 (쉼표 구분)",
            value=", ".join(purposes),
        )

        if st.form_submit_button("정책 저장", type="primary"):
            new_hubs = []
            for line in hubs_raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    name, addr = line.split("|", 1)
                else:
                    name, addr = line, ""
                new_hubs.append({"name": name.strip(), "address": addr.strip()})
            new_purposes = [p.strip() for p in purposes_raw.split(",") if p.strip()]
            save_company_config(
                {
                    **cfg,
                    "company_name": company_name,
                    "policy_note": policy_note,
                    "require_approval": require_approval,
                    "lunch_start": lunch_start,
                    "lunch_end": lunch_end,
                    "exclude_lunch": exclude_lunch,
                    "hubs": new_hubs,
                    "allowed_purposes": new_purposes,
                }
            )
            st.success("공통 정책이 저장되었습니다.")
            st.rerun()

    st.markdown("---")
    st.json(load_company_config())
