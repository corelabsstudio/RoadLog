"""Manual-only Gemini content adapter. No customer or account data is sent."""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx


class RoadLogGeminiProvider:
    name = "Google Gemini"

    def __init__(self, client: httpx.Client | None = None, sleep=time.sleep):
        self.model = os.getenv("SAJU_MODEL", "gemini-3.8-flash")
        self.connected = bool(os.getenv("GEMINI_API_KEY", "").strip())
        self.client = client
        self.sleep = sleep
        self.usage: dict[str, int] = {}

    def generate(self, product: dict[str, Any], platform: str) -> dict[str, Any]:
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise PermissionError("Gemini API 키가 없어 실제 AI 초안을 만들 수 없습니다.")
        snapshot = {field: product.get(field, "UNKNOWN") for field in (
            "product_id", "name", "price_won", "free", "lamp_price", "premium", "confirmed_results", "forbidden_expressions", "synced_at", "source_file"
        )}
        fields = {"platform": "STRING", "product_id": "STRING", "title": "STRING", "hook": "STRING",
                  "body": "STRING", "cta": "STRING", "image_prompt": "STRING", "factual_claims": "ARRAY",
                  "source_facts": "STRING", "uncertainty": "ARRAY"}
        schema = {"type": "OBJECT", "properties": {name: ({"type": "ARRAY", "items": {"type": "STRING"}} if kind == "ARRAY" else {"type": kind}) for name, kind in fields.items()}, "required": list(fields)}
        body = {"systemInstruction": {"parts": [{"text": "ROADLOG 마케팅 초안만 작성하세요. 제공된 상품 사실 외 가격·할인·기능·수치·효과 보장을 만들지 마세요. 불확실한 사실은 쓰지 말고 uncertainty에 적으세요. source_facts는 상품 ID입니다. 한국어로 자연스럽고 과장 없이 쓰세요."}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps({"platform": platform, "facts": snapshot}, ensure_ascii=False)}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024, "thinkingConfig": {"thinkingBudget": 0}, "responseMimeType": "application/json", "responseSchema": schema}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        last_error = "AI 응답 오류"
        for attempt in range(3):
            try:
                if self.client is None:
                    response = httpx.post(url, params={"key": key}, json=body, timeout=20)
                else:
                    response = self.client.post(url, params={"key": key}, json=body, timeout=20)
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"공급자 일시 오류 ({response.status_code})"
                else:
                    response.raise_for_status()
                    payload = response.json()
                    text = "".join(part.get("text", "") for part in payload["candidates"][0]["content"]["parts"])
                    draft = json.loads(text)
                    if not isinstance(draft, dict) or any(name not in draft for name in fields):
                        raise ValueError("필수 필드가 없는 AI 응답")
                    if draft["platform"] != platform or draft["product_id"] != product["product_id"]:
                        raise ValueError("요청 상품·채널과 다른 AI 응답")
                    if any(not isinstance(draft[name], str) for name, kind in fields.items() if kind == "STRING") or any(not isinstance(draft[name], list) or any(not isinstance(v, str) for v in draft[name]) for name, kind in fields.items() if kind == "ARRAY"):
                        raise ValueError("필드 형식이 잘못된 AI 응답")
                    usage = payload.get("usageMetadata") or {}
                    self.usage = {"input_tokens": int(usage.get("promptTokenCount") or 0), "output_tokens": int(usage.get("candidatesTokenCount") or 0)}
                    draft["estimated_cost"] = None
                    return draft
            except (httpx.TimeoutException, httpx.TransportError):
                last_error = "AI 응답 시간 초과 또는 연결 오류"
            except (ValueError, KeyError, IndexError, TypeError):
                last_error = "AI 응답 구조 오류"
                break
            except httpx.HTTPStatusError:
                last_error = f"공급자 요청 거부 ({response.status_code})"
                break
            if attempt < 2:
                self.sleep(2 ** attempt)
        raise ValueError(last_error)
