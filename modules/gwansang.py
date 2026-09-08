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
from typing import Any

import httpx

from modules.saju_writer import MODEL, _URL, api_key

TIMEOUT = 120
MAX_BYTES = 1_500_000          # 브라우저에서 긴 변 768px 로 줄여 보내면 200KB 안쪽이다

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
ASK = {
    "face_first": "첫인상만 짧게 봐 주세요. 이 얼굴이 처음 보는 사람에게 어떻게 읽히는지 "
                  "**세 문장 안쪽**으로. 두드러지는 데 한 곳만 짚어 주세요.",
    "face_me": "이마·눈매·코·입·턱을 **하나씩** 짚어 주세요. 각각 무엇이 그렇게 보이는지와, "
               "그래서 어떤 사람으로 읽히는지 적어 주세요. 마지막에 전체 균형을 한 문단으로 묶어 주세요.",
    "face_you": "이 얼굴의 주인이 **어떤 사람인지** 봐 주세요. 특히 **가까운 사람을 어떻게 대하는지** — "
                "먼저 다가서는 쪽인지, 재는 쪽인지, 마음을 어디까지 보이는지. "
                "🛑 손님이 이 사람과 어떤 사이인지는 모른다. 단정하지 말고 「그렇게 보여요」로 적는다.",
    "face_love": "연애 쪽으로 봐 주세요. **어떤 사람에게 끌리는 얼굴인지**와 **어떤 사람이 다가오는 "
                 "얼굴인지**를 나눠서. 그리고 연애에서 되풀이되기 쉬운 버릇 하나를 짚어 주세요.",
    "face_money": "재물 쪽으로 봐 주세요. **쥐는 힘**(모으는 쪽인지 굴리는 쪽인지)과 "
                  "**새는 자리**(어디서 빠져나가기 쉬운지)를 나눠서 적어 주세요.",
    "face_all": "전체를 다 봐 주세요. 이마·눈매·코·입·턱을 하나씩 짚고, 연애·재물·사람 관계까지 "
                "이어서 적어 주세요. 마지막에 **지금 해 두면 달라지는 것** 하나로 닫아 주세요.",
    "face_pair": "사진이 **두 장**입니다. 첫째가 손님, 둘째가 상대예요. 두 얼굴을 견주어 "
                 "**어디서 맞고 어디서 어긋나는지** 봐 주세요. 누가 더 낫다는 식으로 쓰지 마세요.",
    "face_king": "**그릇의 크기**를 봐 주세요. 이 얼굴이 어디까지 갈 사람으로 읽히는지, "
                 "무엇을 맡았을 때 힘이 나는 얼굴인지. 🛑 「왕이 될 상이다/아니다」로 "
                 "잘라 말하지 말고, **어떤 자리에서 빛나는 얼굴인지**로 답해 주세요.",
}
ASK_DEFAULT = "이 얼굴을 관상으로 봐 주세요. 두드러지는 데 세 곳을 짚어 주세요."


def _part(b64: str) -> dict[str, Any]:
    return {"inline_data": {"mime_type": "image/jpeg", "data": b64}}


def read_face(product: str, shots: list[str], *, name: str = "",
              chars: int = 900, model: str | None = None) -> dict[str, Any]:
    """사진(base64 jpeg) 을 보고 관상 글을 쓴다. 🛑 사진은 어디에도 저장하지 않는다."""
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    if not shots:
        raise ValueError("사진이 없습니다.")
    for b in shots:
        if len(b) > MAX_BYTES * 4 // 3:
            raise ValueError("사진이 너무 큽니다.")

    ask = ASK.get(product, ASK_DEFAULT)
    if name:
        ask += "\n손님 이름은 「%s」예요. 이름+님으로 불러 주세요." % name[:20]
    ask += "\n\n분량은 %d자 안팎으로." % chars

    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [_part(b) for b in shots] + [{"text": ask}]}],
        # 🛑 thinkingBudget 을 0 으로 안 두면 **생각 토큰이 답 예산을 다 먹고 글이 잘린다.**
        #    2026-09-09 에 실제로 27토큰(한 문장 반)에서 끊겼다. saju_writer 와 같은 설정이다.
        "generationConfig": {"temperature": 1.0, "maxOutputTokens": max(700, chars * 2),
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    url = (_URL % (model or MODEL)) + "?key=" + key

    last = None
    for _ in range(2):
        try:
            r = httpx.post(url, json=body, timeout=TIMEOUT)
            j = r.json()
            if "candidates" in j:
                c = j["candidates"][0]
                parts = (c.get("content") or {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    u = j.get("usageMetadata") or {}
                    return {"text": text, "model": model or MODEL,
                            "tokens": {"in": u.get("promptTokenCount"),
                                       "out": u.get("candidatesTokenCount")}}
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
