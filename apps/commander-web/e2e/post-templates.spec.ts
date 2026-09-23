import { expect, test } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

test('apply accepted layout to an existing Post, edit, approve and restore after restart', async ({ page }, info) => {
  test.setTimeout(120000)
  page.setDefaultTimeout(15000)
  const directory = await mkdtemp(resolve(tmpdir(), 'ptw-template-browser-'))
  const port = 43480 + info.workerIndex
  const url = `http://127.0.0.1:${port}`
  const headers = { Authorization: 'Bearer e2e-owner-token', 'X-Firebase-AppCheck': 'e2e-app-check' }
  let child: ChildProcess
  let diagnostic = ''
  const launch = async () => {
    const python = process.env.PTW_E2E_PYTHON || (existsSync('../../.venv/bin/python') ? '../../.venv/bin/python' : 'python3')
    child = spawn(python, ['../../scripts/template_browser_canary.py', '--port', String(port), '--directory', directory, '--project-post'], { stdio: 'pipe' })
    diagnostic = ''
    child.stderr?.on('data', value => { diagnostic += value.toString() })
    for (let attempt = 0; attempt < 250; attempt++) {
      if (child.exitCode !== null) throw Error(diagnostic)
      if (await fetch(url + '/healthz').then(r => r.ok).catch(() => false)) return
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    throw Error('Fixture did not start: ' + diagnostic)
  }
  const stop = async () => { child.kill('SIGTERM'); await new Promise<void>(resolve => child.once('exit', () => resolve())) }
  try {
    await launch()
    const ids = await fetch(url + '/fixture', { headers }).then(r => r.json())
    await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
    await page.route('**/api/**', async route => {
      const request = new URL(route.request().url())
      const response = await route.fetch({ url: url + request.pathname + request.search, timeout: 120000 })
      await route.fulfill({ response })
    })
    await page.goto(`/?e2e=1&page=posts&project=${ids.project_id}&creative=${ids.creative_id}`)
    await expect(page.getByRole('button', { name: 'Change template' })).toBeEnabled({ timeout: 30000 })
    await expect(page.locator('.phone-metrics-canvas-panel img')).toBeVisible()
    await page.screenshot({ path: info.outputPath('post-compact.png'), fullPage: true })
    await page.getByRole('button', { name: 'Change template' }).click()
    const dialog = page.getByRole('dialog', { name: 'Change template' })
    await expect(dialog.locator('.post-template-choices article')).toHaveCount(2, { timeout: 30000 })
    await dialog.locator('.post-template-choices article').filter({ hasNotText: 'Phone & metrics' }).getByRole('button').click()
    await page.screenshot({ path: info.outputPath('post-choose-template.png'), fullPage: true })
    await dialog.getByRole('button', { name: 'Apply to this Post' }).click()
    await expect(dialog).not.toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('heading', { name: 'Post text', exact: true })).toBeVisible()
    await page.getByRole('textbox', { name: 'Headline 1', exact: true }).fill('Owner edited headline')
    await page.getByRole('button', { name: 'Update preview' }).click()
    await expect(page.getByText('Preview up to date', { exact: true })).toBeVisible({ timeout: 15000 })
    await page.getByRole('button', { name: 'Save creative' }).click()
    await expect(page.getByText('Creative saved with an edit checkpoint.', { exact: true })).toBeVisible({ timeout: 15000 })
    const approval = page.waitForResponse(response => response.url().endsWith('/approve') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Approve creative' }).click()
    expect((await approval).ok(), diagnostic).toBeTruthy()
    await expect(page.getByRole('button', { name: 'Approve creative' })).toBeEnabled({ timeout: 15000 })
    const path = `/api/v1/studio/projects/${ids.project_id}/creatives/${ids.creative_id}`
    const before = await fetch(url + path, { headers }).then(r => r.json())
    expect(before.versions).toHaveLength(1)
    expect(before.content.template_text.title).toBe('Owner edited headline')
    await stop(); await launch(); await page.reload()
    await expect(page.getByRole('textbox', { name: 'Headline 1', exact: true })).toHaveValue('Owner edited headline')
    await expect(page.locator('.phone-metrics-canvas-panel img')).toBeVisible()
    const after = await fetch(url + path, { headers }).then(r => r.json())
    expect(after.template_reference).toEqual(before.template_reference)
    expect(after.versions).toEqual(before.versions)
    expect(after.phone_screen_history).toEqual(before.phone_screen_history)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath('post-applied-template.png'), fullPage: true })
  } finally { if (child! && child.exitCode === null) await stop(); await rm(directory, { recursive: true, force: true }) }
})
