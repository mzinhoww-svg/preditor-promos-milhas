import { chromium } from "playwright";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const axeSrc = require("fs").readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const b = await chromium.launch({ channel: "chrome" });
const out = {};
for (const [vname, vp] of [["desktop", { width: 1440, height: 900 }], ["mobile", { width: 390, height: 844 }]]) {
  const ctx = await b.newContext({ viewport: vp }); const p = await ctx.newPage();
  const errors = []; p.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 120))); p.on("pageerror", (e) => errors.push("pageerror " + String(e).slice(0, 120)));
  for (const path of ["/", "/modelo", "/fontes", "/alertas"]) {
    await p.goto("http://127.0.0.1:3201" + path, { waitUntil: "networkidle" });
    await p.addScriptTag({ content: axeSrc });
    const res = await p.evaluate(async () => { const r = await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] } }); return r.violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length })); });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    out[`${vname} ${path}`] = { axe: res, overflowX: overflow };
  }
  // explicacao por item
  await p.goto("http://127.0.0.1:3201/", { waitUntil: "networkidle" });
  const sums = p.locator("summary");
  const n = await sums.count(); let expl = null;
  if (n) {
    await sums.first().focus(); await p.keyboard.press("Enter"); await p.waitForTimeout(1500);
    expl = await p.evaluate(() => { const d = document.querySelector("details[open]"); return d ? d.innerText.replace(/\s+/g, " ").slice(0, 400) : null; });
  }
  out[`${vname} explicacao`] = { summaries: n, texto: expl, console: errors.slice(0, 3) };
  await ctx.close();
}
console.log(JSON.stringify(out, null, 1));
await b.close();
