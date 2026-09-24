"""Offline evidence/strategy regression. No Gemini, search, or publishing calls."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.marketing_core.repository import MarketingRepository
from modules.marketing_research import TavilyResearchProvider
from modules.marketing_strategy import build_strategy
from modules import marketing_safety


def main() -> None:
    # This process uses MockTransport only; production defaults stay OFF.
    os.environ["MARKETING_EXTERNAL_API_ENABLED"] = "true"
    os.environ["MARKETING_RESEARCH_ENABLED"] = "true"
    os.environ["MARKETING_EXTERNAL_RESEARCH_ENABLED"] = "true"
    marketing_safety.DB = Path(tempfile.mkdtemp()) / "audit.db"
    marketing_safety.RELEASE_HOLD = False  # MockTransport only
    calls = []

    def answer(request):
        calls.append(request)
        assert request.url.host == "api.tavily.com"
        assert '"search_depth":"basic"' in request.content.decode()
        return httpx.Response(200, json={"results": [
            {"title": "사주 결과에 무엇이 나오나요?", "url": "https://example.org/question", "content": "공개된 질문"},
            {"title": "악성 주소", "url": "javascript:alert(1)", "content": "버림"}]})

    repo = MarketingRepository(Path(tempfile.mkdtemp()) / "marketing.db", "test")
    provider = TavilyResearchProvider(httpx.Client(transport=httpx.MockTransport(answer)), key="test-key")
    provider.connected = True
    first = repo.search_with_budget("사주 결과 질문", provider, daily_limit=1)
    second = repo.search_with_budget("사주 결과 질문", provider, daily_limit=1)
    assert len(calls) == 1 and first == second and len(first) == 1
    assert first[0]["sourceType"] == "EXTERNAL_SOURCE" and first[0]["url"] == "https://example.org/question"
    try:
        repo.search_with_budget("다른 질문", provider, daily_limit=1)
        raise AssertionError("daily limit bypassed")
    except PermissionError:
        pass
    product = {"product_id": "today", "name": "오늘 운세 한 조각"}
    profile = {"observed_at": "2026-09-24T00:00:00+00:00", "source": "roadlog.stats.overview",
               "products": [{"product_id": "today", "opens_all_time": 3}]}
    tools = {"contentGeneration": {"status": "WORKING"}, "blogPublishing": {"status": "WORKING"},
             "imageGeneration": {"status": "PAUSED_APPROVAL"}, "videoGeneration": {"status": "CONFIG_REQUIRED"}}
    past = [{"id": 7, "product_id": "today", "scorecard": {"visits": 4, "signups": 1, "purchases": 0, "observed_at": "2026-09-23"}}]
    strategy = build_strategy(profile, product, first, past, [], tools)
    assert strategy["externalResearchAvailable"] and strategy["selectedStrategy"] == "SEO_CONTENT"
    assert {e["type"] for e in strategy["evidence"]} == {"MEASURED", "EXTERNAL_SOURCE", "PAST_CAMPAIGN", "AI_INFERENCE"}
    assert all(not c["executable"] for c in strategy["candidates"] if c["strategy"] in {"SOCIAL_IMAGE", "SHORT_FORM"})
    assert strategy["observedQuestions"] and not strategy["inferredQuestions"]
    repo.save_strategy(1, strategy)
    assert repo.strategy(1)["selectedStrategy"] == "SEO_CONTENT"
    offline = build_strategy(profile, product, [], [], [], tools)
    assert offline["selectedStrategy"] == "SEO_CONTENT" and not offline["externalResearchAvailable"]
    duplicate = build_strategy(profile, product, first, [], ["오늘 운세 한 조각 안내"], tools)
    assert duplicate["selectedStrategy"] is None and duplicate["contentGap"]["status"] == "UPDATE_OPPORTUNITY"
    assert not TavilyResearchProvider(key="").connected
    print("PASS: Tavily mock, URL filtering, cache, daily cap, four evidence types, offline fallback, content gap, unavailable media block")


if __name__ == "__main__":
    main()
