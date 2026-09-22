"""ROADLOG 어댑터를 Generic AI Marketing Core에 연결하는 호환 파사드."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from modules.config import DATA_DIR
from modules.marketing_core import BrandPolicy, MarketingRepository, MarketingService, review_draft as core_review
from modules.marketing_roadlog import RoadLogCatalog, RoadLogDemoProvider

DB = Path(DATA_DIR) / "marketing_os.db"
TENANT_ID = "roadlog"
POLICY = BrandPolicy(
    brand_names=("ROADLOG", "로드로그"),
    guarantee_pattern=r"무조건|반드시\s*(?:재회|성공|당첨)|100\s*%|확실(?:히|한)|보장|운명\s*(?:확정|변경)|수익\s*보장|효과\s*보장",
    cliche_pattern=r"혁신적인|획기적인|차세대|게임\s*체인저|한\s*차원\s*높은|새로운\s*가능성을\s*열",
    blocked_brand_pattern=r"ChatGPT|챗GPT|포스텔러|점신|신한라이프",
)

def _service(web_root: Path = Path(".")) -> MarketingService:
    return MarketingService(RoadLogCatalog(web_root), RoadLogDemoProvider(), MarketingRepository(DB, TENANT_ID, legacy_tenant_id=TENANT_ID), POLICY)

def status(web_root: Path) -> dict[str, Any]: return _service(web_root).status()
def products(web_root: Path) -> dict[str, Any]: return _service(web_root).products()
def usage() -> dict[str, Any]: return _service().usage()
def trial(web_root: Path, product_id: str, platform: str, mode: str) -> dict[str, Any]: return _service(web_root).trial(product_id, platform, mode)
def approvals() -> list[dict[str, Any]]: return _service().approvals()
def decide(approval_id: int, decision: str, note: str) -> dict[str, Any]: return _service().decide(approval_id, decision, note)
def review_draft(product: dict[str, Any], draft: dict[str, Any]) -> list[str]: return core_review(product, draft, POLICY)
