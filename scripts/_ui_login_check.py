# -*- coding: utf-8 -*-
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(r"C:\Users\hysoo\projects\RoadLog")
env = {}
for p in (ROOT / ".env", ROOT / "railway-variables.env"):
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
user = env.get("ADMIN_USERNAME") or env.get("ADMIN_EMAIL") or ""
pw = env.get("ADMIN_PASSWORD") or ""
fails = 0
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.goto("https://roadlog.co.kr/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    page.click("#btnAuth")
    page.wait_for_timeout(400)
    page.fill("#loginEmail", user)
    page.fill("#loginPw", pw)
    page.click("#btnLogin")
    page.wait_for_timeout(2500)
    app = page.evaluate(
        "() => !document.getElementById('appHome')?.classList.contains('hidden')"
    )
    print("appHome visible", app)
    if not app:
        fails += 1
    for nav, exp in [
        ("create", "view-create"),
        ("settings", "view-settings"),
        ("style", "view-style"),
        ("reports", "view-reports"),
        ("pricing", "view-pricing"),
        ("home", "view-home"),
    ]:
        page.locator(f'[data-nav="{nav}"]').first.click(force=True)
        page.wait_for_timeout(700)
        av = page.evaluate("() => document.querySelector('.view.active')?.id")
        ok = av == exp
        print(("OK" if ok else "FAIL"), nav, "->", av)
        if not ok:
            fails += 1
    page.locator('[data-nav="create"]').first.click(force=True)
    page.wait_for_timeout(500)
    print("btnGenerate visible", page.locator("#btnGenerate").is_visible())
    page.screenshot(path=str(Path.home() / "Desktop" / "ui_login_ok.png"))
    b.close()
print("fails", fails)
raise SystemExit(1 if fails else 0)
