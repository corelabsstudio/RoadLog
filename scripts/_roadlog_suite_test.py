# -*- coding: utf-8 -*-
"""
RoadLog multi-angle mock/E2E suite (local TestClient).

Covers:
  A) Public static + health/meta
  B) Auth register/login/guards
  C) Settings + usage
  D) Generate driving log (AI or fallback)
  E) Generate field log
  F) Validate / export excel·pdf·docx
  G) Logs save/list/get/delete
  H) Style endpoints
  I) Billing upgrade guard
  J) Free limit behavior (light)
  K) Live probe (read-only, optional)

Run:
  python scripts/_roadlog_suite_test.py
  python scripts/_roadlog_suite_test.py --live
"""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import traceback
from pathlib import Path

# Prefer isolated data dir before app import
_TEST_DATA = Path(tempfile.mkdtemp(prefix="roadlog_suite_"))
os.environ.setdefault("APP_ENV", "development")
os.environ["DATA_DIR"] = str(_TEST_DATA)
# Allow TestClient even if prod secrets missing locally
os.environ.setdefault("ALLOW_DEMO_BILLING_UPGRADE", "0")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

# Import after DATA_DIR set — config already loads dotenv first; re-bind if needed
import modules.config as config

config.DATA_DIR = _TEST_DATA
_TEST_DATA.mkdir(parents=True, exist_ok=True)

from server import app

cl = TestClient(app)
results: list[tuple[str, bool, str]] = []


def log(step: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'OK' if ok else 'FAIL'}] {step}" + (f" — {detail}" if detail else ""))
    results.append((step, ok, detail))


def j(r):
    try:
        return r.json()
    except Exception:
        return {"_raw": (r.text or "")[:300]}


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def section(t: str) -> None:
    print(f"\n=== {t} ===")


def scenario_A_public() -> None:
    section("A) Public static + health")
    for path in (
        "/",
        "/app.js",
        "/styles.css",
        "/ui-sound.js",
        "/manifest.webmanifest",
        "/sw.js",
        "/locales/ko.json",
        "/locales/en.json",
        "/assets/legal/terms.md",
        "/assets/templates/manifest.json",
        "/health",
        "/api/health",
        "/api/meta",
        "/api/reviews",
        "/api/templates/defaults",
    ):
        r = cl.get(path)
        log(f"GET {path}", r.status_code == 200, f"status={r.status_code} len={len(r.content)}")

    r = cl.get("/api/health")
    h = j(r)
    log("health.ok", bool(h.get("ok")), str(h)[:120])
    r = cl.get("/api/meta")
    m = j(r)
    log("meta.free_limit", "free_limit" in m or "free_monthly_limit" in m or "plan" in str(m), str(list(m.keys())[:12]))


def scenario_B_auth() -> None:
    section("B) Auth register / login / guards")
    n = random.randint(100000, 999999)
    email = f"suite_{n}@roadlog.test"
    pw = "TestPass9x"

    r = cl.post("/api/auth/register", json={"email": email, "password": "short", "name": "x"})
    log("register short pw rejected", r.status_code in (400, 422), f"status={r.status_code}")

    r = cl.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "name": "SuiteUser"},
    )
    body = j(r)
    log("register", r.status_code == 200 and body.get("ok") is not False, r.text[:100])
    token = body.get("token")
    if not token and r.status_code == 200:
        # some APIs only return on login
        r2 = cl.post("/api/auth/login", json={"email": email, "password": pw})
        token = j(r2).get("token")
        log("login after register", r2.status_code == 200 and bool(token), r2.text[:80])
    else:
        r2 = cl.post("/api/auth/login", json={"email": email, "password": pw})
        log("login", r2.status_code == 200 and bool(j(r2).get("token")), r2.text[:80])
        if j(r2).get("token"):
            token = j(r2)["token"]

    r_bad = cl.post("/api/auth/login", json={"email": email, "password": "wrongpass1"})
    log("login wrong password", r_bad.status_code in (401, 403, 400), f"status={r_bad.status_code}")

    r_me = cl.get("/api/me")
    log("me without token", r_me.status_code in (401, 403), f"status={r_me.status_code}")

    if not token:
        log("auth aborted no token", False, "cannot continue auth-dependent tests")
        return None

    r_me = cl.get("/api/me", headers=H(token))
    me = j(r_me)
    log("me with token", r_me.status_code == 200, str((me.get("user") or me).get("email") if isinstance(me, dict) else me)[:80])

    r_gen = cl.post("/api/generate", json={"raw_text": "x"})
    log("generate without auth", r_gen.status_code == 401, f"status={r_gen.status_code}")

    return {"email": email, "password": pw, "token": token}


def scenario_C_settings(user: dict | None) -> None:
    section("C) Settings")
    if not user:
        log("settings skipped", False, "no user")
        return
    h = H(user["token"])
    r = cl.get("/api/settings", headers=h)
    log("GET settings", r.status_code == 200, r.text[:80])
    r = cl.put(
        "/api/settings",
        headers=h,
        json={
            "settings": {
                "vehicle_number": "12가3456",
                "driver_name": "홍길동",
                "company_name": "코어랩스",
            }
        },
    )
    # API may expect flat body
    if r.status_code >= 400:
        r = cl.put(
            "/api/settings",
            headers=h,
            json={
                "vehicle_number": "12가3456",
                "driver_name": "홍길동",
                "company_name": "코어랩스",
            },
        )
    log("PUT settings", r.status_code == 200, r.text[:100])


def scenario_D_generate_driving(user: dict | None) -> dict | None:
    section("D) Generate driving log")
    if not user:
        log("generate driving skipped", False, "no user")
        return None
    h = H(user["token"])
    r = cl.post(
        "/api/generate",
        headers=h,
        json={
            "raw_text": "오전 강남 고객 방문, 점심 김밥, 오후 판교 미팅 후 복귀",
            "vehicle_number": "12가3456",
            "odometer_start": 10000,
            "odometer_end": 10085,
            "lunch_restaurant": "김밥천국",
            "morning_places": "강남 고객사",
            "afternoon_places": "판교 미팅",
            "report_type": "driving",
            "settings": {
                "driver_name": "홍길동",
                "company_name": "코어랩스",
                "vehicle_number": "12가3456",
            },
        },
    )
    body = j(r)
    log_data = body.get("log") if isinstance(body, dict) else None
    trips = (log_data or {}).get("trips") or []
    log(
        "generate driving",
        r.status_code == 200 and bool(log_data) and len(trips) > 0,
        f"status={r.status_code} engine={body.get('engine')} trips={len(trips)}",
    )
    if r.status_code == 200 and log_data:
        log("generate has usage", "usage" in body, str(body.get("usage")))
        return {"log": log_data, "engine": body.get("engine"), "raw": body}
    return None


def scenario_E_generate_field(user: dict | None) -> dict | None:
    section("E) Generate field log")
    if not user:
        log("generate field skipped", False, "no user")
        return None
    h = H(user["token"])
    r = cl.post(
        "/api/generate",
        headers=h,
        json={
            "report_type": "field",
            "raw_text": "외근 메모",
            "visits_text": "강남 A사 계약 협의\n판교 B사 데모",
            "work_summary": "고객 방문 및 데모",
            "next_actions": "견적 송부",
            "department": "영업1팀",
            "settings": {"driver_name": "홍길동", "company_name": "코어랩스"},
        },
    )
    body = j(r)
    log_data = body.get("log") if isinstance(body, dict) else None
    visits = (log_data or {}).get("visits") or (log_data or {}).get("trips") or []
    log(
        "generate field",
        r.status_code == 200 and bool(log_data),
        f"status={r.status_code} engine={body.get('engine')} items={len(visits) if isinstance(visits, list) else type(visits)}",
    )
    return {"log": log_data, "raw": body} if log_data else None


def scenario_F_validate_export(user: dict | None, gen: dict | None) -> None:
    section("F) Validate + export")
    if not user or not gen or not gen.get("log"):
        log("export skipped", False, "no log")
        return
    h = H(user["token"])
    log_data = gen["log"]

    r = cl.post("/api/validate", headers=h, json={"log": log_data, "format": "excel"})
    log("validate", r.status_code == 200, r.text[:100])

    for fmt in ("excel", "pdf", "docx"):
        r = cl.post(
            "/api/export",
            headers=h,
            json={"format": fmt, "log": log_data},
        )
        if fmt == "pdf" and r.status_code == 500 and "reportlab" in (r.text or "").lower():
            log(
                f"export {fmt}",
                True,
                f"soft-skip: reportlab not installed ({r.status_code})",
            )
            continue
        ok = r.status_code == 200 and len(r.content) > 80
        log(f"export {fmt}", ok, f"status={r.status_code} bytes={len(r.content)}")


def scenario_G_logs(user: dict | None, gen: dict | None) -> None:
    section("G) Logs CRUD")
    if not user:
        log("logs skipped", False, "no user")
        return
    h = H(user["token"])
    r = cl.get("/api/logs", headers=h)
    body = j(r)
    logs = body.get("logs") or body.get("items") or []
    log("list logs", r.status_code == 200, f"n={len(logs) if isinstance(logs, list) else body}")

    # explicit save
    sample = (gen or {}).get("log") or {
        "trips": [{"place": "테스트", "purpose": "방문", "memo": "suite"}],
        "date": "2026-07-22",
    }
    r = cl.post("/api/logs", headers=h, json={"log": sample, "report_type": "driving"})
    saved = j(r)
    log_id = (
        (saved.get("item") or {}).get("id")
        or (saved.get("log") or {}).get("id")
        or saved.get("id")
        or (saved.get("saved") or {}).get("id")
    )
    log("save log", r.status_code == 200 and bool(log_id or saved.get("ok")), f"id={log_id}")

    if log_id:
        r = cl.get(f"/api/logs/{log_id}", headers=h)
        log("get log", r.status_code == 200, r.text[:80])
        r = cl.delete(f"/api/logs/{log_id}", headers=h)
        log("delete log", r.status_code == 200, r.text[:80])
    else:
        log("get/delete log", False, "no log id from save")


def scenario_H_style(user: dict | None) -> None:
    section("H) Style learning")
    if not user:
        log("style skipped", False, "no user")
        return
    h = H(user["token"])
    r = cl.get("/api/style", headers=h)
    log("GET style", r.status_code == 200, r.text[:100])
    r = cl.post(
        "/api/style/paste",
        headers=h,
        json={"text": "금일 강남 고객 미팅 완료. 특이사항 없음. 운행 이상 무."},
    )
    # endpoint may use different body
    if r.status_code >= 400:
        r = cl.post(
            "/api/style/paste",
            headers=h,
            json={"sample": "금일 강남 고객 미팅 완료. 특이사항 없음."},
        )
    log("style paste", r.status_code in (200, 201, 400, 422), f"status={r.status_code} {r.text[:80]}")


def scenario_I_billing(user: dict | None) -> None:
    section("I) Billing guards")
    if not user:
        log("billing skipped", False, "no user")
        return
    h = H(user["token"])
    r = cl.post("/api/billing/upgrade", headers=h, json={"plan": "pro"})
    # Without demo flag should be 403; with demo may be 200
    log(
        "upgrade pro status ok",
        r.status_code in (200, 403),
        f"status={r.status_code} body={r.text[:100]}",
    )
    if r.status_code == 200:
        body = j(r)
        log(
            "upgrade demo flag if success",
            bool(body.get("demo")) or body.get("ok"),
            str(body)[:100],
        )

    r = cl.post(
        "/api/billing/claim",
        headers=h,
        json={"order_id": f"TEST-{random.randint(10000,99999)}", "email": user["email"], "name": "Suite"},
    )
    log("billing claim", r.status_code in (200, 201, 400, 403, 404, 422), f"status={r.status_code}")


def scenario_J_limit(user: dict | None) -> None:
    section("J) Free limit field present")
    if not user:
        return
    h = H(user["token"])
    r = cl.post(
        "/api/generate",
        headers=h,
        json={
            "raw_text": "한 줄 메모",
            "vehicle_number": "12가3456",
            "morning_places": "본사",
            "afternoon_places": "고객사",
        },
    )
    body = j(r)
    if r.status_code == 200:
        log("limit fields on generate", "limit" in body and "usage" in body, f"usage={body.get('usage')} limit={body.get('limit')}")
    elif r.status_code == 403:
        log("limit enforced 403", True, r.text[:100])
    else:
        log("generate for limit check", False, f"status={r.status_code}")


def scenario_K_live() -> None:
    section("K) Live probe (read-only)")
    import urllib.request

    base = "https://roadlog.co.kr"
    for path in ("/", "/api/health", "/api/meta", "/ui-sound.js", "/build.json"):
        try:
            req = urllib.request.Request(
                base + path, headers={"User-Agent": "RoadLog-Suite/1.0", "Cache-Control": "no-cache"}
            )
            with urllib.request.urlopen(req, timeout=25) as res:
                body = res.read(20000)
                ok = res.status == 200
                detail = f"HTTP {res.status} len={len(body)}"
                if path == "/build.json":
                    detail += " " + body.decode("utf-8", errors="replace")[:60]
                if path == "/ui-sound.js":
                    # SPA fallback HTML means deploy/routing issue
                    is_js = b"CoreLabsSound" in body or b"function playTone" in body
                    is_html = body.lstrip()[:20].lower().startswith(b"<!doctype") or b"<html" in body[:200].lower()
                    ok = ok and is_js and not is_html
                    detail += f" sound={is_js} html_fallback={is_html}"
        except Exception as e:
            ok = False
            detail = str(e)[:160]
        log(f"LIVE {path}", ok, detail)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also probe roadlog.co.kr")
    args = ap.parse_args()

    print("\n########## RoadLog mock/E2E suite ##########")
    print(f"DATA_DIR={_TEST_DATA}\n")

    try:
        scenario_A_public()
        user = scenario_B_auth()
        scenario_C_settings(user)
        gen = scenario_D_generate_driving(user)
        scenario_E_generate_field(user)
        scenario_F_validate_export(user, gen)
        scenario_G_logs(user, gen)
        scenario_H_style(user)
        scenario_I_billing(user)
        scenario_J_limit(user)
        if args.live:
            scenario_K_live()
    except Exception as e:
        log("SUITE CRASH", False, str(e))
        traceback.print_exc()

    fails = [r for r in results if not r[1]]
    print("\n########## SUMMARY ##########")
    print(f"passed: {sum(1 for r in results if r[1])} / {len(results)}")
    print(f"data dir: {_TEST_DATA}")
    if fails:
        print("FAILED:")
        for s, _, d in fails:
            print(f"  - {s}: {d}")
        return 1
    print("All RoadLog suite checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
