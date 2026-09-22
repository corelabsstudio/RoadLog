"""무냥이 저주 신단 결과 생성과 재조회 보관함."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR
from modules import saju_writer

PRODUCT_ID = "curse"
_FILE = Path(DATA_DIR) / "curse_results.json"
_LOCK = threading.RLock()
_MAX_PER_USER = 40

FREE_SCHEMA = {
    "type": "object",
    "properties": {
        "card_title": {"type": "string", "description": "뽑힌 카드의 별명. 14자 안쪽"},
        "verdict": {"type": "string", "description": "소심하고 킹받는 저주 한 문장. 34자 안쪽"},
        "reading": {"type": "string", "description": "왜 이 카드가 나왔는지 장난스럽게 푸는 2문장"},
        "tease": {"type": "string", "description": "상세 결과가 궁금해지는 한 문장. 36자 안쪽"},
    },
    "required": ["card_title", "verdict", "reading", "tease"],
}

DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "전체 결과 제목. 생년이 있으면 반드시 'XX년생 [별명]에게 내리는 저주' 형태"},
        "opening": {"type": "string", "description": "무냥이가 의식을 마친 뒤 건네는 몰입감 있는 3~4문장"},
        "curse": {"type": "string", "description": "실제 위해가 전혀 없는 생활형 불편 저주를 장면이 보이게 풀어 쓴 3~4문장"},
        "trigger": {"type": "string", "description": "이 저주가 발동하는 우스운 순간을 구체적으로 그린 3~4문장"},
        "duration": {"type": "string", "description": "지속 기간과 사그라드는 징조를 과장된 운세처럼 표현한 3~4문장"},
        "side_effect": {"type": "string", "description": "사용자에게 돌아오는 귀여운 부작용과 주의점을 담은 3~4문장"},
        "release": {"type": "string", "description": "마음을 놓아주는 현실적인 해제 의식을 이야기로 풀어 쓴 3~4문장"},
        "share_line": {"type": "string", "description": "친구에게 보내고 싶은 결과 한 줄. 32자 안쪽"},
    },
    "required": ["title", "opening", "curse", "trigger", "duration", "side_effect", "release", "share_line"],
}

_SYSTEM = """너는 Roadlog의 고양이 점술가 무냥이다. 한국어로 짧고 재치 있게 쓴다.
이 서비스는 오락용이다. 저주는 실제 주술이나 위해가 아니라 일상에서 은근히 킹받는
코믹한 불편이다. 죽음, 질병, 상해, 범죄, 협박, 차별, 성적 모욕, 개인정보 노출,
자해, 재산 피해는 절대 쓰지 않는다. 공포나 무속집 말투도 쓰지 않는다.
상대에게 행동하라고 시키거나 연락을 유도하지 않는다. 사용자의 분노는 인정하되
마지막에는 사용자가 자기 일상으로 돌아오게 한다. AI라는 말은 하지 않는다."""


def _payload(target_type: str, target_name: str, birth_date: str, reason: str, card: str,
             has_photo: bool = False) -> str:
    birth_year = birth_date[:4] + "년생" if birth_date else "모름"
    return (
        "대상 관계: %s\n대상 별명: %s\n대상 생년: %s\n봉인 사진: %s\n"
        "대상이 지은 죄와 사연: %s\n직접 뽑은 카드: %s\n"
        "생년이 있으면 결과 제목에 반드시 'XX년생 [별명]에게 내리는 저주'를 넣어라. "
        "사진이 있으면 비민감한 분위기만 의식 묘사에 가볍게 반영하되 신원, 나이, 인종, 건강, 성격 등은 추정하지 마라. "
        "위 재료 밖의 대상 신상이나 사실을 지어내지 마라."
        % (target_type[:30], target_name[:30] or "이름 모를 대상", birth_year,
           "제공됨" if has_photo else "없음", reason[:240], card[:40])
    )


def free_result(target_type: str, target_name: str, birth_date: str, reason: str, card: str,
                photo: str = "") -> dict[str, Any]:
    got = saju_writer._call(
        _SYSTEM,
        _payload(target_type, target_name, birth_date, reason, card, bool(photo))
        + "\n무료 결과를 써라. 가장 중요한 저주 한 줄은 바로 이해되고 캡처하고 싶어야 한다.",
        temperature=1.05, max_tokens=520, schema=FREE_SCHEMA, image_data=photo or None,
    )
    return json.loads(got["text"])


def detail_result(target_type: str, target_name: str, birth_date: str, reason: str, card: str,
                  photo: str = "", free: dict[str, Any] | None = None) -> dict[str, Any]:
    got = saju_writer._call(
        _SYSTEM,
        _payload(target_type, target_name, birth_date, reason, card, bool(photo))
        + "\n이미 보여 준 무료 결과: " + json.dumps(free or {}, ensure_ascii=False)[:900]
        + "\n같은 카드의 상세 결과를 써라. 무료 결과와 모순되지 말고 각 항목은 서로 다른 장면을 다뤄라."
        + " 저주 및 해설 내용은 단답형으로 끝내지 말고, 각 항목마다 최소 3~4문장의 풍부하고 몰입감 있는 주술적 스토리텔링으로 상세히 작성하라.",
        temperature=1.0, max_tokens=1900, schema=DETAIL_SCHEMA, image_data=photo or None,
    )
    return json.loads(got["text"])


def _read() -> dict[str, list[dict[str, Any]]]:
    if not _FILE.exists():
        return {}
    try:
        data = json.loads(_FILE.read_text("utf-8"))
    except Exception as exc:
        raise RuntimeError("저주 신단 결과 보관함을 읽지 못했습니다.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("저주 신단 결과 보관함 형식이 올바르지 않습니다.")
    return data


def _write(data: dict[str, list[dict[str, Any]]]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    tmp.replace(_FILE)


def get(email: str, ritual: str) -> dict[str, Any] | None:
    with _LOCK:
        for row in _read().get(email.lower(), []):
            if row.get("ritual") == ritual:
                return dict(row)
    return None


def save(email: str, ritual: str, pair: str, inputs: dict[str, str],
         free: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    row = {"ritual": ritual, "pair": pair, "at": int(time.time() * 1000),
           "inputs": inputs, "free": free, "detail": detail}
    with _LOCK:
        data = _read()
        rows = data.setdefault(email.lower(), [])
        rows[:] = [x for x in rows if x.get("ritual") != ritual]
        rows.append(row)
        del rows[:-_MAX_PER_USER]
        _write(data)
    return dict(row)
