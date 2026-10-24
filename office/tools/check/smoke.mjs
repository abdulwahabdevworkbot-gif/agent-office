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
/* phone pass (council round 4, E10): no sideways page scroll at 400 px, nothing fixed covering the chat's Send button, no task over 150 ms once loaded */
const ph = await b.newPage({viewport:{width:400, height:860}, isMobile:true, hasTouch:true});
ph.on("pageerror", e => errs.push("phone: " + e.message));
await ph.addInitScript(() => { window.__lt = []; try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(Math.round(e.duration)))).observe({type:"longtask"}); } catch {} });
await ph.goto(url); await ph.waitForTimeout(3500);
await ph.evaluate(() => { window.__lt = []; });   // the first load may take longer; the limit is for using the page
for (const tab of ["office","chat","board","calendar","settings"]) {
  await ph.evaluate(t => document.getElementById("tab-" + t).click(), tab); await ph.waitForTimeout(400);
  const w = await ph.evaluate(() => document.documentElement.scrollWidth); if (w > 401) fails.push(`phone ${tab}: page is ${w} px wide`);
}
/* the calendar's wide views scroll inside their own box (council round 19): Rooms day lanes and one person's hours */
await ph.evaluate(() => document.getElementById("tab-calendar").click()); await ph.waitForTimeout(300);
await ph.evaluate(() => [...document.querySelectorAll("#panel-calendar button")].find(b => b.textContent.trim() === "Rooms")?.click()); await ph.waitForTimeout(400);
let cw = await ph.evaluate(() => document.documentElement.scrollWidth); if (cw > 401) fails.push(`phone calendar rooms: page is ${cw} px wide`);
await ph.evaluate(() => { const s = document.getElementById("calWho"), o = [...s.options].find(o => o.value && o.value !== "rooms"); if (o) { s.value = o.value; s.onchange({target:s}); } }); await ph.waitForTimeout(400);
cw = await ph.evaluate(() => document.documentElement.scrollWidth); if (cw > 401) fails.push(`phone calendar person: page is ${cw} px wide`);
await ph.evaluate(() => document.getElementById("tab-board").click()); await ph.evaluate(() => document.getElementById("tab-chat").click()); await ph.waitForTimeout(400);
const covered = await ph.evaluate(() => { const s = document.getElementById("send"); if (!s) return ""; s.scrollIntoView({block:"center"}); const r = s.getBoundingClientRect(), top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return top && !s.contains(top) ? (top.id || top.className || top.tagName) : ""; });
if (covered) fails.push(`phone chat: the Send button is covered by ${covered}`);
const slow = (await ph.evaluate(() => window.__lt || [])).filter(d => d > 150); if (slow.length) fails.push(`phone: tasks over 150 ms: ${slow.join(", ")}`);
await b.close();
if (errs.length || fails.length) { console.error("FAIL\n" + [...errs.map(e => "error: " + e), ...fails].join("\n")); process.exit(1); }
console.log("ok: every tab and dialog opened with no errors, and the phone pass is clean");
