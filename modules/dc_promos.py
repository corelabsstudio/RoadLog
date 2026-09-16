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
