# -*- coding: utf-8 -*-
"""결과지 글쓰기 안전장치 회귀 검사.

모델을 부르지 않는다. 숫자 대조와 경로 검사가 여전히 도는지만 본다.
2026-09-07 첫 시안에서 비겁 2개를 「셋이나」라고 쓴 적이 있어서 만들었다.
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import saju_writer as W          # noqa: E402

SAJU = {
    "연": "경오", "월": "신사", "일": "경진", "시": "계미", "일간": "경",
    "오행": {"목": 0, "화": 2, "토": 2, "금": 3, "수": 1},
    "십성": {"비겁": 2, "식상": 1, "재성": 0, "관성": 2, "인성": 2},
    "신살": ["화개"], "대운": "정축 (33세부터)", "성별": "여자",
}

# (문장, 걸려야 하는가)
CASES = [
    ("원국에 비겁이 셋이나 버티고 있는데", True),
    ("화 기운이 네 개나 되니", True),
    ("인성 4개가 몰려 있어요", True),
    ("사주에 금 기운만 셋인데", False),
    ("인성이 두 개 있어서", False),
    ("재성은 아예 없고요", False),
    ("일지에 진토가 앉아 있어요", False),
]

BAD_KEYS = ["../etc", "a b", "x" * 200, "", "a/b"]

fails = []

for text, should in CASES:
    hit = bool(W.check_counts(text, SAJU))
    if hit != should:
        fails.append("숫자 검사: %r → %s (기대 %s)"
                     % (text, "걸림" if hit else "통과", "걸림" if should else "통과"))

for key in BAD_KEYS:
    try:
        W._path(key, "abc123")
        fails.append("경로 검사: %r 가 통과했다" % key)
    except ValueError:
        pass

facts = W.facts(SAJU)
for must in ["금 3개", "재성", "화개", "경진"]:
    if must not in facts:
        fails.append("사실 목록에 %r 가 없다" % must)
if "목는" in facts or "목은" in facts:
    pass                     # 조사는 따지지 않는다
if "0개" in facts:
    fails.append("사실 목록에 「0개」가 들어갔다 — 없는 것은 '하나도 없다'로 적어야 한다")

if len(W.OPENERS) < 3 or len(W.CLOSERS) < 3:
    fails.append("형식 변주가 3가지 미만이다 — 항목이 다시 같은 틀로 찍힌다")

if fails:
    print("\n".join("  " + f for f in fails))
    print("\n%d 곳이 어긋났다" % len(fails))
    sys.exit(1)

print("글쓰기 안전장치 통과 — 숫자 대조 %d건 · 경로 %d건 · 형식 %d/%d가지"
      % (len(CASES), len(BAD_KEYS), len(W.OPENERS), len(W.CLOSERS)))
