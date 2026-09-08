import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: true,
  },
  projects: [
    { name: 'chromium-1280', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } } },
    { name: 'chromium-768', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 900 } } },
    { name: 'chromium-360', use: { ...devices['Desktop Chrome'], viewport: { width: 360, height: 780 } } },
    { name: 'webkit-iphone', use: { ...devices['iPhone 13'] } },
  ],
})
