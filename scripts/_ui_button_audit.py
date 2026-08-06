# -*- coding: utf-8 -*-
"""Live UI button audit for RoadLog homepage/app with Playwright."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

BASE = "https://roadlog.co.kr"
DESK = Path.home() / "Desktop"
OUT = DESK / "로드로그_UI검수결과.txt"
results: list[tuple[str, str]] = []


def log(status: str, msg: str) -> None:
    line = f"[{status}] {msg}"
    print(line)
    results.append((status, msg))


def active_view(page) -> str:
    return page.evaluate(
        """() => {
      const v = document.querySelector('.view.active');
      return v ? v.id : '';
    }"""
    )


def body_classes(page) -> str:
    return page.evaluate("() => document.body.className")


def guest_app_state(page) -> dict:
    return page.evaluate(
        """() => ({
      guestHidden: document.getElementById('guestHome')?.classList.contains('hidden') ?? null,
      appHidden: document.getElementById('appHome')?.classList.contains('hidden') ?? null,
      sessionChecking: document.body.classList.contains('session-checking'),
      sessionReady: document.body.classList.contains('session-ready'),
      modalOpen: document.body.classList.contains('modal-open'),
      authShow: document.getElementById('authModal')?.classList.contains('show') ?? null,
      careOpen: document.getElementById('careModal')?.classList.contains('is-open') ?? null,
    })"""
    )


def click_data_nav(page, name: str, wait_ms: int = 800) -> bool:
    sel = f'[data-nav="{name}"]'
    loc = page.locator(sel).first
    if loc.count() == 0:
        log("FAIL", f"data-nav={name} not found in DOM")
        return False
    # prefer visible
    visible = page.locator(f'{sel}:visible').first
    try:
        if visible.count() > 0:
            visible.click(timeout=5000)
        else:
            loc.click(timeout=5000, force=True)
        page.wait_for_timeout(wait_ms)
        return True
    except Exception as e:
        log("FAIL", f"click data-nav={name}: {e}")
        return False


def main() -> int:
    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []

        page.on(
            "console",
            lambda msg: console_errors.append(msg.text)
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # ── Load ──
        log("INFO", f"open {BASE}")
        try:
            page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        except PwTimeout:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)

        st = guest_app_state(page)
        log("INFO", f"body classes: {body_classes(page)}")
        log("INFO", f"home state: {st}")
        if st.get("sessionChecking") and not st.get("sessionReady"):
            log("FAIL", "stuck in session-checking (dimmed home)")
            fails += 1
        else:
            log("OK", "session-ready or not stuck checking")

        if st.get("modalOpen") or st.get("authShow"):
            log("WARN", f"modal unexpectedly open at boot: {st}")

        # ── Guest landing CTAs ──
        log("INFO", "--- Guest navigation ---")
        nav_targets = [
            ("pricing", "view-pricing"),
            ("guide", "view-guide"),
            ("news", "view-news"),
            ("contact", "view-contact"),
            ("about", "view-about"),
            ("home", "view-home"),
            ("create", "view-create"),
            ("home", "view-home"),
        ]
        for nav, expect_view in nav_targets:
            if not click_data_nav(page, nav):
                fails += 1
                continue
            av = active_view(page)
            if av == expect_view:
                log("OK", f"nav {nav} → {av}")
            else:
                # some map create→view-create etc
                log("FAIL", f"nav {nav} expected {expect_view}, got {av}")
                fails += 1
            page.screenshot(path=str(DESK / f"ui_nav_{nav}.png"), full_page=False)

        # free templates link
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)
            link = page.locator('a[href="/resources/"]').first
            if link.count():
                link.click(timeout=5000)
                page.wait_for_timeout(1500)
                if "/resources" in page.url:
                    log("OK", "resources link works")
                else:
                    log("FAIL", f"resources link url={page.url}")
                    fails += 1
            else:
                log("WARN", "resources link not found")
        except Exception as e:
            log("FAIL", f"resources: {e}")
            fails += 1

        # ── Auth modal ──
        log("INFO", "--- Auth modal ---")
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        try:
            page.locator("#btnAuth").click(timeout=5000)
            page.wait_for_timeout(500)
            if page.locator("#authModal.show").count() or page.evaluate(
                "() => document.getElementById('authModal')?.classList.contains('show')"
            ):
                log("OK", "login button opens auth modal")
            else:
                # check display
                vis = page.locator("#authModal").is_visible()
                if vis:
                    log("OK", "auth modal visible")
                else:
                    log("FAIL", "auth modal not shown")
                    fails += 1
            # close
            if page.locator("#authClose").count():
                page.locator("#authClose").click(timeout=3000)
                page.wait_for_timeout(400)
            st2 = guest_app_state(page)
            if st2.get("authShow") or st2.get("modalOpen"):
                log("FAIL", f"auth still open after close: {st2}")
                fails += 1
            else:
                log("OK", "auth modal closes")
        except Exception as e:
            log("FAIL", f"auth modal: {e}")
            fails += 1

        # ── Login with admin ──
        log("INFO", "--- Login flow ---")
        env = {}
        for pth in (Path(r"C:\Users\hysoo\projects\RoadLog\.env"),
                    Path(r"C:\Users\hysoo\projects\RoadLog\railway-variables.env")):
            if not pth.exists():
                continue
            for line in pth.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        user = env.get("ADMIN_USERNAME") or env.get("ADMIN_EMAIL") or ""
        pw = env.get("ADMIN_PASSWORD") or ""
        if user and pw:
            try:
                page.locator("#btnAuth").click(timeout=5000)
                page.wait_for_timeout(400)
                page.fill("#authEmail", user)
                page.fill("#authPassword", pw)
                page.locator("#btnLogin").click(timeout=5000)
                page.wait_for_timeout(2500)
                st3 = guest_app_state(page)
                if not st3.get("appHidden"):
                    log("OK", "after login appHome visible")
                else:
                    log("FAIL", f"appHome still hidden after login: {st3}")
                    fails += 1
                page.screenshot(path=str(DESK / "ui_after_login.png"), full_page=False)

                # app home buttons
                for label, sel in [
                    ("home tab driving", "#homeTabDriving"),
                    ("home tab field", "#homeTabField"),
                    ("home stamp btn", "#btnHomeQuickStamp"),
                    ("start create from tile", '[data-nav="create"]'),
                ]:
                    loc = page.locator(sel).first
                    try:
                        if loc.count() == 0:
                            log("WARN", f"{label}: not found")
                            continue
                        # stamp may need permission - just check enabled
                        disabled = loc.is_disabled() if loc.is_visible() else None
                        log("OK" if disabled is not True else "WARN",
                            f"{label}: visible={loc.is_visible()} disabled={disabled}")
                    except Exception as e:
                        log("FAIL", f"{label}: {e}")
                        fails += 1

                # navigate create
                if click_data_nav(page, "create", 1000):
                    av = active_view(page)
                    if av == "view-create":
                        log("OK", "logged-in nav create → view-create")
                    else:
                        log("FAIL", f"logged-in create got {av}")
                        fails += 1
                    # generate button present
                    if page.locator("#btnGenerate").count():
                        log("OK", "btnGenerate present")
                    else:
                        log("FAIL", "btnGenerate missing")
                        fails += 1

                # mode switch
                try:
                    page.locator('#homeTabField, .report-mode-tab[data-report-mode="field"]').first.click(timeout=3000)
                    page.wait_for_timeout(400)
                    log("OK", "clicked field mode tab")
                except Exception as e:
                    log("WARN", f"field mode tab: {e}")

                for nav in ("settings", "style", "reports", "pricing", "home"):
                    if click_data_nav(page, nav, 700):
                        av = active_view(page)
                        log("OK", f"logged-in nav {nav} → {av}")
                    else:
                        fails += 1
            except Exception as e:
                log("FAIL", f"login flow: {e}")
                fails += 1
        else:
            log("WARN", "no admin creds; skip login UI tests")

        # ── Mobile viewport ──
        log("INFO", "--- Mobile viewport ---")
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        try:
            if page.locator("#menuToggle").is_visible():
                page.locator("#menuToggle").click(timeout=3000)
                page.wait_for_timeout(400)
                log("OK", "mobile menu toggle works")
                if click_data_nav(page, "pricing", 800):
                    log("OK", f"mobile nav pricing → {active_view(page)}")
                else:
                    fails += 1
            else:
                log("WARN", "menuToggle not visible on mobile")
        except Exception as e:
            log("FAIL", f"mobile nav: {e}")
            fails += 1
        page.screenshot(path=str(DESK / "ui_mobile.png"), full_page=False)

        # ── Console errors ──
        if page_errors:
            for e in page_errors[:10]:
                log("FAIL", f"pageerror: {e[:200]}")
                fails += 1
        else:
            log("OK", "no pageerror")
        # filter noisy console
        real_errs = [
            e
            for e in console_errors
            if "favicon" not in e.lower()
            and "net::ERR" not in e
            and "Failed to load resource" not in e
        ]
        if real_errs:
            for e in real_errs[:8]:
                log("WARN", f"console: {e[:180]}")
        else:
            log("OK", "no critical console errors")

        browser.close()

    # write report
    n_ok = sum(1 for s, _ in results if s == "OK")
    n_fail = sum(1 for s, _ in results if s == "FAIL")
    n_warn = sum(1 for s, _ in results if s == "WARN")
    text = [
        f"RoadLog UI Button Audit — {time.strftime('%Y-%m-%d %H:%M')}",
        f"OK={n_ok} WARN={n_warn} FAIL={n_fail}",
        "",
    ]
    for s, m in results:
        text.append(f"[{s}] {m}")
    OUT.write_text("\n".join(text), encoding="utf-8")
    print(f"\nReport: {OUT}")
    print(f"SUMMARY OK={n_ok} WARN={n_warn} FAIL={n_fail}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
