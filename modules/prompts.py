# -*- coding: utf-8 -*-
"""무냥이·관멍이가 쓰는 말투를 **코드를 안 건드리고** 고친다 (2026-09-11 온해님).

> Gemini API 톤앤매너(매운맛/밈)를 코드 수정 없이 관리자 창에서 바로 수정·테스트할 수
> 있는 '프롬프트 관리' 기능이 필수적입니다.

말투를 한 번 바꾸려고 배포를 돌리면 손이 많이 가고, 되돌리기도 배포다.
여기서는 **고친 것만** 파일에 얹어 두고, 코드에 적힌 것은 기본값으로 남긴다.

  · 고친 적이 없으면            → 코드 기본값
  · 관리자 화면에서 고쳤으면      → 그 값
  · 「기본값으로 되돌리기」를 누르면 → 얹어 둔 것을 지운다 (기본값이 다시 산다)

🛑 **캐시하지 않는다.** 고치자마자 다음 글부터 바뀌어야 한다. 파일이 작아서
   매번 읽어도 부담이 없다.
🛑 **이미 써 둔 글은 안 바뀐다.** 리포트는 한 번 쓰면 저장하고 다시 안 쓴다.
   말투를 바꾸면 **그 뒤에 새로 쓰는 글부터** 달라진다 — 화면에도 그렇게 적어 둔다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

FILE = "prompts.json"


def _path() -> Path:
    return Path(os.getenv("DATA_DIR") or ".") / FILE


def _read() -> dict[str, Any]:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        return {}


def _write(d: dict[str, Any]) -> None:
    f = _path()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 무엇을 고칠 수 있나 ────────────────────────────────
# 🛑 `base` 는 **함수로 받는다.** 모듈을 곧바로 import 하면 서로 물려 돌아간다
#    (saju_writer 가 이 파일을 쓰고, 이 파일이 saju_writer 를 보게 되므로).
SPEC: list[dict[str, Any]] = [
    {"key": "saju", "name": "사주 해설",
     "why": "손님이 읽는 글의 대부분이 여기서 나옵니다. 팩트폭격 세 박자가 들어 있어요.",
     "mod": "saju_writer", "attr": "SYSTEM"},
    {"key": "card", "name": "공유 카드 문구",
     "why": "스레드·인스타에 퍼지는 카드의 이름·한 줄·이야기입니다.",
     "mod": "saju_writer", "attr": "CARD_SYSTEM"},
    {"key": "past", "name": "전생 카드",
     "why": "전생 카드 전용. 밈 타이틀과 세 칸(직업·버릇·업보)을 씁니다.",
     "mod": "saju_writer", "attr": "PAST_SYSTEM"},
    {"key": "god", "name": "수호신 카드",
     "why": "수호신 카드 전용. 가챠 등급과 별명을 씁니다. 🛑 등급은 계산이 정합니다.",
     "mod": "saju_writer", "attr": "GOD_SYSTEM"},
    {"key": "summary", "name": "카드 두 줄 요약",
     "why": "카드 맨 아래 두 줄. 결과지를 읽고 뽑습니다.",
     "mod": "saju_writer", "attr": "SUMMARY_SYSTEM"},
    {"key": "ask", "name": "무냥이 대화",
     "why": "리포트를 읽고 더 물어볼 때 답하는 말투입니다. 등불을 쓰는 자리예요.",
     "mod": "saju_writer", "attr": "ASK_SYSTEM"},
    {"key": "gwan_ask", "name": "관멍이 대화",
     "why": "관상 결과를 두고 더 물어볼 때 답하는 말투입니다.",
     "mod": "gwansang", "attr": "ASK_SYSTEM"},
    {"key": "gwan", "name": "관상 해설",
     "why": "관멍이가 얼굴 사진을 보고 쓰는 글입니다.",
     "mod": "gwansang", "attr": "SYSTEM"},
    {"key": "intent", "name": "무엇에 등불을 받나",
     "why": "손님이 쓴 말이 봐 달라는 것인지 그냥 건네는 말인지 가릅니다. "
            "🛑 봐 달라는 것으로 갈리면 등불 30개가 나갑니다.",
     "mod": "intent", "attr": "SYSTEM"},
    {"key": "small", "name": "가벼운 말 받기",
     "why": "인사·잡담에 짧게 답하는 말투입니다. 여기서는 등불을 안 받아요.",
     "mod": "intent", "attr": "SMALL_SYSTEM"},
]
_BY = {x["key"]: x for x in SPEC}


def _base(key: str) -> str:
    """코드에 적힌 기본값. 못 읽으면 빈 문자열."""
    spec = _BY.get(key)
    if not spec:
        return ""
    try:
        mod = __import__("modules.%s" % spec["mod"], fromlist=["*"])
        return str(getattr(mod, spec["attr"], "") or "")
    except Exception:                                    # noqa: BLE001
        return ""


def get(key: str) -> str:
    """지금 쓸 값. 고친 것이 있으면 그것, 없으면 코드 기본값."""
    got = _read().get(key)
    if isinstance(got, dict):
        got = got.get("text")
    text = str(got or "").strip()
    return text or _base(key)


def use(key: str) -> Callable[[], str]:
    """호출부에서 `use('saju')()` 로 쓴다 — 부를 때마다 새로 읽는다."""
    return lambda: get(key)


def put(key: str, text: str, *, who: str = "") -> dict[str, Any]:
    if key not in _BY:
        raise ValueError("없는 프롬프트입니다.")
    text = str(text or "").strip()
    if len(text) < 40:
        raise ValueError("너무 짧습니다. 지우려면 「기본값으로 되돌리기」를 쓰세요.")
    if len(text) > 20000:
        raise ValueError("너무 깁니다.")
    import time
    d = _read()
    d[key] = {"text": text, "at": time.strftime("%Y-%m-%d %H:%M"), "by": who}
    _write(d)
    return d[key]


def reset(key: str) -> None:
    d = _read()
    if key in d:
        d.pop(key)
        _write(d)


def listing() -> list[dict[str, Any]]:
    """관리자 화면이 그릴 목록. 기본값과 지금 값을 함께 준다."""
    saved = _read()
    out = []
    for spec in SPEC:
        k = spec["key"]
        got = saved.get(k) or {}
        base = _base(k)
        out.append({
            "key": k, "name": spec["name"], "why": spec["why"],
            "base": base,
            "text": str(got.get("text") or "").strip() or base,
            "edited": bool(str(got.get("text") or "").strip()),
            "at": got.get("at") or "", "by": got.get("by") or "",
        })
    return out
