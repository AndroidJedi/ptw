import { mkdir, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'

const require = createRequire(new URL('../apps/commander-web/package.json', import.meta.url))
const { chromium, webkit } = require('@playwright/test')

if (process.argv.length !== 5 || !/^https:\/\/[A-Za-z0-9.-]+$/.test(process.argv[2])) {
  throw new Error('usage: node archive_natal_dashboard_screenshots.mjs HTTPS_ORIGIN SCREENSHOT_DIRECTORY MIRROR_DIRECTORY')
}
const origin = process.argv[2]
const output = resolve(process.argv[3])
const mirror = resolve(process.argv[4])
await mkdir(output, { recursive: true })
await mkdir(mirror, { recursive: true })

async function preserveResponse(response) {
  const url = new URL(response.url())
  if (url.origin !== origin || response.status() !== 200) return
  const decoded = decodeURIComponent(url.pathname)
  if (decoded.includes('..')) throw new Error(`unsafe archive path: ${decoded}`)
  const relative = decoded === '/' ? 'index.html' : decoded.replace(/^\//, '')
  const destination = resolve(mirror, relative.endsWith('/') ? `${relative}index.html` : relative)
  if (!destination.startsWith(`${mirror}/`)) throw new Error(`archive path escaped mirror: ${decoded}`)
  try {
    const body = await response.body()
    await mkdir(resolve(destination, '..'), { recursive: true })
    await writeFile(destination, body)
  } catch {
    // A browser may evict an already cached response body; the first successful
    // capture remains authoritative and all archived files are checksummed.
  }
}

for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
  const browser = await engine.launch({ headless: true })
  try {
    for (const width of [1280, 768, 360]) {
      const page = await browser.newPage({ viewport: { width, height: width === 360 ? 780 : 900 } })
      page.on('response', preserveResponse)
      await page.goto(origin, { waitUntil: 'networkidle', timeout: 30_000 })
      await page.screenshot({ path: `${output}/${engineName}-${width}.png`, fullPage: true })
      await page.close()
    }
  } finally {
    await browser.close()
  }
}
