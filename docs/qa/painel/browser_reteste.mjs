import { chromium } from "/private/tmp/claude-503/-Users-aurimar-nogueira-latam-com-Documents-theloyal-preditor-promos-milhas--maestri-roles-a5fcfdca-25b6-4a50-83b7-ac3972cd4a63/b4b86703-843e-423c-85d4-5501b4b909b4/scratchpad/pw/node_modules/playwright/index.mjs";
const S = process.argv[2];
const b = await chromium.launch({ channel: "chrome" });
for (const [name, port] of [["xss", 3391], ["nan", 3392], ["real", 3393], ["nondict", 3394]]) {
  for (const [vn, vp] of [["1440", { width: 1440, height: 900 }], ["1920", { width: 1920, height: 1080 }]]) {
    const p = await (await b.newContext({ viewport: vp })).newPage();
    const errs = []; p.on("pageerror", (e) => errs.push(e.message.slice(0, 80)));
    await p.goto(`http://127.0.0.1:${port}/`); await p.waitForTimeout(3500);
    const info = await p.evaluate(() => ({ title: document.title, xss: window.__xss || 0, imgs: document.querySelectorAll("img").length, overall: document.getElementById("overallNum")?.textContent, banner: [...document.querySelectorAll("body div")].filter((d) => d.children.length === 0 && /erro|falha|indispon|invalid|nao foi/i.test(d.textContent || "")).map((d) => d.textContent.slice(0, 90)).slice(0, 2), ovf: document.documentElement.scrollWidth > document.documentElement.clientWidth, items: document.querySelectorAll(".item").length }));
    await p.screenshot({ path: `${S}/painel/r-${name}-${vn}.png` });
    console.log(name, vn, JSON.stringify(info), errs.slice(0, 2));
  }
}
await b.close();
