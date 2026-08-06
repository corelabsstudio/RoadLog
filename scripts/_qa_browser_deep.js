/**
 * Deep browser QA — multi viewport, multi route, layout/console/network.
 * Run: node _qa_browser_deep.js  (from dir with playwright installed)
 */
const { chromium } = require("playwright");
const fs = require("fs");

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "laptop", width: 1024, height: 700 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
  { name: "mobile-sm", width: 360, height: 740 },
];

const RL_PAGES = [
  { name: "home", url: "https://roadlog.co.kr/?qa=deep" },
  { name: "resources", url: "https://roadlog.co.kr/resources/" },
  { name: "blog", url: "https://roadlog.co.kr/blog/" },
  { name: "news", url: "https://roadlog.co.kr/blog/news/" },
  { name: "guide-article", url: "https://roadlog.co.kr/blog/corporate-vehicle-log.html" },
  { name: "hash-create", url: "https://roadlog.co.kr/#create" },
  { name: "hash-pricing", url: "https://roadlog.co.kr/#pricing" },
];

const WA_PAGES = [
  { name: "home", url: "https://wakeagain.com/?qa=deep" },
  { name: "app", url: "https://wakeagain.com/app/" },
  { name: "sell", url: "https://wakeagain.com/sell.html" },
  { name: "buy", url: "https://wakeagain.com/buy.html" },
  { name: "guide", url: "https://wakeagain.com/guide/" },
  { name: "blog", url: "https://wakeagain.com/blog/" },
  { name: "legal-terms", url: "https://wakeagain.com/legal/terms.html" },
  { name: "get-app", url: "https://wakeagain.com/get-app.html" },
];

function hostOf(url) {
  try {
    return new URL(url).host;
  } catch {
    return "";
  }
}

async function inspect(page) {
  return page.evaluate(() => {
    const docW = document.documentElement.clientWidth;
    const scrollW = document.documentElement.scrollWidth;
    const offenders = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      if (r.right > docW + 2 || r.left < -2) {
        const cs = getComputedStyle(el);
        // skip offscreen intentionally hidden
        if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") continue;
        offenders.push({
          tag: el.tagName,
          id: el.id || "",
          cls: (el.className || "").toString().slice(0, 70),
          left: Math.round(r.left),
          right: Math.round(r.right),
          w: Math.round(r.width),
          pos: cs.position,
        });
      }
    }
    const seen = new Set();
    const uniq = offenders.filter((o) => {
      const k = o.tag + "|" + o.cls + "|" + o.id;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    }).slice(0, 20);

    let fab = null;
    const fabEl = document.querySelector(".free-fab");
    if (fabEl) {
      const r = fabEl.getBoundingClientRect();
      const cs = getComputedStyle(fabEl);
      const strong = fabEl.querySelector("strong");
      fab = {
        text: (fabEl.innerText || "").replace(/\s+/g, " ").trim(),
        visible:
          r.width > 0 &&
          r.height > 0 &&
          cs.display !== "none" &&
          cs.visibility !== "hidden" &&
          cs.opacity !== "0",
        clipped: strong ? strong.scrollWidth > strong.clientWidth + 2 : false,
        box: {
          x: Math.round(r.x),
          y: Math.round(r.y),
          w: Math.round(r.width),
          h: Math.round(r.height),
        },
        z: cs.zIndex,
      };
    }

    const nav =
      document.querySelector("header.nav, header.app-top, .nav, nav[class]") ||
      document.querySelector("header");
    let navInfo = null;
    if (nav) {
      const r = nav.getBoundingClientRect();
      const cs = getComputedStyle(nav);
      navInfo = {
        tag: nav.tagName,
        cls: (nav.className || "").toString().slice(0, 60),
        h: Math.round(r.height),
        w: Math.round(r.width),
        ok: r.height >= 40 && r.height <= 240 && r.width > 100,
        overflow: cs.overflow,
      };
    }

    const brokenImgs = [...document.images]
      .filter((i) => i.complete && i.naturalWidth === 0 && i.src)
      .map((i) => (i.currentSrc || i.src).slice(0, 100));

    // low contrast-ish? skip — hard without canvas
    // text nodes with replacement char
    const hasMojibake =
      document.body.innerText.includes("\ufffd") ||
      document.body.innerText.includes("Ã") ||
      /[ìíîï][\x80-\xff]/.test(document.body.innerText.slice(0, 2000));

    // zero-size interactive?
    const badBtns = [...document.querySelectorAll("button, a.btn, .btn")]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden") return false;
        if (el.disabled || el.getAttribute("aria-hidden") === "true") return false;
        // hidden attribute
        if (el.hidden) return false;
        return r.width > 0 && r.height > 0 && (r.width < 8 || r.height < 8);
      })
      .slice(0, 8)
      .map((el) => ({
        tag: el.tagName,
        text: (el.innerText || "").slice(0, 40),
        cls: (el.className || "").toString().slice(0, 40),
      }));

    // fixed elements stacking at bottom
    const fixedBottom = [...document.querySelectorAll("body *")]
      .filter((el) => {
        const cs = getComputedStyle(el);
        if (cs.position !== "fixed") return false;
        const r = el.getBoundingClientRect();
        return r.height > 20 && r.bottom > window.innerHeight - 120 && r.width > 40;
      })
      .map((el) => ({
        cls: (el.className || "").toString().slice(0, 50),
        id: el.id,
        bottom: Math.round(el.getBoundingClientRect().bottom),
        h: Math.round(el.getBoundingClientRect().height),
      }))
      .slice(0, 10);

    return {
      title: document.title,
      bodyClass: document.body.className.slice(0, 100),
      lang: document.documentElement.lang,
      scrollW,
      clientW: docW,
      overflowX: scrollW > docW + 2,
      offenders: uniq,
      fab,
      nav: navInfo,
      brokenImgs: brokenImgs.slice(0, 8),
      hasMojibake,
      badBtns,
      fixedBottom,
      build: document.querySelector('meta[name="rl-build"]')?.content || null,
      themeYard: document.body.classList.contains("theme-yard"),
    };
  });
}

async function runPage(browser, label, pageSpec, viewport) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    locale: "ko-KR",
    userAgent:
      viewport.width <= 500
        ? "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        : undefined,
  });
  const page = await context.newPage();
  const consoleErrs = [];
  const pageErrs = [];
  const failed = [];
  const host = hostOf(pageSpec.url);

  page.on("console", (m) => {
    if (m.type() === "error") consoleErrs.push(m.text().slice(0, 200));
  });
  page.on("pageerror", (e) => pageErrs.push(String(e).slice(0, 200)));
  page.on("response", (r) => {
    const st = r.status();
    if (st >= 400 && hostOf(r.url()).includes(host.split(".").slice(-2).join("."))) {
      // ignore common noise
      const u = r.url();
      if (u.includes("favicon") || u.includes("demo.mp4")) return;
      failed.push(`${st} ${u.replace(/\?.*$/, "").slice(0, 110)}`);
    }
  });

  const row = {
    label,
    page: pageSpec.name,
    viewport: viewport.name,
    url: pageSpec.url,
  };

  try {
    await page.goto(pageSpec.url, { waitUntil: "domcontentloaded", timeout: 50000 });
    await page.waitForTimeout(1200);
    // light scroll to trigger lazy
    await page.evaluate(() => window.scrollTo(0, Math.min(600, document.body.scrollHeight)));
    await page.waitForTimeout(400);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);

    row.info = await inspect(page);
    row.consoleErrs = [...new Set(consoleErrs)].slice(0, 8);
    row.pageErrs = [...new Set(pageErrs)].slice(0, 5);
    row.failed = [...new Set(failed)].slice(0, 10);

    // click menu toggle on mobile if present (RL)
    if (viewport.width <= 900) {
      const toggle = await page.$(".menu-toggle, #menuToggle, button.menu-toggle, .nav-toggle");
      if (toggle) {
        await toggle.click().catch(() => {});
        await page.waitForTimeout(400);
        row.menuOpen = await page.evaluate(() => {
          const links = document.querySelector(".nav-links, .mobile-nav, .nav-drawer");
          if (!links) return null;
          const r = links.getBoundingClientRect();
          const cs = getComputedStyle(links);
          return {
            openClass: links.className,
            h: Math.round(r.height),
            visible: cs.display !== "none" && r.height > 20,
          };
        });
      }
    }
  } catch (e) {
    row.error = String(e).slice(0, 250);
  }

  await context.close();
  return row;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];

  // Priority matrix: all pages × mobile + desktop; sample tablet for home only
  const matrix = [];
  for (const p of RL_PAGES) {
    for (const vp of VIEWPORTS) {
      if (vp.name === "tablet" || vp.name === "laptop" || vp.name === "mobile-sm") {
        if (p.name !== "home" && p.name !== "hash-create") continue;
      }
      matrix.push(["RL", p, vp]);
    }
  }
  for (const p of WA_PAGES) {
    for (const vp of VIEWPORTS) {
      if (vp.name === "tablet" || vp.name === "laptop" || vp.name === "mobile-sm") {
        if (p.name !== "home" && p.name !== "app") continue;
      }
      matrix.push(["WA", p, vp]);
    }
  }

  for (const [label, p, vp] of matrix) {
    process.stderr.write(`… ${label} ${p.name} @ ${vp.name}\n`);
    results.push(await runPage(browser, label, p, vp));
  }

  // Hash route interaction: create view free-fab should hide after session
  {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
    });
    const page = await context.newPage();
    await page.goto("https://roadlog.co.kr/#create", {
      waitUntil: "domcontentloaded",
      timeout: 50000,
    });
    await page.waitForTimeout(2000);
    const fabState = await page.evaluate(() => {
      const fab = document.querySelector(".free-fab");
      const body = document.body.className;
      if (!fab) return { body, fab: null };
      const cs = getComputedStyle(fab);
      const r = fab.getBoundingClientRect();
      return {
        body,
        fab: {
          display: cs.display,
          visibility: cs.visibility,
          visible: r.width > 0 && r.height > 0 && cs.display !== "none",
        },
        guest: document.body.classList.contains("is-guest-landing"),
      };
    });
    results.push({
      label: "RL",
      page: "create-fab-state",
      viewport: "mobile",
      info: fabState,
      special: true,
    });
    await context.close();
  }

  await browser.close();

  // Score
  const issues = [];
  for (const r of results) {
    if (r.error) issues.push({ sev: "error", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.error });
    if (r.pageErrs?.length)
      issues.push({ sev: "pageerror", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.pageErrs });
    if (r.consoleErrs?.length)
      issues.push({ sev: "console", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.consoleErrs });
    if (r.failed?.length)
      issues.push({ sev: "network", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.failed });
    if (r.info?.overflowX)
      issues.push({
        sev: "overflow",
        where: `${r.label}/${r.page}@${r.viewport}`,
        msg: { scrollW: r.info.scrollW, clientW: r.info.clientW, offenders: r.info.offenders },
      });
    if (r.info?.brokenImgs?.length)
      issues.push({ sev: "img", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.info.brokenImgs });
    if (r.info?.hasMojibake)
      issues.push({ sev: "mojibake", where: `${r.label}/${r.page}@${r.viewport}`, msg: true });
    if (r.info?.fab?.clipped)
      issues.push({ sev: "fab-clip", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.info.fab });
    if (r.info?.nav && r.info.nav.ok === false)
      issues.push({ sev: "nav", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.info.nav });
    if (r.info?.badBtns?.length)
      issues.push({ sev: "tiny-btn", where: `${r.label}/${r.page}@${r.viewport}`, msg: r.info.badBtns });
  }

  const out = { results, issues, issueCount: issues.length };
  const outPath = process.env.QA_OUT || "qa_deep_results.json";
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2), "utf8");
  console.log(JSON.stringify({ issueCount: issues.length, issues }, null, 2));
  console.error("wrote", outPath, "issues", issues.length);
  process.exit(issues.length ? 2 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
