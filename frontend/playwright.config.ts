import { defineConfig, devices } from '@playwright/test';

// Base URL of the running frontend. Override with PLAYWRIGHT_BASE_URL env var
// when pointing at staging.
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
// Backend API URL — used by the global setup to register the test user.
export const API_URL = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global.setup.ts',
  // SSE responses can take 10+ seconds on a cold backend; keep tests patient.
  timeout: 90_000,
  expect: {
    timeout: 30_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
