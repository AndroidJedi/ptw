// Passive, bounded website inspection. All browser traffic is served through
// pinned public IPv4 TLS connections; the page never receives network access.
import { resolve4 } from 'node:dns/promises'
import https from 'node:https'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright'

export function publicAddress(ip) {
  const p = ip.split('.').map(Number)
  if (p.length !== 4 || p.some(v => !Number.isInteger(v) || v < 0 || v > 255)) return false
  const [a, b, c] = p
  return !(a === 0 || a === 10 || a === 127 || a >= 224 || (a === 100 && b >= 64 && b <= 127)
    || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && (b === 168 || b === 0 || (b === 88 && c === 99)))
    || (a === 198 && (b === 18 || b === 19 || (b === 51 && c === 100)))
    || (a === 203 && b === 0 && c === 113))
}
export function publicUrl(value) {
  const u = new URL(value)
  if (u.protocol !== 'https:' || u.username || u.password || (u.port && u.port !== '443')
    || !u.hostname.includes('.') || u.hostname.includes(':') || u.href.length > 2048) throw new Error('Use a public HTTPS website.')
  return u
}
export async function capture(value) {
  publicUrl(value)
  const started = Date.now(), cache = new Map()
  let requests = 0, bytes = 0
  const errors = []
  async function fetchPublic(value, redirects = 0) {
    const u = publicUrl(value)
    if (redirects > 4 || ++requests > 160 || bytes > 20_000_000 || Date.now() - started > 55_000) throw new Error('Website capture limit reached.')
    const addresses = await resolve4(u.hostname)
    if (!addresses.length || addresses.some(ip => !publicAddress(ip))) throw new Error('Website must resolve to public addresses.')
    const response = await new Promise((resolve, reject) => {
      const req = https.get(u, { lookup: (_host, options, done) => options.all
        ? done(null, [{ address: addresses[0], family: 4 }]) : done(null, addresses[0], 4),
      headers: { 'User-Agent': 'Natal-Reference/1.0', Accept: 'text/html,text/css,image/*,font/*;q=0.8' } }, res => {
        const chunks = []; let size = 0
        res.on('data', chunk => { size += chunk.length; bytes += chunk.length
          if (size > 4_000_000 || bytes > 20_000_000) { res.destroy(); reject(new Error('Website resource too large.')) } else chunks.push(chunk) })
        res.on('error', reject)
        res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }))
      })
      req.setTimeout(7000, () => req.destroy(new Error('Website request timed out.')))
      req.on('error', reject)
    })
    if (response.status >= 300 && response.status < 400 && response.headers.location) return fetchPublic(new URL(response.headers.location, u).href, redirects + 1)
    if (response.status !== 200) throw new Error('Website resource unavailable.')
    const type = String(response.headers['content-type'] || '').split(';')[0]
    if (!/^(text\/(html|css)|image\/(png|jpeg|webp|avif|svg\+xml|gif)|font\/|application\/(font|x-font|vnd\.ms-fontobject))/.test(type)
      && !(type === 'application/octet-stream' && /\.(woff2?|ttf|otf)$/i.test(u.pathname))) throw new Error('Unsupported website resource.')
    return { body: response.body, contentType: type, status: 200 }
  }
  const browser = await chromium.launch({ headless: true, ...(process.env.PTW_TEMPLATE_CHROMIUM ? { executablePath: process.env.PTW_TEMPLATE_CHROMIUM } : {}) })
  try {
    const context = await browser.newContext({ javaScriptEnabled: false, serviceWorkers: 'block', viewport: { width: 1280, height: 1000 } })
    await context.route('**/*', async route => {
      if (!['document', 'stylesheet', 'image', 'font'].includes(route.request().resourceType()) || route.request().method() !== 'GET') return route.abort()
      try { const url = route.request().url(); if (!cache.has(url)) cache.set(url, fetchPublic(url)); await route.fulfill({ ...await cache.get(url), headers: { 'Access-Control-Allow-Origin': '*' } }) }
      catch (error) { if (errors.length < 12) errors.push({ resource: route.request().resourceType(), reason: error.message.slice(0, 100) }); await route.abort() }
    })
    const page = await context.newPage()
    await page.goto(value, { waitUntil: 'domcontentloaded', timeout: 30_000 })
    await page.evaluate(() => {
      document.querySelectorAll('link[rel="stylesheet"][media="print"][onload],link[rel="preload"][as="style"]').forEach(link => {
        link.rel = 'stylesheet'; link.media = 'all'; link.removeAttribute('onload')
      })
    })
    await page.waitForLoadState('networkidle', { timeout: 9000 }).catch(() => {})
    const loadVisible = async () => {
      await page.evaluate(() => {
        [...document.querySelectorAll('img')].filter(img => { const r = img.getBoundingClientRect(); return r.width >= 64 && r.height >= 32 && r.bottom >= 0 && r.top < 2400 }).slice(0, 24).forEach(img => {
          if (img.dataset.src) { img.src = img.dataset.src; img.removeAttribute('data-src'); img.classList.add('loaded') }
          if (img.dataset.srcset) { img.srcset = img.dataset.srcset; img.removeAttribute('data-srcset') }
          img.closest('picture')?.querySelectorAll('source[data-srcset]').forEach(source => { source.srcset = source.dataset.srcset; source.removeAttribute('data-srcset') })
          img.loading = 'eager'
        })
      })
      await page.evaluate(() => Promise.race([Promise.all([document.fonts.ready, ...[...document.images].filter(img => img.loading === 'eager').map(img => img.decode().catch(() => {}))]), new Promise(resolve => setTimeout(resolve, 9000))]))
    }
    await loadVisible()
    const evidence = await page.evaluate(() => ({ title: document.title.slice(0, 160), text: (document.body?.innerText || '').slice(0, 7000),
      colors: [...new Set([...document.querySelectorAll('h1,h2,button,a')].slice(0, 35).map(el => getComputedStyle(el).color))].slice(0, 8),
      photos: [...document.images].filter(img => img.naturalWidth > 400 && img.naturalHeight > 240 && !/logo|brand|icon/i.test(img.alt + img.currentSrc)).slice(0, 3).map(img => ({ url: img.currentSrc, alt: img.alt.slice(0, 120) })) }))
    const desktop = await page.screenshot({ type: 'png' })
    await page.setViewportSize({ width: 360, height: 1100 })
    await loadVisible()
    const mobile = await page.screenshot({ type: 'png' })
    const photos = []
    for (const photo of evidence.photos) {
      try { const item = await (cache.get(photo.url) || fetchPublic(photo.url)); if (/^image\/(png|jpeg|webp|avif)$/.test(item.contentType)) photos.push({ ...photo, mime_type: item.contentType, bytes_base64: item.body.toString('base64') }) } catch { /* Optional art; never substitute a logo. */ }
    }
    return { url: value, title: evidence.title, text: evidence.text, colors: evidence.colors, photos, diagnostics: { requests, bytes, errors },
      images: [desktop, mobile].map(buffer => buffer.toString('base64')) }
  } finally { await browser.close() }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { process.stdout.write(JSON.stringify(await capture(process.argv[2]))) }
  catch { process.stderr.write('Could not inspect the public website. Try a screenshot instead.\n'); process.exitCode = 1 }
}
