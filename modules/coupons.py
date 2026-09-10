# -*- coding: utf-8 -*-
"""쿠폰 (2026-09-11 온해님 명세 5).

> 프로모션 코드 / 쿠폰: 스레드 이벤트용 할인 쿠폰 또는 무료 체험 코드 발급

🛑 **깎아 주는 쿠폰은 만들지 않는다.** 결제 금액이 화면과 달라지면 카드사 심사에서
   「노출 금액 = 결제창 금액」 항목에 걸린다 (심사 6번). 대신 **한 편을 열어 주는**
   방식으로 간다 — 선착순 이벤트가 이미 같은 방식으로 돌고 있다.

  · 코드 하나에 **몇 명까지** 쓸지 정한다
  · 한 사람은 한 코드를 **한 번만** 쓴다
  · 쓰면 그 자리에서 리포트가 열린다 (복채를 안 받는다)
  · 원장에 `coupon` 으로 남는다 — 매출에는 안 잡힌다 (돈이 안 들어왔으므로)
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

FILE = "coupons.json"
CODE_RE = re.compile(r"^[A-Z0-9-]{4,20}$")


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


def make(code: str, *, cap: int = 50, note: str = "", by: str = "") -> dict[str, Any]:
    code = (code or "").strip().upper()
    if not CODE_RE.match(code):
        raise ValueError("코드는 영문 대문자·숫자·하이픈으로 4~20자여야 해요.")
    d = _read()
    if code in d:
        raise ValueError("이미 있는 코드예요.")
    cap = max(1, min(int(cap or 1), 100000))
    d[code] = {"cap": cap, "used": [], "note": str(note or "")[:80],
               "by": by, "at": time.strftime("%Y-%m-%d %H:%M"), "on": True}
    _write(d)
    return d[code]


def toggle(code: str, on: bool) -> None:
    d = _read()
    c = d.get((code or "").strip().upper())
    if not c:
        raise ValueError("없는 코드예요.")
    c["on"] = bool(on)
    _write(d)


def drop(code: str) -> None:
    d = _read()
    if d.pop((code or "").strip().upper(), None) is not None:
        _write(d)


def check(code: str, email: str) -> dict[str, Any]:
    """쓸 수 있는 코드인가. 쓰지는 않는다."""
    code = (code or "").strip().upper()
    email = (email or "").strip().lower()
    c = _read().get(code)
    if not c:
        raise ValueError("그런 코드가 없어요.")
    if not c.get("on", True):
        raise ValueError("지금은 쓸 수 없는 코드예요.")
    if email in (c.get("used") or []):
        raise ValueError("이미 쓰신 코드예요.")
    if len(c.get("used") or []) >= int(c.get("cap") or 0):
        raise ValueError("자리가 다 찼어요.")
    return c


def use(code: str, email: str) -> dict[str, Any]:
    """한 자리를 쓴다. 🛑 리포트를 여는 것은 부른 쪽이 한다."""
    code = (code or "").strip().upper()
    email = (email or "").strip().lower()
    check(code, email)
    d = _read()
    c = d[code]
    c.setdefault("used", []).append(email)
    _write(d)
    return {"code": code, "left": max(0, int(c.get("cap") or 0) - len(c["used"]))}


def listing() -> list[dict[str, Any]]:
    out = []
    for code, c in _read().items():
        used = len(c.get("used") or [])
        cap = int(c.get("cap") or 0)
        out.append({"code": code, "cap": cap, "used": used,
                    "left": max(0, cap - used), "note": c.get("note") or "",
                    "on": bool(c.get("on", True)), "at": c.get("at") or ""})
    return sorted(out, key=lambda x: x["at"], reverse=True)
