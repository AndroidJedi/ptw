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
const studioPreviewBytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
const studioPreviewSha256 = createHash('sha256').update(studioPreviewBytes).digest('hex')
const studioComponents = [
  ['background', ['canvas', 'background_media', 'readability_overlay'], ['background_image']],
  ['sticker', ['sticker_object'], ['sticker_object']],
  ['hero_title', ['hero_title'], []],
  ['supporting_text', ['supporting_text'], []],
  ['offer', ['offer'], []],
  ['bullet_list', ['bullet_marker_1', 'bullet_1', 'bullet_marker_2', 'bullet_2', 'bullet_marker_3', 'bullet_3'], []],
  ['cta', ['cta'], []],
  ['logo', ['logo_surface', 'logo'], ['logo']],
].map(([role, nodeIds, assetSlotIds]) => ({
  component_id: `universal_ad.${role}`, role, node_ids: nodeIds,
  asset_slot_ids: assetSlotIds, setting_ids: [],
}))

const studioDetail = {
  schema: 'ptw.studio.universal-ad-workspace.v5',
  catalog: {
    schema: 'ptw.studio.universal-ad-catalog.v4', template_id: 'universal_ad', template_version: 9,
    semantic_roles: ['background', 'sticker', 'hero_title', 'supporting_text', 'offer', 'bullet_list', 'cta', 'logo'],
    components: studioComponents,
    asset_slots: {},
    variation: {
      background_modes: ['solid', 'texture', 'image'], image_layouts: ['full', 'left', 'right', 'top', 'bottom'],
      image_percents: [25, 75],
      texture_presets: ['grain', 'stone', 'marble', 'concrete', 'granite', 'slate', 'travertine'],
      bullet_styles: ['check', 'circle', 'circle_outline'],
      cta_styles: ['filled', 'gradient', 'reverse', 'link', 'outlined'],
      cta_positions: ['below_text', 'bottom_left', 'bottom_right'],
      sticker_positions: ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'right_edge', 'bottom_edge', 'bullet_list', 'hero_title', 'cta'],
      font_families: ['Inter', 'Manrope', 'Oswald', 'Cormorant Garamond'],
      optional_elements: ['sticker', 'bullet_list', 'logo'],
    },
    sha256: 'e'.repeat(64),
  },
  state_sha256: 'f'.repeat(64), template_sha256: 'a'.repeat(64),
  configuration: {
    schema: 'ptw.studio.universal-ad-config.v4',
    background: { mode: 'solid', color: '#F0E653', texture: 'stone', texture_intensity: 0.7, image_layout: 'full', image_percent: 75, image_fit: 'cover', focal_x: 0.5, focal_y: 0.5, overlay_color: '#000000', overlay_opacity: 0 },
    typography: { font_family: 'Inter', benefits_font_family: 'Manrope', hero_size: 112, hero_weight: 800, supporting_size: 34, text_color: '#111111', alignment: 'left' },
    layout: { content_x: 76, content_y: 180, content_width: 720, gap: 24 },
    bullets: { enabled: false, style: 'circle' },
    cta: { style: 'filled', position: 'below_text', background_color: '#111111', text_color: '#FFFFFF', radius: 24 },
    sticker: { enabled: false, position: 'top_right', rotation: -6, width: 320, object_scale: 0.82, offset_right: 0, offset_bottom: 0 },
    logo: { enabled: true, position: 'top_right', width: 180, background_enabled: true, background_color: '#FFFFFF' },
  },
  content: {
    schema: 'ptw.studio.universal-ad-content.v2', hero_title: 'PROVE THE IDEA',
    supporting_text: 'A focused offer.', offer: 'First consultation free',
    bullets: [], cta: 'TEST DEMAND',
  },
  component_settings: {
    schema: 'ptw.studio.universal-ad-component-settings.v2', template_id: 'universal_ad',
    template_version: 9, configuration_schema: 'ptw.studio.universal-ad-config.v4',
    components: studioComponents.map(({ setting_ids: _settingIds, ...component }) => ({
      ...component, settings: [],
    })),
    sha256: '9'.repeat(64),
  },
  assets: [
    { slot: 'background_image', role: 'background', description: 'Background', allowed_mime_types: ['image/jpeg', 'image/png', 'image/webp'], available: false, mime_type: null, sha256: null, byte_count: null, source: null },
    { slot: 'sticker_object', role: 'sticker', description: 'Sticker', allowed_mime_types: ['image/png', 'image/webp'], available: false, mime_type: null, sha256: null, byte_count: null, source: null },
    { slot: 'logo', role: 'logo', description: 'Logo', allowed_mime_types: ['image/png', 'image/webp'], available: true, mime_type: 'image/png', sha256: 'c'.repeat(64), byte_count: 2937, source: { origin: 'canonical_natal_brand_asset', filename: 'logo-natal.png' } },
  ],
  pexels_available: false, versions: [],
}

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
  brief_id: briefId, output_profile: 'instagram_static_ad_v1', platform: 'instagram',
  task: 'Create one ready-to-publish Instagram feed post using Natal.',
  status: 'completed', current_stage: 'completed', progress_percent: 100,
  maximum_minutes: 45, final_result_id: creativeId,
  review_state: 'unreviewed', revision_number: 0,
  created_at: '2026-08-26T08:10:00Z', updated_at: '2026-08-26T08:14:00Z',
}

const result = {
  creative_id: creativeId, run_id: runId, selected_candidate_id: candidateIds[0],
  recipe_id: null, render_id: null,
  decision_summary: [
    'The hook starts with a concrete moment of hesitation.',
    'The offer and next step remain immediately clear.',
  ],
  result_sha256: 'c'.repeat(64), content_sha256: 'd'.repeat(64),
  asset_url: `/api/v1/content-runs/${runId}/result/asset`, asset_sha256: candidateSha256,
  asset_mime_type: 'image/jpeg', asset_width: 1080, asset_height: 1080,
  created_at: '2026-08-26T08:14:00Z',
  content: {
    hook: 'You do not need to commit to therapy to start one honest conversation.',
    headline: 'A calmer first step', primary_text: 'Meet a real psychologist and see whether it feels right.',
    supporting_text: 'Transparent profiles. Simple booking. No card required.',
    offer: briefDocument.offer, cta: briefDocument.cta,
    caption: 'One conversation can make the next step clearer.',
    alt_text: 'A calm square therapy post with one clear next step.',
    desired_emotion: 'calm confidence', visual_concept: '',
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
    if (url.pathname === `/api/v1/projects/${projectId}/assets`) return json({ items: [] })
    if (url.pathname === '/api/v1/learning-summary') return json({
      schema: 'ptw.local-learning-summary.v1', market_performance: false,
      runs: [], lesson_queue: [], approved_lessons: [],
    })
    if (url.pathname === '/api/v1/studio' && method === 'GET') return json(studioDetail)
    if (url.pathname === '/api/v1/studio/tune' && method === 'GET') return json({
      schema: 'ptw.studio.tune-service.v1', mode: 'local_only', available: true,
      unavailable_reason: null, active_run_id: null, allowed_paths: [], runs: [],
    })
    if (url.pathname === '/api/v1/studio/tune-runs' && method === 'POST') {
      const body = route.request().postDataJSON()
      return json({
        schema: 'ptw.studio.tune-run.v1', run_id: '11111111-1111-4111-8111-111111111111',
        iteration: 1, status: 'completed', stage: 'completed', ...body,
        request_sha256: '8'.repeat(64),
        changed_files: ['apps/commander-web/src/views/StudioView.tsx'],
        verification: ['Studio web unit tests', 'Owner Console production build'],
        summary: 'Added the requested Studio test implementation.', error: null,
        preview: { mime_type: 'image/png', sha256: studioPreviewSha256, width: 1080, height: 1080 },
        created_at: '2026-08-29T10:00:00Z', updated_at: '2026-08-29T10:01:00Z',
        started_at: '2026-08-29T10:00:00Z', completed_at: '2026-08-29T10:01:00Z',
      }, 202)
    }
    if (url.pathname === '/api/v1/studio/tune-runs/11111111-1111-4111-8111-111111111111/preview' && method === 'GET') return route.fulfill({
      status: 200, contentType: 'image/png',
      headers: { ETag: `"${studioPreviewSha256}"`, 'Cache-Control': 'private, no-store' },
      body: studioPreviewBytes,
    })
    if (url.pathname === '/api/v1/studio/tune-runs/11111111-1111-4111-8111-111111111111/rules' && method === 'POST') {
      const body = route.request().postDataJSON()
      return json({
        schema: 'ptw.studio.tune-rule-approval.v1',
        run_id: '11111111-1111-4111-8111-111111111111',
        rule: body.rule,
        rule_sha256: '7'.repeat(64),
        skill_path: 'skills/studio-tune-local/references/owner-approved-rules.md',
        created: true,
      })
    }
    if (url.pathname === '/api/v1/studio/preview' && method === 'POST') return route.fulfill({
      status: 200, contentType: 'image/png',
      headers: { ETag: `"${studioPreviewSha256}"`, 'X-PTW-Content-SHA256': studioPreviewSha256, 'Cache-Control': 'private, no-store' },
      body: studioPreviewBytes,
    })
    if (url.pathname === '/api/v1/studio/component-settings' && method === 'POST') {
      return json(studioDetail.component_settings)
    }
    if (url.pathname === '/api/v1/studio/configuration' && method === 'POST') {
      const body = route.request().postDataJSON()
      return json({ ...studioDetail, state_sha256: '9'.repeat(64), configuration: body.configuration, content: body.content })
    }
    if (url.pathname === '/api/v1/briefs') return json({ items: [brief], next_cursor: null })
    if (url.pathname === `/api/v1/briefs/${briefId}`) return json(brief)
    if (url.pathname === '/api/v1/content-runs' && method === 'GET') return json({ items: [run], next_cursor: null })
    if (url.pathname === `/api/v1/content-runs/${runId}`) return json(run)
    if (url.pathname === `/api/v1/content-runs/${runId}/result`) return json(result)
    if (url.pathname === `/api/v1/content-runs/${runId}/result/asset`) return route.fulfill({
      status: 200,
      contentType: 'image/jpeg',
      headers: { ETag: `"${candidateSha256}"`, 'Cache-Control': 'private, no-store' },
      body: candidateBytes,
    })
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

test('shows Product Brief, Social Posts, and Universal Ad Studio workspaces', async ({ page }, testInfo) => {
  await page.goto('/?e2e=1')
  await expect(page.getByRole('button', { name: 'Продуктові брифи' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByRole('button', { name: 'Product Briefs' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Social posts' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Studio' }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Product Briefs' }).first()).toBeVisible()
  await expect(page.getByText('Ad Studio')).toHaveCount(0)
  await expect(page.getByText('Ads', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Landing', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'Social posts' }).first().click()
  await expect(page.getByRole('heading', { name: 'Social posts' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => Object.fromEntries(
    new URLSearchParams(window.location.search),
  ))).toMatchObject({ page: 'result', project: projectId, run: runId })
  await expect(page.getByLabel('Task')).toHaveCount(0)
  await expect(page.getByRole('radio', { name: 'Text' })).toHaveCount(0)
  await expect(page.getByText('PROJECT BRAND KIT')).toHaveCount(0)
  await expect(page.getByRole('article', { name: 'instagram post preview' })).toBeVisible()
  await expect(page.getByText(result.content.caption)).toBeVisible()
  await expect(page.getByText(result.content.hook)).toHaveCount(0)
  await expect(page.getByText(result.content.headline)).toHaveCount(0)
  await expect(page.getByText('WHY THIS DIRECTION')).toHaveCount(0)
  await expect(page.getByText('SOURCE', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Learning & evidence' })).toBeVisible()
  await expect(page.getByText('Internal evaluation only — never a market-performance claim.')).toBeVisible()
  if (testInfo.project.name === 'desktop') {
    await expect(page.getByLabel('Projects and artifacts')).toBeVisible()
  } else {
    await expect(page.getByLabel('Projects and artifacts')).toBeHidden()
    await page.getByRole('button', { name: 'Projects and artifacts' }).click()
    await expect(page.getByLabel('Projects and artifacts')).toBeVisible()
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('opens the Universal Ad Studio and persists its bounded configuration', async ({ page }) => {
  await page.goto('/?e2e=1&page=studio')
  await page.getByRole('button', { name: 'Змінити мову' }).click()

  await expect(page.getByText('ONE TEMPLATE · CONFIGURATION-FIRST')).toHaveCount(0)
  await expect(page.getByText('Universal Ad Studio')).toHaveCount(0)
  await expect(page.locator('.universal-canvas-panel')).toBeVisible()
  await expect(page.locator('.universal-controls')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Build the composition at a glance' })).toBeVisible()
  await expect(page.getByText('ALWAYS ON')).toHaveCount(5)
  await expect(page.getByLabel('Enable logo')).toBeChecked()
  await expect(page.getByLabel('Upload logo', { exact: true })).toBeEnabled()
  const logoOffPreviewRequest = page.waitForRequest((candidate) => {
    if (!candidate.url().endsWith('/api/v1/studio/preview')) return false
    return candidate.postDataJSON()?.configuration?.logo?.enabled === false
  })
  await page.getByLabel('Enable logo').uncheck()
  await logoOffPreviewRequest
  await expect(page.getByText('Live preview up to date')).toBeVisible()
  const logoOnPreviewRequest = page.waitForRequest((candidate) => {
    if (!candidate.url().endsWith('/api/v1/studio/preview')) return false
    const body = candidate.postDataJSON()
    return body?.state_sha256 === 'f'.repeat(64) && body?.configuration === undefined
  })
  await page.getByLabel('Enable logo').check()
  await logoOnPreviewRequest
  await expect(page.getByLabel('Enable logo')).toBeChecked()
  await expect(page.getByText('Preview matches the saved setup')).toBeVisible()
  await page.getByText('Brand mark and background').click()
  await expect(page.getByText('image/png · canonical_natal_brand_asset', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Show logo', { exact: true })).toBeChecked()
  await expect(page.getByLabel('Show logo background')).toBeChecked()
  await expect(page.getByLabel('Logo position')).toHaveValue('top_right')
  await expect(page.getByLabel('Logo width')).toHaveValue('180')
  const logoPreviewRequest = page.waitForRequest((candidate) => {
    if (!candidate.url().endsWith('/api/v1/studio/preview')) return false
    const body = candidate.postDataJSON()
    return body?.configuration?.logo?.background_enabled === false
      && body?.configuration?.logo?.position === 'top_left'
  })
  await page.getByLabel('Show logo background').uncheck()
  await page.getByLabel('Logo position').selectOption('top_left')
  expect((await logoPreviewRequest).postDataJSON().configuration.logo.enabled).toBe(true)
  await expect(page.getByAltText('Current universal advertising creative')).toBeVisible()
  await expect(page.getByText('Reference image')).toHaveCount(0)
  await expect(page.getByText('Primitive tree')).toHaveCount(0)
  await page.getByText('Mood and contrast').click()
  await page.getByLabel('Background mode').selectOption('image')
  await expect(page.getByLabel('Upload sample background image')).toBeVisible()
  await expect(page.getByLabel('Background color', { exact: true })).toHaveValue('#f0e653')

  const draftPreviewRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/api/v1/studio/preview')) return false
    const body = request.postDataJSON()
    return body?.configuration?.bullets?.enabled === true
  })
  await page.getByLabel('Enable bullets').check()
  const draftRequest = await draftPreviewRequest
  expect(draftRequest.postDataJSON().configuration.bullets.enabled).toBe(true)
  await expect(page.getByText('Live preview up to date')).toBeVisible()

  const configurationRequest = page.waitForRequest((request) =>
    request.url().endsWith('/api/v1/studio/configuration'),
  )
  const editedPreviewRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/api/v1/studio/preview')) return false
    const body = request.postDataJSON()
    return body?.configuration?.background?.mode === 'texture'
      && body?.configuration?.background?.texture === 'stone'
      && body?.configuration?.background?.texture_intensity === 0.9
      && body?.configuration?.background?.overlay_opacity === 0.2
      && body?.configuration?.cta?.style === 'gradient'
      && body?.configuration?.cta?.position === 'bottom_right'
      && body?.configuration?.typography?.font_family === 'Oswald'
      && body?.configuration?.typography?.benefits_font_family === 'Cormorant Garamond'
      && body?.content?.hero_title === 'TEST A CLEAR PROMISE'
  })
  await page.getByLabel('Hero Title').fill('TEST A CLEAR PROMISE')
  await page.getByLabel('Background mode').selectOption('texture')
  await page.getByLabel('Texture', { exact: true }).selectOption('stone')
  for (let index = 0; index < 4; index += 1) await page.getByLabel('Texture intensity', { exact: true }).press('ArrowRight')
  for (let index = 0; index < 4; index += 1) await page.getByLabel('Overlay opacity').press('ArrowRight')
  await page.getByText('Type, layout and action').click()
  await page.getByLabel('Font family', { exact: true }).selectOption('Oswald')
  await page.getByLabel('Benefits font family').selectOption('Cormorant Garamond')
  await page.getByLabel('CTA style').selectOption('gradient')
  await page.getByLabel('CTA placement').selectOption('bottom_right')
  await expect(page.getByLabel('CTA background color')).toHaveValue('#111111')
  await expect(page.getByLabel('CTA text color')).toHaveValue('#ffffff')
  const editedPreview = await editedPreviewRequest
  expect(editedPreview.postDataJSON().content.hero_title).toBe('TEST A CLEAR PROMISE')
  await expect(page.getByText('Preview matches your unsaved changes')).toBeVisible()
  await page.getByRole('button', { name: 'Save setup' }).click()
  const request = await configurationRequest
  expect(request.postDataJSON().configuration.background.mode).toBe('texture')
  expect(request.postDataJSON().configuration.background.texture).toBe('stone')
  expect(request.postDataJSON().configuration.cta.style).toBe('gradient')
  expect(request.postDataJSON().configuration.cta.position).toBe('bottom_right')
  expect(request.postDataJSON().configuration.typography.font_family).toBe('Oswald')
  expect(request.postDataJSON().configuration.typography.benefits_font_family).toBe('Cormorant Garamond')
  expect(request.postDataJSON().content.hero_title).toBe('TEST A CLEAR PROMISE')
  await expect(page.getByRole('status')).toContainText('Studio setup saved.')
  const metadataRequest = page.waitForRequest((candidate) =>
    candidate.url().endsWith('/api/v1/studio/component-settings'),
  )
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export config + IDs' }).click()
  expect((await metadataRequest).postDataJSON().configuration.cta.style).toBe('gradient')
  expect((await download).suggestedFilename()).toBe('universal_ad_configuration.json')
  await expect(page.getByRole('status')).toContainText('component ID metadata exported')
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('live previews every bounded sticker placement control', async ({ page }) => {
  await page.route('**/api/v1/studio', async (route) => {
    const request = route.request()
    if (new URL(request.url()).pathname !== '/api/v1/studio' || request.method() !== 'GET') {
      return route.fallback()
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...studioDetail,
        configuration: {
          ...studioDetail.configuration,
          sticker: { ...studioDetail.configuration.sticker, enabled: true },
        },
        assets: studioDetail.assets.map((asset) => asset.slot === 'sticker_object' ? {
          ...asset,
          available: true,
          mime_type: 'image/png',
          sha256: 'd'.repeat(64),
          byte_count: 1024,
          source: { origin: 'bundled_tune_asset' },
        } : asset),
      }),
    })
  })
  await page.goto('/?e2e=1&page=studio')

  await expect(page.getByText('Розміщення стікера', { exact: true })).toBeVisible()
  await expect(page.getByText('Розміщення стікера й логотипа', { exact: true })).toHaveCount(0)
  await page.getByText('Розміщення стікера', { exact: true }).click()

  const changes = [
    ['Sticker rotation', '7', 'rotation', 7],
    ['Sticker width', '700', 'width', 700],
    ['Object scale', '1.25', 'object_scale', 1.25],
    ['Adjust from right', '500', 'offset_right', 500],
    ['Adjust from bottom', '-240', 'offset_bottom', -240],
  ] as const
  for (const [label, inputValue, setting, expected] of changes) {
    const previewResponse = page.waitForResponse((response) => {
      if (!response.url().endsWith('/api/v1/studio/preview') || response.status() !== 200) return false
      const body = response.request().postDataJSON()
      return body?.configuration?.sticker?.[setting] === expected
    })
    await page.getByLabel(label).fill(inputValue)
    const response = await previewResponse
    expect(response.request().postDataJSON().configuration.sticker[setting]).toBe(expected)
  }
  await expect(page.getByText('Прев’ю відповідає незбереженим змінам')).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('opens the local Tune wizard and submits all three generation inputs', async ({ page }) => {
  await page.goto('/?e2e=1&page=studio')
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await page.getByRole('button', { name: 'Feedback & iterations' }).click()

  const wizard = page.getByRole('dialog', { name: 'Test generation' })
  await expect(wizard).toBeVisible()
  await wizard.getByLabel('Project idea').fill('A calm planning tool for independent founders.')
  await wizard.getByLabel('Desired implementation').fill('Use an editorial layout with one clear test action.')
  await wizard.getByLabel('Your feedback').fill('Reduce visual noise and keep the hierarchy quiet.')
  const requestPromise = page.waitForRequest((request) => request.url().endsWith('/api/v1/studio/tune-runs'))
  await wizard.getByRole('button', { name: 'Apply feedback' }).click()
  const request = await requestPromise

  expect(request.postDataJSON()).toEqual({
    project_idea: 'A calm planning tool for independent founders.',
    implementation: 'Use an editorial layout with one clear test action.',
    feedback: 'Reduce visual noise and keep the hierarchy quiet.',
  })
  await expect(wizard.getByText('Verified changes applied')).toBeVisible()
  await expect(wizard.getByAltText('Generated creative for iteration 1')).toBeVisible()
  await expect(wizard.getByText('GENERATED CREATIVE · 1080×1080')).toBeVisible()
  await expect(wizard.getByText('Iteration report')).toBeVisible()
  await expect(wizard.getByText('Added the requested Studio test implementation.')).toBeHidden()
  await wizard.getByText('Iteration report').click()
  await expect(wizard.getByText('Added the requested Studio test implementation.')).toBeVisible()
  await expect(wizard.getByRole('button', { name: 'Back to Studio' })).toBeVisible()

  const followup = 'Remove the paper and use a thick white Apple-style sticker outline.'
  await wizard.getByLabel('Feedback for next iteration').fill(followup)
  const ruleRequestPromise = page.waitForRequest((candidate) => candidate.url().endsWith('/rules'))
  await wizard.getByRole('button', { name: 'Save as reusable rule' }).click()
  const ruleRequest = await ruleRequestPromise
  expect(ruleRequest.postDataJSON()).toEqual({ rule: followup })
  await expect(wizard.getByText('Saved as a reusable rule for future Tune runs.')).toBeVisible()
  await expect(wizard.getByRole('button', { name: 'Reusable rule saved' })).toBeDisabled()
  const followupRequestPromise = page.waitForRequest((candidate) =>
    candidate.url().endsWith('/api/v1/studio/tune-runs'),
  )
  await wizard.getByRole('button', { name: 'Apply feedback' }).click()
  const followupRequest = await followupRequestPromise
  expect(followupRequest.postDataJSON()).toEqual({
    project_idea: 'A calm planning tool for independent founders.',
    implementation: 'Use an editorial layout with one clear test action.',
    feedback: followup,
  })
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('separates new Project creation from the selected Project workspace', async ({ page }) => {
  await page.goto('/?e2e=1')
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toHaveCount(0)

  await page.getByRole('button', { name: 'New Project' }).click()
  await expect(page.getByRole('heading', { name: 'New Project' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toBeVisible()
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toHaveCount(0)

  await page.getByLabel('Existing Project').selectOption(projectId)
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toHaveCount(0)
})

test('keeps candidate parameters and the decision path in collapsed advanced details', async ({ page }) => {
  await page.goto('/?e2e=1')
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await page.getByRole('button', { name: 'Social posts' }).first().click()
  await page.getByText('Export details and decision trace').click()

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
