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


# ── 글이 안 써지면 팔지 않는다 (2026-09-10 온해님) ─────────────
# 🛑 **잔액이 0이 되면 그 계정의 API 키가 전부 즉시 멈춘다.** 그런데 지금 구조에서는
#    LLM 이 멈춰도 **계산 글은 나가서**, 손님이 복채를 내고 무냥이 글이 빠진 리포트를
#    받게 된다. 그게 안 파는 것보다 나쁘다.
#
# 🛑 **잔액을 물어보는 API 가 없다.** 그래서 잔액이 아니라 **실패를 센다** — 원인이
#    잔액이든 구글 장애든, 글이 안 나오면 팔면 안 되는 건 같다.
#
# 🛑 성공하면 그 자리에서 0으로 돌아간다. 충전하시면 **저절로 다시 열린다.**
_FAIL_FILE = "llm_fail.json"
_FAIL_MAX = 3            # 이만큼 잇따라 실패하면 닫는다
_FAIL_HOLD = 600         # 마지막 실패로부터 이 초가 지나면 한 번 더 해 본다


def _fail_path():
    from pathlib import Path
    return Path(os.getenv("DATA_DIR") or ".") / _FAIL_FILE


def _fail_read() -> dict:
    try:
        return json.loads(_fail_path().read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        return {}


def _fail_write(d: dict) -> None:
    try:
        f = _fail_path()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        pass                                             # 못 적어도 글은 나가야 한다


def note_fail(why: str = "") -> None:
    d = _fail_read()
    d["n"] = int(d.get("n") or 0) + 1
    d["at"] = time.time()
    d["why"] = str(why)[:200]
    _fail_write(d)


def note_ok() -> None:
    if _fail_read().get("n"):
        _fail_write({"n": 0, "at": time.time(), "why": ""})


def down() -> bool:
    """글쓰기가 막혀 있나. 막혔으면 복채를 받지 않는다."""
    d = _fail_read()
    if int(d.get("n") or 0) < _FAIL_MAX:
        return False
    # 시간이 꽤 지났으면 한 번 더 해 볼 기회를 준다 (충전하셨을 수 있다)
    return (time.time() - float(d.get("at") or 0)) < _FAIL_HOLD


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


[말하는 결 — 팩트폭격 (2026-09-10 온해님이 정하심)]
손님은 20~30대 여성이다. 지루한 사주 풀이 말고 **위트와 팩트폭격**으로 간다.
화자는 그대로 **무냥이**다. 무냥이가 팩트를 때린다.
한 항목을 이 세 박자로 쓴다.
  ① **팩트폭격** — 돌려 말하지 않는다. 뼈 때리는 한 줄로 연다.
  ② **찰진 비유** — 손님이 자기 얘기라고 느낄 장면 하나.
     「장바구니에 담아 두고 결제는 안 눌러요」 「읽씹 당하고도 프로필은 확인해요」
  ③ **유쾌한 반전** — 그래서 어떻게 하면 되는지로 뒤집어 준다.
🛑 **외모 비하가 아니라 상황·성향을 웃긴다** (온해님 지침). 얼굴·몸을 두고 웃지 않는다.
🛑 **없는 숫자를 지어내지 않는다.** %는 우리가 따로 계산해서 넣어 준다.

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
  무속 말도 마찬가지다: 몸주·좌보·우필. 각각 「나를 맡은 신」·「왼쪽」·「오른쪽」으로 쓴다
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
    # 🛑 **오늘의 운세에만 온다** (2026-09-11 온해님). 위까지는 전부 태어난 사주라,
    #    이 셋이 없으면 오늘 얘기를 쓸 재료가 없어 평생 성격 풀이로 샌다.
    #    화면의 글자 표(`todayBlock`)와 **같은 값**이다 — 어긋나면 한 화면에서
    #    무냥이와 표가 서로 다른 말을 한다.
    if saju.get("오늘"):
        L.append("오늘 날짜와 일진: %s" % str(saju["오늘"])[:60])
    if saju.get("오늘십성"):
        L.append("오늘 글자가 나에게 무엇인가: %s" % str(saju["오늘십성"])[:80])
    if saju.get("오늘걸림"):
        L.append("오늘 글자가 내 사주에 걸리는 자리: %s" % str(saju["오늘걸림"])[:120])
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


# 🛑 **제미나이가 이 규격으로만 답한다** (2026-09-10 온해님).
#    `responseSchema` 로 주면 모델이 어길 수 없다. 부탁이 아니라 규격이다.
CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "카드 제목. 열두 자 안쪽. 재치 있는 별명"},
        "highlight_badge": {"type": "string", "description": "수치·뱃지 한 조각. 재료에 「상위 몇 %」가 있으면 그 숫자를 쓴다. 없으면 빈 문자열"},
        "one_liner": {"type": "string", "description": "한 줄 요약. 스무 자 안쪽. 끝에 마침표를 찍지 않는다"},
        "tale": {"type": "string", "description": "두 문장. 퍼뜨리고 싶은 두 줄로 닫는다"},
    },
    "required": ["title", "one_liner", "tale"],
}

# 🛑 **전생 카드는 규격이 다르다** (2026-09-10 온해님).
#    전생 카드에는 세 칸짜리 표가 들어간다. 그 세 칸을 계산이 채우고 있었는데,
#    계산은 「맨몸으로 시작한 편」 같은 말밖에 못 만든다. 스레드·인스타에 퍼뜨릴
#    카드라 **그 세 칸이 웃겨야** 한다 — 그래서 세 칸도 LLM 이 쓴다.
#
#    🛑 **글자 수가 화면에 맞아야 한다.** 세 칸은 한 칸 폭이 300px 이고 30px 글자로
#       두 줄까지 그린다 — **열여덟 자를 넘으면 잘린다.** 넘으면 코드가 자른다.
PAST_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string",
                  "description": "메인 타이틀. 역사 속 직업이 아니라 현대인의 성향과 연결되는 "
                                 "위트 있는 밈 타이틀. 열두 자 안쪽 "
                                 "(예: 조선의 은둔 재벌, 방구석 도령, 주막 호구 삼돌이)"},
        "subtitle": {"type": "string",
                     "description": "팩트를 유쾌하게 찌르는 한 줄. 열다섯 자 이내. "
                                    "끝에 마침표를 찍지 않는다"},
        "keywords": {
            "type": "object",
            "properties": {
                "type_job": {"type": "string",
                             "description": "전생의 특징이나 직업. **열여덟 자 안쪽** "
                                            "(예: 짚신 팔아 한양 건물주 됨)"},
                "habit": {"type": "string",
                          "description": "현생까지 남은 웃픈 버릇. **열여덟 자 안쪽** "
                                         "(예: 잔고 없어도 일단 장바구니 담음)"},
                "karma": {"type": "string",
                          "description": "전생이 남긴 억울한 업보나 현타 포인트. "
                                         "**열여덟 자 안쪽** (예: 돈은 버는데 쓸 데가 없었음)"},
            },
            "required": ["type_job", "habit", "karma"],
        },
        "summary": {"type": "string",
                    "description": "보자마자 「이거 완전 나잖아」 하고 공감해서 스레드에 "
                                   "올리고 싶어지는, 뼈 때리는 두세 문장. "
                                   "🛑 **백이십 자 안쪽** — 넘으면 카드에서 잘린다"},
    },
    "required": ["title", "subtitle", "keywords", "summary"],
}

# 🛑 **수호신 카드도 규격이 다르다** (2026-09-10 온해님 가챠 규칙).
#    🛑🛑 여기서 **LLM 이 지어내면 안 되는 값이 넷**이다 — 등급·신 이름 셋.
#       등급은 계산(`godOdds`)이 정하고, 최영 장군·바리공주·용왕은 실제로 모시는
#       신명이라 지어내면 안 된다. 스키마에는 있지만 **서버가 계산값으로 덮어쓴다.**
#       그래도 스키마에 두는 이유는, 받아 쓸 자리를 알려 줘야 나머지 글이 그 값에
#       맞게 나오기 때문이다.
GOD_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "rank": {"type": "string",
                 "description": "S급·A급·B급·C급·D급 중 하나. "
                                "🛑 재료의 「정해진 등급」을 **그대로** 쓴다. 올리거나 내리지 마라"},
        "title": {"type": "string",
                  "description": "등급 + 현대적 별명 + 신 이름 "
                                 "(예: S급 | 멱살 견인 전문 대신할머니). "
                                 "🛑 신 이름은 재료의 「정해진 이름」을 한 글자도 안 바꾸고 쓴다"},
        "nick": {"type": "string",
                 "description": "신 이름 앞에 붙일 **현대적 별명만** 따로. 등급도 신 이름도 "
                                "빼고 별명만 (예: 멱살 견인 전문, 똥차 감별 전담). "
                                "🛑 **열두 자 안쪽** — 카드에서 등급과 한 줄에 붙는다"},
        "subtitle": {"type": "string",
                     "description": "수호신 능력을 유쾌하게 요약한 한 줄. 스무 자 이내. "
                                    "끝에 마침표를 찍지 않는다 "
                                    "(예: 내 똥고집과 액운까지 멱살 잡고 견인 중)"},
        "god_details": {
            "type": "object",
            "properties": {
                "left_god": {"type": "string", "description": "왼쪽에 선 신. 🛑 재료 값 그대로"},
                "right_god": {"type": "string", "description": "오른쪽에 선 신. 🛑 재료 값 그대로"},
                "animal": {"type": "string", "description": "띠 짐승. 🛑 재료 값 그대로"},
            },
            "required": ["left_god", "right_god", "animal"],
        },
        "summary": {"type": "string",
                    "description": "스토리에 올려 자랑하거나 공감할 두세 문장. "
                                   "지금 상황과 수호신의 케미를 유머러스하게. "
                                   "🛑 **백 자 안쪽** — 넘으면 카드에서 잘린다"},
    },
    "required": ["rank", "title", "nick", "subtitle", "summary"],
}

SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "nickname": {"type": "string", "description": "이 항목의 제목. 재치 있는 별명. 열여섯 자 안쪽"},
        "fact_bomb": {"type": "string", "description": "뼈 때리는 팩트 폭격. 돌려 말하지 않는다"},
        "meme_analysis": {"type": "string", "description": "밈과 유머를 섞은 성향 분석. 찰진 비유와 장면"},
        "funny_solution": {"type": "string", "description": "유쾌하고 엉뚱한 대안. 그래서 어떻게 하면 되는지"},
        "mutter": {"type": "string", "description": "무냥이 혼잣말 한 줄"},
    },
    "required": ["nickname", "fact_bomb", "meme_analysis", "funny_solution"],
}


# 🛑 **말투는 관리자 화면에서 고칠 수 있다** (2026-09-11 온해님).
#    아래 상수들은 **기본값**이고, 고친 것이 있으면 `prompts.get()` 이 그것을 준다.
#    부를 때마다 조회하므로 고치자마자 다음 글부터 바뀐다 (재배포 필요 없음).
#    🛑 상수를 지우지 말 것 — 「기본값으로 되돌리기」의 기준이다.
def _P(key: str, fallback: str) -> str:
    try:
        from modules import prompts as _pr
        return _pr.get(key) or fallback
    except Exception:                                # noqa: BLE001
        return fallback


def _call(system: str, user: str, *, model: str | None = None,
          temperature: float = 1.0, max_tokens: int = 1400,
          schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """제미나이를 부른다.

    🛑 `schema` 를 주면 **규격을 어길 수 없게** 된다 (2026-09-10 온해님).
       그전에는 「JSON 하나만 내놔라」라고 부탁만 해서, ```json 울타리가 붙거나
       칸이 빠지면 빈 값으로 떨어졌다 — 전수검수에서 두 번 그랬다.
    """
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
    if schema:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = schema
    url = (_URL % (model or MODEL)) + "?key=" + key
    last = None
    for attempt in range(3):
        try:
            r = httpx.post(url, json=body, timeout=TIMEOUT)
            j = r.json()
            if "candidates" in j:
                # 🛑 **글이 없는 답이 온다** (2026-09-11 실측). 길이에 걸리거나 안전
                #    검사에 막히면 `candidates[0]` 은 오는데 그 안에 `parts` 가 없다.
                #    전에는 여기서 `KeyError` 가 나면서 **되풀이 고리를 통째로 건너뛰고**
                #    바로 죽었다 — 아래 `except` 가 httpx 오류만 받기 때문이다.
                #    그러면 손님은 다시 해 보면 될 일에 「막혔어요」를 받는다.
                cand = j["candidates"][0] or {}
                parts = (cand.get("content") or {}).get("parts") or []
                txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                if txt.strip():
                    u = j.get("usageMetadata", {})
                    note_ok()      # 되면 그 자리에서 다시 연다
                    return {"text": txt.strip(),
                            "in": u.get("promptTokenCount", 0),
                            "out": u.get("candidatesTokenCount", 0)}
                last = "빈 답 (%s)" % (cand.get("finishReason") or "이유 없음")
            else:
                last = json.dumps(j, ensure_ascii=False)[:300]
        except httpx.HTTPError as e:
            last = str(e)[:200]
        time.sleep(1.5 * (attempt + 1))
    # 🛑 세 번 다 실패했다. 잔액이 바닥났을 수 있으니 세어 둔다 (위 note_fail 참고)
    note_fail(last or "")
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
    # 🛑 **제목도 여기서 같이 받는다** (2026-09-09 온해님 「항목도 LLM이 뽑게」).
    #    손님이 미리보기에서 보는 건 제목과 두세 줄이 전부다. 제목이 밋밋하면
    #    아래를 안 읽는다. 다만 **본래 제목은 그대로 두고** 보이는 글자만 바꾼다.
    hook = (
        "\n\n[맨 첫 줄에 제목을 쓴다]\n"
        "`제목: ` 으로 시작하는 줄을 하나 쓰고, 한 줄 띄운 뒤에 본문을 쓴다." "\n"
        "  · 이 항목에서 **실제로 나온 답**을 걸고 넘어지는 제목이어야 한다" "\n"
        "  · 열여섯 자 안쪽. 읽고 나서 「그래서 뭔데」가 들게" "\n"
        "  · 🛑 사주 용어를 쓰지 마라. 이모지·느낌표도 쓰지 마라" "\n"
        "  · 🛑 답을 제목에서 다 말하지 마라. 본문을 열게 만드는 게 제목이 할 일이다"

        # 🛑 혼잣말도 같이 받는다 (2026-09-09 온해님 「무냥이 혼잣말도 LLM으로, 모든 항목에」)
        "\n\n[맨 마지막 줄에 혼잣말을 쓴다]\n"
        "`혼잣말: ` 으로 시작하는 줄을 하나 쓴다. 본문 끝에서 한 줄 띄우고." "\n"
        "  · 무냥이가 이 항목을 다 읽고 **옆에서 툭 던지는 한마디**다" "\n"
        "  · 두 문장 안쪽·마흔 자 안쪽. 말풍선에 들어간다" "\n"
        "  · 🛑 본문을 요약하지 마라. 요약은 손님이 방금 읽었다" "\n"
        "  · 🛑 위로하거나 훈훈하게 맺지 마라. 한 발 물러선 자리에서 덧붙이는 말이다" "\n"
        "  · 좋은 보기: 「이 자리 얘기 나오면 다들 한참 말이 없어져요」 "
        "「저도 이건 조심해서 말해요」 「올해 글자는 올해만 써요. 내년엔 또 달라져요」")
    user = ("손님 이름: %s\n\n%s%s[사주]\n%s\n\n[이번에 쓸 항목]\n%s\n\n[이 항목의 형식]\n%s%s"
            % (name, seen or "", head, fact, section, guide, hook))
    res = _call(_P('saju', SYSTEM), user, model=model, max_tokens=max(1400, int(chars * 2.2)))
    bad = check_counts(res["text"], saju)
    if bad:
        fix = user + ("\n\n[다시 쓴다]\n앞서 쓴 글에서 개수를 틀렸다: %s\n"
                      "[사주]에 적힌 개수를 그대로 옮겨라. 헷갈리면 개수를 아예 말하지 마라."
                      % " / ".join(bad))
        res2 = _call(_P('saju', SYSTEM), fix, model=model, temperature=0.7)
        res2["in"] += res["in"]
        res2["out"] += res["out"]
        res2["retried"] = bad
        res = res2
        res["left"] = check_counts(res["text"], saju)
    res["hook"], res["text"] = _split_hook(res.get("text") or "")
    res["mutter"], res["text"] = _split_mutter(res["text"])
    return res


_MUTTER_MAX = 60


def _split_mutter(text: str) -> tuple[str, str]:
    """맨 마지막 줄의 `혼잣말: …` 을 떼어 낸다. 없으면 빈 문자열.

    🛑 모델이 안 붙일 수도 있다. 그때는 빈 혼잣말과 본문 그대로를 준다 —
       화면은 지금까지처럼 정해 둔 혼잣말로 떨어진다.
    """
    lines = (text or "").rstrip().split("\n")
    for i in range(len(lines) - 1, max(-1, len(lines) - 4), -1):
        line = lines[i].strip()
        if not line.startswith("혼잣말:"):
            continue
        say = line[len("혼잣말:"):].strip()
        say = say.strip("\u300c\u300d\"' ")
        if not say or len(say) > _MUTTER_MAX + 20:
            return "", text
        rest = "\n".join(lines[:i]).rstrip()
        return say[:_MUTTER_MAX + 20], rest
    return "", text

_HOOK_MAX = 20          # 화면 한 줄에 들어가는 길이


def _split_hook(text: str) -> tuple[str, str]:
    """맨 첫 줄의 `제목: …` 을 떼어 낸다.

    🛑 모델이 안 붙일 수도 있다. 그때는 빈 제목과 본문 그대로를 준다 —
       화면은 본래 제목으로 떨어진다.
    """
    body = text.lstrip()
    if not body.startswith("제목:"):
        return "", text
    line, _, rest = body.partition("\n")
    hook = line[len("제목:"):].strip().strip("「」\"' .")
    # 너무 길면 제목이 아니라 본문 첫 줄을 잘못 쓴 것이다. 그때는 안 쓴다
    if not hook or len(hook) > _HOOK_MAX + 8:
        return "", text
    return hook[:_HOOK_MAX + 8], rest.lstrip()


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
    #    🛑 **항목이 셋 이하면 순차로 쓴다** (2026-09-11 실측). 오늘의 운세는 항목이
    #       셋인데 재료가 「오늘 일진」 하나뿐이라, 한꺼번에 던지면 서로 뭘 쓰는지 몰라
    #       셋이 거의 같은 말을 한다 — 실제로 세 항목이 전부 「말이 뾰족하게 나간다」로
    #       나왔다. 스물 중 둘이 겹치는 것(10%)과 셋 중 둘이 겹치는 것(66%)은
    #       손님에게 전혀 다른 일이다. 짧은 편은 겹침이 곧 전부다.
    if len(sections) <= 3:
        workers = 1

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
            d = out.get(t) or {}
            txt = d.get("text") or ""
            if txt:
                # 🛑 **LLM 이 쓴 제목**을 넘긴다. 본래 제목만 넘기면 제목끼리 겹친다 —
                #    2026-09-09 실측에서 「남의 짐까지 다 지고 서 있는 버릇」과
                #    「남의 짐까지 지고 계시죠」가 한 편에 같이 나왔다.
                wrote.append((d.get("hook") or t, _first_sentence(txt)))
        start += size
        # 🛑 순차로 가기로 했으면 계속 하나씩이다. 여기서 키우면 셋째 항목이
        #    둘째를 못 보고, 순차로 쓰는 뜻이 사라진다
        if workers > 1:
            size = min(size * 2, _WAVE_MAX)         # 🛑 상한을 둔다. 동시 호출이 너무 늘면 막힌다

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
                       # 화면에 보이는 제목. 비어 있으면 본래 제목을 쓴다
                       "hook": d.get("hook", ""),
                       # 항목 끝에 붙는 무냥이 혼잣말 (2026-09-09 온해님 지시)
                       "mutter": d.get("mutter", ""),
                       "left": d.get("left") or []})
    return {"model": model or MODEL, "blocks": blocks,
            "tokens": {"in": tin, "out": tout}, "fixed": fixed, "errors": errs}


# ── 한 번 쓴 글은 남겨 둔다 ──────────────────────────────────
# 같은 사람이 같은 상품을 다시 열 때마다 새로 뽑으면 글이 매번 달라져서
# 「아까 그 문장이 없어졌다」가 된다. 돈도 두 번 나간다.

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

# 🛑 **날마다 값이 바뀌는 상품** (2026-09-11 온해님). 여기 있는 상품은 그날 쓴 글만
#    쓴다. 저장 키가 `상품|사주` 뿐이라, 이걸 안 두면 어제 쓴 글이 내년까지 그대로
#    나온다 — 「오늘의 운세」에서 그건 상품이 거짓말을 하는 것이다.
# 🛑 파일 이름에 날짜를 붙이지 않는다. 그러면 사람마다 날마다 파일이 하나씩 쌓인다.
#    같은 파일을 덮어쓰고 **안에 적힌 날짜**로 가른다.
DATED = {"today"}


def _day() -> str:
    return time.strftime("%Y-%m-%d")


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
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # 🛑 어제 쓴 「오늘의 운세」는 오늘 것이 아니다. 없는 셈 치면 새로 쓴다
    if product in DATED and str(data.get("day") or "") != _day():
        return None
    return data


def save(product: str, pair: str, data: dict[str, Any]) -> None:
    p = _path(product, pair)
    data = dict(data)
    if product in DATED:
        data["day"] = _day()
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
    # 🛑 **card·summary 를 함께 남긴다.** 전에는 blocks 만 남기고 덮어써서,
    #    글을 이어 쓸 때마다 카드 문구가 사라지고 다시 만들어졌다 (0.5원씩).
    data = {k: v for k, v in (old or {}).items() if k in ("card", "summary")}
    data["blocks"] = list(by.values())
    data["ver"] = WRITE_VER
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
- 🛑 **손님이 물은 것에 답해라.** 위에 물음이 적혀 있으면 그 물음의 답으로 두 줄을 쓴다.
  풀이 과정·생김새를 늘어놓지 마라. 카드를 본 사람이 「나는 어떤 답일까」 싶어야 한다.
- 🛑 **물음을 되풀이하지 마라.** 「~가 드러나요」 「~에 묻어 나와요」 「~가 또렷해져요」
  처럼 **무엇인지 말하지 않고** 넘어가면 답이 아니다. 어떤 사람인지·무엇이
  되풀이되는지를 **그 자리에서 말해라.** 재료에 그게 없으면 헛말로 채우지 말고
  재료에 있는 것만 쓴다.

[좋은 예]
겉으로는 다 받아 주면서 속으로 명단을 적어 두는 사람이에요. 그 명단이 길어지면 조용히 문을 닫죠.
먼저 연락하는 법이 없어요. 기다리는 게 편한 게 아니라, 먼저 손 내미는 법을 안 배운 거예요.

[나쁜 예 — 이렇게 쓰지 마라]
당신은 갑목 일간으로 인성이 강한 사주입니다.  (용어)
좋은 기운이 함께하니 힘내세요.  (훈훈한 마무리)"""


def _cut_sentence(t: str, n: int) -> str:
    """길이를 맞추되 **문장 중간에서 끊지 않는다** (2026-09-10 온해님이 잡으심).

    전에는 `txt[:90]` 으로 잘랐다. 그래서 카드에 **「…구경만 했어요. 나라」**처럼
    뜻 없는 조각이 박혔다. 카드는 손님이 스크린샷을 찍어 퍼뜨리는 물건이라
    그 조각이 그대로 돌아다닌다.
    """
    import re as _re
    t = " ".join((t or "").split())
    if len(t) <= n:
        return t
    head = t[:n]
    ends = list(_re.finditer(r"[.!?](?:\s|$)", head))
    if ends and ends[-1].end() > n * 0.4:
        return head[:ends[-1].end()].strip()
    # 문장 끝을 못 찾으면 어절 단위로라도 끊는다
    i = head.rfind(" ")
    return (head[:i] if i > n * 0.5 else head).strip()


def summarize(blocks: list[dict[str, Any]], *, question: str = "",
              model: str | None = None) -> str:
    """리포트를 읽고 카드에 넣을 두 줄을 뽑는다."""
    src = []
    # 🛑 **앞 세 항목만 보지 않는다** (2026-09-10). 마지막 자리가 대개 종합이라
    #    손님이 물은 것의 답은 거기 있다.
    for b in (blocks[:2] + blocks[-1:] if len(blocks) > 2 else blocks):
        t = (b.get("text") or "").strip()
        if t:
            src.append(t[:900])
    if not src:
        return ""
    user = "[결과지]\n" + "\n\n".join(src)
    # 🛑 **물음을 같이 준다** (2026-09-10 온해님). 카드 제목이 상품의 질문인데
    #    그걸 모른 채 요약하면 엉뚱한 답이 붙는다. 손님은 카드에서 질문과 답을
    #    나란히 보고 「나는 어떤 답일까」 싶어서 QR 을 찍는다.
    if question:
        user = ("[손님이 물은 것 — 이 물음에 답해야 한다]" + chr(10)
                + question.strip() + chr(10) + chr(10) + user)
    # 🛑 한 번은 다시 시킨다 (2026-09-10 온해님 「어김없이 나와야 해」).
    #    여기서 빈 값이 나가면 복채를 낸 손님의 카드에 두 줄이 통째로 빈다.
    txt = ""
    for _ in range(2):
        try:
            res = _call(_P('summary', SUMMARY_SYSTEM), user, model=model,
                        temperature=0.9, max_tokens=300)
            txt = " ".join((res.get("text") or "").split())
        except Exception:                            # noqa: BLE001
            txt = ""
        if txt:
            break
    return _cut_sentence(txt, 90)


# ── 공유 카드 문구 ────────────────────────────────────────
# 왜: 카드가 **표에서 조각을 꺼내 이어 붙이는** 구조라 「조용히 굴리던 뱃짐장수」처럼
# 뜻이 안 통하는 이름이 나왔다 (2026-09-09 온해님 「이게 무슨 뜻인지 너는 알아?」).
#
# 🛑 **계산을 LLM 에게 맡기지 않는다.** 어느 십성·오행·십이운성·신살에서 나왔는지는
#    그대로 우리가 정하고, **말만 다듬게** 한다. 그래야 「왜 이 답인지」가 계속 성립한다.
# 🛑 실패하면 빈 dict 를 준다. 화면은 표로 떨어져 그대로 나온다 — 대비책을 없애지 않는다.

CARD_SYSTEM = """너는 사주 상담 사이트 로드로그의 무냥이다. 공유 카드에 들어갈 짧은 글을 쓴다.

[써야 할 것 — JSON 하나만 내놓는다. 다른 말은 쓰지 마라]
{"name": "…", "line": "…", "tale": "…"}
  name  🛑 열두 자를 넘기지 마라. 쓰고 나서 세어 보고 넘으면 줄여라.
        「어떤 사람이었나 + 무슨 일을 했나」가 한눈에 들어와야 한다
        꾸밈말을 두 번 겹치지 마라 — 「가장 높이 올랐던 글 읽던 사람」처럼 되면 안 된다
  line  스무 자 안쪽. 그 사람이 어떻게 살았는지. 끝에 마침표를 찍지 마라
  tale  두 문장. 그 전생이 지금 나에게 무엇을 남겼는지로 닫는다

[🛑 재료에 「손님이 물은 것」이 있으면 — 가장 중요하다]
  line 과 tale 은 **그 물음의 답**이어야 한다. 2026-09-10 에 「나는 어떤 사람에게
  끌리고 어떤 사람이 나에게 올까?」를 묻는 카드에 「둥근 눈매 아래 살집이
  도톰해요」가 붙어 나갔다. 생김새를 늘어놓지 말고 **물음에 답해라.**
  카드를 본 사람이 「나한테는 어떤 답이 나올까」 싶어야 QR 을 찍는다.
  🛑 line 과 tale 에 **같은 말을 두 번 쓰지 마라** — 「도톰한 살집」이 두 번 나왔다.
  🛑 **물음을 되풀이하지 마라.** 2026-09-10 에 「어떤 사람에게 끌릴까?」를 묻는 카드에
     「끌리는 이와 찾아올 사람의 태도가 얼굴선에 묻어 나와요」가 나왔다. 이건
     **어떤 사람인지를 안 말한 것**이라 답이 아니다. 「~가 드러나요」 「~에 묻어
     나와요」로 넘어가지 말고 **무엇인지 그 자리에서 말해라.** 재료에 그게 없으면
     헛말로 채우지 마라.

[🛑 「관상」이면 — 지난 일이 아니라 **지금 얼굴**이다]
  현재형으로 쓴다. 「~던 삶」·「그때의 눈빛」처럼 지난 일로 쓰지 마라.
  name  지금 그 사람을 한마디로 부르는 말 (예: 먼저 웃어 주는 얼굴)
  line  지금 어떻게 보이는지
  tale  그 얼굴이 사람들 사이에서 어떻게 작용하는지. 지금 일로 닫는다

[🛑 재료에 「정해진 이름」이 있으면]
  그 이름을 name 에 **그대로** 쓴다. 한 글자도 바꾸지 마라.
  실제로 모시는 신의 이름이라 지어내면 안 된다. line 과 tale 만 새로 쓴다.

[🛑 카드는 **퍼뜨리라고 만든 것**이다 (2026-09-10 온해님)]
손님이 스크린샷을 찍어 친구에게 보낼 두세 줄이어야 한다.
밋밋하면 아무도 안 보낸다 — **자극적이고 재미있게, 한 대 치고 끝낸다.**
재료에 「상위 몇 %」가 있으면 **그 숫자를 그대로 카드에 넣는다.** 눈에 확 들어온다.
🛑 없는 숫자를 지어내지 않는다. 재료에 있는 %만 쓴다.
🛑 외모 비하가 아니라 상황·성향을 웃긴다.

[🛑 하지 않는 것 — 하나라도 어기면 다시 쓴다]
1. 재료에 없는 것을 보태지 않는다. 없는 사건·이름·지명을 지어내지 않는다
2. 사주 용어를 쓰지 않는다 — 편재·화개·십이운성·양(養) 같은 말 금지
3. 이모지·느낌표를 쓰지 않는다
4. 목적어 없는 서술어로 이름을 짓지 않는다.
   🛑 「조용히 굴리던 뱃짐장수」처럼 뒤의 직업이 목적어로 읽히면 안 된다
5. 좋은 말로 훈훈하게 맺지 않는다
6. 말투는 「~해요」. 단정하지 않는다 — 「그렇게 보여요」"""

# 🛑 **전생 카드 전용 페르소나** (2026-09-10 온해님이 그대로 주신 지시문).
#    카드가 스레드·인스타로 퍼져야 손님이 온다. 잔잔하면 아무도 안 퍼뜨린다.
PAST_SYSTEM = """너는 2030 여성들의 심리와 연애/인간관계 밈(Meme)을 완벽하게 파악하고 있는 \
'위트 있고 뼈 때리는 도사' 페르소나야.
유저의 생년월일시와 사주 데이터를 바탕으로 전생 유형을 분석하되, 잔잔하거나 진지한 표현 대신 \
현대적인 밈과 유머를 결합해서 출력해줘.

주요 규칙:
1. 메인 타이틀(title): 역사 속 직업이 아닌, 현대인의 성향과 연결되는 위트 있는 밈 타이틀로 작성할 것
   (예: "조선의 은둔 재벌", "방구석 도령", "주막 호구 삼돌이")
2. 소제목(subtitle): 15자 이내로 팩트를 유쾌하게 찌르는 한 줄
3. 3가지 키워드 (type_job, habit, karma):
   - 전생의 특징/직업
   - 현생까지 남은 웃픈 버릇
   - 전생이 남긴 억울한 업보/현타 포인트
4. 한 줄 요약(summary): 유저가 보자마자 "ㅋㅋㅋ 이거 완전 나잖아?" 하고 공감하며 \
스토리/스레드에 공유하고 싶어지는 뼈 때리는 2~3문장

[🛑 우리 쪽에서 지킬 것]
· 화자는 로드로그의 **무냥이**다. 말끝은 「~해요」로 맺는다
· 🛑 **받은 재료에 없는 것을 지어내지 않는다.** 없는 사건·지명·숫자를 만들지 마라.
  재료가 곧 그 사람의 전생이고, 카드 밖 결과지에도 같은 내용이 적혀 있다
· 🛑 **사주 용어를 쓰지 않는다** — 편재·화개·십이운성·양(養)·공망 같은 말 금지
· 🛑 **이모지·느낌표를 쓰지 않는다.** 카드는 그림으로 그려지는데 이모지가 깨진다
  (규칙 4의 「ㅋㅋㅋ」은 손님의 반응을 적은 것이지 글에 쓰라는 말이 아니다)
· 🛑 **외모 비하가 아니라 상황·성향을 웃긴다**
· 🛑 keywords 세 칸은 **열여덟 자를 넘기면 카드에서 잘린다.** 짧게 끊어라
· 세 칸과 summary 에 **같은 말을 두 번 쓰지 마라**"""

# 🛑 **수호신 카드 전용 페르소나** (2026-09-10 온해님이 그대로 주신 지시문).
#    가챠 인증 카드라, 손님이 스크린샷을 올려 서로 등급을 견주게 만드는 것이 목적이다.
GOD_SYSTEM = """너는 2030 여성들의 심리와 게임/연애 밈(Meme)에 통달한 \
'위트 있고 뼈 때리는 도사' 페르소나야.
유저의 사주 데이터를 바탕으로 수호신 결과를 뽑되, 진지한 무속 용어 대신 현지화된 밈과 \
위트 있는 표현으로 구성해줘.

[수호신 등급 시스템]
- S급: 인생을 멱살 잡고 하드캐리해 주는 최강 수호신
- A급: 똥차나 사기꾼을 귀신같이 걸러주는 팩폭형 수호신
- B급: 큰 재물은 못 줘도 소소한 액운을 막아주는 방어형 수호신
- C급/D급: 유저가 사고 칠 때 옆에서 같이 당황하거나 어리버리 타는 웃픈 수호신

주요 규칙:
1. rank: S급, A급, B급, C급, D급 중 하나 선택
2. title: 수호신의 이름과 현대적 별명 (예: "S급 | 멱살 견인 전문 대신할머니")
3. subtitle: 20자 이내의 유쾌한 수호신 능력 요약 (예: "내 똥고집과 액운까지 멱살 잡고 견인 중")
4. left_god / right_god / animal: 좌측/우측 보조 신과 띠 짐승 이름
5. summary: 유저가 스토리에 올려서 "나 S급 수호신 떠서 인생 하드캐리 당하는 중 ㅋㅋㅋ" 하고 \
자랑하거나 공감할 수 있는 2~3문장 (유저의 현재 상황과 수호신의 케미를 유머러스하게 표현)

[🛑🛑 지어내면 안 되는 것 넷 — 이건 이미 정해져서 온다]
1. **등급**은 재료의 「정해진 등급」이 전부다. 사주 284,892가지를 다 세어서 낸 값이고
   화면에도 같은 등급이 떠 있다. **올리지도 내리지도 마라.** 어기면 손님 화면에
   S급이라고 떠 있는데 카드에는 B급이 박힌다
2. **신 이름**(정해진 이름)·**왼쪽에 서는 이**·**오른쪽에 서는 이**·**짐승**은
   실제로 모시는 신명이라 지어내면 안 된다. 재료에 온 이름을 **한 글자도 바꾸지 마라**
   (최영 장군·바리공주·용왕·삼신할머니 같은 이름이다)
🛑 별명은 지어도 된다. **이름을 바꾸지 말라는 것**이지 별명을 붙이지 말라는 게 아니다.

[🛑 우리 쪽에서 지킬 것]
· 화자는 로드로그의 **무냥이**다. 말끝은 「~해요」로 맺는다
· 🛑 **받은 재료에 없는 것을 지어내지 않는다**
· 🛑 **사주 용어를 쓰지 않는다** — 십성·오행·신살·공망 같은 말 금지.
  「몸주」·「좌보」·「우필」도 금지다. 손님이 모르는 말이다
· 🛑 **이모지·느낌표를 쓰지 않는다.** 카드는 그림으로 그려지는데 이모지가 깨진다
  (규칙 5의 「ㅋㅋㅋ」은 손님의 반응을 적은 것이지 글에 쓰라는 말이 아니다)
· 🛑 **낮은 등급이어도 손님을 깎지 않는다.** C급·D급은 **수호신이 어리바리한 것**이지
  손님이 못난 게 아니다. 웃기는 대상은 신이고, 손님은 같이 웃는 편이다
· subtitle 과 summary 에 **같은 말을 두 번 쓰지 마라**"""

# 🛑🛑 **카드 규격 판.** 규격을 바꾸면 이 수를 올린다 (2026-09-10).
#    카드 문구는 한 번 만들면 결과지 옆에 저장되고 다시 안 만든다 — 다시 열 때마다
#    이름이 바뀌면 「내 전생은 ○○이었다」가 흔들리기 때문이다. 그런데 그 규칙 때문에
#    **규격을 바꿔도 이미 열어 본 사주는 영원히 옛 문구가 나왔다.**
#    2026-09-10 에 전생·수호신 카드를 밈 규격으로 갈았는데 화면에는 옛 글이 그대로
#    나왔다 — 온해님이 「똑같이 나오는데?」로 잡으셨다.
#    판이 낮으면 서버가 한 번만 다시 만든다 (0.5원). 그 뒤로는 다시 고정된다.
CARD_VER = 2

# 🛑🛑 **본문 글의 판.** 말투나 얼개를 바꾸면 이 수를 올린다 (2026-09-10).
#    항목은 한 번 쓰면 저장하고 다시 안 쓴다 — 손님이 다시 열 때 글이 바뀌면
#    안 되기 때문이다. 그런데 그 규칙 때문에 **프롬프트를 바꿔도 이미 저장된
#    리포트는 영원히 옛 글이 나왔다.**
#    2026-09-10 에 해설을 「팩트폭격」 말투로 갈았는데 화면에는 진지한 옛 글이
#    그대로 나왔다 — 온해님이 「예전이랑 달라진게 없어」로 잡으셨다.
#    🛑 관상은 `GWAN_VER` 로 이미 같은 장치를 쓰고 있었다. 사주 본문에만 없었다.
WRITE_VER = 2

# 🛑 `badge` 는 계산된 「상위 몇 %」다. 카드에 크게 박을 수 있다 (2026-09-10)
#    `job`·`habit`·`karma` 는 전생 카드의 세 칸이다 (다른 상품에는 안 온다)
_CARD_KEYS = ("name", "line", "tale", "badge", "job", "habit", "karma", "nick", "rank")
_CARD_MAX = {"name": 24, "line": 40, "tale": 200, "badge": 24,
             "job": 22, "habit": 22, "karma": 22, "nick": 16, "rank": 4}

# 🛑 이 이름으로 들어오는 재료는 **글**이라 길게 준다. 나머지는 80자면 넉넉하다.
#    새 재료 이름을 쓰면 여기에도 넣을 것 — 안 넣으면 조용히 80자로 잘린다.
_FACT_MAX = {"관멍이가 쓴 글": 2400, "무냥이가 쓴 글": 2400,
             "상위 몇 %": 90,
             "결과지": 2400, "손님이 물은 것": 200}


def write_card(kind: str, facts: dict[str, str], *,
               model: str | None = None) -> dict[str, str]:
    """계산에서 나온 재료를 주고 카드 문구를 받는다. 못 쓰면 빈 dict."""
    # 🛑 **글 재료를 80자에서 자르면 안 된다** (2026-09-10 온해님 전수검사).
    #    서버가 자리마다 걷어 1,800자를 넘기는데 여기서 80자로 잘려 들어갔다.
    #    80자면 첫 자리의 첫 문장뿐이라, 「어떤 사람에게 끌릴까?」를 묻는 카드에
    #    얼굴 생김새가 답으로 나왔다. 이름·값 같은 짧은 재료만 80자로 둔다.
    rows = [f"  {k} : {str(v).strip()[:_FACT_MAX.get(k, 80)]}"
            for k, v in (facts or {}).items() if str(v or "").strip()]
    if not rows:
        return {}
    user = ("[무엇에 대한 카드인가] " + (kind or "전생") + "\n"
            "[받은 재료]  ← 계산에서 나온 것. 이것 말고는 아무것도 모른다\n"
            + "\n".join(rows[:8]))
    # 🛑 실패하면 화면이 **조용히 옛 방식**(글을 잘라 쓰기)으로 떨어진다.
    #    2026-09-10 전수검사에서 서른여섯 중 하나가 그렇게 빈 값으로 나왔다.
    #    한 번은 다시 시킨다 — 0.5원이고, 떨어지면 카드가 딴 얘기를 한다.
    # 🛑 전생은 규격이 다르다 — 세 칸짜리 표를 LLM 이 채운다 (2026-09-10 온해님)
    k = str(kind or "").strip()
    past, god = k in ("past", "전생"), k in ("god", "수호신")
    sysmsg = (_P('past', PAST_SYSTEM) if past
              else _P('god', GOD_SYSTEM) if god
              else _P('card', CARD_SYSTEM))
    schema = PAST_CARD_SCHEMA if past else GOD_CARD_SCHEMA if god else CARD_SCHEMA
    res = None
    for _ in range(2):
        try:
            res = _call(sysmsg, user, model=model, temperature=1.0,
                        max_tokens=600 if (past or god) else 400, schema=schema)
            break
        except Exception:                                # noqa: BLE001
            res = None
    if res is None:
        return {}
    txt = (res.get("text") or "").strip()
    # ```json 울타리를 걷어낸다. 모델이 자주 붙인다
    if txt.startswith("```"):
        txt = txt.split("```")[1] if "```" in txt[3:] else txt[3:]
        txt = txt[4:] if txt.lower().startswith("json") else txt
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j <= i:
        return {}
    try:
        got = json.loads(txt[i:j + 1])
    except Exception:                                    # noqa: BLE001
        return {}
    # 🛑 온해님이 정한 칸 이름을 우리 칸으로 옮긴다 (2026-09-10).
    #    화면(`main.js`)은 name·line·tale 을 읽는다. 규격만 바뀌고 화면은 그대로다.
    kw = got.get("keywords") if isinstance(got.get("keywords"), dict) else {}
    got = {
        "name": got.get("title") or got.get("name") or "",
        # 전생은 subtitle, 나머지는 one_liner 가 한 줄이다
        "line": got.get("subtitle") or got.get("one_liner") or got.get("line") or "",
        "tale": got.get("summary") or got.get("tale") or "",
        "badge": got.get("highlight_badge") or "",
        "job": kw.get("type_job") or "",
        "habit": kw.get("habit") or "",
        "karma": kw.get("karma") or "",
        "nick": got.get("nick") or "",
        # 🛑 등급은 아래에서 **계산값으로 덮어쓴다.** 여기 값은 참고일 뿐이다
        "rank": got.get("rank") or "",
    }
    out = {}
    # 🛑 정해진 이름은 **코드가 박는다.** 프롬프트로만 시키면 모델이 손댄다
    fixed = str((facts or {}).get("정해진 이름") or "").strip()
    for k in _CARD_KEYS:
        v = " ".join(str(got.get(k) or "").split())
        # 🛑 이름·한 줄은 끝 마침표를 뗀다. 모델이 들쭉날쭉 붙여서 카드가 지저분해진다
        if k in ("name", "line", "job", "habit", "karma"):
            v = v.rstrip(" .。")
        if v:
            out[k] = v[:_CARD_MAX[k]]
    if fixed:
        out["name"] = fixed[:_CARD_MAX["name"]]
    # 🛑 **등급은 계산이 정한다.** 재료로 준 값을 그대로 덮어쓴다 — LLM 이 한 글자라도
    #    다르게 쓰면 화면 눈금과 카드가 어긋나고, 손님은 그걸 바로 알아본다.
    rank = str((facts or {}).get("정해진 등급") or "").strip()
    if rank:
        out["rank"] = rank[:_CARD_MAX["rank"]]
    # 🛑 별명이 신 이름을 삼켜 버리면 카드에 이름이 두 번 나온다. 떼어 낸다
    if out.get("nick") and fixed:
        out["nick"] = out["nick"].replace(fixed, "").strip(" ·|-")
        if not out["nick"]:
            out.pop("nick")
    # 이름과 한 줄이 둘 다 있어야 쓸 수 있다. 하나만 오면 표가 낫다
    if not (out.get("name") and out.get("line")):
        return {}
    out["ver"] = CARD_VER
    return out


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

[🛑 여기서 제일 중요한 것 — 재미있어야 한다]
2026-09-11 온해님 지시다. **채팅하면서 재미가 있어야 손님이 등불을 또 쓴다.**
한 번 물어보고 「그렇군요」로 끝나면 두 번째 물음이 없다.

- **팩트폭격 세 박자로 간다** — ① 뼈 때리는 한 줄 ② 찰진 비유 ③ 유쾌한 반전.
  리포트와 같은 말투인데, 대화는 더 짧으니 **더 세게** 간다.
- **첫 문장을 후려친다.** 「손가락 멈추세요, 지금 연락하면 이불킥 예약이에요」처럼.
  「~일 수 있어요」로 시작하면 그 대화는 거기서 끝난다.
- **손님이 실제로 하고 있을 짓을 그린다.** 새벽에 차단 목록 열었다 닫았다,
  장바구니 띄워 놓고 리뷰 맨 뒷장까지 훑기, 프로필 음악 바뀐 것 확인하기.
  손님이 「어떻게 알았지」 하고 웃어야 다음 물음이 나온다.
- **밈·유행어를 써도 된다.** 「~냥」 말끝도 된다.
- **마지막은 오늘 당장 할 수 있는 한 가지로 닫는다.** 훈계 말고 행동으로.

🛑 **웃기는 것과 얼버무리는 것은 다르다.** 답은 첫 문장에 있어야 한다.
🛑 **외모를 비하하지 않는다.** 웃기는 대상은 상황과 버릇이지 사람이 아니다.
🛑 **이모지·느낌표는 쓰지 않는다.** 글로 웃긴다.

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
    res = _call(_P('ask', ASK_SYSTEM), user, model=model, max_tokens=900)
    bad = check_counts(res["text"], saju)
    if bad:
        # 개수를 틀리면 한 번만 다시. 리포트와 같은 방식이다.
        fix = user + ("\n\n[다시 쓴다]\n개수를 틀렸다: %s\n[사주]에 적힌 대로만 옮겨라."
                      % " / ".join(bad))
        res2 = _call(ASK_SYSTEM, fix, model=model, temperature=0.7, max_tokens=900)
        res2["in"] += res["in"]; res2["out"] += res["out"]
        res = res2
    return res
