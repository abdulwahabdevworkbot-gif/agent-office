// Smoke test for the office page (council round 3, E7). Run it against a served demo copy before each push:
//   node office/tools/check/smoke.mjs http://localhost:8811/index.html
// It opens every tab and the main dialogs, and fails on any page error or an empty panel.
// Playwright comes from the PLAYWRIGHT env var (path to its index.mjs) or the "playwright" package.
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
const url = process.argv[2] || "http://localhost:8811/index.html";
const b = await chromium.launch(), p = await b.newPage({viewport:{width:1400, height:900}}), errs = [], fails = [];
p.on("pageerror", e => errs.push(e.message));
p.on("console", m => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push(m.text()); });
await p.goto(url); await p.waitForTimeout(3500);
const check = async (what, sel) => { const n = await p.locator(sel).count(); const txt = n ? (await p.locator(sel).first().innerText()).trim() : ""; if (!txt) fails.push(`${what}: ${sel} is empty`); };
for (const tab of ["office","roadmap","chat","board","calendar","reviews","team","settings"]) {
  await p.click(`#tab-${tab}`); await p.waitForTimeout(400); await check(`tab ${tab}`, `#panel-${tab}`);
}
await p.click("#tab-office"); await p.waitForTimeout(300);
await check("Needs you", "#inboxList");
await p.click("#callMeet4"); await p.waitForTimeout(400); await check("meeting dialog", "#meetBody"); await p.keyboard.press("Escape");
await p.click("#tab-board"); await p.waitForTimeout(300);
const card = p.locator(".card").first(); if (await card.count()) { await card.click(); await p.waitForTimeout(400); await check("task dialog", "#taskBody"); await p.keyboard.press("Escape"); } else fails.push("board: no cards");
await p.click("#tab-calendar"); await p.waitForTimeout(300);
for (const v of ["@rooms"]) { await p.selectOption("#calWho", v); await p.waitForTimeout(300); await check(`calendar ${v}`, "#calBody"); }
await b.close();
if (errs.length || fails.length) { console.error("FAIL\n" + [...errs.map(e => "error: " + e), ...fails].join("\n")); process.exit(1); }
console.log("ok: every tab and dialog opened with no errors");
