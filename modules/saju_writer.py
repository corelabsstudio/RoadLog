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

from modules.saju_brief import brief_of

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

[어려운 말 — 손님은 사주를 모른다]
🛑 손님은 돈을 내고 「내가 어떤 사람인지」를 보러 왔다. 모르는 말이 나오면 그 자리에서 막힌다.
- **쉬운 말을 앞에 두고, 사주 글자는 괄호로 뒤에 붙인다.**
  ❌ 일간이 경금이라        ✅ 나를 뜻하는 글자가 무쇠(경금)라
  ❌ 일지에 술이 앉아서      ✅ 곁을 내주는 자리(일지)에 술이 앉아서
  ❌ 식상이 강해서          ✅ 밖으로 내보내는 기운(식상)이 세서
  ❌ 대운이 바뀌는 때라      ✅ 십 년마다 바뀌는 흐름(대운)이 갈리는 때라
- 한 항목에서 **두 번째부터는 괄호를 떼고 쉬운 말만** 쓴다. 괄호가 반복되면 그것도 읽기 싫어진다.
- 풀이는 이렇게 쓴다:
  일간=나를 뜻하는 글자 · 일지=곁을 내주는 자리 · 월지=자라온 바탕 · 시지=혼자 있을 때
  대운=십 년마다 바뀌는 흐름 · 세운=올해 기운 · 공망=비어 있는 자리 · 신살=걸린 살
  식상=밖으로 내보내는 기운 · 관성=나를 누르는 기운 · 인성=나를 받쳐 주는 기운
  재성=내가 쥐는 기운 · 비겁=나와 같은 기운
- 🛑 아래 말은 **풀어 써도 쓰지 마라**: 원국·통근·투출·용신·희신·기신·격국·신강·신약·지장간·육친·십신·조후
  ([사주]에 그 말이 있어도 마찬가지다. 손님이 읽을 글에는 넣지 않는다)

[본문에 반드시 들어갈 것]
- 왜 그런지를 [사주]의 글자를 대고 말한다. 위 [어려운 말] 방식대로 풀어서.
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
                  chars: int = 420, seen: str = "") -> dict[str, Any]:
    """항목 하나를 쓴다. 숫자가 어긋나면 한 번 다시 쓰게 한다."""
    fact = facts(saju)
    guide = "%s\n%s\n%s" % (OPENERS[idx % len(OPENERS)], CLOSERS[idx % len(CLOSERS)],
                             _length_note(chars))
    # 🛑 상품이 무엇을 묻는지 안 알려 주면 사주 일반론으로 흐른다 (2026-09-07).
    #    항목 제목은 각도일 뿐이고, 손님이 산 것은 이 질문에 대한 답이다.
    ask = brief_of(product)
    head = ("[이 상품이 답해야 할 것]\n%s\n\n🛑 아래 항목이 무엇이든, 결국 위 "
            "질문에 답하는 방향으로 쓴다.\n\n" % ask) if ask else ""
    # 🛑 앞서 읽은 편이 있으면 그것부터 알려 준다. 겹치면 2차 결제가 끊긴다
    user = ("손님 이름: %s\n\n%s%s[사주]\n%s\n\n[이번에 쓸 항목]\n%s\n\n[이 항목의 형식]\n%s"
            % (name, seen or "", head, fact, section, guide))
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
                 workers: int = 6, chars: int = 420, pair: str = "") -> dict[str, Any]:
    """항목들을 한꺼번에 쓴다. 순서는 넘어온 그대로 지킨다."""
    import concurrent.futures as cf

    # 🛑 앞서 읽은 편은 **여기서 한 번만** 찾는다. 항목마다 찾으면 같은 파일을 열두 번 읽는다.
    seen = ""
    if pair:
        try:
            seen = seen_note(product, pair)
        except Exception:                               # noqa: BLE001
            seen = ""                                   # 앞 편을 못 읽어도 글은 나와야 한다

    # 🛑 **물결로 나눠 쓴다.** 전에는 열두 항목을 한꺼번에 던져서 서로 뭘 썼는지 몰랐다.
    #    그래서 한 편 안에서 같은 장면이 두 번 나왔다(시안 12항목 중 둘에
    #    「장바구니에 담아두고 결제창을 닫는」이 겹쳤다 · 2026-09-07 기록).
    #    한 물결이 끝나면 거기서 쓴 것을 다음 물결에 알려 준다.
    #    순차로 바꾸면 확실하지만 12항목에 1분이 넘는다 — 손님이 기다린다.
    #    물결은 **뒤로 갈수록 키운다.** 앞쪽이 기준을 만들고, 뒤쪽은 참고할 게 이미 많다.
    #    6 → 12 → 12 … 로 가면 51항목 대점이 아홉 물결에서 다섯 물결로 준다.
    out: dict[str, Any] = {}
    wrote: list[tuple[str, str]] = []               # 이 편에서 이미 쓴 (제목, 첫 문장)
    start, size = 0, workers
    while start < len(sections):
        wave = sections[start:start + size]
        note = seen + _same_note(wrote)             # 다른 편 + 이 편에서 이미 쓴 것
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(write_section, name, saju, s, start + i, product=product,
                              model=model, chars=chars, seen=note): s
                    for i, s in enumerate(wave)}
            for f in cf.as_completed(futs):
                try:
                    out[futs[f]] = f.result()
                except Exception as e:              # noqa: BLE001
                    out[futs[f]] = {"text": "", "in": 0, "out": 0, "error": str(e)[:200]}
        # 이 물결에서 나온 것을 다음 물결에 넘길 목록에 쌓는다
        for t in wave:
            txt = (out.get(t) or {}).get("text") or ""
            if txt:
                wrote.append((t, _first_sentence(txt)))
        start += size
        size = min(size * 2, _WAVE_MAX)             # 🛑 상한을 둔다. 동시 호출이 너무 늘면 막힌다

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


# ── 카드에 넣을 한두 줄 ──────────────────────────────────────
# 공유 카드는 남이 본다. 사주 용어를 늘어놓으면 아무도 안 누른다.
# 읽은 사람이 「이거 내 얘기네」 하고 캡처하고 싶어지는 두 줄이어야 한다.

SUMMARY_SYSTEM = """너는 사주 결과지를 읽고, 공유 카드에 넣을 짧은 글을 뽑는다.

[규칙]
- 두 문장. 합쳐서 55자 안쪽. 넘으면 잘린다.
- 남이 본다. 사주 용어(일간·십성·대운·신살·오행 이름)를 쓰지 마라.
- 손님 이름을 넣지 마라. 생년월일도 안 된다.
- 「당신은 ~한 사람입니다」 같은 설명문 말고, 읽은 사람이 뜨끔할 한마디로.
- 존댓말. 「~해요」 「~거든요」 「~죠」. 이모지·느낌표 금지.
- 좋은 말로 마무리하지 마라. 찌르고 끝낸다.

[좋은 예]
겉으로는 다 받아 주면서 속으로 명단을 적어 두는 사람이에요. 그 명단이 길어지면 조용히 문을 닫죠.
먼저 연락하는 법이 없어요. 기다리는 게 편한 게 아니라, 먼저 손 내미는 법을 안 배운 거예요.

[나쁜 예 — 이렇게 쓰지 마라]
당신은 갑목 일간으로 인성이 강한 사주입니다.  (용어)
좋은 기운이 함께하니 힘내세요.  (훈훈한 마무리)"""


def summarize(blocks: list[dict[str, Any]], *, model: str | None = None) -> str:
    """리포트 앞부분을 읽고 카드에 넣을 두 줄을 뽑는다."""
    src = []
    for b in blocks[:3]:
        t = (b.get("text") or "").strip()
        if t:
            src.append(t[:900])
    if not src:
        return ""
    user = "[결과지 앞부분]\n" + "\n\n".join(src)
    res = _call(SUMMARY_SYSTEM, user, model=model, temperature=0.9, max_tokens=300)
    txt = " ".join(res["text"].split())
    return txt[:90]


# ── 앞서 읽은 편과 겹치지 않게 ─────────────────────────────
# 왜: 손님은 한 편을 읽고 다음 편을 산다. 그때 앞에서 읽은 이야기가 또 나오면
# 「돈 두 번 냈는데 같은 글」이 된다. 2·3차 결제가 여기서 끊긴다
# (2026-09-08 실측: 대점 → 재회운 종합 → 다시 만날 필연에서 3편째의 65%가 되풀이였다).
#
# 파일 이름이 `{상품}__{사주쌍}.json` 이라 **같은 사주쌍의 다른 상품 글을 이름만으로 찾을 수 있다.**
# 그 글에서 되풀이되면 안 되는 것만 짧게 뽑아 프롬프트에 넣는다.
#
# 🛑 앞 글을 통째로 넣지 않는다. 입력 토큰이 폭발하고 원가가 몇 배가 된다.
#    항목 제목과 **첫 문장**만 쓴다 — 되풀이는 거기서 제일 잘 드러난다.
# 🛑 「같은 사주를 다르게 읽는 것」과 「다른 말을 지어내는 것」은 다르다.
#    사실은 그대로 두고 **장면·비유·표현**만 겹치지 말라고 시킨다.

_SEEN_MAX_PRODUCTS = 4      # 앞서 읽은 편은 최근 넷까지만 본다
_SEEN_MAX_LINES = 10        # 한 편에서 열 줄까지
_SEEN_HEAD = 70             # 한 줄은 앞 70자만


def seen_before(product: str, pair: str) -> list[tuple[str, list[str]]]:
    """같은 사주쌍으로 **다른 상품**에서 이미 써 둔 글을 찾는다.

    돌려주는 것: [(상품id, [항목제목 — 첫 문장, ...]), ...] · 최근에 쓴 것부터.
    """
    try:
        if not _SAFE.match(product or "") or not _SAFE.match(pair or ""):
            return []
        d = _store_dir()
    except Exception:                                   # noqa: BLE001
        return []
    rows: list[tuple[float, str, list[str]]] = []
    for p in d.glob("*__%s.json" % pair):
        pid = p.name[: -len("__%s.json" % pair)]
        if pid == product or not pid:
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            mtime = p.stat().st_mtime
        except (OSError, ValueError):
            continue
        lines: list[str] = []
        for b in (data.get("blocks") or []):
            t = (b.get("text") or "").strip()
            title = (b.get("title") or "").strip()
            if not t:
                continue
            # 첫 문장만. 되풀이는 여는 문장에서 가장 잘 드러난다
            first = re.split(r"(?<=[.!?요죠])\s", t.replace("\n", " "), 1)[0]
            lines.append("%s — %s" % (title, first[:_SEEN_HEAD]))
            if len(lines) >= _SEEN_MAX_LINES:
                break
        if lines:
            rows.append((mtime, pid, lines))
    rows.sort(key=lambda x: -x[0])
    return [(pid, lines) for _, pid, lines in rows[:_SEEN_MAX_PRODUCTS]]


def seen_note(product: str, pair: str) -> str:
    """앞서 읽은 편을 프롬프트에 넣을 문단으로 만든다. 없으면 빈 문자열."""
    rows = seen_before(product, pair)
    if not rows:
        return ""
    body = []
    for pid, lines in rows:
        body.append("· %s\n%s" % (pid, "\n".join("  - " + x for x in lines)))
    return (
        "[이 손님이 이미 읽은 편]\n"
        "같은 사주로 아래 편들을 먼저 읽었다. 각 줄은 그 편의 항목과 첫 문장이다.\n\n"
        + "\n".join(body)
        + "\n\n🛑 사주 사실은 같으니 같은 글자를 다시 말해도 된다. 다만 **이번 편은 다른 편이다.**\n"
          "- 위에 나온 **장면·비유·예시를 다시 쓰지 마라.** 다른 장면을 찾아라.\n"
          "- 위와 **같은 문장으로 시작하지 마라.**\n"
          "- 같은 글자를 말하더라도 **이 상품의 질문에 맞게 다시 읽어라.**\n"
          "  (같은 일지라도 재회에서는 「돌아오는 방식」, 결혼에서는 「같이 사는 방식」이다.)\n\n"
    )


# ── 한 편 안에서 항목끼리 겹치지 않게 ───────────────────────
# 왜: 항목을 한꺼번에 병렬로 뽑으니 **서로 뭘 썼는지 몰랐다.** 그래서 한 편 안에서
# 같은 장면이 두 번 나왔다(12항목 시안 중 둘에 「장바구니에 담아두고 결제창을 닫는」).
# 손님은 한 편을 이어 읽으므로 이게 앞뒤로 붙어 나오면 바로 보인다.
#
# `write_report` 가 물결마다 이 문단을 만들어 다음 물결에 넘긴다.
# 🛑 첫 문장만 쓴다. 본문을 다 넣으면 뒤 물결일수록 입력이 눈덩이가 된다.

_WAVE_MAX = 12          # 한 물결에 동시에 돌릴 수 있는 최대 (rate limit 안전선)
_SAME_HEAD = 60         # 한 줄은 앞 60자만
_SAME_MAX = 12          # 열두 줄까지 (그 이상은 오래된 것부터 버린다)


def _first_sentence(text: str) -> str:
    """글의 첫 문장. 되풀이는 여는 문장에서 가장 잘 드러난다."""
    t = (text or "").replace("\n", " ").strip()
    return re.split(r"(?<=[.!?요죠])\s", t, 1)[0][:_SAME_HEAD]


def _same_note(wrote: list[tuple[str, str]]) -> str:
    """이 편에서 이미 쓴 항목들. 없으면 빈 문자열."""
    if not wrote:
        return ""
    rows = wrote[-_SAME_MAX:]
    body = "\n".join("  - %s — %s" % (t, f) for t, f in rows)
    return (
        "[이 편에서 이미 쓴 항목]\n"
        "같은 리포트 안에서 아래 항목들을 먼저 썼다. 손님은 이걸 이어서 읽는다.\n\n"
        + body
        + "\n\n🛑 **같은 편 안이라 겹치면 바로 보인다.**\n"
          "- 위에 나온 **장면·비유·예시를 다시 쓰지 마라.** 다른 장면을 찾아라.\n"
          "- 위와 **같은 문장으로 시작하지 마라.**\n"
          "- 같은 글자(십성·오행·신살)를 또 말해야 하면, **이번 항목의 각도로만** 말한다.\n\n"
    )


# ── 무냥이에게 아무거나 묻기 ──────────────────────────────────
# 왜: 「더 물어보기」가 정해진 열 개 질문에서 하나 고르는 방식이었다. 원가는 0원이지만
# 손님이 진짜 묻고 싶은 것을 못 묻는다. 폭스바니처럼 **1:1 대화**로 바꾼다
# (2026-09-09 온해님 지시).
#
# 🛑 사주에 없는 것을 지어내지 않는다. 위 SYSTEM 의 규칙을 그대로 물려받는다.
# 🛑 사주로 답할 수 없는 질문은 **답하지 않고 그렇게 말한다.** 로또 번호·병 진단·
#    수명·시험 합격 같은 것은 이 서비스가 답할 자리가 아니다.
ASK_SYSTEM = SYSTEM + """

[지금은 대화 중이다]
손님이 리포트를 다 읽고 이어서 묻는 자리다. 강의가 아니라 대답이다.
- **3~6문장.** 길게 늘이지 않는다. 묻지 않은 것을 덧붙이지 않는다.
- 첫 문장에서 바로 답한다. 뜸을 들이지 않는다.
- 근거가 되는 사주 글자를 한 번은 댄다. 「일지에 술토가 앉아 있어서」처럼.
- 항목 제목을 붙이지 않는다. 본문만 쓴다.

[무엇이든 사주로 본다]
여기는 점집이다. 손님은 사주라는 걸 알고 묻는다.
수명·건강·시험·이사·전생 — **사주에서 보는 자리면 피하지 말고 사주 언어로 답한다.**
「그건 못 봐요」로 물러서지 마라. 명(命)도 사주가 보는 자리다.
다만 위 [말투]대로 **단정하지 않는다.** 「이렇게 됩니다」가 아니라
「이 자리에 이런 기운이 있어요 / 이때가 꺾이는 자리예요」로 짚는다.

[그래도 답하지 않는 세 가지]
- **로또·복권 번호, 주식 종목** — 사주에 안 나온다. 답하면 거짓말이 된다
- **병명을 확정하는 것** — 「암이에요」는 의사가 할 말이다. 「어느 기운이 약한지」까지가
  우리 자리다. 몸 얘기가 나오면 그 자리를 짚어 주되 병원에 가보시라고 한 줄 덧붙인다
- **남을 해치거나 몰래 알아내려는 것**"""


def answer(name: str, saju: dict[str, Any], question: str,
           *, model: str | None = None, seen: str = "") -> dict[str, Any]:
    """자유 질문 하나에 답한다. 리포트와 같은 사실만 쓴다."""
    q = (question or "").strip()
    if not q:
        raise ValueError("질문이 비었다")
    user = ("손님 이름: %s\n\n%s[사주]\n%s\n\n[손님이 묻는 것]\n%s"
            % (name or "손님", seen or "", facts(saju), q[:400]))
    res = _call(ASK_SYSTEM, user, model=model, max_tokens=900)
    bad = check_counts(res["text"], saju)
    if bad:
        # 개수를 틀리면 한 번만 다시. 리포트와 같은 방식이다.
        fix = user + ("\n\n[다시 쓴다]\n개수를 틀렸다: %s\n[사주]에 적힌 대로만 옮겨라."
                      % " / ".join(bad))
        res2 = _call(ASK_SYSTEM, fix, model=model, temperature=0.7, max_tokens=900)
        res2["in"] += res["in"]; res2["out"] += res["out"]
        res = res2
    return res
