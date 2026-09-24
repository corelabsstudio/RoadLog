"""Conservative preflight estimates for the ROADLOG paid text provider.

This is an internal risk control, never a guarantee about Google's invoice.
Unknown models, currencies, request shapes, or usage must fail closed.
"""
from __future__ import annotations

import json
import math
from decimal import Decimal, ROUND_CEILING

# Official Gemini API Standard paid rates as of 2026-09-25. Do not silently
# carry the introductory 2026 price into 2027.
RATES_USD_PER_MILLION = {"gemini-3.8-flash": (Decimal("0.75"), Decimal("3.75"))}
USD_KRW_SAFETY_RATE = Decimal("2000")  # Conservative planning assumption, not live FX.
SAFETY_MULTIPLIER = Decimal("2")


def _rates(model: str, day: str) -> tuple[Decimal, Decimal]:
    if day > "2026-12-31" or model not in RATES_USD_PER_MILLION:
        raise PermissionError("AI 모델 요금표 미확인 · 유료 호출 차단")
    return RATES_USD_PER_MILLION[model]


def quote(model: str, body: dict, day: str) -> dict[str, int]:
    input_rate, output_rate = _rates(model, day)
    if not isinstance(body, dict) or not isinstance(body.get("generationConfig"), dict):
        raise PermissionError("AI 요청 크기를 계산할 수 없어 유료 호출 차단")
    output_cap = body["generationConfig"].get("maxOutputTokens")
    if type(output_cap) is not int or not 1 <= output_cap <= 2048:
        raise PermissionError("AI 출력 상한이 확인되지 않아 유료 호출 차단")
    encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not encoded or len(encoded) > 100_000:
        raise PermissionError("AI 입력 크기 상한 초과")
    # UTF-8 bytes multiplied by two plus fixed overhead deliberately exceeds
    # a normal text token count. This remains an estimate, not a token proof.
    input_ceiling = len(encoded) * 2 + 2048
    usd = (Decimal(input_ceiling) * input_rate + Decimal(output_cap) * output_rate) / 1_000_000
    estimated = max(1, math.ceil(usd * USD_KRW_SAFETY_RATE))
    reserved = max(estimated, math.ceil(usd * USD_KRW_SAFETY_RATE * SAFETY_MULTIPLIER))
    return {"input_token_ceiling": input_ceiling, "output_token_ceiling": output_cap,
            "estimated_cost_krw": estimated, "reserved_cost_krw": reserved}


def usage_cost(model: str, usage: dict, day: str) -> dict[str, int]:
    input_rate, output_rate = _rates(model, day)
    if not isinstance(usage, dict):
        raise ValueError("AI 사용량 누락")
    fields = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount")
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in fields[:2]):
        raise ValueError("AI 사용량 응답 오류")
    thoughts = usage.get("thoughtsTokenCount", 0)
    if type(thoughts) is not int or thoughts < 0:
        raise ValueError("AI 생각 토큰 응답 오류")
    prompt, output = usage["promptTokenCount"], usage["candidatesTokenCount"] + thoughts
    if prompt <= 0 or output <= 0:
        raise ValueError("AI 사용량 0 또는 누락")
    usd = (Decimal(prompt) * input_rate + Decimal(output) * output_rate) / 1_000_000
    krw = (usd * USD_KRW_SAFETY_RATE).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    return {"input_tokens": prompt, "output_tokens": output,
            "thought_tokens": thoughts, "actual_cost_estimate_krw": float(krw)}
