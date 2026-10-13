import { chromium } from "playwright";
const names = ["calinvalid","folds_missing","folds_str","folds_neg","folds_zero","folds_float","folds_null","folds_ok","weekly_bad","weekly_all_bad","leap","mixed"];
const b = await chromium.launch({ channel: "chrome" }); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const txt = async (port, path, sel) => { const r = await p.goto(`http://127.0.0.1:${port}${path}`); await p.waitForTimeout(300); return [r.status(), await p.evaluate((s) => [...document.querySelectorAll(s)].map((e) => e.innerText.replace(/\s+/g, " ").slice(0, 170)), sel)]; };
const port = (n) => 3900 + names.indexOf(n);
for (const n of ["folds_missing","folds_str","folds_neg","folds_zero","folds_float","folds_null","folds_ok"]) { const [s, t] = await txt(port(n), "/modelo", "main"); const m = t[0].match(/walk-forward[^.]{0,80}|[^.]{0,40}dobras[^.]{0,60}/); console.log(n, s, JSON.stringify(m && m[0]), "undefined?", /undefined|NaN|null/.test(t[0])); }
for (const n of ["weekly_bad","weekly_all_bad"]) { const [s, t] = await txt(port(n), "/modelo", "[role=status], main p.border-dashed"); console.log(n, s, t); const [, rows] = await txt(port(n), "/modelo", "tbody tr"); console.log("   linhas de tabela:", rows.length); }
const [s1, t1] = await txt(port("calinvalid"), "/", "[role=status], article"); console.log("calinvalid /", s1, t1.map((x) => x.slice(0, 110)));
const [s2, t2] = await txt(port("calinvalid"), "/alertas", "h3, [role=status]"); console.log("calinvalid /alertas", s2, t2.slice(0, 4));
const [s3, t3] = await txt(port("leap"), "/", "[role=status], article"); console.log("leap /", s3, t3.map((x) => x.replace(/^.*Última oferta: /, "UO: ").slice(0, 70)));
const [s4, t4] = await txt(port("mixed"), "/modelo", "[role=status]"); console.log("mixed /modelo", s4, t4);
await b.close();
