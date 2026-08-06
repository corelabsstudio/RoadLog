const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: "ko-KR",
    serviceWorkers: "block",
  });
  const page = await ctx.newPage();
  const pageErrs = [];
  page.on("pageerror", (e) => pageErrs.push(String(e).slice(0, 140)));
  await page.goto("https://wakeagain.com/app/?qa=final", {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(2000);
  const info = await page.evaluate(() => ({
    title: document.title,
    body: document.body.className,
    appTop: !!document.querySelector("header.app-top"),
    formLogin: !!document.getElementById("formLogin"),
    themeYard: document.body.classList.contains("theme-yard"),
    appBody: document.body.classList.contains("app-body"),
    child0:
      document.body.children[0] &&
      document.body.children[0].tagName +
        "." +
        document.body.children[0].className,
  }));
  console.log(JSON.stringify({ info, pageErrs }, null, 2));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
