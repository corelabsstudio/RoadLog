# -*- coding: utf-8 -*-
"""Post one RoadLog promo on X via Chrome (persistent profile or CDP)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
USER_DATA = Path.home() / "AppData/Local/Google/Chrome/User Data"
DAY = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
OUT = ROOT / "docs/marketing/x/packs" / DAY
OUT.mkdir(parents=True, exist_ok=True)

CAPTION = (
    "운행일지 엑셀 3종 무료입니다.\n"
    "개인업무 · 법인차 · 월간요약\n\n"
    "https://roadlog.co.kr/resources/\n\n"
    "현장 기록이 잦으면 로드로그 Free\n"
    "https://roadlog.co.kr\n\n"
    "#운행일지 #외근일지 #RoadLog"
)

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
]


def find_chrome() -> Path | None:
    for p in CHROME_CANDIDATES:
        if p.is_file():
            return p
    return None


def kill_chrome() -> None:
    subprocess.run(
        ["taskkill", "/F", "/IM", "chrome.exe"],
        capture_output=True,
        text=True,
    )
    time.sleep(2)


def start_chrome_cdp(chrome: Path, port: int = 9222) -> None:
    subprocess.Popen(
        [
            str(chrome),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={USER_DATA}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "https://x.com/home",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # wait for CDP
    import urllib.request

    for _ in range(30):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Chrome CDP did not start")


def fill_and_post(page, dry: bool) -> str:
    page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=90000)
    time.sleep(3)
    url = page.url
    if "login" in url or "i/flow" in url:
        page.screenshot(path=str(OUT / "x_not_logged_in.png"))
        raise RuntimeError("NOT_LOGGED_IN")

    # dismiss cookie/banner if any
    for label in ("Accept all cookies", "Accept", "확인", "Close"):
        try:
            page.get_by_role("button", name=label).first.click(timeout=1500)
        except Exception:
            pass

    box = page.locator('[data-testid="tweetTextarea_0"]').first
    if box.count() == 0:
        box = page.locator('[role="textbox"][data-testid="tweetTextarea_0"], div[role="textbox"]').first
    box.wait_for(state="visible", timeout=30000)
    box.click()
    time.sleep(0.3)
    # clear then type
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(CAPTION)
    time.sleep(1.5)
    page.screenshot(path=str(OUT / "x_compose_preview.png"))

    if dry:
        return "dry_run"

    post = page.locator('[data-testid="tweetButton"]').first
    if post.count() == 0 or not post.is_visible():
        post = page.locator('[data-testid="tweetButtonInline"]').first
    post.wait_for(state="visible", timeout=15000)
    for _ in range(30):
        try:
            if post.is_enabled():
                break
        except Exception:
            pass
        time.sleep(0.2)
    post.click()
    time.sleep(5)
    page.screenshot(path=str(OUT / "x_after_post.png"))
    return "posted"


def main() -> int:
    dry = "--dry-run" in sys.argv
    no_kill = "--no-kill" in sys.argv
    port = 9222

    chrome = find_chrome()
    if not chrome:
        print("NO_CHROME_EXE")
        return 2
    if not USER_DATA.is_dir():
        print("NO_USER_DATA")
        return 2

    if not no_kill:
        print("Restarting Chrome with CDP…")
        kill_chrome()
        start_chrome_cdp(chrome, port)
        time.sleep(3)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception as e:
            print("CDP_CONNECT_FAIL", e)
            # fallback: persistent context (Chrome must be closed)
            if no_kill:
                return 5
            kill_chrome()
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA),
                channel="chrome",
                headless=False,
                args=["--profile-directory=Default"],
                locale="ko-KR",
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                status = fill_and_post(page, dry)
            except Exception as ex:
                print("ERROR", ex)
                page.screenshot(path=str(OUT / "x_error.png"))
                ctx.close()
                return 1
            meta = {
                "status": status,
                "caption": CAPTION,
                "time": datetime.now().isoformat(timespec="seconds"),
                "mode": "persistent",
            }
            (OUT / "META_chrome_post.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("OK", status)
            # leave browser open: don't close context if user wants it
            return 0

        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            status = fill_and_post(page, dry)
        except Exception as ex:
            print("ERROR", ex)
            try:
                page.screenshot(path=str(OUT / "x_error.png"))
            except Exception:
                pass
            return 1

        meta = {
            "status": status,
            "caption": CAPTION,
            "time": datetime.now().isoformat(timespec="seconds"),
            "mode": "cdp",
            "url": page.url,
        }
        (OUT / "META_chrome_post.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("OK", status, page.url)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
