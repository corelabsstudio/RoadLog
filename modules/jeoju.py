"""저주술사 무냥이 — 매운맛 7단계 저주 의식과 보관함.

2026-10-10 온해님 지시로 로드로그는 저주만 거는 사이트가 됐다.
옛 「저주 신단」(카드 뽑기)을 되살린 것이 아니라 새로 짠 것이다.

단계가 오를수록 **실제 저주 의식의 절차**가 하나씩 얹힌다 (온해님 「단계를 높일수록
점점 실제 저주와 유사하게」).

  1 간지럼맛   악담 한 줄
  2 순한맛     저주문 — 이름·죄목·바라는 일을 격식대로 적는다 (로마 저주판의 글 얼개)
  3 덜매운맛   부적 — 저주문을 넉 자로 줄여 붉은 부적에 쓰고 접어서 못으로 뚫는다
  4 오리지널   인형 — 이름·태어난 해를 적은 짚인형에 못 하나
  5 매운맛     축시 — 새벽 2시에 못을 박는다. 기록은 그 시각이 지나야 열린다
  6 아주매운맛 7일 밤 — 밤마다 못 하나, 기록이 하루 한 장씩 열린다
  7 지옥맛     49일 — 7일 밤 뒤로 이레마다 한 장, 봉인문, 마지막 밤에 거두는 의식

🛑 의식은 전부 화면 안에서만 한다. 상대의 물건을 구하거나 어디에 묻으라는 식의
   현실 행동을 시키지 않는다.
🛑 바라는 일은 「되는 일이 없다 · 재수가 막힌다 · 잠자리가 뒤숭숭하다 · 인연이 꼬인다」까지다.
   죽음 · 병 · 사고 · 범죄는 7단계에서도 쓰지 않는다.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR
from modules import saju_writer

PRODUCT = "jeoju"
_FILE = Path(DATA_DIR) / "jeoju_results.json"
_LOCK = threading.RLock()
_MAX_PER_USER = 60
_KST = timezone(timedelta(hours=9))

# 🛑 값은 lamps.PREMIUM_WON · 프런트 jeoju.js 의 LEVELS · special-products.js 와 같아야 한다.
#    parts = 그 단계에서 열리는 글 · nights = 축시 기록이 몇 장인지
LEVELS: dict[int, dict[str, Any]] = {
    1: {"name": "간지럼맛", "won": 0, "parts": ("line",), "nights": 0},
    2: {"name": "순한맛", "won": 1000, "parts": ("line", "script"), "nights": 0},
    3: {"name": "덜매운맛", "won": 1900, "parts": ("line", "script", "charm"), "nights": 0},
    4: {"name": "오리지널", "won": 3900, "parts": ("line", "script", "charm", "doll"), "nights": 0},
    5: {"name": "매운맛", "won": 7900, "parts": ("line", "script", "charm", "doll"), "nights": 1},
    6: {"name": "아주매운맛", "won": 14800, "parts": ("line", "script", "charm", "doll"), "nights": 7},
    7: {"name": "지옥맛", "won": 29800, "parts": ("line", "script", "charm", "doll", "seal"), "nights": 13},
}
MAX_LEVEL = 7
TARGETS = ("전애인", "썸", "친구", "가족", "직장 사람", "이웃", "모르는 사람")
# 못 박는 자리 → 그 자리가 막는 것. 몸을 다치게 한다는 뜻으로 쓰지 않는다
SPOTS = {
    "입": "하는 말마다 꼬이고 말실수가 는다",
    "손": "손대는 일마다 한 번에 안 된다",
    "발": "가는 길마다 막히고 늦는다",
    "머리": "생각이 엉키고 잠자리가 뒤숭숭하다",
    "가슴": "사람 인연이 자꾸 어긋난다",
}


def product_id(level: int) -> str:
    # 🛑 검사 도구(check_premium.mjs)가 상품 id 를 영문 소문자와 _ 로만 읽는다. 숫자를 넣으면 못 찾는다
    return "%s_%s" % (PRODUCT, "abcdefg"[level - 1])


def night_days(level: int) -> list[int]:
    """기록이 열리는 밤 — 건 날부터 몇 번째 밤인지. 7단계는 7일 밤 뒤로 이레마다."""
    n = LEVELS[level]["nights"]
    if n <= 7:
        return list(range(1, n + 1))
    return [1, 2, 3, 4, 5, 6, 7, 14, 21, 28, 35, 42, 49]


def _night_at(start_ms: int, day: int) -> int:
    """건 뒤 `day` 번째로 오는 새벽 2시(한국 시간)."""
    start = datetime.fromtimestamp(start_ms / 1000, _KST)
    first = start.replace(hour=2, minute=0, second=0, microsecond=0)
    if first <= start:
        first += timedelta(days=1)
    return int((first + timedelta(days=day - 1)).timestamp() * 1000)


_SCHEMA = {
    "title": {"type": "string", "description": "저주장 제목. '[이름]에게 내리는 ○○ 저주' 꼴, 24자 안쪽"},
    "line": {"type": "string", "description": "악담 한 줄. 34자 안쪽. 이름을 부르며 시작하고 캡처하고 싶을 만큼 구체적으로"},
    "scene": {"type": "string", "description": "그 악담이 일상에서 터지는 장면 2~3문장. 구체적인 물건·장소·시간이 들어간다"},
    "script": {"type": "string", "description": (
        "격식을 갖춘 저주문. 6~8문장. ①누구를 묶는지(이름·관계) ②무슨 죄인지 ③무엇을 막아 달라고 비는지 "
        "④언제까지인지 ⑤맺는 말 순서로 쓴다. '~하게 하소서', '~을 묶나이다' 같은 옛 축문 말투")},
    "charm": {"type": "object", "properties": {
        "hanja": {"type": "string", "description": "부적에 쓰는 한자 넉 자. 실제 있는 한자만"},
        "read": {"type": "string", "description": "그 넉 자의 한글 음"},
        "mean": {"type": "string", "description": "넉 자의 뜻과 이 부적이 무엇을 묶는지 2~3문장"},
    }, "required": ["hanja", "read", "mean"]},
    "doll": {"type": "string", "description": "짚인형에 이름을 적고 정해진 자리에 못을 박은 뒤 일어나는 일. 5~6문장. 못 박은 자리가 막는 것만 다룬다. 몸이 아프다는 말은 쓰지 않는다"},
    "seal": {"type": "string", "description": "부적을 태우고 인형을 묻어 저주를 봉인하는 글. 5~6문장. 으스스하지만 끝은 건 사람이 무사하다는 말"},
    "undo": {"type": "string", "description": "저주를 푸는 법. 건 사람이 마음을 놓고 자기 일상으로 돌아가는 작은 의식. 3~4문장"},
}

_SYSTEM = """너는 로드로그의 저주술사 고양이 무냥이다. 작고 귀엽지만 눈빛은 으스스하다.
한국어로 낮게 속삭이듯 쓴다. 말끝에 가끔 '냥'을 붙인다. 저주문과 봉인문은 옛 축문 말투로 쓴다.
이 서비스는 놀이다. 의식의 형식은 진짜처럼 엄숙하게 쓰되, 저주가 가져오는 일은
'되는 일이 없다, 재수가 막힌다, 말이 꼬인다, 길이 막힌다, 잠자리가 뒤숭숭하다, 인연이 어긋난다'까지만 쓴다.
죽음, 질병, 상해, 사고, 범죄, 협박, 자해, 차별, 성적 모욕, 개인정보 노출은 절대 쓰지 않는다.
못은 인형에 박는 것이고 사람 몸이 아프다는 뜻으로 쓰지 않는다.
건 사람에게 현실에서 무엇을 하라고 시키지 않는다(물건을 구해라, 묻어라, 찾아가라, 연락해라 금지).
주어진 재료 밖의 대상 신상이나 사실을 지어내지 마라. AI라는 말은 하지 않는다."""


def _base(order: dict[str, str], level: int) -> str:
    spot = order.get("spot") or ""
    return (
        "저주 대상: %s\n부르는 이름: %s\n태어난 해: %s\n대상이 한 짓: %s\n"
        "매운맛 단계: %d/7 (%s). 단계가 높을수록 의식이 엄숙하고 저주가 집요하다.\n%s"
        % (order.get("target", "")[:20], order.get("nick", "")[:20] or "그 사람",
           order.get("year") or "모름", order.get("sin", "")[:300], level, LEVELS[level]["name"],
           ("못 박는 자리: %s — %s\n" % (spot, SPOTS[spot])) if spot in SPOTS else "")
    )


def write(order: dict[str, str], level: int, have: dict[str, Any] | None = None,
          now_ms: int | None = None) -> dict[str, Any]:
    """그 단계의 저주장을 쓴다. `have` 에 이미 있는 것은 다시 쓰지 않는다."""
    spec = LEVELS[level]
    doc = dict(have or {})
    want = [k for k in ("title",) + spec["parts"] if not doc.get(k)]
    if "line" in want:
        want.append("scene")
    if level >= 2 and not doc.get("undo"):
        want.append("undo")
    days = night_days(level)
    old_nights = list(doc.get("nights") or [])
    new_days = days[len(old_nights):]
    props = {k: _SCHEMA[k] for k in want}
    if new_days:
        props["nights"] = {"type": "array", "items": {"type": "string"}, "description": (
            "축시(새벽 2시) 의식 기록 정확히 %d장. 차례대로 %s 밤의 기록이다. 각 3~4문장. "
            "그 밤 무냥이가 촛불을 켜고 인형에 못을 하나 더 박은 일과, 그날 대상에게 따라붙을 일을 쓴다. "
            "밤이 갈수록 집요해지고%s"
            % (len(new_days), ", ".join("%d번째" % d for d in new_days),
               " 마지막 49번째 밤은 못을 뽑고 저주를 거두는 의식으로 끝낸다" if level == 7 else " 마지막 밤에 사그라든다"))}
    if props:
        prompt = _base(order, level)
        if doc.get("line"):
            prompt += "이미 내린 악담: %s\n" % doc["line"]
        if doc.get("script"):
            prompt += "이미 쓴 저주문(모순되지 않게): %s\n" % str(doc["script"])[:500]
        if old_nights:
            prompt += "이미 쓴 밤 기록 %d장의 마지막: %s\n" % (len(old_nights), str(old_nights[-1].get("text", ""))[:300])
        prompt += "다음 항목만 써라: " + ", ".join(props) + "."
        tokens = 400 + 420 * len(want) + 260 * len(new_days)
        got = saju_writer._call(
            _SYSTEM, prompt, temperature=0.9, max_tokens=tokens,
            schema={"type": "object", "properties": props, "required": list(props)},
        )
        new = json.loads(got["text"])
        for key in want:
            value = new.get(key)
            if key == "charm":
                if not (isinstance(value, dict) and all(str(value.get(k) or "").strip() for k in ("hanja", "read", "mean"))):
                    raise RuntimeError("부적 항목이 비어 왔습니다.")
                doc["charm"] = {k: str(value[k]).strip() for k in ("hanja", "read", "mean")}
            else:
                text = str(value or "").strip()
                if not text:
                    raise RuntimeError("저주장의 %s 항목이 비어 왔습니다." % key)
                doc[key] = text
        if new_days:
            rows = [str(x).strip() for x in (new.get("nights") or []) if str(x).strip()]
            if len(rows) < len(new_days):
                raise RuntimeError("밤 기록이 %d장보다 적게 왔습니다." % len(new_days))
            start = int(doc.get("nightStart") or now_ms or time.time() * 1000)
            doc["nightStart"] = start
            doc["nights"] = old_nights + [
                {"day": d, "at": _night_at(start, d), "text": rows[i]} for i, d in enumerate(new_days)]
    if order.get("spot") in SPOTS and level >= 4:
        doc["spot"] = order["spot"]
    doc["level"] = max(level, int(doc.get("level") or 0))
    return doc


def veil(doc: dict[str, Any], now_ms: int | None = None) -> dict[str, Any]:
    """아직 안 온 밤의 기록은 글을 빼고 내보낸다."""
    now = now_ms or int(time.time() * 1000)
    out = dict(doc)
    if out.get("nights"):
        out["nights"] = [n if n.get("at", 0) <= now else {"day": n.get("day"), "at": n.get("at"), "text": ""}
                         for n in out["nights"]]
    return out


# ── 보관함 ─────────────────────────────────────────────
def _read() -> dict[str, list[dict[str, Any]]]:
    if not _FILE.exists():
        return {}
    try:
        data = json.loads(_FILE.read_text("utf-8"))
    except Exception as exc:
        raise RuntimeError("저주장 보관함을 읽지 못했습니다.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("저주장 보관함 형식이 올바르지 않습니다.")
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


def mine(email: str) -> list[dict[str, Any]]:
    """내가 건 저주 목록. 새것부터."""
    with _LOCK:
        rows = list(_read().get(email.lower(), []))
    # 결제 전에 맡겨 두기만 한 주문서(1단계 이하)는 목록에 올리지 않는다
    rows = [r for r in rows if int((r.get("doc") or {}).get("level") or 0) >= 2]
    return [{"ritual": r.get("ritual"), "at": r.get("at"),
             "level": int((r.get("doc") or {}).get("level") or 1),
             "nick": (r.get("order") or {}).get("nick") or "",
             "target": (r.get("order") or {}).get("target") or "",
             "title": (r.get("doc") or {}).get("title") or ""} for r in reversed(rows)]


def save(email: str, ritual: str, pair: str, order: dict[str, str], doc: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        data = _read()
        rows = data.setdefault(email.lower(), [])
        first = next((x.get("at") for x in rows if x.get("ritual") == ritual), None)
        row = {"ritual": ritual, "pair": pair, "at": first or int(time.time() * 1000), "order": order, "doc": doc}
        rows[:] = [x for x in rows if x.get("ritual") != ritual]
        rows.append(row)
        del rows[:-_MAX_PER_USER]
        _write(data)
    return dict(row)
