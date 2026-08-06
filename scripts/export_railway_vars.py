"""Export .env → .launch/railway-variables.env for Railway RAW Editor paste."""
from __future__ import annotations

import secrets as secmod
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".launch"


def clean(val: object) -> str:
    x = "" if val is None else str(val).strip()
    if len(x) >= 2 and ((x[0] == x[-1] == '"') or (x[0] == x[-1] == "'")):
        x = x[1:-1].strip()
    return x


def main() -> None:
    v = dotenv_values(ROOT / ".env")

    def g(key: str, default: str = "") -> str:
        return clean(v.get(key) or default)

    app_secret = g("APP_SECRET")
    if (
        not app_secret
        or len(app_secret) < 32
        or "change-me" in app_secret
        or "roadlog-dev" in app_secret
    ):
        app_secret = secmod.token_urlsafe(48)

    admin_user = g("ADMIN_USERNAME") or "hhs126"
    admin_pass = g("ADMIN_PASSWORD")
    admin_email = g("ADMIN_EMAIL") or "corelabs.studio@gmail.com"
    openai_key = g("OPENAI_API_KEY")
    contact = g("CONTACT_EMAIL") or "corelabs.studio@gmail.com"
    model = g("OPENAI_MODEL") or "gpt-4o-mini"

    lines = [
        "# RoadLog Railway Variables — Variables > RAW Editor 에 붙여넣기",
        "APP_ENV=production",
        "COST_MODE=hybrid",
        f"APP_SECRET={app_secret}",
        f"ADMIN_USERNAME={admin_user}",
        f"ADMIN_PASSWORD={admin_pass}",
        f"ADMIN_EMAIL={admin_email}",
        "ALLOW_DEMO_BILLING_UPGRADE=false",
        "ALLOWED_ORIGINS=https://roadlog.co.kr",
        f"OPENAI_API_KEY={openai_key}",
        f"OPENAI_MODEL={model}",
        f"CONTACT_EMAIL={contact}",
        f"CONTACT_FORM_URL={g('CONTACT_FORM_URL')}",
        f"BUSINESS_NAME={g('BUSINESS_NAME') or '코어랩스'}",
        f"BUSINESS_OWNER={g('BUSINESS_OWNER')}",
        f"BUSINESS_REG_NO={g('BUSINESS_REG_NO')}",
        f"MAIL_ORDER_REG_NO={g('MAIL_ORDER_REG_NO')}",
        "PRO_PAYMENT_URL=",
        "ENTERPRISE_PAYMENT_URL=",
        "XAI_API_KEY=",
        "SUPABASE_URL=",
        "SUPABASE_KEY=",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    env_path = OUT_DIR / "railway-variables.env"
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    guide = OUT_DIR / "RAILWAY_PASTE_GUIDE.md"
    guide.write_text(
        """# Railway Variables 붙여넣기

## 1. 대시보드
1. https://railway.app/dashboard
2. RoadLog 서비스 선택
3. **Variables** 탭
4. **RAW Editor** 열기

## 2. 파일 통째로 복사
경로:
`C:\\Users\\hysoo\\Projects\\RoadLog\\.launch\\railway-variables.env`

메모장으로 연 뒤 전체 선택(Ctrl+A) → 복사 → Railway RAW에 붙여넣기 → **Save**

## 3. 핵심 변수
| 변수 | 역할 |
|------|------|
| OPENAI_API_KEY | 라이브 AI 켜기 |
| APP_ENV=production | 운영 모드 |
| COST_MODE=hybrid | 키 있으면 AI, 한도면 초안 |
| APP_SECRET | 세션 보안 |
| ADMIN_USERNAME / ADMIN_PASSWORD | 관리자 |
| ALLOWED_ORIGINS | https://roadlog.co.kr |
| ALLOW_DEMO_BILLING_UPGRADE=false | 데모 결제 차단 |

## 4. 저장 후 확인 (1~3분)
https://roadlog.co.kr/api/health

- `"openai": true` → 키 인식됨
- `"cost_mode": "hybrid"` → 최신 코드

## 5. OpenAI 결제 (한도 0이면 생성 실패)
https://platform.openai.com/account/billing  
결제 수단 등록 또는 소액 크레딧 → 사이트에서 일지 1회 생성

## 6. Volume (선택)
지금은 비용 아끼려면 생략. 나중에 Mount `/data` + `DATA_DIR=/data`
""",
        encoding="utf-8",
    )

    print("wrote", env_path)
    print(
        "openai_set",
        bool(openai_key) and not openai_key.startswith("sk-xxxx"),
        "len",
        len(openai_key or ""),
    )
    print("admin_user", admin_user)
    print("secret_len", len(app_secret))
    print("guide", guide)


if __name__ == "__main__":
    main()
