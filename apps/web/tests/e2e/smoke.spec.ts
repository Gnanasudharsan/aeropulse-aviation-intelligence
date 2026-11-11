import { expect, test } from "@playwright/test";

const ROUTES: [string, RegExp][] = [
  ["/", /Intelligence/],
  ["/dashboard", /National Aviation Command Center/],
  ["/airports", /50 monitored U\.S\. airports/],
  ["/airports/JFK", /JFK/],
  ["/weather", /Observed weather across the network/],
  ["/events", /Operational events/],
  ["/methodology", /Data sources, freshness and definitions/],
  ["/about", /A real data product/],
];

for (const [path, heading] of ROUTES) {
  test(`${path} renders without console errors`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      // WebGL may be unavailable in headless CI; the map handles that gracefully.
      if (m.type() === "error" && !/WebGL|Failed to load resource/.test(m.text())) errors.push(m.text());
    });
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
    await page.waitForLoadState("networkidle");
    expect(errors, errors.join("\n")).toEqual([]);
  });
}

test("navigation reaches every primary section", async ({ page, isMobile }) => {
  await page.goto("/dashboard");
  for (const label of ["Airports", "Weather", "Events", "Methodology"]) {
    if (isMobile) await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("navigation", { name: isMobile ? "Mobile" : "Primary" }).getByRole("link", { name: label, exact: false }).first().click();
    await expect(page).toHaveURL(new RegExp(`/${label.toLowerCase()}`));
  }
});

test("unknown airport shows a helpful not-monitored state", async ({ page }) => {
  await page.goto("/airports/ZZZ");
  await expect(page.getByText("ZZZ is not a monitored airport")).toBeVisible();
});

test("airport search filters the explorer", async ({ page }) => {
  await page.goto("/airports");
  await page.getByPlaceholder(/Search/).fill("chicago");
  await expect(page.getByText(/Showing 2 of 50 airports/)).toBeVisible();
});
