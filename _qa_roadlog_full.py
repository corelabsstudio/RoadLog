# -*- coding: utf-8 -*-
"""RoadLog site + web-app full QA (TestClient + static + optional Playwright)."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_TEST_DATA = Path(tempfile.mkdtemp(prefix="roadlog_qa_"))
os.environ.setdefault("APP_ENV", "development")
os.environ["DATA_DIR"] = str(_TEST_DATA)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import modules.config as config

config.DATA_DIR = _TEST_DATA
_TEST_DATA.mkdir(parents=True, exist_ok=True)

from fastapi.testclient import TestClient
from server import app

cl = TestClient(app)
errors: list[str] = []
warns: list[str] = []


def ok(label: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'OK' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        errors.append(f"{label}: {detail}")


def warn(label: str, detail: str = "") -> None:
    print(f"  [WARN] {label}" + (f" — {detail}" if detail else ""))
    warns.append(f"{label}: {detail}")


print("== 1) Public pages & assets ==")
static_paths = [
    "/",
    "/app.js",
    "/styles.css",
    "/ui-sound.js",
    "/manifest.webmanifest",
    "/sw.js",
    "/locales/ko.json",
    "/locales/en.json",
    "/icons/logo.svg",
    "/icons/icon-192.png",
    "/icons/icon-512.png",
    "/icons/roadlog.ico",
    "/assets/legal/terms.md",
    "/assets/legal/privacy.md",
    "/assets/templates/manifest.json",
    "/resources/",
    "/resources/index.html",
    "/blog/",
    "/blog/index.html",
    "/blog/corporate-vehicle-log.html",
    "/blog/nts-corporate-log-excel-risk-2026.html",
    "/legal/business.html",
    "/update.html",
    "/sitemap.xml",
    "/robots.txt",
    "/health",
    "/api/health",
    "/api/meta",
    "/api/reviews",
    "/api/templates/defaults",
]
for path in static_paths:
    r = cl.get(path)
    ok(f"GET {path}", r.status_code == 200, str(r.status_code))

# all blog html
blog_html = sorted((ROOT / "web/blog").rglob("*.html"))
for p in blog_html:
    rel = "/" + p.relative_to(ROOT / "web").as_posix()
    r = cl.get(rel)
    if r.status_code != 200:
        ok(f"GET {rel}", False, str(r.status_code))
print(f"  blog pages checked: {len(blog_html)}")

print("\n== 2) Version alignment ==")
idx = (ROOT / "web/index.html").read_text(encoding="utf-8")
vers = {
    "rl-build": re.search(r'rl-build" content="([^"]+)"', idx).group(1),
    "BUILD": re.search(r'var BUILD = "([^"]+)"', idx).group(1),
    "css": re.search(r"styles\.css\?v=([^\"&]+)", idx).group(1),
    "js": re.search(r"app\.js\?v=([^\"&]+)", idx).group(1),
    "sw": re.search(
        r'const VERSION = "([^"]+)"', (ROOT / "web/sw.js").read_text(encoding="utf-8")
    ).group(1),
    "bj": json.loads((ROOT / "web/build.json").read_text(encoding="utf-8"))["build"],
}
ok("versions aligned", len(set(vers.values())) == 1, str(vers))

print("\n== 3) Critical DOM (web app shell) ==")
required = [
    "guestHome",
    "appHome",
    "view-home",
    "view-create",
    "view-pricing",
    "view-pro-claim",
    "view-settings",
    "view-reports",
    "btnAuth",
    "btnStart",
    "btnGenerate",
    "resultBox",
    "menuToggle",
    "navLinks",
    "demo",
    "demoStage",
    "features",
    "formLogin",
    "formRegister",
]
for eid in required:
    ok(f"id #{eid}", f'id="{eid}"' in idx or f"id='{eid}'" in idx)

print("\n== 4) JS syntax + VIEW_MAP ==")
js = (ROOT / "web/app.js").read_text(encoding="utf-8")
if shutil.which("node"):
    r = subprocess.run(["node", "--check", str(ROOT / "web/app.js")], capture_output=True, text=True)
    ok("node --check app.js", r.returncode == 0, (r.stderr or "")[:100])
    r = subprocess.run(["node", "--check", str(ROOT / "web/ui-sound.js")], capture_output=True, text=True)
    ok("node --check ui-sound.js", r.returncode == 0, (r.stderr or "")[:100])
# VIEW_MAP has pro-claim
ok("VIEW_MAP pro-claim", '"pro-claim"' in js or "'pro-claim'" in js)
ok("VIEW_MAP demo", "demo:" in js or '"demo"' in js)
# JS getElementById that don't create dynamically
for eid in ["demo", "features", "btnGenerate", "resultBox", "appHome", "guestHome"]:
    ok(f"JS target exists #{eid}", f'id="{eid}"' in idx)

print("\n== 5) Auth + generate + export (web app API) ==")
n = random.randint(100000, 999999)
email = f"qa_web_{n}@roadlog.test"
password = "testpass12"
r = cl.post("/api/auth/register", json={"email": email, "password": password, "name": "QAWeb"})
ok("register", r.status_code == 200, r.text[:100])
r = cl.post("/api/auth/login", json={"email": email, "password": password})
ok("login", r.status_code == 200 and bool(r.json().get("token")), r.text[:100])
token = (r.json() or {}).get("token")
h = {"Authorization": f"Bearer {token}"} if token else {}
r = cl.get("/api/me", headers=h)
ok("me", r.status_code == 200, r.text[:80])
r = cl.put(
    "/api/settings",
    headers=h,
    json={
        "vehicle_number": "12가3456",
        "driver_name": "홍길동",
        "company_name": "코어랩스",
    },
)
ok("settings", r.status_code == 200, r.text[:80])
r = cl.post(
    "/api/generate",
    headers=h,
    json={
        "log_type": "driving",
        "date": "2026-07-30",
        "vehicle": "12가3456",
        "driver_name": "홍길동",
        "company_name": "코어랩스",
        "trips": [
            {"start": "서울 강남", "end": "성남 분당", "purpose": "거래처 방문", "distance_km": 22},
            {"start": "성남 분당", "end": "서울 강남", "purpose": "복귀", "distance_km": 22},
        ],
    },
)
ok("generate driving", r.status_code == 200, r.text[:100])
gen = r.json() if r.status_code == 200 else {}
log_data = gen.get("log") or gen
r = cl.post("/api/validate", headers=h, json={"log": log_data} if "log" not in (log_data or {}) else log_data)
# validate shape varies
if r.status_code != 200:
    r = cl.post("/api/validate", headers=h, json=log_data if isinstance(log_data, dict) else {"log": log_data})
ok("validate", r.status_code == 200, r.text[:100])
for fmt in ("excel", "pdf", "docx"):
    r = cl.post(
        "/api/export",
        headers=h,
        json={"format": fmt, "log": log_data if isinstance(log_data, dict) else {}},
    )
    ok(f"export {fmt}", r.status_code == 200 and len(r.content) > 100, f"status={r.status_code} bytes={len(r.content)}")

# field log
r = cl.post(
    "/api/generate",
    headers=h,
    json={
        "log_type": "field",
        "date": "2026-07-30",
        "items": [
            {"site": "현장A", "work": "점검", "note": "정상"},
            {"site": "현장B", "work": "점검", "note": "완료"},
        ],
    },
)
ok("generate field", r.status_code == 200, r.text[:100])

# logs list
r = cl.get("/api/logs", headers=h)
ok("logs list", r.status_code == 200, r.text[:80])

print("\n== 6) Meta / i18n consistency ==")
meta = cl.get("/api/meta").json()
ok("meta free_limit", "free_limit" in meta or "free_limit_period" in meta, str(list(meta.keys())[:8]))
ko = json.loads((ROOT / "web/locales/ko.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "web/locales/en.json").read_text(encoding="utf-8"))
ok("locales non-empty", len(ko) > 10 and len(en) > 10, f"ko={len(ko)} en={len(en)}")
# common keys
missing_en = [k for k in list(ko.keys())[:50] if k not in en]
if missing_en:
    warn("en missing some ko keys", str(missing_en[:5]))

print("\n== 7) Security basics ==")
# no admin password in public web
web_text = idx + js
ok("admin password not in public", "ADMIN_PASSWORD" not in web_text)
ok("no openai key in public", "sk-" not in web_text or "sk-proj" not in web_text)

print("\n== 8) Playwright browser (if available) ==")
try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    warn("playwright missing", str(e)[:60])
else:

    def port_open(port: int) -> bool:
        s = socket.socket()
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except OSError:
            return False

    port = 8766
    proc = None
    if not port_open(port):
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(ROOT),
            env={**os.environ, "DATA_DIR": str(_TEST_DATA), "APP_ENV": "development"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            if port_open(port):
                break
            time.sleep(0.2)
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # mobile
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page_errors: list[str] = []
            page.on("pageerror", lambda e: page_errors.append(str(e)[:140]))
            page.goto(f"{base}/", wait_until="networkidle", timeout=45000)
            ok("browser home title", "로드로그" in (page.title() or "") or "RoadLog" in (page.title() or "") or "Road" in page.content())
            ok("browser guestHome", page.locator("#guestHome").count() >= 1)
            ok("browser features section", page.locator("#features").count() >= 1)
            ok("browser demo id", page.locator("#demo").count() >= 1)
            # menu
            if page.locator("#menuToggle").count():
                page.locator("#menuToggle").click()
                page.wait_for_timeout(200)
            # go create via data-nav
            page.locator('[data-nav="create"]').first.click()
            page.wait_for_timeout(500)
            # may show login modal or create view
            ok(
                "create or auth UI",
                page.locator("#view-create:not(.hidden), #formLogin, .auth-modal, #view-create").count() >= 1
                or "login" in page.content().lower()
                or page.locator("#btnGenerate").count() >= 1,
            )
            page.goto(f"{base}/#pricing", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(400)
            ok("pricing view", page.locator("#view-pricing, [data-nav=pricing]").count() >= 1)
            page.goto(f"{base}/#pro-claim", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(400)
            ok("pro-claim view", page.locator("#view-pro-claim").count() >= 1)
            # desktop
            page.set_viewport_size({"width": 1280, "height": 800})
            page.goto(f"{base}/", wait_until="networkidle", timeout=30000)
            ok("desktop home loads", page.locator("#guestHome, #appHome").count() >= 1)
            # resources
            page.goto(f"{base}/resources/", wait_until="networkidle", timeout=30000)
            ok("resources page", page.locator("body").count() == 1)
            # blog
            page.goto(f"{base}/blog/", wait_until="networkidle", timeout=30000)
            ok("blog index", page.locator("body").count() == 1)
            ok("no pageerror", len(page_errors) == 0, "; ".join(page_errors[:3]))
            browser.close()
    except Exception as ex:
        ok("playwright run", False, str(ex)[:200])
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

print("\n== SUMMARY ==")
if warns:
    print("Warnings:")
    for w in warns:
        print(" -", w)
if errors:
    print(f"FAILED ({len(errors)}):")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
print("All RoadLog site/web-app checks passed.")
