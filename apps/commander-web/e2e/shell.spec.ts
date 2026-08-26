import { expect, test } from '@playwright/test'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const sourceId = '018f07ea-7f20-7000-8000-000000000002'
const briefId = '018f07ea-7f20-7000-8000-000000000003'
const kitId = '018f07ea-7f20-7000-8000-000000000004'
const runId = '018f07ea-7f20-7000-8000-000000000005'
const creativeId = '018f07ea-7f20-7000-8000-000000000006'

const briefDocument = {
  schema_version: 1, language: 'en', product: 'Guided first therapy session',
  target_audience: 'People seeking a low-risk first step into therapy.',
  main_pain: 'Finding trustworthy support feels difficult and high commitment.',
  promise: 'Meet a suitable psychologist with a calmer first step.',
  key_benefits: ['Real consultant profiles', 'Simple booking', 'No-card first step'],
  cta: 'Book the first conversation', trust_strategy: 'Transparent process and real profiles.',
  offer: 'First consultation free',
}

const project = {
  project_id: projectId, request_id: projectId, owner_idea_source_id: sourceId,
  name: briefDocument.product, name_source: 'product_brief', requested_by: 'firebase:owner',
  result_creation_enabled: true, latest_brief_id: briefId, latest_brief_status: 'completed',
  brief_count: 1, result_run_count: 1,
  created_at: '2026-08-26T08:00:00Z', updated_at: '2026-08-26T08:05:00Z',
}

const brief = {
  brief_id: briefId, project_id: projectId, project_name: project.name,
  request_id: briefId, owner_idea_source_id: sourceId,
  raw_idea: 'A calmer way to start therapy.', base_brief_id: null, feedback_id: null,
  status: 'completed', document: briefDocument, document_sha256: 'b'.repeat(64),
  failure_count: 0, approved: true, created_at: '2026-08-26T08:00:00Z',
  ...briefDocument,
}

const run = {
  run_id: runId, request_id: runId, parent_run_id: null, project_id: projectId,
  brief_id: briefId, output_profile: 'marketing_copy_v1',
  task: 'Write a concise post connecting hesitation to a safe first step.',
  status: 'completed', current_stage: 'completed', progress_percent: 100,
  maximum_minutes: 45, final_result_id: creativeId,
  created_at: '2026-08-26T08:10:00Z', updated_at: '2026-08-26T08:14:00Z',
}

const result = {
  creative_id: creativeId, run_id: runId, selected_candidate_id: runId,
  recipe_id: null, render_id: null,
  decision_summary: [
    'The hook starts with a concrete moment of hesitation.',
    'The offer and next step remain immediately clear.',
  ],
  result_sha256: 'c'.repeat(64), content_sha256: 'd'.repeat(64), asset_url: null,
  created_at: '2026-08-26T08:14:00Z',
  content: {
    hook: 'You do not need to commit to therapy to start one honest conversation.',
    headline: 'A calmer first step', primary_text: 'Meet a real psychologist and see whether it feels right.',
    supporting_text: 'Transparent profiles. Simple booking. No card required.',
    offer: briefDocument.offer, cta: briefDocument.cta,
    caption: 'One conversation can make the next step clearer.',
    alt_text: '', desired_emotion: 'calm confidence', visual_concept: '',
  },
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })
    if (url.pathname === '/api/v1/projects') return json({ items: [project], next_cursor: null })
    if (url.pathname === '/api/v1/briefs') return json({ items: [brief], next_cursor: null })
    if (url.pathname === `/api/v1/briefs/${briefId}`) return json(brief)
    if (url.pathname === '/api/v1/project-assets') return json({ items: [] })
    if (url.pathname === '/api/v1/project-brand-kits') return json({ items: [{
      brand_kit_id: kitId, project_id: projectId,
      document: { name: project.name, colors: ['#111111', '#FFFFFF'], fonts: ['Inter'], tone_notes: 'Direct' },
      document_sha256: 'e'.repeat(64), created_at: '2026-08-26T08:05:00Z',
    }] })
    if (url.pathname === '/api/v1/content-runs' && method === 'GET') return json({ items: [run], next_cursor: null })
    if (url.pathname === `/api/v1/content-runs/${runId}`) return json(run)
    if (url.pathname === `/api/v1/content-runs/${runId}/result`) return json(result)
    if (url.pathname.endsWith('/feedback') || url.pathname.endsWith('/outcomes')) return json({ status: 'recorded' })
    return json({ detail: `Unhandled ${method} ${url.pathname}` }, 404)
  })
})

test('shows only Product Brief and one final Result workspace', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByRole('button', { name: 'Product Briefs' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Result' }).first()).toBeVisible()
  await expect(page.getByText('Ad Studio')).toHaveCount(0)
  await expect(page.getByText('Ads', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Landing', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'Result' }).first().click()
  await expect(page.getByRole('heading', { name: 'Result' })).toBeVisible()
  await expect(page.getByText(result.content.hook)).toBeVisible()
  await expect(page.getByText('WHY THIS DIRECTION')).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})
