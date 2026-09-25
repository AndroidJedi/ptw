import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const digest = 'a'.repeat(64)

test('requests responsive hero WebP with stable geometry and falls back to the original', async ({ page }) => {
  const webp = readFileSync(new URL('../../../validation_pipeline/studio_assets/landing-display-v1/iphone-15-pro-black.webp', import.meta.url))
  const png = readFileSync(new URL('../../../validation_pipeline/studio_assets/iphone-15-pro-black.png', import.meta.url))
  let failWebp = false
  await page.route('**/api/v1/public/landings/delivery-test**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('.webp')) return failWebp ? route.fulfill({ status: 404 }) : route.fulfill({ contentType: 'image/webp', body: webp })
    if (path.endsWith('.png')) return route.fulfill({ contentType: 'image/png', body: png })
    const base = '/api/v1/public/landings/delivery-test'
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configuration: { ...configuration, visual_mode: 'image' }, content, project_name: 'Delivery fixture', canonical_url: 'https://natal-service.com/delivery-test', version_sha256: digest,
      assets: { hero_visual: `${base}/original.png`, visual_break_visual: `${base}/support.png` },
      asset_variants: { hero_visual: [480, 960].map(width => ({ url: `${base}/${width}.webp`, width, height: width*2, sha256: digest, mime_type: 'image/webp', byte_count: webp.length })) } }) })
  })
  await page.goto('/delivery-test')
  const hero = page.locator('.lp-hero-art > img')
  await expect(hero).toHaveAttribute('data-image-state', 'ready')
  expect(await hero.evaluate(image => (image as HTMLImageElement).currentSrc)).toMatch(/\.webp$/)
  await expect(hero).toHaveAttribute('loading', 'eager')
  await expect(hero).toHaveAttribute('fetchpriority', 'high')
  await expect(page.locator('.lp-visual img')).toHaveAttribute('loading', 'lazy')
  const before = await hero.boundingBox()
  failWebp = true
  await page.reload()
  await expect(hero).toHaveAttribute('data-image-state', 'ready')
  expect(await hero.evaluate(image => (image as HTMLImageElement).currentSrc)).toMatch(/original\.png$/)
  expect(await hero.boundingBox()).toEqual(before)
})
const configuration = {
  schema: 'ptw.landing.configuration.v1',
  presentation: { language: 'en', cta_target: 'email', heading_scale: 1, spacing: 'comfortable', hero_focus: { x: 50, y: 50 }, visual_break_focus: { x: 50, y: 50 } },
  theme: { background_color: '#ffffff', surface_color: '#eeeeee', text_color: '#111111', accent_color: '#222222', font_family: 'Inter', heading_font_family: 'Inter', corner_radius: 16 },
  hero: { alignment: 'left', image_position: 'right' }, features: { layout: 'three_columns' }, social_proof: { layout: 'cards' }, visual_break: { height: 'medium' }, contacts: { alignment: 'left' }, faq: { style: 'divided' },
}
const content = {
  schema: 'ptw.landing.content.v1', hero: { title: 'A published Natal product', supporting_text: 'One bounded public snapshot.', cta_label: 'Email Natal', visual_direction: '' },
  features: [{ title: 'One', description: 'First' }, { title: 'Two', description: 'Second' }, { title: 'Three', description: 'Third' }],
  social_proof: { heading: '', items: [] }, visual_break: { visual_direction: '' },
  contacts: { heading: 'Contact', supporting_text: 'Talk to Natal.', email: 'hello@example.com', phone: '', url: '' },
  faq: [{ question: 'What is this?', answer: 'A public immutable Landing version.' }],
}

test.beforeEach(async ({ page }) => {
  await page.route('https://commander.proove-them-wrong.com/api/v1/public/landings/**', async route => {
    const url = new URL(route.request().url())
    const match = /^\/api\/v1\/public\/landings\/([a-z0-9-]+)$/.exec(url.pathname)
    if (!match) return route.fulfill({ status: 404, body: '{}' })
    const [, slug] = match
    await route.fulfill({
      status: 200, contentType: 'application/json',
      headers: { 'Cache-Control': 'no-store' },
      body: JSON.stringify({
        canonical_url: `https://natal-service.com/${slug}`,
        project_name: 'Published Project', configuration, content,
        assets: {
          hero_visual: `/api/v1/public/landings/${slug}/versions/${digest}/assets/hero_visual/${digest}.png`,
          visual_break_visual: `/api/v1/public/landings/${slug}/versions/${digest}/assets/visual_break_visual/${digest}.png`,
        },
        version_sha256: digest, published_at: '2026-09-08T00:00:00Z',
      }),
    })
  })
})

test('renders the umbrella with shared legal links', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Natal' })).toBeVisible()
  await expect(page.getByText('Digital products and services by Natal.')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Policies' }).getByRole('link')).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Allow all' })).toBeVisible()
})

test('does not contact Meta before consent and loads the Pixel after consent', async ({ page }) => {
  let metaRequests = 0
  await page.route(/https:\/\/(connect\.facebook\.net|www\.facebook\.com)\/.*/, async route => {
    metaRequests += 1
    await route.fulfill({ status: 204, body: '' })
  })
  await page.goto('/')
  expect(metaRequests).toBe(0)
  await page.getByRole('button', { name: 'Allow all' }).click()
  await expect.poll(() => metaRequests).toBeGreaterThan(0)
})

test('renders the exact shared Landing composition responsively', async ({ page }) => {
  await page.goto('/published-project')
  await expect(page.getByLabel('Landing live preview')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'A published Natal product' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Email Natal/ }).first()).toHaveAttribute('href', 'mailto:hello@example.com')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
})

test('supports a direct SPA deep link and rejects retired prefixed paths', async ({ page }) => {
  await page.goto('/published-project')
  await expect(page.getByRole('heading', { name: 'A published Natal product' })).toBeVisible()
  await page.goto('/legacy/published-project')
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
})

test('uses the branded visual 404 while the SPA response remains successful', async ({ page }) => {
  const response = await page.goto('/unknown/path')
  expect(response?.status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  await expect(page.getByText('This Natal page is unavailable.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Go to Natal' })).toHaveAttribute('href', '/')
})

test('publishes the App Showcase screens through the shared renderer and preserves CTA analytics', async ({ page }) => {
  const events: Array<{ event_type: string; target: string }> = []
  await page.route('**/api/v1/public/landing-analytics/events', async route => {
    events.push(route.request().postDataJSON())
    await route.fulfill({ status: 202, json: {} })
  })
  await page.route('**/api/v1/public/landings/showcase', route => route.fulfill({ json: {
    canonical_url: 'https://natal-service.com/showcase', project_name: 'Showcase', version_sha256: digest,
    published_at: '2026-09-23T00:00:00Z',
    template_reference: { template_id: 'app_showcase', template_version: 1, template_sha256: 'b'.repeat(64) },
    configuration: { ...configuration, showcase: { gradient_end: '#08cbb5', screen_scale: 1, screen_offset: 32 } },
    content: { ...content, app_screens: [1, 2, 3].map(i => ({ title: `Task ${i}`, description: 'A project-specific app screen.', visual_direction: 'A static app screenshot' })) },
    assets: Object.fromEntries(['app_screen_1', 'app_screen_2', 'app_screen_3', 'visual_break_visual'].map(slot => [slot, `/api/v1/public/landings/showcase/versions/${digest}/assets/${slot}/${digest}.png`])),
  } }))
  await page.goto('/showcase')
  await expect(page.locator('.as-phone')).toHaveCount(5)
  await expect(page.locator('.as-screen > img').first()).toHaveAttribute('src', new RegExp(`/versions/${digest}/assets/app_screen_1/${digest}.png$`))
  await expect(page.locator('.as-cta').first()).toHaveAttribute('href', 'mailto:hello@example.com')
  await page.getByRole('checkbox', { name: /Natal analytics/ }).check()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await page.locator('.as-cta').first().click()
  await expect.poll(() => events.some(event => event.event_type === 'primary_cta_click' && event.target === 'email')).toBe(true)
  await expect(page.locator('.as-edit')).toHaveCount(0)
  await expect(page.locator('.lp-phone-row')).toHaveCount(0)
  expect(await page.locator('.as-page').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
})

test('public marketing sections use exact mockup bytes, store links and sample review layouts', async ({ page }) => {
  const { default: defaults } = await import('../../commander-web/src/landing/marketing-defaults.json', { with: { type: 'json' } })
  const marketing = structuredClone(defaults.content)
  marketing.apple_url = 'https://apps.apple.com/app/id123456'
  marketing.store_label = 'Explore Natal'
  marketing.walkthrough_heading = 'A complete app workflow'
  marketing.walkthrough_steps.forEach((item, i) => { item.title = `Step ${i+1}`; item.description = 'An illustrative task' })
  await page.route('**/api/v1/public/landings/marketing', route => route.fulfill({ json: {
    canonical_url: 'https://natal-service.com/marketing', project_name: 'Marketing', version_sha256: digest,
    published_at: '2026-09-24T00:00:00Z',
    configuration: { ...configuration, marketing: { ...defaults.configuration, gradient_id: 'aurora' } },
    content: { ...content, contacts: { ...content.contacts, email: 'welcome@natal-service.com', phone: '+380 93 725 64 69', url: '', instagram: '' }, marketing },
    assets: Object.fromEntries(['hero_visual', 'visual_break_visual', 'walkthrough_visual'].map(slot => [slot, `/api/v1/public/landings/marketing/versions/${digest}/assets/${slot}/${digest}.png`])),
  } }))
  await page.goto('/marketing')
  await expect(page.locator('.mk-mockup img')).toHaveAttribute('src', new RegExp(`/versions/${digest}/assets/walkthrough_visual/${digest}.png$`))
  await expect(page.getByRole('link', { name: 'App Store · Explore Natal' }).first()).toHaveAttribute('href', 'https://apps.apple.com/app/id123456')
  await expect(page.locator('.mk-reference-note')).toContainText('These are not Natal customer reviews.')
  await expect(page.getByText('Complete manually in Landing Studio', { exact: false })).toHaveCount(0)
  expect(await page.locator('.lp-page').evaluate(root => root.scrollWidth <= root.clientWidth)).toBe(true)
  await page.getByRole('link', { name: 'Google Play · Explore Natal' }).first().click()
  await expect(page.locator('.mk-footer')).toBeFocused()
  await expect(page.locator('.mk-footer a[href="mailto:welcome@natal-service.com"]')).toBeVisible()
  await expect(page.locator('.mk-footer a[href="tel:+380937256469"]')).toBeVisible()
  await expect(page.locator('.mk-legal')).toContainText('Privacy policy')
  await expect(page.locator('.mk-legal')).toContainText('Terms & conditions')
  await expect(page.locator('.mk-legal a')).toHaveCount(3)
  await expect(page.locator('.mk-legal a').nth(1)).toHaveAttribute('href', '/legal/terms?lang=en')
  await expect(page.locator('.mk-legal .mk-policy-pending')).toHaveCount(0)
  await expect(page.locator('.mk-socials img')).toHaveCount(3)
  for (const icon of await page.locator('.mk-contact-link img').all()) {
    const box = await icon.boundingBox(); expect(box?.width).toBe(22); expect(box?.height).toBe(22)
  }
  await expect(page.locator('.mk-socials a, .mk-socials button')).toHaveCount(0)
  for (const name of ['Telegram', 'Instagram', 'Threads']) await expect(page.locator('.mk-socials').getByRole('img', { name, exact: true })).toBeVisible()
})

test('every legal document opens directly in both languages, stays untracked and fits the viewport', async ({ page }, testInfo) => {
  let requests = 0
  page.on('request', request => { if (/facebook|\/api\/v1\/public\//.test(request.url())) requests += 1 })
  await page.addInitScript(() => localStorage.setItem('natal_privacy_preferences_v2', JSON.stringify({ version: 2, analytics: true, marketing: true, savedAt: Date.now() })))
  for (const kind of ['terms', 'privacy', 'cookies']) for (const language of ['en', 'uk']) {
    await page.goto(`/legal/${kind}?lang=${language}`)
    await expect(page.locator('html')).toHaveAttribute('lang', language)
    await expect(page.locator('.natal-legal-main h1')).toBeVisible()
    await expect(page.locator('.natal-legal-draft')).toBeVisible()
    await expect(page.locator('.natal-legal-footer .natal-legal-links a')).toHaveCount(3)
    await expect(page.locator('.natal-legal-main a[href="mailto:welcome@natal-service.com"]')).toHaveCount(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const small = await page.locator('.natal-legal-header nav a, .natal-legal-contents a').evaluateAll(links => links.some(link => link.getBoundingClientRect().height < 44))
    expect(small).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`${kind}-${language}.png`) })
  }
  expect(requests).toBe(0)
  await page.getByRole('link', { name: 'English', exact: true }).click()
  await expect(page).toHaveURL(/\/legal\/cookies\?lang=en$/)
  await page.getByRole('button', { name: 'Cookie settings', exact: true }).first().click()
  await expect(page.getByLabel('Privacy preferences', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Reject optional', exact: true }).click()
  expect(requests).toBe(0)
})

test('the basic template links to shared terms without consuming a project slug', async ({ page }) => {
  await page.goto('/published-project')
  await page.getByRole('button', { name: 'Reject optional' }).click()
  await page.locator('.lp-footer').getByRole('link', { name: 'Terms & conditions' }).click()
  await expect(page).toHaveURL(/\/legal\/terms\?lang=en$/)
  await expect(page.getByRole('heading', { name: 'Terms & conditions', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Terms & conditions', exact: true })).toBeVisible()
})

test('separate choices gate requests and withdrawal persists across reloads', async ({ page }) => {
  let metaRequests = 0
  const events: Array<{ event_type: string }> = []
  await page.route(/https:\/\/(connect\.facebook\.net|www\.facebook\.com)\/.*/, route => { metaRequests += 1; return route.fulfill({ status: 204, body: '' }) })
  await page.route('**/api/v1/public/landing-analytics/events', route => { events.push(route.request().postDataJSON()); return route.fulfill({ status: 202, json: {} }) })
  await page.goto('/published-project')
  await expect(page.getByRole('heading', { name: 'A published Natal product' })).toBeVisible()
  expect(metaRequests).toBe(0); expect(events).toHaveLength(0)
  const panel = page.getByLabel('Privacy preferences', { exact: true })
  for (const checkbox of await panel.getByRole('checkbox').all()) await expect(checkbox).not.toBeChecked()
  await page.getByRole('checkbox', { name: /Natal analytics/ }).check()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect.poll(() => events.length).toBe(1)
  expect(metaRequests).toBe(0)
  await page.getByRole('button', { name: 'Cookie settings', exact: true }).click()
  await page.getByRole('checkbox', { name: /Meta advertising/ }).check()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect.poll(() => metaRequests).toBe(1)
  await page.evaluate(() => { document.cookie = '_fbp=test; Path=/'; document.cookie = '_fbc=test; Path=/' })
  await page.getByRole('button', { name: 'Cookie settings', exact: true }).click()
  await page.getByRole('button', { name: 'Reject optional' }).click()
  expect(await page.evaluate(() => document.cookie)).not.toMatch(/_fb[pc]=/)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'A published Natal product' })).toBeVisible()
  await expect(panel).toHaveCount(0)
  expect(metaRequests).toBe(1); expect(events).toHaveLength(1)
})
