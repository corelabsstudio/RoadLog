"""ROADLOG 어댑터를 Generic AI Marketing Core에 연결하는 호환 파사드."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from typing import Any
from zoneinfo import ZoneInfo
from modules.config import DATA_DIR
from modules.marketing_core import BrandPolicy, MarketingRepository, MarketingService, TeamOperations, review_draft as core_review
from modules.marketing_roadlog import RoadLogCatalog, performance_snapshot
from modules.marketing_gemini import RoadLogGeminiProvider
from modules.marketing_core.agents import TASKS

DB = Path(DATA_DIR) / "marketing_os.db"
TENANT_ID = "roadlog"
POLICY = BrandPolicy(
    brand_names=("ROADLOG", "로드로그"),
    guarantee_pattern=r"무조건|반드시\s*(?:재회|성공|당첨)|100\s*%|확실(?:히|한)|보장|운명\s*(?:확정|변경)|수익\s*보장|효과\s*보장",
    cliche_pattern=r"혁신적인|획기적인|차세대|게임\s*체인저|한\s*차원\s*높은|새로운\s*가능성을\s*열",
    blocked_brand_pattern=r"ChatGPT|챗GPT|포스텔러|점신|신한라이프",
)
AGENTS=[("marketing_director","Marketing Director","마케팅 디렉터"),("market_researcher","Market Researcher","시장 조사원"),("seo_specialist","SEO Specialist","검색 전략가"),("content_writer","Content Writer","콘텐츠 작가"),("creative_director","Creative Director","크리에이티브 디렉터"),("social_manager","Social Manager","채널 매니저"),("quality_reviewer","Quality Reviewer","품질 검수자"),("performance_analyst","Performance Analyst","성과 분석가")]
SCHEDULE=[{"time":"팀 시작","job":"team_8","name":"8명 독립 AI 작업 · 정본 검수 · 일일 보고서","automatic":False}]

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
        day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        ops = operations()
        if not RoadLogGeminiProvider().connected:
            ops.mark_ai_unavailable()
            result["message"] = "Gemini API 키가 연결되지 않아 8명 AI 작업을 실행하지 않았습니다. 유료 요청은 0건입니다."
            result["jobs"] = [{"job":"team_8","status":"WAITING_AI"}]
            return result
        if not ops.claim_team_start(day):
            result["message"] = "오늘 8명 작업은 이미 시작했습니다. 팀원별 결과와 실패 기록을 확인해 주세요."
            result["jobs"] = [{"job":"team_8","status":"SKIPPED"}]
            return result
        Thread(target=_run_team, args=(web_root,day), daemon=True, name="roadlog-marketing-team").start()
        result["message"] = "독립 AI 팀원 8명의 작업을 시작했습니다. 화면을 새로고침해 역할별 결과를 확인해 주세요. 실제 청구액은 내부 예약액과 다릅니다. 외부 게시는 하지 않습니다."
        result["jobs"] = [{"job":"team_8","status":"RUNNING"}]
    return result

def _team_running() -> bool:
    return operations().dashboard()["status"]["status"] == "RUNNING"

def _run_role(task: Any, product: dict[str,Any], meta: dict[str,Any], draft: dict[str,Any] | None = None) -> tuple[str,bool]:
    repo = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID)
    ops = operations()
    run_id = None
    try:
        if not _team_running(): raise PermissionError("팀이 일시정지 또는 긴급정지 상태입니다.")
        run_id = repo.reserve_real_run(product["product_id"], datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
                                       20, 5, 3000, 10.0, agent_id=task.agent_id)
        provider = RoadLogGeminiProvider()
        metrics = performance_snapshot() if task.agent_id in {"marketing_director", "market_researcher", "performance_analyst"} else None
        result = provider.generate_role(task,{**product,"synced_at":meta["synced_at"],"source_file":meta["source_file"]},draft=draft,metrics=metrics)
        from modules.marketing_core.policy import review_draft, review_metric_note
        note = "\n".join([result["summary"], *result["recommendations"]])
        safe_draft = {"body": note,"factual_claims": [], "source_facts": product["product_id"]}
        reasons = review_metric_note(note,metrics,POLICY) if metrics else review_draft(product,safe_draft,POLICY)
        allowed = {product["product_id"],product["name"],*(product.get("confirmed_results") or [])}
        if metrics: allowed.add(metrics["source"])
        if any(fact not in allowed for fact in result["source_facts"]): reasons.append("상품 정본에 없는 출처 사실")
        if task.agent_id == "quality_reviewer" and not result["review_passed"]: reasons.append("AI 품질 검수에서 차단")
        if reasons:
            result["unknowns"].extend(reasons)
            state = "REVISION_REQUESTED"
        else:
            state = "DONE"
        repo.finish_real_run(run_id,"COMPLETED" if state == "DONE" else "BLOCKED",result["summary"],**provider.usage)
        ops.record_agent_output(task.agent_id,run_id,product["product_id"],state,result)
        return task.agent_id, state == "DONE"
    except PermissionError as exc:
        if run_id is not None: repo.finish_real_run(run_id,"FAILED","AI 역할 작업 중단")
        budget = "PAUSED_BY_BUDGET" in str(exc)
        ops.record_agent_output(task.agent_id,run_id or 0,product["product_id"],"PAUSED_BY_BUDGET" if budget else "PAUSED",{"summary":"요청 또는 내부 예산 한도에 도달했습니다." if budget else "팀이 일시정지 또는 긴급정지 상태입니다.","recommendations":[],"source_facts":[],"unknowns":[task.missing_data],"review_passed":False})
        return task.agent_id,False
    except Exception:
        if run_id is not None: repo.finish_real_run(run_id,"FAILED","AI 역할 작업 실패")
        ops.record_agent_output(task.agent_id,run_id or 0,product["product_id"],"ERROR",{"summary":"AI 역할 작업 실패. 연결·예산·활동 기록을 확인해 주세요.","recommendations":[],"source_facts":[],"unknowns":[task.missing_data],"review_passed":False})
        return task.agent_id,False

def _run_team(web_root: Path, day: str) -> None:
    ops = operations()
    repo = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID)
    failures = 0
    try:
        if not RoadLogGeminiProvider().connected:
            ops.finish_due(day,"team_8","AI 키 미연결: 유료 요청을 실행하지 않았습니다.",failed=True)
            return
        data = _service(web_root).products()
        product = _daily_product(web_root,day)
        ops.record_kickoff(f"{product['name']} · 상품 정본 확인",True)
        independent = [t for t in TASKS if t.agent_id not in ("content_writer","quality_reviewer")]
        # Each role owns a fresh provider, reservation, output row and failure boundary.
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_run_role,t,product,data["sync"]) for t in independent]
            writer = pool.submit(_service(web_root).trial,product["product_id"],"블로그","REAL",trigger="AUTO",defer_approval=True)
            for future in as_completed(futures):
                if not future.result()[1]: failures += 1
            try:
                content = writer.result()
                ops.record_agent_output("content_writer",content["run_id"],product["product_id"],"DONE" if content["ok"] else "REVISION_REQUESTED",
                                        {"summary":f"AI 블로그 초안 #{content['content_id']} · AI 품질 검수 대기", "recommendations":[],"source_facts":[product["product_id"]],"unknowns":content["review"]["reasons"],"review_passed":False})
            except Exception:
                content = None
                failures += 1
                ops.record_agent_output("content_writer",0,product["product_id"],"ERROR",{"summary":"AI 초안 생성 실패", "recommendations":[],"source_facts":[],"unknowns":[],"review_passed":False})
        reviewer = next(t for t in TASKS if t.agent_id == "quality_reviewer")
        _,review_ok = _run_role(reviewer,product,data["sync"],content["draft"] if content else None)
        if not review_ok: failures += 1
        if content:
            approved = repo.finalize_agent_review(content["content_id"],review_ok and _team_running(),datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            if not approved: failures += 1
        ops.record_report(day)
        ops.finish_due(day,"team_8",f"8명 역할별 AI 작업 종료 · 실패/차단 {failures}건 · 외부 게시 없음",failed=bool(failures))
    except Exception:
        ops.finish_due(day,"team_8","8명 작업 중단. 팀원별 결과와 실패 기록을 확인해 주세요. 외부 게시 없음",failed=True)
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
