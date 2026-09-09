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
        optional_elements: ['offer', 'post_logo', 'phone_logo'], brand: 'Natal', device_pose: 'front_facing_upright',
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
      schema: 'ptw.studio.phone-metrics-config.v9',
      background: { color: '#F4F5F2', texture: 'concrete', texture_intensity: 0.13 },
      copy_background: { texture: 'none' }, logo: { enabled: true }, offer: { enabled: true },
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
  const visualMode = page.getByRole('combobox', { name: 'Visual mode' })
  await visualMode.focus()
  await expect(visualMode).toBeFocused()
  await visualMode.selectOption('image')
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({ visual_mode: 'image' })
  await visualMode.screenshot({ path: `.local/post-visual-mode-${test.info().project.name}.png` })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await visualMode.selectOption('phone')
  await expect.poll(() => previewRequests.at(-1)?.configuration).toMatchObject({ visual_mode: 'phone' })

  const postLogo = page.getByLabel('Show post logo')
  const phoneLogo = page.getByLabel('Show in-phone logo')
  await expect(postLogo).toBeChecked()
  await expect(phoneLogo).toBeChecked()
  await postLogo.focus()
  await page.keyboard.press('Space')
  await phoneLogo.focus()
  await page.keyboard.press('Space')
  await expect(postLogo).not.toBeChecked()
  await expect(phoneLogo).not.toBeChecked()
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
