"""Local-only full funnel. Fake signup/payment/AI; no external calls or public posts."""
from __future__ import annotations

import gc
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="roadlog-mkt-e2e-") as folder:
        os.environ["DATA_DIR"] = folder
        os.environ["APP_ENV"] = "development"
        os.environ["APP_SECRET"] = "test-only-long-secret-not-for-production-1234"
        os.environ.pop("GEMINI_API_KEY",None)
        import server
        from modules.marketing_core.repository import MarketingRepository
        from modules import marketing_attribution as attribution

        repo = server._marketing_repo()
        stamp = attribution.stamp()
        product = {"product_id":"today","name":"오늘 운세","facts_status":"VERIFIED","confirmed_results":["오늘의 흐름"]}
        meta = {"source_file":"test-catalog.json","source_hash":"test"}
        draft = {"platform":"블로그","title":"오늘의 흐름","hook":"실제 검수된 설명","body":"검증된 상품 설명","cta":"상품 살펴보기","image_prompt":""}
        campaign_a = repo.begin_campaign("today","MANUAL",stamp)
        repo.save_strategy(campaign_a,{"selectedStrategy":"SEO_CONTENT","objective":"오늘의 흐름 설명"})
        content, approval = repo.save_trial(product,meta,draft,[],stamp,defer_approval=True)
        assert approval is None
        assert repo.finalize_agent_review(content,True,stamp)
        pub = repo.prepare_publication(campaign_a,content,stamp)
        approval = repo.approvals()[0]["id"]
        assert pub["status"] == "READY_TO_PUBLISH"
        with patch.object(server,"_require_admin",return_value={"email":"admin@example.test"}), patch.object(server.db,"register_user",return_value=(True,"가입됨")), patch.object(server.lamps_ops,"welcome",return_value={"given":0}), patch.object(server,"_welcome_inbox",return_value=None), patch.object(server,"_token_user",return_value={"email":"buyer@example.test"}), patch.object(server,"_verify_payment",return_value={"amount":{"total":1000}}), patch.object(server.lamps_ops,"pack_for_amount",return_value=20), patch.object(server.lamps_ops,"charge",return_value={"ok":True}):
            client = TestClient(server.app,base_url="https://roadlog.co.kr")
            response = client.post(f"/api/admin/marketing/approvals/{approval}/approve",json={"note":"로컬 시험 승인"})
            assert response.status_code == 200, response.text
            published = response.json()
            assert published["status"] == "PUBLISHED"
            page = client.get(urlparse(published["published_url"]).path)
            assert page.status_code == 200 and "오늘의 흐름" in page.text and pub["tracking_url"] .replace("&","&amp;") in page.text
            assert client.get("/blog/").status_code == 200
            assert repo.blog_post(f"ai-{pub['id']}")
            repeat = client.post(f"/api/admin/marketing/approvals/{approval}/approve",json={"note":"중복"})
            assert repeat.status_code == 400
            tracked = client.get(pub["tracking_url"],headers={"user-agent":"Mozilla/5.0 TestBrowser"})
            assert tracked.status_code == 200 and attribution.COOKIE in client.cookies
            signed = client.post("/api/auth/register",json={"email":"buyer@example.test","password":"test-password-123","name":"테스트"})
            assert signed.status_code == 200, signed.text
            paid = client.post("/api/lamps/charge",json={"paymentId":"fake-payment-1"})
            assert paid.status_code == 200, paid.text
            score = repo.save_scorecard(campaign_a,{},attribution.stamp())
            assert score["visits"] == 1 and score["unique_visitors"] == 1 and score["signups"] == 1 and score["purchases"] == 1 and score["revenue_krw"] == 1000, score
            dashboard = client.get("/api/admin/marketing/team")
            assert dashboard.status_code == 200, dashboard.text
            campaign_on_screen = next(c for c in dashboard.json()["campaigns"] if c["id"] == campaign_a)
            assert campaign_on_screen["publications"][0]["published_url"] == published["published_url"]
            assert campaign_on_screen["scorecard"]["signups"] == 1 and campaign_on_screen["scorecard"]["revenue_krw"] == 1000
            assert client.post("/api/lamps/charge",json={"paymentId":"fake-payment-1"}).status_code == 200
            assert repo.save_scorecard(campaign_a,{},attribution.stamp())["purchases"] == 1
            repo.learn_from_scorecard(campaign_a,attribution.stamp())
            learning = repo.recent_learning()[0]
            assert learning["campaign_id"] == campaign_a and learning["measured"]["revenue_krw"] == 1000
            campaign_b = repo.begin_campaign("today","MANUAL",attribution.stamp())
            assert any(item["campaign_id"] == campaign_a for item in repo.recent_learning())
            assert any(item["id"] == campaign_a and item["scorecard"]["purchases"] == 1 for item in repo.recent_campaigns() if item["id"] != campaign_b)
            from modules.marketing_core.agents import TASKS
            director_input = {}
            def fake_director(_self, _task, _product, **kwargs):
                director_input.update(kwargs["metrics"])
                return {"summary":"다른 문안 검토","recommendations":[],"source_facts":[],"unknowns":[],"review_passed":False,"decision":"CREATE","reasonForRetry":"이전 문안과 다른 고객 질문을 사용합니다."}
            with patch.object(server.marketing_ops,"_team_running",return_value=True), patch.object(server.marketing_ops.RoadLogGeminiProvider,"generate_role",fake_director), patch.object(server.marketing_ops,"performance_snapshot",return_value={"source":"test metrics"}), patch.object(server.marketing_ops,"operations") as fake_ops:
                role,state,_ = server.marketing_ops._run_role(TASKS[0],product,{"synced_at":stamp,"source_file":"test-catalog.json"},campaign_id=campaign_b)
                assert role == "marketing_director" and state
                assert fake_ops.return_value.record_agent_output.called
            assert any(c["id"] == campaign_a and c["scorecard"]["purchases"] == 1 for c in director_input["previous_campaigns"])
            assert any(c["id"] == campaign_a and c["strategy"]["selectedStrategy"] == "SEO_CONTENT" and c["publications"][0]["published_url"] == published["published_url"] for c in director_input["previous_campaigns"])
            assert any(item["campaign_id"] == campaign_a and item["measured"]["revenue_krw"] == 1000 for item in director_input["previous_learning"])
            repo.refund_attributed_purchase(attribution.payment_key("fake-payment-1"),attribution.stamp())
            refunded = repo.save_scorecard(campaign_a,{},attribution.stamp())
            assert refunded["purchases"] == 0 and refunded["revenue_krw"] == 0
            assert not attribution.tracked_visit(repo,attribution.new_visitor(),{"rl_campaign_id":"999","rl_publication_id":"999","utm_source":"forged"},"/",attribution.stamp())
            assert not attribution.attributed_signup(repo,"unrelated@example.test","invalid-cookie",attribution.stamp())
            campaign_c = repo.begin_campaign("today","MANUAL",attribution.stamp())
            failed_content,_ = repo.save_trial(product,meta,draft,[],attribution.stamp(),defer_approval=True)
            assert repo.finalize_agent_review(failed_content,True,attribution.stamp())
            repo.prepare_publication(campaign_c,failed_content,attribution.stamp())
            failed_approval = repo.approvals()[0]["id"]
            repo.decide(failed_approval,"APPROVED","로컬 실패 경로",attribution.stamp())
            from modules.marketing_blog import BlogPublisher
            try:
                BlogPublisher(repo,Path(folder) / "missing-web","https://roadlog.co.kr").publish(failed_approval)
                raise AssertionError("missing template was published")
            except FileNotFoundError:
                pass
            assert repo.approval_publication(failed_approval)["status"] == "PUBLISH_FAILED"
            print("OK: local approval -> public route -> tracking -> signup -> fake paid event -> scorecard -> learning -> next context")
            client.close()
        gc.collect()


if __name__ == "__main__":
    main()
