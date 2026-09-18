import { expect, test } from "@playwright/test";

test("native login, workspace, reload, revocation and password change", async ({ page }) => {
  const password = process.env.MIL_E2E_PASSWORD;
  if (!password) throw new Error("Run through scripts.e2e_native_auth with disposable credentials");
  await page.goto("/watchlists");
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  await page.getByLabel("Login", { exact: true }).fill("acceptance-owner");
  await page.getByLabel("Password", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Sign-in failed");
  await expect(page.getByText("Your session expired. Please sign in again.")).toHaveCount(0);

  async function login(secret: string) {
    await page.getByLabel("Login", { exact: true }).fill("acceptance-owner");
    await page.getByLabel("Password", { exact: true }).fill(secret);
    const result = page.waitForResponse(response => response.url().endsWith("/api/v1/auth/login") && response.status() === 200);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    const token = (await (await result).json()).access_token as string;
    await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
    return token;
  }
  const token = await login(password);
  await page.getByLabel("Workspace", { exact: true }).selectOption({ label: "Second acceptance workspace" });
  await page.getByRole("link", { name: "Watchlists", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Watchlists", exact: true })).toBeVisible();
  const storageSafe = await page.evaluate(async (secret) => {
    const values = JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } });
    const databases = "databases" in indexedDB ? await indexedDB.databases() : [];
    return !values.includes(secret) && sessionStorage.length === 0 && databases.length === 0;
  }, token);
  expect(storageSafe).toBe(true);
  expect((await page.context().cookies()).length).toBe(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  const freshToken = await login(password);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  const rejected = await page.request.get(`${process.env.MIL_E2E_API_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${freshToken}` },
  });
  expect(rejected.status()).toBe(401);
  const expiring = await login(password);
  await page.request.post(`${process.env.MIL_E2E_API_URL}/api/v1/auth/logout`, {
    headers: { Authorization: `Bearer ${expiring}`, Origin: process.env.MIL_E2E_URL! },
  });
  await page.getByRole("link", { name: "Watchlists", exact: true }).click();
  await expect(page.getByText("Your session expired. Please sign in again.")).toBeVisible();
  await login(password);
  // Exercise the SPA password-change route without a document reload.
  await page.evaluate(() => {
    history.pushState(null, "", "/reset-password");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await page.getByLabel("Current password", { exact: true }).fill(password);
  await page.getByLabel("New password", { exact: true }).fill(`${password}-changed`);
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await expect(page.getByText(/Password changed. Sign in again/)).toBeVisible();
  await page.getByRole("link", { name: "Return to sign in" }).click();
  await login(`${password}-changed`);
  await page.goto("/reset-password");
  await expect(page.getByText(/Contact the MIL operator/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Change password" })).toHaveCount(0);
});
