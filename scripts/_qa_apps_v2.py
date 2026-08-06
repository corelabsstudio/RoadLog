# -*- coding: utf-8 -*-
"""Live + local QA for RoadLog & WakeAgain."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "RoadLogQA/2.0", "Cache-Control": "no-cache"}


def get(url: str) -> tuple[bytes, int]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.status


def check(name: str, ok: bool, detail="") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"{mark} | {name}" + (f" | {detail}" if detail != "" else ""))
    return ok


fails = 0
total = 0


def t(name, ok, detail=""):
    global fails, total
    total += 1
    if not check(name, ok, detail):
        fails += 1


print("=== LIVE RoadLog ===")
body, st = get("https://roadlog.co.kr/?t=qa2")
text = body.decode("utf-8")
t("RL home 200", st == 200, st)
t("RL build meta", "20260729-tokens" in text)
t("RL free-fab class", "free-fab" in text)
t("RL free-fab 무료", "무료" in text)
for s in ("운행일지", "로드로그", "요금", "시작하기", "서식"):
    t(f"RL has '{s}'", s in text)
t("RL no U+FFFD", "\ufffd" not in text)
t("RL no raw mojibake", "¿" not in text and "Ã" not in text[:5000])

rb, _ = get("https://roadlog.co.kr/resources/")
rt = rb.decode("utf-8")
t("RL resources 200", len(rt) > 500, len(rt))
t("RL resources Korean", "서식" in rt or "무료" in rt)

bj, _ = get("https://roadlog.co.kr/build.json")
build = json.loads(bj.decode("utf-8"))
t("RL build.json", build.get("build") == "20260729-tokens", build)

cs, _ = get("https://roadlog.co.kr/styles.css?v=qa2")
css = cs.decode("utf-8", errors="replace")
t("CSS .free-fab", ".free-fab" in css)
t("CSS --paper", "--paper" in css)
t("CSS --stamp", "--stamp" in css)
t("CSS nav-fix present or clean nav", ".nav-inner" in css)

print("\n=== LIVE WakeAgain ===")
wb, st2 = get("https://wakeagain.com/?t=qa2")
wt = wb.decode("utf-8")
t("WA home 200", st2 == 200, len(wt))
t("WA theme-yard", "theme-yard" in wt)
t("WA yard-theme.css", "yard-theme.css" in wt)
t("WA accent cache bust", "20260729-accent" in wt)
t("WA Korean content", any(x in wt for x in ("웨이크", "사이드", "프로젝트", "중고", "마켓", "판매")))

ab, _ = get("https://wakeagain.com/app/")
at = ab.decode("utf-8")
t("WA app shell scripts", "app.js" in at and "app.css" in at)
t("WA app Korean", any(x in at for x in ("로그인", "마켓", "등록", "목록", "내 정보", "쿠폰")))

sc, _ = get("https://wakeagain.com/styles.css?v=qa2")
ss = sc.decode("utf-8", errors="replace")
t("WA --accent defined", re.search(r"--accent\s*:", ss) is not None)
purp = len(re.findall(r"--purple[\w-]*\s*:", ss))
acc = len(re.findall(r"--accent[\w-]*\s*:", ss))
t("WA accent defs >= purple", acc >= purp, f"accent={acc} purple={purp}")

yc, _ = get("https://wakeagain.com/yard-theme.css?v=qa2")
yt = yc.decode("utf-8", errors="replace")
t("yard-theme non-empty", len(yt) > 1000, len(yt))

print("\n=== LOCAL files ===")
root_rl = pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web")
root_wa = pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public")
for p in [
    root_rl / "index.html",
    root_rl / "styles.css",
    root_rl / "app.js",
    root_rl / "resources" / "index.html",
    root_wa / "index.html",
    root_wa / "app" / "index.html",
    root_wa / "styles.css",
    root_wa / "app" / "app.js",
]:
    raw = p.read_bytes()
    try:
        content = raw.decode("utf-8")
        enc_ok = True
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")
        enc_ok = False
    rep = content.count("\ufffd")
    t(f"UTF-8 {p.relative_to(p.parents[2] if 'RoadLog' in str(p) else p.parents[2])}", enc_ok and rep == 0, f"fffd={rep} bytes={len(raw)}")

# free-fab local
ih = (root_rl / "index.html").read_text(encoding="utf-8")
m = re.search(r'class="free-fab"[^>]*>[\s\S]{0,400}', ih)
if m:
    snippet = re.sub(r"\s+", " ", m.group(0))[:220]
    t("local free-fab has 서식/무료", "무료" in snippet or "서식" in snippet, snippet)
else:
    t("local free-fab exists", False, "missing")

# SW version align
sw = (root_rl / "sw.js").read_text(encoding="utf-8")
sw_ver = re.search(r'VERSION\s*=\s*"([^"]+)"', sw)
bj_local = json.loads((root_rl / "build.json").read_text(encoding="utf-8"))
t(
    "RL SW/build/meta align",
    sw_ver and sw_ver.group(1) == bj_local.get("build") == "20260729-tokens",
    f"sw={sw_ver.group(1) if sw_ver else None} build={bj_local.get('build')}",
)

# broken asset hrefs in index (relative paths that don't exist)
print("\n=== asset existence (RoadLog index) ===")
hrefs = re.findall(r'(?:href|src)="(/[^"#?]+)', ih)
missing = []
for h in sorted(set(hrefs)):
    if h.startswith("//"):
        continue
    if any(h.startswith(p) for p in ("/api", "/auth", "/blog/", "/resources")):
        # blog/resources are dirs; skip deep for now
        pass
    path = root_rl / h.lstrip("/")
    # skip dynamic SPA anchors
    if h in ("/", "/index.html"):
        continue
    if path.suffix and not path.exists():
        # try without leading
        missing.append(h)
t("RL index local assets exist", len(missing) == 0, missing[:15] if missing else "ok")

print("\n=== asset existence (WakeAgain index) ===")
wih = (root_wa / "index.html").read_text(encoding="utf-8")
whrefs = re.findall(r'(?:href|src)="(/[^"#?]+)', wih)
wmissing = []
for h in sorted(set(whrefs)):
    if h.startswith("//") or h in ("/", "/app/", "/app", "/blog/", "/guide/", "/sell.html", "/buy.html"):
        continue
    path = root_wa / h.lstrip("/")
    if path.suffix and not path.exists():
        wmissing.append(h)
t("WA index local assets exist", len(wmissing) == 0, wmissing[:15] if wmissing else "ok")

# app.js node-check already done externally; look for common JS bugs
print("\n=== static smell ===")
app_js = (root_rl / "app.js").read_text(encoding="utf-8")
t("RL app.js no debugger", "debugger" not in app_js)
t("RL app.js size", len(app_js) > 10000, len(app_js))

wa_app = (root_wa / "app" / "app.js").read_text(encoding="utf-8")
t("WA app.js no debugger", "debugger" not in wa_app)

# console.error left as throw? skip
# Check free-fab CSS for overflow/clip issues
ff = re.search(r"\.free-fab\s*\{[^}]+\}", css, re.S)
if ff:
    block = ff.group(0)
    t("free-fab has position fixed/absolute", "position:" in block, block[:180].replace("\n", " "))
else:
    # maybe multi-line with nested
    t("free-fab rule in live CSS", ".free-fab" in css)

print(f"\n=== SUMMARY fail={fails}/{total} ===")
sys.exit(1 if fails else 0)
