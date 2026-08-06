/**
 * Zero-bug loop QA for RoadLog + WakeAgain
 * - multi viewport
 * - cold loads
 * - SPA hash routes
 * - overflow / broken imgs / pageerrors / 4xx
 * - product rules
 */
const { chromium } = require("playwright");
const fs = require("fs");

const RL = "https://roadlog.co.kr";
const WA = "https://wakeagain.com";

const VPS = [
  { name: "desk", width: 1440, height: 900 },
  { name: "laptop", width: 1024, height: 700 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
  { name: "mobile-sm", width: 360, height: 740 },
];

function own(url, host) {
  try {
    return new URL(url).host.includes(host);
  } catch {
    return false;
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
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) continue;
      const cls = (el.className || "").toString();
      if (cls.includes("skip-link")) continue;
      if (r.right > docW + 2 || r.left < -2) {
        offenders.push({
          tag: el.tagName,
          id: el.id || "",
          cls: cls.slice(0, 55),
          left: Math.round(r.left),
          right: Math.round(r.right),
          w: Math.round(r.width),
        });
      }
    }
    const seen = new Set();
    const uniq = offenders
      .filter((o) => {
        const k = o.tag + "|" + o.cls + "|" + o.id;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .slice(0, 15);

    // leaf text nodes that actually clip
    const clippedText = [];
    for (const el of document.querySelectorAll("h1,h2,h3,strong,p,span,a,button,label,small,li")) {
      if (el.children.length > 2) continue; // skip large containers
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      if (cs.whiteSpace === "nowrap" || cs.overflow === "hidden" || cs.textOverflow === "ellipsis") {
        if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 8) {
          clippedText.push({
            tag: el.tagName,
            text: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 50),
            cls: (el.className || "").toString().slice(0, 40),
            sw: el.scrollWidth,
            cw: el.clientWidth,
          });
        }
      }
    }

    const fab = document.querySelector(".free-fab");
    let fabVis = null;
    if (fab) {
      const r = fab.getBoundingClientRect();
      const cs = getComputedStyle(fab);
      fabVis =
        r.width > 0 &&
        r.height > 0 &&
        cs.display !== "none" &&
        cs.visibility !== "hidden" &&
        Number(cs.opacity) > 0;
    }

    const brokenImgs = [...document.images]
      .filter((i) => i.complete && i.naturalWidth === 0 && i.src)
      .map((i) => (i.currentSrc || i.src).slice(0, 100));

    // low-contrast-ish neon leftover in computed colors (sample accent elements)
    const neonSample = [];
    for (const sel of [".btn-primary", "a", "h1", ".brand-name", ".app-tile-icon"]) {
      const el = document.querySelector(sel);
      if (!el) continue;
      const c = getComputedStyle(el).color;
      if (/rgb\(\s*(0|34|94|103),\s*(211|229|232|233),\s*(238|212|217)/.test(c)) {
        neonSample.push(sel + ":" + c);
      }
    }

    // zero-size interactive visible-ish
    const tinyClick = [...document.querySelectorAll("button, a.btn, .btn, [role=button]")]
      .filter((el) => {
        if (el.hidden || el.disabled) return false;
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden") return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (r.width < 10 || r.height < 10);
      })
      .slice(0, 6)
      .map((el) => (el.innerText || el.id || el.className || "").toString().slice(0, 40));

    return {
      title: document.title,
      body: document.body.className.slice(0, 120),
      overflowX: scrollW > docW + 2,
      scrollW,
      clientW: docW,
      offenders: uniq,
      clippedText: clippedText.slice(0, 10),
      fabVis,
      guest: document.body.classList.contains("is-guest-landing"),
      activeView: document.querySelector(".view.active")?.id || null,
      themeYard: document.body.classList.contains("theme-yard"),
      appBody: document.body.classList.contains("app-body"),
      formBody: document.body.classList.contains("form-body"),
      appTop: !!document.querySelector("header.app-top"),
      nav: !!document.querySelector("header.nav, header.app-top, .nav, .nav-pill, .form-nav"),
      formLogin: !!document.getElementById("formLogin"),
      build: document.querySelector('meta[name="rl-build"]')?.content || null,
      brokenImgs: brokenImgs.slice(0, 8),
      neonSample,
      tinyClick,
      hasMojibake:
        document.body.innerText.includes("\ufffd") ||
        /Ã.|Â./.test(document.body.innerText.slice(0, 2500)),
      child0:
        document.body.children[0] &&
        document.body.children[0].tagName +
          "." +
          (document.body.children[0].className || "").toString().slice(0, 40),
      styleBroken: document.documentElement.outerHTML.includes('styles.css?v=') &&
        /styles\.css\?v=[^"\n]+"[a-zA-Z]/.test(document.documentElement.outerHTML),
    };
  });
}

async function run(browser, label, url, vp, host, { blockSW = false, waitMs = 2600 } = {}) {
  const ctx = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    locale: "ko-KR",
    serviceWorkers: blockSW ? "block" : "allow",
  });
  const page = await ctx.newPage();
  const consoleErrs = [];
  const pageErrs = [];
  const failed = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrs.push(m.text().slice(0, 180));
  });
  page.on("pageerror", (e) => pageErrs.push(String(e).slice(0, 180)));
  page.on("response", (r) => {
    if (r.status() < 400) return;
    const u = r.url();
    if (!own(u, host)) return;
    if (u.includes("favicon") || u.includes("oauth/") || u.includes("demo.mp4")) return;
    failed.push(`${r.status()} ${u.replace(/\?.*$/, "").slice(0, 100)}`);
  });

  const row = { label, url, vp: vp.name, w: vp.width };
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(waitMs);
    // light scroll for lazy
    await page.evaluate(() => window.scrollTo(0, Math.min(500, document.body.scrollHeight)));
    await page.waitForTimeout(300);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);
    row.info = await inspect(page);
    row.consoleErrs = [...new Set(consoleErrs)].slice(0, 8);
    row.pageErrs = [...new Set(pageErrs)].slice(0, 6);
    row.failed = [...new Set(failed)].slice(0, 10);
    row.finalUrl = page.url().slice(0, 140);
  } catch (e) {
    row.error = String(e).slice(0, 250);
  }
  await ctx.close();
  return row;
}

function score(rows) {
  const issues = [];
  const add = (sev, where, msg) => issues.push({ sev, where, msg });

  for (const r of rows) {
    const where = `${r.label}@${r.vp}`;
    if (r.error) add("fatal", where, r.error);
    if (r.pageErrs?.length) add("pageerror", where, r.pageErrs);
    if (r.consoleErrs?.length) add("console", where, r.consoleErrs);
    if (r.failed?.length) add("network", where, r.failed);
    if (r.info?.overflowX)
      add("overflowX", where, {
        scrollW: r.info.scrollW,
        clientW: r.info.clientW,
        offenders: r.info.offenders,
      });
    if (r.info?.brokenImgs?.length) add("brokenImg", where, r.info.brokenImgs);
    if (r.info?.hasMojibake) add("mojibake", where, true);
    if (r.info?.clippedText?.length) add("clippedText", where, r.info.clippedText);
    if (r.info?.neonSample?.length) add("neonColor", where, r.info.neonSample);
    if (r.info?.tinyClick?.length) add("tinyClick", where, r.info.tinyClick);
    if (r.info?.styleBroken) add("styleBroken", where, true);

    // product rules
    if (r.label === "RL-home" && r.info) {
      if (!r.info.fabVis) add("rule", where, "free-fab should show on guest home");
      if (!r.info.guest) add("rule", where, "is-guest-landing expected on home");
      if (!r.info.build) add("rule", where, "rl-build meta missing");
    }
    if (r.label === "RL-create" && r.info) {
      if (r.info.activeView !== "view-create") add("rule", where, "expected view-create got " + r.info.activeView);
      if (r.info.fabVis) add("rule", where, "free-fab must hide on create");
      if (r.info.guest) add("rule", where, "guest chrome must off on create");
    }
    if (r.label === "RL-pricing" && r.info) {
      if (r.info.activeView !== "view-pricing") add("rule", where, "expected view-pricing got " + r.info.activeView);
      if (r.info.fabVis) add("rule", where, "free-fab must hide on pricing");
    }
    if (r.label === "WA-app" && r.info) {
      if (!r.info.appBody) add("rule", where, "app-body missing: " + r.info.body);
      if (!r.info.appTop) add("rule", where, "header.app-top missing child0=" + r.info.child0);
      if (!r.info.formLogin) add("rule", where, "formLogin missing");
      if (!r.info.themeYard) add("rule", where, "theme-yard missing");
      if (r.info.title && r.info.title.includes("두 번째 기회"))
        add("rule", where, "app title overwritten by marketing: " + r.info.title);
    }
    if ((r.label === "WA-home" || r.label === "WA-sell" || r.label === "WA-guide") && r.info) {
      if (!r.info.themeYard && !r.info.formBody && !r.info.appBody)
        add("rule", where, "expected theme-yard/form-body: " + r.info.body);
    }
  }
  return issues;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const rows = [];
  const cases = [];

  // Core matrix
  for (const vp of VPS) {
    // full matrix only for home/app; sample secondary pages on mobile+desk
    cases.push(["RL-home", `${RL}/?qa=zero`, vp, "roadlog"]);
    cases.push(["WA-home", `${WA}/?qa=zero`, vp, "wakeagain"]);
    cases.push(["WA-app", `${WA}/app/`, vp, "wakeagain"]);

    if (vp.name === "desk" || vp.name === "mobile") {
      cases.push(["RL-create", `${RL}/#create`, vp, "roadlog"]);
      cases.push(["RL-pricing", `${RL}/#pricing`, vp, "roadlog"]);
      cases.push(["RL-resources", `${RL}/resources/`, vp, "roadlog"]);
      cases.push(["RL-blog", `${RL}/blog/`, vp, "roadlog"]);
      cases.push(["RL-news", `${RL}/blog/news/`, vp, "roadlog"]);
      cases.push(["WA-sell", `${WA}/sell.html`, vp, "wakeagain"]);
      cases.push(["WA-buy", `${WA}/buy.html`, vp, "wakeagain"]);
      cases.push(["WA-guide", `${WA}/guide/`, vp, "wakeagain"]);
      cases.push(["WA-getapp", `${WA}/get-app.html`, vp, "wakeagain"]);
      cases.push(["WA-legal", `${WA}/legal/terms.html`, vp, "wakeagain"]);
    }
    if (vp.name === "mobile") {
      cases.push(["RL-guide-art", `${RL}/blog/corporate-vehicle-log.html`, vp, "roadlog"]);
      cases.push(["WA-how-sell", `${WA}/guide/how-to-sell.html`, vp, "wakeagain"]);
      cases.push(["WA-blog", `${WA}/blog/`, vp, "wakeagain"]);
    }
  }

  for (const [label, url, vp, host] of cases) {
    process.stderr.write(`… ${label} ${vp.name}\n`);
    rows.push(await run(browser, label, url, vp, host));
  }

  // WA app with SW blocked (catches HTML parse issues)
  process.stderr.write("… WA-app nosw mobile\n");
  rows.push(
    await run(browser, "WA-app-nosw", `${WA}/app/?qa=nosw`, VPS.find((v) => v.name === "mobile"), "wakeagain", {
      blockSW: true,
    })
  );

  // session hash after settle
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      locale: "ko-KR",
    });
    const page = await ctx.newPage();
    await page.goto(`${RL}/?qa=sess`, { waitUntil: "domcontentloaded", timeout: 55000 });
    await page.waitForTimeout(2500);
    await page.evaluate(() => {
      location.hash = "create";
    });
    await page.waitForTimeout(1200);
    const info = await inspect(page);
    rows.push({
      label: "RL-session-create",
      url: "#create",
      vp: "mobile",
      w: 390,
      info,
      consoleErrs: [],
      pageErrs: [],
      failed: [],
    });
    await page.evaluate(() => {
      location.hash = "pricing";
    });
    await page.waitForTimeout(800);
    const info2 = await inspect(page);
    rows.push({
      label: "RL-session-pricing",
      url: "#pricing",
      vp: "mobile",
      w: 390,
      info: info2,
      consoleErrs: [],
      pageErrs: [],
      failed: [],
    });
    await ctx.close();
  }

  await browser.close();
  // map session labels to rules
  for (const r of rows) {
    if (r.label === "RL-session-create") r.label = "RL-create";
    if (r.label === "RL-session-pricing") r.label = "RL-pricing";
    if (r.label === "WA-app-nosw") r.label = "WA-app";
  }

  const issues = score(rows);
  const outPath = process.env.QA_OUT || "qa_zero_results.json";
  fs.writeFileSync(outPath, JSON.stringify({ rows, issues, issueCount: issues.length }, null, 2));
  console.log(JSON.stringify({ issueCount: issues.length, issues }, null, 2));
  process.stderr.write(`wrote ${outPath}\n`);
  process.exit(issues.length ? 2 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
