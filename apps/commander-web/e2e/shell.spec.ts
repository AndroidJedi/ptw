import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const sourceId = '018f07ea-7f20-7000-8000-000000000001'
const projectId = '018f07ea-7f20-7000-8000-000000000009'
const secondProjectId = '018f07ea-7f20-7000-8000-000000000019'
const brief1 = '018f07ea-7f20-7000-8000-000000000002'
const brief2 = '018f07ea-7f20-7000-8000-000000000003'
const feedbackId = '018f07ea-7f20-7000-8000-000000000004'
const proposalId = '018f07ea-7f20-7000-8000-000000000005'
const proposalId2 = '018f07ea-7f20-7000-8000-000000000007'
const batchId = '018f07ea-7f20-7000-8000-000000000006'
const studioKitId = '018f07ea-7f20-7000-8000-000000000020'
const studioTemplateId = '018f07ea-7f20-7000-8000-000000000021'
const imageSha256 = 'b5b0c61e6fe8c4f91957b5e48c30326121e24d26898e45f5ebc250c7d129c98b'
const angles = ['emotional', 'practical', 'curiosity', 'authority', 'problem_first'] as const
const personalizedUkrainianInstruction = 'Create a post with simple, short Ukrainian copy that hits the customer pain and shows the service solution. Make it more personalized around life events—for example name, birthday, and a personal horoscope for someone looking for a job.'

async function expectMonochromeChrome(page: Page) {
  const violations = await page.locator('body *').evaluateAll((elements) => {
    const properties = [
      'color', 'background-color', 'border-top-color', 'border-right-color',
      'border-bottom-color', 'border-left-color', 'outline-color',
      'text-decoration-color', 'fill', 'stroke',
    ]
    return elements.flatMap((element) => {
      if (element.closest('.studio-canvas, .studio-post-art, .studio-sample-art')) return []
      const style = getComputedStyle(element)
      return properties.flatMap((property) => {
        const value = style.getPropertyValue(property)
        const match = value.match(/rgba?\(\s*(\d+)\D+(\d+)\D+(\d+)/)
        if (!match) return []
        const [, red, green, blue] = match.map(Number)
        return red === green && green === blue ? [] : [`${element.tagName}.${element.className}: ${property}=${value}`]
      })
    }).slice(0, 20)
  })
  expect(violations).toEqual([])
}

const document = {
  schema_version: 1, language: 'en',
  product: 'Online consultations with real psychologists.',
  target_audience: 'First-time therapy seekers who want a low-risk first step.',
  main_pain: 'Finding trustworthy support feels difficult and high commitment.',
  promise: 'Meet a suitable psychologist with a calmer first step.',
  key_benefits: ['Real consultant profiles', 'Simple booking', 'No-card first step'],
  cta: 'Get free consultation',
  trust_strategy: 'Use real consultant photos, transparent pricing, and no card requirement.',
  offer: 'First consultation free',
}

test.beforeEach(async ({ page }) => {
  let created = false
  let corrected = false
  let approved = false
  let batchCreated = false
  let creativeFeedbackSaved = false
  let studioKitSaved = false
  let studioSamplesCreated = false
  let groupedLessonPlanned = false
  let creativeLesson = 'Prefer a warmer crop with approachable real people.'
  const creativeLesson2 = 'Keep candid human tension in the frame.'
  const currentId = () => corrected ? brief2 : brief1
  const project = () => ({
    project_id: projectId, request_id: brief1, owner_idea_source_id: sourceId,
    name: corrected ? document.product : 'Online platform where psychologists provide online consultations.',
    name_source: corrected ? 'product_brief' : 'raw_idea', requested_by: 'firebase:owner-uid',
    latest_brief_id: currentId(), latest_brief_status: 'completed',
    brief_count: corrected ? 2 : 1, ad_batch_count: batchCreated ? 1 : 0,
    created_at: '2026-08-24T08:00:00Z', updated_at: '2026-08-24T08:00:00Z',
  })
  const brief = (id = currentId()) => ({
    brief_id: id, project_id: projectId, project_name: project().name,
    request_id: id, owner_idea_source_id: sourceId,
    raw_idea: 'Online platform where psychologists provide online consultations.',
    base_brief_id: id === brief2 ? brief1 : null,
    feedback_id: id === brief2 ? feedbackId : null,
    status: 'completed', document, document_sha256: 'd'.repeat(64),
    quality_gates: { passed: true }, failure_count: 0,
    error_code: null, error_message: null,
    approved: approved && id === brief2,
    creative_batch_id: approved && id === brief2 ? batchId : null,
    creative_batch_status: approved && id === brief2 ? 'completed' : null,
    created_at: '2026-08-24T08:00:00Z', ...document,
  })
  const creative = (angle: typeof angles[number], ordinal: number) => ({
    creative_id: `018f07ea-7f20-7000-8000-${String(100 + ordinal).padStart(12, '0')}`,
    brief_id: brief2, ordinal, angle,
    hook: `${angle.replace('_', ' ')}: a calmer first step`,
    primary_text: 'First consultation free. Meet a real psychologist without a high-commitment start.',
    image_description: 'A real adult having a calm conversation with a professional.',
    cta: document.cta, offer: document.offer, desired_emotion: 'calm confidence',
    image_category: 'professional conversation', image_search_query: `real ${angle} conversation`,
    crop_focus: 'center', content_sha256: 'c'.repeat(64),
    image: {
      asset_id: `018f07ea-7f20-7000-8001-${String(100 + ordinal).padStart(12, '0')}`,
      url: `/api/v1/ad-creatives/018f07ea-7f20-7000-8000-${String(100 + ordinal).padStart(12, '0')}/image`,
      mime_type: 'image/jpeg', width: 1080, height: 1080, sha256: imageSha256,
      provider: 'pexels', source_photo_id: String(9000 + ordinal),
      source_url: `https://www.pexels.com/photo/${9000 + ordinal}/`,
      photographer: `Photographer ${ordinal + 1}`,
      photographer_url: 'https://www.pexels.com/@fixture',
      license: 'Pexels License', license_url: 'https://www.pexels.com/license/',
      attribution: `Photo by Photographer ${ordinal + 1} on Pexels`,
      alt: 'Real professional conversation',
    },
  })
  const batch = () => ({
    batch_id: batchId, brief_id: brief2, project_id: projectId, project_name: project().name,
    brief_product: document.product, status: 'completed', batch_sha256: 'b'.repeat(64),
    quality_gates: { passed: true }, failure_count: 0,
    error_code: null, error_message: null,
    creatives: angles.map(creative), created_at: '2026-08-24T08:05:00Z',
  })
  const sampleNames = ['Вікно ясності', 'Одне питання — три кроки', 'Прихований маршрут', 'Прозорий процес', 'Не загальний гороскоп']
  const sampleSet = () => ({
    sample_set_id: sourceId, project_id: projectId, brief_id: brief2, batch_id: batchId,
    brand_kit_id: studioKitId, status: 'completed', created_at: '2026-08-24T09:02:00Z',
    download_url: `/api/v1/ad-studio/sample-sets/${sourceId}/download`, download_sha256: 'f'.repeat(64), download_mime_type: 'application/zip',
    items: angles.map((angle, ordinal) => {
      const ad = creative(angle, ordinal)
      const recipeId = `018f07ea-7f20-7000-8002-${String(100 + ordinal).padStart(12, '0')}`
      const renderId = `018f07ea-7f20-7000-8003-${String(100 + ordinal).padStart(12, '0')}`
      const frames = [
        { instance_id: `018f07ea-7f20-7000-8004-${String(100 + ordinal).padStart(12, '0')}`, tool_id: 'studio.frame.headline.v1', frame: { x: .08, y: .1, width: .84, height: .3 }, z_index: 1, params: { text: ad.hook, color: '#FFFFFF', font_size: 64 }, timeline: null, source_asset_ids: [] },
        { instance_id: `018f07ea-7f20-7000-8005-${String(100 + ordinal).padStart(12, '0')}`, tool_id: 'studio.frame.offer.v1', frame: { x: .08, y: .68, width: .84, height: .1 }, z_index: 2, params: { text: document.offer, color: '#FFFFFF', font_size: 34 }, timeline: null, source_asset_ids: [] },
        { instance_id: `018f07ea-7f20-7000-8006-${String(100 + ordinal).padStart(12, '0')}`, tool_id: 'studio.frame.cta.v1', frame: { x: .08, y: .83, width: .5, height: .09 }, z_index: 3, params: { text: document.cta, color: '#FFFFFF', font_size: 30 }, timeline: null, source_asset_ids: [] },
      ]
      const recipeDocument = { schema_version: 2, parent_recipe_id: null, placement_tool_id: 'studio.placement.instagram.feed_square.v1', duration_seconds: null, frame_rate: null, frames, modifiers: [], strategy_ids: ['studio.strategy.one_message.v1'], validation_ids: [], source_reference_ids: [], share: { caption: ad.primary_text, alt_text: ad.image.alt }, width: 1080, height: 1080, source_asset_ids: [], renderer_version: 'studio-v2' }
      const render = { render_id: renderId, recipe_id: recipeId, mime_type: 'image/jpeg', width: 1080, height: 1080, bytes_sha256: imageSha256, manifest: {}, manifest_sha256: 'e'.repeat(64), renderer_version: 'studio-v2', published: false, created_at: '2026-08-24T09:02:00Z', asset_url: ad.image.url, manifest_url: `/api/v1/ad-studio/renders/${renderId}/manifest` }
      return { ordinal, angle, name: sampleNames[ordinal], source_creative_id: ad.creative_id, template_id: `018f07ea-7f20-7000-8007-${String(100 + ordinal).padStart(12, '0')}`, recipe_id: recipeId, render_id: renderId, caption: ad.primary_text, alt_text: ad.image.alt, template: {}, recipe: { recipe_id: recipeId, project_id: projectId, brief_id: brief2, brand_kit_id: studioKitId, parent_recipe_id: null, placement_tool_id: recipeDocument.placement_tool_id, document: recipeDocument, document_sha256: 'd'.repeat(64), renderer_version: 'studio-v2', created_by: 'owner', created_at: '2026-08-24T09:02:00Z' }, render }
    }),
  })

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname === '/api/v1/projects' && method === 'GET') {
      return json({ items: created ? [project()] : [], next_cursor: null })
    }
    if (url.pathname === `/api/v1/projects/${projectId}/rename` && method === 'POST') {
      return json({ ...project(), name: route.request().postDataJSON().name, name_source: 'owner' })
    }
    if (url.pathname === '/api/v1/briefs' && method === 'GET') {
      const items = !created ? [] : corrected ? [brief(brief2), brief(brief1)] : [brief(brief1)]
      return json({ items, next_cursor: null })
    }
    if (url.pathname === '/api/v1/briefs' && method === 'POST') {
      expect(Object.keys(route.request().postDataJSON()).sort()).toEqual(['raw_idea', 'request_id'])
      created = true; return json({ project: project(), brief: brief(brief1), created: true }, 202)
    }
    if (url.pathname === `/api/v1/briefs/${brief1}/correct` && method === 'POST') {
      expect(Object.keys(route.request().postDataJSON()).sort()).toEqual(['instruction', 'request_id'])
      corrected = true; return json({ brief: brief(brief2), created: true }, 202)
    }
    if (url.pathname === `/api/v1/briefs/${brief2}/approve` && method === 'POST') {
      expect(route.request().postDataJSON()).toEqual({ honor_confirmed: true })
      approved = true; batchCreated = true
      return json({ brief: brief(brief2), batch: batch(), generation_started: true }, 202)
    }
    if (url.pathname.startsWith('/api/v1/briefs/') && method === 'GET') {
      return json(brief(url.pathname.endsWith(brief1) ? brief1 : brief2))
    }
    if (url.pathname === '/api/v1/skill-proposals/product_brief') {
      return json({ items: corrected ? [{ proposal_id: proposalId, feedback_id: feedbackId, target_id: brief2, lesson: 'Narrow the first audience when relevant.', status: 'pending', command_session_id: null, created_at: '2026-08-24T08:02:00Z', updated_at: '2026-08-24T08:02:00Z' }] : [] })
    }
    if (url.pathname === '/api/v1/skill-proposals/ad_creative' && method === 'GET') {
      const firstCreativeId = creative('emotional', 0).creative_id
      const status = groupedLessonPlanned ? 'planning' : 'pending'
      return json({ items: creativeFeedbackSaved ? [
        { proposal_id: proposalId, feedback_id: feedbackId, target_id: firstCreativeId, lesson: creativeLesson, status, command_session_id: groupedLessonPlanned ? brief1 : null, created_at: '2026-08-24T08:06:00Z', updated_at: '2026-08-24T08:06:00Z' },
        { proposal_id: proposalId2, feedback_id: brief2, target_id: creative('practical', 1).creative_id, lesson: creativeLesson2, status, command_session_id: groupedLessonPlanned ? brief1 : null, created_at: '2026-08-24T08:07:00Z', updated_at: '2026-08-24T08:07:00Z' },
      ] : [] })
    }
    if (url.pathname === '/api/v1/skill-proposals/ad_creative/plan' && method === 'POST') {
      expect(route.request().postDataJSON()).toEqual({
        proposal_ids: [proposalId, proposalId2],
        lesson: 'Prefer warmer real-person crops.\nKeep candid human tension in the frame.',
      })
      creativeLesson = 'Prefer warmer real-person crops.'
      groupedLessonPlanned = true
      return json({ id: brief1, status: 'planning' }, 202)
    }
    if (url.pathname === '/api/v1/ad-batches' && method === 'GET') return json({ items: batchCreated ? [batch()] : [], next_cursor: null })
    if (url.pathname === `/api/v1/ad-batches/${batchId}`) return json(batch())
    if (/\/api\/v1\/ad-creatives\/[^/]+\/image$/.test(url.pathname)) {
      return route.fulfill({ status: 200, contentType: 'image/jpeg', headers: { ETag: `"${imageSha256}"` }, body: Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwAooooA/9k=', 'base64') })
    }
    if (/\/api\/v1\/ad-creatives\/[^/]+\/feedback$/.test(url.pathname) && method === 'POST') {
      expect(route.request().postDataJSON()).toEqual({ comment: 'Use a warmer crop.' })
      creativeFeedbackSaved = true
      return json({ feedback_id: feedbackId, weight_update_id: brief1, proposal_id: proposalId })
    }
    if (url.pathname === '/api/v1/ad-studio/tools') return json({ schema_version: 1, renderer_version: 'ptw-studio-renderer-v1', items: [
      { tool_id: 'studio.placement.instagram.feed_square.v1', kind: 'placement', label: 'Instagram feed · square', parameter_schema: {}, supported_placements: ['static'], renderer_handler: 'placement', defaults: { width: 1080, height: 1080 }, bounds: {}, source_refs: [], deprecated: false },
      { tool_id: 'studio.placement.instagram.feed_portrait.v1', kind: 'placement', label: 'Instagram feed · portrait', parameter_schema: {}, supported_placements: ['static'], renderer_handler: 'placement', defaults: { width: 1080, height: 1350 }, bounds: {}, source_refs: [], deprecated: false },
      ...['media', 'shape', 'body', 'offer', 'cta'].map((name) => ({ tool_id: `studio.frame.${name}.v1`, kind: 'frame', label: `${name} frame`, parameter_schema: {}, supported_placements: ['static', 'motion'], renderer_handler: name === 'media' ? 'media' : name === 'shape' ? 'shape' : 'text', defaults: {}, bounds: {}, source_refs: [], deprecated: false })),
      { tool_id: 'studio.frame.headline.v1', kind: 'frame', label: 'Headline frame', parameter_schema: {}, supported_placements: ['static'], renderer_handler: 'text', defaults: {}, bounds: {}, source_refs: [], deprecated: false },
      ...['safe_zone', 'small_screen_hierarchy', 'contrast', 'brand_consistency', 'claim_integrity', 'source_lineage'].map((name) => ({ tool_id: `studio.guard.${name}.v1`, kind: 'guard', label: name, parameter_schema: {}, supported_placements: ['static'], renderer_handler: 'validator', defaults: {}, bounds: {}, source_refs: [], deprecated: false })),
    ] })
    if (url.pathname === '/api/v1/ad-studio/brand-kits' && method === 'GET') return json({ items: studioKitSaved ? [{ brand_kit_id: studioKitId, project_id: projectId, parent_brand_kit_id: null, document: { name: 'Project brand', colors: ['#111111', '#FFFFFF', '#4466AA', '#F0C040'], fonts: ['Inter'], tone_notes: '', logo_source_asset_id: null }, document_sha256: 'a'.repeat(64), created_by: 'owner', created_at: '2026-08-24T09:00:00Z' }] : [] })
    if (url.pathname === '/api/v1/ad-studio/brand-kits' && method === 'POST') {
      studioKitSaved = true
      return json({ brand_kit_id: studioKitId, project_id: projectId, parent_brand_kit_id: null, document: route.request().postDataJSON().document, document_sha256: 'a'.repeat(64), created_by: 'owner', created_at: '2026-08-24T09:00:00Z' }, 201)
    }
    if (url.pathname === '/api/v1/ad-studio/templates' && method === 'GET') return json({ items: [] })
    if (url.pathname === '/api/v1/ad-studio/templates' && method === 'POST') {
      const body = route.request().postDataJSON()
      expect(body.document.frames.find((item: { tool_id: string }) => item.tool_id === 'studio.frame.offer.v1').params.text).toBe('{{offer}}')
      expect(body.document.frames.find((item: { tool_id: string }) => item.tool_id === 'studio.frame.cta.v1').params.text).toBe('{{cta}}')
      return json({ template_id: studioTemplateId, project_id: projectId, name: body.name, placement_tool_id: body.document.placement_tool_id, document: body.document, document_sha256: 'e'.repeat(64), created_by: 'owner', created_at: '2026-08-24T09:01:00Z' }, 201)
    }
    if (url.pathname === '/api/v1/ad-studio/sources' && method === 'GET') return json({ items: [] })
    if (url.pathname === '/api/v1/ad-studio/recipes' && method === 'GET') return json({ items: [] })
    if (url.pathname === '/api/v1/ad-studio/sample-sets' && method === 'GET') return json({ items: studioSamplesCreated ? [sampleSet()] : [] })
    if (url.pathname === '/api/v1/ad-studio/sample-sets' && method === 'POST') { expect(route.request().postDataJSON()).toEqual({ batch_id: batchId }); studioSamplesCreated = true; return json(sampleSet(), 201) }
    if (/\/api\/v1\/ad-studio\/recipes\/[^/]+\/renders$/.test(url.pathname)) return json({ items: [] })
    if (/\/api\/v1\/ad-studio\/recipes\/[^/]+\/wizard-proposals$/.test(url.pathname) && method === 'GET') return json({ items: [] })
    if (/\/api\/v1\/ad-studio\/recipes\/[^/]+\/wizard-proposals$/.test(url.pathname) && method === 'POST') {
      const body = route.request().postDataJSON()
      expect(body).toEqual({ instruction: personalizedUkrainianInstruction, target_instance_id: null })
      await new Promise((resolve) => setTimeout(resolve, 500))
      return json({
        proposal_id: proposalId, recipe_id: sampleSet().items[0].recipe_id, status: 'previewed',
        instruction: body.instruction, target_instance_id: body.target_instance_id,
        patch: [{ op: 'replace', path: '/frames/0/params/text', value: 'A calmer first step' }],
        before_sha256: '1'.repeat(64), after_sha256: '2'.repeat(64),
        preview_url: creative('emotional', 0).image.url, preview_sha256: imageSha256,
        preview_mime_type: 'image/jpeg', created_at: '2026-08-24T09:03:00Z',
      }, 201)
    }
    if (url.pathname === '/api/v1/skill-proposals/ad_studio' && method === 'GET') return json({ items: [] })
    if (url.pathname === '/api/v1/jobs') return json({ items: [], next_cursor: null })
    if (url.pathname === '/api/v1/system/health') return json({ git_revision: 'validation-fixture', services: { gateway: 'ok', validation: { ready: true }, root_broker: 'ok' }, emergency_stop: false, reset: { permitted: true, target: 'ptw_commander.public only' } })
    if (url.pathname === '/api/v1/docs') return json({ items: [{ path: 'docs/README.md', title: 'PTW docs', body: '# PTW Validation' }] })
    return json({ detail: 'not found' }, 404)
  })
})

test('Ad Studio exposes one Wizard-only post revision flow', async ({ page }) => {
  if (test.info().project.name === 'desktop') await page.setViewportSize({ width: 844, height: 596 })
  await page.goto('/?e2e=1')
  await page.getByPlaceholder('Describe one product idea…').fill('Online platform where psychologists provide online consultations.')
  await page.getByRole('button', { name: /Generate Product Brief/ }).click()
  await page.getByPlaceholder('One correction for the complete Brief…').fill('Narrow the audience to first-time therapy seekers.')
  await page.getByRole('button', { name: /Create replacement/ }).click()
  await page.getByRole('button', { name: /I can honor this promise and offer/ }).click()
  await page.getByRole('button', { name: 'Ad Studio' }).first().click()
  await expect(page).toHaveURL(/page=studio/)
  await expect(page.getByRole('heading', { name: 'Ad Studio' })).toBeVisible()
  await expect(page.getByText('Choose a post, tell AI what to change, review it, and save.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toHaveCount(0)
  await expect(page.getByText('Share copy', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Source library', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Reusable templates', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Render UUID', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Publish training example', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Create 5 posts' }).click()
  const gallery = page.getByLabel('Your five Studio posts')
  await expect(gallery.getByRole('button', { name: /Change .* with AI/ })).toHaveCount(5)
  await expect(gallery.getByText('Вікно ясності')).toBeVisible()
  await gallery.getByRole('button', { name: 'Change Вікно ясності with AI' }).click()
  await expect(page.getByLabel('Post preview').getByRole('heading', { name: 'Вікно ясності' })).toBeVisible()
  const wizard = page.getByLabel('AI wizard')
  await expect(wizard.getByRole('heading', { name: 'Change this post' })).toBeVisible()
  await wizard.getByLabel('What should change?').fill(personalizedUkrainianInstruction)
  const previewButton = wizard.getByRole('button', { name: 'Preview change' })
  if (test.info().project.name !== 'desktop') {
    await expect(previewButton).toBeInViewport()
    expect(await page.locator('html').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  }
  await previewButton.click()
  await expect(wizard.getByRole('status')).toContainText('Working on your preview')
  await expect(wizard.getByRole('progressbar')).toHaveAttribute('aria-valuetext', 'In progress')
  await expect(wizard.getByText('New preview ready.')).toBeVisible()
  await expect(page.getByLabel('Post preview').getByText('NEW PREVIEW · NOT SAVED')).toBeVisible()
  await expect(page.getByLabel('Post preview').getByAltText('Preview of proposed change')).toBeVisible()
  await expect(wizard.getByRole('button', { name: 'Use this version' })).toBeVisible()
  await expectMonochromeChrome(page)
})

test('owner completes Product Brief and five-Ad validation journey', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByRole('heading', { name: 'No Project yet' })).toBeVisible()
  await expectMonochromeChrome(page)
  await page.getByPlaceholder('Describe one product idea…').fill('Online platform where psychologists provide online consultations.')
  await page.getByRole('button', { name: /Generate Product Brief/ }).click()
  await expect(page.getByLabel('Project', { exact: true })).toHaveValue(projectId)
  await expect(page.getByText('First consultation free')).toBeVisible()
  await expect(page.getByText(brief1, { exact: false })).toBeVisible()

  await page.getByPlaceholder('One correction for the complete Brief…').fill('Narrow the audience to first-time therapy seekers.')
  await page.getByRole('button', { name: /Create replacement/ }).click()
  await expect(page.getByText(brief2, { exact: false })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Use feedback next time' })).toBeVisible()
  await page.getByRole('button', { name: /I can honor this promise and offer/ }).click()
  await expect(page.getByText(`Approved · creative batch ${batchId}`)).toBeVisible()

  await page.getByRole('button', { name: 'Ads' }).first().click()
  await expect(page.locator('.creative-card')).toHaveCount(5)
  await expect(page.locator('.pexels-credit')).toHaveCount(5)
  await expect(page.locator('.pexels-credit').first().getByRole('link', { name: 'Pexels' })).toHaveAttribute('href', 'https://www.pexels.com')
  await expect(page.locator('.creative-art img')).toHaveCount(5)
  await expect(page.getByText('Problem-first')).toBeVisible()
  await expectMonochromeChrome(page)
  await page.locator('.creative-card summary').first().click()
  await expect(page.getByText('Photo by Photographer 1 on Pexels')).toBeVisible()
  await page.locator('.creative-card textarea').first().fill('Use a warmer crop.')
  await page.locator('.creative-card').first().getByRole('button', { name: /Save feedback/ }).click()
  await expect(page.getByRole('status')).toContainText(`Feedback ${feedbackId} saved`)
  const creativeProposal = page.locator('.ads-workspace > .lesson-proposals')
  await expect(creativeProposal.getByRole('heading', { name: 'Use feedback next time' })).toBeVisible()
  await expect(creativeProposal.locator('textarea')).toHaveValue('Prefer a warmer crop with approachable real people.\nKeep candid human tension in the frame.')
  await creativeProposal.locator('textarea').fill('Prefer warmer real-person crops.\nKeep candid human tension in the frame.')
  await expect(creativeProposal.getByRole('button')).toHaveCount(1)
  await creativeProposal.getByRole('button', { name: 'Review future rule' }).click()
  await expect(creativeProposal.getByText('No feedback is waiting to become a future rule.')).toBeVisible()
  await expect(creativeProposal.getByRole('button', { name: 'Save edit' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Landing' }).first().click()
  await expect(page.getByRole('heading', { name: 'Stage 3 pending' })).toBeVisible()
  await expectMonochromeChrome(page)
  await page.getByRole('button', { name: 'Admin' }).first().click()
  await expect(page.getByRole('heading', { name: 'Jobs' })).toBeVisible()
  await expectMonochromeChrome(page)
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('malformed creative resources show their reason and a bounded retry', async ({ page }) => {
  await page.route('**/api/v1/ad-creatives/**/image', (route) => route.fulfill({
    status: 200,
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgBX2EQZQBOnoA=', 'base64'),
  }))
  await page.goto('/?e2e=1')
  await page.getByPlaceholder('Describe one product idea…').fill('Online platform where psychologists provide online consultations.')
  await page.getByRole('button', { name: /Generate Product Brief/ }).click()
  await page.getByPlaceholder('One correction for the complete Brief…').fill('Narrow the audience to first-time therapy seekers.')
  await page.getByRole('button', { name: /Create replacement/ }).click()
  await page.getByRole('button', { name: /I can honor this promise and offer/ }).click()
  await page.getByRole('button', { name: 'Ads' }).first().click()

  const failures = page.locator('.creative-image-fallback[role="alert"]')
  await expect(failures).toHaveCount(5)
  await expect(failures.first()).toContainText('Authenticated image returned image/png; expected image/jpeg.')
  await expect(failures.first()).toContainText('Creative 018f07ea-7f20-7000-8000-000000000100')
  await expect(failures.first().getByRole('button', { name: 'Retry image' })).toBeVisible()
  await expectMonochromeChrome(page)
})

test('retired page query redirects to Product Briefs', async ({ page }) => {
  await page.goto('/?e2e=1&page=positioning&run=legacy')
  await expect(page).not.toHaveURL(/page=positioning|run=legacy/)
  await expect(page.getByRole('heading', { name: 'No Project yet' })).toBeVisible()
})

test('failed Ad batch shows actionable reason and Telegram state', async ({ page }) => {
  const failed = {
    batch_id: batchId,
    brief_id: brief2,
    project_id: projectId,
    project_name: document.product,
    brief_product: document.product,
    status: 'failed',
    batch_sha256: null,
    quality_gates: null,
    failure_count: 1,
    error_code: 'ValueError',
    error_message: 'every creative must retain the Product Brief offer exactly',
    approved_offer: 'Free 15-minute mentor call.',
    failure_notification: {
      status: 'sent', attempt_id: feedbackId, recorded_at: '2026-08-24T09:44:18Z',
    },
    creatives: [],
    created_at: '2026-08-24T09:43:50Z',
  }
  await page.route('**/api/v1/ad-batches**', async (route) => {
    const url = new URL(route.request().url())
    const value = url.pathname === '/api/v1/ad-batches'
      ? { items: [failed], next_cursor: null }
      : failed
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })
  })
  await page.route('**/api/v1/projects**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ items: [{
      project_id: projectId, request_id: brief1, owner_idea_source_id: sourceId,
      name: document.product, name_source: 'product_brief', requested_by: 'fixture',
      latest_brief_id: brief2, latest_brief_status: 'completed', brief_count: 2,
      ad_batch_count: 1, created_at: '2026-08-24T08:00:00Z', updated_at: '2026-08-24T08:00:00Z',
    }], next_cursor: null }),
  }))

  await page.goto('/?e2e=1&page=ads')
  await expect(page.getByRole('heading', { name: 'Approved offer continuity check failed' })).toBeVisible()
  await expect(page.getByText('Free 15-minute mentor call.', { exact: false })).toBeVisible()
  await expect(page.getByText('no partial creatives or images were saved', { exact: false })).toBeVisible()
  await expect(page.getByText('Telegram failure notification sent', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry entire batch' })).toBeVisible()
  await expectMonochromeChrome(page)
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('recovered Ad batch keeps its earlier failure reason visible', async ({ page }) => {
  const recovered = {
    batch_id: batchId,
    brief_id: brief2,
    project_id: projectId,
    project_name: document.product,
    brief_product: document.product,
    status: 'completed',
    batch_sha256: 'b'.repeat(64),
    quality_gates: { passed: true },
    failure_count: 1,
    error_code: null,
    error_message: null,
    approved_offer: 'Free 15-minute mentor call.',
    last_failed_attempt: {
      attempt_id: feedbackId,
      attempt_number: 1,
      error_code: 'ValueError',
      error_message: 'every creative must retain the Product Brief offer exactly',
      started_at: '2026-08-24T09:43:50Z',
      completed_at: '2026-08-24T09:44:17Z',
    },
    failure_notification: {
      status: 'sent', attempt_id: feedbackId, recorded_at: '2026-08-24T09:44:18Z',
    },
    creatives: [],
    created_at: '2026-08-24T09:43:50Z',
  }
  await page.route('**/api/v1/ad-batches**', async (route) => {
    const url = new URL(route.request().url())
    const value = url.pathname === '/api/v1/ad-batches'
      ? { items: [recovered], next_cursor: null }
      : recovered
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })
  })
  await page.route('**/api/v1/projects**', (route) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ items: [{
      project_id: projectId, request_id: brief1, owner_idea_source_id: sourceId,
      name: document.product, name_source: 'product_brief', requested_by: 'fixture',
      latest_brief_id: brief2, latest_brief_status: 'completed', brief_count: 2,
      ad_batch_count: 1, created_at: '2026-08-24T08:00:00Z', updated_at: '2026-08-24T08:00:00Z',
    }], next_cursor: null }),
  }))

  await page.goto('/?e2e=1&page=ads')
  await expect(page.getByRole('heading', { name: 'Batch completed after an earlier failure' })).toBeVisible()
  await expect(page.getByText('Free 15-minute mentor call.', { exact: false })).toBeVisible()
  await page.getByText('Previous attempt details').click()
  await expect(page.getByText('every creative must retain the Product Brief offer exactly')).toBeVisible()
  await expect(page.getByText('Telegram failure notification sent', { exact: false })).toBeVisible()
  await expectMonochromeChrome(page)
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('global Project selection isolates Brief and Ad workspaces and persists across stages', async ({ page }) => {
  const secondBriefId = '018f07ea-7f20-7000-8000-000000000020'
  const secondBatchId = '018f07ea-7f20-7000-8000-000000000021'
  const projectSummary = (id: string, name: string, latestBriefId: string) => ({
    project_id: id, request_id: id, owner_idea_source_id: sourceId,
    name, name_source: 'product_brief', requested_by: 'fixture',
    latest_brief_id: latestBriefId, latest_brief_status: 'completed', brief_count: 1,
    ad_batch_count: 1, created_at: '2026-08-25T08:00:00Z', updated_at: '2026-08-25T08:05:00Z',
  })
  const scopedBatch = (id: string, ownerProjectId: string, ownerBriefId: string, product: string) => ({
    batch_id: id, brief_id: ownerBriefId, project_id: ownerProjectId, project_name: product,
    brief_product: product, status: 'queued', failure_count: 0, creatives: [],
    created_at: '2026-08-25T08:06:00Z', updated_at: '2026-08-25T08:06:00Z',
  })
  const first = scopedBatch(batchId, projectId, brief2, 'Psychologist consultations')
  const second = scopedBatch(secondBatchId, secondProjectId, secondBriefId, 'Mentor marketplace')

  await page.route('**/api/v1/projects**', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ items: [
      projectSummary(secondProjectId, 'Mentor marketplace', secondBriefId),
      projectSummary(projectId, 'Psychologist consultations', brief2),
    ], next_cursor: null }),
  }))
  await page.route('**/api/v1/ad-batches**', (route) => {
    const url = new URL(route.request().url())
    const value = url.pathname === `/api/v1/ad-batches/${secondBatchId}` ? second
      : url.pathname === `/api/v1/ad-batches/${batchId}` ? first
      : url.searchParams.get('project_id') === secondProjectId
        ? { items: [second], next_cursor: null }
        : { items: [first], next_cursor: null }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })
  })

  await page.goto(`/?e2e=1&page=ads&project=${projectId}`)
  await expect(page.getByLabel('Project', { exact: true })).toHaveValue(projectId)
  const firstBatchSelector = page.getByLabel('Ad generation')
  await expect(firstBatchSelector).toContainText('Ads from Brief · Psychologist consultations · queued')
  await expect(firstBatchSelector).not.toContainText(batchId)
  await expect(page.getByText(`Project ${projectId} · Brief ${brief2} · Batch ${batchId}`)).toBeVisible()

  await page.getByLabel('Project', { exact: true }).selectOption(secondProjectId)
  await expect(page).toHaveURL(new RegExp(`project=${secondProjectId}`))
  await expect(page.getByLabel('Ad generation')).toContainText('Ads from Brief · Mentor marketplace · queued')
  await expect(page.getByText(`Project ${secondProjectId} · Brief ${secondBriefId} · Batch ${secondBatchId}`)).toBeVisible()

  await page.getByRole('button', { name: 'Landing' }).first().click()
  await expect(page.getByRole('heading', { name: 'Stage 3 pending' })).toBeVisible()
  await expect(page.locator('.landing-placeholder').getByText('Mentor marketplace', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Admin' }).first().click()
  await expect(page.getByLabel('Project', { exact: true })).toHaveCount(0)
  await expect(page).toHaveURL(new RegExp(`project=${secondProjectId}`))
  await expectMonochromeChrome(page)
})
