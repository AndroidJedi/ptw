import { expect, test } from '@playwright/test'

const runId = '01234567-89ab-7def-8123-456789abcdef'
const brandRunId = '11234567-89ab-7def-8123-456789abcdef'
const brandKitId = '21234567-89ab-7def-8123-456789abcdef'
const brandStages = [
  'CASE_SNAPSHOT', 'REFERENCE_PLAN', 'REFERENCE_COLLECTION', 'DESIGN_PRINCIPLES', 'BRAND_BRIEF',
  'DIRECTION_SYNTHESIS', 'DIRECTION_EVALUATION', 'LOGO_GENERATION', 'OWNER_REVIEW', 'KIT_ASSEMBLY',
]
const stages = [
  'OWNER_CAPTURE', 'OWNER_DNA', 'QUERY_PLAN', 'SERP_DISCOVERY', 'COMPETITOR_SELECTION',
  'COMPETITOR_EVIDENCE', 'COMPETITOR_DOSSIERS', 'OPPORTUNITY_MATRIX', 'MARKET_SIGNAL_PLAN',
  'MARKET_SIGNAL_COLLECTION', 'MARKET_SIGNAL_GATE', 'SYNTHESIS_PACKET', 'IDEA_EXPANSION',
  'IDEA_CLUSTERING', 'IDEA_EVALUATION', 'FINAL_SHORTLIST',
]

test.beforeEach(async ({ page }) => {
  let brandApproved = false
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })
    Object.defineProperty(navigator, 'canShare', { configurable: true, value: undefined })
  })
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const json = (value: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })
    if (url.pathname === '/api/v1/overview') return json({
      mission: { name: { en: 'Mission', uk: 'Місія' }, deadline_at: '2029-08-18T00:00:00Z' },
      health: { commander: 'ok' },
      jobs: { active: 0, blocked: 0, last_deploy: null }, laval_runs: { total: 1, active: 0, completed: 1 },
      branding_runs: { total: 1, active: 1, completed: 0 },
    })
    if (url.pathname === '/api/v1/branding/providers') return json({
      ready: true, provider: 'openai_brand', image_model: 'gpt-image-2', paid_seo_enabled: false,
    })
    if (url.pathname === '/api/v1/branding/cases') return json({ items: [{
      idea_run_id: runId, owner_idea: 'Make credible progress visible.', created_at: '2026-08-20T00:00:00Z',
      theses: [{ id: runId, title: { en: 'Proof journey', uk: 'Шлях доказів' }, target_user: { en: 'Goal setters', uk: 'Люди з метою' }, recommended: true, verdict: 'survives' }],
      mechanisms: [], quality: { successful: 9, attempted: 10 }, recommended_thesis_id: runId, active_brand_kit: null,
    }] })
    if (url.pathname === '/api/v1/branding/runs' && route.request().method() === 'POST') return json({ run_id: brandRunId, status: 'running' })
    if (url.pathname === '/api/v1/branding/runs') return json({ items: [{
      id: brandRunId, source_laval_run_id: runId, status: brandApproved ? 'completed' : 'awaiting_review',
      current_stage: brandApproved ? 'KIT_ASSEMBLY' : 'OWNER_REVIEW', owner_preview: 'Make credible progress visible.',
      completed_stages: brandApproved ? 10 : 8, created_at: '', updated_at: '', source_stale: false,
      source_snapshot: { owner_idea: 'Make credible progress visible.', theses: [], mechanisms: [] }, constraints_text: '', provider_snapshot: {},
    }] })
    const palette = {
      light: { primary: '#1457d9', secondary: '#6938b8', accent: '#d34100', background: '#ffffff', surface: '#f1f5fb', text: '#111827', muted: '#566174', success: '#087a55', warning: '#855400', error: '#b42336' },
      dark: { primary: '#79a7ff', secondary: '#c3a6ff', accent: '#ff9564', background: '#08101e', surface: '#121d31', text: '#f8faff', muted: '#b0bdd2', success: '#58d9aa', warning: '#ffd16e', error: '#ff7b8b' },
    }
    const directions = ['Proofrise', 'Momentum', 'Verity Loop'].map((name, index) => ({
      id: `${index + 3}1234567-89ab-7def-8123-456789abcdef`, ordinal: index + 1, name, status: 'reviewed',
      manifest: { name, tagline: { en: 'Make progress visible.', uk: 'Зробіть прогрес видимим.' }, positioning: { en: 'Credible momentum.', uk: 'Достовірний прогрес.' }, personality: ['credible'], palette, typography: { display: 'Manrope', body: 'Inter', mono: 'IBM Plex Mono' }, design_principles: ['Visible momentum', 'Earned anticipation', 'Calm action'], retention_patterns: ['proof timeline'], ui_system: {} },
      evaluation: { passed: true, checks: { contrast: { passed: true }, font_coverage: { passed: true }, evidence_lineage: { passed: true } } },
      artifact_digest: `${index + 1}`.repeat(64), logo_asset: { digest: `${index + 1}`.repeat(64), mime_type: 'image/png', width: 1024, height: 1024, url: `/api/v1/branding/assets/${`${index + 1}`.repeat(64)}`, cache: 'private, no-store' },
      latest_feedback_id: `${index + 6}1234567-89ab-7def-8123-456789abcdef`, rating: 4, overall_comment: 'Current review', reviewed_at: '2026-08-20T00:00:00Z',
    }))
    if (url.pathname === `/api/v1/branding/runs/${brandRunId}`) return json({
      run: { id: brandRunId, source_laval_run_id: runId, status: brandApproved ? 'completed' : 'awaiting_review', current_stage: brandApproved ? 'KIT_ASSEMBLY' : 'OWNER_REVIEW', source_snapshot: { owner_idea: 'Make credible progress visible.', theses: [], mechanisms: [] }, source_stale: false, constraints_text: '', provider_snapshot: {}, commander_brand_kit_id: brandApproved ? brandKitId : null, created_at: '', updated_at: '' },
      stages: brandStages.map((stage, ordinal) => ({ stage, ordinal, status: ordinal < 8 || brandApproved ? 'completed' : ordinal === 8 ? 'paused' : 'pending', attempt: ordinal < 8 ? 1 : 0, metrics: ordinal === 2 ? { paid_seo_calls: 0 } : {} })),
      directions, cost: { items: [], total_usd: 0 }, runner_active: false,
    })
    if (url.pathname === `/api/v1/branding/runs/${brandRunId}/show`) return json({ stage: url.searchParams.get('stage'), artifact: { paid_seo_calls: 0 } })
    if (url.pathname.includes(`/api/v1/branding/runs/${brandRunId}/directions/`) && url.pathname.endsWith('/reviews')) return json({ items: [{ feedback_id: '61234567-89ab-7def-8123-456789abcdef', rating: 4, overall_comment: 'Current review', annotations: [], created_at: '2026-08-20T00:00:00Z' }] })
    if (url.pathname.includes(`/api/v1/branding/runs/${brandRunId}/directions/`) && url.pathname.endsWith('/review') && route.request().method() === 'POST') return json({ feedback_id: '71234567-89ab-7def-8123-456789abcdef', weight_update_ids: [], direction_id: directions[0].id })
    if (url.pathname === `/api/v1/branding/runs/${brandRunId}/approve` && route.request().method() === 'POST') {
      brandApproved = true
      return json({ id: brandKitId, commander_brand_kit_id: brandKitId, name: 'Proofrise', status: 'approved', source_stale: false, zip_digest: 'a'.repeat(64), approved_at: '2026-08-20T00:00:00Z', manifest: directions[0].manifest, download: { digest: 'a'.repeat(64), mime_type: 'application/zip', url: `/api/v1/branding/kits/${brandKitId}/download`, cache: 'private, no-store' } })
    }
    if (url.pathname === `/api/v1/branding/kits/${brandKitId}`) return json({ id: brandKitId, commander_brand_kit_id: brandKitId, name: 'Proofrise', status: 'approved', source_stale: false, zip_digest: 'a'.repeat(64), approved_at: '2026-08-20T00:00:00Z', manifest: directions[0].manifest, download: { digest: 'a'.repeat(64), mime_type: 'application/zip', url: `/api/v1/branding/kits/${brandKitId}/download`, cache: 'private, no-store' } })
    if (url.pathname === `/api/v1/branding/kits/${brandKitId}/download`) return route.fulfill({ status: 200, contentType: 'application/zip', body: Buffer.from('PK-fixture') })
    if (url.pathname.startsWith('/api/v1/branding/assets/')) return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+X3L8WQAAAABJRU5ErkJggg==', 'base64') })
    if (url.pathname === '/api/v1/laval/providers') return json({
      llm_provider: 'bridge', search_provider: 'fixture', trend_provider: 'fixture',
      search_live_ready: false, trends_live_ready: false, demo_available: true,
      default_evidence_mode: 'demo_fixture', max_spend_usd: .05, reserved_spend_usd: .04,
      missing: ['dataforseo_credentials'],
      optional_sources: { google_trends: { ready: false, required: false } },
    })
    if (url.pathname === '/api/v1/laval/runs' && route.request().method() === 'POST') return json({ run_id: runId })
    if (url.pathname === '/api/v1/laval/runs') return json({ items: [{
      id: runId, owner_idea_id: runId, status: 'paused', current_stage: 'COMPETITOR_SELECTION',
      approval_mode: 'manual', approval_gates: ['COMPETITOR_SELECTION'], owner_preview: 'Auditable demo',
      completed_stages: 5, variant_count: 0, config: { countries: [{ code: 'US' }] },
      evidence_mode: 'demo_fixture', provider_snapshot: { search: 'fixture', trends: 'fixture' },
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '', updated_at: '',
    }] })
    if (url.pathname === `/api/v1/laval/runs/${runId}`) return json({
      run: {
        id: runId, owner_idea_id: runId, status: 'paused', current_stage: 'COMPETITOR_SELECTION',
        approval_mode: 'manual', approval_gates: ['COMPETITOR_SELECTION'], config: { countries: [{ code: 'US' }] },
        evidence_mode: 'demo_fixture', provider_snapshot: { search: 'fixture', trends: 'fixture' },
        max_spend_usd: .05, reserved_spend_usd: .04,
      },
      stages: stages.map((stage, ordinal) => ({ stage, ordinal, status: ordinal < 5 ? 'completed' : 'pending', attempt: ordinal < 5 ? 1 : 0, provider: ordinal < 5 ? 'fixture' : null, metrics: {}, input_hash: ordinal < 5 ? 'hash' : null })),
      cost: { items: [], total_usd: 0, provider_reserved_usd: 0, provider_actual_usd: 0, max_spend_usd: .05 },
    })
    if (url.pathname.endsWith('/show')) return json({ output: { raw_text: 'visible artifact' } })
    if (url.pathname.endsWith('/export')) return route.fulfill({ status: 200, contentType: url.searchParams.get('format') === 'md' ? 'text/markdown' : 'application/json', body: url.searchParams.get('format') === 'md' ? '# DEMO — NO LIVE RESEARCH' : '{"mode":"demo_fixture"}' })
    if (url.pathname === '/api/v1/jobs') return json({ items: [] })
    if (route.request().method() === 'POST') return json({ ok: true })
    return json({})
  })
})

test('renders the authenticated owner console without horizontal overflow', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByText('sgolovaschuk@gmail.com')).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
  await expect(page.locator('.bottom-nav button')).toHaveCount(5)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('reviews all Branding UI states, annotations, approval, and download', async ({ page }) => {
  await page.goto(`/?e2e=1&page=branding&run=${brandRunId}`)
  await expect(page.getByRole('heading', { name: 'Брендинг' })).toBeVisible()
  await expect(page.locator('.brand-stages button')).toHaveCount(10)
  await expect(page.locator('.brand-directions > button')).toHaveCount(3)
  await expect(page.getByText(/Domain and trademark clearance are not performed/)).toBeVisible()

  await page.locator('.brand-review-panel .image-stage svg').click({ position: { x: 120, y: 120 } })
  await page.getByLabel('Що саме треба змінити?').fill('Зробити символ щільнішим')
  await page.getByRole('button', { name: 'Додати область' }).click()
  await page.locator('.brand-review-panel .rating button').nth(4).click()
  await page.getByLabel('Загальний коментар').fill('Добре працює у favicon')
  await page.getByRole('button', { name: /Зберегти виправлення/ }).click()
  await expect(page.getByText(/Історія відгуків/)).toBeVisible()

  await page.getByRole('button', { name: /Затвердити Proofrise/ }).click()
  await expect(page.getByText('React/TypeScript UI kit готовий')).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: /Завантажити ZIP/ }).click()
  await download
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('opens the exact Laval run from a notification deep link', async ({ page }) => {
  await page.goto(`/?e2e=1&page=ideas&run=${runId}`)
  await expect(page.getByText(`RUN ${runId.slice(0, 8)}…${runId.slice(-4)}`)).toBeVisible()
  await expect(page.getByText('DEMO — NO LIVE RESEARCH').first()).toBeVisible()
})

test('exercises Laval mobile controls, demo gating, stage focus, and export fallback', async ({ page, browserName }) => {
  await page.goto('/?e2e=1')
  await page.getByRole('button', { name: 'Ідеї' }).last().click()
  await expect(page.getByText('DEMO — NO LIVE RESEARCH').first()).toBeVisible()
  await expect(page.locator('.laval-stages button')).toHaveCount(16)

  await page.getByRole('button', { name: /Нова Laval-ідея/ }).click()
  await expect(page.getByText(/DataForSEO ще не налаштовано/)).toBeVisible()
  await expect(page.getByRole('radio', { name: /Живе дослідження/ })).toBeDisabled()
  await page.getByLabel('Повний текст ідеї').fill('Mobile demo idea')
  await page.getByRole('button', { name: /Запустити демо/ }).click()
  await expect(page.getByText(/Демо запущено/)).toBeVisible()

  await page.getByRole('button', { name: /OWNER CAPTURE/ }).click()
  await expect(page.getByText(/visible artifact/)).toBeVisible()
  await expect(page.locator('.laval-inspector')).toBeInViewport()
  await page.getByRole('button', { name: /Перезапустити/ }).click()

  await expect(page.getByRole('button', { name: 'Завантажити PDF' })).toHaveCount(0)
  await page.getByRole('button', { name: 'MD' }).click()
  const preview = page.getByRole('dialog', { name: 'Перегляд експорту' })
  await expect(preview).toBeVisible()
  if (browserName === 'webkit') await expect(page.getByText(/DEMO — NO LIVE RESEARCH/).last()).toBeVisible()
  await preview.getByRole('button', { name: 'Закрити' }).click()
  await expect(page.getByRole('button', { name: /Статус у Telegram/ })).toHaveCount(0)
  await page.getByRole('button', { name: /Схвалити й продовжити/ }).click()
  await expect(page.getByRole('button', { name: 'Пости' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Завдання' }).last().click()
  await expect(page.getByRole('heading', { name: 'Завдання' })).toBeVisible()
})
