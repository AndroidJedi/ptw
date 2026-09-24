// Offline audit of exports from scripts/audit_template_quality.py.
import { chromium, webkit, devices } from 'playwright'
import { readFileSync, writeFileSync, mkdirSync, cpSync } from 'node:fs'
import { resolve, extname, sep } from 'node:path'
import { createServer } from 'node:http'

const root = resolve(process.argv[2] || '../../../.local/template-quality/final')
const catalog = JSON.parse(readFileSync(resolve(root, 'catalog.json')))
const bundle = resolve(new URL('../../../.local/template-preview', import.meta.url).pathname)
const site = resolve(root, 'site'); mkdirSync(site, { recursive: true }); cpSync(bundle, site, { recursive: true })
cpSync(resolve(root, 'posts'), resolve(site, 'posts'), { recursive: true })
const shell = readFileSync(resolve(bundle, 'index.html'), 'utf8')
for (const item of catalog.pages) {
  const fixture = JSON.parse(readFileSync(resolve(root, item.file)))
  writeFileSync(resolve(site, `${item.name}.html`), shell.replace('<head>', `<head><script src="/${item.name}.js"></script>`))
  writeFileSync(resolve(site, `${item.name}.js`), 'window.templateFixture=' + JSON.stringify(fixture).replaceAll('<', '\\u003c'))
}
const server = createServer((request, response) => {
  try {
    const path = resolve(site, '.' + new URL(request.url, 'http://local').pathname)
    if (!path.startsWith(site + sep)) throw Error('Outside site')
    const types = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.png':'image/png', '.svg':'image/svg+xml', '.jpg':'image/jpeg', '.ttf':'font/ttf' }
    response.setHeader('Content-Type', types[extname(path)] || 'application/octet-stream'); response.end(readFileSync(path))
  } catch { response.writeHead(404); response.end() }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const origin = `http://127.0.0.1:${server.address().port}`
const results = [], errors = []
try {
  for (const [engine, options] of [[chromium, null], [webkit, devices['iPhone 13']]]) {
    const browser = await engine.launch()
    try {
      for (const width of options ? [390] : [1440, 1280, 768, 360]) {
        const label = options ? 'iphone-webkit' : String(width)
        const page = await browser.newPage({ ...(options || {}), viewport: { width, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' })
        page.on('pageerror', error => errors.push(`${label}: ${error.message}`))
        for (const fixture of catalog.pages) {
          await page.goto(`${origin}/${fixture.name}.html`, { waitUntil: 'networkidle' })
          await page.locator('.lp-page').waitFor()
          await page.evaluate(async () => {
            await document.fonts.ready
            for (const image of document.images) image.loading = 'eager'
            await Promise.all([...document.images].map(image => image.decode()))
            for (const details of document.querySelectorAll('details')) details.open = true
          })
          const directory = `${fixture.name}-${label}`; mkdirSync(resolve(site, directory), { recursive: true })
          await page.screenshot({ path: resolve(site, directory, 'full.png'), fullPage: true })
          const metrics = await page.evaluate(() => {
            const rect = node => { const b=node.getBoundingClientRect(); return { x:b.x, y:b.y, width:b.width, height:b.height } }
            const root = document.querySelector('.lp-page')
            return { scrollWidth: document.documentElement.scrollWidth, imagesLoaded:[...document.images].every(i=>i.complete && i.naturalWidth>0),
              sections:[...root.querySelectorAll('[data-section]')].map(node=>({ name:node.dataset.section, ...rect(node) })),
              phones:[...root.querySelectorAll('.as-step .as-phone')].map(rect),
              heroColumns:getComputedStyle(root.querySelector('.as-hero,.lp-hero')).gridTemplateColumns.split(' ').length,
              screenFits:[...root.querySelectorAll('.as-screen > img')].map(i=>getComputedStyle(i).objectFit),
              // Font ink can extend beyond its line box when overflow is visible.
              // That is not clipping; only reject content hidden by its box.
              clippedText:[...root.querySelectorAll('h1,h2,h3,p,a,summary')].filter(node=> {
                const css=getComputedStyle(node)
                return node.clientWidth>0 && ((['hidden','clip'].includes(css.overflowX) && node.scrollWidth>node.clientWidth+2)
                  || (['hidden','clip'].includes(css.overflowY) && node.scrollHeight>node.clientHeight+3))
              })
                .map(node=>({ tag:node.tagName, className:node.className, text:node.textContent.slice(0,100), ...rect(node) })),
            }
          })
          if (metrics.scrollWidth > width || !metrics.imagesLoaded) errors.push(`${directory}: horizontal overflow/missing image`)
          if (metrics.screenFits.some(fit=>fit!=='contain')) errors.push(`${directory}: stretched app screen`)
          if (metrics.heroColumns !== (width<=900 ? 1 : 2)) errors.push(`${directory}: cramped hero columns`)
          if (width>600 && metrics.phones.length && Math.max(...metrics.phones.map(p=>p.y))-Math.min(...metrics.phones.map(p=>p.y))>1) errors.push(`${directory}: phone alignment`)
          if (metrics.clippedText.length) errors.push(`${directory}: clipped text ${JSON.stringify(metrics.clippedText)}`)
          const reachable = await page.evaluate(() => [...document.querySelectorAll('.lp-phone-scroll')].every(scroll => {
            scroll.scrollTop=scroll.scrollHeight
            const last=scroll.querySelector('.lp-phone-row:last-child')
            const visible=!last || last.getBoundingClientRect().bottom <= scroll.getBoundingClientRect().bottom+1
            scroll.scrollTop=0
            return visible
          }))
          if (!reachable) errors.push(`${directory}: last app control cannot be reached`)
          const sections = page.locator('.lp-page [data-section]')
          for (let i=0;i<await sections.count();i++) {
            const node=sections.nth(i), name=await node.getAttribute('data-section')
            await node.screenshot({ path:resolve(site,directory,`${name}-${i}.png`), animations:'disabled' })
          }
          results.push({ name:fixture.name, label, directory, ...metrics })
          console.log(`${directory}: ${metrics.sections.length} sections; ${metrics.clippedText.length} clipped text nodes`)
        }
        await page.close()
      }
    } finally { await browser.close() }
  }
  const escape = s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;')
  const pages=catalog.pages.map(p=>`<a href="/${p.name}.html">${escape(p.name)}</a>`).join('')
  const posts=catalog.renders.map(r=>`<figure><a href="/${r.file}"><img loading="lazy" src="/${r.file}"></a><figcaption>${escape(r.identity.template_id)} v${r.identity.template_version} · ${escape(r.sample)}${r.small_secondary_text.length ? ' · small text flagged for revision' : ''}</figcaption></figure>`).join('')
  const sections=results.map(r=>`<details><summary>${escape(r.name)} · ${r.label}</summary><a href="/${r.directory}/full.png">Full page</a><div class="grid">${r.sections.map((s,i)=>`<figure><a href="/${r.directory}/${s.name}-${i}.png"><img loading="lazy" src="/${r.directory}/${s.name}-${i}.png"></a><figcaption>${escape(s.name)}</figcaption></figure>`).join('')}</div></details>`).join('')
  writeFileSync(resolve(site,'index.html'),`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Template quality review</title><style>body{font:16px system-ui;max-width:1440px;margin:32px auto;padding:0 20px;background:#edf2f7;color:#17263c}a{color:#174eb0}nav{display:flex;flex-wrap:wrap;gap:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px;align-items:start}figure{margin:0;background:white;padding:12px;min-width:0}img{display:block;width:100%;height:auto}figcaption{overflow-wrap:anywhere;font-size:13px;margin-top:12px}summary{cursor:pointer;padding:16px 0}h2{margin-top:40px}</style><h1>All templates · local quality review</h1><p>Neutral gallery demonstrations and real project-copy checks. No approvals, publications or deployments changed.</p><nav>${pages}</nav><h2>Native Post layouts</h2><div class="grid">${posts}</div><h2>Every Landing section</h2>${sections}`)
  writeFileSync(resolve(root,'browser-audit.json'),JSON.stringify({ results, errors },null,2))
  if(errors.length) throw Error(errors.join('\n'))
} finally { server.close() }
