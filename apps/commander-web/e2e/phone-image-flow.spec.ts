import { createHash } from 'node:crypto'
import { expect, test } from '@playwright/test'

const projectId = '018f07ea-7f20-7000-8000-000000000101'
const briefId = '018f07ea-7f20-7000-8000-000000000102'
const creativeId = '018f07ea-7f20-7000-8000-000000000103'
const creativePath = `/api/v1/studio/projects/${projectId}/creatives/${creativeId}`
const imageBytes = [Buffer.from('phone-image-one'), Buffer.from('phone-image-two'), Buffer.from('phone-image-three'), Buffer.from('phone-image-four')]
const imageDigests = imageBytes.map((value) => createHash('sha256').update(value).digest('hex'))
const previewBytes = Buffer.from('phone-preview')
const previewDigest = createHash('sha256').update(previewBytes).digest('hex')

function phoneDetail() {
  return {
    creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
    ordinal: 1, origin: 'brief_generation', status: 'draft', approved_version_count: 0,
    schema: 'ptw.studio.workspace.v8', template_id: 'phone_metrics',
    generation: {
      stage: 'draft',
      creative_direction: {
        schema: 'ptw.studio.phone-hero-direction.v1', style: 'cinematic', background: 'scene',
      },
    },
    templates: [{
      template_id: 'phone_metrics', name: 'Phone & metrics', description: 'Phone composition',
      canvas: { width: 1080, height: 1350 },
    }],
    catalog: {
      schema: 'ptw.studio.phone-metrics-catalog.v2', template_id: 'phone_metrics',
      template_version: 23, canvas: { width: 1080, height: 1350 },
      semantic_roles: [], components: [], asset_slots: {}, sha256: 'b'.repeat(64),
      variation: {
        optional_elements: ['offer', 'post_logo', 'phone_logo', 'cta'], brand: 'Natal', device_pose: 'front_facing_upright',
        device_rotation_degrees: 0,
        background_textures: ['none', 'grain', 'concrete', 'travertine'],
        copy_background_textures: ['none', 'grain', 'concrete', 'travertine'],
        phone_screen_textures: ['none', 'grain', 'paper', 'frosted'],
        metric_card_styles: ['filled', 'outlined'], metric_card_shapes: ['square', 'rounded', 'pill'],
        phone_button_styles: ['filled', 'elevated', 'outlined', 'text'],
        phone_button_shapes: ['square', 'rounded', 'pill'],
        font_families: ['Inter', 'Roboto Condensed', 'Manrope', 'Montserrat', 'Source Sans 3', 'Oswald', 'Cormorant Garamond', 'Cormorant Garamond Italic', 'Lora', 'Lora Italic'],
        typography: {
          offer: { minimum: 16, maximum: 42, default: 23 },
          hero_title: { minimum: 42, maximum: 110, default: 76 },
          supporting_text: { minimum: 20, maximum: 46, default: 29 },
          cta: { minimum: 20, maximum: 52, default: 34 },
          metric_value: { minimum: 20, maximum: 56, default: 43 },
          metric_label: { minimum: 14, maximum: 36, default: 22 },
          phone_title: { minimum: 24, maximum: 72, default: 55 },
          phone_buttons: { minimum: 16, maximum: 36, default: 28 },
        },
      },
    },
    state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
    configuration: {
      schema: 'ptw.studio.phone-metrics-config.v11',
      background: { color: '#F4F5F2', texture: 'concrete', texture_intensity: 0.13 },
      copy_background: { texture: 'none' }, logo: { enabled: true }, offer: { enabled: true },
      cta: { enabled: true, background_color: '#316CFF', text_color: '#FFFFFF' },
      hero_title: { highlight_color: '#FF30E8' },
      supporting_text: { highlight_color: '#1675F8' },
      typography: Object.fromEntries([
        'offer', 'hero_title', 'supporting_text', 'cta', 'metric_value', 'metric_label',
        'phone_title', 'phone_buttons',
      ].map((role) => [role, { font_family: 'Manrope', font_size: 28 }])),
      phone_screen: { texture: 'grain', logo_enabled: true },
      metric_cards: [1, 2, 3].map(() => ({
        style: 'filled', text_color: '#FFFFFF', background_color: '#2457C8', shape: 'rounded',
      })),
      phone_buttons: [
        { style: 'filled', text_color: '#FFFFFF', background_color: '#1675F8', shape: 'pill' },
        { style: 'elevated', text_color: '#1675F8', background_color: '#FFFFFF', shape: 'pill' },
        { style: 'text', text_color: '#1675F8', background_color: '#FFFFFF', shape: 'pill' },
      ],
      device: { x: 610, y: 90, width: 410, rotation: 0 },
    },
    content: {
      schema: 'ptw.studio.phone-metrics-content.v2', offer: 'NATAL',
      hero_title: 'A focused promise', supporting_text: 'One clear next step.',
      cta: 'START NOW', stats: [
        { value: '1', label: 'first' }, { value: '2', label: 'second' },
        { value: '3', label: 'third' },
      ], phone_hero_title: '', phone_buttons: ['Create account', 'Sign in', 'Maybe later'],
    },
    component_settings: { sha256: 'd'.repeat(64) },
    assets: [{
      slot: 'phone_screen', role: 'device_screen', description: 'Current phone hero',
      allowed_mime_types: ['image/png'], editable: false, available: true,
      mime_type: 'image/png', sha256: imageDigests[0], byte_count: imageBytes[0].length,
      source: { visual_direction: 'Original translucent form.' },
    }],
    phone_screen_history: [{
      mime_type: 'image/png', sha256: imageDigests[0], width: 1024, height: 1024,
      byte_count: imageBytes[0].length, source: { visual_direction: 'Original translucent form.' },
      selected: true,
    }],
    pexels_available: false, phone_screen_generation_available: true, versions: [],
  }
}

test('a delayed rejected Save is brought into view and keeps the owner draft', async ({ page }) => {
  const current = phoneDetail()
  let releaseSave: (() => void) | undefined
  let saveCount = 0
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/projects') return route.fulfill({ json: { items: [{
      project_id: projectId, name: 'Save feedback', latest_brief_status: 'completed', brief_count: 1,
    }] } })
    if (path === `/api/v1/studio/projects/${projectId}/creatives`) return route.fulfill({ json: { items: [current] } })
    if (path === creativePath) return route.fulfill({ json: current })
    if (path === `${creativePath}/save`) {
      saveCount += 1
      expect(route.request().postDataJSON().content.hero_title).toBe('Keep this owner edit')
      await new Promise<void>(resolve => { releaseSave = resolve })
      return route.fulfill({ status: 409, json: { detail: 'Studio state changed; reload before saving' } })
    }
    if (path === `${creativePath}/preview`) return route.fulfill({
      contentType: 'image/png', body: previewBytes,
      headers: { 'X-PTW-Content-SHA256': previewDigest },
    })
    if (path.includes('/phone-screen/history/')) return route.fulfill({
      contentType: 'image/png', body: imageBytes[0],
      headers: { 'X-PTW-Content-SHA256': imageDigests[0] },
    })
    return route.fulfill({ status: 404, json: { detail: 'Not found' } })
  })
  await page.goto(`/?e2e=1&page=posts&project=${projectId}&creative=${creativeId}`)
  await page.getByRole('textbox', { name: 'Headline', exact: true }).fill('Keep this owner edit')
  await page.getByRole('button', { name: 'Save creative', exact: true }).click()
  await expect.poll(() => Boolean(releaseSave)).toBe(true)
  // Model an owner continuing to inspect a long mobile editor while Save waits.
  await page.getByRole('textbox', { name: 'Phone button 3 text', exact: true }).scrollIntoViewIfNeeded()
  releaseSave!()
  const feedback = page.locator('.studio-action-feedback')
  await expect(feedback).toBeFocused()
  await expect(feedback.getByText('Save was not confirmed. Your edits are still in the editor.', { exact: true })).toBeInViewport()
  await expect(feedback).toContainText('HTTP 409')
  await expect(page.getByRole('textbox', { name: 'Headline', exact: true })).toHaveValue('Keep this owner edit')
  await expect(page.getByText('Creative saved and Project learning updated.', { exact: true })).toHaveCount(0)
  expect(saveCount).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `.local/save-error-${test.info().project.name}.png` })
})

test('runs the Phone Metrics browser UI direction and image workflow', async ({ page }) => {
  let current: any = phoneDetail()
  const directionRequests: any[] = []
  const generationRequests: any[] = []
  const selectionRequests: any[] = []
  const previewRequests: any[] = []
  let generated = 0

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })
    if (url.pathname === '/api/v1/projects') return json({ items: [{
      project_id: projectId, request_id: projectId, owner_idea_source_id: briefId,
      name: 'Phone flow', name_source: 'owner', requested_by: 'test',
      latest_brief_id: briefId, latest_brief_status: 'completed', brief_count: 1,
      created_at: '2026-09-08T00:00:00Z', updated_at: '2026-09-08T00:00:00Z',
    }], next_cursor: null })
    if (url.pathname === `/api/v1/studio/projects/${projectId}/creatives` && method === 'GET') {
      return json({ items: [current], next_cursor: null })
    }
    if (url.pathname === creativePath && method === 'GET') return json(current)
    if (url.pathname === `${creativePath}/preview` && method === 'POST') {
      previewRequests.push(route.request().postDataJSON())
      return route.fulfill({
        status: 200, contentType: 'image/png', body: previewBytes,
        headers: { 'X-PTW-Content-SHA256': previewDigest, 'Cache-Control': 'private, no-store' },
      })
    }
    if (url.pathname.startsWith(`${creativePath}/phone-screen/history/`) && method === 'GET') {
      const digest = url.pathname.split('/').at(-1) || ''
      const index = imageDigests.indexOf(digest)
      return index < 0 ? json({ detail: 'not found' }, 404) : route.fulfill({
        status: 200, contentType: 'image/png', body: imageBytes[index],
        headers: { ETag: `"${digest}"`, 'X-PTW-Content-SHA256': digest, 'Cache-Control': 'private, no-store' },
      })
    }
    if (url.pathname === `${creativePath}/creative-direction` && method === 'POST') {
      const body = route.request().postDataJSON()
      directionRequests.push(body)
      current = { ...current, generation: { ...current.generation, creative_direction: body.creative_direction } }
      return json(current)
    }
    if (url.pathname === `${creativePath}/phone-screen/generate` && method === 'POST') {
      const body = route.request().postDataJSON()
      generationRequests.push(body)
      generated += 1
      const imageIndex = generated
      const record = {
        mime_type: 'image/png', sha256: imageDigests[imageIndex], width: 1024, height: 1024,
        byte_count: imageBytes[imageIndex].length,
        source: {
          visual_direction: body.visual_direction,
          generation_mode: body.enhance_current ? 'enhance_current' : 'generate_new',
          creative_direction: current.generation.creative_direction,
        },
        selected: true,
      }
      current = {
        ...current, state_sha256: String(generated + 1).repeat(64),
        assets: [{
          ...current.assets[0], sha256: record.sha256, byte_count: record.byte_count,
          source: record.source,
        }],
        phone_screen_history: [record, ...current.phone_screen_history.map((item: any) => ({
          ...item, selected: false,
        }))].slice(0, 3),
      }
      return json(current)
    }
    if (url.pathname === `${creativePath}/phone-screen/select` && method === 'POST') {
      const body = route.request().postDataJSON()
      selectionRequests.push(body)
      const selected = current.phone_screen_history.find((item: any) => item.sha256 === body.sha256)
      current = {
        ...current, state_sha256: '7'.repeat(64),
        assets: [{ ...current.assets[0], sha256: selected.sha256, source: selected.source }],
        phone_screen_history: current.phone_screen_history.map((item: any) => ({
          ...item, selected: item.sha256 === body.sha256,
        })),
      }
      return json(current)
    }
    return json({ detail: `Unhandled ${method} ${url.pathname}` }, 404)
  })

  await page.goto(`/?e2e=1&page=posts&project=${projectId}&creative=${creativeId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Generate or enhance hero artwork' })).toBeVisible()

  await page.emulateMedia({ reducedMotion: 'reduce' })
  const updatePreview = page.getByRole('button', { name: 'Update preview' })
  await expect(updatePreview).toBeEnabled()
  const initialPreviewCount = previewRequests.length
  await page.getByLabel('CTA label', { exact: true }).fill('')
  await page.getByRole('textbox', { name: 'Headline', exact: true }).fill('Draft headline')
  await page.waitForTimeout(350)
  expect(previewRequests).toHaveLength(initialPreviewCount)
  await expect(page.getByText(/Changes not previewed/)).toBeVisible()
  await expect(page.getByRole('img', { name: 'Natal phone and metrics creative' })).toBeVisible()
  await updatePreview.focus()
  await expect(updatePreview).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByText('Preview up to date', { exact: true })).toBeVisible()
  expect(previewRequests.at(-1).content.cta).toBe('')
  await updatePreview.screenshot({ path: `.local/manual-preview-${test.info().project.name}.png` })

  const visualMode = page.getByRole('combobox', { name: 'Visual mode' })
  await visualMode.focus()
  await expect(visualMode).toBeFocused()
  await visualMode.selectOption('image')
  await page.getByRole('button', { name: 'Update preview' }).click()
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({ visual_mode: 'image' })
  await visualMode.screenshot({ path: `.local/post-visual-mode-${test.info().project.name}.png` })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await visualMode.selectOption('phone')
  await page.getByRole('button', { name: 'Update preview' }).click()
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({ visual_mode: 'phone' })

  const postLogo = page.getByLabel('Show post logo')
  const phoneLogo = page.getByLabel('Show in-phone logo')
  await expect(postLogo).toBeChecked()
  await expect(phoneLogo).toBeChecked()
  const headline = page.getByLabel('Headline', { exact: true })
  await headline.fill('A focused promise')
  await headline.evaluate((field: HTMLTextAreaElement) => field.setSelectionRange(0, 1))
  await page.getByLabel('Bold selected headline words').click()
  await expect(headline).toHaveValue('**A** focused promise')
  await expect.poll(() => headline.evaluate((field: HTMLTextAreaElement) => [field.selectionStart, field.selectionEnd])).toEqual([2, 3])
  await headline.evaluate((field: HTMLTextAreaElement) => {
    const start = field.value.indexOf('focused')
    field.setSelectionRange(start, start + 'focused'.length)
  })
  await page.getByLabel('Colour selected headline words').click()
  await page.getByLabel('Headline highlight color').fill('#21a179')
  await updatePreview.click()
  await expect.poll(() => previewRequests.at(-1)).toMatchObject({
    configuration: { hero_title: { highlight_color: '#21A179' } },
    content: { hero_title: '**A** ==focused== promise' },
  })
  const bottomCta = page.getByLabel('Show bottom CTA')
  await expect(bottomCta).toBeChecked()
  await bottomCta.uncheck()
  await expect(page.getByLabel('CTA label')).toHaveCount(0)
  await updatePreview.click()
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({
    cta: { enabled: false },
  })
  await bottomCta.check()
  await page.getByLabel('CTA label').fill('BOOK A FREE CONSULTATION')
  await page.getByLabel('CTA background color').fill('#e2385a')
  await page.getByLabel('CTA text color').fill('#f9f4ea')
  await updatePreview.click()
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({
    cta: { enabled: true, background_color: '#E2385A', text_color: '#F9F4EA' },
  })
  await postLogo.focus()
  await page.keyboard.press('Space')
  await phoneLogo.focus()
  await page.keyboard.press('Space')
  await expect(postLogo).not.toBeChecked()
  await expect(phoneLogo).not.toBeChecked()
  await page.getByRole('button', { name: 'Update preview' }).click()
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({
    logo: { enabled: false },
    phone_screen: { logo_enabled: false },
  })
  await expect(page.getByText('Hidden from the post canvas')).toBeVisible()
  await expect(page.getByText('Hidden from the app screen')).toBeVisible()
  await postLogo.check()
  await phoneLogo.check()
  await expect(postLogo).toBeChecked()
  await expect(phoneLogo).toBeChecked()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.getByRole('button', { name: 'Reset image direction' }).click()
  await expect(page.getByRole('button', { name: 'Generate & apply' })).toBeDisabled()
  await page.locator('input[value="minimal_sculptural"]').check()
  await page.locator('input[value="isolated_key_element"]').check()
  await page.getByRole('button', { name: 'Save new direction' }).click()
  await expect(page.getByRole('status')).toContainText('Image direction saved')
  expect(directionRequests).toEqual([{
    base_sha256: 'a'.repeat(64),
    creative_direction: {
      schema: 'ptw.studio.phone-hero-direction.v1',
      style: 'minimal_sculptural', background: 'isolated_key_element',
    },
  }])

  await page.getByLabel('Enhance current image').uncheck()
  await page.getByLabel('iPhone visual direction').fill('A clean sculptural object in quiet blue studio light.')
  await page.getByRole('button', { name: 'Generate & apply' }).click()
  await expect(page.getByRole('status')).toContainText('New iPhone hero visual generated')
  expect(generationRequests[0]).toMatchObject({ enhance_current: false })

  await page.getByLabel('iPhone visual direction').fill('Preserve the object and improve its material detail.')
  await page.getByRole('button', { name: 'Generate & apply' }).click()
  await expect(page.getByRole('status')).toContainText('Current iPhone hero visual enhanced')
  expect(generationRequests[1]).toMatchObject({ enhance_current: true })
  expect(current.phone_screen_history).toHaveLength(3)
  expect(current.phone_screen_history[0].source.creative_direction.style).toBe('minimal_sculptural')

  await page.getByRole('radio', { name: 'Select iPhone image 3' }).click()
  await expect(page.getByRole('status')).toContainText('Selected iPhone image applied')
  expect(selectionRequests).toHaveLength(1)
  expect(selectionRequests[0].sha256).toBe(imageDigests[0])
  await expect(page.getByRole('radio', { name: 'iPhone image 3, current' })).toHaveAttribute('aria-checked', 'true')
  const reference = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  await page.getByLabel(/Upload reference image/).setInputFiles({ name: 'my-reference.png', mimeType: 'image/png', buffer: reference })
  await expect(page.getByRole('img', { name: 'Reference preview' })).toBeVisible()
  await expect(page.getByLabel('Enhance current image')).toBeDisabled()
  await page.getByRole('button', { name: 'Remove reference' }).focus()
  await expect(page.getByRole('button', { name: 'Remove reference' })).toBeFocused()
  await page.locator(".phone-screen-rule").screenshot({ path: `.local/image-reference-post-${test.info().project.name}.png` })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Generate & apply' }).click()
  await expect(page.getByRole('button', { name: 'Remove reference' })).toHaveCount(0)
  expect(generationRequests.at(-1)).toMatchObject({ enhance_current: false, reference_image: { mime_type: 'image/png', bytes_base64: reference.toString('base64') } })

})

for (const configured of [true, false]) {
test(`approved Instagram Post and exact website Ads handoff (${configured ? 'mocked Meta' : 'offline export'})`, async ({ page }) => {
  const current: any = phoneDetail()
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64')
  const digest = createHash('sha256').update(png).digest('hex')
  current.versions = [1, 2].map(version => ({ version, change_note: `Approved ${version}`, render_sha256: digest }))
  current.approved_version_count = 2
  const sources = current.versions.map((item: any) => ({ ...item, creative_id: creativeId, creative_ordinal: 1, template_id: 'phone_metrics', version_sha256: digest, defaults: { headline: `Approved title ${item.version}`, primary_text: 'Approved body', welcome_message: 'Hello' } }))
  const landing = { publication_id: projectId, event_id: briefId, landing_version: 1, landing_version_sha256: digest, canonical_url: 'https://natal-service.com/la/example' }
  const publications: any[] = []
  const adRequests: any[] = []
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/v1/projects') return json({ items: [{ project_id: projectId, name: 'Publishing test', name_source: 'owner', brief_count: 1 }] })
    if (path === `/api/v1/studio/projects/${projectId}/creatives`) return json({ items: [current] })
    if (path === creativePath) return json(current)
    if (path.startsWith(creativePath) && (path.endsWith('/render') || path.endsWith('/preview') || path.includes('/history/'))) return route.fulfill({ contentType: 'image/png', body: png, headers: { 'X-PTW-Content-SHA256': digest } })
    if (path === `/api/v1/instagram/projects/${projectId}`) return json({ connection: { configured, verified: configured, media_ready: configured, graph_version: 'v26.0', instagram: { id: '789', username: 'example' } }, sources, landing, publications })
    if (path === `/api/v1/instagram/projects/${projectId}/publications`) {
      if (method === 'GET') return json({ items: publications })
      const request = route.request().postDataJSON()
      expect(request.version).toBe(1)
      expect(request.caption).toBe('Reviewed Instagram caption')
      publications.push({ publication_id: projectId, request_id: request.request_id, specification: { ...request }, status: 'published', publish_started: true, media_id: 'media-1', permalink: 'https://www.instagram.com/p/example/' })
      return json({ publication: publications[0], created: true }, 202)
    }
    if (path === `/api/v1/ads/projects/${projectId}`) return json({ schema: 'ptw.meta-ads.workspace.v1', project_id: projectId, project_name: 'Publishing test', connection: { configured, verified: configured, graph_version: 'v26.0', account: { id: '123', currency: 'USD' }, instagram: { id: '789', username: 'example' }, pixel: configured ? { id: '101', name: 'Website Pixel' } : null }, sources, landing, deployments: [], experiment: null, presets: [{ preset_id: briefId, version: 1, specification_sha256: digest, specification: { name: 'Local audience', countries: ['UA'], age_min: 25, age_max: 44, gender: 'all', daily_budget_minor: 500 } }] })
    if (path.endsWith('/deployments') && method === 'POST') { adRequests.push(route.request().postDataJSON()); return json({ deployment: {}, created: true }, 202) }
    return json({ detail: 'not found' }, 404)
  })
  await page.goto(`/?e2e=1&page=posts&project=${projectId}&creative=${creativeId}`)
  await page.evaluate(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Publish approved Post' })).toBeVisible()
  await expect(page.getByLabel('CTA label', { exact: true })).toHaveValue('START NOW')
  await page.getByLabel('Approved version').selectOption('1')
  await page.getByRole('button', { name: 'Publish to Instagram', exact: true }).click()
  await expect(page.getByLabel('Instagram caption')).toHaveValue('Approved title 1\n\nApproved body')
  await page.getByLabel('Instagram caption').fill('Reviewed Instagram caption')
  if (configured) {
    await page.getByRole('button', { name: 'Publish now', exact: true }).click()
    await expect(page.getByRole('link', { name: 'View published post' })).toHaveAttribute('href', 'https://www.instagram.com/p/example/')
  } else {
    await expect(page.getByRole('button', { name: 'Publish now', exact: true })).toBeDisabled()
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download image', exact: true }).click()
    const download = await downloadEvent
    expect(download.suggestedFilename()).toBe('post-v1.png')
    const stream = await download.createReadStream()
    const bytes: Buffer[] = []
    for await (const chunk of stream!) bytes.push(Buffer.from(chunk))
    expect(Buffer.concat(bytes)).toEqual(png)
    await expect(page.getByRole('status')).toContainText('Exported')
    await expect(page.getByRole('link', { name: 'View published post' })).toHaveCount(0)
  }
  await expect(page.getByRole('button', { name: 'Download image', exact: true })).toBeEnabled()
  await page.getByRole('link', { name: 'Create Instagram ad', exact: true }).click()
  await expect(page.getByLabel('Destination')).toHaveValue('WEBSITE')
  await expect(page.getByLabel('Headline')).toHaveValue('Approved title 1')
  await expect(page.getByLabel('Initial Direct message')).toHaveCount(0)
  await expect(page.getByRole('link', { name: landing.canonical_url, exact: true })).toBeVisible()
  if (configured) {
    await expect(page.getByText('LANDING_PAGE_VIEWS')).toBeVisible()
    await expect(page.getByText('Website Pixel', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Create PAUSED campaign structure' }).click()
    await expect.poll(() => adRequests.length).toBe(1)
    expect(adRequests[0]).toMatchObject({ creative_id: creativeId, version: 1, destination_type: 'WEBSITE', landing_event_id: briefId })
    expect(adRequests[0]).not.toHaveProperty('welcome_message')
  } else {
    await expect(page.getByRole('button', { name: 'Create PAUSED campaign structure' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Download image', exact: true })).toBeEnabled()
    expect(adRequests).toHaveLength(0)
  }
  await page.screenshot({ path: `.local/publishing-${configured ? 'ready' : 'offline'}-${test.info().project.name}.png`, fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

}
