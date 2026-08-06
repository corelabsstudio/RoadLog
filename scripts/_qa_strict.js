/**
 * Strict dual-app browser QA — fail loudly on real product bugs.
 * node _qa_strict.js
 */
const { chromium } = require("playwright");
const fs = require("fs");

const RL = "https://roadlog.co.kr";
const WA = "https://wakeagain.com";

const VIEWPORTS = [
  { name: "desk", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

function isOwn(url, host) {
  try {
    return new URL(url).host.includes(host);
  } catch {
    return false;
  }
}

async function shot(page, name) {
  // optional: no disk noise by default
}

async function inspectPage(page, opts = {}) {
  return page.evaluate((opts) => {
    const docW = document.documentElement.clientWidth;
    const scrollW = document.documentElement.scrollWidth;
    const offenders = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0)
        continue;
      // skip intentionally offscreen skip-links
      if ((el.className || "").toString().includes("skip-link")) continue;
      if (r.right > docW + 3 || r.left < -3) {
        offenders.push({
          tag: el.tagName,
          id: el.id || "",
          cls: (el.className || "").toString().slice(0, 60),
          left: Math.round(r.left),
          right: Math.round(r.right),
        });
      }
    }
    const seen = new Set();
    const uniq = offenders
      .filter((o) => {
        const k = o.tag + o.cls + o.id;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .slice(0, 12);

    const fab = document.querySelector(".free-fab");
    let fabVis = null;
    if (fab) {
      const r = fab.getBoundingClientRect();
      const cs = getComputedStyle(fab);
      fabVis =
        r.width > 0 &&
        r.height > 0 &&
        cs.display !== "none" &&
        cs.visibility !== "hidden";
    }

    const brokenImgs = [...document.images]
      .filter((i) => i.complete && i.naturalWidth === 0 && (i.src || "").length > 0)
      .map((i) => (i.currentSrc || i.src).slice(0, 100));

    // text overflow sample on nav labels
    const clippedText = [...document.querySelectorAll("a, button, .btn, .free-fab strong")]
      .filter((el) => {
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden") return false;
        if (el.scrollWidth > el.clientWidth + 3 && el.clientWidth > 0) return true;
        return false;
      })
      .slice(0, 8)
      .map((el) => ({
        text: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 40),
        cls: (el.className || "").toString().slice(0, 40),
      }));

    return {
      title: document.title,
      body: document.body.className.slice(0, 100),
      lang: document.documentElement.lang,
      overflowX: scrollW > docW + 2,
      scrollW,
      clientW: docW,
      offenders: uniq,
      fabVis,
      guest: document.body.classList.contains("is-guest-landing"),
      activeView: document.querySelector(".view.active")?.id || null,
      themeYard: document.body.classList.contains("theme-yard"),
      appBody: document.body.classList.contains("app-body"),
      appTop: !!document.querySelector("header.app-top"),
      nav: !!document.querySelector("header.nav, header.app-top, .nav"),
      formLogin: !!document.getElementById("formLogin"),
      build: document.querySelector('meta[name="rl-build"]')?.content || null,
      brokenImgs: brokenImgs.slice(0, 8),
      clippedText,
      hasMojibake:
        document.body.innerText.includes("\ufffd") ||
        /Ã.|Â./.test(document.body.innerText.slice(0, 3000)),
      child0:
        document.body.children[0] &&
        document.body.children[0].tagName +
          "." +
          (document.body.children[0].className || "").toString().slice(0, 40),
    };
  }, opts);
}

async function runCase(browser, label, url, viewport, host) {
  const ctx = await browser.newContext({
    viewport,
    locale: "ko-KR",
    // allow SW — real users have it; but also test with block later if needed
  });
  const page = await ctx.newPage();
  const consoleErrs = [];
  const pageErrs = [];
  const failed = [];

  page.on("console", (m) => {
    if (m.type() === "error") consoleErrs.push(m.text().slice(0, 200));
  });
  page.on("pageerror", (e) => pageErrs.push(String(e).slice(0, 200)));
  page.on("response", (r) => {
    const st = r.status();
    if (st < 400) return;
    const u = r.url();
    if (!isOwn(u, host)) return;
    if (u.includes("favicon") || u.includes("oauth/") || u.includes("demo.mp4")) return;
    failed.push(`${st} ${u.replace(/\?.*$/, "").slice(0, 110)}`);
  });

  const row = { label, url, viewport: `${viewport.width}x${viewport.height}` };
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 55000 });
    // wait for SPA settle
    await page.waitForTimeout(2800);
    row.info = await inspectPage(page);
    row.consoleErrs = [...new Set(consoleErrs)].slice(0, 8);
    row.pageErrs = [...new Set(pageErrs)].slice(0, 6);
    row.failed = [...new Set(failed)].slice(0, 10);
    row.finalUrl = page.url();
  } catch (e) {
    row.error = String(e).slice(0, 250);
  }
  await ctx.close();
  return row;
}

function score(rows) {
  const issues = [];
  for (const r of rows) {
    const where = `${r.label}@${r.viewport}`;
    if (r.error) issues.push({ sev: "fatal", where, msg: r.error });
    if (r.pageErrs?.length) issues.push({ sev: "pageerror", where, msg: r.pageErrs });
    if (r.consoleErrs?.length) issues.push({ sev: "console", where, msg: r.consoleErrs });
    if (r.failed?.length) issues.push({ sev: "network4xx", where, msg: r.failed });
    if (r.info?.overflowX)
      issues.push({
        sev: "overflowX",
        where,
        msg: { scrollW: r.info.scrollW, clientW: r.info.clientW, offenders: r.info.offenders },
      });
    if (r.info?.brokenImgs?.length) issues.push({ sev: "brokenImg", where, msg: r.info.brokenImgs });
    if (r.info?.hasMojibake) issues.push({ sev: "mojibake", where, msg: true });
    if (r.info?.clippedText?.length)
      issues.push({ sev: "clippedText", where, msg: r.info.clippedText });

    // product rules
    if (r.label.startsWith("RL-home") && r.info) {
      if (!r.info.fabVis) issues.push({ sev: "fab-missing-home", where, msg: r.info.fabVis });
      if (!r.info.guest) issues.push({ sev: "guest-missing-home", where, msg: r.info.body });
      if (r.info.build && !String(r.info.build).includes("2026"))
        issues.push({ sev: "build-odd", where, msg: r.info.build });
    }
    if (r.label.startsWith("RL-create") && r.info) {
      if (r.info.activeView !== "view-create")
        issues.push({ sev: "create-not-active", where, msg: r.info.activeView });
      if (r.info.fabVis)
        issues.push({ sev: "fab-visible-on-create", where, msg: true });
      if (r.info.guest)
        issues.push({ sev: "guest-chrome-on-create", where, msg: true });
    }
    if (r.label.startsWith("RL-pricing") && r.info) {
      if (r.info.activeView !== "view-pricing")
        issues.push({ sev: "pricing-not-active", where, msg: r.info.activeView });
      if (r.info.fabVis) issues.push({ sev: "fab-on-pricing", where, msg: true });
    }
    if (r.label.startsWith("WA-app") && r.info) {
      if (!r.info.appBody) issues.push({ sev: "app-body-missing", where, msg: r.info.body });
      if (!r.info.appTop) issues.push({ sev: "app-top-missing", where, msg: r.info.child0 });
      if (!r.info.formLogin) issues.push({ sev: "login-form-missing", where, msg: true });
      if (!r.info.themeYard) issues.push({ sev: "theme-yard-missing", where, msg: r.info.body });
      if (r.info.title && r.info.title.includes("두 번째 기회"))
        issues.push({ sev: "app-title-is-marketing", where, msg: r.info.title });
    }
    if (r.label.startsWith("WA-home") && r.info) {
      if (!r.info.themeYard) issues.push({ sev: "home-no-yard", where, msg: r.info.body });
    }
  }
  return issues;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const rows = [];
  const cases = [];

  for (const vp of VIEWPORTS) {
    cases.push(["RL-home", `${RL}/?qa=strict`, vp, "roadlog"]);
    cases.push(["RL-create", `${RL}/#create`, vp, "roadlog"]);
    cases.push(["RL-pricing", `${RL}/#pricing`, vp, "roadlog"]);
    if (vp.name === "mobile") {
      cases.push(["RL-resources", `${RL}/resources/`, vp, "roadlog"]);
      cases.push(["RL-blog", `${RL}/blog/`, vp, "roadlog"]);
    }
    cases.push(["WA-home", `${WA}/?qa=strict`, vp, "wakeagain"]);
    cases.push(["WA-app", `${WA}/app/`, vp, "wakeagain"]);
    if (vp.name === "mobile") {
      cases.push(["WA-sell", `${WA}/sell.html`, vp, "wakeagain"]);
      cases.push(["WA-guide", `${WA}/guide/`, vp, "wakeagain"]);
      cases.push(["WA-getapp", `${WA}/get-app.html`, vp, "wakeagain"]);
    }
  }

  for (const [label, url, vp, host] of cases) {
    process.stderr.write(`… ${label} ${vp.name}\n`);
    rows.push(await runCase(browser, label, url, vp, host));
  }

  // In-session RL hash after settle (second pass)
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
    });
    const page = await ctx.newPage();
    await page.goto(`${RL}/?qa=session`, { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(2500);
    await page.evaluate(() => {
      location.hash = "create";
    });
    await page.waitForTimeout(1200);
    const info = await inspectPage(page);
    rows.push({
      label: "RL-session-create",
      url: "hash#create",
      viewport: "390x844",
      info,
      consoleErrs: [],
      pageErrs: [],
      failed: [],
    });
    await ctx.close();
  }

  await browser.close();
  const issues = score(rows);
  const out = { rows, issues, issueCount: issues.length };
  const path = process.env.QA_OUT || "qa_strict_results.json";
  fs.writeFileSync(path, JSON.stringify(out, null, 2), "utf8");
  console.log(JSON.stringify({ issueCount: issues.length, issues }, null, 2));
  process.stderr.write(`wrote ${path}\n`);
  process.exit(issues.length ? 2 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
