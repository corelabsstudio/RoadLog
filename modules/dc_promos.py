"""운영자가 디시 글 초안을 보관하는 곳.

게시 자체는 하지 않는다. 글쓰기 화면을 열고 마지막 등록·캡차는 운영자가 직접 한다.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


GALLERIES = {
    "yeokhak": {
        "name": "역학 갤러리",
        "url": "https://gall.dcinside.com/board/lists/?id=divination_new1",
    },
    "sajuhub": {
        "name": "사주허브 미니 갤러리",
        "url": "https://gall.dcinside.com/mini/board/lists/?id=sajuhub",
    },
    "saju8": {
        "name": "사주팔자 미니 갤러리",
        "url": "https://gall.dcinside.com/mini/board/lists/?id=iiiiiiiiiisaju",
    },
}
ORDER = list(GALLERIES)
_LOCK = threading.RLock()


class PromoStoreError(RuntimeError):
    pass


_SYSTEM = """당신은 한국 사주 서비스의 커뮤니티 홍보 문안을 쓰는 편집자입니다.
디시인사이드 게시글에 쓸 제목과 본문 초안 3개를 한국어로 만드세요.

서비스 사실: 로드로그(https://roadlog.co.kr)는 사주와 관상을 볼 수 있는 한국 웹서비스입니다.
과장, 거짓 후기, 수익 보장, 타 서비스 비방, 욕설, 도배 문구는 쓰지 마세요.
각 본문은 자연스러운 문단 2~3개, 220~420자 안팎으로 쓰고 마지막에 서비스 주소를 한 번만 넣으세요.
제목은 42자 이내입니다. 마크다운, 해시태그, 이모지, 인사말은 쓰지 마세요.

갤러리별 결:
- yeokhak(역학 갤러리): 가벼운 운세 소비가 아니라 사주 풀이를 비교해 보고 싶은 사람에게 차분하게.
- sajuhub(사주허브 미니 갤러리): 사주를 처음 보거나 자기 사주를 편하게 읽어 보고 싶은 사람에게 친근하게.
- saju8(사주팔자 미니 갤러리): 일상 고민과 사주 이야기를 함께 나누는 사람에게 부담 없이.

반드시 gallery 값 yeokhak, sajuhub, saju8을 각각 한 번씩 넣으세요."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gallery": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["gallery", "title", "body"],
            },
        },
    },
    "required": ["items"],
}


def _path() -> Path:
    from modules.config import DATA_DIR

    root = Path(DATA_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root / "dc_promo_drafts.json"


def _defaults() -> list[dict[str, str]]:
    return [{"gallery": gallery, "title": "", "body": ""} for gallery in ORDER]


def _clean(items: Any) -> list[dict[str, str]]:
    by_gallery: dict[str, dict[str, str]] = {}
    if isinstance(items, list):
        for raw in items:
            if not isinstance(raw, dict):
                continue
            gallery = str(raw.get("gallery") or "").strip()
            if gallery not in GALLERIES or gallery in by_gallery:
                continue
            by_gallery[gallery] = {
                "gallery": gallery,
                "title": str(raw.get("title") or "").strip()[:120],
                "body": str(raw.get("body") or "").strip()[:5000],
            }
    return [by_gallery.get(gallery, {"gallery": gallery, "title": "", "body": ""}) for gallery in ORDER]


def _read() -> list[dict[str, str]]:
    path = _path()
    if not path.exists():
        return _defaults()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PromoStoreError("홍보 초안 파일을 읽지 못했습니다.") from exc
    return _clean(raw)


def _write(items: list[dict[str, str]]) -> None:
    path = _path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _present(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {**item, "name": GALLERIES[item["gallery"]]["name"], "url": GALLERIES[item["gallery"]]["url"]}
        for item in items
    ]


def listing() -> list[dict[str, str]]:
    with _LOCK:
        return _present(_read())


def save(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    with _LOCK:
        clean = _clean(items)
        _write(clean)
        return _present(clean)


def generate() -> list[dict[str, str]]:
    """Gemini로 세 갤러리 초안을 한 번에 만들고 저장한다."""
    from modules import saju_writer

    if not saju_writer.ready():
        raise PromoStoreError("Gemini 키가 없어 홍보 초안을 만들 수 없습니다.")
    try:
        reply = saju_writer._call(  # 기존 Gemini 호출·실패 기록·비용 집계를 함께 쓴다.
            _SYSTEM,
            "지금 사용할 홍보 초안 세 개를 JSON으로 만들어 주세요.",
            temperature=0.9,
            max_tokens=1400,
            schema=_SCHEMA,
        )
        raw = json.loads(reply["text"])
        clean = _clean(raw.get("items"))
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
        raise PromoStoreError("Gemini가 홍보 초안을 만들지 못했습니다. 잠시 뒤 다시 해 주세요.") from exc
    if any(not item["title"] or not item["body"] for item in clean):
        raise PromoStoreError("Gemini 응답에 제목이나 본문이 빠졌습니다. 다시 만들어 주세요.")
    with _LOCK:
        _write(clean)
        return _present(clean)
