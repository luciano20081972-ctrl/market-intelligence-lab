import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-native",
  workers: 1,
  timeout: 60_000,
  reporter: "list",
  use: {
    baseURL: process.env.MIL_E2E_URL,
    channel: "chrome",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
});
