# -*- coding: utf-8 -*-
"""Login to live RoadLog, generate driving + field logs, export to Desktop."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://roadlog.co.kr"
DESK = Path.home() / "Desktop"
TODAY = date.today().isoformat().replace("-", "")
CTX = ssl.create_default_context()


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for p in (ROOT / ".env", ROOT / "railway-variables.env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def req(method: str, path: str, data=None, token: str | None = None):
    headers = {
        "User-Agent": "RoadLog-LiveExport/1.0",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120, context=CTX) as res:
            return res.status, res.read(), res.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def main() -> int:
    env = load_env()
    user = env.get("ADMIN_USERNAME") or env.get("ADMIN_EMAIL") or "hhs126"
    pw = env.get("ADMIN_PASSWORD") or ""
    if not pw:
        print("FAIL: no ADMIN_PASSWORD in .env / railway-variables.env")
        return 1

    st, raw, _ = req("POST", "/api/auth/login", {"email": user, "password": pw})
    if st != 200:
        print("LOGIN FAIL", st, raw[:240])
        return 1
    login = json.loads(raw.decode())
    token = login.get("token") or login.get("access_token")
    if not token:
        print("LOGIN FAIL: no token", list(login.keys()))
        return 1
    u = login.get("user") or {}
    print("LOGIN OK", u.get("email") or u.get("id") or user)

    settings = {
        "vehicle_number": "12가3456",
        "driver_name": "검수테스터",
        "company_name": "(주)코어랩스",
        "default_purpose": "업무 출장",
        "lunch_start": "12:00",
        "lunch_end": "13:00",
        "exclude_lunch": True,
        "omit_lunch_place": True,
        "frequent_places": [{"name": "본사", "address": "강원 춘천시 후평3동"}],
    }

    # ── 운행일지 ──
    form_d = {
        "odometer_start": 12040,
        "odometer_end": 12065,
        "vehicle_number": "12가3456",
        "morning_places": "동네 슈퍼, 후평3동\n동네 편의점, 후평3동",
        "afternoon_places": "고객사 미팅, 후평3동",
        "extra_note": "라이브 검수 운행 내보내기",
        "fuel_refueled": False,
    }
    st, raw, _ = req(
        "POST",
        "/api/generate",
        {
            "report_type": "driving",
            "form": form_d,
            "settings": settings,
            "raw_text": "",
        },
        token=token,
    )
    print("GENERATE driving", st)
    if st != 200:
        print(raw[:300])
        return 2
    gen = json.loads(raw.decode())
    dlog = gen.get("log") or {}
    print(
        "  engine=",
        gen.get("engine"),
        "trips=",
        len(dlog.get("trips") or []),
        "success=",
        gen.get("success"),
    )
    for fmt in ("excel", "pdf", "docx"):
        st, raw, _ = req("POST", "/api/export", {"log": dlog, "format": fmt}, token=token)
        ext = "xlsx" if fmt == "excel" else fmt
        path = DESK / f"로드로그_라이브_운행일지_{TODAY}.{ext}"
        if st != 200:
            print("  EXPORT FAIL", fmt, st, raw[:160])
            continue
        path.write_bytes(raw)
        print(f"  saved {path.name} ({len(raw):,} bytes)")

    # ── 외근일지 ──
    form_f = {
        "visits_text": (
            "[오전] 10:00 · 강남 고객사, 역삼동 — 계약 조건 협의\n"
            "[오후] 14:30 · 판교 B사, 삼평동 — 제품 데모"
        ),
        "work_summary": "강남·판교 고객 방문 및 견적 협의",
        "next_actions": "견적서 재송부",
        "department": "영업팀",
        "author_name": "검수테스터",
    }
    st, raw, _ = req(
        "POST",
        "/api/generate",
        {
            "report_type": "field",
            "form": form_f,
            "settings": settings,
            "raw_text": form_f["visits_text"],
        },
        token=token,
    )
    print("GENERATE field", st)
    if st != 200:
        print(raw[:300])
        return 3
    gen = json.loads(raw.decode())
    flog = gen.get("log") or {}
    if not flog.get("report_type"):
        flog["report_type"] = "field"
    print(
        "  engine=",
        gen.get("engine"),
        "visits=",
        len(flog.get("visits") or flog.get("trips") or []),
        "success=",
        gen.get("success"),
    )
    for fmt in ("excel", "pdf", "docx"):
        st, raw, _ = req("POST", "/api/export", {"log": flog, "format": fmt}, token=token)
        ext = "xlsx" if fmt == "excel" else fmt
        path = DESK / f"로드로그_라이브_외근일지_{TODAY}.{ext}"
        if st != 200:
            print("  EXPORT FAIL", fmt, st, raw[:160])
            continue
        path.write_bytes(raw)
        print(f"  saved {path.name} ({len(raw):,} bytes)")

    print("DONE → Desktop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
