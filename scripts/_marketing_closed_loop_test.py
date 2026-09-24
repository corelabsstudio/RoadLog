"""No network or billed provider calls."""
from __future__ import annotations
import json
import gc
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.marketing_core.repository import MarketingRepository


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        repo = MarketingRepository(Path(folder) / "marketing.db", "roadlog")
        product = {"product_id":"today","name":"오늘 운세", "facts_status":"VERIFIED", "confirmed_results":["오늘의 흐름"]}
        meta = {"source_file":"catalog.json", "source_hash":"test"}
        draft = {"platform":"블로그","title":"오늘의 흐름","hook":"읽어보세요","body":"실제 상품 설명", "cta":"상품 보기","image_prompt":""}
        stamp = "2026-09-24T10:00:00+09:00"
        campaign = repo.begin_campaign("today","MANUAL",stamp)
        content, approval = repo.save_trial(product,meta,draft,[],stamp,defer_approval=True)
        assert approval is None
        with repo.connect() as conn:
            assert conn.execute("SELECT workflow_state FROM marketing_content WHERE id=?",(content,)).fetchone()[0] == "REVIEWING"
        conn.close()
        assert repo.finalize_agent_review(content,True,stamp)
        assert repo.approvals() == []
        prepared = repo.prepare_publication(campaign,content,stamp)
        assert prepared["status"] == "READY_TO_PUBLISH" and f"rl_campaign_id={campaign}" in prepared["tracking_url"]
        assert len(repo.approvals()) == 1
        assert repo.prepare_publication(campaign,content,stamp)["id"] == prepared["id"]
        assert len(repo.approvals()) == 1
        repo.record_revision(campaign,content,None,0,"초안","PASS",stamp)
        assert repo.recent_campaigns()[0]["revisions"][0]["outcome"] == "PASS"
        score = repo.save_scorecard(campaign,{},stamp)
        assert score["visits"] == 0 and score["signups"] == 0 and score["revenue_krw"] == 0
        image_draft = {**draft,"platform":"인스타그램"}
        image_content, _ = repo.save_trial(product,meta,image_draft,[],stamp,defer_approval=True)
        assert repo.finalize_agent_review(image_content,True,stamp)
        blocked = repo.prepare_publication(campaign,image_content,stamp)
        assert blocked["status"] == "BLOCKED_ASSET_REQUIRED" and len(repo.approvals()) == 1
        failed, _ = repo.save_trial(product,meta,draft,["거짓 가격"],stamp,defer_approval=True)
        assert not repo.finalize_agent_review(failed,True,stamp)
        try:
            repo.prepare_publication(campaign,failed,stamp)
            raise AssertionError("failed review became ready")
        except ValueError:
            pass
        print("OK: final gate, idempotency, asset block, review block, tracking, measured-only scorecard")
        gc.collect()  # sqlite3's context manager commits but does not close its connection on Windows.


if __name__ == "__main__": main()
