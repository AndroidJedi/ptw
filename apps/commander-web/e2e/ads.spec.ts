import { expect, test, type Page } from '@playwright/test'

const projectId = '11111111-1111-4111-8111-111111111111'
const testId = '22222222-2222-4222-8222-222222222222'
const landingUrl = 'https://natal-service.com/ai/idea'
const sources = [1, 2].map(ordinal => ({
  creative_id: `${ordinal}1111111-1111-4111-8111-111111111111`, creative_ordinal: ordinal,
  template_id: 'phone_metrics', version: 1, version_id: `${ordinal}2222222-2222-4222-8222-222222222222`,
  version_sha256: String(ordinal).repeat(64), render_sha256: String(ordinal + 2).repeat(64),
  change_note: `Approved ${ordinal}`, defaults: {
    headline: `Idea ${ordinal}`, primary_text: 'Support\n\nOffer',
    instagram_caption: `Idea ${ordinal}\n\nSupport\n\nOffer`, welcome_message: '',
  },
}))

function workspace(withTest = false) {
  return {
    schema: 'ptw.instagram-validation.workspace.v1', project_id: projectId, project_name: 'Idea',
    sources, landing: {
      publication_id: '33333333-3333-4333-8333-333333333333',
      event_id: '44444444-4444-4444-8444-444444444444', landing_version: 1,
      landing_version_sha256: 'a'.repeat(64), canonical_url: landingUrl,
    },
    ads_manager_url: 'https://adsmanager.facebook.com/adsmanager/manage/campaigns',
    tests: withTest ? [{
      test_id: testId, name: 'Two Posts', state: 'active', total_budget_minor: 5000,
      daily_budget_minor: 1000, currency: 'USD', duration_days: 5,
      campaign_name: 'PTW-test', ad_set_name: 'PTW-test-ADSET',
      current_leader_arm_id: '51111111-1111-4111-8111-111111111111', imports: [],
      arms: sources.map((source, index) => ({
        arm_id: `${index + 5}1111111-1111-4111-8111-111111111111`, ordinal: index + 1,
        source_creative_id: source.creative_id, source_version: 1,
        ad_name: `PTW-test-AD-0${index + 1}`, headline: source.defaults.headline,
        primary_text: `${source.defaults.instagram_caption}\n\n${landingUrl}?ptw_attribution=token${index}`,
        tracked_url: `${landingUrl}?ptw_attribution=token${index}`,
        paid: { spend_minor: (index + 1) * 1000, landing_page_views: index + 2 },
        funnel: { landing_view: index + 2, primary_cta_click: index + 1, contact_click: index },
        cost_per_primary_cta_minor: (index + 1) * 500,
      })),
    }] : [],
  }
}

async function installRoutes(page: Page, withTest = false) {
  const requests: Array<{ path: string; body: Record<string, unknown> }> = []
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const json = (value: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/v1/projects') return json({ items: [{
      project_id: projectId, request_id: projectId, owner_idea_source_id: projectId,
      name: 'Idea', name_source: 'owner', requested_by: 'owner', brief_count: 1,
      created_at: '', updated_at: '',
    }] })
    if (path === `/api/v1/instagram-tests/projects/${projectId}`) return json(workspace(withTest))
    if (request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      requests.push({ path, body })
      if (path.endsWith('/imports/preview')) return json({
        csv_sha256: 'b'.repeat(64), headers: ['Ad name', 'Amount spent (USD)'],
        mapping: { ad_name: 'Ad name', spend: 'Amount spent (USD)', impressions: null, link_clicks: null, landing_page_views: null },
        matched_rows: [{ row: 2, ad_name: 'PTW-test-AD-01', matched_arm_id: '51111111-1111-4111-8111-111111111111' }],
        ignored_rows: [], can_import: true,
      })
      return json({ created: true })
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' })
  })
  return requests
}

test('prepares an exact manual Instagram campaign without horizontal overflow', async ({ page }) => {
  const requests = await installRoutes(page)
  await page.goto(`/?e2e=1&page=ads&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()

  await expect(page.getByRole('heading', { name: 'Instagram tests' })).toBeVisible()
  await expect(page.getByText('FAST IDEA VALIDATION')).toBeVisible()
  await expect(page.getByText(/Do not use “Boost post”/)).toBeVisible()
  await expect(page.getByText('Instagram Feed only')).toBeVisible()
  await page.getByRole('button', { name: /Post 1 · v1/ }).click()
  await page.getByRole('button', { name: /Post 2 · v1/ }).click()
  await page.getByLabel('Test name').fill('Fast validation')
  await page.getByRole('button', { name: 'Prepare launch kit' }).click()

  await expect(page.getByRole('status')).toContainText('Launch kit prepared')
  await expect.poll(() => requests.find(item => item.path.endsWith('/tests'))).toBeTruthy()
  const created = requests.find(item => item.path.endsWith('/tests'))!
  expect(created.body).toMatchObject({
    name: 'Fast validation', total_budget_minor: 5000, currency: 'USD', duration_days: 5,
    arms: sources.map(source => ({ creative_id: source.creative_id, version: 1 })),
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('previews manual CSV results and requires confirmation before completion', async ({ page }) => {
  const requests = await installRoutes(page, true)
  await page.goto(`/?e2e=1&page=ads&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()

  await expect(page.getByText('ACTIVE · PTW-test')).toBeVisible()
  await expect(page.getByText('Current leader: AD-01')).toBeVisible()
  await expect(page.getByText(/informational only/)).toBeVisible()
  await page.getByLabel('Meta Ads Manager CSV').setInputFiles({
    name: 'results.csv', mimeType: 'text/csv',
    buffer: Buffer.from('Ad name,Amount spent (USD)\nPTW-test-AD-01,10'),
  })
  await expect(page.getByText('Matched: 1 · Ignored: 0')).toBeVisible()
  await page.getByRole('button', { name: 'Import results' }).click()
  await expect.poll(() => requests.some(item => item.path.endsWith('/imports'))).toBe(true)

  page.once('dialog', dialog => void dialog.accept())
  await page.getByRole('button', { name: 'Stopped in Meta · complete' }).click()
  await expect.poll(() => requests.find(item => item.path.endsWith('/completed'))?.body.campaign_stopped).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
