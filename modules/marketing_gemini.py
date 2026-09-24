"""Manual-only Gemini content adapter. No customer or account data is sent."""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from modules import marketing_safety


class RoadLogGeminiProvider:
    name = "Google Gemini"

    def __init__(self, client: httpx.Client | None = None, sleep=time.sleep):
        self.model = os.getenv("SAJU_MODEL", "gemini-3.8-flash")
        self.connected = bool(os.getenv("GEMINI_API_KEY", "").strip()) and marketing_safety.enabled("gemini") and bool(marketing_safety.cost_settings()["paid_enabled"])
        self.client = client
        self.sleep = sleep
        self.usage: dict[str, int] = {}

    def generate(self, product: dict[str, Any], platform: str) -> dict[str, Any]:
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise PermissionError("Gemini API 키가 없어 실제 AI 초안을 만들 수 없습니다.")
        if not marketing_safety.enabled("gemini"):
            raise PermissionError("마케팅 Gemini API가 비활성화되어 있습니다.")
        snapshot = {field: product.get(field, "UNKNOWN") for field in (
            "product_id", "name", "price_won", "free", "lamp_price", "premium", "confirmed_results", "forbidden_expressions", "synced_at", "source_file", "marketing_focus_result"
        )}
        fields = {"platform": "STRING", "product_id": "STRING", "title": "STRING", "hook": "STRING",
                  "body": "STRING", "cta": "STRING", "image_prompt": "STRING", "factual_claims": "ARRAY",
                  "source_facts": "STRING", "uncertainty": "ARRAY"}
        schema = {"type": "OBJECT", "properties": {name: ({"type": "ARRAY", "items": {"type": "STRING"}} if kind == "ARRAY" else {"type": kind}) for name, kind in fields.items()}, "required": list(fields)}
        schema["properties"]["factual_claims"]["items"]["enum"] = product["confirmed_results"]
        body = {"systemInstruction": {"parts": [{"text": "ROADLOG 마케팅 초안만 작성하세요. 제공된 상품 사실 외 가격·할인·기능·수치·효과 보장을 만들지 마세요. factual_claims에는 사용한 결과 항목을 confirmed_results에서 글자까지 동일하게 복사하세요. 해당 항목이 없으면 빈 배열로 두세요. 불확실한 사실은 쓰지 말고 uncertainty에 적으세요. source_facts는 상품 ID입니다. strategy_context는 AI 추론이며 검증된 사실이나 수치로 인용하지 마세요. 한국어로 자연스럽고 과장 없이 쓰세요."}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps({"platform": platform, "facts": snapshot, "strategy_context": product.get("strategy_context") or []}, ensure_ascii=False)}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024, "thinkingConfig": {"thinkingBudget": 0}, "responseMimeType": "application/json", "responseSchema": schema}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        last_error = "AI 응답 오류"
        for attempt in range(3):
            usage_recorded = False
            try:
                audit_id = marketing_safety.before_call("gemini", "generate_content", campaign_id=int(product.get("campaign_id") or 0), agent_id="content_writer", model=self.model, request_body=body)
                if self.client is None:
                    response = httpx.post(url, params={"key": key}, json=body, timeout=20)
                else:
                    response = self.client.post(url, params={"key": key}, json=body, timeout=20)
                marketing_safety.after_call(audit_id, "HTTP_" + str(response.status_code))
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"공급자 일시 오류 ({response.status_code})"
                else:
                    response.raise_for_status()
                    payload = response.json()
                    measured = marketing_safety.record_usage(audit_id, self.model, payload.get("usageMetadata"))
                    usage_recorded = True
                    self.usage = {"input_tokens": measured["input_tokens"], "output_tokens": measured["output_tokens"]}
                    text = "".join(part.get("text", "") for part in payload["candidates"][0]["content"]["parts"])
                    draft = json.loads(text)
                    if not isinstance(draft, dict) or any(name not in draft for name in fields):
                        raise ValueError("필수 필드가 없는 AI 응답")
                    if draft["platform"] != platform or draft["product_id"] != product["product_id"]:
                        raise ValueError("요청 상품·채널과 다른 AI 응답")
                    if any(not isinstance(draft[name], str) for name, kind in fields.items() if kind == "STRING") or any(not isinstance(draft[name], list) or any(not isinstance(v, str) for v in draft[name]) for name, kind in fields.items() if kind == "ARRAY"):
                        raise ValueError("필드 형식이 잘못된 AI 응답")
                    draft["estimated_cost"] = None
                    return draft
            except (httpx.TimeoutException, httpx.TransportError):
                marketing_safety.after_call(audit_id, "TIMEOUT")
                last_error = "AI 응답 시간 초과 또는 연결 오류"
            except (ValueError, KeyError, IndexError, TypeError):
                if not usage_recorded:
                    marketing_safety.after_call(audit_id, "USAGE_INVALID")
                    marketing_safety.trip_kill("AI 응답을 해석할 수 없어 사용량 미확인")
                last_error = "AI 응답 구조 오류"
                break
            except httpx.HTTPStatusError:
                last_error = f"공급자 요청 거부 ({response.status_code})"
                break
            if attempt < 2:
                self.sleep(2 ** attempt)
        raise ValueError(last_error)

    def generate_role(self, task: Any, product: dict[str, Any], *, draft: dict[str, Any] | None = None, metrics: dict[str, Any] | None = None, context: list[str] | None = None) -> dict[str, Any]:
        """One separate Gemini request per role. No external metrics or full prompt is stored."""
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise PermissionError("Gemini API 키가 없습니다.")
        if not marketing_safety.enabled("gemini"):
            raise PermissionError("마케팅 Gemini API가 비활성화되어 있습니다.")
        facts = {field: product.get(field, "UNKNOWN") for field in (
            "product_id", "name", "price_won", "free", "lamp_price", "premium",
            "confirmed_results", "forbidden_expressions", "synced_at", "source_file"
        )}
        schema = {"type": "OBJECT", "properties": {
            "summary": {"type": "STRING"}, "recommendations": {"type": "ARRAY", "items": {"type": "STRING"}},
            "source_facts": {"type": "ARRAY", "items": {"type": "STRING"}},
            "unknowns": {"type": "ARRAY", "items": {"type": "STRING"}},
            "review_passed": {"type": "BOOLEAN"},
        }, "required": ["summary", "recommendations", "source_facts", "unknowns", "review_passed"]}
        if task.agent_id == "marketing_director":
            schema["properties"]["decision"] = {"type":"STRING","enum":["NO_ACTION","RESEARCH","CREATE","OPTIMIZE","PUBLISH_READY"]}
            schema["properties"]["reasonForRetry"] = {"type":"STRING"}
            schema["required"].extend(["decision","reasonForRetry"])
        instructions = ("ROADLOG의 지정된 마케팅 역할 한 가지만 수행하세요. 제공되지 않은 가격·할인·기능·"
                        "시장 수치·검색량·성과 수치를 만들지 마세요. 외부 게시를 제안할 수는 있으나 실행했다고 말하지 마세요. "
                        "summary는 300자 이하, recommendations는 최대 3개로 제한하세요. "
                        "source_facts에는 상품 ID, confirmed_results의 원문, 제공된 metrics.source만 글자까지 동일하게 복사하세요. "
                        "metrics가 있으면 그 수치만 인용하고 새 숫자는 만들지 마세요. 미연결 데이터는 unknowns에 쓰세요. "
                        "품질 검수자 외에는 review_passed를 false로 두세요. 품질 검수자는 초안의 사실 불일치가 있으면 false로 두세요. "
                        "context는 앞 단계 AI의 추론이며 검증된 외부 자료가 아닙니다. 마케팅 디렉터는 이전 캠페인 실측 성과와 Learning을 읽고 decision으로 행동 여부를 선택하세요. 동일 상품 전략을 다시 쓴다면 reasonForRetry에 새 근거를 적고, 그렇지 않으면 빈 문자열로 두세요.")
        payload = {"role": task.agent_id, "objective": task.objective, "missing_data": task.missing_data,
                   "facts": facts, "metrics": metrics,
                   "draft": {k: draft.get(k) for k in ("title", "hook", "body", "cta", "factual_claims") } if draft else None,
                   "context": (context or [])[:3]}
        body = {"systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700,
                                     "thinkingConfig": {"thinkingBudget": 0},
                                     "responseMimeType": "application/json", "responseSchema": schema}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        last_error = "AI 응답 오류"
        for attempt in range(3):
            usage_recorded = False
            try:
                audit_id = marketing_safety.before_call("gemini", "generate_role", campaign_id=int(product.get("campaign_id") or 0), agent_id=task.agent_id, model=self.model, request_body=body)
                response = (self.client.post if self.client else httpx.post)(url, params={"key": key}, json=body, timeout=20)
                marketing_safety.after_call(audit_id, "HTTP_" + str(response.status_code))
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"공급자 일시 오류 ({response.status_code})"
                else:
                    response.raise_for_status()
                    raw = response.json()
                    measured = marketing_safety.record_usage(audit_id, self.model, raw.get("usageMetadata"))
                    usage_recorded = True
                    self.usage = {"input_tokens": measured["input_tokens"], "output_tokens": measured["output_tokens"]}
                    result = json.loads("".join(p.get("text", "") for p in raw["candidates"][0]["content"]["parts"]))
                    if not isinstance(result, dict) or not isinstance(result.get("summary"), str) or len(result["summary"]) > 300:
                        raise ValueError("역할 응답 형식 오류")
                    for field in ("recommendations", "source_facts", "unknowns"):
                        if not isinstance(result.get(field), list) or any(not isinstance(x, str) for x in result[field]):
                            raise ValueError("역할 응답 형식 오류")
                    if len(result["recommendations"]) > 3 or not isinstance(result.get("review_passed"), bool):
                        raise ValueError("역할 응답 형식 오류")
                    if task.agent_id == "marketing_director" and result.get("decision") not in {"NO_ACTION","RESEARCH","CREATE","OPTIMIZE","PUBLISH_READY"}:
                        raise ValueError("마케팅 결정 형식 오류")
                    return result
            except (httpx.TimeoutException, httpx.TransportError):
                marketing_safety.after_call(audit_id, "TIMEOUT")
                last_error = "AI 응답 시간 초과 또는 연결 오류"
            except (ValueError, KeyError, IndexError, TypeError):
                if not usage_recorded:
                    marketing_safety.after_call(audit_id, "USAGE_INVALID")
                    marketing_safety.trip_kill("AI 응답을 해석할 수 없어 사용량 미확인")
                last_error = "AI 응답 구조 오류"
                break
            except httpx.HTTPStatusError:
                last_error = f"공급자 요청 거부 ({response.status_code})"
                break
            if attempt < 2:
                self.sleep(2 ** attempt)
        raise ValueError(last_error)
