// Capture README screenshots from the REAL running application (no mock data).
// Usage: BASE_URL=http://localhost:3000 node scripts/screenshots.mjs
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = fileURLToPath(new URL("../../../docs/screenshots/", import.meta.url));
const PAGES = [
  ["landing", "/", 900],
  ["command-center", "/dashboard", 1500],
  ["airport-detail", "/airports/SFO", 1400],
  ["weather", "/weather", 1300],
  ["analytics", "/analytics", 1700],
  ["risk", "/risk", 1300],
  ["events", "/events", 900],
  ["methodology", "/methodology", 1100],
];

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: "dark" });
for (const [name, path, height] of PAGES) {
  const page = await ctx.newPage();
  await page.setViewportSize({ width: 1440, height });
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(6000); // map tiles/geojson + chart animations
  await page.screenshot({ path: `${OUT}${name}.png` });
  console.log("captured", name);
  await page.close();
}
const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, colorScheme: "dark" });
const m = await mobile.newPage();
await m.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
await m.waitForTimeout(5000);
await m.screenshot({ path: `${OUT}mobile-dashboard.png` });
console.log("captured mobile-dashboard");
await browser.close();
