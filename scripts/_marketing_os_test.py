"""Marketing real-mode regression; paid APIs are always mocked."""
from __future__ import annotations
import json, os, shutil, sqlite3, sys, tempfile, time, types
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if "dotenv" not in sys.modules:
    stub = types.ModuleType("dotenv")
    stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = stub
from modules import marketing_os
from modules.marketing_core import MarketingRepository
from modules.marketing_gemini import RoadLogGeminiProvider
from modules.marketing_core.agents import TASKS
from modules.marketing_core.policy import review_metric_note
from modules import marketing_roadlog

def check(value, label):
    assert value, label
    print("OK", label)

class FakeGemini:
    name, model, connected = "TEST", "fake", True
    def __init__(self): self.usage = {"input_tokens": 60, "output_tokens": 30}
    def generate(self, item, platform):
        focus = item.get("marketing_focus_result") or item["confirmed_results"][0]
        return {"platform": platform, "product_id": item["product_id"], "title": item["name"],
                "hook": "정본 항목을 살펴보세요.", "body": f"ROADLOG 상품은 {item['price_won']:,}원입니다. {focus} 항목을 확인해 보세요.",
                "cta": "상품 화면에서 확인하세요.", "image_prompt": "차분한 사주 서비스 화면, 가격 글자 없음",
                "factual_claims": [focus], "source_facts": item["product_id"], "uncertainty": [], "estimated_cost": None}
    seen_metrics = []
    def generate_role(self, task, item, *, draft=None, metrics=None):
        if metrics: self.seen_metrics.append(metrics)
        return {"summary": f"{task.agent_id} 상품 정본을 검토했습니다.", "recommendations": ["상품 설명 확인"],
                "source_facts": [metrics["source"] if metrics else item["product_id"]], "unknowns": [task.missing_data], "review_passed": bool(draft)}

def main():
    temp = Path(tempfile.mkdtemp(prefix="roadlog_marketing_real_"))
    original_provider = marketing_os.RoadLogGeminiProvider
    original_snapshot = marketing_os.performance_snapshot
    old_key = os.environ.pop("GEMINI_API_KEY", None)
    try:
        marketing_os.performance_snapshot = lambda: {"source":"roadlog.stats.overview","period_days":7,"today":{"uv":12,"signups":2},"month":{"sales":2900},"by_source":[],"by_campaign":[],"limitations":["인스타 미연결"]}
        web = temp / "web"
        (web / "admin").mkdir(parents=True)
        shutil.copy2(ROOT / "web/admin/marketing-products.json", web / "admin/marketing-products.json")
        marketing_os.DB = temp / "marketing_os.db"
        legacy = temp / "legacy.db"
        with sqlite3.connect(legacy) as conn: conn.execute("CREATE TABLE marketing_content(id INTEGER PRIMARY KEY)")
        def open_db(_): MarketingRepository(legacy, "tenant-a").connect().close()
        with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(open_db, range(16)))
        with sqlite3.connect(legacy) as conn: columns = {r[1] for r in conn.execute("PRAGMA table_info(marketing_content)")}
        check({"tenant_id", "bundle_id"} <= columns, "기존 DB 병렬 스키마 이관")
        state = marketing_os.status(web)
        check(state["mode"] == "AI 미연결" and not state["real_trial_enabled"], "키 없음 · DEMO 미표시")
        check(state["verified_count"] == state["product_count"] == 44, "상품 정본 44개 대조")
        product = next(p for p in marketing_os.products(web)["products"] if not p["free"] and p["confirmed_results"])
        try:
            marketing_os.trial(web, product["product_id"], "블로그", "DEMO")
            raise AssertionError("DEMO allowed")
        except PermissionError: print("OK DEMO 생성 거부")
        try:
            marketing_os.set_auto_real(True)
            raise AssertionError("auto before proof")
        except PermissionError: print("OK 첫 수동 검증 전 자동 잠금")
        no_key_start = marketing_os.control("start")
        check(no_key_start["jobs"][0]["status"] == "WAITING_AI" and marketing_os.usage()["requests"] == 0, "키 없을 때 8명 대기 · 유료 호출 0")
        marketing_os.RoadLogGeminiProvider = FakeGemini
        day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        started = marketing_os.control("start")
        check(started["status"] == "RUNNING" and started["jobs"][0]["job"] == "team_8", "팀 시작 즉시 8명 배치")
        for _ in range(100):
            if any(j["job_key"] == "team_8" and j["status"] != "RUNNING" for j in marketing_os.team_dashboard()["scheduled_runs"]): break
            time.sleep(0.05)
        else: raise AssertionError("eight-agent batch did not finish")
        team = marketing_os.team_dashboard()
        check({o["agent_id"] for o in team["agent_outputs"]} == {a["agent_id"] for a in team["agents"]}, "8명 각각 결과 저장")
        check(len({o["run_id"] for o in team["agent_outputs"]}) == 8 and all(o["run_id"] > 0 for o in team["agent_outputs"]), "8명 각각 독립 요청")
        check(marketing_os.usage()["requests"] == 8 and marketing_os.usage()["estimated_cost_krw"] == 80, "8명 요청·내부 예약 80원")
        check(len(FakeGemini.seen_metrics) == 3 and all(m["today"]["uv"] == 12 for m in FakeGemini.seen_metrics), "디렉터·시장 조사원·성과 분석가에게 실제 집계 구조 전달")
        check(len(marketing_os.approvals()) == 1, "작성자·AI 검수 통과 후 승인 등록")
        check(not marketing_os.bundles(), "시작 시 가짜 묶음 없음")
        check(all(a["status"] != "IDLE" for a in marketing_os.team_dashboard()["agents"]), "8개 역할에 실제 작업 또는 대기 사유")
        with MarketingRepository(marketing_os.DB, "roadlog").connect() as conn:
            conn.execute("UPDATE marketing_agents SET status='DONE',current_task='영상 대본·카드뉴스 문안 준비' WHERE tenant_id='roadlog' AND agent_id='creative_director'")
        agents = marketing_os.team_dashboard()["agents"]
        check(next(a for a in agents if a["agent_id"] == "creative_director")["status"] == "WAITING_CONTENT", "과거 DEMO 현재 직원 상태 정리")
        due_time = datetime.fromisoformat(day + "T11:05:00+09:00")
        check(not marketing_os.run_due(web, due_time), "시각 기반 AI 예약 없음")
        repeated = marketing_os.control("start")
        check(not repeated["changed"] and repeated["jobs"][0]["status"] == "SKIPPED" and marketing_os.usage()["requests"] == 8, "켜진 팀 재실행 중복 과금 없음")
        marketing_os.control("pause")
        resumed = marketing_os.control("start")
        check(resumed["jobs"][0]["status"] == "SKIPPED" and marketing_os.usage()["requests"] == 8, "일시정지 후 재시작해도 하루 첫 호출만")
        one = marketing_os.trial(web, product["product_id"], "블로그", "REAL")
        check(one["ok"] and one["approval_id"], "모의 REAL 초안 검수 통과·승인 등록")
        check(marketing_os.status(web)["manual_real_success"] and not marketing_os.status(web)["automatic_real_calls"], "시간 예약 AI 생성 꺼짐")
        try:
            marketing_os.set_auto_real(True)
            raise AssertionError("scheduled AI enabled")
        except PermissionError: print("OK 시간 예약 AI 호출 거부")
        due = marketing_os.run_due(web, due_time)
        check(not due and not marketing_os.run_due(web, due_time), "11시에도 예약 호출 없음")
        check(marketing_os.usage()["requests"] == 9 and marketing_os.usage()["estimated_cost_krw"] == 90, "요청 9건·내부 예산 예약")
        with MarketingRepository(marketing_os.DB, "roadlog").connect() as conn:
            real = conn.execute("SELECT COUNT(*) n,MAX(input_tokens) tin FROM marketing_runs WHERE mode='REAL' AND tenant_id='roadlog'").fetchone()
            demo = conn.execute("SELECT COUNT(*) n FROM marketing_runs WHERE mode='DEMO' AND tenant_id='roadlog'").fetchone()
        check(real["n"] == 9 and real["tin"] == 60 and demo["n"] == 0, "토큰 기록·새 DEMO 작업 없음")
        bundle = marketing_os.create_bundle(web, product["product_id"], product["confirmed_results"][0] + "은 무엇인가요?", "REAL")
        check(bundle["mode"] == "REAL" and len(bundle["items"]) == 3 and all(i["approval_id"] for i in bundle["items"]), "실제 AI 묶음 3건·검수")
        check(marketing_os.bundles()[0]["status"] == "REAL_REVIEWED", "REAL 묶음 저장")
        with MarketingRepository(marketing_os.DB, "roadlog").connect() as conn:
            old_content = conn.execute("INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,review_reasons_json,fact_snapshot_json,estimated_cost_krw,mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("roadlog", product["product_id"], product["name"], "블로그", "옛 DEMO", "", "", "", "", "PENDING_APPROVAL", "옛 기록", "[]", "{}", None, "DEMO", day)).lastrowid
            old_approval = conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", ("roadlog", old_content, "PENDING", day)).lastrowid
        check(all(a["id"] != old_approval for a in marketing_os.approvals()), "과거 DEMO 승인 대기 제외")
        try:
            marketing_os.decide(old_approval, "approve", "")
            raise AssertionError("old demo approved")
        except ValueError: print("OK 과거 DEMO 승인 API 차단")
        try:
            marketing_os.trial(web, product["product_id"], "블로그", "REAL")
            raise AssertionError("budget not enforced")
        except PermissionError: print("OK 작성자 하루 5건 요청 한도")
        marketing_os.set_auto_real(False)
        check(not marketing_os.status(web)["automatic_real_calls"], "자동 생성 끄기")
        check("외부 공개는 실행하지 않았습니다" in marketing_os.decide(one["approval_id"], "approve", "")["message"], "승인 후 외부 게시 없음")
        class RejectReviewer(FakeGemini):
            def generate_role(self, task, item, *, draft=None, metrics=None):
                if task.agent_id == "market_researcher": raise ValueError("mock role failure")
                result = super().generate_role(task,item,draft=draft,metrics=metrics)
                if task.agent_id == "quality_reviewer": result["review_passed"] = False
                return result
        marketing_os.DB = temp / "review.db"
        marketing_os.RoadLogGeminiProvider = RejectReviewer
        rejected_start = marketing_os.control("start")
        check(rejected_start["jobs"][0]["status"] == "RUNNING", "차단 사례 8명 작업 시작")
        for _ in range(100):
            runs = marketing_os.team_dashboard()["scheduled_runs"]
            if any(j["job_key"] == "team_8" and j["status"] != "RUNNING" for j in runs): break
            time.sleep(0.05)
        else: raise AssertionError("rejected team did not finish")
        blocked_team = marketing_os.team_dashboard()
        check(not marketing_os.approvals() and blocked_team["content"][0]["status"] == "REVISION_REQUESTED", "AI 검수 실패 시 승인 대기 미등록")
        check({o["agent_id"] for o in blocked_team["agent_outputs"]} == {a["agent_id"] for a in blocked_team["agents"]}
              and next(o for o in blocked_team["agent_outputs"] if o["agent_id"] == "market_researcher")["status"] == "ERROR", "한 역할 실패해도 나머지 역할 격리")
        class FalseGemini(FakeGemini):
            def generate(self, item, platform):
                draft = super().generate(item, platform)
                draft["body"] = "현재 999,999원 할인 이벤트. 재회 100% 보장."
                return draft
        marketing_os.DB = temp / "false.db"
        marketing_os.RoadLogGeminiProvider = FalseGemini
        failed = marketing_os.trial(web, product["product_id"], "블로그", "REAL")
        check(not failed["ok"] and failed["approval_id"] is None and not marketing_os.approvals(), "거짓 가격·할인·보장 승인 차단")
        check("응답 확인" in marketing_os.status(web)["connection_label"], "실제 공급자 응답과 검수 통과 구분")
        base = FakeGemini().generate(product, "블로그")
        check(any("결과 항목" in r for r in marketing_os.review_draft(product, {**base, "factual_claims": ["없는 기능"]})), "없는 결과 항목 차단")
        check(any("수치" in r for r in marketing_os.review_draft(product, {**base, "body": "사용자 100명이 만족했습니다."})), "출처 없는 수치 차단")
        os.environ["GEMINI_API_KEY"] = "TEST-ONLY-NOT-REAL"
        payload = FakeGemini().generate(product, "블로그")
        def response(text): return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 7}})
        def structured_response(req):
            schema = json.loads(req.content)["generationConfig"]["responseSchema"]
            check(schema["properties"]["factual_claims"]["items"]["enum"] == product["confirmed_results"], "정본 결과 항목만 AI 스키마에서 허용")
            return response(json.dumps(payload))
        with httpx.Client(transport=httpx.MockTransport(structured_response)) as client:
            provider = RoadLogGeminiProvider(client=client, sleep=lambda _: None)
            check(provider.generate(product, "블로그")["source_facts"] == product["product_id"] and provider.usage["input_tokens"] == 5, "Gemini JSON·사용량 파싱")
        role_payload = FakeGemini().generate_role(TASKS[0], product)
        with httpx.Client(transport=httpx.MockTransport(lambda req: response(json.dumps(role_payload)))) as client:
            provider = RoadLogGeminiProvider(client=client, sleep=lambda _: None)
            check(provider.generate_role(TASKS[0], product)["summary"] == role_payload["summary"] and provider.usage["output_tokens"] == 7, "독립 역할 JSON·사용량 파싱")
        with httpx.Client(transport=httpx.MockTransport(lambda req: response("not json"))) as client:
            try:
                RoadLogGeminiProvider(client=client, sleep=lambda _: None).generate(product, "블로그")
                raise AssertionError("bad json")
            except ValueError: print("OK 잘못된 JSON 차단")
        attempts = []
        def timeout_twice(req):
            attempts.append(1)
            if len(attempts) < 3: raise httpx.ReadTimeout("timeout")
            return response(json.dumps(payload))
        with httpx.Client(transport=httpx.MockTransport(timeout_twice)) as client:
            RoadLogGeminiProvider(client=client, sleep=lambda _: None).generate(product, "블로그")
        check(len(attempts) == 3, "timeout 최대 3회 재시도")
        metrics = marketing_os.performance_snapshot()
        check(not review_metric_note("방문 12명, 가입 2명",metrics,marketing_os.POLICY), "출처 있는 성과 수치 허용")
        check(any("수치" in reason for reason in review_metric_note("방문 999명",metrics,marketing_os.POLICY)), "출처 없는 성과 수치 차단")
        original_overview = marketing_roadlog.stats.overview
        try:
            marketing_roadlog.stats.overview = lambda days: {"today":{"uv":12,"signups":2},"month":{"sales":2900},"bySource":[{"name":"직접","uv":5}],"byCampaign":[],"byProduct":[{"product":"ask:private","opens":9},{"product":"god","opens":3}],"members":[{"email":"private@example.com"}]}
            snapshot = marketing_roadlog.performance_snapshot()
            check(snapshot["today"]["uv"] == 12 and snapshot["by_product"] == [{"product_id":"god","opens":3}] and "members" not in snapshot and "private@example.com" not in json.dumps(snapshot), "사이트 성과 정본 연결·개인정보·질문 제외")
        finally:
            marketing_roadlog.stats.overview = original_overview
    finally:
        marketing_os.RoadLogGeminiProvider = original_provider
        marketing_os.performance_snapshot = original_snapshot
        if old_key is None: os.environ.pop("GEMINI_API_KEY", None)
        else: os.environ["GEMINI_API_KEY"] = old_key
        shutil.rmtree(temp, ignore_errors=True)

if __name__ == "__main__": main()
