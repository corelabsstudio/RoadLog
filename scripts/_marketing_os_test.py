from __future__ import annotations

import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

from modules import marketing_os
from modules.marketing_core import BrandPolicy, MarketingRepository, MarketingService


def check(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)
    print("OK ", message)


def main() -> None:
    temp = Path(tempfile.mkdtemp(prefix="roadlog_marketing_"))
    try:
        web = temp / "web"
        (web / "admin").mkdir(parents=True)
        shutil.copy2(ROOT / "web" / "admin" / "marketing-products.json", web / "admin" / "marketing-products.json")
        marketing_os.DB = temp / "marketing_os.db"

        old_key = os.environ.pop("GEMINI_API_KEY", None)
        state = marketing_os.status(web)
        check(state["dry_run"] is True and state["mode"] == "DEMO", "DRY RUN DEMO 고정")
        check(state["connected"] is False, "API 키 없음에도 정상 상태")
        check(state["product_count"] == 44, "상품 정본 44개 로드")
        check(state["verified_count"] == 44, "화면과 서버 상품 사실 일치")

        catalog = marketing_os.products(web)["products"]
        product = next(p for p in catalog if not p["free"] and p["confirmed_results"])
        base = {"title": product["name"], "hook": "현재 정보를 확인하세요.", "body": f"현재 {product['price_won']:,}원입니다.",
                "cta": "ROADLOG에서 확인하세요.", "factual_claims": [product["confirmed_results"][0]], "source_facts": product["product_id"]}
        check(not marketing_os.review_draft(product, base), "정상 구조 초안 검수 통과")
        wrong_price = {**base, "body": "현재 999,999원입니다."}
        check(any("가격" in r for r in marketing_os.review_draft(product, wrong_price)), "거짓 가격 차단")
        fake_discount = {**base, "body": base["body"] + " 오늘만 할인 이벤트입니다."}
        check(any("할인" in r for r in marketing_os.review_draft(product, fake_discount)), "가짜 할인 차단")
        fake_feature = {**base, "factual_claims": ["복권 당첨 번호"]}
        check(any("결과 항목" in r for r in marketing_os.review_draft(product, fake_feature)), "없는 결과 항목 차단")
        guarantee = {**base, "body": base["body"] + " 재회를 100% 보장합니다."}
        check(any("보장" in r for r in marketing_os.review_draft(product, guarantee)), "보장 표현 차단")

        result = marketing_os.trial(web, product["product_id"], "블로그", "DEMO")
        check(result["ok"] and result["approval_id"], "검수 통과만 승인 대기 등록")
        bundle = marketing_os.create_bundle(web, product["product_id"], "이 상품에서 무엇을 확인할 수 있나요?", "DEMO")
        check(bundle["dry_run"] and not bundle["published"] and len(bundle["items"]) == 4, "원본과 채널별 DEMO 4건 생성")
        check(bundle["items"][0]["status"] == "SOURCE" and bundle["items"][0]["approval_id"] is None, "원본은 승인 대기에 넣지 않음")
        check(all(item["approval_id"] for item in bundle["items"][1:]), "검수 통과한 채널별 초안만 승인 대기")
        check(marketing_os.bundles()[0]["customer_question"] == "이 상품에서 무엇을 확인할 수 있나요?", "고객 질문과 콘텐츠 묶음 저장")
        check(marketing_os.bundles()[0]["source_file"].endswith("marketing-products.json"), "상품 정본 출처 저장")
        check(any("원본·채널별" in row["action"] for row in marketing_os.team_dashboard()["activity"]), "콘텐츠 담당 활동 기록")
        try:
            marketing_os.create_bundle(web, product["product_id"], "질문", "REAL")
            raise AssertionError("묶음 REAL 호출이 차단되지 않음")
        except PermissionError:
            print("OK  묶음 REAL 유료 호출 잠금")
        try:
            marketing_os.trial(web, product["product_id"], "블로그", "REAL")
            raise AssertionError("REAL 호출이 차단되지 않음")
        except PermissionError:
            print("OK  REAL 유료 호출 잠금")
        decision = marketing_os.decide(result["approval_id"], "approve", "")
        check("외부 공개는 실행하지 않았습니다" in decision["message"], "승인 후 외부 게시 차단")
        use = marketing_os.usage()
        check(use["requests"] == 0 and use["cost_is_estimate"], "DEMO는 유료 사용량에 미포함")
        team = marketing_os.team_dashboard()
        check(len(team["agents"]) == 8 and len(team["schedule"]) == 5, "AI 직원 8명과 작업 시간표 준비")
        check(marketing_os.control("start")["status"] == "RUNNING", "AI 팀 시작")
        job = marketing_os.run_job("market")
        check(job["ok"] and marketing_os.team_dashboard()["activity"], "수동 작업과 활동 기록")
        marketing_os.run_job("report")
        check(bool(marketing_os.team_dashboard()["reports"]), "일일 보고서 생성")
        check(marketing_os.control("pause")["status"] == "PAUSED", "AI 팀 일시정지")
        check(marketing_os.control("stop")["status"] == "EMERGENCY_STOP", "AI 팀 긴급정지")

        class FakeCatalog:
            def load(self):
                return ([{"product_id": "p1", "name": "Sample", "price_won": 1000, "free": False,
                          "confirmed_results": ["항목 A"], "facts_status": "VERIFIED"}],
                        {"source_file": "memory", "source_hash": "one", "synced_at": "now", "warnings": []})

        class FakeProvider:
            name, model, connected = "TEST", "fake", True
            def generate(self, item, platform):
                return {"platform": platform, "product_id": item["product_id"], "title": "Sample",
                        "hook": "확인", "body": "현재 1,000원입니다.", "cta": "확인",
                        "image_prompt": "sample", "factual_claims": ["항목 A"],
                        "source_facts": item["product_id"], "uncertainty": [], "estimated_cost": None}

        generic_policy = BrandPolicy(("SAMPLE",), r"보장", r"혁신적인")
        tenant_a = MarketingService(FakeCatalog(), FakeProvider(), MarketingRepository(marketing_os.DB, "tenant-a"), generic_policy)
        tenant_b = MarketingService(FakeCatalog(), FakeProvider(), MarketingRepository(marketing_os.DB, "tenant-b"), generic_policy)
        tenant_result = tenant_a.trial("p1", "블로그", "DEMO")
        check(len(tenant_a.approvals()) == 1 and not tenant_b.approvals(), "테넌트별 승인 데이터 격리")
        try:
            tenant_b.decide(tenant_result["approval_id"], "approve", "")
            raise AssertionError("다른 테넌트 승인 접근이 허용됨")
        except ValueError:
            print("OK  다른 테넌트 승인 접근 차단")
        class BadVariantProvider(FakeProvider):
            def generate(self, item, platform):
                draft = super().generate(item, platform)
                if platform == "블로그": draft["body"] = "현재 999,999원입니다."
                return draft
        bad_service = MarketingService(FakeCatalog(), BadVariantProvider(), MarketingRepository(marketing_os.DB, "tenant-b"), generic_policy)
        bad_bundle = bad_service.create_bundle("p1", "가격이 궁금합니다")
        check(bad_bundle["items"][1]["status"] == "REVISION_REQUESTED" and bad_bundle["items"][1]["approval_id"] is None, "거짓 가격 채널 초안 승인 차단")
        check(not tenant_a.bundles() and len(tenant_b.bundles()) == 1, "콘텐츠 묶음 테넌트 격리")
        if old_key is not None:
            os.environ["GEMINI_API_KEY"] = old_key
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
