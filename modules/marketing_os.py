"""ROADLOG 어댑터를 Generic AI Marketing Core에 연결하는 호환 파사드."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from typing import Any
from zoneinfo import ZoneInfo
from modules.config import DATA_DIR
from modules.marketing_core import BrandPolicy, MarketingRepository, MarketingService, TeamOperations, review_draft as core_review
from modules.marketing_roadlog import RoadLogCatalog, performance_snapshot
from modules.marketing_diagnosis import build_profile, diagnose
from modules.marketing_research import BraveResearchProvider
from modules.marketing_assets import MarketingAssetStore
from modules.marketing_gemini import RoadLogGeminiProvider
from modules.marketing_instagram import InstagramPublisher, configuration as instagram_configuration, configured as instagram_configured, publishing_enabled as instagram_publishing_enabled, image_url_ok
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

def status(web_root: Path) -> dict[str, Any]:
    result = _service(web_root).status()
    result["dry_run_scope"] = "automatic_external_publishing"
    result["manual_instagram_publish_enabled"] = instagram_configured() and instagram_publishing_enabled()
    return result
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
def approvals() -> list[dict[str, Any]]:
    items = _service().approvals()
    assets = MarketingAssetStore(MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID), Path(DATA_DIR))
    for item in items:
        if item["status"] in {"PENDING", "APPROVED"}:
            item["creative_assets"] = assets.list_for_approval(item["id"])
            item["creative_status"] = "IMPORTED_UNVERIFIED" if item["creative_assets"] else "ASSET_REQUIRED"
        else:
            item["creative_assets"] = []
            item["creative_status"] = "NOT_APPLICABLE"
        if item["platform"] == "인스타그램":
            item["caption"] = "\n\n".join(str(item.get(k) or "") for k in ("title", "hook", "body", "cta") if item.get(k))
    return items
def creative_brief(approval_id: int) -> dict[str, Any]:
    return MarketingAssetStore(MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID), Path(DATA_DIR)).brief(approval_id)
def import_creative_asset(approval_id: int, kind: str, mime: str, data_base64: str) -> dict[str, Any]:
    return MarketingAssetStore(MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID), Path(DATA_DIR)).import_base64(approval_id,kind,mime,data_base64)
def creative_asset_file(asset_id: int) -> tuple[Path, str]:
    return MarketingAssetStore(MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID), Path(DATA_DIR)).private_file(asset_id)
def decide(approval_id: int, decision: str, note: str) -> dict[str, Any]: return _service().decide(approval_id, decision, note)

def instagram_status() -> dict[str, Any]:
    configured = instagram_configured()
    enabled = instagram_publishing_enabled()
    return {"target": "@mumung_101", "configured": configured, "publishing_enabled": enabled,
            "label": "Meta 연결 정보 없음" if not configured else "게시 비활성화" if not enabled else "키 설정됨 · 계정 검증은 게시 직전",
            "posts": MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID).instagram_posts()}

def publish_instagram(approval_id: int, image_url: str, *, publisher: InstagramPublisher | None = None) -> dict[str, Any]:
    """The only external publish path: a single explicit admin request per approved post."""
    if operations().dashboard()["status"]["status"] == "EMERGENCY_STOP":
        raise PermissionError("AI 마케팅 팀 긴급정지 중에는 외부 게시할 수 없습니다.")
    if not instagram_publishing_enabled():
        raise PermissionError("인스타그램 게시가 비활성화돼 있습니다.")
    config = instagram_configuration()
    if config is None:
        raise PermissionError("Meta 연결 정보가 없습니다.")
    if not image_url_ok(image_url):
        raise ValueError("ROADLOG 공개 JPEG 주소만 사용할 수 있습니다.")
    repo = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID)
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    item = repo.begin_instagram_post(approval_id,image_url,stamp)
    caption = "\n\n".join(str(item[k]) for k in ("title","hook","body","cta") if item[k])
    try:
        result = (publisher or InstagramPublisher()).publish_image(image_url,caption,config)
    except Exception:
        repo.finish_instagram_post(approval_id,"UNCERTAIN",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        raise RuntimeError("인스타그램 게시 결과를 확인하지 못했습니다. 계정을 확인하기 전 재시도하지 마세요.") from None
    repo.finish_instagram_post(approval_id,"PUBLISHED",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),result["media_id"])
    return {"status":"PUBLISHED","media_id":result["media_id"],"message":"인스타그램 게시 완료"}
def set_auto_real(enabled: bool) -> dict[str, Any]:
    repo = MarketingRepository(DB, TENANT_ID, legacy_tenant_id=TENANT_ID)
    repo.set_auto_real(enabled)
    return {"ok": True, "automatic_real_calls": enabled,
            "message": "매일 자동 점검 켜짐 · 실제 호출은 수동 검수 통과 후 · 외부 게시 없음" if enabled else "자동 점검 꺼짐"}
def review_draft(product: dict[str, Any], draft: dict[str, Any]) -> list[str]: return core_review(product, draft, POLICY)
def operations() -> TeamOperations: return TeamOperations(MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID),AGENTS,SCHEDULE)
def team_dashboard() -> dict[str,Any]:
    result = operations().dashboard()
    repo = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID)
    result["campaigns"] = repo.recent_campaigns()
    profile = repo.site_profile()
    if profile:
        result["site_profile"] = {"observed_at": profile["observed_at"], "catalog_hash": profile["catalog_hash"], "product_count": len(profile["products"]), "limitations": profile["limitations"]}
        recent = repo.recent_campaign_product_ids((datetime.now(ZoneInfo("Asia/Seoul"))-timedelta(days=14)).date().isoformat())
        result["diagnosis"] = diagnose(profile, recent)
    result["learning"] = repo.recent_learning()
    result["automatic_real_calls"] = repo.auto_real_enabled()
    result["approval_policy"] = "MANUAL_EVERY_PUBLICATION"
    result["next_run"] = "매일 09:00 KST" if result["automatic_real_calls"] and result["status"]["status"] == "RUNNING" else None
    result["providers"] = {
        "internal_analytics":"CONNECTED", "external_research":"CONNECTED" if BraveResearchProvider().connected else "NOT_CONNECTED",
        "search_metrics":"NOT_CONNECTED", "creative_assets":"LOCAL_ASSISTED_ONLY",
        "instagram":"MANUAL_UNVERIFIED" if instagram_configured() and instagram_publishing_enabled() else "NOT_CONNECTED",
    }
    return result
def control(action:str) -> dict[str,Any]:
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

def _run_role(task: Any, product: dict[str,Any], meta: dict[str,Any], draft: dict[str,Any] | None = None, campaign_id: int | None = None, context: list[str] | None = None) -> tuple[str,bool,dict[str,Any] | None]:
    repo = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID)
    ops = operations()
    run_id = None
    try:
        if not _team_running(): raise PermissionError("팀이 일시정지 또는 긴급정지 상태입니다.")
        run_id = repo.reserve_real_run(product["product_id"], datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
                                       20, 5, 3000, 10.0, agent_id=task.agent_id)
        provider = RoadLogGeminiProvider()
        metrics = performance_snapshot() if task.agent_id in {"marketing_director", "market_researcher", "performance_analyst"} else None
        if metrics is not None: metrics = {**metrics,"previous_learning":repo.recent_learning()}
        result = provider.generate_role(task,{**product,"synced_at":meta["synced_at"],"source_file":meta["source_file"]},draft=draft,metrics=metrics,context=context)
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
        if campaign_id: repo.campaign_event(campaign_id,task.agent_id,run_id,state,result["summary"],datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        return task.agent_id, state == "DONE", result
    except PermissionError as exc:
        if run_id is not None: repo.finish_real_run(run_id,"FAILED","AI 역할 작업 중단")
        budget = "PAUSED_BY_BUDGET" in str(exc)
        ops.record_agent_output(task.agent_id,run_id or 0,product["product_id"],"PAUSED_BY_BUDGET" if budget else "PAUSED",{"summary":"요청 또는 내부 예산 한도에 도달했습니다." if budget else "팀이 일시정지 또는 긴급정지 상태입니다.","recommendations":[],"source_facts":[],"unknowns":[task.missing_data],"review_passed":False})
        if campaign_id: repo.campaign_event(campaign_id,task.agent_id,run_id,"PAUSED_BY_BUDGET" if budget else "PAUSED","작업 중단",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        return task.agent_id,False,None
    except Exception:
        if run_id is not None: repo.finish_real_run(run_id,"FAILED","AI 역할 작업 실패")
        ops.record_agent_output(task.agent_id,run_id or 0,product["product_id"],"ERROR",{"summary":"AI 역할 작업 실패. 연결·예산·활동 기록을 확인해 주세요.","recommendations":[],"source_facts":[],"unknowns":[task.missing_data],"review_passed":False})
        if campaign_id: repo.campaign_event(campaign_id,task.agent_id,run_id,"ERROR","AI 역할 작업 실패",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        return task.agent_id,False,None

def _run_team(web_root: Path, day: str, job_key: str = "team_8") -> None:
    ops = operations()
    repo = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID)
    failures = 0
    campaign_id = None
    try:
        if not RoadLogGeminiProvider().connected:
            ops.finish_due(day,job_key,"AI 키 미연결: 유료 요청을 실행하지 않았습니다.",failed=True)
            return
        data = _service(web_root).products()
        snapshot = performance_snapshot()
        profile = build_profile(data["products"], snapshot, data["sync"]["source_hash"])
        repo.save_site_profile(profile)
        recent_ids = repo.recent_campaign_product_ids((datetime.fromisoformat(day)-timedelta(days=14)).date().isoformat())
        diagnosis = diagnose(profile, recent_ids)
        if diagnosis["decision"] == "NO_ACTION":
            ops.finish_due(day,job_key,diagnosis["reason"])
            return
        product = next(p for p in data["products"] if p["product_id"] == diagnosis["product_id"])
        if job_key == "campaign_daily":
            previous = next((c for c in repo.recent_campaigns(10) if c["status"] == "AWAITING_APPROVAL"), None)
            if previous:
                try:
                    elapsed = datetime.now(ZoneInfo("Asia/Seoul")) - datetime.fromisoformat(previous["created_at"])
                except ValueError:
                    elapsed = timedelta(days=99)
                if elapsed < timedelta(days=2):
                    campaign_id = repo.begin_campaign(product["product_id"],"DAILY",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
                    repo.campaign_event(campaign_id,"marketing_director",None,"NO_ACTION","최근 48시간 내 승인 대기 캠페인이 있어 중복 제작하지 않았습니다.",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
                    repo.finish_campaign(campaign_id,"NO_ACTION","최근 승인 대기 캠페인 점검 · 유료 요청 0건",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
                    ops.finish_due(day,job_key,"NO_ACTION · 최근 캠페인 중복 방지 · 유료 요청 0건")
                    return
        campaign_id = repo.begin_campaign(product["product_id"],"MANUAL" if job_key == "team_8" else "DAILY",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        repo.campaign_event(campaign_id,"marketing_director",None,"DIAGNOSED",diagnosis["reason"],datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        if diagnosis["selected_channel"] != "사이트 블로그":
            repo.finish_campaign(campaign_id,"NO_ACTION","상품 상세페이지 개선이 우선이지만 안전한 적용·검수 경로가 없어 블로그를 임의 생성하지 않음",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            ops.finish_due(day,job_key,"상세페이지 개선 우선 · 자동 수정 경로 미연결 · 유료 AI 요청 0건")
            return
        try:
            today = snapshot.get("today") or {}
            repo.record_learning(campaign_id,product["product_id"],f"실행 전 사이트 집계: 방문 {int(today.get('uv') or 0)}, 가입 {int(today.get('signups') or 0)}, 결제 {int(today.get('charges') or 0)}. 캠페인 귀속 성과는 아님.",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        except Exception:
            pass  # 내부 집계 장애는 팀 작업과 분리한다. 성과를 지어내지 않는다.
        ops.record_kickoff(f"{product['name']} · 상품 정본 확인",True)
        tasks = {task.agent_id:task for task in TASKS}
        _,director_ok,direction = _run_role(tasks["marketing_director"],product,data["sync"],campaign_id=campaign_id,context=[diagnosis["objective"],diagnosis["reason"]])
        if not director_ok:
            repo.finish_campaign(campaign_id,"FAILED","디렉터 결정 실패 · 콘텐츠 생성 안 함",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            ops.finish_due(day,job_key,"디렉터 결정 실패 · 외부 게시 없음",failed=True)
            return
        if direction["decision"] == "NO_ACTION":
            repo.finish_campaign(campaign_id,"NO_ACTION","디렉터가 실행 불필요 결정 · 유료 작성 요청 없음",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            ops.finish_due(day,job_key,"NO_ACTION · 디렉터 결정 · 외부 게시 없음")
            return
        if direction["decision"] not in {"CREATE","OPTIMIZE"}:
            repo.finish_campaign(campaign_id,"NO_ACTION",f"디렉터 결정 {direction['decision']} · 조사/게시 자동 실행 미허용",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            ops.finish_due(day,job_key,f"{direction['decision']} · 콘텐츠 자동 생성 보류 · 외부 게시 없음")
            return
        strategy = [direction["summary"]]
        research = BraveResearchProvider()
        if research.connected:
            try:
                sources = research.search(product["name"] + " 사주 이용 후기 질문")
                repo.save_research_sources(campaign_id,sources)
                repo.campaign_event(campaign_id,"market_researcher",None,"EXTERNAL_SOURCE",f"실제 공개 검색 결과 {len(sources)}건 저장",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
                strategy.extend(f"EXTERNAL_SOURCE {item['title']} {item['url']}: {item['summary']}" for item in sources[:3])
            except Exception:
                repo.campaign_event(campaign_id,"market_researcher",None,"RESEARCH_FAILED","외부 검색 실패 · 검색한 것으로 표시하지 않음",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        else:
            repo.campaign_event(campaign_id,"market_researcher",None,"NOT_CONNECTED","외부 검색 미연결 · AI 추론과 구분",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_run_role,tasks[aid],product,data["sync"],campaign_id=campaign_id,context=strategy)
                       for aid in ("market_researcher","seo_specialist")]
            for future in as_completed(futures):
                _,ok,output = future.result()
                if not ok: failures += 1
                elif output: strategy.append(output["summary"])
        try:
            content = _service(web_root).trial(product["product_id"],"블로그","REAL",trigger="AUTO",defer_approval=True,strategy_context=strategy)
            ops.record_agent_output("content_writer",content["run_id"],product["product_id"],"DONE" if content["ok"] else "REVISION_REQUESTED",
                                    {"summary":f"AI 블로그 초안 #{content['content_id']} · AI 품질 검수 대기", "recommendations":[],"source_facts":[product["product_id"]],"unknowns":content["review"]["reasons"],"review_passed":False})
            repo.campaign_event(campaign_id,"content_writer",content["run_id"],"DONE" if content["ok"] else "REVISION_REQUESTED",f"AI 블로그 초안 #{content['content_id']}",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        except Exception:
            content = None
            failures += 1
            ops.record_agent_output("content_writer",0,product["product_id"],"ERROR",{"summary":"AI 초안 생성 실패", "recommendations":[],"source_facts":[],"unknowns":[],"review_passed":False})
            repo.campaign_event(campaign_id,"content_writer",None,"ERROR","AI 초안 생성 실패",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        reviewer = next(t for t in TASKS if t.agent_id == "quality_reviewer")
        approved = False
        revision = 0
        while content and _team_running():
            _,review_ok,review_note = _run_role(reviewer,product,data["sync"],content["draft"],campaign_id=campaign_id,context=strategy)
            approved = repo.finalize_agent_review(content["content_id"],review_ok and _team_running(),datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            if approved: break
            failures += 1
            if revision >= 2: break
            revision += 1
            feedback = (content["review"]["reasons"] + ([review_note["summary"]] if review_note else []))[:3]
            try:
                content = _service(web_root).trial(product["product_id"],"블로그","REAL",trigger="AUTO",defer_approval=True,strategy_context=["수정 요청: " + " / ".join(feedback),*strategy])
                ops.record_agent_output("content_writer",content["run_id"],product["product_id"],"DONE" if content["ok"] else "REVISION_REQUESTED",
                                        {"summary":f"AI 수정 초안 #{content['content_id']} · {revision}차", "recommendations":[],"source_facts":[product["product_id"]],"unknowns":content["review"]["reasons"],"review_passed":False})
                repo.campaign_event(campaign_id,"content_writer",content["run_id"],"DONE" if content["ok"] else "REVISION_REQUESTED",f"AI 수정 초안 #{content['content_id']} · {revision}차",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
            except Exception:
                content = None
                failures += 1
                repo.campaign_event(campaign_id,"content_writer",None,"ERROR","AI 수정 초안 생성 실패",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
                break
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_run_role,tasks[aid],product,data["sync"],draft=content["draft"] if content else None,campaign_id=campaign_id,context=strategy)
                       for aid in ("creative_director","social_manager","performance_analyst")]
            for future in as_completed(futures):
                if not future.result()[1]: failures += 1
        repo.finish_campaign(campaign_id,"AWAITING_APPROVAL" if content and approved else "NEEDS_REVISION",f"역할별 실패/차단 {failures}건 · 외부 게시 없음",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        ops.record_report(day)
        ops.finish_due(day,job_key,f"8명 역할별 AI 작업 종료 · 실패/차단 {failures}건 · 외부 게시 없음",failed=bool(failures))
    except Exception:
        if campaign_id: repo.finish_campaign(campaign_id,"FAILED","팀 작업 중단 · 외부 게시 없음",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"))
        ops.finish_due(day,job_key,"8명 작업 중단. 팀원별 결과와 실패 기록을 확인해 주세요. 외부 게시 없음",failed=True)
def _daily_product(web_root: Path, day: str) -> dict[str, Any]:
    catalog = _service(web_root).products()["products"]
    verified = [p for p in catalog if p["facts_status"] == "VERIFIED" and p.get("confirmed_results")]
    if not verified: raise ValueError("확인된 상품 정본과 결과 항목이 없습니다.")
    recent = MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID).recent_campaign_product_ids((datetime.fromisoformat(day)-timedelta(days=14)).date().isoformat())
    candidates = [p for p in verified if p["product_id"] not in recent] or verified
    product = candidates[datetime.fromisoformat(day).date().toordinal() % len(candidates)]
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
    local = (when or datetime.now(ZoneInfo("Asia/Seoul"))).astimezone(ZoneInfo("Asia/Seoul"))
    if local.strftime("%H:%M") >= "09:00" and MarketingRepository(DB,TENANT_ID,legacy_tenant_id=TENANT_ID).auto_real_enabled():
        day = local.date().isoformat()
        if ops.claim_daily_campaign(day):
            Thread(target=_run_team,args=(web_root,day,"campaign_daily"),daemon=True,name="roadlog-marketing-daily").start()
            results.append({"date":day,"job":"campaign_daily","status":"RUNNING","result":"자동 캠페인 점검 시작 · 외부 게시 없음"})
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
