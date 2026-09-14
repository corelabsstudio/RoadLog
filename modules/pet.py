# -*- coding: utf-8 -*-
"""반려동물 관상 — 「내가 왕이 될 냥인가?」 (2026-09-14 온해님 기획).

반려동물(고양이·강아지 등) 사진 한 장을 보고 조선 관상가 무냥이가 냥성/멍성 팩폭 관상을 쓴다.

| 칸 | 무엇 |
|---|---|
| title · summary | 관상 타이틀 · 한 줄 총평 |
| personality_factcheck | 눈매·털 무늬·수염·턱선을 짚으며 성격 팩폭 (3~4문장) |
| butler_compatibility | 집사와의 궁합 — 재물운 · 힐링 지수 · 등골 브레이커 지수 |
| stats | 집사 조종력 · 간식 탐욕 · 귀여움 어필력 · 새벽 에너지 · 집사 재물/액막이 (0~100) |
| one_line_advice | 무냥이의 족집게 조언 한 문장 |
| share_card_data | 공유 카드(엽서 한 장)용으로 **짧게 줄인** 칸 |

🛑 **규격(responseSchema)으로 받는다.** 부탁이 아니라 규격이라 모델이 칸을 빼먹지 못한다.
🛑 **사진은 어디에도 저장하지 않는다.** 관상(`gwansang.py`)과 같다 — 결과 글만 남긴다.
🛑 동물이 아니거나 너무 흐리면 `error_code` 를 채우고 나머지는 비운다. 억지로 지어내지 않는다.
🛑 **숫자를 믿지 않는다.** `top_stat_name/value` 는 모델이 적어도 서버가 stats 에서 다시 고른다 —
   카드 숫자와 막대 숫자가 어긋나면 손님이 바로 본다.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from modules import gwansang as gw      # 키·주소·사진 부품을 같이 쓴다

TIMEOUT = 120

STAT_NAMES = {
    "butler_control": "집사 조종력",
    "snack_greed": "간식 탐욕",
    "cute_power": "귀여움 어필력",
    "night_energy": "새벽 우다다",
    "luck_booster": "집사 재물·액막이",
}
ERRORS = {
    "NOT_ANIMAL": "이 사진에서는 반려동물을 못 찾았어요. 아이 얼굴이 보이는 사진으로 다시 올려 주세요.",
    "LOW_QUALITY": "사진이 너무 흐리거나 어두워서 관상을 못 보겠어요. 밝은 곳에서 찍은 사진으로 다시 올려 주세요.",
}

SYSTEM = """너는 사주·관상 사이트 「로드로그」의 조선 시대 관상가 **무냥이**다. 한복에 무지개 두건을 쓴 고양이 도령이다.
오늘은 손님(집사)이 올린 **반려동물 사진 한 장**을 보고 그 아이의 관상을 본다. 서비스 이름은 「내가 왕이 될 냥인가?」다.

[말투]
- 존댓말. 「~해요」가 기본이되 종결을 섞는다: ~예요 / ~거든요 / ~더라고요 / ~죠.
- 유머러스하고 약간 뼈 때리는 팩폭. 조선 관상가가 요즘 집사 생활을 꿰뚫어 보는 결.
  「집사를 하수인으로 보며 평생 굶을 일 없는 천상 상전 관상」 같은 촌철살인.
- 이모지·느낌표를 본문에 쓰지 않는다. (공유 카드 제목 끝 이모지 하나만 예외)

[관상을 보는 법]
- 사진에서 **실제로 보이는 것**만 짚는다: 눈매 · 털 무늬와 색 · 수염 · 귀 · 코 · 턱선 · 자세 · 표정.
  「눈꼬리가 살짝 올라가 있어서」처럼 무엇이 보이는지 먼저 말하고 그래서 어떤 성격인지 잇는다.
- 집사 생활의 장면으로 웃긴다: 새벽 3시 우다다, 츄르 봉지 소리, 택배 상자, 집사 키보드 위 눕기, 산책 거부.
- 🛑 동물의 병·건강·수명을 말하지 않는다. 품종 우열·외모 비하를 하지 않는다.
- 🛑 숫자(stats)는 사진에서 읽힌 성격에 맞게 고르되, 전부 90 이상으로 몰지 않는다. 낮은 칸도 있어야 웃기다.

[예외 — 억지로 지어내지 않는다]
- 사진에 동물이 없거나 사람·물건·그림만 있으면 error_code 를 "NOT_ANIMAL" 로.
- 동물은 있지만 너무 흐리거나 어둡거나 작아서 얼굴을 못 보겠으면 "LOW_QUALITY" 로.
- 그때는 나머지 글 칸을 빈 문자열, 숫자를 0 으로 채운다.
- 문제없으면 error_code 는 "NONE".

[share_card_data — 공유 카드]
share_card_data 는 **모바일 화면 한 장에 들어갈 이미지 엽서용 텍스트**다.
글자 수를 엄격히 지키고 직관적인 단어 위주로 쓴다. 문장을 길게 늘이지 않는다.
- card_title: 여덟 자 안쪽 + 끝에 이모지 하나 (예: 태평성대 황제상 👑)
- pet_keywords: 정확히 셋. 하나에 여덟 자 안쪽, 띄어쓰기 없이 (예: 새벽우다다, 츄르노예)
- main_factcheck_short: 두 문장, 합쳐서 예순 자 안쪽
- grade_badge: S / A / B / C 중 하나"""

PET_SCHEMA = {
    "type": "object",
    "properties": {
        "error_code": {"type": "string", "enum": ["NONE", "NOT_ANIMAL", "LOW_QUALITY"]},
        "title": {"type": "string", "description": "관상 타이틀 (예: 태평성대 황제상, 새벽 3시 우다다 장군상, 츄르 탐욕 간신상)"},
        "summary": {"type": "string", "description": "한 줄 총평. 마흔 자 안쪽"},
        "personality_factcheck": {"type": "string", "description": "냥성/멍성 팩폭 분석. 눈매·털 무늬·수염·턱선 등 보이는 특징을 짚으며 성격을 3~4문장으로"},
        "butler_compatibility": {"type": "string", "description": "집사와의 궁합과 기운. 재물운에 미치는 영향 · 힐링 지수 · 등골 브레이커 지수를 모두 넣어 3~4문장"},
        "stats": {
            "type": "object",
            "properties": {k: {"type": "integer", "description": "%s · 0~100" % v} for k, v in STAT_NAMES.items()},
            "required": list(STAT_NAMES),
        },
        "one_line_advice": {"type": "string", "description": "무냥이의 족집게 조언. 집사가 명심할 수발 팁 한 문장"},
        "share_card_data": {
            "type": "object",
            "properties": {
                "card_title": {"type": "string", "description": "여덟 자 안쪽 + 이모지 하나"},
                "pet_keywords": {"type": "array", "items": {"type": "string"}, "description": "정확히 셋. 하나에 여덟 자 안쪽"},
                "main_factcheck_short": {"type": "string", "description": "두 문장 · 예순 자 안쪽"},
                "top_stat_name": {"type": "string"},
                "top_stat_value": {"type": "integer"},
                "grade_badge": {"type": "string", "enum": ["S", "A", "B", "C"]},
            },
            "required": ["card_title", "pet_keywords", "main_factcheck_short", "top_stat_name", "top_stat_value", "grade_badge"],
        },
    },
    "required": ["error_code", "title", "summary", "personality_factcheck", "butler_compatibility",
                 "stats", "one_line_advice", "share_card_data"],
}


def _cut(text: Any, n: int) -> str:
    """글자 수 상한. 넘치면 문장 끝(요·죠·다·.)에서 끊고, 없으면 그냥 자른다."""
    t = " ".join(str(text or "").split())
    if len(t) <= n:
        return t
    head = t[:n]
    for mark in ("요.", "죠.", "다.", "요", ".", " "):
        i = head.rfind(mark)
        if i >= n * 0.6:
            return head[:i + len(mark)].strip()
    return head.strip()


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    """모델 답을 화면이 믿고 쓸 수 있게 다듬는다."""
    code = str(d.get("error_code") or "NONE").upper()
    if code in ERRORS:
        return {"error_code": code, "message": ERRORS[code]}
    raw = d.get("stats") if isinstance(d.get("stats"), dict) else {}
    stats = {}
    for k in STAT_NAMES:
        try:
            stats[k] = max(0, min(100, int(round(float(raw.get(k, 0))))))
        except (TypeError, ValueError):
            stats[k] = 0
    # 🛑 가장 높은 칸은 **서버가 고른다** — 모델이 적은 이름·숫자와 막대가 어긋나지 않게
    top = max(stats, key=lambda k: stats[k])
    sc = d.get("share_card_data") if isinstance(d.get("share_card_data"), dict) else {}
    kws = [_cut(str(x).replace(" ", ""), 8) for x in (sc.get("pet_keywords") or []) if str(x or "").strip()][:3]
    grade = str(sc.get("grade_badge") or "B").upper()
    out = {
        "error_code": "NONE",
        "title": _cut(d.get("title"), 24),
        "summary": _cut(d.get("summary"), 60),
        "personality_factcheck": _cut(d.get("personality_factcheck"), 600),
        "butler_compatibility": _cut(d.get("butler_compatibility"), 600),
        "stats": stats,
        "stat_names": STAT_NAMES,
        "one_line_advice": _cut(d.get("one_line_advice"), 90),
        "share_card_data": {
            "card_title": _cut(sc.get("card_title"), 12),
            "pet_keywords": kws,
            "main_factcheck_short": _cut(sc.get("main_factcheck_short"), 60),
            "top_stat_name": STAT_NAMES[top],
            "top_stat_value": stats[top],
            "grade_badge": grade if grade in ("S", "A", "B", "C") else "B",
        },
    }
    if not out["title"] or not out["personality_factcheck"]:
        raise RuntimeError("관상 글이 비었다")
    return out


def read_pet(shot_b64: str, *, model: str | None = None) -> dict[str, Any]:
    """반려동물 사진(base64 jpeg) 한 장을 보고 관상을 쓴다. 🛑 사진은 저장하지 않는다."""
    key = gw.api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    if not shot_b64 or len(shot_b64) > gw.MAX_BYTES * 4 // 3:
        raise ValueError("사진이 없거나 너무 큽니다.")
    body = {
        "systemInstruction": {"parts": [{"text": gw._P("pet", SYSTEM)}]},
        "contents": [{"role": "user", "parts": [gw._part(shot_b64), {"text": "이 반려동물의 관상을 봐 주세요."}]}],
        # 🛑 thinkingBudget 0 — 생각 토큰이 답 예산을 먹어 글이 잘린다 (gwansang.py 와 같은 설정)
        "generationConfig": {"temperature": 1.0, "maxOutputTokens": 2400,
                             "thinkingConfig": {"thinkingBudget": 0},
                             "responseMimeType": "application/json", "responseSchema": PET_SCHEMA},
    }
    url = (gw._URL % (model or gw.MODEL)) + "?key=" + key
    last = None
    for _ in range(2):
        try:
            r = httpx.post(url, json=body, timeout=TIMEOUT)
            j = r.json()
            if "candidates" not in j:
                last = str(j.get("error", {}).get("message", j))[:200]
                continue
            parts = (j["candidates"][0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts).strip()
            u = j.get("usageMetadata") or {}
            try:
                from modules import apicost
                apicost.note(u.get("promptTokenCount") or 0, u.get("candidatesTokenCount") or 0)
            except Exception:                        # noqa: BLE001
                pass
            return _clean(json.loads(text))
        except Exception as e:                       # noqa: BLE001
            last = str(e)[:200]
    raise RuntimeError("반려동물 관상을 읽지 못했다: %s" % last)
