"""Brave Web Search adapter; returns observed snippets, never inferred facts."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx


class BraveResearchProvider:
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, client: httpx.Client | None = None, key: str | None = None):
        self.key = key if key is not None else os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.enabled = os.getenv("MARKETING_EXTERNAL_RESEARCH_ENABLED", "false").lower() == "true"
        self.connected = bool(self.key and self.enabled)
        self.client = client

    def search(self, query: str) -> list[dict]:
        if not self.connected:
            raise PermissionError("외부 검색 키 또는 별도 활성화 설정이 없습니다.")
        query = query.strip()[:180]
        if not query:
            raise ValueError("검색어가 비었습니다.")
        client = self.client or httpx.Client(timeout=8.0)
        try:
            response = client.get(self.endpoint, params={"q": query, "country": "KR", "search_lang": "ko", "count": 5},
                                  headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
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
