import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8765", headless: true },
  webServer: {
    command: "python3 ../tests/workz/server.py",
    url: "http://127.0.0.1:8765",
    reuseExistingServer: false,
  },
});
