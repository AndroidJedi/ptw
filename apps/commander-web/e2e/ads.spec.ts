import { expect, test } from '@playwright/test'

const projectId = '11111111-1111-4111-8111-111111111111'

test('renders the project Ads safety and configuration states without horizontal overflow', async ({ page }) => {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (value: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/v1/projects') return json({ items: [{
      project_id: projectId, request_id: projectId, owner_idea_source_id: projectId,
      name: 'Natal idea', name_source: 'owner', requested_by: 'owner', brief_count: 1,
      created_at: '', updated_at: '',
    }] })
    if (path === `/api/v1/ads/projects/${projectId}`) return json({
      schema: 'ptw.meta-ads.workspace.v1', project_id: projectId, project_name: 'Natal idea',
      connection: {
        configured: false, verified: false, graph_version: 'v26.0',
        explanation: 'Add the Meta system-user token and assigned asset IDs to the local secrets file.',
        required_permissions: ['ads_management', 'ads_read'],
      },
      presets: [], sources: [], experiment: null, deployments: [], ads_manager_url: null,
    })
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' })
  })
  await page.goto(`/?e2e=1&page=ads&project=${projectId}`)
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByRole('heading', { name: 'Ads', exact: true })).toBeVisible()
  await expect(page.getByText('PAUSED ONLY')).toBeVisible()
  await expect(page.getByText('Meta staging disabled')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What is still needed' })).toBeVisible()
  await expect(page.getByRole('link', { name: /System users/ })).toHaveAttribute('href', 'https://business.facebook.com/settings/system-users')
  await expect(page.getByRole('link', { name: 'Open Post Studio' })).toHaveAttribute('href', `?page=posts&project=${projectId}`)
  await expect(page.getByRole('button', { name: 'New preset' })).toBeVisible()
  await page.getByRole('button', { name: 'New preset' }).click()
  await page.getByLabel('Geography').selectOption('cities')
  await expect(page.getByLabel('Search city in Meta')).toHaveValue('Kyiv')
  await expect(page.getByRole('button', { name: 'Search Meta' })).toBeDisabled()
  await expect(page.getByText(/Connect and verify Meta first/)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
