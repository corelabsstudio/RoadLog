# -*- coding: utf-8 -*-
"""RoadLog full QA pass 2 after fixes."""
from __future__ import annotations
import json, os, random, re, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path

_TEST_DATA = Path(tempfile.mkdtemp(prefix="roadlog_qa2_"))
os.environ.setdefault("APP_ENV", "development")
os.environ["DATA_DIR"] = str(_TEST_DATA)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import modules.config as config
config.DATA_DIR = _TEST_DATA
from fastapi.testclient import TestClient
from server import app
cl = TestClient(app)
errors = []

def ok(label, cond, detail=""):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        errors.append(f"{label}: {detail}")

print("== Static core ==")
for path in ["/", "/app.js", "/styles.css", "/api/health", "/api/meta", "/blog/", "/resources/", "/sitemap.xml"]:
    r = cl.get(path)
    ok(path, r.status_code == 200, str(r.status_code))

# all templates
man = cl.get("/assets/templates/manifest.json").json()
for t in man:
    for k in ("xlsx", "docx"):
        p = t.get(k)
        if not p: continue
        r = cl.get(p)
        ok(f"template {p}", r.status_code == 200 and len(r.content) > 500, f"{r.status_code} {len(r.content)}")

# all blog
for p in sorted((ROOT / "web/blog").rglob("*.html")):
    rel = "/" + p.relative_to(ROOT / "web").as_posix()
    r = cl.get(rel)
    ok(f"blog {rel}", r.status_code == 200)

print("== DOM ==")
idx = (ROOT / "web/index.html").read_text(encoding="utf-8")
for eid in ["demo", "demoStage", "features", "authLoginForm", "authRegisterForm", "guestHome", "appHome", "btnGenerate", "resultBox", "view-create", "view-pro-claim"]:
    ok(f"#{eid}", f'id="{eid}"' in idx)

print("== JS syntax ==")
if shutil.which("node"):
    for rel in ["web/app.js", "web/ui-sound.js"]:
        r = subprocess.run(["node", "--check", str(ROOT / rel)], capture_output=True, text=True)
        ok(f"syntax {rel}", r.returncode == 0, (r.stderr or "")[:80])

print("== API flow ==")
email = f"qa2_{random.randint(10000,99999)}@roadlog.test"
pw = "TestPass9x"
cl.post("/api/auth/register", json={"email": email, "password": pw, "name": "QA2"})
tok = cl.post("/api/auth/login", json={"email": email, "password": pw}).json()["token"]
h = {"Authorization": f"Bearer {tok}"}
r = cl.put("/api/settings", headers=h, json={"settings": {"vehicle_number": "12가3456", "driver_name": "홍길동", "company_name": "코어랩스"}})
ok("settings", r.status_code == 200)
r = cl.post("/api/generate", headers=h, json={
    "raw_text": "오전 강남 고객 방문, 점심 김밥, 오후 판교 미팅 후 복귀",
    "vehicle_number": "12가3456", "odometer_start": 10000, "odometer_end": 10085,
    "lunch_restaurant": "김밥천국", "morning_places": "강남 고객사", "afternoon_places": "판교 미팅",
    "report_type": "driving",
    "settings": {"driver_name": "홍길동", "company_name": "코어랩스", "vehicle_number": "12가3456"},
})
body = r.json()
log_data = body.get("log")
ok("generate", r.status_code == 200 and body.get("success") and log_data and (log_data.get("trips") or []), f"trips={len((log_data or {}).get('trips') or [])}")
r = cl.post("/api/validate", headers=h, json={"log": log_data})  # format optional now
ok("validate without format", r.status_code == 200, r.text[:80])
for fmt in ("excel", "pdf", "docx"):
    r = cl.post("/api/export", headers=h, json={"format": fmt, "log": log_data})
    ok(f"export {fmt}", r.status_code == 200 and len(r.content) > 1000, str(len(r.content)))

print("== Browser ==")
try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    print("  skip playwright", e)
else:
    def port_open(port):
        s = socket.socket(); s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port)); s.close(); return True
        except OSError:
            return False
    port = 8767
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env={**os.environ, "DATA_DIR": str(_TEST_DATA), "APP_ENV": "development"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        if port_open(port): break
        time.sleep(0.2)
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)[:120]))
            page.goto(base + "/", wait_until="networkidle", timeout=45000)
            ok("mobile home", page.locator("#guestHome").count() >= 1)
            ok("demo id", page.locator("#demo").count() == 1)
            page.locator('[data-nav="create"]').first.click()
            page.wait_for_timeout(600)
            # open auth if needed
            if page.locator("#authModal").count() and page.locator("#authModal.open, #authModal:not(.hidden)").count() == 0:
                page.locator("#btnAuth").click()
                page.wait_for_timeout(300)
            ok("auth form", page.locator("#authLoginForm, #loginEmail").count() >= 1)
            page.goto(base + "/#pricing", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(300)
            ok("pricing", page.locator("#view-pricing").count() >= 1)
            page.set_viewport_size({"width": 1280, "height": 800})
            page.goto(base + "/", wait_until="networkidle", timeout=30000)
            ok("desktop home", page.locator("#guestHome").count() >= 1)
            # interactive: register + generate
            page.goto(base + "/", wait_until="networkidle", timeout=30000)
            page.locator("#btnAuth").click()
            page.wait_for_timeout(400)
            # switch to register tab if needed
            tabs = page.locator("[data-auth-tab=register], button:has-text('가입')")
            if tabs.count():
                tabs.first.click()
                page.wait_for_timeout(200)
            em = f"browser_{random.randint(1000,9999)}@roadlog.test"
            if page.locator("#regEmail").count():
                page.fill("#regEmail", em)
                if page.locator("#regPw").count():
                    page.fill("#regPw", "TestPass9x")
                if page.locator("#regPw2").count():
                    page.fill("#regPw2", "TestPass9x")
                if page.locator("#regName").count():
                    page.fill("#regName", "BrowserQA")
                page.locator("#btnRegister").click()
                page.wait_for_timeout(1200)
            # login
            if page.locator("#loginEmail").count():
                page.fill("#loginEmail", em)
                page.fill("#loginPw", "TestPass9x")
                page.locator("#btnLogin").click()
                page.wait_for_timeout(1500)
            # after login app home or create
            ok("logged in UI", page.locator("#appHome:not(.hidden), #view-create, #btnGenerate").count() >= 1 or "로그아웃" in page.content() or page.locator("#btnAuth").inner_text() != "로그인")
            page.goto(base + "/#create", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(500)
            if page.locator("#btnGenerate").count():
                # fill fields if present
                for sel, val in [("#morningPlaces", "강남 고객"), ("#afternoonPlaces", "판교 미팅"), ("#odometerStart", "10000"), ("#odometerEnd", "10050")]:
                    if page.locator(sel).count():
                        page.fill(sel, val)
                page.locator("#btnGenerate").click()
                page.wait_for_timeout(8000)
                ok("generate result area", page.locator("#resultBox, #resultEditPanel").count() >= 1)
            ok("no pageerror", len(errs) == 0, "; ".join(errs[:3]))
            browser.close()
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except Exception: proc.kill()

print("== SUMMARY ==")
if errors:
    print("FAILED", len(errors))
    for e in errors: print(" -", e)
    raise SystemExit(1)
print("All RoadLog checks passed.")
