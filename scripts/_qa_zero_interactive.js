/**
 * Interactive / edge-case pass — click nav, open menus, forms present.
 */
const { chromium } = require("playwright");
const fs = require("fs");

const RL = "https://roadlog.co.kr";
const WA = "https://wakeagain.com";

async function safeClick(page, sel) {
  const el = await page.$(sel);
  if (!el) return false;
  const vis = await el.isVisible().catch(() => false);
  if (!vis) return false;
  await el.click({ timeout: 4000 }).catch(() => {});
  return true;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const issues = [];
  const notes = [];

  // --- RoadLog mobile menu + create via click ---
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
    });
    const page = await ctx.newPage();
    const pageErrs = [];
    page.on("pageerror", (e) => pageErrs.push(String(e).slice(0, 120)));
    await page.goto(RL + "/?qa=ix", { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(2800);

    // open mobile menu if toggle exists
    const toggled = await safeClick(page, ".menu-toggle, #menuToggle, button.menu-toggle");
    await page.waitForTimeout(400);
    const menuOpen = await page.evaluate(() => {
      const n = document.querySelector(".nav-links");
      if (!n) return null;
      return {
        open: n.classList.contains("open"),
        h: Math.round(n.getBoundingClientRect().height),
        display: getComputedStyle(n).display,
      };
    });
    notes.push({ step: "RL menu toggle", toggled, menuOpen });

    // click pricing in nav (may need menu open)
    await safeClick(page, 'a[data-nav="pricing"]');
    await page.waitForTimeout(1000);
    let st = await page.evaluate(() => ({
      hash: location.hash,
      active: document.querySelector(".view.active")?.id,
      fab: (() => {
        const f = document.querySelector(".free-fab");
        if (!f) return null;
        const r = f.getBoundingClientRect();
        const cs = getComputedStyle(f);
        return r.width > 0 && cs.display !== "none" && cs.visibility !== "hidden";
      })(),
      guest: document.body.classList.contains("is-guest-landing"),
    }));
    if (st.active !== "view-pricing")
      issues.push({ sev: "rule", where: "RL-click-pricing", msg: st });
    if (st.fab) issues.push({ sev: "rule", where: "RL-click-pricing-fab", msg: st });
    notes.push({ step: "RL click pricing", st });

    // click create
    await safeClick(page, ".menu-toggle, #menuToggle");
    await page.waitForTimeout(200);
    await safeClick(page, 'a[data-nav="create"]');
    await page.waitForTimeout(1000);
    st = await page.evaluate(() => ({
      hash: location.hash,
      active: document.querySelector(".view.active")?.id,
      fab: (() => {
        const f = document.querySelector(".free-fab");
        if (!f) return null;
        const r = f.getBoundingClientRect();
        const cs = getComputedStyle(f);
        return r.width > 0 && cs.display !== "none" && cs.visibility !== "hidden";
      })(),
      guest: document.body.classList.contains("is-guest-landing"),
    }));
    if (st.active !== "view-create")
      issues.push({ sev: "rule", where: "RL-click-create", msg: st });
    if (st.fab) issues.push({ sev: "rule", where: "RL-click-create-fab", msg: st });
    notes.push({ step: "RL click create", st });

    // open auth modal
    await safeClick(page, "#btnAuth, #btnStart, button#btnAuth");
    await page.waitForTimeout(600);
    const auth = await page.evaluate(() => {
      const m = document.querySelector("#authModal, .auth-modal, .modal.show");
      if (!m) return { open: false };
      const cs = getComputedStyle(m);
      return {
        open: m.classList.contains("show") || !m.hidden,
        display: cs.display,
        vis: cs.visibility,
      };
    });
    notes.push({ step: "RL auth", auth });
    // not a hard fail if btn hidden when logged in — guest should open
    if (auth.open === false) {
      // soft: try start button
      await safeClick(page, "#btnStart");
      await page.waitForTimeout(500);
    }

    if (pageErrs.length) issues.push({ sev: "pageerror", where: "RL-ix", msg: pageErrs });
    await ctx.close();
  }

  // --- RoadLog desk free-fab click ---
  {
    const ctx = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      locale: "ko-KR",
    });
    const page = await ctx.newPage();
    await page.goto(RL + "/?qa=fab", { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(2500);
    const fabHref = await page.evaluate(() => {
      const f = document.querySelector(".free-fab");
      return f ? f.getAttribute("href") : null;
    });
    if (fabHref !== "/resources/")
      issues.push({ sev: "rule", where: "RL-fab-href", msg: fabHref });
    const [resp] = await Promise.all([
      page.waitForNavigation({ timeout: 10000 }).catch(() => null),
      page.click(".free-fab").catch(() => null),
    ]);
    await page.waitForTimeout(800);
    const url = page.url();
    if (!url.includes("/resources"))
      issues.push({ sev: "rule", where: "RL-fab-nav", msg: url });
    notes.push({ step: "RL fab click", url, fabHref });
    await ctx.close();
  }

  // --- WA app: top bar links, login form fields ---
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
      serviceWorkers: "block",
    });
    const page = await ctx.newPage();
    const pageErrs = [];
    page.on("pageerror", (e) => pageErrs.push(String(e).slice(0, 120)));
    await page.goto(WA + "/app/?qa=ix", { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(2200);
    const shell = await page.evaluate(() => ({
      appTop: !!document.querySelector("header.app-top"),
      formLogin: !!document.getElementById("formLogin"),
      loginEmail: !!document.getElementById("loginEmail"),
      loginPass: !!document.getElementById("loginPass"),
      body: document.body.className,
      title: document.title,
      panels: document.querySelectorAll(".app-panel, section.app-panel").length,
    }));
    if (!shell.appTop || !shell.formLogin || !shell.loginEmail || !shell.loginPass)
      issues.push({ sev: "rule", where: "WA-app-shell", msg: shell });
    if (shell.title.includes("두 번째"))
      issues.push({ sev: "rule", where: "WA-app-title", msg: shell.title });

    // switch register tab
    await safeClick(page, '.auth-tabs .tab[data-tab="register"], button[data-tab="register"]');
    await page.waitForTimeout(400);
    const reg = await page.evaluate(() => {
      const f = document.getElementById("formRegister");
      if (!f) return { exists: false };
      return { exists: true, hidden: f.hidden, display: getComputedStyle(f).display };
    });
    notes.push({ step: "WA register tab", reg, shell });
    if (pageErrs.length) issues.push({ sev: "pageerror", where: "WA-app-ix", msg: pageErrs });
    await ctx.close();
  }

  // --- WA home CTAs ---
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
    });
    const page = await ctx.newPage();
    await page.goto(WA + "/?qa=ix", { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(2000);
    const ctas = await page.evaluate(() => {
      const links = [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
      return {
        hasApp: links.some((h) => h && h.includes("/app")),
        hasSell: links.some((h) => h && (h.includes("sell") || h.includes("#new"))),
        themeYard: document.body.classList.contains("theme-yard"),
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      };
    });
    if (!ctas.themeYard) issues.push({ sev: "rule", where: "WA-home-theme", msg: ctas });
    if (ctas.overflowX) issues.push({ sev: "overflowX", where: "WA-home-ix", msg: ctas });
    notes.push({ step: "WA home ctas", ctas });
    await ctx.close();
  }

  // --- Guide hub after fix ---
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
    });
    const page = await ctx.newPage();
    await page.goto(WA + "/guide/", { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(1500);
    const hub = await page.evaluate(() => {
      return [...document.querySelectorAll(".gv-hub a")].map((a) => {
        const img = a.querySelector("img");
        const span = a.querySelector(".gv-hub-body span");
        const ir = img ? img.getBoundingClientRect() : null;
        const sr = span ? span.getBoundingClientRect() : null;
        const ar = a.getBoundingClientRect();
        return {
          text: (span && span.innerText) || "",
          spanH: sr ? Math.round(sr.height) : 0,
          spanW: sr ? Math.round(sr.width) : 0,
          imgBottom: ir ? Math.round(ir.bottom) : 0,
          spanTop: sr ? Math.round(sr.top) : 0,
          overlap: ir && sr ? ir.bottom > sr.top + 2 : false,
          aOverflow: a.scrollWidth > a.clientWidth + 4,
        };
      });
    });
    for (const h of hub) {
      if (h.spanH < 8 || h.spanW < 20)
        issues.push({ sev: "rule", where: "WA-guide-span", msg: h });
      if (h.overlap) issues.push({ sev: "rule", where: "WA-guide-overlap", msg: h });
      if (h.aOverflow) issues.push({ sev: "overflow", where: "WA-guide-card", msg: h });
    }
    notes.push({ step: "WA guide hub", hub });
    await ctx.close();
  }

  // --- Resources download link head ---
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();
    await page.goto(RL + "/resources/", { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(1000);
    const links = await page.evaluate(() =>
      [...document.querySelectorAll("a[href*='templates'], a[href*='.xlsx'], a[href*='.docx']")]
        .map((a) => a.getAttribute("href"))
        .slice(0, 12)
    );
    notes.push({ step: "RL resources links", links });
    if (links.length < 3)
      issues.push({ sev: "rule", where: "RL-resources-links", msg: links });
    await ctx.close();
  }

  await browser.close();
  const out = { issues, notes, issueCount: issues.length };
  fs.writeFileSync(
    process.env.QA_OUT || "qa_zero_ix.json",
    JSON.stringify(out, null, 2),
    "utf8"
  );
  console.log(JSON.stringify({ issueCount: issues.length, issues }, null, 2));
  process.exit(issues.length ? 2 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
