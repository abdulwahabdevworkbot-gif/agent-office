// Render every .svg in a folder to a transparent .png of the svg's own width x height.
// usage: NODE_PATH=$(npm root -g) node render.cjs <svg-dir> <png-dir> [scale]
// Uses the Chromium that Playwright already has; no downloads.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
(async () => {
const [src, out, scale = "1"] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: +scale });
for (const f of fs.readdirSync(src).filter(f => f.endsWith(".svg")).sort()) {
  const svg = fs.readFileSync(path.join(src, f), "utf8");
  const w = +(/width="([\d.]+)"/.exec(svg) || [])[1], h = +(/height="([\d.]+)"/.exec(svg) || [])[1];
  await page.setViewportSize({ width: Math.ceil(w), height: Math.ceil(h) });
  await page.setContent(`<!doctype html><html><body style="margin:0;background:transparent">${svg}</body></html>`);
  await page.locator("svg").first().screenshot({ path: path.join(out, f.replace(/\.svg$/, ".png")), omitBackground: true });
}
await browser.close();
})();
