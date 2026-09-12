# -*- coding: utf-8 -*-
"""관상 — 얼굴 사진을 보고 관멍이가 짚어 준다 (2026-09-09).

🛑 **사진을 저장하지 않는다.** 받은 그대로 Gemini 로 넘기고 그 자리에서 버린다.
   파일을 만들지 않으므로 디스크에 남을 일이 없다 — 그래서 `UploadFile`(multipart) 이
   아니라 **base64 JSON 본문**으로 받는다. multipart 는 크면 임시 파일로 떨어진다.
🛑 남기는 것은 **해석한 글**뿐이다.

🛑 **유료 티어라야 한다.** Google 약관상 무료(Unpaid) 는 보낸 것을 제품 개선에 쓰고
   사람이 읽어 볼 수 있다. 우리 키는 결제 계정에 붙어 있다 — 키를 갈아 끼울 때
   **결제 연결부터 확인**할 것. (docs/관상_준비.md)

화자는 무냥이가 아니라 **관멍이**다. 사주는 무냥이, 관상은 관멍이.
"""
from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from modules.saju_writer import MODEL, _URL, api_key

TIMEOUT = 120
MAX_BYTES = 1_500_000          # 브라우저에서 긴 변 768px 로 줄여 보내면 200KB 안쪽이다

def _P(key: str, fallback: str) -> str:
    """관리자 화면에서 고친 말투가 있으면 그것을 쓴다 (2026-09-11)."""
    try:
        from modules import prompts as _pr
        return _pr.get(key) or fallback
    except Exception:                                # noqa: BLE001
        return fallback


SYSTEM = """너는 사주 상담 사이트 「로드로그」의 관상을 본다. 화자는 **관멍이**라는 강아지 도령이다.
갓을 쓰고 돋보기를 든 어린 진돗개다. 사주는 무냥이가 보고, 얼굴은 네가 본다.

[말투]
- 존댓말. 「~해요」가 기본이되 종결을 섞는다: ~예요 / ~거든요 / ~더라고요 / ~죠.
- 손님을 「지현님」처럼 이름+님으로 부른다. 이름을 안 주면 부르지 않는다.
- 단정하지 않는다. 「그렇게 보여요」. 아는 것과 본 것을 나눈다.
- 반말·훈계·예언 말투를 쓰지 않는다.

[관상을 보는 법]
사진에서 **실제로 보이는 것**만 말한다. 이마·눈매·코·입·턱·얼굴 균형 중에서
그 사람에게 두드러지는 데를 골라 짚는다.
- 「이마가 둥글고 트여 있어요」처럼 **무엇이 그렇게 보이는지 먼저** 말하고,
  그래서 어떤 사람으로 읽히는지 이어 붙인다
- 일상에서 뭘로 나타나는지 **장면 하나**를 든다.
  「먼저 말 거는 대신 한 번 더 보고 나서 움직이는」 같은 것

[말하는 결 — 팩트폭격 (2026-09-10 온해님이 정하심)]
손님은 20~30대 여성이다. 지루한 사주 풀이 말고 **위트와 팩트폭격**으로 간다.
화자는 그대로 **관멍이**다. 관멍이가 팩트를 때린다.
한 항목을 이 세 박자로 쓴다.
🛑 **박자는 뼈대이지 문단 수가 아니다** (2026-09-12 실측). 아래 [적는 법]이 시키는
   문단 수만큼 **박자를 펴서** 쓴다. 세 문단으로 끝내면 값을 치른 손님이 허전해한다.
   — 「한 자리 1,200자」를 시켰는데 260자로 끝나던 것이 이 때문이었다.
  ① **팩트폭격** — 돌려 말하지 않는다. 뼈 때리는 문장으로 연다.
     길게 쓸 때는 **무엇이 보이나 → 그래서 어떤 사람으로 읽히나**로 나눈다.
  ② **찰진 비유** — 손님이 자기 얘기라고 느낄 장면.
     「장바구니에 담아 두고 결제는 안 눌러요」 「읽씹 당하고도 프로필은 확인해요」
     🛑 길게 쓸 때는 **장면을 여럿** 든다. 하나로 끝내지 않는다.
  ③ **유쾌한 반전** — 그래서 어떻게 하면 되는지로 뒤집어 준다.
     길게 쓸 때는 **하면 되는 것과 하면 안 되는 것**을 나눠 적는다.
🛑 **외모 비하가 아니라 상황·성향을 웃긴다** (온해님 지침). 얼굴·몸을 두고 웃지 않는다.
🛑 **없는 숫자를 지어내지 않는다.** %는 우리가 따로 계산해서 넣어 준다.

[🛑 하지 않는 것 — 하나라도 어기면 다시 쓴다]
1. **병·건강을 말하지 않는다.** 얼굴을 보고 아픈 데를 짚지 않는다. 의료가 아니다.
2. 미모를 평가하지 않는다. 예쁘다·잘생겼다·못생겼다를 쓰지 않는다.
3. 나이·인종·출신을 짐작해 말하지 않는다.
4. 사진 속 인물이 누구인지 알아내려 하지 않는다.
5. 이모지·느낌표를 쓰지 않는다.
6. 좋은 말로 훈훈하게 맺지 않는다.
7. 대구를 만들지 않는다. 「A하면 B하고, C하면 D해요」처럼 앞뒤가 딱 맞는 문장 금지.

[어려운 말]
손님은 관상을 모른다. **관상 용어를 홀로 쓰지 않는다.**
❌ 인당이 넓어  ✅ 눈썹 사이(인당)가 넓어
아예 쓰지 않는 말: 관록궁·명궁·재백궁·천창·지고·오악·십이궁

[사진이 얼굴이 아니면]
사람 얼굴이 아니거나 너무 어두워 못 보겠으면, **억지로 지어내지 말고**
「이 사진으로는 보기 어려워요」라고 한 줄로 말한다."""

# 상품마다 무엇을 볼지. 🛑 새 상품을 만들면 여기에 한 줄 넣는다 — 없으면 기본으로 떨어진다
# 🛑 **상품마다 볼 자리를 정해 둔다** (2026-09-09 온해님 「해설이 너무 짧아」).
#    전에는 「첫인상만 짧게, 세 문장 안쪽으로」라고 스스로 시켜서 980원짜리가 200자로 나왔다.
#    사주 900원짜리(수호신)가 2,450자인데 그건 도둑이다.
#
# 🛑 **늘리는 법은 자리를 나누는 것**이지 같은 말을 돌려쓰는 게 아니다.
#    얼굴에서 실제로 볼 수 있는 데를 하나씩 짚으면 억지 없이 길어진다.
#    자리 목록은 `roadlog-saju/gwansang.js` 의 `sections` 가 정본이고, 앞단이 보내 준다.

ASK_HEAD = {
    "face_first": "처음 보는 사람에게 이 얼굴이 **다가가기 쉬운 얼굴로 읽히는지, 도도해 "
                  "보이는지** 봐 주세요. 겉으로 보이는 것과 다른 **반전**이 있으면 그것도 짚어 주세요.",
    "face_me": "이 얼굴에서 **복이 앉은 자리**를 찾아 주세요. 이목구비마다 무엇을 맡고 있는지 "
               "보고, **연애와 재물 쪽으로 그 자리를 어떻게 쓰면 좋은지**까지 적어 주세요. "
               "🛑 **없는 점을 지어내지 마세요.** 사진에 실제로 보이는 것만 짚습니다.",
    "face_you": "이 얼굴의 주인이 어떤 사람인지, 특히 가까운 사람을 어떻게 대하는지 봐 주세요. "
                "🛑 손님이 이 사람과 어떤 사이인지는 모른다. 단정하지 말고 「그렇게 보여요」로 적는다.",
    "face_love": "연애 쪽으로 봐 주세요. **빠지는 속도와 식는 속도**를 나눠서 — 금방 빠지는 "
                 "얼굴인지 천천히 데워지는 얼굴인지, 식을 때 어느 자리가 먼저 바뀌는지.",
    "face_money": "재물 쪽으로 봐 주세요. 쥐는 힘과 새는 자리를 나눠서.",
    "face_all": "이 얼굴을 전부 봐 주세요. 자리를 하나씩 짚고 연애·재물·사람 관계까지 이어서.",
    "face_pair": "사진이 **두 장**입니다. 첫째가 손님, 둘째가 상대예요. "
                 "두 얼굴을 견주어 어디서 맞고 어디서 어긋나는지 봐 주세요. "
                 "🛑 누가 더 낫다는 식으로 쓰지 마세요.",
    "face_king": "이 얼굴의 **그릇**을 봐 주세요. "
                 "🛑 「왕이 될 상이다/아니다」로 잘라 말하지 말고, "
                 "어떤 자리에서 빛나는 얼굴인지로 답해 주세요.",
    "face_flag": "이 얼굴을 **믿어도 되는지**로 봐 주세요. 말과 행동이 어긋나기 쉬운 자리, 한눈팔기 쉬운 자리, 화났을 때 나오는 얼굴을 나눠서. 🛑 손님이 이 사람과 어떤 사이인지는 모른다. 단정하지 말고 「그렇게 보여요」로 적는다.",
    "face_read": "이 얼굴의 **겉과 속이 얼마나 다른지** 봐 주세요. 웃을 때 눈이 같이 웃는지, 입꼬리와 눈꼬리가 어긋나는지를 나눠서. 🛑 거짓말쟁이라고 단정하지 마세요. 「이 자리에서는 속을 덜 보여요」까지만.",
    "face_fix": "🛑 **시술을 권하지도 말리지도 마세요. 의료 조언이 아닙니다.** 「코를 세우세요」 「하세요」 「하지 마세요」를 쓰지 마세요. 지금 얼굴에서 **어느 자리가 무엇을 맡고 있는지**만 봐 주세요. 손대면 그 자리가 맡던 것이 달라진다는 것까지가 우리가 말할 수 있는 전부예요. 고를 사람은 손님입니다.",
    "face_luck": "**한 번에 크게 들어오는 얼굴인지**로 봐 주세요. 광대와 점이 앉은 자리를 나눠서. 🛑 「당첨된다」고 말하지 마세요. 도박을 권하지도 마세요. 「크게 들어오는 결인지, 쌓아 가는 결인지」까지만.",
}
ASK_DEFAULT = "이 얼굴을 관상으로 봐 주세요."


ASK_SYSTEM = """너는 관멍이다. 손님 얼굴을 이미 한 번 봐 주었고, 지금은 그 결과를 두고
손님이 더 묻는 것에 답한다.

[가장 중요]
🛑 **아래 [관멍이가 본 것] 에 적힌 것만 쓴다.** 사진은 지금 없다. 새로 보지 못한다.
   거기 없는 것을 물으면 「그건 사진에서 못 본 자리예요」라고 솔직히 말한다.
🛑 사주를 보지 마라. 너는 얼굴만 본다.

[말투]
- 존댓말. 「~해요」가 기본. 손님을 이름+님으로 부른다(이름을 주면).
- 팩트폭격 세 박자로 간다 — ① 뼈 때리는 한 줄 ② 찰진 비유 ③ 유쾌한 반전.
- 이모지·느낌표를 쓰지 않는다.

[🛑 재미있어야 한다 (2026-09-11 온해님)]
**채팅하면서 재미가 있어야 손님이 등불을 또 쓴다.** 한 번 묻고 「그렇군요」로
끝나면 두 번째 물음이 없다.
- **첫 문장을 후려친다.** 「~일 수 있어요」로 시작하면 그 대화는 거기서 끝난다.
- **손님이 실제로 하고 있을 짓을 그린다.** 거울 앞에서 각도 재기, 셀카 마흔 장 찍고
  두 장 남기기. 「어떻게 알았지」 하고 웃어야 다음 물음이 나온다.
- 밈·유행어를 써도 된다. 「~멍」 말끝도 된다.
- 마지막은 오늘 당장 할 수 있는 한 가지로 닫는다. 훈계 말고 행동으로.
🛑 웃기는 것과 얼버무리는 것은 다르다. 답은 첫 문장에 있어야 한다.

[길이]
세 문단 안쪽. 400자 안팎. 물은 것에만 답하고 딴 데로 새지 않는다.

[🛑 하지 않는 것]
1. 병·건강을 말하지 않는다. 의료가 아니다.
2. 미모를 평가하지 않는다.
3. 없는 것을 지어내지 않는다."""


def answer(name: str, seen: str, question: str, *, model: str | None = None) -> dict[str, Any]:
    """관상 결과를 두고 더 묻는 것에 답한다 (2026-09-11).

    🛑 사진을 다시 보지 않는다 — 저장하지 않기 때문이다. **써 둔 글**만 재료로 쓴다.
    """
    q = " ".join(str(question or "").split())
    if not q:
        raise ValueError("질문이 비었다")
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    user = ("손님 이름: %s%s%s[관멍이가 본 것]%s%s%s%s[손님이 묻는 것]%s%s"
            % (name or "손님", chr(10), chr(10), chr(10),
               str(seen or "")[:4000], chr(10), chr(10), chr(10), q[:400]))
    body = {
        "systemInstruction": {"parts": [{"text": _P("gwan_ask", ASK_SYSTEM)}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 1.0, "maxOutputTokens": 900,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    r = httpx.post((_URL % (model or MODEL)) + "?key=" + key, json=body, timeout=TIMEOUT)
    j = r.json()
    if "candidates" not in j:
        raise RuntimeError(str(j)[:200])
    parts = (j["candidates"][0].get("content") or {}).get("parts") or []
    u = j.get("usageMetadata", {})
    tin = u.get("promptTokenCount", 0)
    tout = u.get("candidatesTokenCount", 0)
    # 🛑 얼마나 썼는지 적어 둔다 (2026-09-11). 관상 대화도 같은 지갑에서 나간다
    try:
        from modules import apicost
        apicost.note(tin, tout)
    except Exception:                                # noqa: BLE001
        pass
    return {"text": "".join(p.get("text", "") for p in parts).strip(),
            "in": tin, "out": tout}


def _part(b64: str) -> dict[str, Any]:
    return {"inline_data": {"mime_type": "image/jpeg", "data": b64}}


# ── 사진 점검 ────────────────────────────────────────
# 🛑 **해석하기 전에 무엇이 안 보이는지 먼저 말한다** (2026-09-09 온해님 지시).
#    그전에는 사진이 어떻든 관멍이가 무조건 답을 냈다. 이마가 가려졌는데도
#    이마 얘기를 하면 손님은 「돈 냈는데 엉뚱한 소리」로 읽는다.
#    가려진 데를 먼저 말하고, **그걸 알고도 볼지** 손님이 정하게 한다.
#
# 🛑 여기서 관상을 보지 않는다. 출력이 짧아 한 번에 1원 안팎이다.

LOOK_SYSTEM = """너는 얼굴 사진이 관상을 보기에 쓸 만한지 살피는 사람이다.
관상을 보지 마라. 무엇이 보이고 무엇이 안 보이는지만 말한다.

[내놓는 것 — JSON 하나만. 다른 말은 쓰지 마라]
{"good": true, "miss": ["이마"], "say": "…"}

  good  이대로 봐도 괜찮으면 true, 다시 올리는 게 나으면 false
  miss  잘 안 보이는 자리만 골라 담는다. 쓸 수 있는 말:
        이마 · 눈매 · 눈썹 · 코 · 입 · 턱 · 광대 · 귀 · 얼굴 윤곽
        다 잘 보이면 빈 배열
  say   손님에게 할 한두 문장. 마흔 자 안쪽

[say 를 쓰는 법]
  · 무냥이 말투. 「~해요」. 이모지·느낌표 금지
  · 다 보이면: 「잘 보여요. 이대로 봐 드릴게요.」처럼 짧게
  · 가려졌으면: 무엇이 왜 안 보이는지. 「앞머리에 이마가 가려서 그 자리는 흐리게 봐야 해요.」
  · 🛑 다시 올리라고 명령하지 마라. 사실만 말한다 — 정하는 건 손님이다
  · 🛑 얼굴 생김새를 평하지 마라. 잘생겼다·못생겼다 같은 말 금지

[good 을 false 로 하는 때]
  · 얼굴이 아예 없거나 너무 작아 이목구비를 못 알아볼 때
  · 절반 넘게 가려졌을 때 (마스크·손·심한 역광)
  그 밖에는 true 로 두고 miss 에만 적는다. 조금 가린 걸로 막지 마라."""


def look_shot(shots: list[str], *, model: str | None = None) -> dict[str, Any]:
    """사진을 훑고 {good, miss, say} 를 돌려준다. 🛑 관상은 보지 않는다."""
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    if not shots:
        raise ValueError("사진이 없습니다.")

    body = {
        "systemInstruction": {"parts": [{"text": LOOK_SYSTEM}]},
        "contents": [{"role": "user", "parts": [_part(b) for b in shots]
                      + [{"text": "이 사진이 관상을 보기에 쓸 만한지 살펴 주세요."}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 400,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    r = httpx.post((_URL % (model or MODEL)) + "?key=" + key, json=body, timeout=TIMEOUT)
    j = r.json()
    if "candidates" not in j:
        raise RuntimeError(str(j)[:200])
    parts = (j["candidates"][0].get("content") or {}).get("parts") or []
    txt = "".join(p.get("text", "") for p in parts).strip()
    i, k = txt.find("{"), txt.rfind("}")
    if i < 0 or k <= i:
        return {"good": True, "miss": [], "say": ""}
    try:
        got = json.loads(txt[i:k + 1])
    except Exception:                                 # noqa: BLE001
        return {"good": True, "miss": [], "say": ""}
    miss = [str(x)[:12] for x in (got.get("miss") or [])][:6]
    return {"good": bool(got.get("good", True)), "miss": miss,
            "say": " ".join(str(got.get("say") or "").split())[:80]}


# 🛑 **관상도 규격으로 받는다** (2026-09-10 온해님).
#    자리를 몇 개 쓰라고 부탁하면 빠뜨린다 — 그래서 개수를 세어 다시 시키는
#    뒤처리가 붙어 있었다. 배열 규격을 주면 모델이 개수를 어길 수 없다.
#    칸 이름은 온해님이 주신 그대로다.
FACE_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nickname": {"type": "string",
                                 "description": "이 자리의 제목. 준 자리 이름을 그대로 쓰거나 더 재치 있게"},
                    "fact_bomb": {"type": "string",
                                  "description": "뼈 때리는 팩트 폭격. 사진에서 보이는 것을 돌려 말하지 않는다"},
                    "meme_analysis": {"type": "string",
                                      "description": "밈과 유머를 섞은 성향 분석. 일상 장면 하나를 든다"},
                    "funny_solution": {"type": "string",
                                       "description": "유쾌하고 엉뚱한 대안. 그래서 어떻게 하면 되는지"},
                },
                "required": ["nickname", "fact_bomb", "meme_analysis", "funny_solution"],
            },
        },
    },
    "required": ["sections"],
}


def _weave(data, secs):
    """규격으로 받은 자리들을 화면이 읽는 평문으로 잇는다.

    🛑 화면(`main.js`)은 `## 제목` 으로 나뉜 평문을 그린다. 여기서 JSON 을
       그대로 내보내면 관상 화면이 통째로 깨진다.
    """
    rows = (data or {}).get("sections") or []
    out = []
    for i, r in enumerate(rows):
        title = str(r.get("nickname") or (secs[i] if i < len(secs) else "")).strip()
        body = [str(r.get(k) or "").strip()
                for k in ("fact_bomb", "meme_analysis", "funny_solution")]
        body = [x for x in body if x]
        if not body:
            continue
        out.append("## " + title + chr(10) + chr(10) + (chr(10) + chr(10)).join(body))
    return (chr(10) + chr(10)).join(out)


def _para_note(chars: int) -> str:
    """한 자리를 몇 문단으로 펼지. 🛑 **글자 수만 시키면 안 늘어난다** (2026-09-12 실측).

    세 박자(① 팩트폭격 ② 찰진 비유 ③ 유쾌한 반전)가 그대로 **세 문단**이 되어 버려서,
    「1,200자 안팎」 을 시켜도 자리마다 260자에서 멈췄다. 박자를 **펴서** 쓰게 한다.
    """
    if chars >= 1600:
        return ("🛑 **한 자리를 여덟에서 열 문단으로 편다.** 세 박자를 넓게 벌려 쓴다 —\n"
                "   ① 팩트폭격에 두세 문단(무엇이 보이나 · 그래서 어떤 사람으로 읽히나)\n"
                "   ② 찰진 비유에 서너 문단(**장면을 여럿** 든다. 하나로 끝내지 마라)\n"
                "   ③ 유쾌한 반전에 두세 문단(무엇을 하면 되나 · 하면 안 되는 것)\n")
    if chars >= 1400:
        return ("🛑 **한 자리를 예닐곱 문단으로 편다.** 세 박자를 벌려 쓴다 —\n"
                "   ①에 둘 · ②에 **장면 두셋** · ③에 둘.\n")
    if chars >= 1200:
        return ("🛑 **한 자리를 다섯에서 여섯 문단으로 편다.** ②에 장면을 **둘 이상** 든다.\n")
    return "🛑 **한 자리를 네 문단 정도로** 쓴다.\n"


def read_face(product: str, shots: list[str], *, name: str = "",
              sections: list[str] | None = None,
              chars: int = 260, model: str | None = None) -> dict[str, Any]:
    """사진(base64 jpeg) 을 보고 관상 글을 쓴다. 🛑 사진은 어디에도 저장하지 않는다."""
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    if not shots:
        raise ValueError("사진이 없습니다.")
    for b in shots:
        if len(b) > MAX_BYTES * 4 // 3:
            raise ValueError("사진이 너무 큽니다.")

    ask = ASK_HEAD.get(product, ASK_DEFAULT)
    if name:
        ask += "\n손님 이름은 「%s」예요. 이름+님으로 불러 주세요." % name[:20]
    secs = [str(x).strip() for x in (sections or []) if str(x).strip()][:20]
    if secs:
        ask += ("\n\n[볼 자리 — 순서를 그대로 지키고 하나도 빠뜨리지 마라]\n"
                + "\n".join("%d. %s" % (n + 1, t) for n, t in enumerate(secs))
                + "\n\n[적는 법]\n"
                "자리마다 **소제목을 그대로 쓰고** 줄을 바꿔 본문을 쓴다.\n"
                "  ## 소제목\n  본문\n\n"
                "자리 하나에 **%d자 안팎**. 전체는 %d자쯤 된다.\n" % (chars, chars * len(secs))
                # 🛑 **문단 수를 같이 정해 줘야 길이가 따라온다** (2026-09-12 실측).
                #    「1,200자 안팎」 만 시켰더니 자리마다 **235~279자**가 나왔다.
                #    세 박자(팩트→비유→반전)가 곧 **세 문단**이라, 구조가 길이를 이긴다.
                #    사주(`saju_writer._length_note`)는 문단 수까지 정해 준다 — 같게 맞춘다.
                #    🛑 재시도(floor 55%)로는 못 고친다. 세 번 다시 써도 구조가 같아서
                #       똑같이 짧게 나오고 원가만 세 배 든다.
                + _para_note(chars)
                + "🛑 **채우려고 같은 말을 돌려 쓰지 마라.** 자리마다 사진에서 **다른 데**를 본다.\n"
                  "🛑 사진에서 그 자리가 잘 안 보이면 **안 보인다고 적고 넘어간다.** "
                  "지어내는 것보다 낫다.\n"
                  "🛑 자리마다 **일상에서 뭘로 나타나는지 장면 하나**를 든다. "
                  "그게 없으면 손님은 자기 얘기로 안 읽는다.")
    else:
        ask += "\n\n분량은 %d자 안팎으로." % (chars * 5)

    body = {
        # 🛑 말투는 관리자 화면에서 고칠 수 있다 (modules/prompts.py)
        "systemInstruction": {"parts": [{"text": _P("gwan", SYSTEM)}]},
        "contents": [{"role": "user", "parts": [_part(b) for b in shots] + [{"text": ask}]}],
        # 🛑 thinkingBudget 을 0 으로 안 두면 **생각 토큰이 답 예산을 다 먹고 글이 잘린다.**
        #    2026-09-09 에 실제로 27토큰(한 문장 반)에서 끊겼다. saju_writer 와 같은 설정이다.
        # 🛑 예산이 모자라면 마지막 자리가 통째로 잘린다. 항목 수만큼 잡는다
        "generationConfig": {"temperature": 1.0,
                             "maxOutputTokens": max(900, chars * max(1, len(secs)) * 3),
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    # 🛑 **자리가 있으면 규격으로 받는다** (2026-09-10 온해님).
    #    부탁하면 자리를 빠뜨린다. 배열 규격을 주면 모델이 개수를 어길 수 없다.
    if secs:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = FACE_SCHEMA
    url = (_URL % (model or MODEL)) + "?key=" + key

    # 🛑 **짧게 나오면 한 번 더 쓰게 한다** (2026-09-09).
    #    980원짜리가 200자로 나온 적이 있다. 길이는 눈으로 확인할 방법이 없어서
    #    (사람 얼굴 사진이 있어야 시험이 된다) 코드가 스스로 잰다.
    #    🛑 「이 사진으로는 보기 어려워요」처럼 **물러선 답은 다시 시키지 않는다.**
    #       사진이 나쁜 것이지 글이 짧은 게 아니다.
    want = chars * max(1, len(secs)) if secs else chars * 5
    floor = int(want * 0.55)

    last = None
    tin = tout = 0
    for turn in range(3):
        try:
            r = httpx.post(url, json=body, timeout=TIMEOUT)
            j = r.json()
            if "candidates" in j:
                c = j["candidates"][0]
                parts = (c.get("content") or {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts).strip()
                # 🛑 규격으로 받았으면 **화면이 읽는 평문으로 잇는다.**
                #    화면은 `## 제목` 으로 나뉜 글을 그린다 — JSON 을 그대로
                #    내보내면 관상 화면이 통째로 깨진다.
                if secs and text.lstrip().startswith("{"):
                    try:
                        text = _weave(json.loads(text), secs) or text
                    except Exception:            # noqa: BLE001
                        pass                     # 못 읽으면 받은 그대로 쓴다
                if text:
                    u = j.get("usageMetadata") or {}
                    _i = u.get("promptTokenCount") or 0
                    _o = u.get("candidatesTokenCount") or 0
                    tin += _i
                    tout += _o
                    try:
                        from modules import apicost
                        apicost.note(_i, _o)
                    except Exception:                # noqa: BLE001
                        pass
                    plain = len(text.replace(" ", "").replace("\n", ""))
                    short = plain < floor and len(text) > 60 and turn < 2
                    if short and secs:
                        # 자리를 몇 개나 빠뜨렸는지 짚어서 다시 시킨다
                        got = text.count("## ")
                        body["contents"][0]["parts"][-1] = {"text": ask + (
                            "\n\n[🛑 다시 쓴다]\n"
                            "방금 쓴 글이 **%d자**였다. **%d자**는 되어야 한다.\n"
                            "소제목을 %d개 썼는데 **%d개**를 써야 한다.\n"
                            "빠뜨린 자리를 채우고, 자리마다 **보이는 것 + 그래서 어떤 사람인지 + "
                            "일상 장면 하나**를 다 적어라.\n"
                            "🛑 같은 말을 늘려 쓰지 마라. 사진에서 아직 안 본 데를 봐라."
                            % (plain, want, got, len(secs)))}
                        last = "짧아서 다시 (%d자)" % plain
                        continue
                    return {"text": text, "model": model or MODEL,
                            "tokens": {"in": tin, "out": tout},
                            "chars": plain, "want": want, "retried": turn}
                last = "빈 답 (%s)" % c.get("finishReason", "")
            else:
                last = str(j.get("error", {}).get("message", j))[:200]
        except Exception as e:                       # noqa: BLE001
            last = str(e)[:200]
    raise RuntimeError("관상을 읽지 못했다: %s" % last)


def check_jpeg(raw: str) -> str:
    """data URL 을 벗기고 jpeg 인지 본다. base64 문자열을 돌려준다."""
    b64 = raw.split(",", 1)[1] if raw.startswith("data:") else raw
    try:
        data = base64.b64decode(b64, validate=True)
    except Exception:
        raise ValueError("사진을 읽지 못했습니다.")
    if not data:
        raise ValueError("사진이 비어 있습니다.")
    if len(data) > MAX_BYTES:
        raise ValueError("사진이 너무 큽니다.")
    if data[:3] != bytes((0xFF, 0xD8, 0xFF)):
        raise ValueError("jpg 로 보내 주세요.")
    return b64
