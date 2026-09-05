import { expect, test, type Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import type { LandingDetail } from '../src/types'

const project = '018f07ea-7f20-7000-8000-000000000011'
const landing = '018f07ea-7f20-7000-8000-000000000012'
const base = `/api/v1/landings/projects/${project}/pages/${landing}`
const bytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
const sha = createHash('sha256').update(bytes).digest('hex')
const fonts = ['Inter', 'Manrope', 'Source Sans 3', 'Roboto Condensed', 'Montserrat', 'Oswald', 'Cormorant Garamond', 'Cormorant Garamond Italic', 'Lora', 'Lora Italic'] as const
function fixture(): LandingDetail {
  return {
    schema: 'ptw.landing.workspace.v1', landing_id: landing, project_id: project,
    source_brief_id: '018f07ea-7f20-7000-8000-000000000013', source_creative_id: '018f07ea-7f20-7000-8000-000000000014', source_version: 1, source_version_sha256: 'a'.repeat(64),
    ordinal: 1, origin: 'post_generation', status: 'draft', state_sha256: 'b'.repeat(64), approved_version_count: 0, generation: {}, created_at: '', updated_at: '',
    template_id: 'project_landing', catalog: { section_order: [], font_families: [...fonts] },
    configuration: { schema: 'ptw.landing.configuration.v1', theme: { background_color: '#f4f5f2', surface_color: '#ffffff', text_color: '#1a1a1a', accent_color: '#1675f8', font_family: 'Manrope', heading_font_family: 'Source Sans 3', corner_radius: 24 }, hero: { alignment: 'left', image_position: 'right' }, features: { layout: 'three_columns' }, social_proof: { layout: 'cards' }, visual_break: { height: 'medium' }, contacts: { alignment: 'left' }, faq: { style: 'divided' } },
    content: {
      schema: 'ptw.landing.content.v1', hero: { title: 'Наведіть лад у домашній аптечці', supporting_text: 'Зберігайте ліки за фото упаковок та швидко переглядайте домашню аптечку.', cta_label: 'Записатися на дзвінок', visual_direction: 'A calm product illustration' },
      features: [{ title: 'Облік за фото упаковок', description: 'Додавайте ліки за фото їхніх упаковок.' }, { title: 'Огляд домашньої аптечки', description: 'Переглядайте, які ліки вже є вдома.' }, { title: 'Зрозумілий список ліків', description: 'Тримайте домашню аптечку впорядкованою.' }],
      social_proof: { heading: 'Досвід користувачів', items: [] }, visual_break: { visual_direction: 'A supporting landscape illustration' },
      contacts: { heading: 'Познайомтеся із застосунком', supporting_text: 'Запишіться на безкоштовний 15-хвилинний дзвінок із ментором.', email: '', phone: '', url: '' },
      faq: [{ question: 'Що допомагає робити застосунок?', answer: 'Застосунок допомагає вести облік ліків удома.' }, { question: 'Як додати ліки?', answer: 'Додайте фото упаковки.' }, { question: 'Чи замінює він консультацію лікаря?', answer: 'Ні, він допомагає з обліком ліків.' }],
    },
    assets: (['hero_visual', 'visual_break_visual'] as const).map(slot => ({ slot, available: true, sha256: sha, history: [{ sha256: sha, selected: true, width: 1, height: 1, mime_type: 'image/png', visual_direction: 'Test image' }] })),
    image_generation_available: true, versions: [],
  }
}
async function setup(page: Page) {
  let current = fixture()
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (value: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/v1/projects') return json({ items: [{ project_id: project, name: 'Landing visual test', created_at: '', updated_at: '' }] })
    if (path.endsWith('/source-posts')) return json({ items: [] })
    if (path.endsWith('/pages')) return json({ items: [current] })
    if (path === base) return json(current)
    if (path.includes('/history/')) return route.fulfill({ contentType: 'image/png', body: bytes, headers: { 'Cache-Control': 'private, no-store', 'X-PTW-Content-SHA256': sha } })
    if (path.endsWith('/configuration') || path.endsWith('/save') || path.endsWith('/approve')) {
      const body = route.request().postDataJSON()
      current = { ...current, configuration: body.configuration, content: body.content, state_sha256: 'c'.repeat(64) }
      if (path.endsWith('/approve')) current.approved_version_count++
      return json(path.endsWith('/configuration') ? current : { landing: current, checkpoint: null, learning_proposal: null })
    }
    return json({ items: [] })
  })
  await page.goto(`/?e2e=1&page=landing&project=${project}&landing=${landing}`)
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByLabel('Hero title')).toBeVisible()
}
const editorSection = (page: Page, name: string) => page.getByRole('navigation', { name: 'Page sections' }).getByRole('button', { name, exact: true })

test('renders at each device width with loaded fonts, bounded images, and no placeholder proof', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog', { name: 'Full-screen Landing preview' })
  await expect(dialog.locator('.lp-hero img')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  expect(await page.evaluate(() => document.fonts.check('18px "Landing Manrope"', 'Її Єє Ґґ Іі'))).toBe(true)
  expect(await page.evaluate(() => document.fonts.check('700 36px "Landing Source Sans 3"', 'Її Єє Ґґ Іі'))).toBe(true)
  for (const [name, width] of [['Desktop', 1280], ['Tablet', 768], ['Mobile', 360]] as const) {
    await dialog.getByRole('button', { name: `${name} ${width}` }).click()
    await expect(dialog.locator('.landing-device-page')).toHaveCSS('width', `${width}px`)
    const bounds = await dialog.locator('.lp-page').evaluate(root => ({ width: root.clientWidth, scroll: root.scrollWidth, heroColumns: getComputedStyle(root.querySelector('.lp-hero')!).gridTemplateColumns.split(' ').length, breakHeight: (root.querySelector('.lp-visual-frame') as HTMLElement).offsetHeight, breakWidth: (root.querySelector('.lp-visual-frame') as HTMLElement).offsetWidth, sectionWidth: (root.querySelector('.lp-visual') as HTMLElement).offsetWidth }))
    expect(bounds.scroll).toBeLessThanOrEqual(bounds.width)
    expect(bounds.heroColumns).toBe(width === 360 ? 1 : 2)
    expect(bounds.breakHeight).toBeLessThanOrEqual(width === 360 ? 280 : 420)
    expect(bounds.breakWidth).toBe(bounds.sectionWidth)
    await expect(dialog.locator('[data-section=social_proof]')).toHaveCount(0)
    await expect(dialog.locator('.lp-page')).not.toContainText('PRIVATE LANDING')
    await expect(dialog.locator('.lp-page')).not.toContainText('Owner-provided evidence')
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'View Landing' })).toBeFocused()
})

test('offers actual page interactions and keeps console and page languages independent', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Mobile 360' }).click()
  await dialog.locator('.lp-cta').click()
  await expect(dialog.locator('[data-section=contacts]')).toBeFocused()
  await dialog.locator('.lp-nav').getByRole('link', { name: 'Запитання', exact: true }).click()
  const faq = dialog.locator('details').first()
  await expect(faq).not.toHaveAttribute('open')
  await faq.locator('summary').click()
  await expect(faq).toHaveAttribute('open', '')
  await page.keyboard.press('Escape')
  await editorSection(page, 'Page design').click()
  await page.getByLabel('Page language').selectOption('en')
  await page.getByRole('button', { name: 'View Landing' }).click()
  await expect(page.getByRole('dialog').getByRole('navigation')).toHaveAccessibleName('Page navigation')
  await expect(page.getByRole('dialog').locator('h1')).toHaveText('Наведіть лад у домашній аптечці')
})

test('validates all CTA destinations and approves without evidence', async ({ page }) => {
  await setup(page)
  await expect(page.getByRole('button', { name: 'Approve Landing' })).toBeDisabled()
  await editorSection(page, 'Get in touch').click()
  await page.getByLabel('HTTPS contact URL').fill('https://example.test/book')
  await page.getByLabel('Email', { exact: true }).fill('owner@example.test')
  await page.getByLabel('Phone', { exact: true }).fill('+380 (50) 123-45-67')
  await editorSection(page, 'Hero').click()
  for (const [target, href] of [['url', 'https://example.test/book'], ['email', 'mailto:owner@example.test'], ['phone', 'tel:+380501234567']]) {
    await page.getByLabel('Button destination').selectOption(target)
    await page.getByRole('button', { name: 'View Landing' }).click()
    await expect(page.getByRole('dialog').locator('.lp-cta')).toHaveAttribute('href', href)
    await expect(page.getByRole('dialog').locator(`.lp-contact-links a[href="${href}"]`)).toHaveCount(1)
    await page.keyboard.press('Escape')
  }
  await expect(page.getByRole('button', { name: 'Approve Landing' })).toBeEnabled()
  await page.getByRole('button', { name: 'Approve Landing' }).click()
  await expect(page.getByRole('status')).toContainText('Landing approved')
})

test('edits sections, crop focus and type without leaking editor controls into preview', async ({ page }) => {
  await setup(page)
  if ((page.viewportSize()?.width || 0) > 700) {
    await page.locator('.lp-features').click({ position: { x: 20, y: 30 } })
    await expect(page.getByLabel('Feature layout')).toBeVisible()
  }
  await editorSection(page, 'Visual story').click()
  await page.getByRole('slider', { name: 'Horizontal focus' }).press('Home')
  for (let i = 0; i < 25; i++) await page.getByRole('slider', { name: 'Horizontal focus' }).press('ArrowRight')
  await page.getByLabel('Image height').selectOption('small')
  await editorSection(page, 'Page design').click()
  await page.getByLabel('Heading font').selectOption('Cormorant Garamond Italic')
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.locator('.lp-edit-section')).toHaveCount(0)
  await expect(dialog.locator('.lp-visual img')).toHaveCSS('object-position', '25% 50%')
  await page.evaluate(() => document.fonts.ready)
  expect(await page.evaluate(() => document.fonts.check('italic 700 36px "Landing Cormorant Garamond Italic"', 'Її Єє Ґґ Іі'))).toBe(true)
  await expect(dialog.locator('h1')).toHaveCSS('font-style', 'italic')
})

test('contains maximum-length copy and loads every selectable font', async ({ page }) => {
  await setup(page)
  await page.getByLabel('Hero title').fill('W'.repeat(140))
  await page.getByLabel('Supporting text').fill('Long supporting copy. '.repeat(18).slice(0, 360))
  await page.getByLabel('CTA label').fill('A'.repeat(60))
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Mobile 360' }).click()
  const geometry = await dialog.locator('.lp-page').evaluate(root => ({ pageWidth: root.clientWidth, scrollWidth: root.scrollWidth, buttonWidth: root.querySelector('.lp-cta')!.getBoundingClientRect().width, heroWidth: root.querySelector('.lp-hero')!.getBoundingClientRect().width }))
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.pageWidth)
  expect(geometry.buttonWidth).toBeLessThanOrEqual(geometry.heroWidth)
  const loaded = await page.evaluate(async names => Promise.all(names.map(async font => {
    const faces = await document.fonts.load(`${font.includes('Italic') ? 'italic ' : ''}400 18px "Landing ${font}"`, 'Її Єє Ґґ Іі')
    return faces.length > 0 && faces.every(face => face.status === 'loaded')
  })), [...fonts])
  expect(loaded.every(Boolean)).toBe(true)
})
