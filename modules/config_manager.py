"""
사용자별 설정 관리 UI
- 점심시간, 차량번호, 자주 가는 곳, 회사/운전자명 등
- Supabase 또는 로컬 JSON 저장
"""

from __future__ import annotations

import streamlit as st

from modules import db
from modules.auth import current_user, require_login


def render_settings_page() -> None:
    """설정 탭/페이지 렌더링."""
    st.caption("계정별로 저장되며 생성 시 자동 반영됩니다.")

    if not require_login("설정을 저장하려면 로그인해 주세요."):
        st.markdown(
            """
<div class="uil-card uil-card-accent">
  <strong>저장 항목</strong><br/>
  차량번호 · 운전자/회사명 · 점심시간(자동 제외) · 자주 가는 곳 · 기본 목적
</div>
            """,
            unsafe_allow_html=True,
        )
        return

    user = current_user()
    assert user is not None
    settings = db.load_settings(user["email"])

    with st.form("user_settings_form"):
        st.markdown("#### 기본")
        c1, c2 = st.columns(2)
        with c1:
            vehicle = st.text_input(
                "차량번호",
                value=settings.get("vehicle_number", ""),
                placeholder="12가3456",
            )
            driver = st.text_input(
                "운전자명",
                value=settings.get("driver_name", ""),
                placeholder="홍길동",
            )
        with c2:
            company = st.text_input(
                "회사명",
                value=settings.get("company_name", ""),
                placeholder="(주)예시컴퍼니",
            )
            fuel = st.selectbox(
                "유종",
                ["휘발유", "경유", "LPG", "전기", "하이브리드", "기타"],
                index=max(
                    0,
                    ["휘발유", "경유", "LPG", "전기", "하이브리드", "기타"].index(
                        settings.get("fuel_type", "휘발유")
                    )
                    if settings.get("fuel_type", "휘발유")
                    in ["휘발유", "경유", "LPG", "전기", "하이브리드", "기타"]
                    else 0,
                ),
            )

        st.markdown("#### 점심시간")
        exclude_lunch = st.checkbox(
            "점심 구간을 운행시간에서 제외",
            value=bool(settings.get("exclude_lunch", True)),
        )
        lc1, lc2 = st.columns(2)
        with lc1:
            lunch_start = st.text_input(
                "점심 시작 (HH:MM)",
                value=settings.get("lunch_start", "12:00"),
            )
        with lc2:
            lunch_end = st.text_input(
                "점심 종료 (HH:MM)",
                value=settings.get("lunch_end", "13:00"),
            )

        st.markdown("#### 업무")
        purpose = st.text_input(
            "기본 운행 목적",
            value=settings.get("default_purpose", "업무 출장"),
        )

        st.markdown("#### 자주 가는 곳")
        st.caption("한 줄에 하나 · 장소명 | 주소")
        places = settings.get("frequent_places") or []
        places_text_default = "\n".join(
            f"{p.get('name', '')} | {p.get('address', '')}".rstrip(" |")
            for p in places
            if p.get("name")
        )
        places_raw = st.text_area(
            "자주 가는 곳 목록",
            value=places_text_default,
            height=140,
            placeholder="본사 | 서울시 중구 ...\n강남 고객사 | 서울시 강남구 ...\n물류센터",
        )

        submitted = st.form_submit_button("설정 저장", type="primary", use_container_width=True)

        if submitted:
            frequent = _parse_places(places_raw)
            new_settings = {
                "vehicle_number": vehicle.strip(),
                "driver_name": driver.strip(),
                "company_name": company.strip(),
                "fuel_type": fuel,
                "exclude_lunch": exclude_lunch,
                "lunch_start": lunch_start.strip() or "12:00",
                "lunch_end": lunch_end.strip() or "13:00",
                "default_purpose": purpose.strip() or "업무 출장",
                "frequent_places": frequent,
            }
            if db.save_settings(user["email"], new_settings):
                st.success("설정이 저장되었습니다.")
            else:
                st.error("설정 저장에 실패했습니다.")


def _parse_places(raw: str) -> list[dict]:
    result = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            name, addr = line.split("|", 1)
            result.append({"name": name.strip(), "address": addr.strip()})
        else:
            result.append({"name": line, "address": ""})
    return result


def get_settings_for_current_user() -> dict:
    """생성 로직에서 호출."""
    user = current_user()
    if not user:
        from modules.config import DEFAULT_USER_SETTINGS

        return dict(DEFAULT_USER_SETTINGS)
    return db.load_settings(user["email"])
