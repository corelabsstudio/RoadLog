# -*- coding: utf-8 -*-
import json
import time
import urllib.error
import urllib.request
import ssl

BASE = "https://roadlog.co.kr"
CTX = ssl.create_default_context()


def req(method, path, data=None, token=None, timeout=60):
    h = {"User-Agent": "qa-recheck"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=timeout) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    st, raw = req("GET", "/build.json")
    print("build", raw.decode())

    st, html_b = req("GET", "/")
    html = html_b.decode("utf-8", "replace")
    st, js_b = req("GET", "/app.js")
    js = js_b.decode("utf-8", "replace")
    checks = [
        "view-reports",
        "업무 요약",
        "PDF 저장",
        'data-nav="reports"',
        "loadReportsSummary",
        "downloadReportFile",
        "downloadReportPng",
    ]
    for n in checks:
        in_html = n in html
        in_js = n in js
        print(f"has {n!r}: html={in_html} js={in_js}")

    em = f"qa_re_{int(time.time())}@roadlog.test"
    st, raw = req(
        "POST",
        "/api/auth/register",
        {"email": em, "password": "QaTest!xyz12345", "name": "q"},
    )
    token = json.loads(raw.decode()).get("token")
    print("register", st, "token", bool(token))

    st, raw = req("GET", "/api/logs/summary?period=month", token=token)
    print("summary", st, raw[:180])

    st, raw = req(
        "GET",
        "/api/logs/summary/export?period=month&format=pdf",
        token=token,
        timeout=90,
    )
    print("pdf", st, raw[:8], "len", len(raw))

    st, raw = req(
        "GET",
        "/api/logs/summary/export?period=month&format=xlsx",
        token=token,
        timeout=90,
    )
    print("xlsx", st, raw[:4], "len", len(raw))

    st, raw = req("GET", "/api/meta")
    m = json.loads(raw.decode())
    print(
        "meta",
        {
            k: m.get(k)
            for k in (
                "free_limit",
                "free_limit_period",
                "pro_price",
                "pro_url",
            )
        },
    )


if __name__ == "__main__":
    main()
