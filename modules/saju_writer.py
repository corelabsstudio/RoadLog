# -*- coding: utf-8 -*-
"""결과지 문장을 모델에게 맡긴다.

왜 이걸 만들었나
----------------
문장을 코드에 박아 두면 같은 십성인 사람은 언제나 같은 글을 받는다.
두 번만 봐도 기계가 찍어 낸 티가 난다. 2026-09-07 에 온해님이 그 점을
지적했고, 폭스바니 결과지를 열어 보니 그쪽은 매번 새로 쓰고 있었다.

무엇을 맡기고 무엇을 안 맡기나
------------------------------
**계산은 우리가 한다.** 원국·십성·대운·신살은 이미 프론트가 뽑아 놓았고,
모델에는 그 값을 문장으로 옮기는 일만 시킨다. 사주를 세는 일을 맡기면
틀린다 — 실제로 첫 시안에서 비겁 2 개를 「셋이나」라고 썼다.
그래서 숫자는 아래 두 겹으로 막는다.

1. 데이터를 JSON 이 아니라 **다 세어 놓은 우리말 문장**으로 넘긴다
2. 받은 글에서 수량 표현을 뽑아 원본과 대조한다 (`check_counts`)
   어긋나면 그 항목만 한 번 다시 쓰게 한다

또 하나 — 항목마다 같은 틀로 쓰면 한 편을 이어 읽을 때 다시 기계가 된다.
시작과 마무리 형식을 항목 순번으로 돌린다 (`OPENERS` / `CLOSERS`).
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

MODEL = os.getenv("SAJU_MODEL", "gemini-3.8-flash")
_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
TIMEOUT = 90


def api_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def ready() -> bool:
    return bool(api_key())


# ── 문장 형식을 항목마다 돌린다 ──────────────────────────────
# 열두 항목이 전부 「이름, ~죠」로 시작해서 「오늘 ~ 세어 보세요」로 끝나면
# 항목 하나는 사람 같아도 한 편은 여전히 기계다.

OPENERS = [
    "손님 이름을 부르며 결론부터 던진다. 「지현님, ~」",
    "이름을 부르지 말고 단정하는 문장으로 바로 시작한다.",
    "손님이 겪었을 장면을 한 줄 묘사하며 시작한다. 설명은 그다음에 붙인다.",
    "되묻는 문장으로 시작한다. 「~한 적 있으시죠?」",
    "사주 글자 하나를 먼저 짚고 시작한다. 「일지에 진토가 앉아 있어요.」",
]

CLOSERS = [
    "마지막 줄은 오늘 지켜볼 것 하나를 준다. 조언이 아니라 관찰거리로.",
    "마지막 줄에 조심할 것을 한 가지만 짧게 둔다.",
    "마무리 문장을 따로 붙이지 않는다. 설명이 끝나는 데서 그냥 끊는다.",
    "마지막을 짧은 한마디로 끊는다. 열 글자 안쪽.",
]

SYSTEM = """너는 사주 상담 사이트 「로드로그」의 글을 쓴다. 화자는 무냥이라는 고양이 도령이다.

[가장 중요 — 어기면 못 쓴다]
사주 계산은 이미 끝났다. 아래 [사주]에 적힌 사실만 쓴다.
- 숫자를 새로 세지 마라. [사주]에 적힌 개수를 그대로 옮긴다.
- [사주]에 없는 십성·신살·대운·글자를 만들어 내지 마라.
- 확실하지 않으면 그 글자를 아예 언급하지 않는다. 빼는 편이 안전하다.

[말투]
- 존댓말. 「~해요」가 기본이되 종결을 섞는다: ~예요 / ~거든요 / ~더라고요 / ~죠 / 명사로 끊기.
- 반말·훈계·단정적 예언은 쓰지 않는다.
- 손님을 「지현님」처럼 이름+님으로 부른다. 「당신」은 쓰지 않는다.
- 🛑 이름은 준 그대로 쓴다. 성을 떼거나 줄이지 마라. 「호현수」면 「호현수님」이다.

[금지 — 하나라도 어기면 다시 쓴다]
1. 대구를 만들지 않는다. 「A하면 B하고, C하면 D해요」처럼 앞뒤가 딱 맞아떨어지는 문장 금지.
2. 문장 길이를 고르게 하지 않는다. 긴 문장 옆에 다섯 글자짜리 문장을 둔다.
3. 「~하는 자리」 「~인 셈이에요」 같은 표현을 한 항목에서 두 번 넘게 쓰지 않는다.
4. 좋은 말로 훈훈하게 맺지 않는다.
5. 이모지·느낌표를 쓰지 않는다.
6. 「사주에 따르면」 「~라고 볼 수 있습니다」 같은 해설자 말투를 쓰지 않는다.

[본문에 반드시 들어갈 것]
- 왜 그런지를 [사주]의 글자를 대고 말한다. 「일간이 경금인데 월지에 사화가 붙어 있어서」처럼.
- 그래서 일상에서 뭘로 나타나는지 구체적인 장면 하나. 「카톡 답장을 바로 안 하고 한 번 더 읽어보는」 같은 것.

[길게 쓸 때]
분량을 채우려고 같은 말을 돌려 쓰지 마라. 문단마다 각도를 바꾼다.
쓸 수 있는 각도: 평소에 나오는 모습 / 관계에서 나오는 모습 / 일이나 돈에서 나오는 모습 /
스스로는 모르는 부분 / 어떤 조건이면 달라지는지 / 지금 당장 해볼 것.
특히 아래 둘은 손님이 가장 고마워하는 대목이니 길게 쓸수록 꼭 넣는다.
- 조건: 「무조건 이렇다」가 아니라 「이 조건이면 이렇게, 아니면 저렇게」로 갈라 준다
- 그대로 써먹을 것: 해볼 행동이나 하지 말 말을 손에 잡히게 적어 준다"""


def facts(saju: dict[str, Any]) -> str:
    """모델에 넘길 사실 목록. 세는 일은 여기서 끝낸다."""
    L = []
    L.append("원국: 연주 %s · 월주 %s · 일주 %s · 시주 %s"
             % (saju.get("연", "?"), saju.get("월", "?"), saju.get("일", "?"), saju.get("시", "?")))
    if saju.get("일간"):
        L.append("일간(나 자신을 뜻하는 글자): %s" % saju["일간"])
    for key, label in (("오행", "오행 개수"), ("십성", "십성 개수")):
        d = saju.get(key) or {}
        if not d:
            continue
        have = ["%s %d개" % (k, v) for k, v in d.items() if v]
        zero = [k for k, v in d.items() if not v]
        line = "%s: %s" % (label, ", ".join(have) if have else "없음")
        if zero:
            line += " / %s는 하나도 없다" % ("·".join(zero))
        L.append(line)
    if saju.get("신살"):
        L.append("신살: %s (이 목록에 없는 신살은 쓰지 않는다)" % ", ".join(saju["신살"]))
    else:
        L.append("신살: 없다 (신살 얘기를 꺼내지 않는다)")
    if saju.get("대운"):
        L.append("지금 지나는 대운: %s" % saju["대운"])
    if saju.get("성별"):
        L.append("성별: %s" % saju["성별"])
    return "\n".join("- " + x for x in L)


# ── 받은 글의 숫자를 원본과 대조한다 ─────────────────────────
_NUM = {
    "하나": 1, "한": 1, "1": 1, "일": 1,
    "둘": 2, "두": 2, "2": 2, "이": 2,
    "셋": 3, "세": 3, "3": 3, "삼": 3,
    "넷": 4, "네": 4, "4": 4, "사": 4,
    "다섯": 5, "5": 5, "오": 5,
    "여섯": 6, "6": 6, "일곱": 7, "7": 7, "여덟": 8, "8": 8,
}
_WORDS = ["비겁", "식상", "재성", "관성", "인성", "목", "화", "토", "금", "수"]
# 「금 기운만 셋」 「재성이 두 개」 「인성 3개」 처럼 낱말 뒤 열두 글자 안에 오는 수량만 본다
_PAT = re.compile(
    r"(%s)\s*(?:기운|글자)?[가-힣이 ]{0,6}?"
    r"(하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|[1-8])\s*(?:개|자|가지|이나|씩)" % "|".join(_WORDS)
)


def check_counts(text: str, saju: dict[str, Any]) -> list[str]:
    """글에 적힌 개수가 계산값과 다르면 그 대목을 돌려준다."""
    truth: dict[str, int] = {}
    truth.update({k: v for k, v in (saju.get("오행") or {}).items()})
    truth.update({k: v for k, v in (saju.get("십성") or {}).items()})
    bad = []
    for word, num in _PAT.findall(text):
        if word not in truth:
            continue
        said = _NUM.get(num)
        if said is None:
            continue
        if said != truth[word]:
            bad.append("%s은(는) %d개인데 글에는 %s(으)로 적혔다" % (word, truth[word], num))
    return bad


def _call(system: str, user: str, *, model: str | None = None,
          temperature: float = 1.0, max_tokens: int = 1400) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    url = (_URL % (model or MODEL)) + "?key=" + key
    last = None
    for attempt in range(3):
        try:
            r = httpx.post(url, json=body, timeout=TIMEOUT)
            j = r.json()
            if "candidates" in j:
                txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
                u = j.get("usageMetadata", {})
                return {"text": txt.strip(),
                        "in": u.get("promptTokenCount", 0),
                        "out": u.get("candidatesTokenCount", 0)}
            last = json.dumps(j, ensure_ascii=False)[:300]
        except httpx.HTTPError as e:
            last = str(e)[:200]
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("생성 실패: %s" % last)


def _length_note(chars: int) -> str:
    """몇 자로 쓸지. 문단 수까지 같이 정해 줘야 늘어지지 않는다."""
    if chars >= 1000:
        return "길이: %d자 안팎. 문단을 다섯에서 여섯으로 나누고, 문단마다 각도를 바꾼다." % chars
    if chars >= 700:
        return "길이: %d자 안팎. 문단 넷 정도로 나눈다." % chars
    return "길이: %d자 안팎. 문단 셋 정도." % max(chars, 300)


def write_section(name: str, saju: dict[str, Any], section: str, idx: int = 0,
                  *, product: str = "", model: str | None = None,
                  chars: int = 420) -> dict[str, Any]:
    """항목 하나를 쓴다. 숫자가 어긋나면 한 번 다시 쓰게 한다."""
    fact = facts(saju)
    guide = "%s\n%s\n%s" % (OPENERS[idx % len(OPENERS)], CLOSERS[idx % len(CLOSERS)],
                             _length_note(chars))
    user = ("손님 이름: %s\n\n[사주]\n%s\n\n[이번에 쓸 항목]\n%s\n\n[이 항목의 형식]\n%s"
            % (name, fact, section, guide))
    res = _call(SYSTEM, user, model=model, max_tokens=max(1400, int(chars * 2.2)))
    bad = check_counts(res["text"], saju)
    if bad:
        fix = user + ("\n\n[다시 쓴다]\n앞서 쓴 글에서 개수를 틀렸다: %s\n"
                      "[사주]에 적힌 개수를 그대로 옮겨라. 헷갈리면 개수를 아예 말하지 마라."
                      % " / ".join(bad))
        res2 = _call(SYSTEM, fix, model=model, temperature=0.7)
        res2["in"] += res["in"]
        res2["out"] += res["out"]
        res2["retried"] = bad
        res = res2
        res["left"] = check_counts(res["text"], saju)
    return res


def write_report(name: str, saju: dict[str, Any], sections: list[str],
                 *, product: str = "", model: str | None = None,
                 workers: int = 6, chars: int = 420) -> dict[str, Any]:
    """항목들을 한꺼번에 쓴다. 순서는 넘어온 그대로 지킨다."""
    import concurrent.futures as cf

    out: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(write_section, name, saju, s, i, product=product,
                          model=model, chars=chars): s
                for i, s in enumerate(sections)}
        for f in cf.as_completed(futs):
            try:
                out[futs[f]] = f.result()
            except Exception as e:                      # noqa: BLE001
                out[futs[f]] = {"text": "", "in": 0, "out": 0, "error": str(e)[:200]}

    blocks, tin, tout, errs, fixed = [], 0, 0, [], 0
    for s in sections:
        d = out.get(s) or {}
        tin += d.get("in", 0)
        tout += d.get("out", 0)
        if d.get("retried"):
            fixed += 1
        if d.get("error"):
            errs.append("%s: %s" % (s, d["error"]))
        blocks.append({"title": s, "text": d.get("text", ""),
                       "left": d.get("left") or []})
    return {"model": model or MODEL, "blocks": blocks,
            "tokens": {"in": tin, "out": tout}, "fixed": fixed, "errors": errs}


# ── 한 번 쓴 글은 남겨 둔다 ──────────────────────────────────
# 같은 사람이 같은 상품을 다시 열 때마다 새로 뽑으면 글이 매번 달라져서
# 「아까 그 문장이 없어졌다」가 된다. 돈도 두 번 나간다.

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _store_dir():
    from pathlib import Path
    from modules.config import DATA_DIR
    d = Path(DATA_DIR) / "saju_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(product: str, pair: str):
    if not _SAFE.match(product or "") or not _SAFE.match(pair or ""):
        raise ValueError("상품·사주 키가 올바르지 않습니다")
    return _store_dir() / ("%s__%s.json" % (product, pair))


def load(product: str, pair: str) -> dict[str, Any] | None:
    p = _path(product, pair)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(product: str, pair: str, data: dict[str, Any]) -> None:
    p = _path(product, pair)
    data = dict(data)
    data["savedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def merge(product: str, pair: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """새로 쓴 항목을 이미 있는 것 위에 얹는다. 있던 항목은 그대로 둔다."""
    old = load(product, pair) or {"blocks": []}
    by = {b["title"]: b for b in old.get("blocks", []) if b.get("text")}
    for b in blocks:
        if b.get("text"):
            by[b["title"]] = b
    data = {"blocks": list(by.values())}
    save(product, pair, data)
    return data
