"""Capture live RoadLog screenshots for long promo image."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "marketing" / "promo" / "shots"
OUT.mkdir(parents=True, exist_ok=True)


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if not p.exists():
        return env
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    env = load_env()
    user = env.get("ADMIN_USERNAME", "hhs126")
    pw = env.get("ADMIN_PASSWORD", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            locale="ko-KR",
        )
        page = ctx.new_page()

        page.goto("https://roadlog.co.kr/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "landing_mobile.png"), full_page=False)
        print("landing_mobile")

        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto("https://roadlog.co.kr/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "landing_desktop.png"), full_page=False)
        print("landing_desktop")

        page.evaluate("window.scrollTo(0, 750)")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "landing_features.png"), full_page=False)
        print("landing_features")

        # login
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("https://roadlog.co.kr/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(800)
        for sel in ["#btnAuth", "text=로그인"]:
            try:
                page.locator(sel).first.click(timeout=2000)
                break
            except Exception:
                pass
        page.wait_for_timeout(500)
        page.fill("#loginEmail", user)
        page.fill("#loginPw", pw)
        page.click("#btnLogin")
        page.wait_for_timeout(2500)

        # free preview if available
        for sel in [
            "button:has-text('Free')",
            "[data-view-as='free']",
            "#viewAsFree",
            "text=Free 사용자",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1000):
                    loc.click()
                    page.wait_for_timeout(900)
                    break
            except Exception:
                pass

        page.goto("https://roadlog.co.kr/#home", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "app_home.png"), full_page=False)
        print("app_home")

        page.goto("https://roadlog.co.kr/#create", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "create.png"), full_page=False)
        print("create")

        page.evaluate("window.scrollTo(0, 420)")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "create_stamp.png"), full_page=False)
        print("create_stamp")

        page.goto("https://roadlog.co.kr/#reports", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "reports.png"), full_page=False)
        print("reports")

        page.goto("https://roadlog.co.kr/#pricing", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "pricing.png"), full_page=False)
        print("pricing")

        browser.close()

    print("done", [p.name for p in OUT.glob("*.png")])


if __name__ == "__main__":
    main()
