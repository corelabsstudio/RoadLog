"""
관리자 알림 (폰 푸시)

지원:
- ntfy (권장): 폰에 ntfy 앱 설치 후 토픽 구독 → HTTP POST 만으로 푸시
- Telegram: 봇 토큰 + chat_id

스마트스토어 결제는 서버로 직접 웹훅이 오지 않으므로,
고객이 /api/billing/claim 으로 주문번호를 남기면 여기서 알림을 보냅니다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from modules.config import DATA_DIR, _get_secret

CLAIMS_JSON = DATA_DIR / "payment_claims.json"

# 환경변수
NTFY_SERVER = (_get_secret("NTFY_SERVER", "https://ntfy.sh") or "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = _get_secret("NTFY_TOPIC", "").strip()
NTFY_TOKEN = _get_secret("NTFY_TOKEN", "").strip()  # 비공개 토픽용 (선택)
TELEGRAM_BOT_TOKEN = _get_secret("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = _get_secret("TELEGRAM_CHAT_ID", "").strip()


def notify_configured() -> bool:
    return bool(NTFY_TOPIC) or (bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_claims() -> list[dict[str, Any]]:
    if not CLAIMS_JSON.exists():
        return []
    try:
        raw = json.loads(CLAIMS_JSON.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _write_claims(items: list[dict[str, Any]]) -> None:
    CLAIMS_JSON.parent.mkdir(parents=True, exist_ok=True)
    CLAIMS_JSON.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_claim(
    *,
    order_id: str,
    email: str,
    name: str = "",
    note: str = "",
    plan: str = "pro",
) -> dict[str, Any]:
    items = _read_claims()
    entry = {
        "id": secrets_token(),
        "order_id": order_id.strip(),
        "email": email.strip().lower(),
        "name": (name or "").strip(),
        "note": (note or "").strip(),
        "plan": plan or "pro",
        "status": "pending",
        "created_at": _now(),
    }
    items.insert(0, entry)
    # keep last 500
    _write_claims(items[:500])
    return entry


def secrets_token() -> str:
    import secrets

    return secrets.token_hex(8)


def list_claims(limit: int = 50) -> list[dict[str, Any]]:
    return _read_claims()[: max(1, min(limit, 200))]


def send_admin_push(title: str, message: str, *, priority: int = 4) -> dict[str, Any]:
    """관리자 폰으로 푸시. 설정된 채널에 전송."""
    results: dict[str, Any] = {"ok": False, "channels": {}}
    any_ok = False

    if NTFY_TOPIC:
        ok, detail = _send_ntfy(title, message, priority=priority)
        results["channels"]["ntfy"] = {"ok": ok, "detail": detail}
        any_ok = any_ok or ok

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        ok, detail = _send_telegram(title, message)
        results["channels"]["telegram"] = {"ok": ok, "detail": detail}
        any_ok = any_ok or ok

    if not results["channels"]:
        results["detail"] = "알림 채널 미설정 (NTFY_TOPIC 또는 TELEGRAM_*)"
    results["ok"] = any_ok
    return results


def _send_ntfy(title: str, message: str, *, priority: int = 4) -> tuple[bool, str]:
    topic = NTFY_TOPIC.strip().lstrip("/")
    if not topic:
        return False, "no topic"
    url = f"{NTFY_SERVER}/{parse.quote(topic)}"
    # HTTP 헤더는 latin-1 제한 → 제목 한글은 RFC2047, 본문은 UTF-8 body
    try:
        from email.header import Header

        title_hdr = Header(title[:80], "utf-8").encode()
    except Exception:
        title_hdr = "RoadLog"
    # 본문에 제목 포함 (폰 알림 가독성)
    body_text = f"{title}\n\n{message}"
    headers = {
        "Title": title_hdr,
        "Priority": str(max(1, min(5, priority))),
        "Tags": "moneybag,roadlog",
        "Content-Type": "text/plain; charset=utf-8",
    }
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
    try:
        req = request.Request(
            url,
            data=body_text.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=15) as res:
            return True, f"status={res.status}"
    except error.HTTPError as e:
        return False, f"http {e.code}"
    except Exception as e:
        return False, str(e)[:200]


def _send_telegram(title: str, message: str) -> tuple[bool, str]:
    text = f"*{title}*\n{message}"
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    try:
        req = request.Request(
            api,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=15) as res:
            return True, f"status={res.status}"
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return False, f"http {e.code} {body}"
    except Exception as e:
        return False, str(e)[:200]
