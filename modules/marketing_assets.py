"""Private, human-supplied assets made with free web/local production tools."""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


LIMITS = {"image": 8 * 1024 * 1024, "video": 16 * 1024 * 1024}
MIME = {"image/jpeg": ".jpg", "image/png": ".png", "video/mp4": ".mp4"}


def validate_asset(kind: str, mime: str, data: bytes) -> None:
    if kind not in LIMITS or not data or len(data) > LIMITS[kind]:
        raise ValueError("파일 종류 또는 크기가 허용 범위를 벗어났습니다.")
    if mime not in MIME or (kind == "image") != mime.startswith("image/"):
        raise ValueError("JPEG·PNG 이미지 또는 MP4 영상만 받습니다.")
    if kind == "image":
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                if image.format != ("JPEG" if mime == "image/jpeg" else "PNG") or image.width < 256 or image.height < 256 or image.width * image.height > 20_000_000:
                    raise ValueError("이미지 형식·크기를 확인해 주세요.")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError("이미지 파일을 읽을 수 없습니다.") from exc
    elif len(data) < 16 or data[4:8] != b"ftyp":
        raise ValueError("MP4 파일 헤더를 확인할 수 없습니다.")


class MarketingAssetStore:
    def __init__(self, repository: Any, data_dir: Path):
        self.repository = repository
        self.root = Path(data_dir) / "marketing_assets"

    @contextmanager
    def _connection(self):
        conn = self.repository.connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _approval_content(self, conn: sqlite3.Connection, approval_id: int) -> int:
        row = conn.execute("SELECT a.content_id FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id WHERE a.tenant_id=? AND a.id=? AND c.mode='REAL' AND c.status='PENDING_APPROVAL' AND a.status IN ('PENDING','APPROVED')", (self.repository.tenant_id, approval_id)).fetchone()
        if not row:
            raise ValueError("검수 통과한 승인 항목이 아닙니다.")
        return int(row["content_id"])

    def brief(self, approval_id: int) -> dict[str, Any]:
        with self._connection() as conn:
            self._approval_content(conn, approval_id)
            row = conn.execute("SELECT c.product_id,c.product_name,c.platform,c.title,c.hook,c.body,c.cta,c.image_prompt FROM marketing_content c JOIN marketing_approvals a ON a.content_id=c.id AND a.tenant_id=c.tenant_id WHERE a.tenant_id=? AND a.id=?", (self.repository.tenant_id, approval_id)).fetchone()
        return {**dict(row), "approval_id": approval_id, "image_method": "Gemini 웹앱에서 생성 후 파일 가져오기", "video_method": "로컬 FFmpeg/Clipchamp; 말하는 얼굴은 SadTalker 선택", "status": "ASSET_REQUIRED", "note": "지시안은 이미지·영상 파일이 아닙니다. 업로드 후에도 자동 게시되지 않습니다."}

    def import_base64(self, approval_id: int, kind: str, mime: str, encoded: str) -> dict[str, Any]:
        if len(encoded) > (LIMITS.get(kind, 0) * 4 // 3 + 64):
            raise ValueError("파일 크기가 제한을 넘었습니다.")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("파일 인코딩을 읽을 수 없습니다.") from exc
        validate_asset(kind, mime, data)
        with self._connection() as conn:
            content_id = self._approval_content(conn, approval_id)
        self.root.mkdir(parents=True, exist_ok=True)
        filename = uuid.uuid4().hex + MIME[mime]
        path = self.root / filename
        with path.open("xb") as file:
            file.write(data)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with self._connection() as conn:
                asset_id = int(conn.execute("INSERT INTO marketing_assets(tenant_id,content_id,kind,mime,filename,bytes,sha256,origin,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (self.repository.tenant_id, content_id, kind, mime, filename, len(data), hashlib.sha256(data).hexdigest(), "USER_SUPPLIED_FREE_TOOL", "IMPORTED_UNVERIFIED", stamp)).lastrowid)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {"id": asset_id, "kind": kind, "mime": mime, "bytes": len(data), "origin": "USER_SUPPLIED_FREE_TOOL", "status": "IMPORTED_UNVERIFIED", "created_at": stamp}

    def save_generated_image(self, content_id: int, mime: str, data: bytes, provider: str) -> dict[str, Any]:
        """Persist only genuine provider bytes, never a prompt or placeholder."""
        validate_asset("image", mime, data)
        with self._connection() as conn:
            row = conn.execute("SELECT id FROM marketing_content WHERE tenant_id=? AND id=? AND mode='REAL'", (self.repository.tenant_id, content_id)).fetchone()
            if not row:
                raise ValueError("실제 콘텐츠를 찾지 못했습니다.")
        self.root.mkdir(parents=True, exist_ok=True)
        filename = uuid.uuid4().hex + MIME[mime]
        path = self.root / filename
        with path.open("xb") as file:
            file.write(data)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with self._connection() as conn:
                asset_id = int(conn.execute("INSERT INTO marketing_assets(tenant_id,content_id,kind,mime,filename,bytes,sha256,origin,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (self.repository.tenant_id, content_id, "image", mime, filename, len(data), hashlib.sha256(data).hexdigest(), provider[:80], "GENERATED_UNVERIFIED", stamp)).lastrowid)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {"id": asset_id, "kind": "image", "mime": mime, "bytes": len(data), "origin": provider[:80], "status": "GENERATED_UNVERIFIED", "created_at": stamp}

    def list_for_approval(self, approval_id: int) -> list[dict[str, Any]]:
        with self._connection() as conn:
            content_id = self._approval_content(conn, approval_id)
            rows = conn.execute("SELECT id,kind,mime,bytes,origin,status,created_at FROM marketing_assets WHERE tenant_id=? AND content_id=? ORDER BY id DESC", (self.repository.tenant_id, content_id)).fetchall()
        return [dict(row) for row in rows]

    def private_file(self, asset_id: int) -> tuple[Path, str]:
        with self._connection() as conn:
            row = conn.execute("SELECT filename,mime FROM marketing_assets WHERE tenant_id=? AND id=?", (self.repository.tenant_id, asset_id)).fetchone()
        if not row:
            raise ValueError("파일을 찾을 수 없습니다.")
        path = self.root / row["filename"]
        if not path.is_file():
            raise FileNotFoundError("저장된 파일이 없습니다.")
        return path, str(row["mime"])
