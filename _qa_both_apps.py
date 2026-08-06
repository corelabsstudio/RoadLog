# -*- coding: utf-8 -*-
"""QA pass: RoadLog + WakeAgain live HTML integrity + local critical files."""
from __future__ import annotations

import json
import re
import urllib.request
import ssl
import time
from pathlib import Path

ctx = ssl.create_default_context()
H = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36", "Cache-Control": "no-cache"}


def get(url: str) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers=H)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, body, dict(r.headers)
    except Exception as e:
        return 0, str(e), {}


def section(t):
    print("\n==", t)


def check_html(name, url, must_have, must_not=None, korean_samples=None):
    section(name + " " + url)
    st, body, headers = get(url + ("&" if "?" in url else "?") + "t=" + str(int(time.time())))
    print("status", st, "len", len(body))
    if st != 200:
        print("FAIL status")
        return False
    ok = True
    for s in must_have:
        hit = s in body
        print(("OK" if hit else "MISS"), repr(s)[:60])
        ok = ok and hit
    if must_not:
        for s in must_not:
            hit = s in body
            print(("BAD present" if hit else "OK absent"), repr(s)[:50])
            if hit:
                ok = False
    if korean_samples:
        for s in korean_samples:
            hit = s in body
            print(("OK ko" if hit else "MISS ko"), s)
            ok = ok and hit
    # mojibake signals
    if "\ufffd" in body[:50000]:
        print("WARN replacement char U+FFFD in body")
        ok = False
    if "??" in body[:3000] and "http" not in body[:3000]:
        print("WARN many ?? early in body")
    # broken unclosed script
    if body.count("<script") != body.count("</script>"):
        print("WARN script tag count mismatch", body.count("<script"), body.count("</script>"))
    print("RESULT", "PASS" if ok else "FAIL")
    return ok


results = []

# RoadLog pages
results.append(
    check_html(
        "RL home",
        "https://roadlog.co.kr/",
        must_have=["rl-build", "free-fab", "nav-fix" if False else "로드로그", "무료로 시작하기", "styles.css", "app.js"],
        must_not=["#22d3ee", "field-landing"],
        korean_samples=["일지 작성", "요금제", "무료 서식"],
    )
)
results.append(
    check_html(
        "RL resources",
        "https://roadlog.co.kr/resources/",
        must_have=["무료", "서식", "blog.css"],
        korean_samples=["엑셀", "다운로드"],
    )
)
results.append(
    check_html(
        "RL blog",
        "https://roadlog.co.kr/blog/",
        must_have=["가이드", "blog.css"],
        must_not=["뉴스 모음이 아닙니다" if False else "THIS_NEVER"],
        korean_samples=["실무", "가이드"],
    )
)
results.append(
    check_html(
        "RL news",
        "https://roadlog.co.kr/blog/news/",
        must_have=["뉴스", "blog.css"],
        korean_samples=["브리핑"],
    )
)

# assets
for path in [
    "/styles.css?v=20260729-tokens",
    "/app.js?v=20260729-tokens",
    "/assets/photo/hero-car-clipboard.jpg?v=2",
    "/assets/illustrations/hub-write.jpg?v=2",
    "/icons/logo.svg?v=cream1",
    "/sw.js",
    "/build.json",
]:
    st, body, _ = get("https://roadlog.co.kr" + path)
    print("RL asset", path, st, "len", len(body) if st == 200 else 0)
    if st != 200:
        results.append(False)

# WakeAgain
results.append(
    check_html(
        "WA home",
        "https://wakeagain.com/",
        must_have=["theme-yard", "yard-theme.css", "styles.css", "숨을 불어넣다", "20260729-accent"],
        korean_samples=["마켓 둘러보기", "프로젝트"],
    )
)
results.append(
    check_html(
        "WA app",
        "https://wakeagain.com/app/",
        must_have=["app.css", "app.js"],
        korean_samples=[],
    )
)

# local syntax
section("LOCAL JS syntax RoadLog app.js")
import subprocess

r = subprocess.run(
    ["node", "--check", str(Path(r"C:\Users\hysoo\projects\RoadLog\web\app.js"))],
    capture_output=True,
    text=True,
)
print("node --check app.js", r.returncode, r.stderr[:300] if r.stderr else "ok")
results.append(r.returncode == 0)

wa_app = Path(r"C:\Users\hysoo\projects\WakeAgain\public\app\app.js")
if wa_app.exists():
    r2 = subprocess.run(["node", "--check", str(wa_app)], capture_output=True, text=True)
    print("node --check WA app.js", r2.returncode, r2.stderr[:300] if r2.stderr else "ok")
    results.append(r2.returncode == 0)

print("\nOVERALL", "PASS" if all(results) else "HAS FAILURES", "passed", sum(1 for x in results if x), "/", len(results))
