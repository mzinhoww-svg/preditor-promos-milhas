import { chromium } from "playwright";
const names = ["calinvalid","folds_missing","folds_str","folds_neg","folds_zero","folds_float","folds_null","folds_ok"];
const b = await chromium.launch({ channel: "chrome" }); const p = await (await b.newContext()).newPage();
for (const n of names.slice(1)) {
  await p.goto(`http://127.0.0.1:${3900 + names.indexOf(n)}/modelo`);
  const t = await p.evaluate(() => document.body.innerText.split("\n").find((l) => /dobras|walk-forward,/.test(l)) || document.body.innerText.match(/walk-forward[^\n]{0,120}/)?.[0] || "(sem trecho)");
  console.log(n, "=>", t.slice(0, 140), "| undefined/NaN:", /undefined|NaN|null/.test(await p.evaluate(() => document.body.innerText)));
}
await b.close();
