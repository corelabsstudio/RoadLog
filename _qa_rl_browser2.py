# -*- coding: utf-8 -*-
import os, random, socket, subprocess, sys, tempfile, time
from pathlib import Path
_TEST_DATA = Path(tempfile.mkdtemp(prefix="rl_br2_"))
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

port = 8769
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port)],
    cwd=str(ROOT), env={**os.environ, "DATA_DIR": str(_TEST_DATA), "APP_ENV": "development"},
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
for _ in range(80):
    if port_open(port): break
    time.sleep(0.2)
base = f"http://127.0.0.1:{port}"
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        pe = []
        page.on("pageerror", lambda e: pe.append(str(e)[:100]))
        page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(800)
        assert page.locator("#guestHome").count() == 1
        assert page.locator("#demo").count() == 1
        page.goto(base + "/#pricing", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        assert page.locator("#view-pricing").count() == 1
        page.goto(base + "/#pro-claim", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        assert page.locator("#view-pro-claim").count() == 1
        page.goto(base + "/", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        page.locator("#btnAuth").click()
        page.wait_for_timeout(400)
        # register
        page.locator("[data-auth-tab='register']").first.click()
        page.wait_for_timeout(300)
        em = f"br{random.randint(10000,99999)}@roadlog.test"
        page.fill("#regEmail", em)
        page.fill("#regName", "BrQA")
        page.fill("#regPw", "TestPass9x")
        page.fill("#regPw2", "TestPass9x")
        page.locator("#btnRegister").click()
        page.wait_for_timeout(2000)
        # login form should become visible
        page.locator("[data-auth-tab='login']").first.click()
        page.wait_for_timeout(300)
        page.fill("#loginEmail", em, force=True)
        page.fill("#loginPw", "TestPass9x", force=True)
        page.locator("#btnLogin").click()
        page.wait_for_timeout(2500)
        txt = page.locator("#btnAuth").inner_text()
        print("btnAuth after login:", txt)
        page.goto(base + "/#create", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        print("btnGenerate", page.locator("#btnGenerate").count())
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(base + "/", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        print("home panels", page.locator("#guestHome, #appHome").count())
        print("pageerrors", pe)
        browser.close()
        assert not pe, pe
        print("BROWSER ALL OK")
finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
