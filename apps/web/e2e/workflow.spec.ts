import { expect, test } from "@playwright/test";

test("authenticated workspace research workflow has no severe console errors", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => { if (message.type() === "error") severe.push(message.text()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Market overview" })).toBeVisible();
  await page.getByLabel("Workspace", { exact: true }).selectOption({
    label: "Legacy Development Workspace",
  });
  await expect(page.getByText(/Simulation only · owner/)).toBeVisible();
  await page.getByRole("link", { name: "Providers" }).click();
  await expect(page.getByRole("heading", { name: "Providers" })).toBeVisible();
  await expect(page.getByText("Deterministic Synthetic Demonstration Provider")).toBeVisible();
  await expect(page.getByText("Stooq Historical Daily Data")).toBeVisible();
  await expect(page.getByText("Twelve Data Historical Daily Data")).toBeVisible();
  await page.getByRole("link", { name: "Stooq Historical Daily Data" }).click();
  await expect(page.getByRole("heading", { name: "Stooq Historical Daily Data" })).toBeVisible();
  await expect(page.getByText("No API key required")).toBeVisible();
  await page.route("**/api/v1/providers/*/test", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      status: "degraded",
      connectivity: "reachable_invalid",
      response_classification: "html_access_page",
      schema_compatible: false,
      message: "Stooq returned an HTML verification or access page instead of market data",
    }),
  }));
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByText("html_access_page")).toBeVisible();
  await expect(page.getByText(/HTML verification or access page/)).toBeVisible();
  await page.getByRole("link", { name: "Import Jobs" }).click();
  await expect(page.getByRole("heading", { name: "Historical imports" })).toBeVisible();
  await page.getByLabel("Symbols").fill("AAPL,SPY");
  await page.getByRole("button", { name: "Preview import" }).click();
  await expect(page.getByText("Preview passed")).toBeVisible();
  await page.getByRole("button", { name: "Queue import" }).click();
  await expect(page.getByText(/queued successfully/)).toBeVisible();
  await page.getByRole("link", { name: "synthetic" }).first().click();
  await expect.poll(async () => {
    await page.reload();
    return page.getByRole("heading", { level: 1 }).textContent();
  }, { timeout: 20_000 }).toContain("succeeded");
  await expect(page.getByRole("heading", { name: "Provenance" })).toBeVisible();
  await page.getByRole("link", { name: "Strategy Lab" }).click();
  await page.getByLabel("Symbols").fill("AAPL");
  await page.getByLabel("Backtest data source").selectOption("imported");
  await page.getByLabel("Start date").fill("2026-07-06");
  await page.getByLabel("End date").fill("2026-08-14");
  await page.getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByText(/Hypothetical results · imported data/)).toBeVisible();
  await expect(page.getByText("imported", { exact: true }).first()).toBeVisible();
  await page.getByRole("link", { name: "Reproducibility manifest" }).click();
  await expect(page.getByRole("heading", { name: "Reproducibility manifest" })).toBeVisible();
  await page.goBack();
  await page.getByRole("link", { name: "Validation report" }).click();
  await expect(page.getByRole("heading", { name: "Bias and leakage validation" })).toBeVisible();
  await page.getByRole("link", { name: "Queue & Workers" }).click();
  await expect(page.getByRole("heading", { name: "Queue dashboard" })).toBeVisible();
  await page.getByRole("link", { name: "Schedules" }).click();
  await expect(page.getByRole("heading", { name: "Import schedules" })).toBeVisible();
  await page.getByRole("link", { name: "Reconciliation" }).click();
  await expect(page.getByRole("heading", { name: "Reconciliation" })).toBeVisible();
  await page.getByRole("link", { name: "Data Quality" }).click();
  await expect(page.getByRole("heading", { name: "Data quality" })).toBeVisible();
  await page.getByRole("link", { name: "Asset Explorer" }).click();
  await expect(page.getByRole("link", { name: "AAPL" })).toBeVisible();
  await page.getByRole("link", { name: "Watchlists" }).click();
  const watchlistName = `E2E Research ${Date.now()}`;
  await page.getByLabel("New watchlist name").fill(watchlistName);
  await page.getByRole("button", { name: "Create watchlist" }).click();
  const watchlist = page.locator("article.watchlist").filter({ has: page.getByRole("heading", { name: watchlistName }) });
  await watchlist.getByLabel(`Add asset to ${watchlistName}`).fill("AAPL");
  await watchlist.getByRole("button", { name: "Add" }).click();
  await watchlist.getByRole("link", { name: /AAPL/ }).click();
  await expect(page.getByRole("heading", { name: "AAPL" })).toBeVisible();
  await page.getByRole("link", { name: "Paper Portfolios" }).click();
  const portfolioName = `E2E Paper ${Date.now()}`;
  await page.getByLabel("Portfolio name").fill(portfolioName);
  await page.getByRole("button", { name: "Create portfolio" }).click();
  await page.getByRole("link", { name: new RegExp(portfolioName) }).click();
  await page.getByRole("link", { name: "Simulate order" }).click();
  await page.getByRole("button", { name: "Preview risk checks" }).click();
  await expect(page.getByText("All enabled portfolio risk checks passed.")).toBeVisible();
  await page.getByRole("button", { name: "Submit simulated order" }).click();
  await expect(page.getByText("Simulation recorded")).toBeVisible();
  const workspaceName = `E2E Workspace B ${Date.now()}`;
  const workspaceResponse = await page.request.post("http://127.0.0.1:8000/api/v1/workspaces", {
    data: { name: workspaceName, slug: `e2e-workspace-b-${Date.now()}` },
  });
  expect(workspaceResponse.ok()).toBeTruthy();
  await page.reload();
  await page.getByLabel("Workspace", { exact: true }).selectOption({ label: workspaceName });
  await page.getByRole("link", { name: "Watchlists" }).click();
  await expect(page.getByText(watchlistName)).not.toBeVisible();
  await page.getByLabel("New watchlist name").fill("Workspace B Private Watchlist");
  await page.getByRole("button", { name: "Create watchlist" }).click();
  await expect(page.getByText("Workspace B Private Watchlist")).toBeVisible();
  await page.getByLabel("Workspace", { exact: true }).selectOption({ label: "Legacy Development Workspace" });
  await expect(page.getByText("Workspace B Private Watchlist")).not.toBeVisible();
  await page.getByRole("link", { name: "Providers" }).click();
  await page.getByRole("link", { name: "Twelve Data Historical Daily Data" }).click();
  await expect(page.getByText(/fixture-tested, not live-verified/i)).toBeVisible();
  await page.getByRole("link", { name: "Infrastructure" }).click();
  await expect(page.getByRole("heading", { name: "Infrastructure services" })).toBeVisible();
  await page.getByRole("link", { name: "SEC Intelligence" }).click();
  await expect(page.getByRole("heading", { name: "SEC intelligence" })).toBeVisible();
  await page.getByRole("button", { name: "Load deterministic fixture filings" }).click();
  await expect(page.getByText(/Fixture filings loaded/)).toBeVisible();
  await page.getByRole("link", { name: "0000320193-26-000001" }).click();
  await expect(page.getByRole("heading", { name: "Filing detail" })).toBeVisible();
  await page.getByRole("link", { name: "SEC Intelligence" }).click();
  await page.getByRole("link", { name: "Insider transactions" }).click();
  await expect(page.getByRole("heading", { name: "Insider transactions" })).toBeVisible();
  await page.getByRole("link", { name: "Analytics Comparison" }).click();
  await page.getByRole("button", { name: "Run analytics comparison" }).click();
  await expect(page.getByText("Daily return-series methodology").first()).toBeVisible();
  await page.getByRole("link", { name: "Optimization" }).click();
  await page.getByRole("button", { name: "Run deterministic optimization" }).click();
  await expect(page.getByText(/No shorting/)).toBeVisible();
  await page.getByRole("link", { name: "Upstream Integrations" }).click();
  await expect(page.getByRole("heading", { name: "Upstream integrations status" })).toBeVisible();
  await expect(page.getByText(/optional dependency unavailable/).first()).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect(severe).toEqual([]);
});
