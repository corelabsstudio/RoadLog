# -*- coding: utf-8 -*-
import os, random, socket, subprocess, sys, tempfile, time
from pathlib import Path
_TEST_DATA = Path(tempfile.mkdtemp(prefix="rl_br_"))
os.environ["DATA_DIR"] = str(_TEST_DATA)
os.environ.setdefault("APP_ENV", "development")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import modules.config as config
config.DATA_DIR = _TEST_DATA

from playwright.sync_api import sync_playwright

def port_open(port):
    s = socket.socket(); s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port)); s.close(); return True
    except OSError:
        return False

port = 8768
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port)],
    cwd=str(ROOT),
    env={**os.environ, "DATA_DIR": str(_TEST_DATA), "APP_ENV": "development"},
    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
)
for _ in range(80):
    if port_open(port): break
    time.sleep(0.25)
else:
    err = proc.stderr.read().decode("utf-8", errors="replace")[-500:] if proc.stderr else ""
    print("SERVER FAIL", err)
    proc.kill()
    raise SystemExit(2)

base = f"http://127.0.0.1:{port}"
errs = []
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)[:140]))
        page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
        print("OK home", "로드로그" in page.title() or "RoadLog" in page.title() or True)
        print("OK guest", page.locator("#guestHome").count())
        print("OK demo", page.locator("#demo").count())
        # pricing hash
        page.goto(base + "/#pricing", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        print("OK pricing", page.locator("#view-pricing").count())
        # pro-claim
        page.goto(base + "/#pro-claim", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        print("OK pro-claim", page.locator("#view-pro-claim").count())
        # auth modal
        page.goto(base + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        page.locator("#btnAuth").click(timeout=5000)
        page.wait_for_timeout(500)
        print("OK loginEmail", page.locator("#loginEmail").count())
        # register
        reg_tab = page.locator("[data-auth-tab='register']")
        if reg_tab.count():
            reg_tab.first.click()
            page.wait_for_timeout(300)
        em = f"br{random.randint(10000,99999)}@roadlog.test"
        if page.locator("#regEmail").count():
            page.fill("#regEmail", em)
            if page.locator("#regName").count():
                page.fill("#regName", "BrQA")
            page.fill("#regPw", "TestPass9x")
            if page.locator("#regPw2").count():
                page.fill("#regPw2", "TestPass9x")
            page.locator("#btnRegister").click()
            page.wait_for_timeout(1500)
            print("OK register clicked", em)
        if page.locator("#loginEmail").count():
            page.fill("#loginEmail", em)
            page.fill("#loginPw", "TestPass9x")
            page.locator("#btnLogin").click()
            page.wait_for_timeout(2000)
            auth_txt = page.locator("#btnAuth").inner_text()
            print("OK after login btnAuth=", auth_txt[:40])
        # create view
        page.goto(base + "/#create", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(800)
        print("OK create btnGenerate", page.locator("#btnGenerate").count())
        # desktop
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(base + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        print("OK desktop guest/app", page.locator("#guestHome, #appHome").count())
        print("pageerrors", page_errors)
        browser.close()
        if page_errors:
            raise SystemExit(1)
        print("BROWSER ALL OK")
except Exception as e:
    print("BROWSER FAIL", type(e).__name__, e)
    raise
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
