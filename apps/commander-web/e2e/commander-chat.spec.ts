import { expect, test } from '@playwright/test'

const capabilities = { models: [{ id: 'runtime-model', name: 'Runtime model', default: true, default_effort: 'medium', efforts: ['low', 'medium', 'high'] }], modes: ['build', 'plan'] }

test('dedicated Commander supports send, reload, stop, and mobile layout', async ({ page }) => {
  const base = '/api/v1/settings/commander'
  let status = 'completed'
  let message = ''
  let attachmentName = ''
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/capabilities')) return route.fulfill({ json: capabilities })
    if (path.endsWith('/events')) return route.fulfill({ json: { cursor: 0, events: [] } })
    if (path.endsWith('/chatgpt-authorization')) return route.fulfill({ json: { status: 'authorized', test_status: null } })
    const chat = () => ({ id: 'chat-1', turns: message ? [{ id: 'turn-1', message, reply: '', status, error_code: status === 'cancelled' ? 'stopped' : null }] : [] })
    if (path === base) return route.fulfill({ json: {
      target: 'local', available: true, chats: [{ id: 'chat-1', title: 'Carousel tab' }],
      active_turn: status === 'running' ? { id: 'turn-1', chat_id: 'chat-1' } : null,
    } })
    if (path.endsWith('/messages')) {
      const body = route.request().postDataJSON()
      message = body.message
      attachmentName = body.attachments?.[0]?.name || ''
      status = 'running'
    }
    if (path.endsWith('/stop')) status = 'cancelled'
    return route.fulfill({ json: chat() })
  })
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.goto('/?e2e=1&page=commander')
  await expect(page.getByRole('heading', { name: 'Commander GOD mode' })).toBeVisible()
  await page.getByLabel('Attach images').setInputFiles({
    name: 'settings-screen.png', mimeType: 'image/png', buffer: Buffer.from('temporary screenshot'),
  })
  await expect(page.getByText('settings-screen.png')).toBeVisible()
  await page.getByLabel('Message Commander').fill('Add a carousel creation tab with slide editing')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect.poll(() => attachmentName).toBe('settings-screen.png')
  await expect(page.getByText('Working… You can reply below.')).toBeVisible()
  await page.reload()
  await expect(page.getByText(message, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Stop', exact: true }).click()
  await expect(page.getByText(/This task stopped before completion/)).toBeVisible()
  const size = await page.getByRole('button', { name: 'Send', exact: true }).boundingBox()
  expect(size!.height).toBeGreaterThanOrEqual(44)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: `.local/commander-chat-${test.info().project.name}.png`, fullPage: true })
})

test('Settings keeps authorization and persists the language selected there', async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/chatgpt-authorization/refresh')) return route.fulfill({ json: {
      status: 'authorizing', test_status: null, authorization_url: 'https://auth.openai.com/codex/device', device_code: 'ABCD-12345',
    } })
    if (path.endsWith('/chatgpt-authorization')) return route.fulfill({ json: { status: 'authorized', test_status: null } })
    return route.fulfill({ json: { target: 'local', available: true, chats: [], active_turn: null } })
  })
  await page.goto('/?e2e=1&page=settings')
  await expect(page.getByRole('heading', { name: 'ChatGPT Authorization' })).toBeVisible()
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByRole('heading', { name: 'Language', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Language', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Commander/ })).toHaveCount(0)
  await expect(page.getByRole('navigation').getByRole('button', { name: 'Change language' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Refresh authorization' }).click()
  await expect(page.getByText('ABCD-12345')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test('Commander deploys in one click without page overflow', async ({ page }) => {
  const base = '/api/v1/settings/commander'
  let deployment: Record<string, unknown> | null = null
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/capabilities')) return route.fulfill({ json: capabilities })
    if (path.endsWith('/events')) return route.fulfill({ json: { cursor: 0, events: [] } })
    if (path.endsWith('/chatgpt-authorization')) return route.fulfill({ json: { status: 'authorized', test_status: 'passed' } })
    if (path.endsWith('/deploy')) deployment = { id: 'deployment-1', status: 'queued', revision: 'b'.repeat(40) }
    if (path === `${base}/deployments`) {
      if (route.request().method() === 'POST') deployment = {
        id: 'deployment-1', base_revision: 'a'.repeat(40), revision: 'b'.repeat(40),
        branch: 'god-deploy/deployment-1', status: 'queued', error_code: null,
        workflow_url: null, updated_at: new Date().toISOString(),
      }
      return route.fulfill({ json: {
        candidate: { available: true, deployable: deployment === null, changed_files: ['apps/commander-web/src/change.tsx'], protected_files: [] },
        deployment,
      } })
    }
    if (path === base) return route.fulfill({ json: { target: 'hosted', available: true, chats: [], active_turn: null } })
    return route.fulfill({ json: { id: 'chat-1', turns: [] } })
  })
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.goto('/?e2e=1&page=commander')
  await page.getByRole('button', { name: 'Deploy', exact: true }).click()
  await expect(page.getByRole('alertdialog')).toHaveCount(0)
  await expect(page.getByText('Building, checking and deploying…')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})
