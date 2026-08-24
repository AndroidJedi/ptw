import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const sourceId = '018f07ea-7f20-7000-8000-000000000001'
const brief1 = '018f07ea-7f20-7000-8000-000000000002'
const brief2 = '018f07ea-7f20-7000-8000-000000000003'
const feedbackId = '018f07ea-7f20-7000-8000-000000000004'
const proposalId = '018f07ea-7f20-7000-8000-000000000005'
const batchId = '018f07ea-7f20-7000-8000-000000000006'
const angles = ['emotional', 'practical', 'curiosity', 'authority', 'problem_first'] as const

async function expectMonochromeChrome(page: Page) {
  const violations = await page.locator('body *').evaluateAll((elements) => {
    const properties = [
      'color', 'background-color', 'border-top-color', 'border-right-color',
      'border-bottom-color', 'border-left-color', 'outline-color',
      'text-decoration-color', 'fill', 'stroke',
    ]
    return elements.flatMap((element) => {
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
  let creativeLesson = 'Prefer a warmer crop with approachable real people.'
  const currentId = () => corrected ? brief2 : brief1
  const brief = (id = currentId()) => ({
    brief_id: id, request_id: id, owner_idea_source_id: sourceId,
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
      mime_type: 'image/jpeg', width: 1080, height: 1080, sha256: 'a'.repeat(64),
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
    batch_id: batchId, brief_id: brief2, status: 'completed', batch_sha256: 'b'.repeat(64),
    quality_gates: { passed: true }, failure_count: 0,
    error_code: null, error_message: null,
    creatives: angles.map(creative), created_at: '2026-08-24T08:05:00Z',
  })

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname === '/api/v1/briefs' && method === 'GET') {
      const items = !created ? [] : corrected ? [brief(brief2), brief(brief1)] : [brief(brief1)]
      return json({ items, next_cursor: null })
    }
    if (url.pathname === '/api/v1/briefs' && method === 'POST') {
      expect(Object.keys(route.request().postDataJSON()).sort()).toEqual(['raw_idea', 'request_id'])
      created = true; return json({ brief: brief(brief1), created: true }, 202)
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
      const targetId = url.searchParams.get('target_id')
      const firstCreativeId = creative('emotional', 0).creative_id
      return json({ items: creativeFeedbackSaved && targetId === firstCreativeId ? [{ proposal_id: proposalId, feedback_id: feedbackId, target_id: firstCreativeId, lesson: creativeLesson, status: 'pending', command_session_id: null, created_at: '2026-08-24T08:06:00Z', updated_at: '2026-08-24T08:06:00Z' }] : [] })
    }
    if (url.pathname === `/api/v1/skill-proposals/ad_creative/${proposalId}/update` && method === 'POST') {
      creativeLesson = route.request().postDataJSON().lesson
      return json({ proposal_id: proposalId, feedback_id: feedbackId, target_id: creative('emotional', 0).creative_id, lesson: creativeLesson, status: 'pending' })
    }
    if (url.pathname === '/api/v1/ad-batches' && method === 'GET') return json({ items: batchCreated ? [batch()] : [], next_cursor: null })
    if (url.pathname === `/api/v1/ad-batches/${batchId}`) return json(batch())
    if (/\/api\/v1\/ad-creatives\/[^/]+\/image$/.test(url.pathname)) {
      return route.fulfill({ status: 200, contentType: 'image/jpeg', headers: { ETag: `"${'a'.repeat(64)}"` }, body: Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAEf/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EH//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EH//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EH//2Q==', 'base64') })
    }
    if (/\/api\/v1\/ad-creatives\/[^/]+\/feedback$/.test(url.pathname) && method === 'POST') {
      expect(route.request().postDataJSON()).toEqual({ comment: 'Use a warmer crop.' })
      creativeFeedbackSaved = true
      return json({ feedback_id: feedbackId, weight_update_id: brief1, proposal_id: proposalId })
    }
    if (url.pathname === '/api/v1/jobs') return json({ items: [], next_cursor: null })
    if (url.pathname === '/api/v1/system/health') return json({ git_revision: 'validation-fixture', services: { gateway: 'ok', validation: { ready: true }, root_broker: 'ok' }, emergency_stop: false, reset: { permitted: true, target: 'ptw_commander.public only' } })
    if (url.pathname === '/api/v1/docs') return json({ items: [{ path: 'docs/README.md', title: 'PTW docs', body: '# PTW Validation' }] })
    return json({ detail: 'not found' }, 404)
  })
})

test('owner completes Product Brief and five-Ad validation journey', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByText('No Product Brief yet')).toBeVisible()
  await expectMonochromeChrome(page)
  await page.getByPlaceholder('Describe one product idea…').fill('Online platform where psychologists provide online consultations.')
  await page.getByRole('button', { name: /Generate Product Brief/ }).click()
  await expect(page.getByText('First consultation free')).toBeVisible()
  await expect(page.getByText(brief1, { exact: false })).toBeVisible()

  await page.getByPlaceholder('One correction for the complete Brief…').fill('Narrow the audience to first-time therapy seekers.')
  await page.getByRole('button', { name: /Create replacement/ }).click()
  await expect(page.getByText(brief2, { exact: false })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Owner lesson proposals' })).toBeVisible()
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
  const creativeProposal = page.locator('.creative-card').first().locator('.lesson-proposals')
  await expect(creativeProposal.getByRole('heading', { name: 'Owner lesson proposals' })).toBeVisible()
  await creativeProposal.locator('textarea').fill('Prefer warmer real-person crops.')
  await creativeProposal.getByRole('button', { name: 'Save edit' }).click()
  await expect(creativeProposal.locator('textarea')).toHaveValue('Prefer warmer real-person crops.')

  await page.getByRole('button', { name: 'Landing' }).first().click()
  await expect(page.getByRole('heading', { name: 'Stage 3 pending' })).toBeVisible()
  await expectMonochromeChrome(page)
  await page.getByRole('button', { name: 'Admin' }).first().click()
  await expect(page.getByRole('heading', { name: 'Завдання' })).toBeVisible()
  await expectMonochromeChrome(page)
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('retired page query redirects to Product Briefs', async ({ page }) => {
  await page.goto('/?e2e=1&page=positioning&run=legacy')
  await expect(page).not.toHaveURL(/page=positioning|run=legacy/)
  await expect(page.getByText('No Product Brief yet')).toBeVisible()
})

test('failed Ad batch shows actionable reason and Telegram state', async ({ page }) => {
  const failed = {
    batch_id: batchId,
    brief_id: brief2,
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

  await page.goto('/?e2e=1&page=ads')
  await expect(page.getByRole('heading', { name: 'Approved offer continuity check failed' })).toBeVisible()
  await expect(page.getByText('Free 15-minute mentor call.', { exact: false })).toBeVisible()
  await expect(page.getByText('no partial creatives or images were saved', { exact: false })).toBeVisible()
  await expect(page.getByText('Telegram failure notification sent', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry entire batch' })).toBeVisible()
  await expectMonochromeChrome(page)
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})
