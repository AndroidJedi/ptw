import { expect, test as base } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

const test = base.extend<{ backend: { url: string; restart: () => Promise<void> } }>({
  backend: async ({}, use, info) => {
    const directory = await mkdtemp(resolve(tmpdir(), 'ptw-template-browser-'))
    const port = 43180 + info.workerIndex
    const url = `http://127.0.0.1:${port}`
    let child: ChildProcess
    const launch = async () => {
      const python = process.env.PTW_E2E_PYTHON || (existsSync('../../.venv/bin/python') ? '../../.venv/bin/python' : 'python3')
      child = spawn(python, ['../../scripts/template_browser_canary.py', '--port', String(port), '--directory', directory], { stdio: 'pipe' })
      let diagnostic = ''
      child.stderr?.on('data', value => { diagnostic += value.toString() })
      for (let attempt = 0; attempt < 80; attempt++) {
        if (child.exitCode !== null) throw Error(diagnostic)
        if (await fetch(url + '/healthz').then(r => r.ok).catch(() => false)) return
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      throw Error('Templates fixture unavailable: ' + diagnostic)
    }
    const stop = async () => { child.kill('SIGTERM'); await new Promise<void>(resolve => child.once('exit', () => resolve())) }
    await launch()
    try { await use({ url, restart: async () => { await stop(); await launch() } }) }
    finally { await stop(); await rm(directory, { recursive: true, force: true }) }
  },
})

test.beforeEach(async ({ page, backend }) => {
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.route('**/api/**', route => route.fulfill({ status: 404, json: { detail: 'Outside disposable Templates fixture' } }))
  await page.route('**/api/v1/templates**', async route => {
    const url = new URL(route.request().url())
    const response = await route.fetch({ url: backend.url + url.pathname + url.search, timeout: 120000 })
    await route.fulfill({ response })
  })
})

test('opens the built-in Landing template through its exact version route', async ({ page }) => {
  test.setTimeout(120000)
  await page.goto('/?page=templates')
  await page.locator('.template-filter').getByRole('button', { name: 'Landing', exact: true }).click()
  const cards = page.locator('.template-gallery .template-card')
  await expect(cards).toHaveCount(2, { timeout: 30000 })
  const card = cards.filter({ hasText: 'Project landing' })
  await expect(card).toHaveCount(1, { timeout: 30000 })
  await expect(card).toContainText('Project landing')
  const detailResponse = page.waitForResponse(response =>
    response.url().includes('/api/v1/templates/landing/project_landing/versions/5?sha256=')
      && response.request().method() === 'GET',
  )
  await card.getByRole('button', { name: 'Open template' }).click()
  const response = await detailResponse
  expect(response.status()).toBe(200)
  expect(await response.json()).toMatchObject({
    surface: 'landing', template_id: 'project_landing', template_version: 5, builtin: true,
  })
  await expect(page.locator('.template-detail')).toContainText('Project landing · v5')
  await expect(page.getByRole('button', { name: 'Edit template' })).toBeEnabled()
})

test('failed draft preview survives restart and resumes without being hidden', async ({ page, backend }) => {
  test.setTimeout(120000)
  await page.goto('/?page=templates')
  await expect(page.getByRole('heading', { name: 'Drafts' })).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.template-draft-card img')).toHaveCount(1)
  await expect(page.locator('.template-draft-card')).toContainText('Failed')
  await backend.restart()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Drafts' })).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.template-draft-card img')).toHaveCount(1)
  await page.getByRole('button', { name: 'Review next action' }).click()
  await expect(page.locator('.template-run')).toBeFocused()
  await expect(page.locator('.template-run')).toBeInViewport()
  await expect(page.getByRole('button', { name: 'Accept template version' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Continue saved changes' }).click()
  await expect(page.getByRole('button', { name: 'Accept template version' })).toBeEnabled({ timeout: 60000 })
  await page.goto('/?page=templates')
  await page.getByRole('button', { name: 'Open for review' }).click()
  await expect(page.locator('.template-run')).toBeFocused()
  await expect(page.locator('.template-run')).toBeInViewport()
  await expect(page.getByText('Check the preview. Accepting creates an immutable version and makes it available in Projects.')).toBeVisible()
  await page.getByRole('button', { name: 'Accept template version' }).click()
  await expect(page.getByRole('heading', { name: 'Drafts' })).toHaveCount(0)
  await expect(page.locator('.template-gallery .template-card')).toHaveCount(4)
})

test('authoritative gallery, all three scopes, immutable review and restart', async ({ page, backend }, info) => {
  test.setTimeout(120000)
  await page.goto('/?page=templates')
  await expect(page.getByRole('heading', { name: 'Templates', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Phone & metrics' })).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.template-gallery img')).toHaveCount(3)
  await expect(page.locator('.project-switcher')).toHaveCount(0)
  await expect(page.locator('.template-gallery img').first()).toHaveJSProperty('complete', true)
  await page.screenshot({ path: info.outputPath('templates-gallery.png'), fullPage: true })
  await page.locator('.template-filter').getByRole('button', { name: 'Landing', exact: true }).click()
  await expect(page.locator('.template-card')).toHaveCount(2)
  await page.getByRole('button', { name: 'All templates' }).click()
  for (const scope of ['post', 'landing', 'combined']) {
    await page.getByRole('button', { name: 'Create Template Agent', exact: true }).click()
    await page.getByLabel('Creation scope').selectOption(scope)
    await page.getByLabel('Design instruction').fill('A clear title, a large image, and a lower action')
    if (scope === 'combined') await page.getByLabel('Visual references (up to 2)').setInputFiles({ name: 'reference.png', mimeType: 'image/png', buffer: await page.locator('.template-gallery img').first().screenshot() })
    await page.getByRole('button', { name: 'Start creation' }).click()
    await expect(page.getByRole('button', { name: 'Accept template version' })).toBeEnabled({ timeout: 30000 })
    await expect(page.getByText('No unresolved visual differences reported.')).toBeVisible()
    await expect(page.locator('input[type=file]')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (scope === 'combined') await page.screenshot({ path: info.outputPath('templates-compared.png'), fullPage: true })
    await page.getByRole('button', { name: 'Accept template version' }).click()
    await expect(page.locator('.template-run-status')).toContainText('Accepted')
  }
  const location = page.url()
  await backend.restart()
  await page.reload()
  await expect(page.locator('.template-run-status')).toContainText('Accepted')
  expect(page.url()).toBe(location)
  await page.getByRole('button', { name: 'Open post · v1' }).click()
  await expect(page.getByText('Immutable registered version')).toBeVisible()
  await page.getByRole('button', { name: 'Edit template' }).click()
  await page.getByLabel('Design instruction').fill('Move the CTA lower')
  await page.getByRole('button', { name: 'Start creation' }).click()
  await expect(page.getByRole('button', { name: 'Accept template version' })).toBeEnabled({ timeout: 30000 })
  await page.getByRole('button', { name: 'Accept template version' }).click()
  await expect(page.getByRole('button', { name: 'Open post · v2' })).toBeVisible()
})

test('gallery transport failure offers retry and references can be removed', async ({ page }) => {
  let fail = true
  await page.route('**/api/v1/templates', async route => {
    if (fail) { return route.fulfill({ status: 503, json: { detail: 'Gallery temporarily unavailable' } }) }
    await route.fallback()
  })
  await page.goto('/?page=templates')
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible()
  fail = false
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Phone & metrics' })).toBeVisible({ timeout: 30000 })
  await page.getByRole('button', { name: 'Create Template Agent', exact: true }).click()
  await page.getByLabel('Visual references (up to 2)').setInputFiles({ name: 'reference-with-long-name-for-small-viewports.png', mimeType: 'image/png', buffer: await page.locator('.template-gallery img').first().screenshot() })
  await expect(page.getByRole('button', { name: 'Start creation' })).toBeEnabled()
  await page.getByRole('button', { name: 'Remove' }).click()
  await expect(page.getByRole('button', { name: 'Start creation' })).toBeDisabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('two SVG assets are rasterized, ordered, and passed to the Template Agent', async ({ page }) => {
  test.setTimeout(120000)
  await page.goto('/?page=templates')
  await page.getByRole('button', { name: 'Create Template Agent', exact: true }).click()
  const first = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90"><defs><linearGradient id="a"><stop stop-color="#000"/><stop offset="1" stop-color="#444"/></linearGradient></defs><rect width="120" height="90" fill="url(#a)"/></svg>'
  const second = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90"><style>.badge{fill:#222}</style><path class="badge" d="M0 0h120v90H0z"/></svg>'
  await page.getByLabel('Visual references (up to 2)').setInputFiles({ name: 'unsafe.svg', mimeType: 'image/svg+xml', buffer: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90"><script>alert(1)</script></svg>') })
  await page.getByLabel('Design instruction').fill('Inspect the attachment')
  await page.getByRole('button', { name: 'Start creation' }).click()
  await expect(page.getByRole('alert')).toContainText('SVG contains unsupported content.')
  await page.getByRole('button', { name: 'Remove' }).click()
  await page.getByLabel('Visual references (up to 2)').setInputFiles([
    { name: 'apple.svg', mimeType: 'image/svg+xml', buffer: Buffer.from(first) },
    { name: 'google.svg', mimeType: 'image/svg+xml', buffer: Buffer.from(second) },
  ])
  await expect(page.locator('.template-reference-file')).toHaveCount(2)
  await page.getByLabel('Design instruction').fill('Use the two attached badge shapes as visual guidance')
  const uploads: string[] = []
  page.on('request', request => { if (request.url().endsWith('/api/v1/templates/references') && request.method() === 'POST') uploads.push(request.postDataJSON().image.mime_type) })
  await page.getByRole('button', { name: 'Start creation' }).click()
  await expect(page.getByRole('button', { name: 'Accept template version' })).toBeEnabled({ timeout: 60000 })
  expect(uploads).toEqual(['image/png', 'image/png'])
  await expect(page.locator('.template-run')).toBeVisible()
  await expect(page.locator('.template-workspace-preview img')).toHaveJSProperty('complete', true)
  await expect.poll(() => page.locator('.template-workspace-preview img').evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  await page.close()
})


test('App Showcase has native desktop/mobile previews and an exact built-in identity', async ({ page }) => {
  test.setTimeout(120000)
  await page.goto('/?page=templates')
  await page.locator('.template-filter').getByRole('button', { name: 'Landing', exact: true }).click()
  const card = page.locator('.template-gallery .template-card').filter({ hasText: 'App Showcase' })
  await expect(card.locator('img')).toBeVisible({ timeout: 30000 })
  const response = page.waitForResponse(r => r.url().includes('/landing/app_showcase/versions/2?sha256='))
  await card.getByRole('button', { name: 'Open template' }).click()
  const body = await (await response).json()
  expect(body).toMatchObject({ template_id: 'app_showcase', template_version: 2, builtin: true })
  expect(Object.keys(body.previews)).toEqual(expect.arrayContaining(['desktop', 'mobile']))
  await expect(page.locator('.template-detail')).toContainText('App Showcase · v2')
})
