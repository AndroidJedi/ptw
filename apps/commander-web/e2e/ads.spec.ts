import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'

const projectId = '11111111-1111-4111-8111-111111111111'
const approvedPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxRcbAAAAABJRU5ErkJggg==', 'base64')
const approvedPngSha256 = createHash('sha256').update(approvedPng).digest('hex')

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
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
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

test('shows the exact Meta app Live action for a Creative-stage stop', async ({ page }) => {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (value: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/v1/projects') return json({ items: [{
      project_id: projectId, request_id: projectId, owner_idea_source_id: projectId,
      name: 'Natal idea', name_source: 'owner', requested_by: 'owner', brief_count: 1,
      created_at: '', updated_at: '',
    }] })
    if (path.endsWith('/versions/2/render')) return route.fulfill({
      contentType: 'image/png', body: approvedPng,
    })
    if (path === `/api/v1/ads/projects/${projectId}`) return json({
      schema: 'ptw.meta-ads.workspace.v1', project_id: projectId, project_name: 'Natal idea',
      connection: {
        configured: true, verified: true, graph_version: 'v26.0',
        account: { id: 'act_123', name: 'Local Ads', currency: 'UAH', minimum_daily_budget_minor: 4491 },
        page: { id: '456', name: 'Natal' }, instagram: { id: '789', username: 'natal' },
        pixel: { id: '101', name: 'Natal Website' },
      },
      presets: [{
        preset_id: '33333333-3333-4333-8333-333333333333', version: 2,
        specification_sha256: 'b'.repeat(64), created_at: '',
        specification: {
          schema: 'ptw.meta-ads.preset.v2', name: 'Kyiv', countries: ['UA'],
          age_min: 25, age_max: 55, gender: 'all', daily_budget_minor: 5000,
          publisher_platforms: ['instagram'], instagram_positions: ['stream'], location_types: ['home'],
        },
      }],
      sources: [{
        creative_id: '22222222-2222-4222-8222-222222222222', creative_ordinal: 1,
        template_id: 'universal_ad', version: 2, version_sha256: 'a'.repeat(64),
        render_sha256: approvedPngSha256, change_note: 'Approved',
        defaults: { headline: 'Natal headline', primary_text: 'Guidance', welcome_message: 'Hello' },
      }],
      landing: {
        publication_id: 'landing', event_id: 'event', landing_version: 1,
        landing_version_sha256: 'd'.repeat(64), canonical_url: 'https://natal-service.com/la/example',
      },
      experiment: null, ads_manager_url: 'https://adsmanager.facebook.com/test',
      deployments: [{
        deployment_id: '55555555-5555-4555-8555-555555555555', request_id: '44444444-4444-4444-8444-444444444444',
        project_id: projectId, source_creative_id: '22222222-2222-4222-8222-222222222222', source_version: 2,
        render_sha256: approvedPngSha256, status: 'failed', meta_campaign_id: 'campaign-1',
        meta_ad_set_id: 'adset-1', meta_image_hash: 'image-hash', created_at: '', updated_at: '',
        specification: {
          destination_type: 'WEBSITE', headline: 'Natal headline', primary_text: 'Guidance',
          special_ad_categories: ['NONE'], landing: { canonical_url: 'https://natal-service.com/la/example' },
          preset: {
            schema: 'ptw.meta-ads.preset.v2', name: 'Kyiv', countries: ['UA'], age_min: 25,
            age_max: 55, gender: 'all', daily_budget_minor: 5000,
            publisher_platforms: ['instagram'], instagram_positions: ['stream'], location_types: ['home'],
          },
        },
        error: { error_message: 'Meta adcreatives reconciliation failed. Check the Meta connection and retry from Ads. (http=400, code=100)', provider_context: { http_status: 400, code: '100', transient: false } },
      }],
    })
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' })
  })

  await page.goto(`/?e2e=1&page=ads&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await expect(page.getByText('Creation stopped at Creative. Nothing was activated.').first()).toBeVisible()
  await expect(page.getByText(/saved error came from the former Creative lookup/)).toBeVisible()
  await expect(page.getByText(/PTW Local Ads is still in Development mode/)).toBeVisible()
  await expect(page.getByRole('link', { name: /Open Meta app dashboard/ })).toHaveAttribute('href', 'https://developers.facebook.com/apps/')
  await expect(page.getByRole('button', { name: 'App is Live — retry this deployment once' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry safely' })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
