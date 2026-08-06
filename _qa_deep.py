# -*- coding: utf-8 -*-
"""Deeper static QA for RoadLog + WakeAgain app shells."""
from __future__ import annotations

import json
import re
import urllib.request
import ssl
import time
from pathlib import Path

RL = Path(r"C:\Users\hysoo\projects\RoadLog")
WA = Path(r"C:\Users\hysoo\projects\WakeAgain")
ctx = ssl.create_default_context()
H = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
issues: list[str] = []


def note(s: str):
    print("!", s)
    issues.append(s)


def ok(s: str):
    print("OK", s)


# ── RoadLog index structure ──
print("=== RoadLog local structure ===")
idx = (RL / "web/index.html").read_text(encoding="utf-8")
# version consistency
vers = {
    "rl-build": re.search(r'rl-build" content="([^"]+)"', idx).group(1),
    "BUILD": re.search(r'var BUILD = "([^"]+)"', idx).group(1),
    "css": re.search(r"styles\.css\?v=([^\"&]+)", idx).group(1),
    "js": re.search(r"app\.js\?v=([^\"&]+)", idx).group(1),
}
sw = re.search(r'const VERSION = "([^"]+)"', (RL / "web/sw.js").read_text(encoding="utf-8")).group(1)
bj = json.loads((RL / "web/build.json").read_text(encoding="utf-8"))["build"]
print("versions", vers, "sw", sw, "build.json", bj)
if len({vers["rl-build"], vers["BUILD"], vers["css"], vers["js"], sw, bj}) > 1:
    note(f"RoadLog version mismatch: {vers} sw={sw} bj={bj}")
else:
    ok("RoadLog versions aligned")

# critical IDs used by app.js
for eid in [
    "navLinks",
    "menuToggle",
    "btnAuth",
    "btnStart",
    "navLang",
    "guestHome",
    "appHome",
    "view-home",
    "view-create",
    "view-pricing",
    "free-fab" if False else "navResources",
]:
    pass

required_ids = [
    "navLinks",
    "menuToggle",
    "btnAuth",
    "btnStart",
    "navLang",
    "guestHome",
    "appHome",
    "view-home",
    "view-create",
    "view-pricing",
    "navResources",
]
for eid in required_ids:
    if f'id="{eid}"' not in idx and f"id='{eid}'" not in idx:
        # free-fab has id=navResources
        if eid == "navResources" and 'id="navResources"' in idx:
            ok(f"id {eid}")
            continue
        note(f"RoadLog missing id={eid}")
    else:
        ok(f"id {eid}")

if 'class="free-fab"' not in idx:
    note("RoadLog free-fab missing")
else:
    ok("free-fab present")

# free-fab full label
if "무료 서식" not in idx:
    note("RoadLog missing 무료 서식 text")
else:
    ok("무료 서식 text present")

# duplicate ids
ids = re.findall(r'\bid="([^"]+)"', idx)
from collections import Counter

dups = [k for k, v in Counter(ids).items() if v > 1]
# navResourcesMobile is separate - check real dups
if dups:
    note(f"RoadLog duplicate ids: {dups}")
else:
    ok("no duplicate ids in index")

# locales
for loc in ["ko.json", "en.json"]:
    p = RL / "web" / "locales" / loc
    try:
        json.loads(p.read_text(encoding="utf-8"))
        ok(f"locale {loc} valid JSON")
    except Exception as e:
        note(f"locale {loc} invalid: {e}")

# CSS free-fab not display:none accidentally on desktop
css = (RL / "web/styles.css").read_text(encoding="utf-8")
# broken comment check
if css.count("/*") != css.count("*/"):
    note(f"RoadLog CSS comment mismatch /* {css.count('/*')} */ {css.count('*/')}")
else:
    ok("RoadLog CSS comments balanced")

# ── WakeAgain ──
print("\n=== WakeAgain local structure ===")
widx = (WA / "public/index.html").read_text(encoding="utf-8")
if "숨을 불어넣다" not in widx:
    note("WA missing signature title")
else:
    ok("WA signature title")
if "theme-yard" not in widx:
    note("WA missing theme-yard body class")
else:
    ok("WA theme-yard")
# css order yard last
links = re.findall(r'href="(/[^"]+\.css[^"]*)"', widx)
print("css order", links)
if links and "yard-theme" not in links[-1]:
    note(f"WA yard-theme should load last, got {links}")
else:
    ok("WA yard-theme last")

# app shell
app_html = (WA / "public/app/index.html").read_text(encoding="utf-8")
for s in ["app.css", "app.js"]:
    if s not in app_html:
        note(f"WA app shell missing {s}")
    else:
        ok(f"WA app has {s}")

# accent tokens
yt = (WA / "public/yard-theme.css").read_text(encoding="utf-8")
if "--accent:" not in yt and "--accent :" not in yt:
    # might be --accent: with space
    if not re.search(r"--accent\s*:", yt):
        note("WA yard-theme missing --accent definition")
    else:
        ok("WA --accent defined")
else:
    ok("WA --accent defined")

# live API health if any
print("\n=== Live probes ===")
req = urllib.request.Request("https://roadlog.co.kr/build.json", headers=H)
try:
    bj = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read().decode())
    print("RL build.json", bj)
    if bj.get("build") != vers["rl-build"]:
        note(f"live build.json {bj.get('build')} != index {vers['rl-build']}")
    else:
        ok("live build.json matches index version token family or check separately")
except Exception as e:
    note(f"RL build.json fetch fail {e}")

# WA live accent
try:
    wa = urllib.request.urlopen(
        urllib.request.Request("https://wakeagain.com/?t=" + str(int(time.time())), headers=H),
        context=ctx,
        timeout=20,
    ).read().decode("utf-8", "replace")
    if "20260729-accent" not in wa:
        note("WA live not on accent CSS cache yet")
    else:
        ok("WA live accent CSS")
    if "숨을 불어넣다" not in wa:
        note("WA live missing signature")
    else:
        ok("WA live signature")
except Exception as e:
    note(f"WA live fail {e}")

# RL live free-fab CSS exists
try:
    st = urllib.request.urlopen(
        urllib.request.Request(
            "https://roadlog.co.kr/styles.css?v=" + vers["css"], headers=H
        ),
        context=ctx,
        timeout=20,
    ).read().decode("utf-8", "replace")
    if ".free-fab" not in st:
        note("RL live CSS missing .free-fab")
    else:
        ok("RL live CSS has .free-fab")
    if "nav-fix" not in st and "NAV HARD RESET" not in st:
        note("RL live CSS missing nav-fix block")
    else:
        ok("RL live CSS has nav-fix")
except Exception as e:
    note(f"RL css fetch {e}")

print("\n=== ISSUES ===")
if not issues:
    print("None critical from deep static QA")
else:
    for i in issues:
        print("-", i)
print("count", len(issues))
