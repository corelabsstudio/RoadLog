"""ROADLOG creative provider. Paid generation is opt-in and never runs on import."""
from __future__ import annotations

import base64
import binascii
import os
from typing import Any

import httpx


class GeminiImageProvider:
    name = "Google Gemini image"
    model = "gemini-3.1-flash-image"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent"

    def __init__(self, client: httpx.Client | None = None, *, key: str | None = None, enabled: bool | None = None):
        self._key = key if key is not None else os.getenv("GEMINI_API_KEY", "")
        self.enabled = enabled if enabled is not None else os.getenv("MARKETING_IMAGE_GENERATION_ENABLED", "false").lower() == "true"
        self.connected = bool(self._key.strip() and self.enabled)
        self.client = client

    def generate_image(self, brief: dict[str, Any]) -> dict[str, Any]:
        if not self.connected:
            raise PermissionError("이미지 생성 API가 비활성화됐거나 키가 없습니다.")
        if not brief.get("product_id") or not brief.get("image_prompt"):
            raise ValueError("상품 정본과 이미지 지시안이 필요합니다.")
        # Do not request rendered price or product claims in the image. Text facts
        # remain subject to the separate catalog reviewer.
        prompt = ("Create one original, high-quality Korean social marketing image. "
                  "No text, letters, prices, discounts, logos or watermarks. "
                  "Do not depict guaranteed outcomes. Visual brief: " + str(brief["image_prompt"])[:1200])
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]}}
        client = self.client or httpx.Client(timeout=90.0, follow_redirects=False)
        try:
            response = client.post(self.endpoint, headers={"x-goog-api-key": self._key, "Content-Type": "application/json"}, json=body)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Do not leak provider response bodies, request URLs, or secrets.
            raise ValueError("이미지 공급자 요청 또는 응답에 실패했습니다.") from None
        finally:
            if self.client is None:
                client.close()
        for candidate in payload.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data") or {}
                mime = inline.get("mimeType") or inline.get("mime_type")
                if mime not in {"image/png", "image/jpeg"}:
                    continue
                try:
                    data = base64.b64decode(inline.get("data", ""), validate=True)
                except (ValueError, binascii.Error):
                    raise ValueError("이미지 공급자의 파일 인코딩이 올바르지 않습니다.") from None
                if not data:
                    raise ValueError("이미지 공급자가 빈 파일을 반환했습니다.")
                return {"data": data, "mime": mime, "provider": self.name, "model": self.model,
                        "usage": payload.get("usageMetadata") or {}}
        raise ValueError("이미지 공급자가 실제 이미지 파일을 반환하지 않았습니다.")
