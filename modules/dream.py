# -*- coding: utf-8 -*-
"""꿈 해몽 — 꿈에서 본 것을 무냥이가 읽는다 (2026-09-13 온해님 기획).

상품은 둘이고, 공유 카드가 하나 붙는다. 정본 목록은 앞단 `dream.js` 다.

| 상품 | 무엇을 받나 | 무엇을 주나 |
|---|---|---|
| `dream_scan` 꿈 스캔 (무료) | 꿈에서 본 것 고르기 + 한 줄 | 등급 · 별명 · 한 줄 팩폭 · 짧은 풀이 |
| `dream_saju` 꿈 사주 (유료) | 꿈 이야기 + 내 사주 | 이 꿈이 내 사주의 어디를 건드렸나 — 항목별 리포트 |

🛑 **사주 상품(`saju_writer`)과 섞지 않는다.** 사주는 생년월일만 보고, 꿈은 손님이 쓴
   글을 본다. 관상을 따로 둔 것과 같은 이유다(`gwansang.py` 머리말).
🛑 **등급은 모델이 고르고, 등급 이름은 여기 표가 붙인다.** 모델에게 이름까지 맡기면
   같은 S 가 「대박 길몽」 「초대박」 「역대급」으로 흩어져 카드마다 말이 달라진다.
🛑 **같은 꿈은 같은 등급이다.** 입력으로 열쇠를 만들어 저장한다. 안 그러면 S 가 나올
   때까지 다시 누르게 되고, 원가가 새고, 등급이 아무 뜻이 없어진다.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from modules import saju_writer

# 🛑 2 — 자리마다 무냥이 한줄평(`mutter`)을 받고 자리를 나눠 준다 (2026-09-13). 옛 저장분은 다시 쓴다
VER = 2

# 🛑 등급 이름표. 공유 카드·화면이 이 이름을 그대로 쓴다
GRADES = {
    "S": "대박 길몽",
    "A": "길몽",
    "B": "반반 꿈",
    "C": "개꿈",
    "D": "조심 꿈",
}

KEYWORDS_MAX = 3        # 고르는 것은 셋까지. 더 받으면 풀이가 목록 읽기가 된다
TEXT_MAX = 300          # 꿈 이야기 글자 수

SYSTEM = """너는 사주 상담 사이트 「로드로그」의 꿈 해몽을 쓴다. 화자는 무냥이라는 고양이 도령이다.
손님은 20~30대 여성이 많다. 지루한 해몽집 말투가 아니라 위트와 팩트폭격으로 쓴다.

[말투]
- 어미는 「~해요」. 「~합니다」는 쓰지 않는다. 「~냥」 말끝과 밈은 써도 된다.
- 고양이 감각으로 비유한다. 볕, 그늘, 발끝, 귀, 문틈, 창가.
- 단정하지 않는다. 「그렇게 읽혀요」.

[꿈을 읽는 법]
- 전통 해몽(물·불·뱀·돼지·똥·이·피·돈·죽음 등)의 일반적인 풀이를 바탕으로 한다.
- 무서운 꿈이라고 흉몽으로 몰지 않는다. 죽음·피·불은 전통적으로 좋게 읽는 경우가 많다.
- 꿈에 나온 **손님의 말을 한 번은 그대로 짚는다.** 그래야 자기 얘기로 읽는다.

[🛑 하지 않는 것]
- 병·임신·사고를 확정하지 않는다. 몸이 걱정되는 꿈이면 「걱정되면 병원에 가 보는 게 먼저예요」.
- 복권·도박·코인을 사라고 권하지 않는다. 당첨 번호나 숫자를 주지 않는다.
- 없는 통계(%·몇 명 중 몇 명)를 지어내지 않는다.
- 외모를 깎아내리지 않는다. 상황과 성향을 웃긴다.
- 이모지·느낌표를 쓰지 않는다.
"""

SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "grade": {"type": "string", "enum": list(GRADES.keys()),
                  "description": "S 대박 길몽 · A 길몽 · B 반반 · C 개꿈 · D 조심하라는 꿈. "
                                 "S 는 정말 드물게 준다"},
        "title": {"type": "string", "description": "이 꿈의 별명. 열여섯 자 안쪽. 재치 있게"},
        "punch": {"type": "string", "description": "무냥이의 한 줄 팩폭. 마흔 자 안쪽. 돌려 말하지 않는다"},
        "read": {"type": "string", "description": "왜 그렇게 읽히는지 두세 문장. 백팔십 자 안쪽"},
        "tip": {"type": "string", "description": "오늘 해 보면 좋은 것 한 가지. 마흔 자 안쪽"},
    },
    "required": ["grade", "title", "punch", "read", "tip"],
}

def _hard_words() -> str:
    """사주 글쓰기 규칙의 「어려운 말」 절을 그대로 빌린다.

    🛑 **따로 베껴 적지 않는다.** 두 곳에 두면 한쪽만 고쳐진다. 처음 시험에서
       「경금 일간」 「술토」 「인성」이 풀이 없이 나왔다 (2026-09-13).
    """
    src = saju_writer.SYSTEM
    a, b = src.find("[어려운 말"), src.find("[본문에")
    return src[a:b].strip() if 0 <= a < b else ""


REPORT_RULES = """
[사주를 엮을 때 — 어기면 못 쓴다]
- 사주 계산은 이미 끝났다. [사주]에 적힌 사실만 쓴다. 개수를 새로 세지 않는다.
- [사주]에 없는 글자·신살·대운을 만들지 않는다. 확실하지 않으면 그 글자를 빼고 쓴다.
- 손님을 이름+님으로 부른다. 이름을 모르면 이름 없이 쓴다. 「당신」은 쓰지 않는다.
- 이모지·느낌표를 쓰지 않는다.
"""


REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "grade": {"type": "string", "enum": list(GRADES.keys())},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nickname": {"type": "string", "description": "이 자리의 제목. 준 자리 이름을 그대로 쓴다"},
                    "fact_bomb": {"type": "string", "description": "뼈 때리는 팩트 폭격"},
                    "meme_analysis": {"type": "string", "description": "꿈 상징과 사주를 엮은 풀이. 일상 장면 하나를 든다"},
                    "funny_solution": {"type": "string", "description": "그래서 무엇을 하면 되는지. 유쾌하게"},
                    "mutter": {"type": "string", "description": "무냥이의 족집게 한줄평. 이 자리를 한 줄로 콕 찌르는 팩폭. 서른 자 안쪽. 느낌표 금지"},
                },
                "required": ["nickname", "fact_bomb", "meme_analysis", "funny_solution", "mutter"],
            },
        },
    },
    "required": ["grade", "sections"],
}


def clean_input(keywords: list[str] | None, text: str | None) -> tuple[list[str], str]:
    """받은 값을 다듬는다. 🛑 둘 다 비었으면 부르지 않는다 — 빈 꿈으로 돈이 나간다."""
    kw = []
    for k in keywords or []:
        k = " ".join(str(k).split())[:20]
        if k and k not in kw:
            kw.append(k)
    kw = kw[:KEYWORDS_MAX]
    t = " ".join(str(text or "").split())[:TEXT_MAX]
    if not kw and not t:
        raise ValueError("꿈에서 본 것을 하나라도 골라 주세요.")
    return kw, t


def key_of(*parts: str) -> str:
    """같은 입력이면 같은 열쇠. 저장 파일 이름으로 쓴다(`saju_writer._SAFE` 에 맞는 16진수)."""
    raw = json.dumps(parts, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


def _loads(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except ValueError:
        # 규격으로 받는데도 앞뒤에 뭐가 붙는 때가 있다 — 중괄호만 떼어 다시 읽는다
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            return json.loads(text[a:b + 1])
        raise


def scan(keywords: list[str], text: str, *, name: str = "") -> dict[str, Any]:
    """꿈 스캔 한 번. 짧은 답이라 한 번에 1원 안쪽이다."""
    lines = []
    if name:
        lines.append("손님 이름: %s (이름+님으로 부른다)" % name[:20])
    if keywords:
        lines.append("꿈에서 본 것: " + ", ".join(keywords))
    if text:
        lines.append("손님이 적은 꿈: " + text)
    user = "\n".join(lines)
    # 🛑 max_tokens 를 인색하게 잡지 않는다 — 짧은 답에 8을 줬다가 빈 답이 온 적이 있다
    #    (CLAUDE.md 「LLM 이 글 없는 답을 돌려줄 때가 있다」). 쓴 만큼만 값이 나간다.
    res = saju_writer._call(saju_writer._P("dream", SYSTEM), user,
                            max_tokens=700, schema=SCAN_SCHEMA)
    d = _loads(res["text"])
    g = str(d.get("grade") or "B").upper()
    if g not in GRADES:
        g = "B"
    return {
        "grade": g,
        "label": GRADES[g],
        "title": str(d.get("title") or "").strip()[:24],
        "punch": str(d.get("punch") or "").strip()[:80],
        "read": str(d.get("read") or "").strip()[:320],
        "tip": str(d.get("tip") or "").strip()[:80],
        "tokens": {"in": res.get("in", 0), "out": res.get("out", 0)},
    }


def read(text: str, saju: dict[str, Any], sections: list[str], *,
         keywords: list[str] | None = None, name: str = "",
         grade: str = "", chars: int = 320) -> dict[str, Any]:
    """꿈 사주 리포트. 꿈 이야기와 사주를 엮어 항목마다 쓴다.

    🛑 **스캔에서 매긴 등급을 넘겨받으면 그대로 쓴다.** 안 넘기면 같은 꿈이 스캔은 A급,
       리포트는 S급으로 따로 나온다 (2026-09-13 첫 시험에서 그랬다).
    """
    secs = [str(x).strip() for x in (sections or []) if str(x).strip()][:12]
    if not secs:
        raise ValueError("볼 자리가 없습니다.")
    fixed = str(grade or "").strip().upper()
    fixed = fixed if fixed in GRADES else ""
    user = (
        ("손님 이름: %s (이름+님으로 부른다)\n\n" % name[:20] if name else "")
        + ("꿈에서 본 것: %s\n" % ", ".join(keywords) if keywords else "")
        + "손님이 적은 꿈:\n%s\n\n[사주]\n%s\n\n" % (text, saju_writer.facts(saju))
        + "[볼 자리 — 순서를 그대로 지키고 하나도 빠뜨리지 마라]\n"
        + "\n".join("%d. %s" % (n + 1, t) for n, t in enumerate(secs))
        + ("\n\n[등급]\n이 꿈은 이미 %s급(%s)으로 매겼다. 이 등급과 어긋나는 말을 하지 않는다."
           % (fixed, GRADES[fixed]) if fixed else "")
        + "\n\n[적는 법]\n"
          "자리 하나에 %d자 안팎. 세 박자로 쓴다 — 팩트폭격 → 찰진 비유 → 유쾌한 반전.\n"
          "🛑 **꿈 상징만 풀면 해몽집이다.** 자리마다 [사주]에 적힌 것 하나를 짚어 "
          "그 꿈이 왜 **이 사람에게** 그렇게 읽히는지 잇는다.\n"
          "🛑 [사주]에 없는 글자·개수를 지어내지 않는다.\n"
          "🛑 채우려고 같은 말을 돌려 쓰지 않는다. 자리마다 다른 데를 본다." % chars
    )
    system = saju_writer._P("dream", SYSTEM) + REPORT_RULES + "\n" + _hard_words()
    res = saju_writer._call(system, user,
                            max_tokens=max(1600, chars * len(secs) * 3),
                            schema=REPORT_SCHEMA)
    d = _loads(res["text"])
    got = d.get("sections") or []
    parts, blocks = [], []
    for i, t in enumerate(secs):
        s = got[i] if i < len(got) and isinstance(got[i], dict) else {}
        b = {
            "title": t,
            "fact": str(s.get("fact_bomb") or "").strip(),
            "body": str(s.get("meme_analysis") or "").strip(),
            "tip": str(s.get("funny_solution") or "").strip(),
            "mutter": str(s.get("mutter") or "").strip()[:60],
        }
        body = "\n\n".join(x for x in (b["fact"], b["body"], b["tip"]) if x)
        if body:
            parts.append("## %s\n%s" % (t, body))
            # 🛑 **자리를 나눠서도 준다** (2026-09-13 온해님 「주제별 독립된 카드」). 화면이
            #    팩폭·풀이·처방·한줄평을 따로 꾸미려면 한 덩어리 글로는 못 가른다
            blocks.append(b)
    if not parts:
        raise RuntimeError("꿈 리포트가 비었다")
    g = fixed or str(d.get("grade") or "B").upper()
    return {"grade": g if g in GRADES else "B", "text": "\n\n".join(parts), "blocks": blocks,
            "tokens": {"in": res.get("in", 0), "out": res.get("out", 0)}}


def veil_blocks(blocks: list[dict[str, Any]] | None, paid: bool) -> list[dict[str, Any]]:
    """자리 목록도 복채 전에는 첫 자리만. 🛑 서버에서 자른다 (아래 `veil` 과 같은 이유)."""
    blocks = [b for b in (blocks or []) if isinstance(b, dict)]
    return blocks if paid else blocks[:1]


def veil(text: str, paid: bool) -> str:
    """복채 전에는 **첫 자리만** 준다.

    🛑 **서버에서 자른다.** 화면에서만 흐리면 개발자 도구로 다 보인다 (관상 `_gwan_veil` 과 같다).
    """
    if paid:
        return text
    blocks = [b for b in str(text or "").split("\n## ") if b.strip()]
    if not blocks:
        return ""
    first = blocks[0]
    return first if first.startswith("## ") else "## " + first
