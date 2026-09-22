from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from .policy import BrandPolicy, review_draft
from .ports import CatalogProvider, ContentProvider
from .repository import MarketingRepository

def now() -> str: return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

@dataclass(frozen=True)
class UsagePolicy:
    daily_requests: int = 20
    daily_cost: float = 3000
    per_agent_requests: int = 5

class MarketingService:
    def __init__(self, catalog: CatalogProvider, content: ContentProvider, repository: MarketingRepository, brand_policy: BrandPolicy, usage_policy: UsagePolicy = UsagePolicy()):
        self.catalog, self.content, self.repository = catalog, content, repository
        self.brand_policy, self.usage_policy = brand_policy, usage_policy

    def products(self) -> dict[str, Any]:
        items, meta = self.catalog.load(); self.repository.record_sync(meta, len(items))
        return {"products": items, "sync": meta}

    def status(self) -> dict[str, Any]:
        data = self.products(); items = data["products"]
        return {"dry_run":True,"mode":"DEMO","provider":self.content.name,"model":self.content.model,"connected":self.content.connected,"connection_label":"연결됨" if self.content.connected else "AI 연결되지 않음","real_trial_enabled":False,"automatic_real_calls":False,"tenant_id":self.repository.tenant_id,"product_count":len(items),"verified_count":sum(p["facts_status"]=="VERIFIED" for p in items),"sync":data["sync"]}

    def usage(self) -> dict[str, Any]:
        day=now()[:10]; requests,cost=self.repository.usage(day); p=self.usage_policy
        return {"date":day,"requests":requests,"request_limit":p.daily_requests,"remaining_requests":max(0,p.daily_requests-requests),"estimated_cost_krw":cost,"cost_limit_krw":p.daily_cost,"remaining_cost_krw":max(0,p.daily_cost-cost),"cost_is_estimate":True,"agent_limit":p.per_agent_requests}

    def trial(self, product_id: str, platform: str, mode: str) -> dict[str, Any]:
        if mode.upper()!="DEMO": raise PermissionError("실제 유료 AI 호출은 잠겨 있습니다.")
        data=self.products(); product=next((p for p in data["products"] if p["product_id"]==product_id),None)
        if not product: raise ValueError("상품을 찾지 못했습니다.")
        if product["facts_status"]!="VERIFIED": raise ValueError("상품 정본이 일치하지 않아 콘텐츠를 만들 수 없습니다.")
        draft=self.content.generate(product,platform); reasons=review_draft(product,draft,self.brand_policy)
        cid,aid=self.repository.save_trial(product,data["sync"],draft,reasons,now()); passed=not reasons
        return {"ok":passed,"content_id":cid,"approval_id":aid,"status":"PENDING_APPROVAL" if passed else "REVISION_REQUESTED","review":{"status":"PASSED" if passed else "BLOCKED","reasons":reasons},"estimated_cost_krw":None,"cost_label":"예상 비용 단가 미설정","draft":draft}

    def approvals(self) -> list[dict[str, Any]]: return self.repository.approvals()

    def decide(self, approval_id: int, decision: str, note: str) -> dict[str, Any]:
        states={"approve":"APPROVED","reject":"REJECTED","revise":"REVISION_REQUESTED"}
        if decision not in states: raise ValueError("지원하지 않는 결정입니다.")
        self.repository.decide(approval_id,states[decision],note,now())
        return {"ok":True,"status":states[decision],"message":"승인 이력만 저장했습니다. 외부 공개는 실행하지 않았습니다."}
