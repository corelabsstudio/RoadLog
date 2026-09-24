"""Offline endpoint and production-provider diagnostic contract checks."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    os.environ["DATA_DIR"] = temporary
    os.environ["MARKETING_RELEASE_HOLD"] = "false"
    os.environ["MARKETING_EXTERNAL_API_ENABLED"] = "true"
    os.environ["MARKETING_RESEARCH_ENABLED"] = "true"
    os.environ["MARKETING_EXTERNAL_RESEARCH_ENABLED"] = "true"
    os.environ["MARKETING_DIAGNOSTICS_LIVE_ENABLED"] = "true"
    os.environ["TAVILY_API_KEY"] = "offline-test-only"
    os.environ.pop("GEMINI_API_KEY", None)

    from fastapi.testclient import TestClient
    from modules import marketing_diagnostics as diag, marketing_safety
    from modules.marketing_core.repository import MarketingRepository
    from modules.marketing_research import TavilyResearchProvider as RealTavily
    import server

    marketing_safety.DB = Path(temporary) / "audit.db"
    repo = MarketingRepository(Path(temporary) / "research.db", "diagnostic-test")
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"results": [{"title": "오늘 운세 참고", "url": "https://example.org/fortune",
                                                   "content": "오늘 운세 관련 정보"}]})

    transport_client = httpx.Client(transport=httpx.MockTransport(reply), timeout=8)
    def provider() -> RealTavily:
        return RealTavily(client=transport_client, key="offline-test-only")

    catalog = {"products": [{"product_id": "today", "name": "오늘 운세 한 조각", "facts_status": "VERIFIED"}]}
    with patch.object(server, "_marketing_repo", return_value=repo), \
         patch.object(diag, "TavilyResearchProvider", side_effect=provider), \
         patch("modules.marketing_os.products", return_value=catalog):
        client = TestClient(server.app)
        path = "/api/admin/marketing/providers"
        assert client.get(path).status_code == 401
        assert client.post(path + "/tavily/test", json={"live": True, "product_id": "today"}).status_code == 401
        with patch.object(server, "_require_admin", return_value={"email": "admin@example.org", "is_admin": True}):
            state = client.get(path).json()["items"]
            assert len(state) == 6 and all("key" not in row for row in state)
            assert client.post(path + "/tavily/test", json={"live": False, "product_id": "today"}).status_code == 423
            assert client.post(path + "/gemini_text/test", json={"live": True}).status_code == 423
            with patch.dict(os.environ, {"MARKETING_DIAGNOSTICS_LIVE_ENABLED": "false"}):
                assert client.post(path + "/tavily/test", json={"live": True, "product_id": "today"}).status_code == 423
            assert len(calls) == 0 and marketing_safety.audit_count() == 0
            response = client.post(path + "/tavily/test", json={"live": True, "product_id": "today", "query": "오늘 운세"})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["requestCount"] == 1 and body["resultCount"] == 1 and len(calls) == 1
            assert body["actualCalls"] == {"tavily": 1, "gemini": 0, "image": 0, "video": 0, "publishing": 0}
            assert body["results"][0]["url"] == "https://example.org/fortune"
            with repo.connect() as conn:
                row = conn.execute("SELECT id,status,request_count FROM marketing_provider_diagnostics").fetchone()
            assert row["status"] == "LIVE_TEST_PASSED" and row["request_count"] == 1
            saved = repo.research_sources(-row["id"])
            assert saved[0]["origin"] == "PROVIDER_DIAGNOSTIC" and saved[0]["source_type"] == "EXTERNAL_SOURCE"
            assert saved[0]["query_text"] == "오늘 운세" and saved[0]["observed_at"]
            assert marketing_safety.diagnostic_audit_count(row["id"]) == 1
            assert client.post(path + "/tavily/test", json={"live": True, "product_id": "today"}).status_code == 423
            assert len(calls) == 1
            assert client.get(path).json()["items"][1]["lastTestStatus"] == "LIVE_TEST_PASSED"
    with sqlite3.connect(marketing_safety.DB) as conn:
        assert conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE provider!='research'").fetchone()[0] == 0
    transport_client.close()
print("marketing diagnostics offline checks passed")
