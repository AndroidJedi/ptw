import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:42731', trace: 'on-first-retry' },
  webServer: { command: 'VITE_E2E=true VITE_LOCAL_APP=true npm run dev -- --host 127.0.0.1 --port 42731', url: 'http://127.0.0.1:42731', reuseExistingServer: false },
  projects: [
    { name: 'mobile-360', use: { ...devices['Pixel 7'], viewport: { width: 360, height: 800 } } },
    { name: 'iphone-webkit', use: { ...devices['iPhone 13'], browserName: 'webkit' } },
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
  ],
})
