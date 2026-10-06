import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against a running stack (local Compose plus `pnpm dev:web`, or CI's
// ephemeral stack). Host names come from the environment so the same tests run everywhere.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: { trace: "retain-on-failure" },
  // Every spec, axe checks included, runs on a phone and on a desktop browser (UI_DESIGN_SYSTEM.md
  // section 12). Phone below the sm breakpoint, desktop at a laptop width.
  projects: [
    { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
    { name: "desktop-chrome", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
  ],
});
