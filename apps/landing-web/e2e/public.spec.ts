import { expect, test } from '@playwright/test'

const digest = 'a'.repeat(64)
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
    const match = /^\/api\/v1\/public\/landings\/(ai|la|wa)\/([a-z0-9-]+)$/.exec(url.pathname)
    if (!match) return route.fulfill({ status: 404, body: '{}' })
    const [, lane, slug] = match
    await route.fulfill({
      status: 200, contentType: 'application/json',
      headers: { 'Cache-Control': 'no-store' },
      body: JSON.stringify({
        canonical_url: `https://natal-service.com/${lane}/${slug}`,
        project_name: 'Published Project', configuration, content,
        assets: {
          hero_visual: `/api/v1/public/landings/${lane}/${slug}/versions/${digest}/assets/hero_visual/${digest}.png`,
          visual_break_visual: `/api/v1/public/landings/${lane}/${slug}/versions/${digest}/assets/visual_break_visual/${digest}.png`,
        },
        version_sha256: digest, published_at: '2026-09-08T00:00:00Z',
      }),
    })
  })
})

test('renders the umbrella with no directory or CTA', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Natal' })).toBeVisible()
  await expect(page.getByText('Digital products and services by Natal.')).toBeVisible()
  await expect(page.getByRole('link')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Allow' })).toBeVisible()
})

test('does not contact Meta before consent and loads the Pixel after consent', async ({ page }) => {
  let metaRequests = 0
  await page.route(/https:\/\/(connect\.facebook\.net|www\.facebook\.com)\/.*/, async route => {
    metaRequests += 1
    await route.fulfill({ status: 204, body: '' })
  })
  await page.goto('/')
  expect(metaRequests).toBe(0)
  await page.getByRole('button', { name: 'Allow' }).click()
  await expect.poll(() => metaRequests).toBeGreaterThan(0)
})

test('renders the exact shared Landing composition responsively', async ({ page }) => {
  await page.goto('/ai/published-project')
  await expect(page.getByLabel('Landing live preview')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'A published Natal product' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Email Natal/ }).first()).toHaveAttribute('href', 'mailto:hello@example.com')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
})

test('supports every lane and direct SPA deep links', async ({ page }) => {
  for (const lane of ['ai', 'la', 'wa']) {
    await page.goto(`/${lane}/published-project`)
    await expect(page.getByRole('heading', { name: 'A published Natal product' })).toBeVisible()
  }
})

test('uses the branded visual 404 while the SPA response remains successful', async ({ page }) => {
  const response = await page.goto('/unknown/path')
  expect(response?.status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  await expect(page.getByText('This Natal page is unavailable.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Go to Natal' })).toHaveAttribute('href', '/')
})
