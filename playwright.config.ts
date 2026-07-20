import { defineConfig, devices } from '@playwright/test';

/**
 * Workshop Helmsman — e2e gate config (spec/roadmap.md Phase 1, slice S3).
 *
 * The gate starts the app externally (`uv run python -m src`, single origin on
 * :8001 serving /api/* and the static export at /app/*) — therefore NO
 * `webServer` block here. Specs run against that live server.
 *
 * Poll intervals are 2 s (dashboard) / 3 s (tracker); the 12 s expect timeout
 * covers every "within one poll" assertion without fixed sleeps.
 */
export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 90_000,
  expect: { timeout: 12_000 },
  retries: 0,
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001/app',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // No traces/videos: a failure trace would persist the X-Admin-Key request
    // header to disk (secret hygiene). Screenshots + the line reporter suffice.
    trace: 'off',
    video: 'off',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
