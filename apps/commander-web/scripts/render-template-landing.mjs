// Fixed renderer only: stdin is validated fixture data, never code or HTML.
import { chromium } from 'playwright'
import { readFileSync, realpathSync } from 'node:fs'
import { resolve, extname, sep } from 'node:path'
const chunks = []
let size = 0
for await (const chunk of process.stdin) { size += chunk.length; if (size > 24 * 1024 * 1024) throw Error('Fixture too large'); chunks.push(chunk) }
const { fixture, width } = JSON.parse(Buffer.concat(chunks).toString())
if (![360, 1280].includes(width)) throw Error('Unsupported viewport')
const root = realpathSync(process.env.PTW_TEMPLATE_PREVIEW_BUNDLE || new URL('../../../.local/template-preview', import.meta.url).pathname)
const browser = await chromium.launch({ headless: true, ...(process.env.PTW_TEMPLATE_CHROMIUM ? { executablePath: process.env.PTW_TEMPLATE_CHROMIUM } : {}) })
try {
  const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1, locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' })
  await page.addInitScript(value => { window.templateFixture = value }, fixture)
  await page.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (url.origin !== 'https://template.ptw.invalid') return route.abort()
    try {
      const path = realpathSync(resolve(root, '.' + (url.pathname === '/' ? '/index.html' : decodeURIComponent(url.pathname))))
      if (!path.startsWith(root + sep)) return route.abort()
      const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ttf': 'font/ttf' }
      await route.fulfill({ body: readFileSync(path), contentType: types[extname(path)] || 'application/octet-stream' })
    } catch { await route.abort() }
  })
  await page.goto('https://template.ptw.invalid/', { waitUntil: 'networkidle', timeout: 20000 })
  await page.locator('.lp-page').waitFor()
  await page.evaluate(async () => { await document.fonts.ready; for (const image of document.images) image.loading = 'eager'; await Promise.all(Array.from(document.images, image => image.decode())) })
  const geometry = await page.locator('.lp-page').evaluate(element => {
    const root = element.getBoundingClientRect()
    return Array.from(element.querySelectorAll('[data-section]'), node => { const b = node.getBoundingClientRect(); return { role: node.getAttribute('data-section'), box: [(b.x-root.x)/root.width,(b.y-root.y)/root.height,b.width/root.width,b.height/root.height] } })
  })
  const bytes = await page.locator('.lp-page').screenshot({ animations: 'disabled', timeout: 20000 })
  process.stdout.write(JSON.stringify({ png: bytes.toString('base64'), geometry }))
} finally { await browser.close() }
