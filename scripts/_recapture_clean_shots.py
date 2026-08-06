"""Recapture app screenshots without admin chrome for promo."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "marketing" / "promo" / "shots"


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


HIDE_JS = """
() => {
  const hideSel = (sel) => {
    document.querySelectorAll(sel).forEach((el) => {
      el.style.setProperty('display', 'none', 'important');
    });
  };
  hideSel('#adminViewAsBar');
  hideSel('[id*="viewAs"]');
  hideSel('.admin-view-as-bar');
  // banners mentioning free preview / return to admin
  document.querySelectorAll('div, section, header, aside').forEach((el) => {
    const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
    if (t.length > 80) return;
    if (/Free 사용자로 보는 중|관리자로 돌아가기/.test(t)) {
      el.style.setProperty('display', 'none', 'important');
    }
  });
  // soft user-facing labels
  const g = document.querySelector('#appHomeGreeting');
  if (g) g.textContent = '안녕하세요';
  const u = document.querySelector('#appHomeUsage');
  if (u) {
    u.innerHTML = '<span class="uil-badge uil-badge-free">Free</span><span>체험 0/10회 · 잔여 10회</span>';
  }
  document.querySelectorAll('button, a, span').forEach((el) => {
    const t = (el.textContent || '').trim();
    if (t.length > 28) return;
    if (/^관리자/.test(t) || /미리보기/.test(t) || /FREE \\(/.test(t)) {
      el.style.setProperty('display', 'none', 'important');
    }
  });
}
"""


def main() -> None:
    env = load_env()
    user = env.get("ADMIN_USERNAME", "hhs126")
    pw = env.get("ADMIN_PASSWORD", "")
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            locale="ko-KR",
        ).new_page()

        page.goto("https://roadlog.co.kr/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(800)
        page.locator("#btnAuth").first.click()
        page.wait_for_timeout(400)
        page.fill("#loginEmail", user)
        page.fill("#loginPw", pw)
        page.click("#btnLogin")
        page.wait_for_timeout(2500)

        # Force Free user preview (admin UI otherwise lands on dashboard)
        page.evaluate(
            """() => {
              try { localStorage.setItem('rl_view_as', 'free'); } catch (e) {}
              const freeBtn = document.querySelector('[data-view-as="free"]');
              if (freeBtn) freeBtn.click();
            }"""
        )
        page.wait_for_timeout(1200)

        page.goto("https://roadlog.co.kr/#home", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        # if still admin dashboard, click free again
        page.evaluate(
            """() => {
              const freeBtn = document.querySelector('[data-view-as="free"]');
              if (freeBtn) freeBtn.click();
            }"""
        )
        page.wait_for_timeout(1000)
        page.goto("https://roadlog.co.kr/#home", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.evaluate(HIDE_JS)
        page.wait_for_timeout(300)
        # ensure app home visible
        page.evaluate(
            """() => {
              const app = document.querySelector('#appHome');
              const guest = document.querySelector('#guestHome');
              if (app) app.classList.remove('hidden');
              if (guest) guest.classList.add('hidden');
            }"""
        )
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "app_home.png"), full_page=False)
        print("app_home")

        page.goto("https://roadlog.co.kr/#create", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.evaluate(HIDE_JS)
        page.evaluate("window.scrollTo(0, 380)")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "create_stamp.png"), full_page=False)
        print("create_stamp")

        page.goto("https://roadlog.co.kr/#reports", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.evaluate(HIDE_JS)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "reports.png"), full_page=False)
        print("reports")

        browser.close()
    print("ok")


if __name__ == "__main__":
    main()
