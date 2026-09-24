"""Admin-only provider diagnostics; only Tavily has an executable live test."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from modules import marketing_safety
from modules.marketing_attribution import account_key
from modules.marketing_core.repository import MarketingRepository
from modules.marketing_instagram import configured as instagram_configured
from modules.marketing_research import TavilyResearchProvider

PROVIDERS = (
    ("gemini_text", "Gemini Text"), ("tavily", "Tavily Search"),
    ("gemini_image", "Gemini Image"), ("video", "Video Provider"),
    ("blog", "Blog Publisher"), ("sns", "SNS Publisher"),
)


def provider_status(repo: MarketingRepository, web_root: Path) -> list[dict]:
    tavily = TavilyResearchProvider()
    blog_ready = (web_root / "blog" / "first-time-saju.html").is_file() and (web_root / "blog" / "index.html").is_file()
    configured = {
        "gemini_text": bool(os.getenv("GEMINI_API_KEY")), "tavily": bool(tavily.key),
        "gemini_image": bool(os.getenv("GEMINI_API_KEY")), "video": False,
        "blog": blog_ready, "sns": instagram_configured(),
    }
    enabled = {
        "gemini_text": marketing_safety.enabled("gemini"),
        "tavily": marketing_safety.enabled("research") and marketing_safety.on("MARKETING_EXTERNAL_RESEARCH_ENABLED"),
        "gemini_image": marketing_safety.enabled("image") and marketing_safety.on("MARKETING_IMAGE_GENERATION_ENABLED"),
        "video": marketing_safety.enabled("video"), "blog": blog_ready,
        "sns": marketing_safety.enabled("sns"),
    }
    live_enabled = marketing_safety.on("MARKETING_DIAGNOSTICS_LIVE_ENABLED")
    rows = []
    for key, label in PROVIDERS:
        last = repo.provider_diagnostic(key)
        rows.append({"provider": key, "label": label, "configured": configured[key], "enabled": enabled[key],
                     "liveTestAllowed": key == "tavily" and live_enabled and configured[key] and enabled[key],
                     "lastTestAt": last["tested_at"] if last else None,
                     "lastTestStatus": last["status"] if last else None,
                     "lastErrorKind": last["error_kind"] if last else None,
                     "diagnosticsLiveEnabled": live_enabled if key == "tavily" else False})
    return rows


def test_tavily(repo: MarketingRepository, web_root: Path, administrator_email: str,
                product_id: str, query: str, *, live: bool) -> dict:
    if not live:
        raise PermissionError("live=true가 있어야 실제 검색 1회를 실행합니다.")
    status = next(row for row in provider_status(repo, web_root) if row["provider"] == "tavily")
    if not status["liveTestAllowed"]:
        raise PermissionError("Tavily 키·검색·진단 호출 설정을 모두 확인해 주세요.")
    from modules.marketing_os import products
    catalog = products(web_root)["products"]
    product = next((item for item in catalog if item["product_id"] == product_id and item["facts_status"] == "VERIFIED"), None)
    if not product:
        raise ValueError("확인된 ROADLOG 상품을 선택해 주세요.")
    provider = TavilyResearchProvider()
    selected_query = query.strip()[:180] if query.strip() else provider.question_query(product)
    if not selected_query:
        raise ValueError("검색어가 비었습니다.")
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    diagnostic_id = repo.claim_provider_diagnostic("tavily", now.date().isoformat(),
                                                    account_key(administrator_email)[:16], selected_query,
                                                    now.isoformat(timespec="seconds"))
    if diagnostic_id is None:
        raise PermissionError("오늘 Tavily 진단을 이미 시도했습니다. 중복 호출을 막았습니다.")
    try:
        results = provider.search(selected_query, max_results=5, campaign_id=-diagnostic_id,
                                  audit_operation="diagnostic:tavily_search",
                                  audit_agent_id="diagnostic:" + account_key(administrator_email)[:16])
        count = marketing_safety.diagnostic_audit_count(diagnostic_id)
        if count != 1:
            raise RuntimeError("Tavily 호출 감사 기록을 확인하지 못했습니다.")
        repo.save_research_sources(-diagnostic_id, results, origin="PROVIDER_DIAGNOSTIC")
        stored = repo.research_sources(-diagnostic_id)
        if not stored or len(stored) != len(results) or any(
            item["source_type"] != "EXTERNAL_SOURCE" or item["origin"] != "PROVIDER_DIAGNOSTIC"
            or item["query_text"] != selected_query or item["url"] != original["url"]
            or item["title"] != original["title"] or item["observed_at"] != original["observedAt"]
            for item, original in zip(stored, results)
        ):
            raise RuntimeError("외부 조사 결과 저장·재조회를 확인하지 못했습니다.")
        repo.finish_provider_diagnostic(diagnostic_id, "LIVE_TEST_PASSED", count)
        return {"provider": "tavily", "testedAt": now.isoformat(timespec="seconds"), "query": selected_query,
                "resultCount": len(stored), "requestCount": count,
                "actualCalls": {"tavily": count, "gemini": 0, "image": 0, "video": 0, "publishing": 0},
                "results": [{"title": item["title"], "url": item["url"], "snippet": item["summary"],
                             "source": item["provider"], "observedAt": item["observed_at"],
                             "sourceType": item["source_type"], "origin": item["origin"]} for item in stored]}
    except Exception as exc:
        count = marketing_safety.diagnostic_audit_count(diagnostic_id)
        repo.finish_provider_diagnostic(diagnostic_id, "LIVE_TEST_FAILED", count, type(exc).__name__)
        raise RuntimeError("Tavily 진단 실패: " + type(exc).__name__ + ". 자동 재시도는 하지 않았습니다.") from None
