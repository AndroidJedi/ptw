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
  ['background', ['canvas'], []], ['brand', ['logo'], []],
  ['offer', ['offer'], []], ['hero_title', ['hero_title'], []],
  ['supporting_text', ['supporting_text'], []],
  ['device', ['phone_device'], ['phone_screen']],
  ['metrics', ['metric_card_1', 'metric_card_2', 'metric_card_3'], []],
  ['cta', ['cta'], []],
].map(([role, nodeIds, assetSlotIds]) => ({
  component_id: `phone_metrics.${role}`, role, node_ids: nodeIds,
  asset_slot_ids: assetSlotIds, setting_ids: [],
}))

const studioDetail = {
  creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
  ordinal: 1, origin: 'brief_generation', status: 'draft', approved_version_count: 0,
  template_id: 'phone_metrics', generation: {
    stage: 'draft', creative_direction: {
      schema: 'ptw.studio.phone-hero-direction.v1', style: 'cinematic', background: 'scene',
    },
  },
  schema: 'ptw.studio.workspace.v8',
  templates: [{
    template_id: 'phone_metrics', name: 'Phone & metrics', description: 'Phone composition',
    canvas: { width: 1080, height: 1350 }, template_version: 27,
    template_sha256: 'a'.repeat(64),
  }],
  catalog: {
    schema: 'ptw.studio.phone-metrics-catalog.v2', template_id: 'phone_metrics', template_version: 27,
    canvas: { width: 1080, height: 1350 }, semantic_roles: [], components: studioComponents,
    asset_slots: { phone_screen: { role: 'device_screen', allowed_mime_types: ['image/png'], description: 'Generated artwork' } },
    variation: {
      optional_elements: ['offer', 'post_logo', 'phone_logo', 'cta'], brand: 'Natal',
      device_pose: 'front_facing_upright', device_rotation_degrees: 0,
      background_textures: ['none', 'grain', 'concrete', 'travertine'],
      copy_background_textures: ['none', 'grain', 'concrete', 'travertine'],
      phone_screen_textures: ['none', 'grain', 'paper', 'frosted'],
      metric_card_styles: ['filled', 'outlined'], metric_card_shapes: ['square', 'rounded', 'pill'],
      phone_button_styles: ['filled', 'elevated', 'outlined', 'text'], phone_button_shapes: ['square', 'rounded', 'pill'],
      font_families: ['Inter', 'Roboto Condensed', 'Manrope', 'Montserrat', 'Source Sans 3', 'Oswald', 'Cormorant Garamond', 'Cormorant Garamond Italic', 'Lora', 'Lora Italic'],
      typography: {
        offer: { minimum: 16, maximum: 42, default: 23 }, hero_title: { minimum: 42, maximum: 110, default: 76 },
        supporting_text: { minimum: 20, maximum: 46, default: 29 }, cta: { minimum: 20, maximum: 52, default: 34 },
        metric_value: { minimum: 20, maximum: 56, default: 43 }, metric_label: { minimum: 14, maximum: 36, default: 22 },
        phone_title: { minimum: 24, maximum: 72, default: 55 }, phone_buttons: { minimum: 16, maximum: 36, default: 28 },
      },
    },
    sha256: 'e'.repeat(64),
  },
  state_sha256: 'f'.repeat(64), template_sha256: 'a'.repeat(64),
  configuration: {
    schema: 'ptw.studio.phone-metrics-config.v13', visual_mode: 'phone',
    background: { color: '#F4F5F2', texture: 'concrete', texture_intensity: 0.13 },
    copy_background: { texture: 'none' }, logo: { enabled: true, symbol_color: '#87D0DD', name_color: '#383840' },
    offer: { enabled: true }, cta: { enabled: true, background_color: '#316CFF', text_color: '#FFFFFF' },
    hero_title: { enabled: true, highlight_color: '#FF30E8' }, supporting_text: { enabled: true, highlight_color: '#1675F8' },
    typography: {
      offer: { font_family: 'Manrope', font_size: 23 }, hero_title: { font_family: 'Manrope', font_size: 76 },
      supporting_text: { font_family: 'Manrope', font_size: 29 }, cta: { font_family: 'Manrope', font_size: 34 },
      metric_value: { font_family: 'Manrope', font_size: 43 }, metric_label: { font_family: 'Manrope', font_size: 22 },
      phone_title: { font_family: 'Manrope', font_size: 55 }, phone_buttons: { font_family: 'Manrope', font_size: 28 },
    },
    phone_screen: { texture: 'grain', logo_enabled: true, title_enabled: true },
    metric_cards: [1, 2, 3].map(() => ({ enabled: true, style: 'filled', text_color: '#FFFFFF', background_color: '#2457C8', shape: 'rounded' })),
    phone_buttons: [
      { enabled: true, style: 'filled', text_color: '#FFFFFF', background_color: '#1675F8', shape: 'pill' },
      { enabled: true, style: 'elevated', text_color: '#1675F8', background_color: '#FFFFFF', shape: 'pill' },
      { enabled: true, style: 'text', text_color: '#1675F8', background_color: '#FFFFFF', shape: 'pill' },
    ],
    device: { enabled: true, x: 610, y: 90, width: 410, rotation: 0 },
  },
  content: {
    schema: 'ptw.studio.phone-metrics-content.v2', offer: 'NATAL', hero_title: 'PROVE THE IDEA',
    supporting_text: 'A focused offer.', cta: 'TEST DEMAND',
    stats: [{ value: '01', label: 'Plan' }, { value: '02', label: 'Test' }, { value: '03', label: 'Learn' }],
    phone_hero_title: 'A calmer next step', phone_buttons: ['Create account', 'Sign in', 'Maybe later'],
  },
  component_settings: {
    schema: 'ptw.studio.phone-metrics-component-settings.v3', template_id: 'phone_metrics',
    template_version: 27, configuration_schema: 'ptw.studio.phone-metrics-config.v13',
    components: studioComponents.map(({ setting_ids: _settingIds, ...component }) => ({
      ...component, settings: [],
    })),
    sha256: '9'.repeat(64),
  },
  assets: [
    { slot: 'phone_screen', role: 'device_screen', description: 'Generated artwork', allowed_mime_types: ['image/png'], editable: false, available: false, mime_type: null, sha256: null, byte_count: null, source: null },
    { slot: 'iphone_frame', role: 'device_frame', description: 'Fixed phone frame', allowed_mime_types: ['image/png'], editable: false, available: true, mime_type: 'image/png', sha256: 'b'.repeat(64), byte_count: 2937, source: { origin: 'checked_in' } },
    { slot: 'logo', role: 'brand', description: 'Natal', allowed_mime_types: ['image/png'], editable: false, available: true, mime_type: 'image/png', sha256: 'c'.repeat(64), byte_count: 2937, source: { origin: 'canonical_natal_brand_asset', filename: 'logo-natal.png' } },
  ],
  phone_screen_history: [], phone_screen_generation_available: true, versions: [],
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

function analyticsWorkspace(scope: 'project' | 'global', windowDays: number) {
  const selected = scope === 'project'
  return {
    schema: 'ptw.analytics.workspace.v1', scope,
    project_id: selected ? projectId : null, project_ids: [projectId], window_days: windowDays,
    readiness: {
      instagram: { available: true },
      tiktok: { available: false, explanation: 'Public-photo canary is not yet audited.' },
      meta: { available: true }, landing: { available: true },
    },
    organic: selected && windowDays !== 1 ? [{
      provider: 'instagram', publication_id: '018f07ea-7f20-7000-8000-000000000020',
      project_id: projectId, published_at: '2026-08-26T08:00:00Z', age_hours: 96,
      metrics: { views: 100, likes: 5, comments: 2, shares: 1, saves: 1 },
      funnel: { landing_view: 10, primary_cta_click: 3, contact_click: 2 },
      rates: { outbound_contact: 0.02, primary_cta: 0.03, high_intent: 0.04, interaction: 0.09, view_velocity_per_day: 25 },
      insight: { capture_kind: 'milestone', created_at: '2026-08-30T08:00:00Z' },
    }] : [],
    paid: [],
    landing_funnel: selected && windowDays === 1
      ? { landing_view: 2, primary_cta_click: 1, contact_click: 0, primary_cta_rate: 0.5, outbound_contact_rate: 0, surfaces: { page: 2, hero: 1 }, conversion_label: 'Outbound contact click · conversion proxy' }
      : selected
      ? { landing_view: 10, primary_cta_click: 3, contact_click: 2, primary_cta_rate: 0.3, outbound_contact_rate: 0.2, surfaces: { page: 10, hero: 3, telegram: 2 }, conversion_label: 'Outbound contact click · conversion proxy' }
      : { landing_view: 0, primary_cta_click: 0, contact_click: 0, primary_cta_rate: null, outbound_contact_rate: null, surfaces: {}, conversion_label: 'Outbound contact click · conversion proxy' },
    skills: { snapshot: null, rules: [] }, learning_runs: [], learning_curve: [],
    freshness: { instagram: selected && windowDays !== 1 ? '2026-08-30T08:00:00Z' : null, tiktok: null },
    metric_definitions: selected ? { outbound_contact_rate: { numerator: 'attributed contact_click', denominator: 'provider reach/views', source: 'PTW Landing + provider snapshot', limitation: 'conversion proxy; not a lead or sale' } } : {},
  }
}

test.beforeEach(async ({ page }) => {
  let currentStudio = structuredClone(studioDetail)
  let visibleProjects = [project]
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })
    if (url.pathname === '/api/v1/projects') return json({ items: visibleProjects, next_cursor: null })
    if (url.pathname === `/api/v1/projects/${projectId}/delete` && method === 'POST') {
      const body = route.request().postDataJSON()
      if (body.confirmation_name !== project.name || !body.request_id) return json({ detail: 'invalid confirmation' }, 400)
      visibleProjects = []
      return json({ project_id: projectId, deleted: true, deleted_at: '2026-09-23T10:00:00Z' })
    }
    if (url.pathname === `/api/v1/analytics/${projectId}/workspace`) return json(analyticsWorkspace('project', Number(url.searchParams.get('window') || 30)))
    if (url.pathname === '/api/v1/analytics/global/workspace') return json(analyticsWorkspace('global', Number(url.searchParams.get('window') || 30)))
    if (url.pathname === '/api/v1/studio/templates' && method === 'GET') return json({ items: [
      { template_id: 'phone_metrics', name: 'Phone & metrics', description: 'Phone composition', canvas: { width: 1080, height: 1350 }, template_version: 17, template_sha256: 'b'.repeat(64) },
    ] })
    if (url.pathname === '/api/v1/templates' && url.searchParams.get('surface') === 'post' && method === 'GET') return json({ items: [
      { surface: 'post', template_id: 'phone_metrics', name: 'Phone & metrics', description: 'Phone composition', template_version: 27, template_sha256: 'a'.repeat(64), previews: {} },
      { surface: 'post', template_id: 'design_aaaaaaaaaaaaaaaaaaaa', name: 'Editorial Post', description: 'Accepted Post layout', template_version: 3, template_sha256: 'b'.repeat(64), previews: {} },
    ] })
    if (url.pathname === `/api/v1/studio/projects/${projectId}/creatives` && method === 'GET') return json({ items: [{
      creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
      ordinal: 1, origin: 'brief_generation', template_id: 'phone_metrics',
      template_version: 27, template_sha256: currentStudio.template_sha256,
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
        preview: { mime_type: 'image/png', sha256: studioPreviewSha256, width: 1080, height: 1350 },
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
      const projectLogoDefaultUpdated = (
        body.configuration.logo.symbol_color !== currentStudio.configuration.logo.symbol_color
        || body.configuration.logo.name_color !== currentStudio.configuration.logo.name_color
      )
      currentStudio = { ...currentStudio, state_sha256: '9'.repeat(64), configuration: body.configuration, content: body.content }
      return json({
        creative: currentStudio, checkpoint_created: true, version_created: false,
        checkpoint: {
          checkpoint_id: '018f07ea-7f20-7000-8000-000000000005',
          creative_id: creativeId, project_id: projectId, kind: 'save',
          before_state_sha256: '1'.repeat(64), after_state_sha256: '2'.repeat(64),
          changed_paths: ['content.hero_title'], status: 'saved',
        },
        learning_proposal: null,
        project_logo_default_updated: projectLogoDefaultUpdated,
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
          changed_paths: ['content.hero_title'], status: 'saved',
        },
        learning_proposal: null,
        project_logo_default_updated: (
          body.configuration.logo.symbol_color !== currentStudio.configuration.logo.symbol_color
          || body.configuration.logo.name_color !== currentStudio.configuration.logo.name_color
        ),
      })
    }
    if (url.pathname === `/api/v1/briefs/${briefId}/approve` && method === 'POST') return json({
      brief: { ...brief, approved: true }, approved_now: true,
      creative: { creative_id: creativeId, project_id: projectId, source_brief_id: briefId, ordinal: 1, origin: 'brief_generation', template_id: 'phone_metrics', template_version: 27, template_sha256: 'a'.repeat(64), status: 'queued', state_sha256: 'f'.repeat(64), approved_version_count: 0, generation: { stage: 'queued' }, created_at: '2026-08-26T08:06:00Z', updated_at: '2026-08-26T08:06:00Z' }, creative_created: true,
    }, 202)
    if (url.pathname === '/api/v1/briefs') return json({ items: [brief], next_cursor: null })
    if (url.pathname === `/api/v1/briefs/${briefId}`) return json(brief)
    return json({ detail: `Unhandled ${method} ${url.pathname}` }, 404)
  })
})

test('approves a Brief through the required template picker and opens its creative', async ({ page }) => {
  let approvalBody: unknown = null
  await page.route(`**/api/v1/briefs/${briefId}`, async (route) => {
    if (route.request().method() === 'GET') return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ...brief, approved: false }),
    })
    return route.fallback()
  })
  await page.route(`**/api/v1/briefs/${briefId}/approve`, async (route) => {
    approvalBody = route.request().postDataJSON()
    return route.fulfill({
      status: 202, contentType: 'application/json',
      body: JSON.stringify({
        brief: { ...brief, approved: true }, approved_now: true,
        creative: {
          creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
          ordinal: 1, origin: 'brief_generation', template_id: 'phone_metrics',
          template_version: 27, template_sha256: 'a'.repeat(64), status: 'queued',
          state_sha256: 'f'.repeat(64), approved_version_count: 0,
          generation: { stage: 'queued' }, created_at: '2026-08-26T08:06:00Z',
          updated_at: '2026-08-26T08:06:00Z',
        },
        creative_created: true,
      }),
    })
  })
  await page.goto(`/?e2e=1&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await page.getByRole('button', { name: 'I can honor this promise and offer — approve' }).click()
  const picker = page.getByRole('dialog', { name: 'Choose the creative template' })
  await expect(picker).toBeVisible()
  await expect(picker.getByRole('button', { name: 'Approve Brief & generate creative' })).toBeDisabled()
  await expect(picker.locator('.post-template-choices article')).toHaveCount(2)
  await picker.getByRole('button', { name: /Editorial Post/ }).click()
  await picker.locator('input[value="cinematic"]').check()
  await picker.locator('input[value="scene"]').check()
  const approveButton = picker.getByRole('button', { name: 'Approve Brief & generate creative' })
  await expect(approveButton).toBeEnabled()
  await approveButton.dispatchEvent('click')
  await expect.poll(() => approvalBody).toEqual({
    honor_confirmed: true, template_id: 'design_aaaaaaaaaaaaaaaaaaaa',
    template_reference: { surface: 'post', template_id: 'design_aaaaaaaaaaaaaaaaaaaa', template_version: 3, template_sha256: 'b'.repeat(64) },
    creative_direction: {
      schema: 'ptw.studio.phone-hero-direction.v1', style: 'cinematic', background: 'scene',
    },
  })
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('posts')
  await expect.poll(() => new URL(page.url()).searchParams.get('creative')).toBe(creativeId)
})

test('opens an approved Brief\'s existing creative without resubmitting approval', async ({ page }) => {
  let approvalPosts = 0
  let creativeListGets = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith(`/briefs/${briefId}/approve`)) {
      approvalPosts += 1
    }
    if (request.method() === 'GET' && request.url().endsWith(`/studio/projects/${projectId}/creatives`)) {
      creativeListGets += 1
    }
  })

  await page.goto(`/?e2e=1&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  const openCreative = page.getByRole('button', { name: 'Open or create its creative' })
  await expect(openCreative).toHaveAttribute('data-contract', 'approved-brief-existing-creative-v1')
  await openCreative.click()

  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('posts')
  await expect.poll(() => new URL(page.url()).searchParams.get('creative')).toBe(creativeId)
  await expect(page.getByRole('dialog', { name: 'Choose the creative template' })).toHaveCount(0)
  expect(creativeListGets).toBeGreaterThan(0)
  expect(approvalPosts).toBe(0)
})

test('explains a persisted API-backed Brief failure without exposing raw provider text', async ({ page }) => {
  const failed = {
    ...brief, status: 'failed', document: null, document_sha256: null,
    failure_count: 2, error_code: 'RuntimeError',
    error_message: 'structured bridge request 437 failed', approved: false,
  }
  await page.route('**/api/v1/briefs**', async (route) => {
    const url = new URL(route.request().url())
    if (route.request().method() !== 'GET') return route.fallback()
    return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(url.pathname === '/api/v1/briefs' ? { items: [failed], next_cursor: null } : failed),
    })
  })

  await page.goto(`/?e2e=1&project=${projectId}`)
  await expect(page.getByText('Не вдалося згенерувати продуктовий бриф.')).toBeVisible()
  await expect(page.getByText(/Пояснення: Сервіс ChatGPT\/Codex/)).toBeVisible()
  await expect(page.getByText(/Що робити: У Налаштуваннях/)).toBeVisible()
  await expect(page.getByText(new RegExp(`bridge job 437 · ID ${briefId}`))).toBeVisible()
  await expect(page.getByText('structured bridge request 437 failed')).toHaveCount(0)
})

test('shows Brief, the project-scoped Post editor, Landing, and Instagram tests', async ({ page }) => {
  await page.goto(`/?e2e=1&project=${projectId}`)
  await expect(page.getByRole('button', { name: 'Бриф' }).first()).toBeVisible()
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await expect(page.getByRole('button', { name: 'Brief' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Social posts' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Post', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Landing', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Instagram tests', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Natal Studio', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Studio', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Post', exact: true }).first().click()
  await expect(page.locator('.phone-metrics-canvas-panel')).toBeVisible()
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('posts')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Post', exact: true }).first()).toBeVisible()
  await expect(page.getByText('Ad Studio')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Instagram tests', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Landing', exact: true }).first().click()
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('landing')

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('shows Project and All Projects analytics without automatic activation', async ({ page }) => {
  await page.goto(`/?e2e=1&page=analytics&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()

  await expect(page.getByRole('heading', { name: 'Creative Analytics' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Landing funnel' })).toBeVisible()
  await expect(page.getByText('Post leaderboard')).toBeVisible()
  await expect(page.getByText('2.0%')).toBeVisible()
  await expect(page.getByText('Public-photo canary is not yet audited.')).toBeVisible()
  await expect(page.getByText('No active snapshot yet.')).toBeVisible()
  await page.getByRole('combobox', { name: 'Analytics window' }).selectOption('1')
  await expect(page.getByText(/Landing events since midnight/)).toBeVisible()
  await expect(page.getByText('Posts published today', { exact: true })).toBeVisible()
  await expect(page.locator('.analytics-metrics .analytics-metric').first()).toContainText('2')
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('analytics')
  await page.screenshot({ path: `.local/analytics-today-${test.info().project.name}.png`, fullPage: true })
  await page.getByRole('button', { name: 'All Projects' }).click()
  await expect(page.getByText('No provider snapshots in this window.')).toBeVisible()
  await expect(page.getByText('GLOBAL SPIRIT')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `.local/analytics-${test.info().project.name}.png`, fullPage: true })
})

test('opens the local Tune wizard and submits all three generation inputs', async ({ page }) => {
  await page.goto(`/?e2e=1&page=posts&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
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
  await expect(wizard.getByText('GENERATED CREATIVE · 1080×1350')).toBeVisible()
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

test('waits for an explicit Project selection before loading project content', async ({ page }) => {
  const projectReads: string[] = []
  page.on('request', request => {
    if (/\/briefs\?|\/studio\/projects\//.test(request.url())) projectReads.push(request.url())
  })
  await page.goto('/?e2e=1')
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await expect(page.getByLabel('Existing Project')).toHaveValue('')
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Marketing approach', { exact: true })).toHaveCount(0)
  expect(projectReads).toEqual([])
  await page.getByLabel('Existing Project').selectOption(projectId)
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toHaveCount(0)

  await page.getByRole('button', { name: 'New Project' }).click()
  await expect(page.getByRole('heading', { name: 'New Project' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Name the Project' })).toBeVisible()
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toHaveCount(0)

  await page.getByLabel('Existing Project').selectOption(projectId)
  await expect(page.getByText('BRIEF HISTORY', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What do you want to validate?' })).toHaveCount(0)
})

test('deletes a Project only after exact name confirmation', async ({ page }) => {
  await page.goto(`/?e2e=1&project=${projectId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()

  await page.getByRole('button', { name: 'Delete' }).click()
  const dialog = page.getByRole('alertdialog', { name: `Delete “${project.name}”?` })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Delete Project' })).toBeDisabled()
  await dialog.getByLabel(`Type ${project.name} to confirm`).fill(project.name)
  const requestPromise = page.waitForRequest(request =>
    request.url().endsWith(`/api/v1/projects/${projectId}/delete`) && request.method() === 'POST',
  )
  await dialog.getByRole('button', { name: 'Delete Project' }).click()
  const request = await requestPromise
  expect(request.postDataJSON()).toEqual({
    request_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
    confirmation_name: project.name,
  })
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'New Project' })).toBeVisible()
  await expect(page.getByLabel('Existing Project')).toHaveCount(0)
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('Project marketing choice creates a visible hypothesis and immutable replacement', async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  const values: typeof brief[] = []
  const createDocument = (approach: string) => ({ ...briefDocument, schema_version: 3, brand_identity: {
    belief: "Your next step deserves attention.", identity_signal: "I choose my next move deliberately.",
    values: "Curiosity and practical progress.", cultural_tension: "Advice that never becomes action.",
    category_reframe: "A conversation that opens a next step.", emotional_reward: "Confidence in a considered choice.",
    competence_cue: "Bring one decision to the conversation.", proof_anchor: "Real consultant profiles and clear booking.",
    voice: "Warm and direct. Choose your next step.", visual_world: "Two people in conversation with an open notebook.", ritual: "",
  }, positioning: {
    marketing_approach: approach, desired_identity: 'Ready to take a considered first step',
    customer_tension: 'Want guidance without a large commitment', category_frame: 'A guided first conversation',
    functional_value: 'Clear booking and real consultant profiles',
  } })
  await page.route('**/api/v1/briefs**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/briefs') return route.fulfill({ json: { items: values } })
    const current = values.find(item => url.pathname.includes(item.brief_id))
    if (url.pathname.endsWith('/correct')) {
      const body = route.request().postDataJSON()
      expect(body.marketing_approach).toBe('benefit_led')
      expect(body.instruction).toBeTruthy()
      const replacement = { ...brief, brief_id: '018f07ea-7f20-7000-8000-000000000099', approved: false, document: createDocument(body.marketing_approach) }
      values.unshift(replacement)
      return route.fulfill({ status: 202, json: { brief: replacement, created: true } })
    }
    return route.fulfill({ json: current })
  })
  await page.route(`**/api/v1/projects/${projectId}/briefs`, async route => {
    const body = route.request().postDataJSON()
    expect(body.marketing_approach).toBe('identity_led')
    const created = { ...brief, approved: false, document: createDocument(body.marketing_approach) }
    values.unshift(created)
    return route.fulfill({ status: 202, json: { project, brief: created, created: true } })
  })
  await page.goto(`/?e2e=1&project=${projectId}`)
  await expect(page.getByLabel('Marketing approach', { exact: true })).toHaveValue('benefit_led')
  await page.getByLabel('Marketing approach', { exact: true }).selectOption('identity_led')
  await page.getByPlaceholder('Describe one product idea…').fill('A guided first conversation')
  await page.getByRole('button', { name: 'Generate first Product Brief', exact: true }).click()
  await expect(page.locator('.marketing-approach-badge')).toContainText('Identity-led')
  await expect(page.getByRole('region', { name: 'Positioning', exact: true })).toContainText('Clear booking')
  await expect(page.getByRole('region', { name: 'Brand identity', exact: true })).toContainText('Your next step deserves attention.')
  await page.getByLabel('Marketing approach for replacement', { exact: true }).selectOption('benefit_led')
  await page.getByRole('button', { name: 'Create replacement', exact: true }).click()
  await expect(page.locator('.marketing-approach-badge')).toContainText('Benefit-led')
  expect(values).toHaveLength(2)
  expect(values[1].document).toEqual(createDocument('identity_led'))
  await page.reload()
  await expect(page.locator('.marketing-approach-badge')).toContainText('Benefit-led')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: info.outputPath('marketing-approach-project.png'), fullPage: true })
})

test('Ukrainian brand strategy stays readable and historical V2 has no invented section', async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'uk'))
  const doc = { ...briefDocument, schema_version: 3, language: 'uk', product: 'Авто для вихідних із друзями',
    promise: 'Вихідні з друзями починаєш ти.', target_audience: 'Друг, який бере ініціативу зібрати всіх.',
    main_pain: 'Спільні плани залишаються розмовами.', cta: 'Запитати про авто', offer: 'Дізнайтеся про авто на ваші дати.',
    trust_strategy: 'Відкрито пояснити умови користування.', key_benefits: ['Авто на час поїздки', 'Час разом у дорозі', 'Без купівлі власного авто'],
    positioning: { marketing_approach: 'identity_led', desired_identity: 'Друг, який перетворює плани на спільний час.',
      customer_tension: 'Хочеться поїхати, але плани відкладаються.', category_frame: 'Початок вихідних разом.', functional_value: 'Тимчасове користування авто.' },
    brand_identity: {
      belief: 'Спільним планам варто давати початок.', identity_signal: 'Я беру на себе перший крок, щоб у нас був час одне для одного.',
      values: 'Ініціатива — запропонувати поїздку; дружба — виділити час; уважність — обрати авто під спільні плани.',
      cultural_tension: 'Звичне «треба якось зібратися» залишає вихідні на рівні розмов.', category_reframe: 'Каршеринг як перший практичний крок до вихідних разом.',
      emotional_reward: 'Приємно бути тим, хто допоміг друзям зібратися.', competence_cue: 'Спершу визначте кількість людей, багаж і маршрут; потім обирайте автомобіль.',
      proof_anchor: 'Тимчасове користування автомобілем.', voice: 'Тепла й рішуча: «Ці вихідні — наші».',
      visual_world: 'У дворі друзі складають сумки в чітко впізнаваний автомобіль. Дорожні сумки й тепле ранкове світло.',
      ritual: 'Запропонувати в чаті конкретний день і місце наступного виїзду.',
    },
  }
  const older = { ...brief, brief_id: '018f07ea-7f20-7000-8000-000000000098', document: { ...doc, schema_version: 2, brand_identity: undefined, product: 'Попередній бриф' } }
  const current = { ...brief, document: doc }
  await page.route('**/api/v1/briefs**', route => {
    const path = new URL(route.request().url()).pathname
    return route.fulfill({ json: path === '/api/v1/briefs' ? { items: [current, older] } : path.endsWith(older.brief_id) ? older : current })
  })
  await page.goto(`/?e2e=1&project=${projectId}`)
  const section = page.getByRole('region', { name: 'Ідентичність бренду', exact: true })
  await expect(section).toContainText(doc.brand_identity.visual_world)
  await section.screenshot({ path: info.outputPath('brand-identity-uk.png') })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.getByRole('button', { name: /Попередній бриф/ }).click()
  await expect(section).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Позиціонування', exact: true })).toBeVisible()
})
