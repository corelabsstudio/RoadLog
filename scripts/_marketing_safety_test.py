"""Offline safety regression. Every network client here must be a mock."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import marketing_safety, marketing_os
from modules.marketing_gemini import RoadLogGeminiProvider
from modules.marketing_research import TavilyResearchProvider
from modules.marketing_creative import GeminiImageProvider
from modules.marketing_core.repository import MarketingRepository


def main() -> None:
    keys = ["MARKETING_EXTERNAL_API_ENABLED", *marketing_safety.FLAGS.values(),
            "MARKETING_AUTO_TEAM_ENABLED", "MARKETING_AUTO_PUBLISH_ENABLED",
            "MARKETING_EXTERNAL_RESEARCH_ENABLED", "MARKETING_IMAGE_GENERATION_ENABLED", "GEMINI_API_KEY", "TAVILY_API_KEY"]
    previous = {key:os.environ.get(key) for key in keys}
    original_db, original_os_db, original_hold = marketing_safety.DB, marketing_os.DB, marketing_safety.RELEASE_HOLD
    try:
        for key in keys: os.environ.pop(key, None)
        db = Path(tempfile.mkdtemp()) / "safety.db"
        marketing_safety.DB = marketing_os.DB = db
        assert not marketing_safety.board()["external_api_enabled"]
        assert not any(item["enabled"] for item in marketing_safety.board()["providers"].values())
        assert not RoadLogGeminiProvider().connected
        assert not TavilyResearchProvider(key="present").connected
        assert not GeminiImageProvider(key="present", enabled=True).connected
        try: marketing_safety.before_call("gemini", "test")
        except PermissionError: pass
        else: raise AssertionError("default-off bypassed")
        assert marketing_safety.audit_count() == 0
        os.environ["MARKETING_EXTERNAL_API_ENABLED"] = "true"
        os.environ["MARKETING_GEMINI_ENABLED"] = "true"
        assert not marketing_safety.enabled("gemini"), "release hold must override even enabled Railway variables"
        os.environ["MARKETING_EXTERNAL_API_ENABLED"] = "false"
        marketing_safety.RELEASE_HOLD = False  # only in this isolated MockTransport test process

        web = Path(__file__).resolve().parents[1] / "web"
        product = next(p for p in marketing_os.products(web)["products"] if p["facts_status"] == "VERIFIED")
        before = marketing_safety.audit_count()
        result = marketing_os.test_campaign(web, product["product_id"])
        assert result["mode"] == "TEST" and result["ready_to_publish"] == "EXPECTED_ONLY_NOT_CREATED"
        assert sum(result["actual_calls"].values()) == 0 and marketing_safety.audit_count() == before
        repo = MarketingRepository(db, "roadlog")
        campaign = repo.recent_campaigns()[0]
        assert campaign["mode"] == "TEST" and len(campaign["events"]) == 7 and not campaign["publications"]
        assert not repo.recent_campaign_product_ids("2000-01-01")
        for operation in (lambda: repo.save_scorecard(result["campaign_id"], {}, "2026-09-24"),
                          lambda: repo.prepare_publication(result["campaign_id"], 999, "2026-09-24")):
            try: operation()
            except PermissionError: pass
            else: raise AssertionError("TEST/production isolation bypassed")
        try: marketing_os.test_campaign(web, product["product_id"], use_search=True)
        except PermissionError: pass
        else: raise AssertionError("disabled checkbox accepted")

        os.environ["MARKETING_EXTERNAL_API_ENABLED"] = "true"
        os.environ["MARKETING_GEMINI_ENABLED"] = "true"
        os.environ["MARKETING_RESEARCH_ENABLED"] = "true"
        os.environ["MARKETING_EXTERNAL_RESEARCH_ENABLED"] = "true"
        hits = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (hits.append(request), httpx.Response(200,json={"results":[]}))[1]))
        provider = TavilyResearchProvider(client=client, key="test")
        for _ in range(5): provider.search("사주")
        assert len(hits) == 5
        try: provider.search("사주")
        except PermissionError: pass
        else: raise AssertionError("research cap bypassed")
        os.environ["MARKETING_EXTERNAL_API_ENABLED"] = "false"
        try: provider.search("사주")
        except PermissionError: pass
        else: raise AssertionError("global switch did not override provider")
        assert len(hits) == 5 and marketing_safety.audit_count() == 5
        print("PASS: default-off, provider override, TEST isolation, zero DRY RUN calls, 5-call hard cap")
    finally:
        marketing_safety.DB, marketing_os.DB, marketing_safety.RELEASE_HOLD = original_db, original_os_db, original_hold
        for key, value in previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value


if __name__ == "__main__": main()
