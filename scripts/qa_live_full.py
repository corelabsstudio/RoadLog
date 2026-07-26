# -*- coding: utf-8 -*-
"""Live QA suite for https://roadlog.co.kr — API + HTML smoke."""
from __future__ import annotations

import json
import re
import secrets
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

BASE = "https://roadlog.co.kr"
CTX = ssl.create_default_context()
RESULTS: list[dict] = []


def add(phase: str, name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(
        {"phase": phase, "name": name, "ok": bool(ok), "detail": (detail or "")[:400]}
    )
    mark = "OK" if ok else "FAIL"
    print(mark, phase, name, (detail or "")[:140])


def req(
    method: str,
    path: str,
    data: dict | None = None,
    token: str | None = None,
    timeout: int = 30,
) -> tuple[int, str, bytes]:
    headers = {
        "User-Agent": "RoadLog-QA/1.0",
        "Accept": "application/json,text/html,*/*",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        urljoin(BASE, path), data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=CTX) as res:
            return res.status, res.headers.get("Content-Type", ""), res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read()
    except Exception as e:
        return 0, "", str(e).encode("utf-8", "replace")


def main() -> None:
    # ── Phase 1: landing / public ──
    for path in [
        "/",
        "/build.json",
        "/api/health",
        "/api/meta",
        "/robots.txt",
        "/sitemap.xml",
        "/assets/legal/terms.md",
        "/assets/legal/privacy.md",
        "/app.js",
        "/styles.css",
        "/manifest.webmanifest",
    ]:
        st, ct, raw = req("GET", path)
        add(
            "P1",
            f"GET {path}",
            st in (200, 301, 302, 304),
            f"status={st} ct={ct[:50]} len={len(raw)}",
        )

    st, _, html_b = req("GET", "/")
    html = html_b.decode("utf-8", "replace") if st == 200 else ""
    for needle in [
        'data-nav="create"',
        'data-nav="pricing"',
        'data-nav="contact"',
        'data-nav="reports"',
        "view-reports",
        "btnUpgradePro",
        "pro-claim",
        "요금제",
        "시작",
        "업무 요약",
        "PDF 저장",
        "Excel 저장",
        "이미지 저장",
    ]:
        add("P1", f"landing/html has `{needle}`", needle in html, "")

    # unauth protected
    for path in [
        "/api/me",
        "/api/logs",
        "/api/logs/summary?period=month",
        "/api/settings",
        "/api/logs/summary/export?period=month&format=pdf",
    ]:
        st, _, raw = req("GET", path)
        add(
            "P2",
            f"unauth GET {path}",
            st in (401, 403),
            f"status={st} body={raw[:100]!r}",
        )

    st, _, raw = req("POST", "/api/generate", {"raw_text": "test"})
    add("P2", "unauth POST /api/generate", st in (401, 403), f"status={st}")

    # meta / pricing
    st, _, raw = req("GET", "/api/meta")
    meta = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
    add(
        "P4",
        "meta free_limit",
        isinstance(meta.get("free_limit"), int) and meta["free_limit"] > 0,
        str(meta.get("free_limit")),
    )
    add(
        "P4",
        "meta free_limit_period lifetime",
        meta.get("free_limit_period") == "lifetime",
        str(meta.get("free_limit_period")),
    )
    add(
        "P4",
        "meta pro_price",
        meta.get("pro_price") in (4900, 9900),
        str(meta.get("pro_price")),
    )
    add(
        "P4",
        "meta enterprise prices",
        meta.get("enterprise_price") == 89000
        and meta.get("enterprise_annual_price") == 890000,
        f"m={meta.get('enterprise_price')} a={meta.get('enterprise_annual_price')}",
    )
    add(
        "P4",
        "meta seat price",
        meta.get("enterprise_seat_price") == 8000,
        str(meta.get("enterprise_seat_price")),
    )
    add(
        "P4",
        "meta payment_ready",
        bool(meta.get("payment_ready")),
        str(meta.get("payment_ready")),
    )
    add(
        "P4",
        "meta pro_url smartstore",
        "smartstore.naver.com" in str(meta.get("pro_url") or ""),
        str(meta.get("pro_url") or "")[-50:],
    )
    add(
        "P4",
        "meta new product ids",
        "13684008" in str(meta.get("pro_url") or ""),
        str(meta.get("pro_url") or "")[-30:],
    )

    # auth validation
    st, _, raw = req("POST", "/api/auth/login", {"email": "bad", "password": ""})
    add("P2", "login invalid payload", st in (400, 401, 422), f"status={st} {raw[:100]!r}")

    st, _, raw = req(
        "POST",
        "/api/auth/register",
        {"email": "not-an-email", "password": "1", "name": "t"},
    )
    add("P2", "register invalid email", st in (400, 401, 422), f"status={st} {raw[:120]!r}")

    # register flow
    em = f"qa_{int(time.time())}_{secrets.token_hex(3)}@roadlog.test"
    pw = "QaTest!" + secrets.token_hex(4)
    st, _, raw = req(
        "POST",
        "/api/auth/register",
        {"email": em, "password": pw, "name": "QA Tester"},
    )
    add("P2", "register valid", st == 200, f"status={st} {raw[:160]!r}")
    token = None
    if st == 200:
        try:
            token = json.loads(raw.decode("utf-8", "replace")).get("token")
        except Exception:
            token = None
    if not token:
        st, _, raw = req("POST", "/api/auth/login", {"email": em, "password": pw})
        add("P2", "login fallback", st == 200, f"status={st}")
        if st == 200:
            token = json.loads(raw.decode("utf-8", "replace")).get("token")

    if not token:
        add("P2", "auth session", False, "no token — remaining authed tests skipped")
    else:
        st, _, raw = req("GET", "/api/me", token=token)
        me = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
        add(
            "P2",
            "/api/me session",
            st == 200 and bool(me.get("user")),
            f"usage={me.get('usage')} limit={me.get('limit')} period={me.get('free_limit_period')}",
        )
        add(
            "P4",
            "free lifetime on /me",
            me.get("free_limit_period") == "lifetime" or me.get("limit") == 15,
            f"period={me.get('free_limit_period')} limit={me.get('limit')}",
        )

        # empty generate validation-ish
        st, _, raw = req(
            "POST",
            "/api/generate",
            {"report_type": "driving", "raw_text": "", "form": {}},
            token=token,
            timeout=60,
        )
        add(
            "P3",
            "generate empty driving form",
            st in (200, 400, 422),
            f"status={st} {raw[:140]!r}",
        )

        # driving generate
        t0 = time.time()
        st, _, raw = req(
            "POST",
            "/api/generate",
            {
                "report_type": "driving",
                "raw_text": "",
                "form": {
                    "vehicle_number": "12가3456",
                    "odometer_start": 1000,
                    "odometer_end": 1035.5,
                    "morning_places": "강남 고객사",
                    "afternoon_places": "판교 협력사",
                    "extra_note": "QA 테스트 운행",
                },
            },
            token=token,
            timeout=120,
        )
        elapsed = time.time() - t0
        gen = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
        log = gen.get("log") if isinstance(gen, dict) else None
        add(
            "P3",
            "generate driving",
            st == 200 and isinstance(log, dict) and bool(log),
            f"status={st} engine={gen.get('engine')} sec={elapsed:.1f}",
        )
        add(
            "P5",
            "generate driving latency < 30s",
            elapsed < 30,
            f"{elapsed:.1f}s",
        )

        # field generate
        t0 = time.time()
        st, _, raw = req(
            "POST",
            "/api/generate",
            {
                "report_type": "field",
                "visits_text": "강남 A사 — 계약 협의 / 견적 재요청\n판교 B사 — 데모 시연",
                "work_summary": "고객 방문 QA",
                "next_actions": "목요일 견적 송부",
                "department": "영업1팀",
            },
            token=token,
            timeout=120,
        )
        elapsed = time.time() - t0
        gen2 = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
        log2 = gen2.get("log") if isinstance(gen2, dict) else {}
        visits = (log2 or {}).get("visits") or []
        add(
            "P3",
            "generate field",
            st == 200 and bool(log2),
            f"status={st} engine={gen2.get('engine')} visits={len(visits)} sec={elapsed:.1f}",
        )

        # long text
        st, _, raw = req(
            "POST",
            "/api/generate",
            {
                "report_type": "field",
                "visits_text": "가" * 1200,
                "work_summary": "긴 텍스트 QA",
            },
            token=token,
            timeout=120,
        )
        add(
            "P3",
            "generate long text 1200 chars",
            st in (200, 400, 422, 413),
            f"status={st} len={len(raw)}",
        )

        # save + list
        if isinstance(log, dict) and log:
            st, _, raw = req(
                "POST",
                "/api/logs",
                {"log": log, "report_type": "driving", "title": "QA 운행"},
                token=token,
            )
            add("P3", "save log", st == 200, f"status={st} {raw[:100]!r}")

        if isinstance(log2, dict) and log2:
            st, _, raw = req(
                "POST",
                "/api/logs",
                {"log": log2, "report_type": "field", "title": "QA 외근"},
                token=token,
            )
            add("P3", "save field log", st == 200, f"status={st}")

        st, _, raw = req("GET", "/api/logs?limit=20", token=token)
        logs = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
        add(
            "P3",
            "list logs",
            st == 200 and int(logs.get("count") or 0) >= 1,
            f"count={logs.get('count')}",
        )

        # summary
        for p in ("week", "month"):
            st, _, raw = req("GET", f"/api/logs/summary?period={p}", token=token)
            s = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
            add(
                "P4",
                f"summary {p}",
                st == 200 and "total_logs" in s and "report_text" in s,
                f"status={st} total={s.get('total_logs')} km={s.get('total_distance_km')} tops={len(s.get('top_places') or [])}",
            )

        # summary exports
        st, _, raw = req(
            "GET",
            "/api/logs/summary/export?period=month&format=pdf",
            token=token,
            timeout=90,
        )
        add(
            "P4",
            "export summary PDF",
            st == 200 and raw[:4] == b"%PDF",
            f"status={st} len={len(raw)} head={raw[:8]!r}",
        )
        st, _, raw = req(
            "GET",
            "/api/logs/summary/export?period=month&format=xlsx",
            token=token,
            timeout=90,
        )
        add(
            "P4",
            "export summary Excel",
            st == 200 and raw[:2] == b"PK",
            f"status={st} len={len(raw)}",
        )

        # log exports
        if isinstance(log, dict) and log:
            for fmt, magic in (
                ("pdf", b"%PDF"),
                ("xlsx", b"PK"),
                ("docx", b"PK"),
            ):
                st, _, raw = req(
                    "POST",
                    "/api/export",
                    {"log": log, "format": fmt},
                    token=token,
                    timeout=90,
                )
                ok = st == 200 and len(raw) > 100 and raw.startswith(magic)
                add(
                    "P3",
                    f"export log {fmt}",
                    ok,
                    f"status={st} len={len(raw)} head={raw[:6]!r}",
                )

        # paywall / billing
        st, _, raw = req("POST", "/api/billing/upgrade", {"plan": "pro"}, token=token)
        add(
            "P4",
            "demo billing upgrade blocked",
            st in (403, 400),
            f"status={st} {raw[:120]!r}",
        )

        st, _, raw = req(
            "POST",
            "/api/billing/claim",
            {"order_id": "", "email": em, "plan": "pro"},
        )
        add("P4", "claim empty order_id", st in (400, 422), f"status={st}")

        st, _, raw = req(
            "POST",
            "/api/billing/claim",
            {
                "order_id": "QAORDER123456",
                "email": em,
                "plan": "pro",
                "billing_period": "monthly",
                "name": "QA",
            },
        )
        add("P4", "claim valid order", st == 200, f"status={st} {raw[:140]!r}")

        st, _, raw = req(
            "GET",
            "/api/geo/reverse?lat=37.5665&lon=126.9780",
            token=token,
            timeout=40,
        )
        add(
            "P3",
            "geo reverse Seoul",
            st in (200, 429, 502, 503),
            f"status={st} {raw[:120]!r}",
        )

        # free limit message path (simulate by checking remain after gens)
        st, _, raw = req("GET", "/api/me", token=token)
        me2 = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
        add(
            "P4",
            "usage incremented after generate",
            int(me2.get("usage") or 0) >= 1,
            f"usage={me2.get('usage')} remain={me2.get('remain')}",
        )

    # Phase 5 static assets from index
    st, _, html_b = req("GET", "/")
    html = html_b.decode("utf-8", "replace") if st == 200 else ""
    assets = sorted(set(re.findall(r"""(?:src|href)=["'](/[^"'#?]+)""", html)))
    broken = []
    for a in assets:
        if a.startswith("//"):
            continue
        st, _, _ = req("GET", a)
        if st not in (200, 301, 302, 304):
            broken.append((a, st))
    add(
        "P5",
        "index static assets resolve",
        len(broken) == 0,
        f"broken={broken[:10]} checked={len(assets)}",
    )

    st, _, raw = req("GET", "/app.js?v=qa")
    js = raw.decode("utf-8", "replace") if st == 200 else ""
    add("P4", "app.js reports loader", "loadReportsSummary" in js, "")
    add("P4", "app.js report export", "downloadReportFile" in js or "summary/export" in js, "")
    add("P4", "app.js report png", "downloadReportPng" in js, "")
    add("P3", "app.js field+stamp mode", "reportMode" in js and "field" in js, "")
    add("P5", "app.js console throw patterns low risk", "TODO_BROKEN" not in js, "")

    st, _, raw = req("GET", "/api/health")
    health = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
    add(
        "P5",
        "health production/openai",
        bool(health.get("ok")) and (health.get("production") or health.get("env") == "production"),
        json.dumps(health, ensure_ascii=False)[:220],
    )
    add(
        "P5",
        "health openai true",
        health.get("openai") is True,
        str(health.get("openai")),
    )

    st, _, raw = req("GET", "/build.json")
    build = json.loads(raw.decode("utf-8", "replace")) if st == 200 else {}
    add(
        "P5",
        "build.json present",
        bool(build.get("build")),
        str(build.get("build")),
    )

    # write markdown report
    fails = [r for r in RESULTS if not r["ok"]]
    oks = [r for r in RESULTS if r["ok"]]
    out = Path(__file__).resolve().parents[1] / "docs" / "ops" / "QA_REPORT_20260727.md"
    lines = [
        "# RoadLog QA 검수 리포트",
        "",
        f"- Target: {BASE}",
        f"- Method: live HTTP/API suite (`scripts/qa_live_full.py`)",
        f"- Result: **{len(oks)} passed / {len(fails)} failed / {len(RESULTS)} total**",
        "",
        "## 총평",
        "",
    ]
    if not fails:
        lines.append(
            "핵심 API·인증·생성·요약·내보내기·결제 가드가 모두 정상 응답했습니다. "
            "브라우저 실기기 반응형·실 GPS 권한·콘솔 런타임은 본 스크립트 범위 밖입니다."
        )
    else:
        lines.append(
            f"총 {len(fails)}건 실패. 아래 우선순위 이슈를 먼저 확인하세요. "
            "통과 항목은 상세 섹션에 ✅로 표시됩니다."
        )
    lines += ["", "## 실패 항목", ""]
    if not fails:
        lines.append("- (없음)")
    for r in fails:
        lines.append(f"- **[{r['phase']}] {r['name']}** — {r['detail']}")
    lines += ["", "## 전체 체크리스트", ""]
    for r in RESULTS:
        mark = "✅" if r["ok"] else "❌"
        lines.append(f"- {mark} **[{r['phase']}] {r['name']}** — {r['detail']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("WROTE", out)
    print("SUMMARY", len(oks), "pass", len(fails), "fail")
    for r in fails:
        print("FAIL_ITEM", r)


if __name__ == "__main__":
    main()
