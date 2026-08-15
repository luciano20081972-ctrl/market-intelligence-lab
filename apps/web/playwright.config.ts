import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5182", trace: "retain-on-failure" },
  webServer: [
    { command: "python -m scripts.e2e", cwd: "../..", url: "http://127.0.0.1:5182", reuseExistingServer: false, timeout: 120_000 },
  ],
});
