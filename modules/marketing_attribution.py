"""First-party, explicit-link attribution. No IP, email or payment ID in marketing DB."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from modules.config import APP_SECRET
from modules.marketing_core.repository import MarketingRepository

COOKIE = "rl_mkt_visitor"
WINDOW_DAYS = 30
MODEL = "last_known_eligible_campaign_before_signup"


def _digest(value: str) -> str:
    return hmac.new(APP_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def visitor_cookie(visitor_id: str) -> str:
    return visitor_id + "." + _digest("visitor:" + visitor_id)


def valid_visitor(cookie: str) -> str | None:
    visitor_id, dot, sig = (cookie or "").partition(".")
    if not dot or not re.fullmatch(r"[0-9a-f]{32}", visitor_id) or not hmac.compare_digest(sig,_digest("visitor:"+visitor_id)):
        return None
    return visitor_id


def new_visitor() -> str:
    return secrets.token_hex(16)


def account_key(email: str) -> str:
    return _digest("account:" + email.strip().lower())


def payment_key(payment_id: str) -> str:
    return _digest("payment:" + payment_id.strip())


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tracked_visit(repo: MarketingRepository, visitor_id: str, query: dict[str,str], landing_page: str, when: str | None = None) -> bool:
    try:
        campaign_id = int(query.get("rl_campaign_id", ""))
        publication_id = int(query.get("rl_publication_id", ""))
    except (ValueError,TypeError):
        return False
    if campaign_id <= 0 or publication_id <= 0: return False
    publication = repo.published_tracking(campaign_id,publication_id)
    if not publication: return False
    expected = parse_qs(urlparse(publication["tracking_url"]).query)
    source, medium = query.get("utm_source", ""), query.get("utm_medium", "")
    if (source != expected.get("utm_source",[None])[0] or medium != expected.get("utm_medium",[None])[0]
        or query.get("utm_campaign") != expected.get("utm_campaign",[None])[0]): return False
    return repo.record_attributed_visit(visitor_id,campaign_id,publication_id,source,medium,landing_page,when or stamp())


def attributed_signup(repo: MarketingRepository, email: str, cookie: str, when: str | None = None) -> bool:
    visitor_id = valid_visitor(cookie)
    return bool(visitor_id and repo.record_attributed_signup(account_key(email),visitor_id,when or stamp(),WINDOW_DAYS))


def attributed_purchase(repo: MarketingRepository, email: str, payment_id: str, product_id: str, kind: str, amount: int, when: str | None = None) -> bool:
    return repo.record_attributed_purchase(payment_key(payment_id),account_key(email),product_id,kind,amount,when or stamp(),WINDOW_DAYS)
