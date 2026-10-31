import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e-real",
  workers: 1,
  use: { headless: true },
});
