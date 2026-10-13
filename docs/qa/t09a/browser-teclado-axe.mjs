import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
const b = await chromium.launch({ channel: "chrome" });
// 1) elemento que causa overflow em extremes
let ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); let p = await ctx.newPage();
await p.goto("http://127.0.0.1:3202/");
const wide = await p.evaluate(() => [...document.querySelectorAll("body *")].filter((e) => e.getBoundingClientRect().right > innerWidth + 1).slice(0, 6).map((e) => `${e.tagName}.${(e.className || "").toString().slice(0, 60)} right=${Math.round(e.getBoundingClientRect().right)} text="${e.textContent.slice(0, 40)}"`));
console.log("OVERFLOW elementos:", wide);
// 2) teclado no mock (desktop): sequencia de foco, indicador visivel, skip link
ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); p = await ctx.newPage();
await p.goto("http://127.0.0.1:3200/");
const seq = [];
for (let i = 0; i < 14; i++) {
  await p.keyboard.press("Tab");
  seq.push(await p.evaluate(() => { const e = document.activeElement; const cs = getComputedStyle(e); return `${e.tagName}:${(e.innerText || e.getAttribute("aria-label") || "").slice(0, 28).replace(/\n/g, " ")} outline=${cs.outlineStyle}/${cs.outlineWidth} shadow=${cs.boxShadow !== "none"}`; }));
}
console.log("TAB:\n" + seq.join("\n"));
// skip link
await p.goto("http://127.0.0.1:3200/"); await p.keyboard.press("Tab"); console.log("skip link visivel:", await p.evaluate(() => { const r = document.activeElement.getBoundingClientRect(); return `${document.activeElement.textContent} w=${r.width} h=${r.height}`; }));
await p.keyboard.press("Enter"); console.log("apos Enter hash:", await p.evaluate(() => location.hash + " foco=" + document.activeElement.id));
// details por teclado
await p.goto("http://127.0.0.1:3200/");
const sum = p.locator("summary").first(); await sum.focus(); await p.keyboard.press("Enter");
console.log("details abre por Enter:", await p.evaluate(() => document.querySelector("details").open));
// filtros por teclado
await p.goto("http://127.0.0.1:3200/"); const chip = p.getByRole("link", { name: "Compra com desconto" }); await chip.focus(); await p.keyboard.press("Enter"); await p.waitForURL(/type=purchase_discount/); console.log("filtro por teclado ok:", p.url());
// 3) axe mobile mock + extremes
for (const [n, port] of [["mock", 3200], ["extremes", 3202]]) {
  ctx = await b.newContext({ viewport: { width: 390, height: 844 } }); p = await ctx.newPage();
  for (const r of ["/", "/modelo", "/fontes", "/alertas"]) {
    await p.goto(`http://127.0.0.1:${port}${r}`);
    const res = await new AxeBuilder({ page: p }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    console.log("AXE mobile", n + r, res.violations.map((v) => `${v.id}(${v.impact}) x${v.nodes.length}`).join("; ") || "sem violacoes");
  }
}
// 4) zoom 200% / texto grande no mobile mock
ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 }); p = await ctx.newPage();
await p.goto("http://127.0.0.1:3200/"); await p.addStyleTag({ content: "html{font-size:200% !important}" });
console.log("texto 200% overflowX:", await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth));
// 5) prefers-reduced-motion / forced colors nao testados
await b.close();
