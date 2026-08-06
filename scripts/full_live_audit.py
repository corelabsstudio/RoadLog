"""Comprehensive live smoke audit for roadlog.co.kr."""
from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request
from typing import Any

BASE = "https://roadlog.co.kr"


def req(
    method: str,
    path: str,
    *,
    data: dict | None = None,
    token: str | None = None,
    timeout: int = 60,
) -> tuple[int, Any, dict]:
    headers = {"Cache-Control": "no-cache"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(
        BASE + path, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as res:
            raw = res.read()
            ct = res.headers.get("Content-Type", "")
            hdrs = {k.lower(): v for k, v in res.headers.items()}
            if "json" in ct or raw[:1] in (b"{", b"["):
                try:
                    return res.status, json.loads(raw.decode("utf-8")), hdrs
                except Exception:
                    return res.status, raw[:200], hdrs
            return res.status, raw, hdrs
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = raw[:300].decode("utf-8", errors="replace")
        return e.code, payload, {}


def ok(name: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def main() -> None:
    print(f"BASE {BASE}\n")
    results: list[tuple[str, bool]] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        ok(name, cond, detail)
        results.append((name, cond))

    # Static assets
    for path in (
        "/",
        "/app.js",
        "/styles.css",
        "/manifest.webmanifest",
        "/sw.js",
        "/icons/logo.svg",
        "/locales/ko.json",
        "/locales/en.json",
        "/assets/legal/terms.md",
        "/assets/legal/privacy.md",
        "/assets/templates/manifest.json",
        "/update.html",
    ):
        code, body, _ = req("GET", path)
        check(f"GET {path}", code == 200, f"status={code} type={type(body).__name__}")

    code, health, _ = req("GET", "/api/health")
    check("GET /api/health", code == 200 and isinstance(health, dict) and health.get("ok"))
    if isinstance(health, dict):
        check("health.openai", bool(health.get("openai")), str(health.get("openai")))
        check(
            "health.production",
            bool(health.get("production")) or health.get("env") == "production",
            f"env={health.get('env')}",
        )
        check("health.demo_billing_off", health.get("demo_billing_upgrade") is False)

    code, meta, _ = req("GET", "/api/meta")
    check("GET /api/meta", code == 200 and isinstance(meta, dict) and "free_limit" in meta)

    code, reviews, _ = req("GET", "/api/reviews")
    check(
        "GET /api/reviews",
        code == 200 and isinstance(reviews, dict) and "reviews" in reviews,
        f"n={len((reviews or {}).get('reviews') or []) if isinstance(reviews, dict) else 0}",
    )

    code, templates, _ = req("GET", "/api/templates/defaults")
    check("GET /api/templates/defaults", code == 200)

    # Unauth protections
    code, _, _ = req("POST", "/api/generate", data={"raw_text": "x"})
    check("generate without auth → 401", code == 401, f"status={code}")

    code, _, _ = req("GET", "/api/admin/dashboard")
    check("admin without auth → 401/403", code in (401, 403), f"status={code}")

    code, _, _ = req(
        "POST", "/api/billing/upgrade", data={"plan": "pro"}, token="fake"
    )
    check("billing upgrade fake token → 401/403", code in (401, 403), f"status={code}")

    # Auth flow
    email = f"audit_{secrets.token_hex(4)}@roadlog.test"
    pw = "AuditTest9x"
    code, reg, _ = req(
        "POST",
        "/api/auth/register",
        data={"email": email, "password": pw, "name": "Audit"},
    )
    check("register", code == 200 and isinstance(reg, dict) and reg.get("ok"), str(reg)[:80])

    code, short, _ = req(
        "POST",
        "/api/auth/register",
        data={"email": f"s_{secrets.token_hex(2)}@t.com", "password": "short", "name": "x"},
    )
    check("register short password rejected", code == 400, f"status={code}")

    code, login, _ = req(
        "POST", "/api/auth/login", data={"email": email, "password": pw}
    )
    token = (login or {}).get("token") if isinstance(login, dict) else None
    check("login", code == 200 and bool(token), f"status={code}")

    if not token:
        print("\nABORT: no token")
        failed = [n for n, c in results if not c]
        print(f"\nSUMMARY fail={len(failed)} / {len(results)}")
        for n in failed:
            print(" -", n)
        return

    code, me, _ = req("GET", "/api/me", token=token)
    check("GET /api/me", code == 200 and isinstance(me, dict), f"status={code}")

    code, settings, _ = req("GET", "/api/settings", token=token)
    check("GET /api/settings", code == 200, f"status={code}")

    code, put_s, _ = req(
        "PUT",
        "/api/settings",
        data={
            "settings": {
                "vehicle_number": "99가9999",
                "driver_name": "감사원",
                "company_name": "코어랩스",
            }
        },
        token=token,
    )
    check("PUT /api/settings", code == 200, f"status={code}")

    # Generate AI
    t0 = time.time()
    code, gen, _ = req(
        "POST",
        "/api/generate",
        data={
            "raw_text": "오전 강남 고객 방문, 오후 판교 미팅 후 복귀",
            "vehicle_number": "12가3456",
            "morning_places": "강남 고객사",
            "afternoon_places": "판교",
            "settings": {
                "driver_name": "홍길동",
                "company_name": "코어랩스",
                "vehicle_number": "12가3456",
            },
        },
        token=token,
        timeout=120,
    )
    dt = round(time.time() - t0, 1)
    log = (gen or {}).get("log") if isinstance(gen, dict) else None
    check(
        "POST /api/generate",
        code == 200 and isinstance(gen, dict) and bool(log),
        f"status={code} engine={gen.get('engine') if isinstance(gen, dict) else None} {dt}s",
    )
    if isinstance(gen, dict):
        check("generate engine openai", gen.get("engine") == "openai", str(gen.get("engine")))
        trips = (log or {}).get("trips") or []
        check("generate has trips", len(trips) > 0, f"n={len(trips)}")
        memos = " ".join(str(t.get("memo") or "") for t in trips)
        check(
            "no internal memo leak",
            "규칙 기반" not in memos and "OpenAI 키" not in memos,
            memos[:60],
        )

    # Logs list/save
    code, logs, _ = req("GET", "/api/logs", token=token)
    check(
        "GET /api/logs",
        code == 200 and isinstance(logs, dict),
        f"count={(logs or {}).get('count') if isinstance(logs, dict) else None}",
    )

    if log:
        code, saved, _ = req(
            "POST",
            "/api/logs",
            data={"log": log, "report_type": "driving", "title": "audit"},
            token=token,
        )
        check("POST /api/logs", code == 200, f"status={code}")

        for fmt in ("pdf", "excel", "docx"):
            code, blob, hdrs = req(
                "POST",
                "/api/export",
                data={"format": fmt, "log": log},
                token=token,
                timeout=60,
            )
            is_bin = isinstance(blob, (bytes, bytearray))
            check(
                f"export {fmt}",
                code == 200 and is_bin and len(blob) > 100,
                f"status={code} bytes={len(blob) if is_bin else 0} ct={hdrs.get('content-type','')[:40]}",
            )

        code, val, _ = req(
            "POST", "/api/validate", data={"log": log, "format": "pdf"}, token=token
        )
        check("POST /api/validate", code == 200, f"status={code}")

    # Style endpoints
    code, style, _ = req("GET", "/api/style", token=token)
    check("GET /api/style", code == 200, f"status={code}")

    code, paste, _ = req(
        "POST",
        "/api/style/paste",
        data={"title": "샘플", "text": "본사 출발 강남 방문 업무 출장 복귀"},
        token=token,
    )
    check("POST /api/style/paste", code == 200, f"status={code} {str(paste)[:60]}")

    # Field generate
    code, field, _ = req(
        "POST",
        "/api/generate",
        data={
            "report_type": "field",
            "visits_text": "강남 고객사 — 미팅 / 계약 협의",
            "work_summary": "외근 미팅",
            "settings": {"driver_name": "홍길동", "company_name": "코어랩스"},
        },
        token=token,
        timeout=120,
    )
    check(
        "generate field report",
        code == 200 and isinstance(field, dict) and bool((field or {}).get("log")),
        f"status={code} engine={field.get('engine') if isinstance(field, dict) else None}",
    )

    # Geo reverse (may depend on external)
    code, geo, _ = req(
        "GET", "/api/geo/reverse?lat=37.5665&lon=126.9780", token=token, timeout=30
    )
    check(
        "GET /api/geo/reverse",
        code in (200, 502),
        f"status={code} (502=external ok to note)",
    )

    # Wrong password
    code, _, _ = req(
        "POST", "/api/auth/login", data={"email": email, "password": "wrongpass1"}
    )
    check("login wrong password → 401", code == 401, f"status={code}")

    failed = [n for n, c in results if not c]
    print("\n========== SUMMARY ==========")
    print(f"PASS {len(results) - len(failed)} / {len(results)}")
    if failed:
        print("FAILED:")
        for n in failed:
            print(" -", n)
    else:
        print("All checks passed.")


if __name__ == "__main__":
    main()
