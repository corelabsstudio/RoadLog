"""Search adapters; production uses opt-in Tavily, legacy Brave stays for tests."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from modules import marketing_safety


class BraveResearchProvider:
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, client: httpx.Client | None = None, key: str | None = None):
        self.key = key if key is not None else os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.enabled = os.getenv("MARKETING_EXTERNAL_RESEARCH_ENABLED", "false").lower() == "true"
        self.connected = bool(self.key and self.enabled and marketing_safety.enabled("research") and marketing_safety.cost_settings()["paid_enabled"])
        self.client = client

    def search(self, query: str) -> list[dict]:
        if not self.connected:
            raise PermissionError("외부 검색 키 또는 별도 활성화 설정이 없습니다.")
        if not marketing_safety.enabled("research"):
            raise PermissionError("마케팅 외부 검색이 비활성화되어 있습니다.")
        query = query.strip()[:180]
        if not query:
            raise ValueError("검색어가 비었습니다.")
        client = self.client or httpx.Client(timeout=8.0)
        try:
            audit_id = marketing_safety.before_call("research", "brave_search")
            response = client.get(self.endpoint, params={"q": query, "country": "KR", "search_lang": "ko", "count": 5},
                                  headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
            marketing_safety.after_call(audit_id, "HTTP_" + str(response.status_code))
            response.raise_for_status()
            results = response.json().get("web", {}).get("results", [])
        finally:
            if self.client is None:
                client.close()
        observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        safe = []
        for item in results[:5]:
            url = str(item.get("url") or "")
            if urlparse(url).scheme not in {"https", "http"}:
                continue
            safe.append({"title": str(item.get("title") or "")[:200], "url": url[:1000],
                         "observedAt": observed_at, "summary": str(item.get("description") or "")[:500],
                         "sourceType": "EXTERNAL_SOURCE", "query": query, "source": "Brave Web Search"})
        return safe


class TavilyResearchProvider:
    """Opt-in search. Basic queries only; no raw page extraction or AI answers."""
    endpoint = "https://api.tavily.com/search"

    def __init__(self, client: httpx.Client | None = None, key: str | None = None):
        self.key = key if key is not None else os.getenv("TAVILY_API_KEY", "")
        self.enabled = os.getenv("MARKETING_EXTERNAL_RESEARCH_ENABLED", "false").lower() == "true"
        self.connected = bool(self.key and self.enabled and marketing_safety.enabled("research"))
        self.client = client

    def search(self, query: str, max_results: int = 5, campaign_id: int = 0, *,
               audit_operation: str = "tavily_search", audit_agent_id: str = "market_researcher") -> list[dict]:
        if not self.connected:
            raise PermissionError("외부 검색 키 또는 활성화 설정이 없습니다.")
        if not marketing_safety.enabled("research"):
            raise PermissionError("마케팅 외부 검색이 비활성화되어 있습니다.")
        query = query.strip()[:180]
        if not query:
            raise ValueError("검색어가 비었습니다.")
        client = self.client or httpx.Client(timeout=8.0)
        audit_id = None
        try:
            audit_id = marketing_safety.before_call("research", audit_operation, campaign_id=campaign_id, agent_id=audit_agent_id)
            response = client.post(self.endpoint, headers={"Authorization": f"Bearer {self.key}"},
                                   json={"query": query, "search_depth": "basic", "max_results": max(1, min(max_results, 5)),
                                         "country": "south korea", "language": "ko", "include_answer": False,
                                         "include_raw_content": False, "include_images": False})
            marketing_safety.after_call(audit_id, "HTTP_" + str(response.status_code))
            response.raise_for_status()
            results = response.json().get("results", [])
            if not isinstance(results, list):
                raise ValueError("검색 결과 형식 오류")
            marketing_safety.after_call(audit_id, "SUCCESS", actual_cost_estimate_krw=16)
        except (httpx.TimeoutException, httpx.TransportError):
            if audit_id is not None:
                marketing_safety.after_call(audit_id, "TRANSPORT_ERROR")
            raise
        except (ValueError, TypeError):
            if audit_id is not None:
                marketing_safety.after_call(audit_id, "USAGE_INVALID")
                marketing_safety.trip_kill("검색 응답 형식 오류")
            raise
        finally:
            if self.client is None:
                client.close()
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        safe = []
        for item in results[:max(1, min(max_results, 5))]:
            url = str(item.get("url") or "")
            if urlparse(url).scheme not in {"http", "https"} or not urlparse(url).netloc:
                continue
            safe.append({"query": query, "title": str(item.get("title") or "")[:200], "url": url[:1000],
                         "summary": str(item.get("content") or "")[:500], "observedAt": stamp,
                         "sourceType": "EXTERNAL_SOURCE", "source": "Tavily Search"})
        return safe

    def question_query(self, product: dict) -> str:
        return f"{product['name']} 사주 결과 궁금한 점"

    def competitor_query(self, product: dict) -> str:
        return f"{product['name']} 비슷한 사주 서비스 비교"

    def topic_query(self, topic: str) -> str:
        return topic.strip()[:180]
