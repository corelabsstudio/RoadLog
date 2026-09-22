"""ROADLOG 어댑터를 Generic AI Marketing Core에 연결하는 호환 파사드."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
from modules.config import DATA_DIR
from modules.marketing_core import BrandPolicy, MarketingRepository, MarketingService, TeamOperations, review_draft as core_review
from modules.marketing_roadlog import RoadLogCatalog
from modules.marketing_gemini import RoadLogGeminiProvider

DB = Path(DATA_DIR) / "marketing_os.db"
TENANT_ID = "roadlog"
POLICY = BrandPolicy(
    brand_names=("ROADLOG", "로드로그"),
    guarantee_pattern=r"무조건|반드시\s*(?:재회|성공|당첨)|100\s*%|확실(?:히|한)|보장|운명\s*(?:확정|변경)|수익\s*보장|효과\s*보장",
    cliche_pattern=r"혁신적인|획기적인|차세대|게임\s*체인저|한\s*차원\s*높은|새로운\s*가능성을\s*열",
    blocked_brand_pattern=r"ChatGPT|챗GPT|포스텔러|점신|신한라이프",
)
AGENTS=[("marketing_director","Marketing Director","마케팅 디렉터"),("market_researcher","Market Researcher","시장 조사원"),("seo_specialist","SEO Specialist","검색 전략가"),("content_writer","Content Writer","콘텐츠 작가"),("creative_director","Creative Director","크리에이티브 디렉터"),("social_manager","Social Manager","채널 매니저"),("quality_reviewer","Quality Reviewer","품질 검수자"),("performance_analyst","Performance Analyst","성과 분석가")]
SCHEDULE=[{"time":"즉시","job":"kickoff","name":"상품 정본 점검","automatic":False},{"time":"즉시","job":"market","name":"시장 데이터 연결 상태 확인","automatic":False},{"time":"즉시","job":"seo","name":"검색 데이터 연결 상태 확인","automatic":False},{"time":"즉시","job":"content","name":"검증된 상품 AI 초안 1건","automatic":False},{"time":"즉시","job":"review","name":"새 초안 사실 검수","automatic":False},{"time":"즉시","job":"report","name":"일일 보고서","automatic":False}]

def _service(web_root: Path = Path(".")) -> MarketingService:
    provider = RoadLogGeminiProvider()
    return MarketingService(RoadLogCatalog(web_root), provider, MarketingRepository(DB, TENANT_ID, legacy_tenant_id=TENANT_ID), POLICY, real_content=provider)

def status(web_root: Path) -> dict[str, Any]: return _service(web_root).status()
def products(web_root: Path) -> dict[str, Any]: return _service(web_root).products()
def usage() -> dict[str, Any]: return _service().usage()
def trial(web_root: Path, product_id: str, platform: str, mode: str) -> dict[str, Any]:
    result = _service(web_root).trial(product_id, platform, mode)
    operations().record_real_content(result["content_id"], result["ok"], result["draft"]["product_id"])
    return result
def create_bundle(web_root: Path, product_id: str, customer_question: str, mode: str, source_text: str = "") -> dict[str, Any]:
    ops = operations()
    result = _service(web_root).create_bundle(product_id, customer_question, mode, source_text)
    ops.record_bundle(result["bundle_id"], len(result["items"]))
    return result
def bundles() -> list[dict[str, Any]]: return _service().bundles()
def approvals() -> list[dict[str, Any]]: return _service().approvals()
def decide(approval_id: int, decision: str, note: str) -> dict[str, Any]: return _service().decide(approval_id, decision, note)
def set_auto_real(enabled: bool) -> dict[str, Any]:
    repo = MarketingRepository(DB, TENANT_ID, legacy_tenant_id=TENANT_ID)
    repo.set_auto_real(False)
    if enabled: raise PermissionError("시간 예약 AI 호출은 종료됐습니다. 팀 시작 시 즉시 실행합니다.")
    return {"ok": True, "automatic_real_calls": False, "message": "시간 예약 AI 호출 꺼짐"}
def review_draft(product: dict[str, Any], draft: dict[str, Any]) -> list[str]: return core_review(product, draft, POLICY)
def operations() -> TeamOperations: return TeamOperations(MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID),AGENTS,SCHEDULE)
def team_dashboard() -> dict[str,Any]: return operations().dashboard()
def control(action:str) -> dict[str,Any]:
    if action == "start":
        MarketingRepository(DB, TENANT_ID, legacy_tenant_id=TENANT_ID).set_auto_real(False)
    result = operations().control(action)
    if action == "start":
        web_root = Path(__file__).resolve().parents[1] / "web"
        ops = operations()
        day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        jobs = []
        try:
            product = _daily_product(web_root, day)
            ops.record_kickoff(f"{product['name']} · 상품 정본 확인", bool(_service(web_root).real_content.connected))
            jobs.append({"job":"kickoff","status":"COMPLETED"})
        except Exception:
            result["message"] = "팀은 켜졌지만 상품 정본 점검에 실패했습니다. 상품 정보를 확인해 주세요."
            result["jobs"] = [{"job":"kickoff","status":"FAILED"}]
            return result
        for job in ("market", "seo"):
            ops.run_job(job)
            jobs.append({"job":job,"status":"WAITING_DATA"})
        provider = _service(web_root).real_content
        if provider and provider.connected and ops.claim_start_content(day):
            try:
                draft = trial(web_root, product["product_id"], "블로그", "REAL")
                ops.finish_due(day, "start_content", f"실제 AI 초안 #{draft['content_id']} · {draft['status']} · 외부 게시 없음")
                jobs.append({"job":"content","status":draft["status"]})
            except Exception:
                ops.finish_due(day, "start_content", "AI 생성 실패. 오늘 자동 재호출 없음; 사용량과 작업 기록을 확인해 주세요.", failed=True)
                jobs.append({"job":"content","status":"FAILED"})
        else:
            reason = "AI 미연결" if not provider or not provider.connected else "오늘 팀 시작 AI 초안 이미 실행"
            ops.record_content_skipped(reason)
            jobs.append({"job":"content","status":"SKIPPED","reason":reason})
        ops.record_report(day)
        jobs.append({"job":"report","status":"COMPLETED"})
        result["jobs"] = jobs
        result["message"] = "팀 작업을 즉시 실행했습니다. " + ("AI 초안 생성 결과를 확인해 주세요." if jobs[-2]["status"] not in ("SKIPPED", "FAILED") else "AI 초안은 생성되지 않았습니다. 연결·사용량·활동 기록을 확인해 주세요.")
    return result
def _daily_product(web_root: Path, day: str) -> dict[str, Any]:
    catalog = _service(web_root).products()["products"]
    verified = [p for p in catalog if p["facts_status"] == "VERIFIED" and p.get("confirmed_results")]
    if not verified: raise ValueError("확인된 상품 정본과 결과 항목이 없습니다.")
    product = verified[datetime.fromisoformat(day).date().toordinal() % len(verified)]
    return product

def _real_daily_draft(web_root: Path, day: str) -> str:
    product = _daily_product(web_root, day)
    result = _service(web_root).trial(product["product_id"], "블로그", "REAL", trigger="AUTO")
    operations().record_real_content(result["content_id"], result["ok"], product["name"])
    return f"{product['name']} · 실제 AI 초안 #{result['content_id']} · {result['status']} · 외부 게시 없음"

def run_job(job_key:str) -> dict[str,Any]:
    if job_key == "content":
        if operations().dashboard()["status"]["status"] != "RUNNING": raise ValueError("먼저 AI 팀을 시작해 주세요.")
        day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        return {"ok":True,"message":_real_daily_draft(Path(__file__).resolve().parents[1] / "web", day)}
    return operations().run_job(job_key)

def run_due(web_root: Path, when: datetime | None = None) -> list[dict[str, str]]:
    """Claim each KST daily job once; AI needs manual proof and explicit auto opt-in."""
    ops = operations()
    results = []
    for day, job_key in ops.claim_due(when):
        try:
            if job_key == "kickoff":
                product = _daily_product(web_root, day)
                result = f"{product['name']} · 상품 정본 확인 · AI 초안/외부 게시 없음"
                ops.record_kickoff(result, _service(web_root).status()["automatic_real_calls"])
            elif job_key == "content":
                result = _real_daily_draft(web_root, day)
            elif job_key == "report":
                ops.record_report(day)
                result = f"{day} 일일 보고서 저장 · 외부 성과 연결되지 않음"
            else:
                raise ValueError("자동 실행이 허용되지 않은 작업입니다.")
            ops.finish_due(day, job_key, result)
            results.append({"date":day,"job":job_key,"status":"COMPLETED","result":result})
        except Exception:
            result = "예약 작업에 실패했습니다. 관리자 화면에서 상품 정본과 작업 기록을 확인해 주세요. 자동 재시도 없음."
            ops.finish_due(day, job_key, result, failed=True)
            results.append({"date":day,"job":job_key,"status":"FAILED","result":result})
    return results
