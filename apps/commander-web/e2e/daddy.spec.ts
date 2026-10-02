import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
const fixture = JSON.parse(readFileSync(new URL('./daddy-fixture.json', import.meta.url), 'utf8'))

const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGM0zPnPgA0wYRUdtBIARPEBrHUXkNsAAAAASUVORK5CYII=', 'base64')
const digest = createHash('sha256').update(image).digest('hex')
const base = `/api/v1/studio/projects/${fixture.project_id}/creatives/${fixture.creative_id}`

test('Daddy preserves copy across presets, Agent changes and explicit preview / save', async ({ page }) => {
  let current = { ...structuredClone(fixture), status: 'failed', generation: { ...fixture.generation, daddy: { phase: 'asset:scene', composed: true, corrections: 0, failure: { code: 'temporary_storage_full', slot: 'scene', provider_request_id: 1434 } } } }
  const retries: string[] = []
  const previews: Array<Record<string, any>> = []
  const saves: Array<Record<string, any>> = []
  await page.addInitScript(() => localStorage.setItem('ptw-owner-language-v1', 'en'))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ json: body })
    if (path === '/api/v1/projects') return json({ items: [{ project_id: fixture.project_id, name: 'Daddy review', latest_brief_status: 'completed', brief_count: 1 }] })
    if (path === `/api/v1/studio/projects/${fixture.project_id}/creatives`) return json({ items: [current] })
    if (path === base) return json(current)
    if (path === `${base}/retry`) {
      retries.push(route.request().postDataJSON().request_id)
      current = { ...current, status: 'draft', generation: { ...current.generation, daddy: { ...current.generation.daddy, phase: 'ready_for_manual_edit', review_mode: 'manual' } } }
      return json(current)
    }
    if (path === `${base}/agent`) {
      const body = route.request().postDataJSON()
      return json({ request_id: body.request_id, base_sha256: body.base_sha256, configuration: body.configuration,
        content: { ...body.content, supporting_text: 'A clearer supporting message' }, changed_paths: ['content.supporting_text'], image_actions: [], reply: 'Updated the supporting message.' })
    }
    if (path === `${base}/save`) {
      const body = route.request().postDataJSON(); saves.push(body)
      current = { ...current, configuration: body.configuration, content: body.content, state_sha256: 'd'.repeat(64) }
      return json({ creative: current, checkpoint_created: true, version_created: false, checkpoint: null, learning_proposal: null, project_logo_default_updated: false })
    }
    if (path === `${base}/preview` || path.includes('/presets/')) {
      if (route.request().method() === 'POST') previews.push(route.request().postDataJSON())
      return route.fulfill({ contentType: 'image/png', body: image, headers: { 'X-PTW-Content-SHA256': digest } })
    }
    return json({ items: [] })
  })
  await page.goto(`/?e2e=1&page=posts&project=${fixture.project_id}&creative=${fixture.creative_id}`)
  await expect(page.getByRole('heading', { name: 'Background image failed; your text and layout are saved' })).toBeVisible()
  await expect(page.getByText(/This preview is incomplete. The image worker ran out of temporary storage./)).toBeVisible()
  await expect(page.getByText('Incomplete preview — required images are not ready yet.')).toBeVisible()
  await page.getByRole('button', { name: 'Retry image' }).click()
  await expect(page.getByRole('heading', { name: 'Compose a Post' })).toBeVisible()
  expect(retries).toHaveLength(1)
  expect(retries[0]).toMatch(/^[a-f0-9-]{36}$/)
  await expect(page.getByAltText('Daddy Post preview')).toBeVisible()
  await expect(page.getByText('Ready for your review and manual tuning. No automatic visual polish was applied.')).toBeVisible()
  const initialPreviews = previews.length
  const copy = page.getByRole('heading', { name: 'Copy', exact: true })
  await expect(copy.locator('xpath=../..')).not.toHaveAttribute('open')
  await copy.click()
  await page.getByRole('textbox', { name: 'Headline', exact: true }).fill('Your plans. Your space.')
  expect(previews).toHaveLength(initialPreviews)
  await page.getByRole('heading', { name: 'Composition', exact: true }).click()
  await page.getByRole('button', { name: 'Phone on a blurred scene', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Headline', exact: true })).toHaveValue('Your plans. Your space.')
  await expect(page.getByRole('heading', { name: 'App screen' })).toBeVisible()
  await page.getByRole('button', { name: 'Bold text poster', exact: true }).click()
  await page.getByRole('button', { name: 'Agent mode', exact: true }).click()
  await page.getByRole('textbox', { name: 'Task', exact: true }).fill('Make the support more concrete')
  await page.getByRole('button', { name: 'Apply task' }).click()
  await expect(page.getByRole('textbox', { name: 'Supporting message', exact: true })).toHaveValue('A clearer supporting message')
  await page.getByRole('button', { name: 'Update preview', exact: true }).click()
  await expect.poll(() => previews.length).toBe(initialPreviews + 1)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(() => saves.length).toBe(1)
  expect(saves[0].content.hero_title).toBe('Your plans. Your space.')
  expect(saves[0].content.supporting_text).toBe('A clearer supporting message')
  await page.reload()
  await page.getByRole('heading', { name: 'Copy', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Headline', exact: true })).toHaveValue('Your plans. Your space.')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `.local/daddy-${test.info().project.name}.png`, fullPage: true })
})
