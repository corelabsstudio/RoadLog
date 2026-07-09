"""
<<<<<<< HEAD
세션 기반 인증 · Free 월 10회 제한 · plan_type 라우팅 연동
=======
세션 기반 인증 · Free 월 10회 제한 · 관리자 가드
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
"""

from __future__ import annotations

<<<<<<< HEAD
=======
from typing import Callable

>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
import streamlit as st

from modules.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    FREE_MONTHLY_LIMIT,
    PRO_PAYMENT_URL,
)
from modules import db
from modules.styles import render_pro_cta, render_usage_bar
<<<<<<< HEAD
from modules.user_config import load_user_config, resolve_plan_type, username_from_email


# ── 세션 키 ────────────────────────────────────────────
SK_USER = "user"
SK_ADMIN = "is_admin"
SK_PAGE = "nav_page"
SK_LOGGED_IN = "logged_in"
SK_USER_PLAN = "user_plan"  # personal | enterprise
SK_USERNAME = "username"


def init_session() -> None:
    """세션 기본값 초기화 (키 없으면만)."""
=======


# ── 세션 키 ────────────────────────────────────────────
SK_USER = "user"  # dict | None
SK_ADMIN = "is_admin"  # bool
SK_PAGE = "nav_page"


def init_session() -> None:
    """세션 기본값 초기화."""
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    defaults = {
        SK_USER: None,
        SK_ADMIN: False,
        SK_PAGE: "home",
<<<<<<< HEAD
        SK_LOGGED_IN: False,
        SK_USER_PLAN: "personal",
        SK_USERNAME: "",
        "last_result": None,
        "last_raw_input": "",
        "gen_error": None,
        "personal_nav": "작성",
=======
        "last_result": None,
        "last_raw_input": "",
        "gen_error": None,
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


<<<<<<< HEAD
def clear_session() -> None:
    """로그아웃 — 세션 완전 초기화."""
    st.session_state.clear()


=======
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
def current_user() -> dict | None:
    return st.session_state.get(SK_USER)


def is_logged_in() -> bool:
<<<<<<< HEAD
    return bool(st.session_state.get(SK_LOGGED_IN)) and current_user() is not None


def get_user_plan() -> str:
    """personal | enterprise"""
    return st.session_state.get(SK_USER_PLAN) or "personal"
=======
    return current_user() is not None
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)


def is_pro() -> bool:
    u = current_user()
<<<<<<< HEAD
    return bool(u and (u.get("plan") == "pro" or u.get("is_admin")))


def is_admin() -> bool:
    return bool(st.session_state.get(SK_ADMIN)) or bool(
        (current_user() or {}).get("is_admin")
    )


def _apply_login_session(user: dict) -> None:
    """로그인 성공 시 plan_type 로드 및 세션 세팅."""
    email = user.get("email") or ""
    username = username_from_email(email)
    plan_type = resolve_plan_type(email, user)
    cfg = load_user_config(email)

    st.session_state[SK_USER] = user
    st.session_state[SK_LOGGED_IN] = True
    st.session_state[SK_USER_PLAN] = plan_type
    st.session_state[SK_USERNAME] = username
    st.session_state[SK_ADMIN] = bool(user.get("is_admin") or plan_type == "enterprise")
    st.session_state["user_config"] = cfg
=======
    return bool(u and u.get("plan") == "pro")


def is_admin() -> bool:
    return bool(st.session_state.get(SK_ADMIN))
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)


def login_user(email: str, password: str) -> tuple[bool, str]:
    ok, user, msg = db.authenticate(email, password)
    if ok and user:
<<<<<<< HEAD
        _apply_login_session(user)
=======
        st.session_state[SK_USER] = user
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        return True, msg
    return False, msg


def logout_user() -> None:
<<<<<<< HEAD
    """완전 세션 종료."""
    clear_session()


def login_admin(username: str, password: str) -> tuple[bool, str]:
    """레거시 관리자 폼 호환 — 일반 인증으로 통합."""
    ok, user, msg = db.authenticate(username, password)
    if ok and user:
        _apply_login_session(user)
        return True, msg
    if username.strip() == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        # 폴백: ensure admin user
        user = db.ensure_admin_owner()
        _apply_login_session(user)
=======
    st.session_state[SK_USER] = None
    st.session_state["last_result"] = None


def login_admin(username: str, password: str) -> tuple[bool, str]:
    if username.strip() == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        st.session_state[SK_ADMIN] = True
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        return True, "관리자 로그인 성공"
    return False, "관리자 계정 정보가 올바르지 않습니다."


def logout_admin() -> None:
<<<<<<< HEAD
    clear_session()


def refresh_user_plan() -> None:
    """결제 후 plan / plan_type 재적용."""
    u = current_user()
    if not u:
        return
    email = u.get("email") or ""
    fresh = db.get_user(email) or u
    # enterprise 결제 직후 config 반영
    from modules.user_config import load_user_config

    cfg = load_user_config(email)
    if cfg.get("plan_type") == "enterprise" and not fresh.get("is_admin"):
        # plan_type enterprise 면 라우팅만 enterprise (is_admin은 소유자 전용)
        pass
    _apply_login_session(fresh)
=======
    st.session_state[SK_ADMIN] = False


def refresh_user_plan() -> None:
    """DB에서 plan 재조회 (결제 후 등)."""
    u = current_user()
    if not u:
        return
    fresh = db.get_user(u["email"])
    if fresh:
        st.session_state[SK_USER] = fresh
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)


# ── 사용량 / 제한 ─────────────────────────────────────


def get_monthly_usage() -> int:
    u = current_user()
    if not u:
        return 0
    return db.get_usage(u["email"])


def can_generate() -> tuple[bool, str]:
<<<<<<< HEAD
    if not is_logged_in():
        return False, "로그인이 필요합니다."
    if is_pro() or get_user_plan() == "enterprise":
=======
    """생성 가능 여부. Free는 월 정확히 10회."""
    if not is_logged_in():
        return False, "로그인이 필요합니다."
    if is_pro():
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        return True, "ok"
    used = get_monthly_usage()
    if used >= FREE_MONTHLY_LIMIT:
        return (
            False,
            f"이번 달 Free 한도({FREE_MONTHLY_LIMIT}회)를 모두 사용했습니다. Pro로 업그레이드해 주세요.",
        )
    return True, "ok"


def consume_usage() -> int:
<<<<<<< HEAD
    u = current_user()
    if not u:
        return 0
=======
    """생성 성공 시 호출 — 사용량 +1."""
    u = current_user()
    if not u:
        return 0
    if is_pro():
        # Pro도 통계용으로 기록 (한도 미적용)
        return db.increment_usage(u["email"], 1)
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    return db.increment_usage(u["email"], 1)


def show_usage_widget() -> None:
<<<<<<< HEAD
    if not is_logged_in():
        return
    if get_user_plan() == "enterprise" or is_pro():
        st.markdown(
            """
<div class="uil-usage">
  <span class="uil-badge uil-badge-pro">Enterprise / Pro</span>
  &nbsp; 무제한 생성
</div>
            """,
            unsafe_allow_html=True,
        )
        return
    used = get_monthly_usage()
    render_usage_bar(used, FREE_MONTHLY_LIMIT, False)


def show_limit_cta_if_needed() -> bool:
=======
    """사이드바/본문 사용량 표시."""
    if not is_logged_in():
        return
    used = get_monthly_usage()
    render_usage_bar(used, FREE_MONTHLY_LIMIT, is_pro())


def show_limit_cta_if_needed() -> bool:
    """
    한도 초과 시 Pro CTA 표시.
    Returns: True 이면 차단 상태(생성 불가)
    """
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    ok, msg = can_generate()
    if not ok and is_logged_in() and not is_pro():
        st.warning(msg)
        render_pro_cta(PRO_PAYMENT_URL)
        return True
    return False


# ── UI 블록 ────────────────────────────────────────────


<<<<<<< HEAD
def show_login_page() -> None:
    """로그인 전용 풀 페이지 (모드 선택 없음)."""
    from modules.styles import render_landing_hero, render_footer, render_sidebar_brand

    render_sidebar_brand()
    st.sidebar.caption("계정으로 로그인하면 요금제(plan_type)에 따라 화면이 자동 전환됩니다.")

    render_landing_hero()
    st.markdown("### 로그인")
    st.caption("회원가입 없이 등록된 계정으로 접속하세요. 관리자 계정은 기업용 대시보드로 이동합니다.")

    tab_login, tab_reg = st.tabs(["로그인", "회원가입"])
    with tab_login:
        email = st.text_input("이메일 또는 ID", key="login_email_main", placeholder="you@company.com")
        pw = st.text_input("비밀번호", type="password", key="login_pw_main")
        if st.button("로그인", type="primary", use_container_width=True, key="btn_login_main"):
=======
def render_auth_sidebar() -> None:
    """사이드바 로그인/가입/로그아웃."""
    st.sidebar.markdown("### 계정")
    user = current_user()

    if user:
        plan_label = "PRO" if user.get("plan") == "pro" else "FREE"
        st.sidebar.success(f"**{user.get('name') or user['email']}**  ·  {plan_label}")
        st.sidebar.caption(user["email"])
        show_usage_widget()
        if not is_pro():
            st.sidebar.markdown(f"[Pro 업그레이드]({PRO_PAYMENT_URL})")
        if st.sidebar.button("로그아웃", use_container_width=True, key="btn_logout"):
            logout_user()
            st.rerun()
        return

    tab_login, tab_reg = st.sidebar.tabs(["로그인", "회원가입"])
    with tab_login:
        email = st.text_input("이메일", key="login_email", placeholder="you@company.com")
        pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", use_container_width=True, type="primary", key="btn_login"):
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
            ok, msg = login_user(email, pw)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    with tab_reg:
<<<<<<< HEAD
        name = st.text_input("이름 (선택)", key="reg_name_main")
        email = st.text_input("이메일", key="reg_email_main", placeholder="you@company.com")
        pw = st.text_input("비밀번호", type="password", key="reg_pw_main")
        pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2_main")
        if st.button("가입하기", use_container_width=True, key="btn_reg_main"):
=======
        name = st.text_input("이름(선택)", key="reg_name")
        email = st.text_input("이메일", key="reg_email", placeholder="you@company.com")
        pw = st.text_input("비밀번호", type="password", key="reg_pw")
        pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
        if st.button("가입하기", use_container_width=True, key="btn_reg"):
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
            if pw != pw2:
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                ok, msg = db.register_user(email, pw, name)
                if ok:
<<<<<<< HEAD
                    # 기본 personal config 생성
                    from modules.user_config import load_user_config

                    load_user_config(email)
                    st.success(msg + " 로그인해 주세요.")
                else:
                    st.error(msg)

    render_footer()


def render_auth_sidebar() -> None:
    """로그인 후 사이드바 계정 영역 + 로그아웃(세션 clear)."""
    user = current_user()
    if not user:
        return

    plan_type = get_user_plan()
    plan_label = "기업용" if plan_type == "enterprise" else (
        "PRO" if user.get("plan") == "pro" else "FREE"
    )
    display = user.get("name") or (user["email"].split("@")[0] if user.get("email") else "User")
    st.sidebar.markdown(f"**{display}**")
    st.sidebar.caption(f"{user.get('email', '')}  ·  {plan_label}")
    if plan_type != "enterprise":
        show_usage_widget()
        if not is_pro():
            st.sidebar.link_button("Pro 업그레이드", PRO_PAYMENT_URL, use_container_width=True)

    if st.sidebar.button("로그아웃", use_container_width=True, key="btn_logout"):
        logout_user()  # session_state.clear()
        st.rerun()

=======
                    st.success(msg)
                else:
                    st.error(msg)

>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)

def require_login(message: str = "이 기능을 사용하려면 로그인해 주세요.") -> bool:
    if is_logged_in():
        return True
    st.info(message)
    return False


def admin_login_form() -> bool:
<<<<<<< HEAD
    """레거시 호환 — 이미 로그인·enterprise면 True."""
    if is_logged_in() and (is_admin() or get_user_plan() == "enterprise"):
        return True
    st.markdown("### 관리자 로그인")
    with st.form("admin_login_form"):
        u = st.text_input("관리자 ID", value="", placeholder=ADMIN_USERNAME)
        p = st.text_input("비밀번호", type="password")
=======
    """관리자 로그인 폼. 성공 시 True."""
    if is_admin():
        return True
    st.markdown("### 관리자 로그인")
    with st.form("admin_login_form"):
        u = st.text_input("관리자 ID", value="", placeholder="admin")
        p = st.text_input("비밀번호", type="password", placeholder="••••••••")
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        submitted = st.form_submit_button("로그인", type="primary")
        if submitted:
            ok, msg = login_admin(u, p)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
<<<<<<< HEAD
=======
    st.caption("기본: admin / admin123")
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    return False
