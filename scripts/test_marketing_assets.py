"""Offline checks for importing real files from the free creative workflow."""
from __future__ import annotations

import base64
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from modules.marketing_assets import MarketingAssetStore
from modules.marketing_core.repository import MarketingRepository


class MarketingAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="roadlog_assets_")
        self.root = Path(self.temp.name)
        self.repo = MarketingRepository(self.root / "marketing.db", "roadlog")
        conn = self.repo.connect()
        try:
            content_id = conn.execute("INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,fact_snapshot_json,mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("roadlog","today","오늘 운세","인스타그램","오늘 운세","안내","실제 상품 사실","상품 보기","차분한 이미지","PENDING_APPROVAL","PASSED","{}","REAL","2026-09-24")).lastrowid
            conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", ("roadlog",content_id,"PENDING","2026-09-24"))
            conn.commit()
        finally:
            conn.close()
        self.store = MarketingAssetStore(self.repo,self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_brief_and_private_image(self):
        brief = self.store.brief(1)
        self.assertEqual(brief["image_prompt"], "차분한 이미지")
        self.assertEqual(brief["status"], "ASSET_REQUIRED")
        image = Image.new("RGB", (256, 256), "#48527a")
        data = io.BytesIO(); image.save(data, format="JPEG")
        item = self.store.import_base64(1,"image","image/jpeg",base64.b64encode(data.getvalue()).decode())
        self.assertEqual(item["status"], "IMPORTED_UNVERIFIED")
        self.assertEqual(self.store.list_for_approval(1)[0]["id"],item["id"])
        path, mime = self.store.private_file(item["id"])
        self.assertEqual(path.read_bytes(),data.getvalue())
        self.assertEqual(mime,"image/jpeg")

    def test_reject_non_image_and_other_tenant(self):
        with self.assertRaises(ValueError):
            self.store.import_base64(1,"image","image/jpeg",base64.b64encode(b"not an image").decode())
        with self.assertRaises(ValueError):
            self.store.import_base64(99,"video","video/mp4",base64.b64encode(b"\0\0\0\x18ftypisom0000").decode())
        with self.assertRaises(ValueError):
            MarketingAssetStore(MarketingRepository(self.root / "marketing.db","other"),self.root).brief(1)


if __name__ == "__main__":
    unittest.main()
