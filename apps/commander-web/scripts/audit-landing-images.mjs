// Local-only visual evidence. Requires fixtures from verify_landing_image_quality.py
// and a fresh build:template-preview. Never writes a Project or publication.
import { chromium, webkit, devices } from 'playwright'
import { readFileSync, writeFileSync, mkdirSync, cpSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'node:http'
const root = resolve(process.argv[2] || '../../../.local/landing-image-quality-final')
const bundle = resolve(new URL('../../../.local/template-preview', import.meta.url).pathname)
const fixture = JSON.parse(readFileSync(resolve(root, 'after.json')))
const original = JSON.parse(readFileSync(resolve(root, 'original.json')))
const site = resolve(root, 'site'); mkdirSync(site, { recursive: true }); cpSync(bundle, site, { recursive: true })
const shell = readFileSync(resolve(bundle, 'index.html'), 'utf8')
for (const [name, value] of Object.entries({ showcase: fixture, original })) {
  writeFileSync(resolve(site, `${name}.json`), JSON.stringify(value))
  writeFileSync(resolve(site, `${name}.html`), shell.replace('<head>', `<head><script src="/${name}.js"></script>`))
  writeFileSync(resolve(site, `${name}.js`), 'window.templateFixture=' + JSON.stringify(value).replaceAll('<', '\\u003c'))
}
const server = createServer((request, response) => {
  try {
    const path = resolve(site, '.' + new URL(request.url, 'http://local').pathname)
    if (!path.startsWith(site + '/')) throw Error('Outside audit site')
    const type = path.endsWith('.html') ? 'text/html' : path.endsWith('.js') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : path.endsWith('.png') ? 'image/png' : path.endsWith('.svg') ? 'image/svg+xml' : path.endsWith('.jpg') ? 'image/jpeg' : path.endsWith('.ttf') ? 'font/ttf' : 'application/octet-stream'
    response.setHeader('Content-Type', type); response.end(readFileSync(path))
  } catch { response.writeHead(404); response.end() }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const origin = `http://127.0.0.1:${server.address().port}`
const report = []; const errors = []
try {
  for (const [engine, options] of [[chromium, null], [webkit, devices['iPhone 13']]]) {
    const browser = await engine.launch()
    try {
      for (const width of options ? [390] : [1440, 1280, 768, 360]) {
        const label = options ? 'iphone-webkit' : `${width}`
        const page = await browser.newPage({ ...(options || {}), viewport: { width, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' })
        page.on('pageerror', error => errors.push(`${label}: ${error.message}`))
        for (const template of ['showcase', 'original']) {
          await page.goto(`${origin}/${template}.html`, { waitUntil: 'networkidle' })
          await page.locator('.lp-page').waitFor()
          await page.evaluate(async () => { await document.fonts.ready; for (const i of document.images) i.loading = 'eager'; await Promise.all(Array.from(document.images, i => i.decode())) })
          const dir = `${template}-${label}`; mkdirSync(resolve(site, dir), { recursive: true })
          await page.screenshot({ path: resolve(site, dir, 'full.png'), fullPage: true })
          const metrics = await page.evaluate(() => {
            const rect = el => { const b=el.getBoundingClientRect(); return { x:b.x,y:b.y,width:b.width,height:b.height } }
            const root = document.querySelector('.lp-page')
            return { viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth, fontsLoaded: document.fonts.status,
              imagesLoaded: [...document.images].every(i => i.complete && i.naturalWidth > 0),
              sections: [...root.querySelectorAll('[data-section]')].map(el => ({ name:el.dataset.section, ...rect(el) })),
              screens: [...root.querySelectorAll('.as-screen > img')].map(el => ({ fit:getComputedStyle(el).objectFit, ...rect(el), naturalWidth:el.naturalWidth, naturalHeight:el.naturalHeight })),
              phones: [...root.querySelectorAll('.as-step .as-phone')].map(rect),
              buttons: [...root.querySelectorAll('.mk-store')].map(rect),
              heroColumns: root.querySelector('.as-hero') ? getComputedStyle(root.querySelector('.as-hero')).gridTemplateColumns.split(' ').length : null,
            }
          })
          if (metrics.scrollWidth > width || !metrics.imagesLoaded) errors.push(`${dir}: overflow or missing images`)
          if (template==='showcase' && metrics.heroColumns !== (width<=900 ? 1 : 2)) errors.push(`${dir}: hero columns`)
          if (metrics.screens.some(i => i.fit!=='contain' || Math.abs(i.width/i.height - 9/19.5)>.01)) errors.push(`${dir}: distorted screen aperture`)
          if (width>600 && metrics.phones.length && Math.max(...metrics.phones.map(p=>p.y))-Math.min(...metrics.phones.map(p=>p.y))>1) errors.push(`${dir}: misaligned phones`)
          const sections = page.locator('.lp-page [data-section]')
          for (let i=0;i<await sections.count();i++) {
            const node = sections.nth(i); const name = await node.getAttribute('data-section')
            await node.screenshot({ path: resolve(site, dir, `${name}.png`), animations: 'disabled' })
          }
          report.push({ template, label, directory:dir, ...metrics })
          console.log(`${dir}: ${metrics.sections.length} sections; loaded images; scroll ${metrics.scrollWidth}/${width}`)
        }
        await page.close()
      }
    } finally { await browser.close() }
  }
  writeFileSync(resolve(root,'visual-audit.json'),JSON.stringify({ report, errors },null,2))
  const rows=report.map(r=>`<section><h2>${r.template} · ${r.label}</h2><a href="/${r.directory}/full.png">Full page</a><div class="grid">${r.sections.filter(s=>s.name!=='app_feature').map(s=>`<figure><a href="/${r.directory}/${s.name}.png"><img loading="lazy" src="/${r.directory}/${s.name}.png"></a><figcaption>${s.name}</figcaption></figure>`).join('')}</div></section>`).join('')
  writeFileSync(resolve(site,'index.html'),`<!doctype html><meta charset="utf-8"><title>Landing image quality review</title><style>body{font:16px system-ui;max-width:1440px;margin:32px auto;padding:0 20px;background:#edf2f7;color:#17263c}a{color:#174eb0}nav{display:flex;flex-wrap:wrap;gap:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:20px;align-items:start}figure{margin:0;background:white;padding:12px}img{display:block;width:100%;height:auto}h2{margin-top:48px}</style><h1>Landing image quality review</h1><p>Local preview using real generated assets. No approval, deployment or publication.</p><nav><a href="/showcase.html">Corrected hotel · App Showcase</a><a href="/original.html">Project Landing</a><a href="/before-hero.png">Published hero · before</a><a href="/before-walkthrough.png">Published walkthrough · before</a><a href="/showcase-1280/hero.png">Corrected hero · after</a><a href="/showcase-1280/walkthrough.png">Corrected walkthrough · after</a></nav>${rows}`)
  if (errors.length) throw Error(errors.join('\n'))
} finally { server.close() }
