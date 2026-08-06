# -*- coding: utf-8 -*-
"""RoadLog end-to-end audit: APIs + generate driving/field logs + export to Desktop."""
from __future__ import annotations

import json
import sys
import traceback
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DESKTOP = Path.home() / "Desktop"
TODAY = date.today().isoformat()
OUT = []


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")
    OUT.append(("OK", msg))


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")
    OUT.append(("WARN", msg))


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    OUT.append(("FAIL", msg))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    fails = 0

    # ── 1) Local modules / template ──
    section("1. Local modules & default Excel template")
    try:
        from modules.export import (
            export_excel,
            export_pdf,
            export_docx,
            _default_driving_template_path,
        )
        from modules.generator import generate_driving_log, generate_field_visit_log
        from modules.validator import validate_log

        tmpl = _default_driving_template_path()
        if tmpl.is_file() and tmpl.stat().st_size > 1000:
            ok(f"default template exists: {tmpl} ({tmpl.stat().st_size} bytes)")
        else:
            fail(f"default template missing/small: {tmpl}")
            fails += 1
    except Exception as e:
        fail(f"import failed: {e}")
        traceback.print_exc()
        return 1

    # ── 2) Generate driving log ──
    section("2. Generate 운행일지 (driving)")
    settings = {
        "vehicle_number": "12가3456",
        "driver_name": "검수테스터",
        "company_name": "(주)코어랩스",
        "default_purpose": "업무 출장",
        "lunch_start": "12:00",
        "lunch_end": "13:00",
        "exclude_lunch": True,
        "omit_lunch_place": True,
        "frequent_places": [
            {"name": "본사", "address": "강원 춘천시 후평3동"},
        ],
    }
    form_driving = {
        "odometer_start": 12040,
        "odometer_end": 12065,
        "vehicle_number": "12가3456",
        "morning_places": "동네 슈퍼, 후평3동\n동네 편의점, 후평3동",
        "afternoon_places": "고객사 미팅, 후평3동",
        "extra_note": "검수 자동화 테스트 운행",
        "fuel_refueled": False,
    }
    try:
        res = generate_driving_log(
            raw_text="",
            settings=settings,
            form=form_driving,
            user_email=None,
            report_type="driving",
        )
        log = res.get("log") or {}
        engine = res.get("engine")
        trips = log.get("trips") or []
        if not trips:
            fail(f"driving log has no trips: {res.get('errors')} {res.get('message')}")
            fails += 1
        else:
            ok(
                f"driving generated engine={engine} trips={len(trips)} "
                f"dist={log.get('total_distance_km')} success={res.get('success')}"
            )
            # place dong check
            with_dong = sum(
                1
                for t in trips
                if "동" in str(t.get("from") or "") or "동" in str(t.get("to") or "")
            )
            if with_dong:
                ok(f"place labels include dong on {with_dong}/{len(trips)} legs")
            else:
                warn("no dong in from/to (may be ok if input lacked dong)")
            # sample from/to
            for t in trips[:3]:
                print(f"    {t.get('depart_time')}-{t.get('arrive_time')} "
                      f"{t.get('from')} → {t.get('to')} ({t.get('distance_km')}km)")
        # export
        for fmt, fn in (
            ("excel", export_excel),
            ("pdf", export_pdf),
            ("docx", export_docx),
        ):
            try:
                data, name = fn(log)
                path = DESKTOP / f"로드로그_검수_운행일지_{TODAY.replace('-', '')}.{name.split('.')[-1]}"
                # normalize name from export
                ext = name.rsplit(".", 1)[-1]
                path = DESKTOP / f"로드로그_검수_운행일지_{TODAY.replace('-', '')}.{ext}"
                path.write_bytes(data)
                if len(data) < 500:
                    fail(f"driving {fmt} too small: {len(data)} -> {path.name}")
                    fails += 1
                else:
                    ok(f"driving {fmt} saved: {path.name} ({len(data):,} bytes)")
            except Exception as e:
                fail(f"driving {fmt} export: {e}")
                fails += 1
                traceback.print_exc()
    except Exception as e:
        fail(f"driving generate: {e}")
        fails += 1
        traceback.print_exc()
        log = {}

    # ── 3) Generate field log ──
    section("3. Generate 외근일지 (field)")
    form_field = {
        "visits_text": (
            "[오전] 10:00 · 강남 고객사, 역삼동 — 계약 조건 협의\n"
            "[오후] 14:30 · 판교 B사, 삼평동 — 제품 데모 / 다음 주 방문 조율"
        ),
        "work_summary": "강남·판교 고객 방문 및 견적 협의",
        "next_actions": "견적서 재송부, 다음 주 본사 방문 일정 확정",
        "department": "영업팀",
        "author_name": "검수테스터",
    }
    try:
        # try generate_field_visit_log if available
        try:
            fres = generate_field_visit_log(
                raw_text=form_field["visits_text"],
                settings=settings,
                form=form_field,
                user_email=None,
            )
        except TypeError:
            fres = generate_field_visit_log(
                raw_text=form_field["visits_text"],
                settings=settings,
                form=form_field,
            )
        flog = fres.get("log") or {}
        # ensure report_type field
        if flog and not flog.get("report_type"):
            flog["report_type"] = "field"
        visits = flog.get("visits") or flog.get("trips") or []
        if not visits and not flog:
            fail(f"field log empty: {fres.get('errors')} {fres.get('message')}")
            fails += 1
        else:
            ok(
                f"field generated engine={fres.get('engine')} "
                f"visits/trips={len(visits)} success={fres.get('success')}"
            )
            for v in (visits[:4] if isinstance(visits, list) else []):
                if isinstance(v, dict):
                    print(
                        f"    {v.get('time') or v.get('depart_time') or '—'} "
                        f"{v.get('place') or v.get('to') or '—'} | "
                        f"{v.get('purpose') or ''}"
                    )
        for fmt, fn in (
            ("excel", export_excel),
            ("pdf", export_pdf),
            ("docx", export_docx),
        ):
            try:
                data, name = fn(flog)
                ext = name.rsplit(".", 1)[-1]
                path = DESKTOP / f"로드로그_검수_외근일지_{TODAY.replace('-', '')}.{ext}"
                path.write_bytes(data)
                if len(data) < 500:
                    fail(f"field {fmt} too small: {len(data)}")
                    fails += 1
                else:
                    ok(f"field {fmt} saved: {path.name} ({len(data):,} bytes)")
            except Exception as e:
                fail(f"field {fmt} export: {e}")
                fails += 1
                traceback.print_exc()
    except Exception as e:
        fail(f"field generate: {e}")
        fails += 1
        traceback.print_exc()

    # ── 4) Live API probe ──
    section("4. Live API probe (roadlog.co.kr)")
    try:
        import ssl
        import urllib.error
        import urllib.request

        ctx = ssl.create_default_context()
        base = "https://roadlog.co.kr"

        def hit(path: str, method: str = "GET", data: dict | None = None):
            raw = None if data is None else json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                base + path,
                data=raw,
                method=method,
                headers={
                    "User-Agent": "RoadLog-Audit/1.0",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()

        checks = [
            ("/healthz", "GET", None),
            ("/api/health", "GET", None),
            ("/api/meta", "GET", None),
            ("/api/templates/defaults", "GET", None),
            ("/api/reviews", "GET", None),
            ("/api/stats/visitors", "GET", None),
            ("/assets/templates/default_driving_log.xlsx", "GET", None),
            ("/manifest.webmanifest", "GET", None),
        ]
        for path, method, data in checks:
            st, body = hit(path, method, data)
            if 200 <= st < 300:
                ok(f"LIVE {st} {path} ({len(body)} bytes)")
            elif st in (401, 403) and path.startswith("/api/admin"):
                ok(f"LIVE {st} {path} (auth expected)")
            else:
                # SPA fallback returns 200 HTML for missing - check xlsx magic
                if path.endswith(".xlsx") and body[:2] != b"PK":
                    fail(f"LIVE {st} {path} not xlsx (got {body[:20]!r})")
                    fails += 1
                elif st >= 400:
                    fail(f"LIVE {st} {path}")
                    fails += 1
                else:
                    warn(f"LIVE {st} {path} ({len(body)} bytes)")

        # unauthenticated generate should fail or work depending on policy
        st, body = hit(
            "/api/generate",
            "POST",
            {
                "report_type": "driving",
                "form": form_driving,
                "settings": settings,
            },
        )
        if st in (200, 401, 403, 422):
            ok(f"LIVE generate without auth → {st} (expected gate or ok)")
        else:
            warn(f"LIVE generate without auth → {st}: {body[:120]!r}")
    except Exception as e:
        fail(f"live probe: {e}")
        fails += 1
        traceback.print_exc()

    # ── 5) Static code smells / known regressions ──
    section("5. Code smoke checks")
    app_js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    for needle, label in [
        ("markSessionReady", "session ready recovery"),
        ("removeTripAt", "trip delete button"),
        ("MIN_TRIP_ROWS", "print blank rows"),
        ("session-checking", "boot dim class used"),
        ("_sessionReadyDone", "session ready guard"),
    ]:
        if needle in app_js:
            ok(f"app.js has {label}")
        else:
            warn(f"app.js missing {label} ({needle})")

    exp = (ROOT / "modules" / "export.py").read_text(encoding="utf-8")
    if "default_driving_log.xlsx" in exp:
        ok("export uses default_driving_log.xlsx template")
    else:
        fail("export missing template reference")
        fails += 1
    if "점심제외" in exp and '"점심제외(분)"' in exp:
        fail("export still has 점심제외(분) column")
        fails += 1
    else:
        ok("export has no 점심제외(분) column")

    gen = (ROOT / "modules" / "generator.py").read_text(encoding="utf-8")
    if "enrich_trip_place_labels" in gen and "_DONG_TAIL_RE" in gen:
        ok("generator has place+dong enrichment")
    else:
        warn("generator place+dong helpers may be missing")

    # ── Summary ──
    section("SUMMARY")
    n_ok = sum(1 for s, _ in OUT if s == "OK")
    n_warn = sum(1 for s, _ in OUT if s == "WARN")
    n_fail = sum(1 for s, _ in OUT if s == "FAIL")
    print(f"OK={n_ok}  WARN={n_warn}  FAIL={n_fail}")
    print(f"Desktop: {DESKTOP}")
    for p in sorted(DESKTOP.glob(f"로드로그_검수_*{TODAY.replace('-', '')}*")):
        print(f"  file: {p.name} ({p.stat().st_size:,} bytes)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
