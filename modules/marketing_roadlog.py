from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from modules import lamps, stats

def _now() -> str: return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

class RoadLogCatalog:
    def __init__(self,web_root:Path): self.path=Path(web_root)/"admin"/"marketing-products.json"
    def load(self)->tuple[list[dict[str,Any]],dict[str,Any]]:
        raw=self.path.read_bytes(); payload=json.loads(raw.decode("utf-8")); products=[]; warnings=[]
        for source in payload.get("products",[]):
            item=dict(source); pid=item.get("product_id") or ""; issues=[]; free=pid in lamps.FREE_PRODUCTS; price=0 if free else lamps.PREMIUM_WON.get(pid)
            if item.get("price_won")!=price: issues.append(f"원화 가격 불일치: 화면 {item.get('price_won')}, 서버 {price if price is not None else 'UNKNOWN'}")
            if bool(item.get("free"))!=free: issues.append("무료 여부 불일치")
            if bool(item.get("premium"))!=(pid in lamps.PREMIUM_ONLY): issues.append("결제 전용 여부 불일치")
            item["lamp_price"]=0 if free else ("결제 전용" if pid in lamps.PREMIUM_ONLY else lamps.PRICES.get(pid,"UNKNOWN")); item["facts_status"]="VERIFIED" if not issues else "MISMATCH"; item["issues"]=issues
            products.append(item); warnings.extend(f"{pid}: {issue}" for issue in issues)
        return products,{"source_file":str(self.path),"source_hash":hashlib.sha256(raw).hexdigest(),"generated_at":payload.get("generated_at") or "UNKNOWN","synced_at":_now(),"warnings":warnings}


def performance_snapshot(days: int = 7) -> dict[str, Any]:
    """Only first-party aggregates; never send members, emails, visits or raw ledgers to AI."""
    report = stats.overview(days=max(1, min(days, 30)))
    allowed = ("uv", "pv", "signups", "charges", "sales", "opens")
    return {
        "source": "roadlog.stats.overview",
        "period_days": days,
        "today": {key: int((report.get("today") or {}).get(key) or 0) for key in allowed},
        "month": {key: int((report.get("month") or {}).get(key) or 0) for key in allowed},
        "by_source": [{"name": str(row.get("name") or "UNKNOWN")[:60], "uv": int(row.get("uv") or 0)} for row in (report.get("bySource") or [])[:5]],
        "by_campaign": [{"name": str(row.get("name") or "UNKNOWN")[:60], "uv": int(row.get("uv") or 0)} for row in (report.get("byCampaign") or [])[:5]],
        "by_product": [{"product_id": str(row.get("product") or "UNKNOWN")[:60], "opens": int(row.get("opens") or 0)} for row in (report.get("byProduct") or [])[:10]],
        "limitations": ["검색 노출·검색량은 Search Console 미연결", "인스타 게시·노출·참여 성과 미연결"],
    }
