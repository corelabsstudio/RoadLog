from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any
from .policy import BrandPolicy, review_draft
from .ports import CatalogProvider, ContentProvider
from .repository import MarketingRepository

def now() -> str: return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")

REQUEST_BUDGET_RESERVATION_KRW = 20.0  # Internal planning amount, not a provider billing cap.

@dataclass(frozen=True)
class UsagePolicy:
    daily_requests: int = 20
    daily_cost: float = 3000
    per_agent_requests: int = 5

class MarketingService:
    def __init__(self, catalog: CatalogProvider, content: ContentProvider, repository: MarketingRepository, brand_policy: BrandPolicy, usage_policy: UsagePolicy = UsagePolicy(), real_content: ContentProvider | None = None):
        self.catalog, self.content, self.repository = catalog, content, repository
        self.brand_policy, self.usage_policy = brand_policy, usage_policy
        self.real_content = real_content

    def products(self) -> dict[str, Any]:
        items, meta = self.catalog.load(); self.repository.record_sync(meta, len(items))
        return {"products": items, "sync": meta}

    def status(self) -> dict[str, Any]:
        data = self.products(); items = data["products"]
        connected = bool(self.real_content and self.real_content.connected)
        manual_success = self.repository.has_manual_real_success()
        connection_label = "AI 연결되지 않음"
        if connected:
            connection_label = "수동 생성·검수 성공" if manual_success else ("실제 AI 응답 확인 · 검수 통과 대기" if self.repository.has_real_provider_response() else "키 설정됨 · 실제 호출 미검증")
        return {"dry_run":True,"dry_run_scope":"external_publishing","mode":"REAL · 실제 AI 초안" if connected else "AI 미연결","provider":self.real_content.name if self.real_content else self.content.name,"model":self.real_content.model if self.real_content else self.content.model,"connected":connected,"connection_label":connection_label,"real_trial_enabled":connected,"manual_real_success":manual_success,"automatic_real_calls":self.repository.auto_real_enabled(),"tenant_id":self.repository.tenant_id,"product_count":len(items),"verified_count":sum(p["facts_status"]=="VERIFIED" for p in items),"sync":data["sync"]}

    def usage(self) -> dict[str, Any]:
        day=now()[:10]; requests,cost=self.repository.usage(day); p=self.usage_policy
        from modules import marketing_safety
        external = marketing_safety.cost_status()
        return {"date":day,"requests":requests,"request_limit":external["daily_requests"],"remaining_requests":max(0,external["daily_requests"]-external["calls"]),"estimated_cost_krw":cost,"cost_limit_krw":external["daily_budget_krw"],"remaining_cost_krw":max(0,external["daily_budget_krw"]-external["reserved_cost_krw"]),"cost_is_estimate":True,"agent_limit":external["per_agent_requests"],"external_calls":external["calls"],"external_reserved_cost_krw":external["reserved_cost_krw"],"actual_cost_estimate_krw":external["actual_cost_estimate_krw"]}

    def trial(self, product_id: str, platform: str, mode: str, *, trigger: str = "MANUAL", focus_result: str = "", defer_approval: bool = False, strategy_context: list[str] | None = None, campaign_id: int = 0) -> dict[str, Any]:
        mode = mode.upper()
        if mode != "REAL": raise PermissionError("DEMO 생성은 종료됐습니다. 실제 AI 생성만 지원합니다.")
        if trigger not in ("MANUAL", "AUTO"): raise ValueError("지원하지 않는 실행 경로입니다.")
        data=self.products(); product=next((p for p in data["products"] if p["product_id"]==product_id),None)
        if not product: raise ValueError("상품을 찾지 못했습니다.")
        if product["facts_status"]!="VERIFIED": raise ValueError("상품 정본이 일치하지 않아 콘텐츠를 만들 수 없습니다.")
        if not product.get("confirmed_results") or product.get("price_won") is None: raise ValueError("가격 또는 확인된 결과 항목이 없어 AI 초안을 만들 수 없습니다.")
        run_id = None
        if not self.real_content or not self.real_content.connected: raise PermissionError("AI 연결되지 않음: 서버에 Gemini API 키가 없습니다.")
        provider = self.real_content
        # Budget allocation, not an upper bound on provider billing.
        reservation = REQUEST_BUDGET_RESERVATION_KRW
        from modules import marketing_safety
        p = marketing_safety.cost_settings()
        run_id = self.repository.reserve_real_run(product_id, now(), p["daily_requests"], p["per_agent_requests"], p["daily_budget_krw"], reservation)
        try:
            writing_product = {**product, "synced_at": data["sync"]["synced_at"], "source_file": data["sync"]["source_file"], "marketing_focus_result": focus_result, "strategy_context": (strategy_context or [])[:3], "campaign_id": campaign_id}
            draft=provider.generate(writing_product,platform); reasons=review_draft(product,draft,self.brand_policy)
            cid,aid=self.repository.save_trial(product,data["sync"],draft,reasons,now(),mode,reservation,defer_approval=defer_approval); passed=not reasons
            if run_id is not None:
                usage = getattr(provider, "usage", {})
                self.repository.finish_real_run(run_id, "COMPLETED", f"{ '수동' if trigger == 'MANUAL' else '자동' } 검수 통과" if passed else "수정 대기", usage.get("input_tokens", 0), usage.get("output_tokens", 0))
            return {"ok":passed,"content_id":cid,"run_id":run_id,"approval_id":aid,"status":"AWAITING_AI_REVIEW" if defer_approval else "PENDING_APPROVAL" if passed else "REVISION_REQUESTED","review":{"status":"PASSED" if passed else "BLOCKED","reasons":reasons},"estimated_cost_krw":reservation,"cost_label":"예산 예약액 20원 (실제 청구액 아님)","draft":draft}
        except Exception:
            if run_id is not None: self.repository.finish_real_run(run_id, "FAILED", "AI 생성 또는 저장 실패")
            raise

    def approvals(self) -> list[dict[str, Any]]: return self.repository.approvals()

    def create_bundle(self, product_id: str, customer_question: str, mode: str = "REAL", source_text: str = "") -> dict[str, Any]:
        if mode.upper() != "REAL": raise PermissionError("DEMO 묶음은 종료됐습니다. 실제 AI 묶음만 지원합니다.")
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
        # The source text is never passed to the model; only a catalog-matched fact is.
        trials = []
        partial_error = ""
        for channel in ("블로그", "짧은 영상 대본", "카드뉴스"):
            try:
                trials.append(self.trial(product_id, channel, "REAL", focus_result=focus))
            except (ValueError, PermissionError):
                if not trials: raise
                partial_error = "일부 채널 생성이 중단됐습니다. 남은 사용량과 활동 기록을 확인해 주세요."
                break
        result = self.repository.group_trials(product, data["sync"], question, source_text, focus, trials, now())
        return {**result, "mode": "REAL", "dry_run": True, "published": False,
                "focus_result": focus or "UNKNOWN", "performance_label": "연결되지 않음", "cost_label": f"AI {len(trials)}회 · 예산 예약액 {REQUEST_BUDGET_RESERVATION_KRW * len(trials):,.0f}원 (실제 청구액 아님)", "partial_error": partial_error}

    def bundles(self) -> list[dict[str, Any]]: return self.repository.bundles()

    def decide(self, approval_id: int, decision: str, note: str) -> dict[str, Any]:
        states={"approve":"APPROVED","reject":"REJECTED","revise":"REVISION_REQUESTED"}
        if decision not in states: raise ValueError("지원하지 않는 결정입니다.")
        self.repository.decide(approval_id,states[decision],note,now())
        return {"ok":True,"status":states[decision],"message":"승인 이력만 저장했습니다. 외부 공개는 실행하지 않았습니다."}
