import { expect, test, type Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import { componentDefaults } from '../src/landing/model'
import type { LandingDetail, LandingThemePreset } from '../src/types'

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
async function setup(page: Page, showcase = false, projectName = 'Landing visual test') {
  let current = fixture()
  if (showcase) {
    current.template_id = 'app_showcase'
    current.configuration.showcase = { gradient_end: '#08cbb5', screen_scale: 1, screen_offset: 32 }
    current.content.app_screens = [1, 2, 3].map(i => ({ title: `Екран застосунку ${i}`, description: 'Додавайте та впорядковуйте речі у власному просторі.', visual_direction: `A clean app screen ${i}` }))
    current.assets = (['app_screen_1', 'app_screen_2', 'app_screen_3', 'visual_break_visual'] as const).map(slot => ({ ...current.assets[0], slot }))
  }
  current.catalog.theme_presets = (['studio', 'editorial', 'soft'] as const).map((id, i) => ({
    id, en: ['Studio', 'Editorial', 'Soft bloom'][i], uk: ['Студія', 'Редакційна', 'М’якість'][i], description_en: 'Coordinated components', description_uk: 'Узгоджені компоненти',
    theme: { ...current.configuration.theme, background_color: ['#f7f8fc', '#f7f3eb', '#f0f6f2'][i], corner_radius: [20, 4, 32][i] },
    components: { ...componentDefaults, button_style: ['filled', 'outlined', 'elevated'][i], button_shape: ['rounded', 'square', 'pill'][i], card_style: ['filled', 'minimal', 'elevated'][i] }, faq: { style: 'divided' },
  } as LandingThemePreset))
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (value: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/v1/projects') return json({ items: [{ project_id: project, name: projectName, created_at: '', updated_at: '' }] })
    if (path.endsWith('/source-posts')) return json({ items: [] })
    if (path.endsWith('/pages')) return json({ items: [current] })
    if (path === base) return json(current)
    if (path.includes('/history/')) return route.fulfill({ contentType: 'image/png', body: bytes, headers: { 'Cache-Control': 'private, no-store', 'X-PTW-Content-SHA256': sha } })
    if (path.endsWith('/generate')) {
      if (path.includes('/walkthrough_visual/')) current.assets.push({ ...current.assets[0], slot: 'walkthrough_visual' })
      return json(current)
    }
    if (path.endsWith('/configuration') || path.endsWith('/save') || path.endsWith('/approve')) {
      const body = route.request().postDataJSON()
      current = { ...current, configuration: body.configuration, content: body.content, state_sha256: 'c'.repeat(64) }
      if (path.endsWith('/approve')) current.approved_version_count++
      return json(path.endsWith('/configuration') ? current : { landing: current, checkpoint: null, learning_proposal: null })
    }
    return json({ items: [] })
  })
  await page.goto(`/?e2e=1&page=landing&project=${project}&landing=${landing}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await expect(page.getByLabel('Hero title')).toBeVisible()
}
const editorSection = (page: Page, name: string) => ({ click: () => page.getByRole('combobox', { name: 'Page section', exact: true }).selectOption({ label: name }) })
const openPublication = async (page: Page) => {
  await page.getByLabel('More actions', { exact: true }).click()
  await page.getByRole('button', { name: 'Approve & publish', exact: true }).click()
}

test('changes template directly from an unsaved unapproved draft and returns through history', async ({ page }) => {
  await setup(page, false, 'Застосунок для обліку домашньої аптечки за фото упаковок ліків')
  const original = fixture()
  const reference = { template_id: 'app_showcase', template_version: 2, template_sha256: 'c'.repeat(64) }
  const next = fixture()
  next.landing_id = '018f07ea-7f20-7000-8000-000000000099'
  next.ordinal = 2; next.template_id = 'app_showcase'; next.template_reference = reference
  next.configuration.showcase = { gradient_end: '#08cbb5', screen_scale: 1, screen_offset: 32 }
  next.content.app_screens = [1, 2, 3].map(i => ({ title: `Екран ${i}`, description: 'Завдання застосунку', visual_direction: 'A clear app screen' }))
  next.assets = []
  let created = false
  const writes: string[] = []
  page.on('request', request => { if (request.method() === 'POST') writes.push(new URL(request.url()).pathname) })
  await page.route('**/api/v1/landings/templates', route => route.fulfill({ json: { items: [{ ...reference, name: 'App Showcase' }] } }))
  await page.route(`**/api/v1/landings/projects/${project}/pages`, route => route.fulfill({ json: { items: created ? [next, original] : [original] } }))
  await page.route(`**/api/v1/landings/projects/${project}/pages/${next.landing_id}`, route => route.fulfill({ json: next }))
  await page.route(`**/api/v1/landings/projects/${project}/pages/variants`, route => {
    const body = route.request().postDataJSON()
    expect(body.template_reference).toEqual(reference)
    expect(body.request_id).toMatch(/^[a-f0-9-]{36}$/)
    created = true
    return route.fulfill({ status: 202, json: { landing: next, created: true } })
  })
  await page.reload()
  await page.getByLabel('Hero title').fill('Збережіть цю незавершену думку')
  await expect(page.locator('.landing-actions > button')).toHaveCount(2)
  await expect(page.getByRole('button', { name: 'Approve Landing' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Change template' }).click()
  const chooser = page.getByRole('dialog', { name: 'Change template', exact: true })
  await chooser.getByRole('button', { name: 'App Showcase', exact: true }).click()
  expect(await chooser.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  await chooser.getByRole('button', { name: 'Apply template', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(next.landing_id))
  await expect(page.getByRole('heading', { name: 'App Showcase', exact: true })).toBeVisible()
  await expect(page.locator('.as-page')).toHaveCount(1)
  expect(writes).toEqual([`/api/v1/landings/projects/${project}/pages/variants`])
  await page.getByLabel('More actions', { exact: true }).click()
  await page.getByRole('button', { name: 'History', exact: true }).click()
  await page.getByRole('dialog', { name: 'Landing history' }).getByRole('button', { name: /Project landing/ }).click()
  await expect(page.getByLabel('Hero title')).toHaveValue('Збережіть цю незавершену думку')
  await page.reload()
  await expect(page.getByLabel('Hero title')).toHaveValue('Збережіть цю незавершену думку')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 768, height: 1024 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(page.locator('.landing-workbench.is-edit .landing-preview-area')).toBeHidden()
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.locator('.landing-preview-area')).toBeVisible()
})

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
    expect(bounds.heroColumns).toBe(width <= 900 ? 1 : 2)
    const faqColumns = await dialog.locator('.lp-faq').evaluate(node => getComputedStyle(node).gridTemplateColumns.split(' ').length)
    expect(faqColumns).toBe(width <= 900 ? 1 : 2)
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
  await openPublication(page)
  await expect(page.getByRole('button', { name: 'Approve Landing' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await editorSection(page, 'Get in touch').click()
  await page.getByLabel('Telegram bot link').fill('https://example.test/book')
  await openPublication(page)
  await expect(page.getByRole('button', { name: 'Approve Landing' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await page.getByLabel('Telegram bot link').fill('https://t.me/natal_helper_bot')
  await page.getByLabel('Instagram profile link').fill('https://www.instagram.com/natal_service/')
  await page.getByLabel('Email', { exact: true }).fill('owner@example.test')
  await page.getByLabel('Phone', { exact: true }).fill('+380 (50) 123-45-67')
  await editorSection(page, 'Hero').click()
  for (const [target, href] of [['url', 'https://t.me/natal_helper_bot'], ['email', 'mailto:owner@example.test'], ['phone', 'tel:+380501234567']]) {
    await page.getByLabel('Button destination').selectOption(target)
    await page.getByRole('button', { name: 'View Landing' }).click()
    await expect(page.getByRole('dialog').locator('.lp-cta')).toHaveAttribute('href', href)
    await expect(page.getByRole('dialog').locator('.lp-phone-action')).toHaveAttribute('href', href)
    await expect(page.getByRole('dialog').locator(`.lp-contact-links a[href="${href}"]`)).toHaveCount(1)
    if (target === 'url') await expect(page.getByRole('dialog').locator(`.lp-contact-links a[href="${href}"]`)).toContainText('@natal_helper_bot')
    await page.keyboard.press('Escape')
  }
  await page.getByRole('button', { name: 'View Landing' }).click()
  const instagram = page.getByRole('dialog').locator('.lp-contact-links a[href="https://www.instagram.com/natal_service/"]')
  await expect(instagram).toContainText('@natal_service')
  await expect(instagram.locator('svg')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await openPublication(page)
  await expect(page.getByRole('button', { name: 'Approve Landing' })).toBeEnabled()
  await page.getByRole('button', { name: 'Approve Landing' }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('Landing approved')
  await page.keyboard.press('Escape')
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


test('keeps canonical Natal identity across tunable themes and preview widths', async ({ page }) => {
  await setup(page)
  await editorSection(page, 'Page design').click()
  for (const [name, style] of [['Studio', 'filled'], ['Editorial', 'outlined'], ['Soft bloom', 'elevated']] as const) {
    await page.getByRole('button', { name: new RegExp(name + ' Coordinated') }).click()
    await page.getByRole('button', { name: 'View Landing' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.locator('.lp-page')).toHaveClass(new RegExp(`lp-button-${style}`))
    for (const width of ['Desktop 1280', 'Tablet 768', 'Mobile 360']) {
      await dialog.getByRole('button', { name: width }).click()
      await expect(dialog.locator('.lp-brand')).toHaveAccessibleName('Natal')
      await expect(dialog.locator('.lp-brand img')).toHaveAttribute('alt', 'Natal')
      await expect(dialog.locator('.lp-brand img')).toHaveJSProperty('complete', true)
      expect(await dialog.locator('.lp-page').evaluate(root => root.scrollWidth <= root.clientWidth)).toBe(true)
    }
    await page.keyboard.press('Escape')
  }
  await editorSection(page, 'Hero').click()
  await page.getByLabel('Button style', { exact: true }).selectOption('outlined')
  await page.getByLabel('Button shape', { exact: true }).selectOption('pill')
  await editorSection(page, 'Features').click()
  await page.getByLabel('Card style', { exact: true }).selectOption('minimal')
  await page.getByLabel('Icon style', { exact: true }).selectOption('hidden')
  await editorSection(page, 'Get in touch').click()
  await page.getByLabel('Panel style', { exact: true }).selectOption('surface')
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.locator('.lp-cta')).toHaveCSS('border-radius', '999px')
  await expect(dialog.locator('.lp-cta')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await expect(dialog.locator('.lp-feature-icon').first()).toBeHidden()
  await expect(dialog.locator('.lp-feature-grid article').first()).toHaveCSS('border-radius', '0px')
  await page.keyboard.press('Escape')
  const saved = page.waitForRequest(request => request.url().endsWith('/save'))
  await page.getByRole('button', { name: 'Save Landing' }).click()
  const body = (await saved).postDataJSON()
  expect(body.configuration.identity).toBeUndefined()
  expect(body.configuration.components.card_style).toBe('minimal')
})

test('saves independent Post-style image directions before generating or enhancing', async ({ page }) => {
  await setup(page)
  await page.locator('.landing-direction-picker > summary').click()
  await page.getByRole('radio', { name: /Tactile handmade/ }).check()
  await page.getByRole('radio', { name: /Remove scene background/ }).check()
  await page.getByLabel('Hero title', { exact: true }).fill('Збережений заголовок')
  const saved = page.waitForRequest(request => request.url().endsWith('/configuration'))
  const generated = page.waitForRequest(request => request.url().endsWith('/hero_visual/generate'))
  await page.getByRole('button', { name: 'Generate', exact: true }).click()
  const body = (await saved).postDataJSON()
  expect(body.configuration.image_directions.hero_visual).toEqual({ style: 'tactile_handmade', background: 'isolated_key_element' })
  expect(body.configuration.image_directions.visual_break_visual.style).toBe('premium_editorial')
  expect(body.content.hero.title).toBe('Збережений заголовок')
  await generated
  await expect(page.getByLabel('Hero title')).toHaveValue('Збережений заголовок')
  await editorSection(page, 'Visual story').click()
  // The same mounted inspector retains its disclosure state across sections.
  const picker = page.locator('.landing-direction-picker')
  if (!(await picker.evaluate(element => element.hasAttribute('open')))) await picker.locator('summary').click()
  await page.getByRole('radio', { name: /Contemporary 3D/ }).check()
  const enhanced = page.waitForRequest(request => request.url().endsWith('/visual_break_visual/generate'))
  await page.getByRole('button', { name: 'Enhance', exact: true }).click()
  expect((await enhanced).postDataJSON().enhance_current).toBe(true)
})

test('edits the app task, switches screen themes and layouts, and saves pending feature copy', async ({ page }) => {
  await setup(page)
  if ((page.viewportSize()?.width || 0) > 700) {
    await page.locator('.lp-phone-edit').click()
    await expect(page.getByLabel('Key feature title')).toBeVisible()
    await expect(page.locator('.lp-phone-stage')).toHaveClass(/lp-phone-selected/)
  } else await editorSection(page, 'App feature').click()
  await page.getByLabel('Key feature title').fill('Забронювати сафарі')
  await page.getByLabel('Feature screen description').fill('Оберіть формат відвідування у застосунку.')
  await page.getByLabel('App action label').fill('Дізнатися про візит')
  await page.getByLabel('Row label', { exact: true }).nth(0).fill('Формат сафарі')
  await page.getByLabel('Row detail (optional)', { exact: true }).nth(0).fill('Переглянути варіанти')
  for (const [theme, layout] of [['Light', 'overview'], ['Dark', 'booking'], ['Glass', 'checklist']] as const) {
    await page.getByRole('button', { name: theme, exact: true }).click()
    await page.getByLabel('Feature screen layout').selectOption(layout)
    await page.getByRole('button', { name: 'View Landing' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.locator('.lp-phone')).toHaveClass(new RegExp(`lp-phone-${theme.toLowerCase()} lp-phone-${layout}`))
    await expect(dialog.locator('.lp-phone h2')).toHaveText('Забронювати сафарі')
    await expect(dialog.locator('.lp-phone-edit')).toHaveCount(0)
    await dialog.locator('.lp-phone-row').first().click()
    await expect(dialog.locator('.lp-phone-row').first()).toHaveAttribute('aria-pressed', 'true')
    await dialog.locator('.lp-phone-row').nth(1).click()
    await expect(dialog.locator('.lp-phone-row').first()).toHaveAttribute('aria-pressed', layout === 'checklist' ? 'true' : 'false')
    await dialog.locator('.lp-phone-action').click()
    await expect(dialog.locator('[data-section=contacts]')).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByLabel('Key feature title')).toHaveValue('Забронювати сафарі')
  }
  const saved = page.waitForRequest(request => request.url().endsWith('/save'))
  await page.getByRole('button', { name: 'Save Landing' }).click()
  const body = (await saved).postDataJSON()
  expect(body.configuration.phone_mockup).toEqual({ theme: 'glass', layout: 'checklist' })
  expect(body.content.app_feature.items[0]).toEqual({ label: 'Формат сафарі', value: 'Переглянути варіанти' })
})

test('keeps long app UI inside the canonical phone at all preview widths', async ({ page }) => {
  await setup(page)
  await editorSection(page, 'App feature').click()
  await page.getByLabel('Key feature title').fill('Ї'.repeat(72))
  await page.getByLabel('Feature screen description').fill('Опис '.repeat(32))
  for (let i = 0; i < 3; i++) {
    await page.getByLabel('Row label', { exact: true }).nth(i).fill('Назва '.repeat(10))
    await page.getByLabel('Row detail (optional)', { exact: true }).nth(i).fill('Деталі '.repeat(11))
  }
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  for (const width of ['Desktop 1280', 'Tablet 768', 'Mobile 360']) {
    await dialog.getByRole('button', { name: width }).click()
    const bounds = await dialog.locator('.lp-phone').evaluate(phone => {
      const screen = phone.querySelector('.lp-phone-screen') as HTMLElement
      const scroll = phone.querySelector('.lp-phone-scroll') as HTMLElement
      const action = phone.querySelector('.lp-phone-action') as HTMLElement
      return { width: screen.clientWidth, scrollWidth: screen.scrollWidth, height: phone.clientHeight, overflow: scroll.scrollHeight > scroll.clientHeight, actionBottom: action.getBoundingClientRect().bottom, bottom: screen.getBoundingClientRect().bottom }
    })
    expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width)
    expect(bounds.height).toBeLessThanOrEqual(601)
    expect(bounds.overflow).toBe(true)
    expect(bounds.actionBottom).toBeLessThan(bounds.bottom)
    const scroll = dialog.getByRole('region', { name: 'Екран ключової функції' })
    await scroll.scrollIntoViewIfNeeded()
    await scroll.evaluate(el => { el.scrollTop = el.scrollHeight })
    await expect(dialog.locator('.lp-phone-row').last()).toBeInViewport()
  }
})


test('uses a temporary reference in either image slot, clears on completion, error and navigation', async ({ page }) => {
  await setup(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const upload = () => page.getByLabel(/Upload reference image/).setInputFiles({ name: 'reference.png', mimeType: 'image/png', buffer: bytes })
  await upload()
  await expect(page.getByRole('button', { name: 'Enhance', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Remove reference' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Remove reference' })).toHaveCount(0)
  for (const [section, slot] of [['Hero', 'hero_visual'], ['Visual story', 'visual_break_visual']]) {
    if (slot === 'visual_break_visual') await editorSection(page, section).click()
    await upload()
    await page.locator(".landing-image-editor").screenshot({ path: `.local/image-reference-landing-${slot}-${test.info().project.name}.png` })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const request = page.waitForRequest(request => request.url().endsWith(`/${slot}/generate`))
    await page.getByRole('button', { name: 'Generate', exact: true }).click()
    expect((await request).postDataJSON()).toMatchObject({ reference_image: { mime_type: 'image/png', bytes_base64: bytes.toString('base64') } })
    await expect(page.getByRole('button', { name: 'Remove reference' })).toHaveCount(0)
  }
  await upload()
  await editorSection(page, 'Hero').click()
  await expect(page.getByRole('button', { name: 'Remove reference' })).toHaveCount(0)
  await upload()
  await page.route('**/hero_visual/generate', route => route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Generation failed; previous image preserved' }) }))
  await page.getByRole('button', { name: 'Generate', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Remove reference' })).toHaveCount(0)
  await expect(page.getByText(/Generation failed; previous image preserved/)).toBeVisible()
})

test('switches between the phone and image-only hero and retains the saved mode', async ({ page }) => {
  await setup(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const mode = page.getByRole('combobox', { name: 'Visual mode' })
  await mode.focus()
  await expect(mode).toBeFocused()
  await mode.selectOption('image')
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog', { name: 'Full-screen Landing preview' })
  await expect(dialog.locator('.lp-phone')).toHaveCount(0)
  for (const [name, width] of [['Desktop', 1280], ['Mobile', 360]] as const) {
    await dialog.getByRole('button', { name: `${name} ${width}` }).click()
    await expect(dialog.locator('.lp-hero-art > img')).toHaveCSS('opacity', '1')
    expect(await dialog.locator('.lp-page').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    const art = dialog.locator('.lp-hero-art')
    const bounds = await art.evaluate(el => ({ width: el.clientWidth, height: el.clientHeight }))
    expect(bounds.height).toBeLessThanOrEqual(bounds.width + 1)
    await art.scrollIntoViewIfNeeded()
    await page.screenshot({ path: `.local/landing-image-mode-${width}-${test.info().project.name}.png` })
  }
  await dialog.getByRole('button', { name: 'Close full-screen preview' }).click()
  const request = page.waitForRequest(req => req.url().endsWith('/save') && req.method() === 'POST')
  await page.getByRole('button', { name: 'Save Landing' }).click()
  expect((await request).postDataJSON().configuration.visual_mode).toBe('image')
  await page.reload()
  await expect(mode).toHaveValue('image')
  await mode.selectOption('phone')
  await page.getByRole('button', { name: 'View Landing' }).click()
  await expect(dialog.locator('.lp-phone')).toBeVisible()
})


test('App Showcase uses static screens with individual inspectors and responsive walkthrough', async ({ page }) => {
  await setup(page, true)
  await page.getByLabel('Button style', { exact: true }).selectOption('outlined')
  await editorSection(page, 'Get in touch').click()
  await page.getByLabel('Panel style', { exact: true }).selectOption('surface')
  await editorSection(page, 'Screen 2').click()
  await expect(page.getByLabel('Screen title', { exact: true })).toHaveValue('Екран застосунку 2')
  await page.getByLabel('Screen title', { exact: true }).fill('Дуже довга назва екрана застосунку для перевірки перенесення українського тексту')
  await expect(page.getByRole('button', { name: 'Enhance', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.locator('.as-phone')).toHaveCount(5)
  await expect(dialog.locator('.lp-phone-row')).toHaveCount(0)
  await expect(dialog.locator('.as-cta').first()).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await expect(dialog.locator('.as-contact')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  for (const [name, width] of [['Desktop', 1280], ['Tablet', 768], ['Mobile', 360]] as const) {
    await dialog.getByRole('button', { name: `${name} ${width}` }).click()
    const bounds = await dialog.locator('.as-page').evaluate(root => ({ width: root.clientWidth, scroll: root.scrollWidth, steps: getComputedStyle(root.querySelector('.as-steps')!).gridTemplateColumns.split(' ').length }))
    expect(bounds.scroll).toBeLessThanOrEqual(bounds.width)
    expect(bounds.steps).toBe(width === 360 ? 1 : 3)
    await expect(dialog.locator('.as-arrow').first()).toHaveCSS('width', '32px')
    await expect(dialog.locator('.as-icon').first()).toHaveCSS('height', '40px')
    await expect(dialog.locator('.as-wave')).toHaveCSS('height', '65px')
    // The full aperture uses proportional fitting. Generated portrait content
    // reserves its camera area; legacy squares stay square without cropped labels.
    const screens = await dialog.locator('.as-screen > img').evaluateAll(images => images.map(image => {
      const aperture = image.parentElement!.getBoundingClientRect()
      const pixels = image.getBoundingClientRect()
      return { fit: getComputedStyle(image).objectFit, ratio: aperture.width / aperture.height, left: pixels.left - aperture.left,
        right: aperture.right - pixels.right, bottom: aperture.bottom - pixels.bottom,
        camera: pixels.top - aperture.top }
    }))
    expect(screens).toHaveLength(5)
    for (const screen of screens) {
      expect(screen.fit).toBe('contain')
      expect(Math.abs(screen.ratio - 9 / 19.5)).toBeLessThan(.01)
      expect(Math.abs(screen.left)).toBeLessThan(1)
      expect(Math.abs(screen.right)).toBeLessThan(1)
      expect(Math.abs(screen.bottom)).toBeLessThan(1)
      expect(Math.abs(screen.camera)).toBeLessThan(1)
    }
    const hero = await dialog.locator('.as-hero').evaluate(el => ({
      columns: getComputedStyle(el).gridTemplateColumns.split(' ').length,
      copyBottom: el.querySelector('.as-hero-copy')!.getBoundingClientRect().bottom,
      phonesTop: el.querySelector('.as-hero-phones')!.getBoundingClientRect().top,
    }))
    expect(hero.columns).toBe(width <= 900 ? 1 : 2)
    if (width <= 900) expect(hero.phonesTop).toBeGreaterThan(hero.copyBottom)
    await expect(dialog.locator('[data-section=social_proof]')).toHaveCount(0)
  }
  await dialog.locator('.as-cta').first().click()
  await expect(dialog.locator('[data-section=contacts]')).toBeFocused()
  await dialog.locator('.as-faq summary').first().click()
  await expect(dialog.locator('.as-faq details').first()).toHaveAttribute('open', '')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})


for (const showcase of [false, true]) test(`Marketing sections work in ${showcase ? 'App Showcase' : 'original Landing'}`, async ({ page }) => {
  await setup(page, showcase)
  await editorSection(page, 'Page design').click()
  await page.getByRole('button', { name: 'Enable showcase sections' }).click()
  await expect(page.getByRole('button', { name: /Aurora · calm/ })).toBeVisible()
  await page.getByRole('button', { name: /Aurora · calm/ }).click()
  await page.getByLabel(/Logo.*HEX/).fill('#ffffff')
  await page.getByLabel('Small Natal logos').uncheck()
  await expect(page.locator('.mk-motifs')).toHaveCount(0)
  await page.getByLabel('Small Natal logos').check()
  await editorSection(page, 'Comparison').click()
  await expect(page.getByText('Provide this item manually in Landing Studio, or hide it.').first()).toBeVisible()
  await page.getByLabel('Comparison item 4', { exact: true }).fill('Перевірений власником пункт із довгим українським текстом для перевірки перенесення')
  await page.getByLabel('Show row 5', { exact: true }).uncheck()
  await page.getByLabel('Show row 6', { exact: true }).uncheck()
  await editorSection(page, 'How it works').click()
  await page.getByLabel('Step 1 · title').fill('Додайте річ')
  const generated = page.waitForRequest(r => r.url().includes('/walkthrough_visual/generate'))
  await page.getByRole('button', { name: 'Generate', exact: true }).click()
  expect((await generated).postDataJSON().visual_direction).toContain('phone mockups')
  await editorSection(page, 'CTA panel').click()
  await page.getByLabel('Show CTA panel').uncheck()
  await expect(page.locator('.mk-section-cta, .as-banner')).toHaveCount(0)
  await page.getByLabel('Show CTA panel').check()
  await editorSection(page, 'Store buttons & footer').click()
  await page.getByLabel('Store button label', { exact: true }).fill('Спробувати Natal')
  await page.getByLabel('App Store URL', { exact: true }).fill('https://apps.apple.com/app/id123456')
  await page.getByLabel('Privacy policy URL', { exact: true }).fill('https://natal-service.com/privacy')
  await page.getByRole('button', { name: 'View Landing' }).click()
  const dialog = page.getByRole('dialog')
  for (const [name, width] of [['Desktop', 1280], ['Tablet', 768], ['Mobile', 360]] as const) {
    await dialog.getByRole('button', { name: `${name} ${width}` }).click()
    await expect(dialog.locator('.mk-comparison-row')).toHaveCount(4)
    await expect(dialog.locator('.mk-reviews blockquote')).toHaveCount(3)
    await expect(dialog.locator('.mk-mockup img')).toHaveCount(1)
    await expect(dialog.locator('.mk-reference-note')).toContainText('Це не відгуки клієнтів Natal.')
    await expect(dialog.locator('.mk-legal')).toContainText('Політика конфіденційності')
    await expect(dialog.locator('.mk-legal')).toContainText('Публічна оферта')
    await expect(dialog.locator('.mk-legal a')).toHaveCount(1)
    await expect(dialog.locator('.mk-legal a')).toHaveAttribute('href', 'https://natal-service.com/privacy')
    await expect(dialog.locator('.mk-legal .mk-policy-pending')).toHaveCount(1)
    await expect(dialog.getByRole('link', { name: 'App Store · Спробувати Natal' }).first()).toHaveAttribute('href', 'https://apps.apple.com/app/id123456')
    const geometry = await dialog.locator('.lp-page').evaluate(root => ({ width: root.clientWidth, scroll: root.scrollWidth, gradient: getComputedStyle(root).getPropertyValue('--mk-start').trim(), icons: [...root.querySelectorAll('.mk-icon:not(img)')].map(el => ({ width: el.getBoundingClientRect().width, mask: getComputedStyle(el).maskImage })), reviews: [...root.querySelectorAll<HTMLElement>('.mk-reviews blockquote')].map(el => el.clientWidth) }))
    expect(geometry.scroll).toBeLessThanOrEqual(geometry.width)
    expect(geometry.gradient).toBe('#7562c6')
    expect(geometry.icons.every(icon => icon.width > 0 && icon.width <= 44 && icon.mask !== 'none')).toBe(true)
    expect(geometry.reviews.every(width => width > 150)).toBe(true)
    await expect(dialog.getByText('Заповніть вручну в Landing Studio', { exact: false }).first()).toBeVisible()
  }
  await dialog.getByRole('link', { name: 'Google Play · Спробувати Natal' }).first().click()
  await expect(dialog.locator('.mk-footer')).toBeFocused()
})
