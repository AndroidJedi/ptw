import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const sourceId = '018f07ea-7f20-7000-8000-000000000002'
const briefId = '018f07ea-7f20-7000-8000-000000000003'
const runId = '018f07ea-7f20-7000-8000-000000000005'
const creativeId = '018f07ea-7f20-7000-8000-000000000006'
const candidateIds = Array.from({ length: 5 }, (_value, index) =>
  `018f07ea-7f20-7000-8000-${String(index + 10).padStart(12, '0')}`,
)
const candidateBytes = Buffer.from([0xff, 0xd8, 0xff, 0xd9])
const candidateSha256 = createHash('sha256').update(candidateBytes).digest('hex')

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
  brief_id: briefId, output_profile: 'instagram_static_ad_v1',
  task: 'Create one ready-to-publish Instagram feed post using Natal.',
  status: 'completed', current_stage: 'completed', progress_percent: 100,
  maximum_minutes: 45, final_result_id: creativeId,
  created_at: '2026-08-26T08:10:00Z', updated_at: '2026-08-26T08:14:00Z',
}

const result = {
  creative_id: creativeId, run_id: runId, selected_candidate_id: candidateIds[0],
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

const candidates = candidateIds.map((candidateId, index) => ({
  candidate_id: candidateId, alias: `C${index + 1}`, round: 0, generation_kind: 'initial',
  parent_candidate_id: null,
  template_id: ['moment_tension', 'contrast_reframe', 'mechanism_proof', 'human_story', 'direct_offer'][index],
  template_version: 1,
  parameters: {
    hook_pressure: 50 + index, emotional_intensity: 40 + index,
    conceptual_novelty: 60 + index, information_density: 30 + index,
    visual_complexity: 20 + index,
  },
  document: {
    hook: `Candidate hook ${index + 1}`, headline: `Candidate headline ${index + 1}`,
    primary_text: 'One clear message.', supporting_text: 'One supporting point.',
    offer: briefDocument.offer, cta: briefDocument.cta, caption: 'Caption',
    alt_text: `Candidate preview ${index + 1}`, desired_emotion: 'calm confidence',
    visual_concept: 'One coherent layout.',
  },
  preview: {
    asset_url: `/api/v1/content-runs/${runId}/candidates/${candidateId}/asset`,
    sha256: candidateSha256, mime_type: 'image/jpeg', width: 1080, height: 1080,
  },
}))

const criticPass = (passNumber: 1 | 2 | 3, ranking: string[]) => ({
  pass_id: `pass-${passNumber}`, pass_number: passNumber, active_candidate_ids: ranking,
  hard_gates: Object.fromEntries(ranking.map((id) => [id, {
    exact_offer_cta: true, honest_claims: true, safe_crop_layout: true,
  }])),
  element_scores: {},
  candidate_scores: Object.fromEntries(ranking.map((id, index) => [id, {
    scores: { message_clarity: 10 - index }, complexity: 'none',
    weighted_total: 92 - index, eligible: true, reason_codes: ['clear_message'],
  }])),
  ranking,
  pairwise_results: [{
    left: ranking[0], right: ranking[1], winner: ranking[0], reason_codes: ['clearer'],
  }],
  observations: [`Pass ${passNumber} retained the clearest direction.`],
  actions: passNumber < 3 ? [{
    action_type: 'regenerate_elements', base_candidate_id: ranking[0], status: 'completed',
  }] : [],
  final_selection: passNumber === 3 ? {
    candidate_id: ranking[0], decision_summary: result.decision_summary,
  } : null,
})

const debug = {
  candidates,
  critic_passes: [
    criticPass(1, candidateIds), criticPass(2, candidateIds.slice(0, 3)),
    criticPass(3, candidateIds.slice(0, 2)),
  ],
  result,
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
    if (url.pathname === '/api/v1/content-runs' && method === 'GET') return json({ items: [run], next_cursor: null })
    if (url.pathname === `/api/v1/content-runs/${runId}`) return json(run)
    if (url.pathname === `/api/v1/content-runs/${runId}/result`) return json(result)
    if (url.pathname === `/api/v1/content-runs/${runId}/debug`) return json(debug)
    if (url.pathname.includes(`/api/v1/content-runs/${runId}/candidates/`) && url.pathname.endsWith('/asset')) {
      return route.fulfill({
        status: 200,
        contentType: 'image/jpeg',
        headers: { ETag: `"${candidateSha256}"`, 'Cache-Control': 'private, no-store' },
        body: candidateBytes,
      })
    }
    if (url.pathname.endsWith('/feedback') || url.pathname.endsWith('/outcomes')) return json({ status: 'recorded' })
    return json({ detail: `Unhandled ${method} ${url.pathname}` }, 404)
  })
})

test('shows only Product Brief and one-click Instagram post workspace', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByRole('button', { name: 'Продуктові брифи' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByRole('button', { name: 'Product Briefs' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Instagram post' }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Product Briefs' }).first()).toBeVisible()
  await expect(page.getByText('Ad Studio')).toHaveCount(0)
  await expect(page.getByText('Ads', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Landing', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'Instagram post' }).first().click()
  await expect(page.getByRole('heading', { name: 'Instagram post' })).toBeVisible()
  await expect(page.getByText('Natal branding is applied automatically. Nothing else is required.')).toBeVisible()
  await expect(page.getByLabel('Task')).toHaveCount(0)
  await expect(page.getByRole('radio', { name: 'Text' })).toHaveCount(0)
  await expect(page.getByText('PROJECT BRAND KIT')).toHaveCount(0)
  await expect(page.getByText(result.content.hook)).toBeVisible()
  await expect(page.getByText('WHY THIS DIRECTION')).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('separates new Project creation from the selected Project workspace', async ({ page }) => {
  await page.goto('/?e2e=1')
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByText('BRIEF HISTORY')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toHaveCount(0)

  await page.getByRole('button', { name: 'New Project' }).click()
  await expect(page.getByRole('heading', { name: 'New Project' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toBeVisible()
  await expect(page.getByText('BRIEF HISTORY')).toHaveCount(0)

  await page.getByLabel('Existing Project').selectOption(projectId)
  await expect(page.getByText('BRIEF HISTORY')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toHaveCount(0)
})

test('shows five candidate layouts, parameters, and the visual decision path', async ({ page }) => {
  await page.goto('/?e2e=1')
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await page.getByRole('button', { name: 'Instagram post' }).first().click()
  await page.getByText('See all five directions and the decision').click()

  await expect(page.getByRole('heading', { name: 'Every image and its exact generation parameters' })).toBeVisible()
  await expect(page.locator('.candidate-card')).toHaveCount(5)
  await expect(page.locator('.candidate-image-wrap img')).toHaveCount(5)
  await expect(page.getByText('Hook pressure')).toHaveCount(5)
  await expect(page.getByRole('heading', { name: 'Screen all five' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Compare improvements' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Choose the finalist' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Selected C1' })).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})
