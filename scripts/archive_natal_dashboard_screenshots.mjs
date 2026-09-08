import { mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'

const require = createRequire(new URL('../apps/commander-web/package.json', import.meta.url))
const { chromium, webkit } = require('@playwright/test')

if (process.argv.length !== 4 || !/^https:\/\/[A-Za-z0-9.-]+$/.test(process.argv[2])) {
  throw new Error('usage: node archive_natal_dashboard_screenshots.mjs HTTPS_ORIGIN OUTPUT_DIRECTORY')
}
const origin = process.argv[2]
const output = resolve(process.argv[3])
await mkdir(output, { recursive: true })
for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
  const browser = await engine.launch({ headless: true })
  try {
    for (const width of [1280, 768, 360]) {
      const page = await browser.newPage({ viewport: { width, height: width === 360 ? 780 : 900 } })
      await page.goto(origin, { waitUntil: 'networkidle', timeout: 30_000 })
      await page.screenshot({ path: `${output}/${engineName}-${width}.png`, fullPage: true })
      await page.close()
    }
  } finally {
    await browser.close()
  }
}
