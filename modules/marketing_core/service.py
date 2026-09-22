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

    def create_bundle(self, product_id: str, customer_question: str, mode: str = "DEMO", source_text: str = "") -> dict[str, Any]:
        if mode.upper() != "DEMO": raise PermissionError("실제 유료 AI 호출은 잠겨 있습니다.")
        question = customer_question.strip()
        if not question or len(question) > 300: raise ValueError("고객 질문은 1~300자로 적어 주세요.")
        source_text = source_text.strip()
        if len(source_text) > 5000: raise ValueError("원본 대본은 5,000자 이내로 적어 주세요.")
        data = self.products()
        product = next((p for p in data["products"] if p["product_id"] == product_id), None)
        if not product or product["facts_status"] != "VERIFIED": raise ValueError("확인된 상품 정본을 선택해 주세요.")
        facts = product.get("confirmed_results") or []
        source_facts = [fact for fact in facts if fact in source_text] if source_text else []
        if source_text and not source_facts:
            raise ValueError("원본 대본에서 선택한 상품의 확인된 결과 항목을 찾지 못했습니다. 정본에 있는 항목을 포함해 주세요.")
        candidates = source_facts if source_text else facts
        focus = next((fact for fact in candidates if fact in question), None)
        focus = focus or (candidates[0] if candidates else "")
        # Keep unverified source copy out of generation; only the matched catalog fact crosses this boundary.
        writing_product = {**product, "marketing_focus_result": focus}
        channels = ("원본", "블로그", "짧은 영상 대본", "카드뉴스")
        drafts = [(draft, review_draft(product, draft, self.brand_policy))
                  for draft in (self.content.generate(writing_product, channel) for channel in channels)]
        if drafts[0][1]: raise ValueError("원본 초안이 사실 검수를 통과하지 못했습니다.")
        result = self.repository.save_bundle(product, data["sync"], question, source_text, focus, drafts, now())
        return {**result, "mode": "DEMO", "dry_run": True, "published": False,
                "focus_result": focus or "UNKNOWN", "performance_label": "연결되지 않음", "cost_label": "외부 AI 호출 없음 · 예상 비용 0원"}

    def bundles(self) -> list[dict[str, Any]]: return self.repository.bundles()

    def decide(self, approval_id: int, decision: str, note: str) -> dict[str, Any]:
        states={"approve":"APPROVED","reject":"REJECTED","revise":"REVISION_REQUESTED"}
        if decision not in states: raise ValueError("지원하지 않는 결정입니다.")
        self.repository.decide(approval_id,states[decision],note,now())
        return {"ok":True,"status":states[decision],"message":"승인 이력만 저장했습니다. 외부 공개는 실행하지 않았습니다."}
