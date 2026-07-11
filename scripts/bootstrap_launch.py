"""
정식 런칭 부트스트랩 — 비밀값 생성, .env 보강, OpenAI 점검, Railway 변수 파일 출력.

사용:
  .venv\\Scripts\\python.exe scripts\\bootstrap_launch.py
  .venv\\Scripts\\python.exe scripts\\bootstrap_launch.py --rotate-admin
"""
from __future__ import annotations

import argparse
import re
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
OUT_PATH = ROOT / ".launch" / "railway-variables.env"
SECRETS_NOTE = ROOT / ".launch" / "SECRETS_README.txt"


def _load_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _env_map(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _set_key(lines: list[str], key: str, value: str) -> list[str]:
    found = False
    out: list[str] = []
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for line in lines:
        if pat.match(line):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    return out


def _strong_password(n: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(n))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in "!@#$%^&*-_" for c in pw)
        ):
            return pw


def _test_llm(api_key: str, base_url: str = "", model: str = "gpt-4o-mini") -> tuple[bool, str]:
    try:
        from openai import OpenAI

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK only"}],
            max_tokens=5,
        )
        text = (r.choices[0].message.content or "").strip()
        return True, text or "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rotate-admin", action="store_true", help="ADMIN_PASSWORD 재발급")
    parser.add_argument("--rotate-secret", action="store_true", help="APP_SECRET 재발급")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    lines = _load_env_lines()
    env = _env_map(lines)

    app_secret = env.get("APP_SECRET") or ""
    if args.rotate_secret or not app_secret or len(app_secret) < 32 or "change-me" in app_secret:
        app_secret = secrets.token_urlsafe(48)
        lines = _set_key(lines, "APP_SECRET", app_secret)
        print("[ok] APP_SECRET rotated")

    admin_user = env.get("ADMIN_USERNAME") or "roadlog_admin"
    admin_pass = env.get("ADMIN_PASSWORD") or ""
    admin_email = env.get("ADMIN_EMAIL") or "admin@roadlog.local"
    if args.rotate_admin or not admin_pass or len(admin_pass) < 8:
        admin_pass = _strong_password(20)
        lines = _set_key(lines, "ADMIN_USERNAME", admin_user)
        lines = _set_key(lines, "ADMIN_PASSWORD", admin_pass)
        lines = _set_key(lines, "ADMIN_EMAIL", admin_email)
        print("[ok] ADMIN_PASSWORD rotated")
    else:
        # ensure keys present
        lines = _set_key(lines, "ADMIN_USERNAME", admin_user)
        lines = _set_key(lines, "ADMIN_PASSWORD", admin_pass)
        lines = _set_key(lines, "ADMIN_EMAIL", admin_email)

    # production-oriented defaults for Railway file (local .env stays development)
    openai_key = env.get("OPENAI_API_KEY") or ""
    contact = env.get("CONTACT_EMAIL") or "corelabs.studio@gmail.com"

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] wrote {ENV_PATH}")

    # LLM probe
    llm_ok = False
    llm_msg = "no key"
    if openai_key and not openai_key.startswith("sk-xxxx"):
        llm_ok, llm_msg = _test_llm(openai_key, model=env.get("OPENAI_MODEL") or "gpt-4o-mini")
        print(f"[llm/openai] {'OK' if llm_ok else 'FAIL'} — {llm_msg[:200]}")
    xai = env.get("XAI_API_KEY") or ""
    if not llm_ok and xai:
        llm_ok, llm_msg = _test_llm(
            xai,
            base_url=env.get("XAI_BASE_URL") or "https://api.x.ai/v1",
            model=env.get("XAI_MODEL") or "grok-2-latest",
        )
        print(f"[llm/xai] {'OK' if llm_ok else 'FAIL'} — {llm_msg[:200]}")

    if not llm_ok:
        print(
            "\n[action] OpenAI 크레딧 충전 또는 XAI_API_KEY 설정 필요\n"
            "  https://platform.openai.com/account/billing\n"
            "  또는 https://console.x.ai/ → API key → .env 에 XAI_API_KEY=...\n"
        )

    # Railway variables (production)
    launch_dir = ROOT / ".launch"
    launch_dir.mkdir(parents=True, exist_ok=True)
    railway_env = f"""# Railway Variables — 대시보드 Raw Editor 에 붙여넣기
# 생성: scripts/bootstrap_launch.py

APP_ENV=production
APP_SECRET={app_secret}
ADMIN_USERNAME={admin_user}
ADMIN_PASSWORD={admin_pass}
ADMIN_EMAIL={admin_email}
ALLOW_DEMO_BILLING_UPGRADE=false
ALLOWED_ORIGINS=https://roadlog.co.kr
DATA_DIR=/data
OPENAI_API_KEY={openai_key}
OPENAI_MODEL={env.get('OPENAI_MODEL') or 'gpt-4o-mini'}
XAI_API_KEY={xai}
CONTACT_EMAIL={contact}
PRO_PAYMENT_URL={env.get('PRO_PAYMENT_URL') or ''}
ENTERPRISE_PAYMENT_URL={env.get('ENTERPRISE_PAYMENT_URL') or ''}
BUSINESS_NAME={env.get('BUSINESS_NAME') or '코어랩스'}
BUSINESS_OWNER={env.get('BUSINESS_OWNER') or ''}
BUSINESS_REG_NO={env.get('BUSINESS_REG_NO') or ''}
MAIL_ORDER_REG_NO={env.get('MAIL_ORDER_REG_NO') or ''}
SUPABASE_URL={env.get('SUPABASE_URL') or ''}
SUPABASE_KEY={env.get('SUPABASE_KEY') or ''}
"""
    OUT_PATH.write_text(railway_env, encoding="utf-8")
    SECRETS_NOTE.write_text(
        "이 폴더(.launch/)는 gitignore 대상입니다.\n"
        "railway-variables.env 를 Railway Variables 에 넣고,\n"
        "Volume 을 서비스에 연결해 mount path = /data 로 설정하세요.\n"
        f"\n관리자 ID: {admin_user}\n관리자 비밀번호: {admin_pass}\n"
        f"LLM 상태: {'OK' if llm_ok else 'NEED_CREDITS_OR_XAI'}\n",
        encoding="utf-8",
    )
    print(f"[ok] Railway vars → {OUT_PATH}")
    print(f"[ok] Secrets note → {SECRETS_NOTE}")
    print("\n=== ADMIN (저장해 두세요) ===")
    print(f"  username: {admin_user}")
    print(f"  password: {admin_pass}")
    print("============================\n")
    return 0 if llm_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
