# -*- coding: utf-8 -*-
"""방문자 · 매출 · 가입 집계.

방문자는 서버가 직접 센다. 쿠키를 굽지 않고 애널리틱스도 붙이지 않는다.
「그날 처음 온 브라우저」만 세려고 (IP + 브라우저 + 날짜)를 그날치 소금과 함께
해시로만 남긴다. 원래 값으로 되돌릴 수 없고, 90일 지나면 지운다.

매출과 가입은 이미 쌓이고 있는 것(lamps.json 장부, users.json 가입일)을 훑어서 낸다.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

VISITS_JSON = Path(DATA_DIR) / "visits.json"
KEEP_DAYS = 90
_LOCK = threading.Lock()
_SALT = (os.environ.get("APP_SECRET") or "roadlog") + "|visit"

# 사주 서비스를 연 날. 이전에 만들어진 계정은 옛 운행일지 계정이다.
SAJU_SINCE = os.environ.get("SAJU_SINCE", "2026-09-04")


KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """서버는 세계표준시로 돈다. 날짜는 한국 시간으로 끊어야 맞다."""
    return datetime.now(KST)


def _today() -> str:
    return now_kst().strftime("%Y-%m-%d")


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)


def _fingerprint(ip: str, ua: str, day: str) -> str:
    raw = f"{_SALT}|{day}|{ip}|{ua}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# 어디서 왔는지 — 주소의 호스트를 사람이 읽는 이름으로 묶는다
SOURCES = [
    ("google.", "구글"), ("naver.", "네이버"), ("daum.", "다음"),
    ("kakao", "카카오"), ("instagram.", "인스타그램"), ("threads.", "스레드"),
    ("tistory.", "티스토리"), ("youtube.", "유튜브"), ("youtu.be", "유튜브"),
    ("bing.", "빙"), ("x.com", "X"), ("twitter.", "X"), ("facebook.", "페이스북"),
    ("t.co", "X"), ("chatgpt.com", "챗GPT"), ("perplexity.", "퍼플렉시티"),
]


def source_of(ref: str, host: str = "") -> str:
    """유입경로 한 줄. 광고 파라미터(utm_source)가 있으면 그것을 우선한다."""
    r = (ref or "").strip().lower()
    if not r:
        return "직접 · 앱"
    try:
        from urllib.parse import urlsplit
        p = urlsplit(r)
        h = p.netloc
    except Exception:
        h = r
    if not h:
        return "직접 · 앱"
    if host and host.lower() in h:
        return "사이트 안"
    for key, name in SOURCES:
        if key in h:
            return name
    return h[:40]


def hit(ip: str, ua: str, path: str, ref: str = "", host: str = "") -> None:
    """페이지 한 번 열림. 화면(HTML)만 세고 자산·API 는 안 센다."""
    day = _today()
    fp = _fingerprint(ip or "", ua or "", day)
    src = source_of(ref, host)
    with _LOCK:
        data = _read(VISITS_JSON, {})
        d = data.setdefault(day, {"pv": 0, "uv": [], "src": {}})
        d.setdefault("src", {})
        d["pv"] = int(d.get("pv", 0)) + 1
        if fp not in d["uv"]:
            d["uv"].append(fp)
            # 유입경로는 그날 처음 온 사람만 센다 — 안 그러면 새로고침이 다 잡힌다
            d["src"][src] = int(d["src"].get(src, 0)) + 1
        # 오래된 날짜는 버린다
        if len(data) > KEEP_DAYS + 10:
            cut = (now_kst() - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
            for k in [k for k in data if k < cut]:
                data.pop(k, None)
        _write(VISITS_JSON, data)


def forget_visits(day: str | None = None) -> int:
    """방문 기록을 지운다. 잘못 센 날을 털어낼 때 쓴다."""
    with _LOCK:
        data = _read(VISITS_JSON, {})
        if day:
            gone = 1 if data.pop(day, None) is not None else 0
        else:
            gone = len(data)
            data = {}
        _write(VISITS_JSON, data)
    return gone


def _visits() -> dict[str, dict[str, Any]]:
    out = {}
    for day, d in _read(VISITS_JSON, {}).items():
        out[day] = {
            "pv": int(d.get("pv", 0)),
            "uv": len(d.get("uv", [])),
            "src": dict(d.get("src", {})),
        }
    return out


def _charges() -> list[dict[str, Any]]:
    """등불 충전 기록 전부. 계정별 장부에 흩어져 있는 것을 모은다."""
    from modules import lamps as lamps_ops

    rows = []
    for email, acc in (lamps_ops._read() or {}).items():
        if not isinstance(acc, dict):
            continue
        for e in acc.get("ledger", []):
            if e.get("type") != "charge":
                continue
            at = str(e.get("at", ""))[:10]
            if not at:
                continue
            rows.append({
                "day": at,
                "email": email,
                "price": int(e.get("price") or 0),
                "lamps": int(e.get("lamps") or 0),
            })
    return rows


def _spends() -> list[dict[str, Any]]:
    """어떤 사주가 몇 번 열렸나."""
    from modules import lamps as lamps_ops

    rows = []
    for email, acc in (lamps_ops._read() or {}).items():
        if not isinstance(acc, dict):
            continue
        for o in acc.get("owned", []):
            at = str(o.get("at", ""))[:10]
            if at:
                rows.append({"day": at, "product": o.get("product", ""), "email": email})
    return rows


def _signups() -> list[str]:
    """사주 손님만. 옛 운행일지 계정은 세지 않는다."""
    return [m["at"] for m in members() if m["at"] and not m["legacy"]]


def members(limit: int = 300) -> list[dict[str, Any]]:
    """가입한 사람들. 관리자만 본다."""
    from modules.config import USERS_JSON
    from modules import lamps as lamps_ops

    lamp = lamps_ops._read() or {}
    out = []
    for email, u in (_read(Path(USERS_JSON), {}) or {}).items():
        if not isinstance(u, dict):
            continue
        acc = lamp.get(email) or {}
        charged = sum(int(e.get("price") or 0)
                      for e in acc.get("ledger", []) if e.get("type") == "charge")
        bal = sum(int(l.get("remain") or 0) for l in acc.get("lots", []))
        if email.endswith("@kakao.local"):
            how = "카카오"
        elif email.endswith("@roadlog.local"):
            how = "관리자"
        else:
            how = "이메일 · 소셜"
        at = str(u.get("created_at", ""))[:10]
        opens = len(acc.get("owned", []))
        # 사주를 쓴 적이 있거나, 사주 시작일 이후에 가입했으면 사주 손님이다
        used = bool(opens or acc.get("ledger"))
        legacy = (how == "관리자") or not (used or (at and at >= SAJU_SINCE))
        out.append({
            "email": email,
            "name": u.get("name") or "",
            "at": at,
            "how": how,
            "lamps": bal,
            "spent": charged,
            "opens": opens,
            "legacy": legacy,
        })
    out.sort(key=lambda m: m["at"], reverse=True)
    return out[:limit]


def overview(days: int = 30) -> dict[str, Any]:
    """오늘·이번 달·최근 N일을 한 번에."""
    now = now_kst()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    vis = _visits()
    ch = _charges()
    sp = _spends()
    su = _signups()

    start = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    by_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sales": 0, "charges": 0, "signups": 0, "uv": 0, "pv": 0, "opens": 0})
    for r in ch:
        by_day[r["day"]]["sales"] += r["price"]
        by_day[r["day"]]["charges"] += 1
    for d in su:
        by_day[d]["signups"] += 1
    for r in sp:
        by_day[r["day"]]["opens"] += 1
    for d, v in vis.items():
        by_day[d]["uv"] = v["uv"]
        by_day[d]["pv"] = v["pv"]

    daily = [{"day": d, **by_day[d]} for d in sorted(by_day) if d >= start]
    daily.reverse()

    def _sum(keep) -> dict[str, int]:
        out = {"sales": 0, "charges": 0, "signups": 0, "uv": 0, "pv": 0, "opens": 0}
        for d, v in by_day.items():
            if not keep(d):
                continue
            for k in out:
                out[k] += v[k]
        return out

    by_month: dict[str, int] = defaultdict(int)
    for r in ch:
        by_month[r["day"][:7]] += r["price"]

    prod: dict[str, int] = defaultdict(int)
    for r in sp:
        prod[r["product"]] += 1

    # 유입경로 — 이번 달과 최근 N일
    src_month: dict[str, int] = defaultdict(int)
    src_recent: dict[str, int] = defaultdict(int)
    for d, v in vis.items():
        for name, c in (v.get("src") or {}).items():
            if d.startswith(month):
                src_month[name] += c
            if d >= start:
                src_recent[name] += c

    return {
        "today": {"day": today, **_sum(lambda d: d == today)},
        "month": {"month": month, **_sum(lambda d: d.startswith(month))},
        "total": {
            "sales": sum(r["price"] for r in ch),
            "charges": len(ch),
            "signups": len(su),
            "opens": len(sp),
            "members": len(su),
            "legacy": len([m for m in members() if m["legacy"]]),
            "uv": sum(v["uv"] for v in vis.values()),
            "pv": sum(v["pv"] for v in vis.values()),
        },
        "members": members(),
        "daily": daily,
        "byMonth": [{"month": m, "sales": s} for m, s in sorted(by_month.items(), reverse=True)],
        "bySource": sorted(
            [{"name": n, "uv": c} for n, c in src_recent.items()],
            key=lambda x: x["uv"], reverse=True),
        "bySourceMonth": sorted(
            [{"name": n, "uv": c} for n, c in src_month.items()],
            key=lambda x: x["uv"], reverse=True),
        "byProduct": sorted(
            [{"product": p, "opens": c} for p, c in prod.items()],
            key=lambda x: x["opens"], reverse=True),
    }
