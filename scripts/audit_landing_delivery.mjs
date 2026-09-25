#!/usr/bin/env node
import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
const require = createRequire(resolve('apps/landing-web/package.json'))
const { chromium, webkit, devices } = require('@playwright/test')
const root = resolve(process.argv[2] || '.local/landing-performance-review')
const origin = process.argv[3] || 'http://127.0.0.1:42810'
const results = []
for (const [name, engine, options] of [
  ['desktop', chromium, { viewport: { width: 1440, height: 1000 } }],
  ['tablet', chromium, { viewport: { width: 768, height: 1024 } }],
  ['mobile-360', chromium, { viewport: { width: 360, height: 800 } }],
  ['iphone-webkit', webkit, devices['iPhone 13']],
]) {
  const browser = await engine.launch()
  for (const version of ['before', 'after']) {
    const context = await browser.newContext(options)
    const page = await context.newPage()
    await page.addInitScript(() => {
      window.layoutShift = 0
      if (PerformanceObserver.supportedEntryTypes?.includes('layout-shift')) new PerformanceObserver(list => {
        for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.layoutShift += entry.value
      }).observe({ type: 'layout-shift', buffered: true })
    })
    const directory = resolve(root, `${version}-${name}`)
    await mkdir(directory, { recursive: true })
    await page.goto(`${origin}/${version}.html`)
    await page.locator('[data-section="hero"]').waitFor()
    await page.evaluate(() => document.fonts.ready)
    const sections = await page.locator('[data-section]').evaluateAll(items => [...new Set(items.map(item => item.dataset.section))])
    for (const section of sections) {
      const element = page.locator(`[data-section="${section}"]`).first()
      await element.scrollIntoViewIfNeeded()
      await element.evaluate(async node => { await Promise.all([...node.querySelectorAll('img')].map(image => image.decode())) })
      await element.screenshot({ path: resolve(directory, `${section}.png`) })
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: resolve(directory, 'full.png'), fullPage: true })
    const evidence = await page.evaluate(() => ({
      viewport: window.innerWidth, width: document.documentElement.scrollWidth, cls: window.layoutShift,
      images: [...document.querySelectorAll('.lp-delivery-image')].map(image => ({ src: image.currentSrc, loading: image.loading, priority: image.fetchPriority, complete: image.complete && image.naturalWidth > 0 })),
      resources: performance.getEntriesByType('resource').filter(entry => /\.(png|webp)$/.test(entry.name)).map(entry => ({ url: entry.name, bytes: entry.encodedBodySize, duration: entry.duration })),
    }))
    if (evidence.width > evidence.viewport || evidence.images.some(image => !image.complete)) throw Error(`Invalid layout/image at ${version}-${name}`)
    if (version === 'after' && evidence.images.some(image => !image.src.endsWith('.webp'))) throw Error('Optimized image was not selected')
    results.push({ name, version, sections: sections.length, ...evidence })
    await context.close()
  }
  await browser.close()
}
await writeFile(resolve(root, 'browser-audit.json'), JSON.stringify(results, null, 2))
console.log(JSON.stringify(results.map(({ name, version, cls, sections }) => ({ name, version, cls, sections }))))
