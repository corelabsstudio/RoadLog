# -*- coding: utf-8 -*-
"""제미나이에 얼마나 썼나 (2026-09-11 온해님 「API 잔액 실시간으로 보게 할 수 없나」).

🛑 **구글은 잔액을 알려 주는 API 를 내놓지 않았다.** 2026-09-11 확인 — 선불 크레딧
   잔액은 `aistudio.google.com/billing` 화면에서만 본다. Cloud Monitoring 으로
   사용량은 받을 수 있지만 서비스 계정·권한이 필요하고 몇 시간 늦는다.

   그래서 **우리가 쓴 만큼을 우리가 센다.** 제미나이는 응답마다 토큰 수를
   `usageMetadata` 로 알려 주는데, 그동안 그 값을 받아 놓고 버리고 있었다.
   시작 잔액을 한 번 적어 두면 **쓴 만큼 뺀 추정 잔액**이 나온다.

🛑 **「추정」이다.** 단가가 바뀌거나 실패한 호출·그림 생성이 섞이면 어긋난다.
   진짜 잔액은 AI Studio 에서 봐야 한다 — 화면에도 그렇게 적어 둔다.
🛑 **단가는 관리자가 넣는다.** 백만 토큰당 얼마인지는 모델과 시점에 따라 달라서
   코드에 박아 두면 조용히 틀린 값이 나온다. 안 넣으면 토큰 수만 보여 준다.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

FILE = "api_cost.json"


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
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def note(tin: int = 0, tout: int = 0, *, calls: int = 1) -> None:
    """한 번 부른 것을 적는다. 🛑 실패하면 부르지 않는다 — 값이 안 나가니까.

    🛑 **여기서 예외를 내보내지 않는다.** 세는 일 때문에 손님 글이 막히면 안 된다.
    """
    try:
        day = time.strftime("%Y-%m-%d")
        d = _read()
        rows = d.setdefault("days", {})
        r = rows.setdefault(day, {"calls": 0, "in": 0, "out": 0})
        r["calls"] += int(calls or 0)
        r["in"] += int(tin or 0)
        r["out"] += int(tout or 0)
        # 🛑 날짜가 끝없이 쌓이지 않게 최근 120일만 남긴다
        if len(rows) > 120:
            for k in sorted(rows)[:-120]:
                rows.pop(k, None)
        _write(d)
    except Exception:                                    # noqa: BLE001
        pass


def settings() -> dict[str, Any]:
    d = _read()
    return {
        "won_in": float(d.get("won_in") or 0),      # 들어간 토큰 백만 개당 원
        "won_out": float(d.get("won_out") or 0),    # 나온 토큰 백만 개당 원
        "start": float(d.get("start") or 0),        # 시작 잔액(원)
        "startAt": str(d.get("startAt") or ""),     # 그 잔액을 적은 날
    }


def put_settings(*, won_in: float, won_out: float, start: float) -> dict[str, Any]:
    """단가와 시작 잔액을 적는다.

    🛑 **시작 잔액을 새로 적으면 그날부터 다시 센다.** 충전할 때마다 적어 두면
       추정이 어긋나지 않는다.
    """
    d = _read()
    d["won_in"] = max(0.0, float(won_in or 0))
    d["won_out"] = max(0.0, float(won_out or 0))
    old = float(d.get("start") or 0)
    if float(start or 0) != old:
        d["start"] = max(0.0, float(start or 0))
        d["startAt"] = time.strftime("%Y-%m-%d")
    _write(d)
    return settings()


def _won(tin: int, tout: int, s: dict[str, Any]) -> float:
    return (tin / 1_000_000.0) * s["won_in"] + (tout / 1_000_000.0) * s["won_out"]


def summary(days: int = 14) -> dict[str, Any]:
    """오늘·이번 달·시작 잔액을 적은 뒤로 쓴 것."""
    d = _read()
    rows = d.get("days") or {}
    s = settings()
    today = time.strftime("%Y-%m-%d")
    month = today[:7]

    def add(keys: list[str]) -> dict[str, Any]:
        c = i = o = 0
        for k in keys:
            r = rows.get(k) or {}
            c += int(r.get("calls") or 0)
            i += int(r.get("in") or 0)
            o += int(r.get("out") or 0)
        return {"calls": c, "in": i, "out": o, "won": round(_won(i, o, s), 1)}

    allk = sorted(rows)
    since = [k for k in allk if not s["startAt"] or k >= s["startAt"]]
    used = add(since)
    left = (s["start"] - used["won"]) if s["start"] else 0
    return {
        "today": add([today]),
        "month": add([k for k in allk if k.startswith(month)]),
        "since": used,
        "start": s["start"], "startAt": s["startAt"],
        "wonIn": s["won_in"], "wonOut": s["won_out"],
        "left": round(left, 1) if s["start"] else None,
        # 🛑 최근 며칠치를 그대로 준다 — 화면이 막대로 그린다
        "recent": [dict(day=k, **(rows.get(k) or {}),
                        won=round(_won(int((rows.get(k) or {}).get("in") or 0),
                                       int((rows.get(k) or {}).get("out") or 0), s), 1))
                   for k in allk[-days:]],
    }
