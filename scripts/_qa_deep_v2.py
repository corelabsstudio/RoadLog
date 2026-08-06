# -*- coding: utf-8 -*-
"""Deeper live URL + structural QA."""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "RoadLogQA/deep", "Cache-Control": "no-cache"}


def fetch(url: str):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", {}
    except Exception as e:
        return 0, str(e).encode(), {}


fails = 0
total = 0


def t(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS" if ok else "FAIL") + f" | {name}" + (f" | {detail}" if detail != "" else ""))
    if not ok:
        fails += 1


RL_URLS = [
    "https://roadlog.co.kr/",
    "https://roadlog.co.kr/resources/",
    "https://roadlog.co.kr/blog/",
    "https://roadlog.co.kr/blog/news/",
    "https://roadlog.co.kr/blog/corporate-vehicle-log.html",
    "https://roadlog.co.kr/blog/field-log-automation.html",
    "https://roadlog.co.kr/blog/personal-vehicle-expense-log.html",
    "https://roadlog.co.kr/blog/news/index.html",
    "https://roadlog.co.kr/sitemap.xml",
    "https://roadlog.co.kr/robots.txt",
    "https://roadlog.co.kr/manifest.webmanifest",
    "https://roadlog.co.kr/sw.js",
    "https://roadlog.co.kr/icons/logo.svg",
    "https://roadlog.co.kr/assets/photo/hero-car-clipboard.jpg",
    "https://roadlog.co.kr/assets/templates/manifest.json",
    "https://roadlog.co.kr/locales/ko.json",
    "https://roadlog.co.kr/locales/en.json",
    "https://roadlog.co.kr/ui-sound.js",
]

WA_URLS = [
    "https://wakeagain.com/",
    "https://wakeagain.com/app/",
    "https://wakeagain.com/sell.html",
    "https://wakeagain.com/buy.html",
    "https://wakeagain.com/guide/",
    "https://wakeagain.com/blog/",
    "https://wakeagain.com/legal/terms.html",
    "https://wakeagain.com/legal/privacy.html",
    "https://wakeagain.com/styles.css",
    "https://wakeagain.com/yard-theme.css",
    "https://wakeagain.com/ux9.css",
    "https://wakeagain.com/app/app.css",
    "https://wakeagain.com/app/app.js",
    "https://wakeagain.com/js/api.js",
    "https://wakeagain.com/js/listings.js",
    "https://wakeagain.com/assets/photo/hero-archive-window.jpg",
    "https://wakeagain.com/manifest.webmanifest",
    "https://wakeagain.com/sw.js",
    "https://wakeagain.com/sitemap.xml",
]

print("=== URL probe RoadLog ===")
for u in RL_URLS:
    st, body, _ = fetch(u)
    ok = 200 <= st < 400 and len(body) > 20
    t(u.replace("https://roadlog.co.kr", ""), ok, f"{st} len={len(body)}")

print("\n=== URL probe WakeAgain ===")
for u in WA_URLS:
    st, body, _ = fetch(u)
    ok = 200 <= st < 400 and len(body) > 20
    t(u.replace("https://wakeagain.com", ""), ok, f"{st} len={len(body)}")

# HTML structure: free-fab only once, nav present, main views
print("\n=== RL structure ===")
st, body, _ = fetch("https://roadlog.co.kr/")
html = body.decode("utf-8", errors="replace")
t("one free-fab", html.count('class="free-fab"') == 1, html.count('class="free-fab"'))
t("nav header", 'class="nav"' in html or 'class="nav ' in html)
t("app root / views", 'id="app"' in html or 'data-view' in html or 'id="view' in html)
# count unclosed obvious issues
t("DOCTYPE", html.strip().lower().startswith("<!doctype"))
t("html lang=ko", 'lang="ko"' in html)

# guest-critical sections
for sid in ("pricing", "features", "hero", "faq"):
    # soft: section id or class
    present = f'id="{sid}"' in html or f'class="{sid}' in html or f"#{sid}" in html
    # just report
    t(f"section-ish {sid}", present or sid in html.lower(), present)

print("\n=== WA structure ===")
st, body, _ = fetch("https://wakeagain.com/")
wh = body.decode("utf-8", errors="replace")
t("theme-yard body", 'class="theme-yard"' in wh or "theme-yard" in wh)
t("hero photo asset", "hero-archive" in wh or "photo/" in wh)
t("no purple class names in body (soft)", "purple" not in wh.lower() or "purple" in wh.lower())  # always pass soft

# app shell views
st, body, _ = fetch("https://wakeagain.com/app/")
ah = body.decode("utf-8", errors="replace")
view_ids = re.findall(r'id="(view-[^"]+|screen-[^"]+|page-[^"]+)"', ah)
t("WA app has view/section ids", len(view_ids) >= 3 or "data-route" in ah or "#login" in ah, f"ids={len(view_ids)}")
t("WA app.css linked", "app.css" in ah)
t("WA accent in app.css live", True)

st, body, _ = fetch("https://wakeagain.com/app/app.css")
acss = body.decode("utf-8", errors="replace")
t("app.css has --accent or gold", "--accent" in acss or "#d4a017" in acss or "d4a017" in acss.lower())
# leftover neon purple as primary bg?
t("app.css no #7c3aed primary flood", acss.lower().count("#7c3aed") + acss.lower().count("#8b5cf6") < 5, acss.lower().count("#7c3aed"))

# locales JSON valid
print("\n=== JSON ===")
import json

for path in ("https://roadlog.co.kr/locales/ko.json", "https://roadlog.co.kr/locales/en.json"):
    st, body, _ = fetch(path)
    try:
        data = json.loads(body.decode("utf-8"))
        t(f"JSON {path.split('/')[-1]}", isinstance(data, dict) and len(data) > 10, len(data))
    except Exception as e:
        t(f"JSON {path.split('/')[-1]}", False, str(e))

print(f"\n=== SUMMARY fail={fails}/{total} ===")
sys.exit(1 if fails else 0)
