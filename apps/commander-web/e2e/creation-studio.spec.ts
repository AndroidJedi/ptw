import { expect, test as base } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

const test = base.extend<{ backend: { url: string; restart: () => Promise<void> } }>({
  backend: async ({}, use, info) => {
    const directory = await mkdtemp(resolve(tmpdir(), 'ptw-creation-browser-'))
    const url = `http://127.0.0.1:${43380 + info.workerIndex}`
    let child: ChildProcess
    const launch = async () => {
      child = spawn(process.env.PTW_E2E_PYTHON || '../../.venv/bin/python', ['../../scripts/creation_browser_canary.py', '--port', String(43380 + info.workerIndex), '--directory', directory], { stdio: 'pipe' })
      let diagnostic = ''; child.stderr?.on('data', data => { diagnostic += data.toString() })
      for (let i = 0; i < 80; i++) {
        if (child.exitCode !== null) throw Error(diagnostic)
        if (await fetch(url+'/healthz').then(r => r.ok).catch(() => false)) return
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      throw Error(diagnostic)
    }
    const stop = async () => { if (child.exitCode !== null) return; const done = new Promise<void>(resolve => child.once('exit', () => resolve())); child.kill('SIGTERM'); await done }
    await launch()
    try { await use({ url, restart: async () => { await stop(); await launch() } }) }
    finally { await stop(); await rm(directory, { recursive: true, force: true }) }
  },
})
test.beforeEach(async ({ page, backend }) => {
  await page.addInitScript(() => { if (!localStorage.getItem('ptw-owner-language-v1')) localStorage.setItem('ptw-owner-language-v1', 'en') })
  await page.route('**/api/**', route => route.fulfill({ status: 404, json: { detail: 'Outside disposable Creation fixture' } }))
  await page.route('**/api/v1/create/**', async route => {
    try { const url = new URL(route.request().url()); const response = await route.fetch({ url: backend.url + url.pathname, timeout: 60000 }); await route.fulfill({ response }) }
    catch { if (!page.isClosed()) await route.fulfill({ status: 503, json: { detail: 'Fixture restarting' } }) }
  })
})

test('one input creates a real draft package, restores it and edits only through the agent', async ({ page, backend }, info) => {
  test.setTimeout(90000)
  await page.goto('/?page=create')
  await expect(page.getByRole('heading', { name: 'Your next idea starts here.' })).toBeVisible()
  await page.getByLabel('What would you like to create?').fill('A calm focus planner for independent professionals')
  await page.getByRole('button', { name: 'Create with agent', exact: true }).click()
  await expect(page.getByText('Draft ready', { exact: true })).toBeVisible({ timeout: 45000 })
  await expect(page.locator('.creation-preview img')).toHaveCount(2)
  await expect(page.locator('.creation-preview img').first()).toHaveJSProperty('naturalWidth', 1080)
  await page.getByRole('button', { name: 'Mobile', exact: true }).click()
  await expect(page.locator('.creation-preview.landing img')).toHaveJSProperty('naturalWidth', 360)
  await page.screenshot({ path: info.outputPath('natal-studio-package.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await backend.restart(); await page.reload()
  await expect(page.getByText('Draft ready', { exact: true })).toBeVisible({ timeout: 20000 })
  await page.getByRole('button', { name: 'Ask agent to edit Brief' }).click()
  await page.getByLabel('Message to agent').fill('Emphasize calmer focus')
  await page.getByRole('button', { name: 'Send edit', exact: true }).click()
  await expect(page.getByText('Calm focus planner', { exact: true })).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('Draft ready', { exact: true })).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.creation-brief input, .creation-brief textarea')).toHaveCount(0)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download package' }).click()
  expect((await download).suggestedFilename()).toBe('natal-studio.zip')
})

test('reference input, collapsed sections and saved templates stay on the same page', async ({ page }, info) => {
  test.setTimeout(90000)
  await page.goto('/?page=create')
  await page.getByRole('button', { name: 'Reusable templates', exact: true }).click()
  await page.getByLabel('What would you like to create?').fill('A clear editorial Natal template with rounded panels')
  await page.locator('.creation-reference > summary').click()
  await expect(page.getByLabel('Website link')).toBeVisible()
  await page.getByLabel('Upload reference image').setInputFiles('../../natal/assets/logo-natal.png')
  await page.getByRole('button', { name: 'Remove reference', exact: true }).click()
  await page.getByRole('button', { name: 'Create with agent', exact: true }).click()
  await expect(page.getByText('Draft ready', { exact: true })).toBeVisible({ timeout: 40000 })
  await page.getByRole('button', { name: 'Save to Templates' }).click()
  await expect(page.getByRole('button', { name: 'Saved in Templates' })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: 'New creation', exact: true }).click()
  await page.getByRole('button', { name: 'Brief + Post + Landing', exact: true }).click()
  await expect(page.getByLabel('Design', { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('natal-studio-input.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test('a timed out design explains recovery and continues without replacing the Brief', async ({ page, backend }, info) => {
  test.setTimeout(90000)
  await page.goto('/?page=create')
  await page.getByLabel('What would you like to create?').fill('A calm focus planner [design timeout]')
  await page.getByRole('button', { name: 'Create with agent', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Design generation timed out' })).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('Your Brief is saved. Continuing will keep it.', { exact: true })).toBeVisible()
  await expect(page.getByText('The design needs another agent pass.', { exact: false })).toHaveCount(0)
  const id = new URL(page.url()).searchParams.get('creation')
  const read = () => fetch(`${backend.url}/api/v1/create/runs/${id}`, { headers: { Authorization: 'Bearer e2e-owner-token', 'X-Firebase-AppCheck': 'e2e-app-check' } }).then(r => r.json())
  const before = await read()
  await page.locator('.creation-agent > summary').click()
  await page.getByRole('button', { name: 'Describe a change', exact: true }).click()
  await expect(page.getByLabel('Message to agent')).toBeFocused()
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'uk'))
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Час очікування дизайну минув' })).toBeVisible()
  await page.screenshot({ path: info.outputPath('natal-studio-timeout-recovery.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.getByRole('button', { name: 'Продовжити створення', exact: true }).click()
  await expect(page.getByText('Чернетка готова', { exact: true })).toBeVisible({ timeout: 45000 })
  const after = await read()
  expect(after.brief).toEqual(before.brief)
  expect(after.template_run_id).toEqual(before.template_run_id)
  await expect(page.locator('.creation-preview img')).toHaveCount(2)
})
