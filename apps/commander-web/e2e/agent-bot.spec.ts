import { expect, test } from '@playwright/test'

const conversation = { id: 'conversation-1', title: 'Research an idea', status: 'idle' }
const agents = [
  { id: 'commander', name: 'Commander', role: 'Coordinator', description: 'Coordinates.' },
  { id: 'business_researcher', name: 'Business Researcher', role: 'Specialist', description: 'Researches.' },
]
const permissions = [
  { agent_id: 'business_researcher', capability: 'research', mode: 'allowed', reason: 'Can research.' },
  { agent_id: 'business_researcher', capability: 'system_expansion', mode: 'denied', reason: 'Cannot expand.' },
]

test('Commander Bot keeps three agent workspace panes usable across desktop and mobile', async ({ page }, testInfo) => {
  let detail: { conversation: typeof conversation; messages: Array<Record<string, unknown>>; tasks: unknown[]; actions: unknown[]; agents: typeof agents; permissions: typeof permissions } = { conversation, messages: [], tasks: [], actions: [], agents, permissions }
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    if (url.pathname === '/api/v1/agent-bot/conversations' && method === 'POST') {
      return route.fulfill({ json: { conversation } })
    }
    if (url.pathname.endsWith('/messages') && method === 'POST') {
      const body = route.request().postDataJSON()
      detail = { ...detail, messages: [{ id: 'message-1', sender: 'user', recipient: 'commander', kind: 'user_input', text: body.message, data: {} }] }
      return route.fulfill({ json: detail })
    }
    if (url.pathname.endsWith('/conversations/conversation-1')) return route.fulfill({ json: detail })
    if (url.pathname === '/api/v1/agent-bot') return route.fulfill({ json: { available: true, agents, permissions, conversations: [] } })
    return route.fulfill({ status: 404, json: { detail: 'not found' } })
  })
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.goto('/?e2e=1&page=agent-bot')

  await expect(page.getByRole('complementary', { name: 'Agents pane' })).toBeVisible()
  await expect(page.getByText('Pane 02 · Hub-and-spoke')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Task and permissions pane' })).toBeVisible()
  await expect(page.getByText('Commander')).toBeVisible()
  await expect(page.getByText('Business Researcher')).toBeVisible()
  await expect(page.getByText('The registered workers in this session.')).toBeVisible()

  const layout = page.locator('.agent-bot-layout')
  const columns = await layout.evaluate(node => getComputedStyle(node).gridTemplateColumns.trim().split(/\s+/).length)
  if (testInfo.project.name === 'desktop') expect(columns).toBe(3)
  else expect(columns).toBe(1)

  await page.getByLabel('Message Commander Bot').fill('A service for family meal planning')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('A service for family meal planning', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: `.local/agent-bot-${testInfo.project.name}.png`, fullPage: true })
})
