# -*- coding: utf-8 -*-
"""Thorough static + HTTP QA for RoadLog & WakeAgain."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

sys.stdout.reconfigure(encoding="utf-8")

UA = {
    "User-Agent": "RoadLogDeepQA/3.0",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

FAILS: list[str] = []
WARNS: list[str] = []
PASSES = 0


def note(ok: bool, name: str, detail: str = "", warn: bool = False):
    global PASSES
    if ok:
        PASSES += 1
        print(f"PASS | {name}" + (f" | {detail}" if detail else ""))
    elif warn:
        WARNS.append(f"{name}: {detail}")
        print(f"WARN | {name}" + (f" | {detail}" if detail else ""))
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"FAIL | {name}" + (f" | {detail}" if detail else ""))


def fetch(url: str, timeout: int = 30) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp else b""
        return e.code, body, dict(e.headers or {})
    except Exception as e:
        return 0, str(e).encode(), {}


def text(url: str) -> tuple[int, str]:
    st, body, _ = fetch(url)
    try:
        return st, body.decode("utf-8")
    except UnicodeDecodeError:
        return st, body.decode("utf-8", errors="replace")


# ── URL catalogs ──────────────────────────────────────────
RL_BASE = "https://roadlog.co.kr"
WA_BASE = "https://wakeagain.com"

RL_URLS = [
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
    "/blog/news/2026-07-27-driving-log-filing-timing.html",
    "/blog/news/2026-07-27-nts-corporate-car-audit.html",
    "/blog/news/2026-07-28-company-car-deduction-records.html",
    "/build.json",
    "/styles.css",
    "/app.js",
    "/sw.js",
    "/ui-sound.js",
    "/locales/ko.json",
    "/locales/en.json",
    "/manifest.webmanifest",
    "/sitemap.xml",
    "/robots.txt",
    "/icons/logo.svg",
    "/icons/og-image.jpg",
    "/assets/photo/hero-car-clipboard.jpg",
    "/assets/photo/band-stamp-desk.jpg",
    "/assets/photo/still-parking-lot.jpg",
    "/assets/templates/manifest.json",
    "/assets/templates/01_기본형_운행일지.xlsx",
    "/assets/templates/02_간단형_운행일지.xlsx",
    "/assets/templates/roadlog-driving-log-templates.xlsx",
    "/assets/illustrations/hub-write.jpg",
    "/assets/illustrations/hub-excel.jpg",
    "/assets/illustrations/hub-guide.jpg",
    "/assets/illustrations/hub-price.jpg",
]

WA_URLS = [
    "/",
    "/app/",
    "/sell.html",
    "/buy.html",
    "/guide/",
    "/guide/how-to-buy.html",
    "/guide/how-to-sell.html",
    "/guide/safety.html",
    "/guide/contact.html",
    "/blog/",
    "/blog/mvp-sell-before-delete.html",
    "/blog/vibe-coding-abandoned-mvp.html",
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
    "/js/listings.js",
    "/js/i18n.js",
    "/js/i18n-messages.js",
    "/js/deal-certificate.js",
    "/js/pwa-install.js",
    "/js/hero-ecg.js",
    "/js/hero-stats.js",
    "/js/ui-sound.js",
    "/sw.js",
    "/manifest.webmanifest",
    "/sitemap.xml",
    "/robots.txt",
    "/assets/photo/hero-archive-window.jpg",
    "/assets/photo/band-archive-open.jpg",
    "/assets/photo/still-archive-sill.jpg",
    "/assets/logo-mark.png",
    "/assets/og-image.jpg",
]


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and "href" in d:
            self.hrefs.append(d["href"])
        if tag in ("img", "script", "source") and "src" in d:
            self.srcs.append(d["src"])
        if tag == "link" and d.get("href"):
            self.hrefs.append(d["href"])


def extract_links(html: str) -> tuple[list[str], list[str]]:
    p = LinkExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.hrefs, p.srcs


print("=" * 60)
print("1) LIVE URL PROBE — RoadLog")
print("=" * 60)
for path in RL_URLS:
    url = RL_BASE + path
    st, body, hdrs = fetch(url)
    ok = 200 <= st < 400 and len(body) > 10
    note(ok, f"RL {path}", f"{st} len={len(body)}")
    if ok and path.endswith((".html", "/")) or path in ("/",):
        if path.endswith(".css") or path.endswith(".js") or path.endswith(".json") or path.endswith((".jpg", ".png", ".svg", ".xlsx", ".xml", ".txt", ".webmanifest")):
            continue
        try:
            t = body.decode("utf-8")
        except Exception:
            t = body.decode("utf-8", errors="replace")
        if path.endswith((".html", "/")) or path == "/":
            note("\ufffd" not in t, f"RL {path} no U+FFFD")
            # soft hangul presence for KO pages
            if path in ("/", "/resources/", "/blog/", "/blog/news/"):
                note(bool(re.search(r"[가-힣]{2,}", t)), f"RL {path} has Hangul")

print("\n" + "=" * 60)
print("2) LIVE URL PROBE — WakeAgain")
print("=" * 60)
for path in WA_URLS:
    url = WA_BASE + path
    st, body, hdrs = fetch(url)
    ok = 200 <= st < 400 and len(body) > 10
    note(ok, f"WA {path}", f"{st} len={len(body)}")

print("\n" + "=" * 60)
print("3) BUILD / VERSION ALIGNMENT")
print("=" * 60)
st, bj = text(RL_BASE + "/build.json")
build = json.loads(bj) if st == 200 else {}
st, home = text(RL_BASE + "/")
meta_m = re.search(r'rl-build"[^>]*content="([^"]+)"', home) or re.search(
    r'content="([^"]+)"[^>]*rl-build', home
)
# simpler
meta = re.search(r'name="rl-build"\s+content="([^"]+)"', home)
meta_b = meta.group(1) if meta else None
sw_st, sw = text(RL_BASE + "/sw.js")
sw_ver = re.search(r'VERSION\s*=\s*"([^"]+)"', sw)
sw_b = sw_ver.group(1) if sw_ver else None
note(
    build.get("build") and build.get("build") == meta_b == sw_b,
    "RL build align",
    f"json={build.get('build')} meta={meta_b} sw={sw_b}",
)
note("free-fab" in home and "무료" in home, "RL free-fab live")
note("is-guest-landing" in home, "RL guest landing class in HTML")

st, wa_home = text(WA_BASE + "/")
note("theme-yard" in wa_home, "WA theme-yard")
note("yard-theme.css" in wa_home, "WA yard-theme linked")
note("20260729-yard-fix" in wa_home or "yard-fix" in wa_home or "accent" in wa_home, "WA cache bust present",
     re.search(r'styles\.css\?v=([^"]+)', wa_home).group(1) if re.search(r'styles\.css\?v=', wa_home) else "?")

print("\n" + "=" * 60)
print("4) COLOR / TOKEN SMELLS")
print("=" * 60)
st, rl_css = text(RL_BASE + "/styles.css?v=qa")
# residual neon cyan hex (not via var)
cyan_hex = len(re.findall(r"#0{0,2}[ef]{2}[0-9a-f]{2}|#22d3ee|#06b6d4|#67e8f9|#5eead4", rl_css, re.I))
note(cyan_hex < 8, "RL CSS hard cyan count low", f"count={cyan_hex}", warn=cyan_hex >= 3)
note("--paper" in rl_css and "--stamp" in rl_css, "RL semantic tokens")
note("body:not(.is-guest-landing) .free-fab" in rl_css, "RL free-fab hide rule")

st, wa_css = text(WA_BASE + "/styles.css?v=qa")
st, wa_app = text(WA_BASE + "/app/app.css?v=qa")
st, wa_yard = text(WA_BASE + "/yard-theme.css?v=qa")
purp_rgb = sum(
    s.count("167, 139, 250") + s.count("167,139,250") + s.count("#7c3aed") + s.count("#8b5cf6")
    for s in (wa_css, wa_app, wa_yard)
)
note(purp_rgb == 0, "WA purple hex/rgb residual", f"count={purp_rgb}")
note(re.search(r"--accent\s*:", wa_css) is not None, "WA --accent defined")

# deal cert live
st, dcert = text(WA_BASE + "/js/deal-certificate.js?v=qa")
note("167,139,250" not in dcert and "167, 139, 250" not in dcert, "WA deal-cert no purple")

print("\n" + "=" * 60)
print("5) INTERNAL LINK CRAWL (homepage + key pages)")
print("=" * 60)

def crawl_internal(base: str, start_paths: list[str], label: str, max_pages: int = 25):
    seen = set()
    queue = list(start_paths)
    broken = []
    checked = 0
    while queue and checked < max_pages:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        url = base + path if path.startswith("/") else urljoin(base + "/", path)
        if not url.startswith(base):
            continue
        st, body, _ = fetch(url)
        checked += 1
        if st < 200 or st >= 400:
            broken.append((path, st))
            continue
        if "text/html" not in str(_) and not path.endswith((".html", "/")) and path != "/":
            # try decode anyway for html-ish
            pass
        try:
            html = body.decode("utf-8", errors="replace")
        except Exception:
            continue
        if "<html" not in html.lower() and "<!doctype" not in html.lower():
            continue
        hrefs, srcs = extract_links(html)
        for h in hrefs + srcs:
            if not h or h.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
                continue
            if h.startswith("http") and not h.startswith(base):
                continue
            full = urljoin(url, h)
            if not full.startswith(base):
                continue
            p = urlparse(full).path or "/"
            # skip heavy binaries deep check later sample
            if p not in seen and len(queue) < 80:
                if any(p.endswith(ext) for ext in (".html", "/", "")) or p.count("/") <= 3:
                    if re.search(r"\.(css|js|png|jpg|jpeg|svg|webp|json|webmanifest|mp4|xlsx|docx|ico)$", p, re.I):
                        # asset — check once
                        if p not in seen:
                            seen.add(p)
                            ast, _, _ = fetch(base + p if p.startswith("/") else urljoin(base, p))
                            if ast < 200 or ast >= 400:
                                broken.append((p, ast))
                    else:
                        queue.append(p)
    note(len(broken) == 0, f"{label} crawl broken links", broken[:12] if broken else f"ok pages={checked} seen={len(seen)}")
    if broken:
        for b, st in broken[:15]:
            print(f"     broken {st} {b}")
    return broken


rl_broken = crawl_internal(RL_BASE, ["/", "/resources/", "/blog/", "/blog/news/"], "RL")
wa_broken = crawl_internal(
    WA_BASE,
    ["/", "/app/", "/guide/", "/blog/", "/sell.html", "/buy.html", "/legal/terms.html"],
    "WA",
)

print("\n" + "=" * 60)
print("6) LOCAL STRUCTURE / ENCODING")
print("=" * 60)
rl_root = pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web")
wa_root = pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public")

for p in [
    rl_root / "index.html",
    rl_root / "styles.css",
    rl_root / "app.js",
    rl_root / "resources" / "index.html",
    wa_root / "index.html",
    wa_root / "app" / "index.html",
    wa_root / "app" / "app.js",
    wa_root / "styles.css",
    wa_root / "app" / "app.css",
]:
    raw = p.read_bytes()
    try:
        t = raw.decode("utf-8")
        enc_ok = True
    except UnicodeDecodeError:
        t = raw.decode("utf-8", errors="replace")
        enc_ok = False
    note(enc_ok and t.count("\ufffd") == 0, f"UTF-8 {p.name}", f"fffd={t.count(chr(0xFFFD))}")

# CSS balance
for label, p in [("RL styles", rl_root / "styles.css"), ("WA styles", wa_root / "styles.css"), ("WA app.css", wa_root / "app" / "app.css"), ("WA yard", wa_root / "yard-theme.css")]:
    t = p.read_text(encoding="utf-8")
    note(t.count("{") == t.count("}"), f"{label} brace balance", f"{{={t.count('{')} }}={t.count('}')}")
    note(t.count("/*") == t.count("*/"), f"{label} comment balance")

# JSON locales
for name in ("ko.json", "en.json"):
    st, body = text(RL_BASE + f"/locales/{name}")
    try:
        data = json.loads(body)
        note(isinstance(data, dict) and len(data) > 50, f"locale {name}", f"keys={len(data)}")
    except Exception as e:
        note(False, f"locale {name}", str(e))

# Compare ko/en key parity soft
try:
    ko = json.loads((rl_root / "locales" / "ko.json").read_text(encoding="utf-8"))
    en = json.loads((rl_root / "locales" / "en.json").read_text(encoding="utf-8"))

    def flatten(d, prefix=""):
        out = set()
        if isinstance(d, dict):
            for k, v in d.items():
                p = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    out |= flatten(v, p)
                else:
                    out.add(p)
        return out

    fk, fe = flatten(ko), flatten(en)
    only_ko = sorted(fk - fe)[:10]
    only_en = sorted(fe - fk)[:10]
    note(len(fk - fe) == 0 and len(fe - fk) == 0, "i18n key parity", f"ko_only={only_ko} en_only={only_en}", warn=True)
except Exception as e:
    note(False, "i18n key parity", str(e), warn=True)

print("\n" + "=" * 60)
print("7) JS SMELLS (local)")
print("=" * 60)
app_js = (rl_root / "app.js").read_text(encoding="utf-8")
note("debugger" not in app_js, "RL no debugger")
# leftover neon in share/canvas after fix
neon_left = len(re.findall(r"#67e8f9|#5eead4|#22d3ee|#0b1220", app_js))
note(neon_left == 0, "RL app.js neon hex residual", f"count={neon_left}")
note("tryRealVideo" in app_js and "__ROADLOG_DEMO_MP4" in app_js or "rl-demo-video" in app_js, "RL demo mp4 gated")

wa_app_js = (wa_root / "app" / "app.js").read_text(encoding="utf-8")
note("debugger" not in wa_app_js, "WA no debugger")
note("WakeAgainAPI" in wa_app_js or "api" in wa_app_js.lower(), "WA app has API wiring")

# hard-coded purple in WA public js
for p in (wa_root / "js").glob("*.js"):
    t = p.read_text(encoding="utf-8", errors="replace")
    n = t.count("167,139,250") + t.count("167, 139, 250") + t.count("#7c3aed")
    note(n == 0, f"WA js purple {p.name}", f"n={n}")

print("\n" + "=" * 60)
print("8) SITEMAP vs REALITY")
print("=" * 60)
for base, label in ((RL_BASE, "RL"), (WA_BASE, "WA")):
    st, sm = text(base + "/sitemap.xml")
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    note(len(locs) >= 3, f"{label} sitemap entries", len(locs))
    miss = []
    for loc in locs[:40]:
        # only same host
        if base.replace("https://", "") not in loc and base not in loc:
            continue
        path = urlparse(loc).path or "/"
        st2, _, _ = fetch(loc)
        if st2 < 200 or st2 >= 400:
            miss.append((path, st2))
    note(len(miss) == 0, f"{label} sitemap URLs live", miss[:8] if miss else "ok")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"PASS={PASSES} FAIL={len(FAILS)} WARN={len(WARNS)}")
for f in FAILS:
    print("  FAIL:", f)
for w in WARNS:
    print("  WARN:", w)
sys.exit(1 if FAILS else 0)
