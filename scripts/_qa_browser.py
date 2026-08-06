# -*- coding: utf-8 -*-
"""Browser QA via playwright CLI driver if python package missing.

Uses playwright.exe install path: run node-based script instead.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

JS = r"""
const { chromium, devices } = require('playwright');

(async () => {
  const results = [];
  const browser = await chromium.launch({ headless: true });

  async function checkPage(name, url, opts = {}) {
    const context = await browser.newContext({
      viewport: opts.viewport || { width: 1280, height: 800 },
      locale: 'ko-KR',
      userAgent: opts.ua,
    });
    const page = await context.newPage();
    const consoleErrs = [];
    const pageErrs = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrs.push(msg.text().slice(0, 200));
    });
    page.on('pageerror', err => pageErrs.push(String(err).slice(0, 200)));
    const failed = [];
    page.on('response', res => {
      const st = res.status();
      if (st >= 400 && res.url().includes(opts.host || '')) {
        failed.push(st + ' ' + res.url().slice(0, 120));
      }
    });
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
    } catch (e) {
      results.push({ name, url, ok: false, error: String(e).slice(0, 200) });
      await context.close();
      return;
    }
    await page.waitForTimeout(800);

    const info = await page.evaluate(() => {
      const fab = document.querySelector('.free-fab');
      let fabBox = null;
      let fabClipped = false;
      let fabText = '';
      if (fab) {
        const r = fab.getBoundingClientRect();
        fabBox = { x: r.x, y: r.y, w: r.width, h: r.height, top: r.top, bottom: r.bottom, right: r.right };
        fabText = (fab.innerText || '').replace(/\s+/g, ' ').trim();
        const cs = getComputedStyle(fab);
        fabClipped = cs.overflow === 'hidden' && r.width < fab.scrollWidth - 2;
        // text truncated if strong narrower than content
        const strong = fab.querySelector('strong');
        if (strong) {
          fabClipped = fabClipped || strong.scrollWidth > strong.clientWidth + 2;
        }
      }
      const nav = document.querySelector('header.nav, .nav, nav');
      let navOk = false;
      let navH = 0;
      if (nav) {
        const r = nav.getBoundingClientRect();
        navOk = r.height > 40 && r.height < 200 && r.width > 200;
        navH = r.height;
      }
      const bodyOverflowX = document.documentElement.scrollWidth > window.innerWidth + 2;
      const title = document.title;
      const bodyClass = document.body.className;
      // broken images
      const imgs = [...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src.slice(0,100));
      // visible horizontal overflow elements (sample)
      return {
        title,
        bodyClass,
        fab: !!fab,
        fabBox,
        fabText,
        fabClipped,
        fabDisplay: fab ? getComputedStyle(fab).display : null,
        navOk,
        navH,
        bodyOverflowX,
        brokenImgs: imgs.slice(0, 8),
        lang: document.documentElement.lang,
      };
    });

    results.push({
      name,
      url,
      ok: pageErrs.length === 0,
      info,
      consoleErrs: consoleErrs.slice(0, 8),
      pageErrs: pageErrs.slice(0, 5),
      failedReqs: failed.slice(0, 10),
    });
    await context.close();
  }

  await checkPage('RL desktop', 'https://roadlog.co.kr/?qa=1', { host: 'roadlog.co.kr' });
  await checkPage('RL mobile', 'https://roadlog.co.kr/?qa=1', {
    host: 'roadlog.co.kr',
    viewport: { width: 390, height: 844 },
    ua: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
  });
  await checkPage('RL resources', 'https://roadlog.co.kr/resources/', { host: 'roadlog.co.kr' });
  await checkPage('WA desktop', 'https://wakeagain.com/?qa=1', { host: 'wakeagain.com' });
  await checkPage('WA mobile', 'https://wakeagain.com/?qa=1', {
    host: 'wakeagain.com',
    viewport: { width: 390, height: 844 },
    ua: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
  });
  await checkPage('WA app', 'https://wakeagain.com/app/', { host: 'wakeagain.com' });

  console.log(JSON.stringify(results, null, 2));
  await browser.close();
})().catch(e => {
  console.error(String(e));
  process.exit(1);
});
"""

tmpdir = pathlib.Path(tempfile.mkdtemp())
js_path = tmpdir / "qa_browser.js"
js_path.write_text(JS, encoding="utf-8")

# Prefer project-local playwright or global npx
candidates = [
    ["npx", "--yes", "playwright", "test", "--help"],  # probe only
]
# Run with node + require playwright from npx cache or local
# Install playwright browsers if needed via npx playwright
cmd = f'cd /d "{tmpdir}" && npm init -y >nul 2>&1 && npm install playwright@1.49.0 --no-save --no-package-lock 2>&1 && node "{js_path}"'
print("Installing playwright in temp and running browser QA (may take a bit)...")
# Use subprocess with shell for windows
proc = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     f"Set-Location '{tmpdir}'; npm init -y | Out-Null; npm install playwright@1.49.1 --no-save --no-fund --no-audit 2>&1 | Select-Object -Last 5; node '{js_path}'"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=300,
)
print(proc.stdout[-8000:] if proc.stdout else "")
if proc.stderr:
    print("STDERR:", proc.stderr[-3000:])
print("exit", proc.returncode)
sys.exit(proc.returncode if proc.returncode else 0)
