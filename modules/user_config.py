"""
사용자별 계정 설정: config_{username}.json
plan_type: personal | enterprise  → Streamlit 자동 라우팅 기준
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

CONFIGS_DIR = DATA_DIR / "user_configs"
CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_USER_CONFIG: dict[str, Any] = {
    "plan_type": "personal",  # personal | enterprise
    "display_name": "",
    "company_id": "",
    "team_id": "",
    "role": "member",  # member | manager | admin
}


def username_from_email(email: str) -> str:
    """config 파일명용 안전한 username."""
    raw = (email or "user").strip().lower()
    # 로컬파트 우선, 없으면 전체
    local = raw.split("@")[0] if "@" in raw else raw
    safe = re.sub(r"[^a-z0-9._-]+", "_", local)
    return safe or "user"


def config_path(username: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", (username or "user").strip())
    return CONFIGS_DIR / f"config_{safe}.json"


def load_user_config(email_or_username: str) -> dict[str, Any]:
    """이메일 또는 username 으로 설정 로드."""
    username = username_from_email(email_or_username)
    path = config_path(username)
    if not path.exists():
        cfg = {**DEFAULT_USER_CONFIG, "username": username}
        # 관리자 계정 자동 enterprise
        from modules.config import ADMIN_USERNAME, ADMIN_EMAIL

        low = (email_or_username or "").strip().lower()
        if low in {
            (ADMIN_USERNAME or "").lower(),
            (ADMIN_EMAIL or "").lower(),
            "hhs126",
            "admin",
        }:
            cfg["plan_type"] = "enterprise"
            cfg["role"] = "admin"
            cfg["display_name"] = "관리자"
        save_user_config(username, cfg)
        return cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_USER_CONFIG, **data, "username": username}
    except Exception:
        return {**DEFAULT_USER_CONFIG, "username": username}


def save_user_config(username: str, config: dict[str, Any]) -> dict[str, Any]:
    path = config_path(username)
    clean = {**DEFAULT_USER_CONFIG, **config}
    clean["username"] = username_from_email(username)
    # plan_type 정규화
    pt = str(clean.get("plan_type") or "personal").lower().strip()
    clean["plan_type"] = "enterprise" if pt in ("enterprise", "ent", "company", "biz") else "personal"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    return clean


def set_plan_type(email: str, plan_type: str) -> dict[str, Any]:
    username = username_from_email(email)
    cfg = load_user_config(email)
    cfg["plan_type"] = plan_type
    return save_user_config(username, cfg)


def resolve_plan_type(email: str, user: dict | None = None) -> str:
    """
    라우팅용 plan_type 결정.
    1) config_{username}.json 의 plan_type
    2) user.is_admin 이면 enterprise
    """
    cfg = load_user_config(email)
    if user and user.get("is_admin"):
        # 관리자 계정은 항상 enterprise 보장
        if cfg.get("plan_type") != "enterprise":
            cfg = set_plan_type(email, "enterprise")
        return "enterprise"
    return cfg.get("plan_type") or "personal"
