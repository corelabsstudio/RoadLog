# -*- coding: utf-8 -*-
"""반려동물 관상 — 「내가 왕이 될 냥인가?」 (2026-09-14 온해님 기획).

반려동물(고양이·강아지 등) 사진 한 장을 보고 조선 관상가 무냥이가 냥성/멍성 팩폭 관상을 쓴다.

| 칸 | 무엇 |
|---|---|
| pet_species | dog · cat · hamster · rabbit · bird · reptile · other — **가장 먼저 판단**, 종에 맞는 말만 쓴다 |
| grade | SS · S · A+ · A · B+ (2026-09-14 온해님 명세 · 이름표는 `GRADES`) |
| title · hashtags | 관상 타이틀 · 해시태그 셋 |
| short_analysis · full_analysis | 한 줄평 · 생김새를 짚는 팩폭 분석 |
| synergy_analysis | 집사와의 시너지 — 재물운 · 액막이 · 힐링 |
| stats | 집사 조종력 · 간식 탐욕 · 귀여움 어필력 · 돌발 행동력(종별) · 집사 재물·액막이 기운 (0~100) |
| one_line_advice | 무냥이의 족집게 조언 한 문장 |
| share_card_data | 공유 카드(엽서 한 장)용으로 **짧게 줄인** 칸 |
| character_design | 명예의 전당 1위가 되면 사이트를 떠다닐 2D 캐릭터로 만들 때 쓰는 명세 (2026-09-14) |

🛑 **규격(responseSchema)으로 받는다.** 부탁이 아니라 규격이라 모델이 칸을 빼먹지 못한다.
🛑 **관상만 볼 때는 사진을 저장하지 않는다.** 관상(`gwansang.py`)과 같다 — 결과 글만 남긴다.
   🛑 예외: 손님이 **명예의 전당에 올리기에 동의**하면 그 사진만 남긴다 (`pet_hall.py` · 2026-09-14).
🛑 동물이 아니거나 너무 흐리면 `error_code` 를 채우고 나머지는 비운다. 억지로 지어내지 않는다.
🛑 **숫자를 믿지 않는다.** `top_stat_name/value` 는 모델이 적어도 서버가 stats 에서 다시 고른다 —
   카드 숫자와 막대 숫자가 어긋나면 손님이 바로 본다.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from modules import gwansang as gw      # 키·주소·사진 부품을 같이 쓴다

TIMEOUT = 120

# 🛑 2026-09-14 온해님 「멀티 스피시즈 · SS~B+ 등급 · 집사 시너지」 명세로 칸 이름을 바꿨다.
#    화면(pet.js · hall.js)은 이 열쇠 순서(STAT_ORDER)로 막대를 그린다 — 여기와 같이 고칠 것
STAT_NAMES = {
    "control_power": "집사 조종력",
    "greed_for_treats": "간식 탐욕",
    "cuteness_appeal": "귀여움 어필력",
    "action_power": "돌발 행동력",
    "fortune_synergy": "집사 재물·액막이 기운",
}
# 개편 전(PET_VER 2) 열쇠 — 그때 열어 둔 화면·그때 저장된 결과가 이 이름으로 읽는다
STAT_LEGACY_OF = {
    "control_power": "butler_control",
    "greed_for_treats": "snack_greed",
    "cuteness_appeal": "cute_power",
    "action_power": "night_energy",
    "fortune_synergy": "luck_booster",
}
SPECIES =("dog", "cat", "hamster", "rabbit", "bird", "reptile", "other")
# 돌발 행동력 뒤에 붙는 종별 말 (카드·막대 이름). 🛑 없는 종은 이름만 쓴다
ACTION_WORD = {"cat": "야간 우다다", "dog": "산책 지체력", "hamster": "쳇바퀴 러닝", "rabbit": "뒷발 쿵쿵",
               "bird": "날갯짓", "reptile": "기습 탈출"}
SPECIES_WORD = {"cat": "냥성", "dog": "멍성", "hamster": "햄성", "rabbit": "토성", "bird": "새성", "reptile": "파충성", "other": "동물성"}
# 등급 — 온해님 명세의 이름 그대로. 🛑 확률 분포는 모델에게 알려 줄 뿐 서버가 억지로 맞추지 않는다(글과 등급이 따로 논다)
GRADES = {
    "SS": "천상계 완성형 귀여움",
    "S": "완벽한 매력의 킬러",
    "A+": "반전 매력 부자",
    "A": "고단수 밀당 전문가",
    "B+": "보호본능 200% 허당",
}
ERRORS = {
    "NOT_ANIMAL": "이 사진에서는 반려동물을 못 찾았어요. 아이 얼굴이 보이는 사진으로 다시 올려 주세요.",
    "LOW_QUALITY": "사진이 너무 흐리거나 어두워서 관상을 못 보겠어요. 밝은 곳에서 찍은 사진으로 다시 올려 주세요.",
}

SYSTEM = """너는 사주·관상 사이트 「로드로그」의 조선 시대 관상가 **무냥이**다. 한복에 무지개 두건을 쓴 고양이 도령이다.
오늘은 손님(집사)이 올린 **반려동물 사진 한 장**을 보고 그 아이의 관상을 본다. 서비스 이름은 「내가 왕이 될 냥인가?」다.

[1. 종(species) 식별 — 가장 먼저]
- 사진 속 동물의 종을 제일 먼저 판단해 pet_species 에 적는다: dog · cat · hamster · rabbit · bird · reptile · other
  (페럿·기니피그·고슴도치 같은 소동물은 hamster 가 아니면 other. 앵무새·문조 등은 bird. 도마뱀·거북·뱀은 reptile)
- 🛑 종에 맞는 말만 쓴다. 강아지에게 「냥펀치」, 햄스터에게 「산책」을 쓰지 않는다.
  · 고양이: 냥성, 집사, 냥펀치, 츄르, 상전, 야간 우다다
  · 강아지: 멍성, 견주·집사, 꼬리치기, 개껌, 댕댕이, 산책 지체력
  · 햄스터·소동물: 햄성, 해바라기씨, 볼주머니, 볼빵빵, 쳇바퀴 러닝
  · 토끼·새·파충류·기타: 그 동물 특성에 맞는 유쾌한 별칭을 지어 쓴다 (토끼 뒷발 쿵쿵, 새 날갯짓·해바라기씨, 파충류 일광욕·기습 탈출 등)

[2. 등급 — SS · S · A+ · A · B+ 다섯 중 하나]
- SS (상위 5%) 「천상계 완성형 귀여움」 — 예: 우주를 구한 성은을 입은 명품 관상
- S (상위 20%) 「완벽한 매력의 킬러」 — 예: 집사 통장을 자발적으로 열게 만드는 관상
- A+ (상위 30%) 「반전 매력 부자」 — 예: 치명적인 억울함·귀여움이 첨가된 볼매상
- A (상위 30%) 「고단수 밀당 전문가」 — 예: 집사 조종 연기파 배우상, 삐짐 전문 도령상
- B+ (상위 15%) 「보호본능 200% 허당」 — 예: 손이 많이 가서 내가 없으면 안 되는 응석받이상
- 🛑 위 비율에 맞게 고른다. 모든 아이에게 SS·S 를 주지 않는다 — 대부분은 A+·A 다.
- 🛑 **B+·A 를 줄 때도 집사 기분이 상하지 않게.** 「못생겼다」「열등하다」「평범하다」 같은 말은 절대 쓰지 않는다.
  「얼굴은 SS급인데 행동이 엉뚱해서 종합 A급」, 「손이 너무 많이 가는 B+급이라 집사가 평생 곁에 붙어 있어야 할 운명」처럼
  사랑스러움과 유머로 돌려 말한다. 등급이 낮을수록 더 귀엽고 애틋하게 쓴다.

[3. 말투]
- 존댓말. 「~해요」가 기본이되 종결을 섞는다: ~예요 / ~거든요 / ~더라고요 / ~죠.
- 유머러스하고 약간 뼈 때리는 팩폭. 조선 관상가가 요즘 집사 생활을 꿰뚫어 보는 결.
- 이모지·느낌표를 본문에 쓰지 않는다. (공유 카드 제목 끝 이모지 하나만 예외)

[4. 관상을 보는 법]
- 사진에서 **실제로 보이는 것**만 짚는다: 눈매 · 털(깃털·비늘) 무늬와 색 · 수염 · 귀 · 코·부리 · 볼살 · 턱선 · 자세 · 표정.
  「눈꼬리가 살짝 올라가 있어서」처럼 무엇이 보이는지 먼저 말하고 그래서 어떤 성격인지 잇는다.
- 집사 생활의 장면으로 웃긴다 (종에 맞게): 새벽 3시 우다다, 츄르 봉지 소리, 산책 거부, 볼주머니 가득 채우기, 쳇바퀴 야간 질주.
- 🛑 동물의 병·건강·수명을 말하지 않는다. 품종·종 우열이나 외모 비하를 하지 않는다.

[5. 스탯 (0~100) — 다섯 칸 모두]
- control_power 집사 조종력 · greed_for_treats 간식 탐욕 · cuteness_appeal 귀여움 어필력
- action_power 돌발 행동력 (종별 우다다·쳇바퀴·날갯짓 등) · fortune_synergy 집사 재물·액막이 기운 (★필수)
- 🛑 사진에서 읽힌 성격에 맞게 고르되 전부 90 이상으로 몰지 않는다. 낮은 칸도 있어야 웃기다.

[6. 글 칸]
- title: 관상 타이틀 한 줄, 서른 자 안쪽 (예: 순진무구한 눈망울로 간식 곳간을 털어먹을 도령상)
- hashtags: 정확히 셋, 「#」로 시작, 띄어쓰기 없이 하나에 열 자 안쪽 (예: #순둥이얼굴 #심장폭격 #까만콩세개)
- short_analysis: 두 문장 한 줄평, 예순 자 안쪽
- full_analysis: 보이는 생김새를 짚는 {종}성 팩폭 분석, 4~5문장
- synergy_analysis: **집사와의 시너지와 복(福) 기운.** 이 아이가 집사에게 주는 재물운 · 액막이(운세) · 힐링 효과를
  관상학적으로 풀어 3~4문장. 예: 「보송한 볼살은 액운을 흡수하는 방패예요. 간식비로 통장은 가벼워져도 귀여움으로
  집사의 스트레스를 액땜해 승진운과 재물운을 불러올 복덩이예요.」
- one_line_advice: 무냥이의 족집게 조언, 집사가 명심할 수발 팁 한 문장

[예외 — 억지로 지어내지 않는다]
- 사진에 동물이 없거나 사람·물건·그림만 있으면 error_code 를 "NOT_ANIMAL" 로.
- 동물은 있지만 너무 흐리거나 어둡거나 작아서 얼굴을 못 보겠으면 "LOW_QUALITY" 로.
- 그때는 나머지 글 칸을 빈 문자열, 숫자를 0 으로 채운다. 문제없으면 error_code 는 "NONE".

[share_card_data — 공유 카드]
모바일 화면 한 장에 들어갈 이미지 엽서용 텍스트다. 글자 수를 엄격히 지킨다.
- card_title: 여덟 자 안쪽 + 끝에 이모지 하나 (예: 태평성대 황제상 👑)
- main_factcheck_short: 두 문장, 합쳐서 예순 자 안쪽

[character_design — 캐릭터화 명세]
이 아이가 「이달의 관상왕」이 되면 사이트 모퉁이를 돌아다니는 2D 캐릭터로 만든다.
- visual_features: 사진에서 **실제로 보이는** 특징을 쉼표로 (털색·무늬 위치·눈 색·귀 모양·표정)
  🛑 무냥이처럼 조선 옷차림 소품 하나를 얹어도 된다(갓·두건 등). 그때도 아이의 무늬는 그대로 둔다
- sprite_concept: 사이트 모퉁이를 돌아다닐 때의 픽셀 아트 콘셉트 한 문장
- motion_keyword: 시그니처 동작 한두 낱말 (예: 둥둥 떠다니기, 냥펀치 날리기, 볼주머니 채우기)"""

PET_SCHEMA = {
    "type": "object",
    "properties": {
        "error_code": {"type": "string", "enum": ["NONE", "NOT_ANIMAL", "LOW_QUALITY"]},
        "pet_species": {"type": "string", "enum": list(SPECIES)},
        "grade": {"type": "string", "enum": list(GRADES)},
        "title": {"type": "string", "description": "관상 타이틀 · 서른 자 안쪽"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "정확히 셋 · #으로 시작 · 띄어쓰기 없이"},
        "stats": {
            "type": "object",
            "properties": {k: {"type": "integer", "description": "%s · 0~100" % v} for k, v in STAT_NAMES.items()},
            "required": list(STAT_NAMES),
        },
        "short_analysis": {"type": "string", "description": "두 문장 한 줄평 · 예순 자 안쪽"},
        "full_analysis": {"type": "string", "description": "보이는 생김새를 짚는 팩폭 분석 · 4~5문장"},
        "synergy_analysis": {"type": "string", "description": "집사와의 시너지 · 재물운 · 액막이 · 힐링 효과 · 3~4문장"},
        "one_line_advice": {"type": "string", "description": "무냥이의 족집게 조언 한 문장"},
        "character_design": {
            "type": "object",
            "properties": {
                "visual_features": {"type": "string", "description": "사진에서 보이는 캐릭터화 특징. 쉼표로 · 백 자 안쪽"},
                "sprite_concept": {"type": "string", "description": "사이트를 돌아다닐 픽셀 아트 콘셉트 한 문장 · 예순 자 안쪽"},
                "motion_keyword": {"type": "string", "description": "시그니처 동작 · 열두 자 안쪽"},
            },
            "required": ["visual_features", "sprite_concept", "motion_keyword"],
        },
        "share_card_data": {
            "type": "object",
            "properties": {
                "card_title": {"type": "string", "description": "여덟 자 안쪽 + 이모지 하나"},
                "main_factcheck_short": {"type": "string", "description": "두 문장 · 예순 자 안쪽"},
            },
            "required": ["card_title", "main_factcheck_short"],
        },
    },
    "required": ["error_code", "pet_species", "grade", "title", "hashtags", "stats", "short_analysis", "full_analysis",
                 "synergy_analysis", "one_line_advice", "character_design", "share_card_data"],
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


def stat_names_for(species: str) -> dict[str, str]:
    """막대·카드에 쓰는 스탯 이름. 돌발 행동력 뒤에 종별 말을 붙인다 (고양이 → 돌발 행동력(야간 우다다))."""
    names = dict(STAT_NAMES)
    w = ACTION_WORD.get(species)
    if w:
        names["action_power"] = "돌발 행동력(%s)" % w
    return names


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    """모델 답을 화면이 믿고 쓸 수 있게 다듬는다.

    🛑 명세 칸(pet_species · grade · hashtags · short/full/synergy_analysis)을 그대로 내보내고,
       화면·공유 카드·명예의 전당이 읽던 옛 칸(summary · personality_factcheck · butler_compatibility ·
       share_card_data.grade_badge/pet_keywords/top_stat_*)도 **같은 값으로** 채워 준다 — 한쪽만 바꾸면 화면이 빈다.
    """
    code = str(d.get("error_code") or "NONE").upper()
    if code in ERRORS:
        return {"error_code": code, "message": ERRORS[code]}
    species = str(d.get("pet_species") or "other").lower()
    if species not in SPECIES:
        species = "other"
    grade = str(d.get("grade") or "A").upper().replace(" ", "")
    if grade not in GRADES:
        grade = "A"
    raw = d.get("stats") if isinstance(d.get("stats"), dict) else {}
    stats = {}
    for k in STAT_NAMES:
        v = raw.get(k, raw.get(STAT_LEGACY_OF[k]))
        m = re.search(r"\d+(?:\.\d+)?", str(v if v is not None else ""))   # 「88점」처럼 와도 숫자만
        stats[k] = max(0, min(100, int(round(float(m.group()))))) if m else 0
    # 🛑 다섯 칸이 전부 0 이면 모델이 칸을 비운 것이다 — 받지 않고 다시 부른다 (2026-09-14 「수치가 안 나와」)
    if not any(stats.values()):
        raise RuntimeError("관상 스탯이 비었다")
    names = stat_names_for(species)
    # 🛑 가장 높은 칸은 **서버가 고른다** — 모델이 적은 이름·숫자와 막대가 어긋나지 않게
    top = max(stats, key=lambda k: stats[k])
    tags = []
    for x in (d.get("hashtags") or []):
        t = str(x or "").replace(" ", "").lstrip("#")
        if t:
            tags.append(_cut(t, 10))
    tags = tags[:3]
    sc = d.get("share_card_data") if isinstance(d.get("share_card_data"), dict) else {}
    short = _cut(d.get("short_analysis"), 80)
    full = _cut(d.get("full_analysis"), 700)
    syn = _cut(d.get("synergy_analysis"), 600)
    out = {
        "error_code": "NONE",
        # 명세 칸
        "pet_species": species,
        "species_word": SPECIES_WORD.get(species, "동물성"),
        "grade": grade,
        "grade_label": GRADES[grade],
        "title": _cut(d.get("title"), 32),
        "hashtags": ["#" + t for t in tags],
        # 🛑 옛 열쇠(butler_control…)도 같은 값으로 싣는다 — 개편 전에 열어 둔 화면은 옛 열쇠를 읽어서 0 이 찍힌다
        "stats": {**stats, **{STAT_LEGACY_OF[k]: v for k, v in stats.items()}},
        "stat_names": {**names, **{STAT_LEGACY_OF[k]: v for k, v in names.items()}},
        "short_analysis": short,
        "full_analysis": full,
        "synergy_analysis": syn,
        "one_line_advice": _cut(d.get("one_line_advice"), 90),
        # 옛 칸 (화면·카드·전당이 읽는다)
        "summary": short,
        "personality_factcheck": full,
        "butler_compatibility": syn,
        "share_card_data": {
            "card_title": _cut(sc.get("card_title"), 12),
            "pet_keywords": tags,
            "main_factcheck_short": _cut(sc.get("main_factcheck_short") or short, 60),
            "top_stat_name": names[top],
            "top_stat_value": stats[top],
            "grade_badge": grade,
        },
    }
    cd = d.get("character_design") if isinstance(d.get("character_design"), dict) else {}
    out["character_design"] = {
        "visual_features": _cut(cd.get("visual_features"), 120),
        "sprite_concept": _cut(cd.get("sprite_concept"), 80),
        "motion_keyword": _cut(cd.get("motion_keyword"), 16),
    }
    if not out["title"] or not out["full_analysis"]:
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
        "systemInstruction": {"parts": [{"text": gw._P("pet3", SYSTEM)}]},
        "contents": [{"role": "user", "parts": [gw._part(shot_b64), {"text": "이 반려동물의 관상을 봐 주세요."}]}],
        # 🛑 thinkingBudget 0 — 생각 토큰이 답 예산을 먹어 글이 잘린다 (gwansang.py 와 같은 설정)
        "generationConfig": {"temperature": 1.0, "maxOutputTokens": 3200,
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
