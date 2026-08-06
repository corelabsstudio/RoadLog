# -*- coding: utf-8 -*-
"""Strict static/live HTTP checks — HTML integrity, tokens, templates, sitemaps."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "StrictQA/1.0", "Cache-Control": "no-cache"}
FAILS: list[str] = []
WARNS: list[str] = []


def get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""
    except Exception as e:
        return 0, str(e).encode()


def text(url: str) -> tuple[int, str]:
    st, b = get(url)
    return st, b.decode("utf-8", errors="replace")


def fail(msg: str):
    FAILS.append(msg)
    print("FAIL", msg)


def warn(msg: str):
    WARNS.append(msg)
    print("WARN", msg)


def ok(msg: str):
    print("PASS", msg)


print("=== RoadLog live ===")
st, home = text("https://roadlog.co.kr/?t=s")
bj_st, bj = text("https://roadlog.co.kr/build.json")
build = json.loads(bj).get("build") if bj_st == 200 else None
meta = re.search(r'name="rl-build"\s+content="([^"]+)"', home)
meta_b = meta.group(1) if meta else None
sw_st, sw = text("https://roadlog.co.kr/sw.js")
sw_b = re.search(r'VERSION\s*=\s*"([^"]+)"', sw)
sw_ver = sw_b.group(1) if sw_b else None
if build and build == meta_b == sw_ver:
    ok(f"RL build align {build}")
else:
    fail(f"RL build misalign json={build} meta={meta_b} sw={sw_ver}")

st, css = text(f"https://roadlog.co.kr/styles.css?v={build or 'x'}")
for bad, name in [
    ("#5eead4", "cyan-5eead4"),
    ("#67e8f9", "cyan-67e8"),
    ("#22d3ee", "cyan-22d3"),
    ("167, 139, 250", "purple-rgb"),
    ('styles.css?v=', "self-ref-odd"),
]:
    if bad in css and name != "self-ref-odd":
        fail(f"RL CSS residual {name} count={css.count(bad)}")
if "body:has(.view.active:not(#view-home)) .free-fab" not in css:
    fail("RL free-fab hide rule missing")
else:
    ok("RL free-fab hide rule")

# templates with proper encoding
for fname in [
    "01_기본형_운행일지.xlsx",
    "01_기본형_운행일지.docx",
    "05_현장공사형.xlsx",
]:
    url = "https://roadlog.co.kr/assets/templates/" + urllib.parse.quote(fname)
    st, body = get(url)
    if st != 200 or len(body) < 100:
        fail(f"RL template {fname} -> {st} len={len(body)}")
    else:
        ok(f"RL template {fname} {len(body)}b")

# update page
st, up = text("https://roadlog.co.kr/update.html")
if "#67e8f9" in up or "#22d3ee" in up:
    fail("RL update.html still neon")
else:
    ok("RL update.html cream")
if build and build not in up:
    warn(f"RL update.html BUILD may lag live={build}")

print("\n=== WakeAgain live ===")
st, wa = text("https://wakeagain.com/?t=s")
if "theme-yard" not in wa:
    fail("WA home no theme-yard")
else:
    ok("WA home theme-yard")
st, app = text("https://wakeagain.com/app/?t=s")
if '<style id="wa-topbar-fix">' not in app:
    fail("WA app critical style broken/missing")
else:
    ok("WA app style tag intact")
if 'styles.css?v=' in app and re.search(r'styles\.css\?v=[^"\n]+"[a-zA-Z]', app):
    fail("WA app corrupt styles version in markup")
if "<body class=\"app-body theme-yard\">" not in app and "app-body theme-yard" not in app:
    fail("WA app body classes missing in HTML")
else:
    ok("WA app body classes in HTML")
if "<header" not in app or "app-top" not in app:
    fail("WA app header missing in HTML")
else:
    ok("WA app header in HTML")

st, wa_css = text("https://wakeagain.com/styles.css?v=x")
st, app_css = text("https://wakeagain.com/app/app.css?v=x")
purp = (wa_css + app_css).count("167, 139, 250") + (wa_css + app_css).count("167,139,250")
if purp:
    fail(f"WA purple rgb residual {purp}")
else:
    ok("WA no purple rgb")

# HTML integrity local
print("\n=== Local HTML integrity ===")
for root, label in [
    (pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web"), "RL"),
    (pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public"), "WA"),
]:
    for p in root.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        if t.count("<style") != t.count("</style>"):
            fail(f"{label} style mismatch {p.relative_to(root)}")
        if re.search(r'styles\.css\?v=[^"\n<>]+"[a-zA-Z]', t):
            fail(f"{label} corrupt css version ate markup {p.relative_to(root)}")
        if "\ufffd" in t:
            fail(f"{label} U+FFFD {p.relative_to(root)}")

# local residual colors
rl_css = pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web\styles.css").read_text(encoding="utf-8")
for bad in ["#5eead4", "#67e8f9", "#22d3ee", "167, 139, 250"]:
    if bad in rl_css:
        fail(f"RL local CSS still has {bad}")
wa_paths = list(pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public").rglob("*.css"))
joined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in wa_paths)
if "167, 139, 250" in joined or "#7c3aed" in joined:
    fail("WA local CSS purple residual")
else:
    ok("WA local CSS clean of purple hex/rgb")

print("\n=== SUMMARY ===")
print(f"FAIL={len(FAILS)} WARN={len(WARNS)}")
for f in FAILS:
    print(" ", f)
for w in WARNS:
    print(" ", w)
sys.exit(1 if FAILS else 0)
