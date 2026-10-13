import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
const S = process.argv[2];
const scen = { mock: 3400, empty: 3401, extremes: 3402, missing: 3403, badjson: 3404, error500: 3405, baddate: 3407, nociband: 3408, oddnums: 3409, apidown: 3411, nokey: 3410 };
const routes = ["/", "/?type=purchase_discount", "/?type=boosted_accrual", "/modelo", "/fontes", "/alertas", "/nao-existe"];
const vps = { mobile: { width: 390, height: 844 }, desktop: { width: 1440, height: 900 }, zoom200: { width: 195, height: 422 } };
const browser = await chromium.launch({ channel: "chrome" });
const out = [];
for (const [name, port] of Object.entries(scen)) {
  for (const [vn, vp] of Object.entries(vps)) {
    const ctx = await browser.newContext({ viewport: vp }); const page = await ctx.newPage();
    const errs = []; page.on("pageerror", (e) => errs.push("pageerror: " + e.message.slice(0, 120))); page.on("console", (m) => m.type() === "error" && errs.push("console: " + m.text().slice(0, 120)));
    for (const r of routes) {
      if (name !== "mock" && name !== "extremes" && (r.includes("type=") )) continue;
      errs.length = 0;
      let status = "-", t = Date.now();
      try { const resp = await page.goto(`http://127.0.0.1:${port}${r}`, { waitUntil: "load", timeout: 20000 }); status = resp?.status(); } catch (e) { status = "ERR " + e.message.slice(0, 60); }
      const info = await page.evaluate(() => {
        const t = document.body.innerText;
        return { h1: document.querySelector("h1")?.innerText, overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
          bad: ["undefined", "NaN", "Infinity", "[object", "null"].filter((w) => t.includes(w)), badge: [...document.querySelectorAll("header span")].map((s) => s.textContent).find((x) => /exemplo|API/.test(x || "")),
          leak: /SECRET_DETAIL|stack|at .*\(.*:\d+:\d+\)|fake-test-key/.test(document.documentElement.outerHTML) };
      });
      const safe = r.replace(/[^a-z0-9]+/gi, "_");
      await page.screenshot({ path: `${S}/shots2/${name}-${vn}${safe}.png`, fullPage: true });
      out.push({ name, vn, r, status, ms: Date.now() - t, ...info, errs: [...errs] });
    }
    await ctx.close();
  }
}
// axe contraste/acessibilidade, mock e extremes, desktop
for (const [name, port] of [["mock", 3400], ["extremes", 3402]]) {
  const ctx = await browser.newContext({ viewport: vps.desktop }); const page = await ctx.newPage();
  for (const r of ["/", "/modelo", "/fontes", "/alertas"]) {
    await page.goto(`http://127.0.0.1:${port}${r}`);
    const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    out.push({ axe: name + r, violations: res.violations.map((v) => `${v.id}(${v.impact}) x${v.nodes.length}: ${v.nodes[0].target.join(" ")} ${v.nodes[0].failureSummary?.split("\n")[1] ?? ""}`) });
  }
  await ctx.close();
}
await browser.close();
for (const o of out) console.log(JSON.stringify(o));
