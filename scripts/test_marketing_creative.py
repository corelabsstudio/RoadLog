"""Offline provider tests; no paid call or account access."""
from __future__ import annotations

import base64
import io
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.marketing_assets import MarketingAssetStore
from modules.marketing_core.repository import MarketingRepository
from modules.marketing_creative import GeminiImageProvider
from modules.marketing_tools import tool_registry


class CreativeTests(unittest.TestCase):
    def setUp(self):
        self.png = io.BytesIO()
        Image.new("RGB", (512, 512), "#727590").save(self.png, format="PNG")

    def test_disabled_is_not_a_call(self):
        provider = GeminiImageProvider(key="test-key", enabled=False)
        self.assertFalse(provider.connected)
        with self.assertRaises(PermissionError):
            provider.generate_image({"product_id": "today", "image_prompt": "차분한 밤"})

    def test_registry_does_not_call_unconnected_tools_connected(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "BRAVE_SEARCH_API_KEY": "", "MARKETING_IMAGE_GENERATION_ENABLED": "false", "MARKETING_EXTERNAL_RESEARCH_ENABLED": "false"}):
            tools = tool_registry()
        self.assertEqual(tools["imageGeneration"]["status"], "CONFIG_REQUIRED")
        self.assertEqual(tools["videoGeneration"]["status"], "CONFIG_REQUIRED")
        self.assertEqual(tools["research"]["status"], "CONFIG_REQUIRED")

    def test_provider_returns_real_bytes_and_private_store(self):
        def respond(request):
            self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(self.png.getvalue()).decode()}}]}}]})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            provider = GeminiImageProvider(client, key="test-key", enabled=True)
            result = provider.generate_image({"product_id": "today", "image_prompt": "차분한 밤"})
        self.assertEqual(result["data"], self.png.getvalue())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = MarketingRepository(root / "marketing.db", "roadlog")
            conn = repo.connect()
            try:
                content_id = conn.execute("INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,fact_snapshot_json,mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("roadlog","today","오늘 운세","인스타그램","제목","도입","본문","링크","차분한 밤","AWAITING_AI_REVIEW","PENDING","{}","REAL","2026-09-24")).lastrowid
                conn.commit()
            finally:
                conn.close()
            store = MarketingAssetStore(repo, root)
            asset = store.save_generated_image(content_id, result["mime"], result["data"], result["provider"])
            self.assertEqual(asset["status"], "GENERATED_UNVERIFIED")
            self.assertEqual(store.private_file(asset["id"])[0].read_bytes(), self.png.getvalue())

    def test_missing_image_is_failure(self):
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "done"}]}}]}))) as client:
            with self.assertRaisesRegex(ValueError, "실제 이미지 파일"):
                GeminiImageProvider(client, key="test-key", enabled=True).generate_image({"product_id": "today", "image_prompt": "차분한 밤"})


if __name__ == "__main__":
    unittest.main()
