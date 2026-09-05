import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const sourceId = '018f07ea-7f20-7000-8000-000000000002'
const briefId = '018f07ea-7f20-7000-8000-000000000003'
const creativeId = '018f07ea-7f20-7000-8000-000000000004'
const studioBasePath = `/api/v1/studio/projects/${projectId}/creatives/${creativeId}`
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
  ['logo', ['logo'], ['logo']],
].map(([role, nodeIds, assetSlotIds]) => ({
  component_id: `universal_ad.${role}`, role, node_ids: nodeIds,
  asset_slot_ids: assetSlotIds, setting_ids: [],
}))

const studioDetail = {
  creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
  ordinal: 1, origin: 'brief_generation', status: 'draft', approved_version_count: 0,
  template_id: 'universal_ad', generation: { stage: 'draft' },
  schema: 'ptw.studio.workspace.v8',
  catalog: {
    schema: 'ptw.studio.universal-ad-catalog.v7', template_id: 'universal_ad', template_version: 12,
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
      cta_font_size: { minimum: 18, maximum: 42, default: 27 },
      sticker_positions: ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'right_edge', 'bottom_edge', 'bullet_list', 'hero_title', 'cta'],
      font_families: ['Inter', 'Roboto Condensed', 'Manrope', 'Montserrat', 'Source Sans 3', 'Oswald', 'Cormorant Garamond', 'Cormorant Garamond Italic', 'Lora', 'Lora Italic'],
      optional_elements: ['sticker', 'bullet_list', 'logo'],
    },
    sha256: 'e'.repeat(64),
  },
  state_sha256: 'f'.repeat(64), template_sha256: 'a'.repeat(64),
  configuration: {
    schema: 'ptw.studio.universal-ad-config.v6',
    background: { mode: 'solid', color: '#F0E653', texture: 'stone', texture_intensity: 0.7, image_layout: 'full', image_percent: 75, image_fit: 'cover', focal_x: 0.5, focal_y: 0.5, overlay_color: '#000000', overlay_opacity: 0 },
    typography: { font_family: 'Inter', supporting_font_family: 'Inter', offer_font_family: 'Inter', benefits_font_family: 'Manrope', hero_size: 112, hero_weight: 800, supporting_size: 34, offer_size: 28, benefits_size: 26, text_color: '#111111', alignment: 'left' },
    layout: { content_x: 76, content_y: 180, content_width: 720, gap: 24 },
    bullets: { enabled: false, style: 'circle' },
    cta: { style: 'filled', position: 'below_text', background_color: '#111111', text_color: '#FFFFFF', radius: 24, font_family: 'Inter', font_size: 27 },
    sticker: { enabled: false, position: 'top_right', rotation: -6, width: 320, object_scale: 0.82, offset_right: 0, offset_bottom: 0 },
    logo: { enabled: true, position: 'top_right', width: 180, background_enabled: false, background_color: '#FFFFFF' },
  },
  content: {
    schema: 'ptw.studio.universal-ad-content.v2', hero_title: 'PROVE THE IDEA',
    supporting_text: 'A focused offer.', offer: 'First consultation free',
    bullets: [], cta: 'TEST DEMAND',
  },
  component_settings: {
    schema: 'ptw.studio.universal-ad-component-settings.v3', template_id: 'universal_ad',
    template_version: 12, configuration_schema: 'ptw.studio.universal-ad-config.v6',
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
  latest_brief_id: briefId, latest_brief_status: 'completed', brief_count: 1,
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

test.beforeEach(async ({ page }) => {
  let currentStudio = structuredClone(studioDetail)
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })
    if (url.pathname === '/api/v1/projects') return json({ items: [project], next_cursor: null })
    if (url.pathname === '/api/v1/studio/templates' && method === 'GET') return json({ items: [
      { template_id: 'universal_ad', name: 'Universal ad', description: 'Square composition', canvas: { width: 1080, height: 1080 }, template_version: 11, template_sha256: 'a'.repeat(64) },
      { template_id: 'phone_metrics', name: 'Phone & metrics', description: 'Phone composition', canvas: { width: 1080, height: 1350 }, template_version: 17, template_sha256: 'b'.repeat(64) },
    ] })
    if (url.pathname === `/api/v1/studio/projects/${projectId}/creatives` && method === 'GET') return json({ items: [{
      creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
      ordinal: 1, origin: 'brief_generation', template_id: 'universal_ad',
      template_version: 11, template_sha256: currentStudio.template_sha256,
      status: 'draft', state_sha256: currentStudio.state_sha256,
      approved_version_count: currentStudio.versions.length, generation: { stage: 'draft' },
      created_at: '2026-08-26T08:06:00Z', updated_at: '2026-08-26T08:06:00Z',
    }], next_cursor: null })
    if (url.pathname === studioBasePath && method === 'GET') return json(currentStudio)
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
    if (url.pathname === `${studioBasePath}/preview` && method === 'POST') return route.fulfill({
      status: 200, contentType: 'image/png',
      headers: { ETag: `"${studioPreviewSha256}"`, 'X-PTW-Content-SHA256': studioPreviewSha256, 'Cache-Control': 'private, no-store' },
      body: studioPreviewBytes,
    })
    if (url.pathname === `${studioBasePath}/component-settings` && method === 'POST') {
      return json(currentStudio.component_settings)
    }
    if (url.pathname === `${studioBasePath}/configuration` && method === 'POST') {
      const body = route.request().postDataJSON()
      currentStudio = { ...currentStudio, state_sha256: '9'.repeat(64), configuration: body.configuration, content: body.content }
      return json(currentStudio)
    }
    if (url.pathname === `${studioBasePath}/save` && method === 'POST') {
      const body = route.request().postDataJSON()
      currentStudio = { ...currentStudio, state_sha256: '9'.repeat(64), configuration: body.configuration, content: body.content }
      return json({
        creative: currentStudio, checkpoint_created: true, version_created: false,
        checkpoint: {
          checkpoint_id: '018f07ea-7f20-7000-8000-000000000005',
          creative_id: creativeId, project_id: projectId, kind: 'save',
          before_state_sha256: '1'.repeat(64), after_state_sha256: '2'.repeat(64),
          changed_paths: ['content.hero_title'], status: 'completed',
          edit_summary: 'Shortened the headline and strengthened contrast.',
          project_lesson: 'Use a concise promise for this Project.',
        },
        learning_proposal: {
          proposal_id: '018f07ea-7f20-7000-8000-000000000006',
          checkpoint_id: '018f07ea-7f20-7000-8000-000000000005',
          project_skill_snapshot_id: '018f07ea-7f20-7000-8000-000000000007',
          global_rule: 'Prefer concise promises when the template has limited space.',
          global_rule_sha256: '3'.repeat(64), decision: 'pending',
        },
      })
    }
    if (url.pathname === `${studioBasePath}/approve` && method === 'POST') {
      const body = route.request().postDataJSON()
      return json({
        creative: {
          ...currentStudio, state_sha256: '8'.repeat(64),
          configuration: body.configuration, content: body.content,
          versions: [{
            version: 1, state_sha256: '8'.repeat(64),
            template_sha256: currentStudio.template_sha256,
            render_sha256: studioPreviewSha256, change_note: body.change_note,
          }],
        },
        checkpoint_created: true, version_created: true,
        checkpoint: {
          checkpoint_id: '018f07ea-7f20-7000-8000-000000000008',
          creative_id: creativeId, project_id: projectId, kind: 'approve',
          before_state_sha256: '2'.repeat(64), after_state_sha256: '4'.repeat(64),
          changed_paths: ['content.hero_title'], status: 'completed',
          edit_summary: 'Approved a more specific final headline.',
          project_lesson: 'Prefer a specific final headline for this Project.',
        },
        learning_proposal: {
          proposal_id: '018f07ea-7f20-7000-8000-000000000009',
          checkpoint_id: '018f07ea-7f20-7000-8000-000000000008',
          project_skill_snapshot_id: '018f07ea-7f20-7000-8000-000000000010',
          global_rule: 'Prefer specific final headlines before approval.',
          global_rule_sha256: '5'.repeat(64), decision: 'pending',
        },
      })
    }
    if (url.pathname.includes('/learning/') && method === 'POST') return json({ decision: route.request().postDataJSON().decision })
    if (url.pathname === `/api/v1/briefs/${briefId}/approve` && method === 'POST') return json({
      brief: { ...brief, approved: true }, approved_now: true,
      creative: { creative_id: creativeId, project_id: projectId, source_brief_id: briefId, ordinal: 1, origin: 'brief_generation', template_id: 'universal_ad', template_version: 11, template_sha256: 'a'.repeat(64), status: 'queued', state_sha256: 'f'.repeat(64), approved_version_count: 0, generation: { stage: 'queued' }, created_at: '2026-08-26T08:06:00Z', updated_at: '2026-08-26T08:06:00Z' }, creative_created: true,
    }, 202)
    if (url.pathname === '/api/v1/briefs') return json({ items: [brief], next_cursor: null })
    if (url.pathname === `/api/v1/briefs/${briefId}`) return json(brief)
    return json({ detail: `Unhandled ${method} ${url.pathname}` }, 404)
  })
})

test('approves a Brief through the required template picker and opens its creative', async ({ page }) => {
  await page.route(`**/api/v1/briefs/${briefId}`, async (route) => {
    if (route.request().method() === 'GET') return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ...brief, approved: false }),
    })
    return route.fallback()
  })
  await page.goto(`/?e2e=1&project=${projectId}`)
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await page.getByRole('button', { name: 'I can honor this promise and offer — approve' }).click()
  const picker = page.getByRole('dialog', { name: 'Choose the creative template' })
  await expect(picker).toBeVisible()
  await expect(picker.getByRole('button', { name: 'Approve Brief & generate creative' })).toBeDisabled()
  await picker.getByRole('button', { name: /Phone & metrics/ }).click()
  await picker.locator('input[value="cinematic"]').check()
  await picker.locator('input[value="scene"]').check()
  const approvalRequest = page.waitForRequest((request) => (
    request.url().endsWith(`/briefs/${briefId}/approve`) && request.method() === 'POST'
  ))
  await picker.getByRole('button', { name: 'Approve Brief & generate creative' }).click()
  expect((await approvalRequest).postDataJSON()).toEqual({
    honor_confirmed: true, template_id: 'phone_metrics',
    creative_direction: {
      schema: 'ptw.studio.phone-hero-direction.v1', style: 'cinematic', background: 'scene',
    },
  })
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('posts')
  await expect.poll(() => new URL(page.url()).searchParams.get('creative')).toBe(creativeId)
})

test('shows Product Briefs, the project-scoped Post editor, and Landing Studio', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByRole('button', { name: 'Продуктові брифи' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Змінити мову' }).click()
  await expect(page.getByRole('button', { name: 'Product Briefs' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Social posts' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Post', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Landing', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Studio' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Post', exact: true }).first().click()
  await expect(page.locator('.universal-canvas-panel')).toBeVisible()
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('posts')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Post', exact: true }).first()).toBeVisible()
  await expect(page.getByText('Ad Studio')).toHaveCount(0)
  await expect(page.getByText('Ads', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Landing', exact: true }).first().click()
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('landing')

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('opens the Post editor and persists its bounded configuration', async ({ page }) => {
  await page.goto('/?e2e=1&page=posts')
  await page.getByRole('button', { name: 'Змінити мову' }).click()

  await expect(page.getByText('ONE TEMPLATE · CONFIGURATION-FIRST')).toHaveCount(0)
  await expect(page.getByText('Universal Ad Studio')).toHaveCount(0)
  await expect(page.locator('.universal-canvas-panel')).toBeVisible()
  await expect(page.locator('.universal-controls')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Build the composition at a glance' })).toBeVisible()
  await expect(page.getByText('ALWAYS ON')).toHaveCount(5)
  await expect(page.getByLabel('Enable logo')).toHaveCount(0)
  await expect(page.getByLabel('Upload logo', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Upload sticker_object asset')).toHaveCount(0)
  await expect(page.getByText('Pexels photograph only')).toBeVisible()
  await expect(page.getByText('Preview matches the saved setup')).toBeVisible()
  await expect(page.getByText('Natal', { exact: true })).toBeVisible()
  await expect(page.getByText('Canonical brand lock-up')).toBeVisible()
  await expect(page.getByLabel('Show logo', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Show logo background')).toHaveCount(0)
  await expect(page.getByLabel('Logo position')).toHaveCount(0)
  await expect(page.getByLabel('Logo width')).toHaveCount(0)
  await expect(page.getByAltText('Current universal advertising creative')).toBeVisible()
  await expect(page.getByText('Reference image')).toHaveCount(0)
  await expect(page.getByText('Primitive tree')).toHaveCount(0)
  await page.getByText('Mood and contrast').click()
  await page.getByLabel('Background mode').selectOption('image')
  await expect(page.getByLabel('Upload sample background image')).toBeVisible()
  await expect(page.getByLabel('Background color', { exact: true })).toHaveValue('#f0e653')

  const draftPreviewRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/preview')) return false
    const body = request.postDataJSON()
    return body?.configuration?.bullets?.enabled === true
  })
  await page.getByLabel('Enable bullets').check()
  const draftRequest = await draftPreviewRequest
  expect(draftRequest.postDataJSON().configuration.bullets.enabled).toBe(true)
  await expect(page.getByText('Live preview up to date')).toBeVisible()

  const configurationRequest = page.waitForRequest((request) =>
    request.url().endsWith('/save'),
  )
  const editedPreviewRequest = page.waitForRequest((request) => {
    if (!request.url().endsWith('/preview')) return false
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
  await page.getByLabel('Headline font family', { exact: true }).selectOption('Oswald')
  await page.getByLabel('Benefits font family').selectOption('Cormorant Garamond')
  await page.getByLabel('CTA style').selectOption('gradient')
  await page.getByLabel('CTA placement').selectOption('bottom_right')
  await expect(page.getByLabel('CTA background color')).toHaveValue('#111111')
  await expect(page.getByLabel('CTA text color')).toHaveValue('#ffffff')
  const editedPreview = await editedPreviewRequest
  expect(editedPreview.postDataJSON().content.hero_title).toBe('TEST A CLEAR PROMISE')
  await expect(page.getByText('Preview matches your unsaved changes')).toBeVisible()
  await page.getByRole('button', { name: 'Save creative' }).click()
  const request = await configurationRequest
  expect(request.postDataJSON().configuration.background.mode).toBe('texture')
  expect(request.postDataJSON().configuration.background.texture).toBe('stone')
  expect(request.postDataJSON().configuration.cta.style).toBe('gradient')
  expect(request.postDataJSON().configuration.cta.position).toBe('bottom_right')
  expect(request.postDataJSON().configuration.typography.font_family).toBe('Oswald')
  expect(request.postDataJSON().configuration.typography.benefits_font_family).toBe('Cormorant Garamond')
  expect(request.postDataJSON().content.hero_title).toBe('TEST A CLEAR PROMISE')
  const learning = page.getByRole('alertdialog', { name: 'Project skill updated' })
  await expect(learning).toBeVisible()
  await expect(learning).toContainText('Shortened the headline and strengthened contrast.')
  await expect(learning).toContainText('Use a concise promise for this Project.')
  await expect(learning).toContainText('Prefer concise promises when the template has limited space.')
  await learning.getByRole('button', { name: 'Keep project-only' }).click()
  await expect(page.getByRole('status')).toContainText('lesson remains Project-only')
  const metadataRequest = page.waitForRequest((candidate) =>
    candidate.url().endsWith('/component-settings'),
  )
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export config + IDs' }).click()
  expect((await metadataRequest).postDataJSON().configuration.cta.style).toBe('gradient')
  expect((await download).suggestedFilename()).toBe('universal_ad_configuration.json')
  await expect(page.getByRole('status')).toContainText('component ID metadata exported')

  await page.getByLabel('Hero Title').fill('A SPECIFIC FINAL PROMISE')
  await page.getByLabel('Version note').fill('Owner-approved first creative')
  const approvalRequest = page.waitForRequest((candidate) => candidate.url().endsWith('/approve'))
  await page.getByRole('button', { name: 'Approve creative' }).click()
  const approval = await approvalRequest
  expect(approval.postDataJSON()).toMatchObject({
    content: { hero_title: 'A SPECIFIC FINAL PROMISE' },
    change_note: 'Owner-approved first creative',
  })
  const approvalLearning = page.getByRole('alertdialog', { name: 'Project skill updated' })
  await expect(approvalLearning).toContainText('Approved a more specific final headline.')
  await approvalLearning.getByRole('button', { name: 'Apply globally' }).click()
  await expect(page.getByRole('status')).toContainText('global Studio skill')
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('live previews every bounded sticker placement control', async ({ page }) => {
  await page.route(`**${studioBasePath}`, async (route) => {
    const request = route.request()
    if (new URL(request.url()).pathname !== studioBasePath || request.method() !== 'GET') {
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
          source: {
            origin: 'pexels', provider: 'pexels', media_type: 'photograph',
            subject_type: 'physical_object', transformation: 'edge_color_soft_alpha_v1',
          },
        } : asset),
      }),
    })
  })
  await page.goto('/?e2e=1&page=posts')

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
      if (!response.url().endsWith('/preview') || response.status() !== 200) return false
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
  await page.goto('/?e2e=1&page=posts')
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
