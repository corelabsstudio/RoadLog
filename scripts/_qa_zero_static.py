# -*- coding: utf-8 -*-
"""Deep static/live integrity for RoadLog + WakeAgain."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "ZeroQA/1", "Cache-Control": "no-cache"}
FAILS = []
WARNS = []


def get(url: str):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, (e.read() if e.fp else b""), {}
    except Exception as e:
        return 0, str(e).encode(), {}


def text(url: str):
    st, b, h = get(url)
    return st, b.decode("utf-8", "replace"), h


def fail(m):
    FAILS.append(m)
    print("FAIL", m)


def warn(m):
    WARNS.append(m)
    print("WARN", m)


def ok(m):
    print("PASS", m)


# --- RoadLog ---
print("=== RL live ===")
st, home, _ = text("https://roadlog.co.kr/?t=z")
st, bj, _ = text("https://roadlog.co.kr/build.json")
build = json.loads(bj).get("build") if st == 200 or bj else None
try:
    build = json.loads(bj).get("build")
except Exception:
    build = None
meta = re.search(r'name="rl-build"\s+content="([^"]+)"', home)
meta_b = meta.group(1) if meta else None
_, sw, _ = text("https://roadlog.co.kr/sw.js")
sw_m = re.search(r'VERSION\s*=\s*"([^"]+)"', sw)
sw_b = sw_m.group(1) if sw_m else None
if build and build == meta_b == sw_b:
    ok(f"RL build {build}")
else:
    fail(f"RL build misalign json={build} meta={meta_b} sw={sw_b}")

_, css, _ = text(f"https://roadlog.co.kr/styles.css?v={build or 'x'}")
for bad in ["#5eead4", "#67e8f9", "#22d3ee", "167, 139, 250", "#7c3aed"]:
    if bad in css:
        fail(f"RL CSS residual {bad} x{css.count(bad)}")
if "body:has(.view.active:not(#view-home)) .free-fab" not in css:
    fail("RL free-fab hide missing")
else:
    ok("RL free-fab hide")

# templates
for f in [
    "01_기본형_운행일지.xlsx",
    "02_간단형_운행일지.xlsx",
    "03_상세형_누적거리.xlsx",
    "04_영업외근형.xlsx",
    "05_현장공사형.xlsx",
    "01_기본형_운행일지.docx",
]:
    url = "https://roadlog.co.kr/assets/templates/" + urllib.parse.quote(f)
    st, body, _ = get(url)
    if st != 200 or len(body) < 500:
        fail(f"template {f} -> {st}/{len(body)}")
    else:
        ok(f"template {f}")

# RL many pages
rl_pages = [
    "/",
    "/resources/",
    "/blog/",
    "/blog/news/",
    "/blog/corporate-vehicle-log.html",
    "/blog/field-log-automation.html",
    "/blog/personal-vehicle-expense-log.html",
    "/blog/nts-corporate-log-excel-risk-2026.html",
    "/blog/employee-car-insurance-log-routine-2026.html",
    "/blog/vehicle-log-explanation-request-2026.html",
    "/update.html",
    "/locales/ko.json",
    "/locales/en.json",
    "/manifest.webmanifest",
    "/sitemap.xml",
    "/icons/logo.svg",
    "/assets/photo/hero-car-clipboard.jpg",
]
for p in rl_pages:
    st, body, _ = get("https://roadlog.co.kr" + p)
    if st < 200 or st >= 400 or len(body) < 20:
        fail(f"RL {p} -> {st}/{len(body)}")
    else:
        ok(f"RL {p}")
    if p.endswith(".html") or p.endswith("/"):
        t = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
        if "\ufffd" in t:
            fail(f"RL mojibake {p}")

# sitemap
_, sm, _ = text("https://roadlog.co.kr/sitemap.xml")
for loc in re.findall(r"<loc>([^<]+)</loc>", sm):
    st, b, _ = get(loc)
    if st < 200 or st >= 400:
        fail(f"RL sitemap dead {loc} {st}")

print("\n=== WA live ===")
wa_pages = [
    "/",
    "/app/",
    "/sell.html",
    "/buy.html",
    "/guide/",
    "/guide/how-to-sell.html",
    "/guide/how-to-buy.html",
    "/guide/safety.html",
    "/guide/contact.html",
    "/blog/",
    "/blog/mvp-sell-before-delete.html",
    "/legal/terms.html",
    "/legal/privacy.html",
    "/legal/delete-account.html",
    "/get-app.html",
    "/project.html",
    "/review.html",
    "/showcase.html",
    "/promo/event.html",
    "/styles.css",
    "/yard-theme.css",
    "/ux9.css",
    "/app/app.css",
    "/app/app.js",
    "/js/api.js",
    "/js/i18n.js",
    "/js/deal-certificate.js",
    "/guide/guide-visual.css",
    "/sw.js",
    "/sitemap.xml",
    "/manifest.webmanifest",
    "/assets/photo/hero-archive-window.jpg",
]
for p in wa_pages:
    st, body, _ = get("https://wakeagain.com" + p)
    if st < 200 or st >= 400 or len(body) < 20:
        fail(f"WA {p} -> {st}/{len(body)}")
    else:
        ok(f"WA {p}")

_, app, _ = text("https://wakeagain.com/app/?t=z")
if '<style id="wa-topbar-fix">' not in app:
    fail("WA app style tag broken")
else:
    ok("WA app style tag")
if re.search(r'styles\.css\?v=[^"\n]+"[a-zA-Z]', app):
    fail("WA app markup corrupted by cache-bust")
if "app-body" not in app or "theme-yard" not in app:
    fail("WA app body classes missing in source")
else:
    ok("WA app body classes")
if "header" not in app or "app-top" not in app:
    fail("WA app header missing in source")
else:
    ok("WA app header")

_, wa_css, _ = text("https://wakeagain.com/styles.css?v=z")
_, app_css, _ = text("https://wakeagain.com/app/app.css?v=z")
_, gcss, _ = text("https://wakeagain.com/guide/guide-visual.css?v=z")
blob = wa_css + app_css + gcss
for bad in ["167, 139, 250", "167,139,250", "#7c3aed", "#8b5cf6"]:
    if bad in blob:
        fail(f"WA CSS residual {bad}")
if "scale(1.08)" in gcss:
    fail("WA guide still has scale(1.08)")
else:
    ok("WA guide no scale bleed")

_, sm, _ = text("https://wakeagain.com/sitemap.xml")
for loc in re.findall(r"<loc>([^<]+)</loc>", sm):
    st, b, _ = get(loc)
    if st < 200 or st >= 400:
        fail(f"WA sitemap dead {loc} {st}")

print("\n=== Local integrity ===")
for root, lab in [
    (pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web"), "RL"),
    (pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public"), "WA"),
]:
    for p in root.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        if t.count("<style") != t.count("</style>"):
            fail(f"{lab} style mismatch {p.relative_to(root)}")
        if re.search(r'styles\.css\?v=[^"\n<>]+"[a-zA-Z]', t):
            fail(f"{lab} corrupt css bust {p.relative_to(root)}")
        if "\ufffd" in t:
            fail(f"{lab} fffd {p.relative_to(root)}")
    for p in root.rglob("*.css"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if t.count("{") != t.count("}"):
            fail(f"{lab} brace {p.relative_to(root)}")
        if t.count("/*") != t.count("*/"):
            fail(f"{lab} comment {p.relative_to(root)}")

# JS syntax via node is separate
print("\n=== SUMMARY FAIL", len(FAILS), "WARN", len(WARNS), "===")
for f in FAILS:
    print(" ", f)
sys.exit(1 if FAILS else 0)
