import { expect, test } from '@playwright/test'

const runId = '01234567-89ab-7def-8123-456789abcdef'
const stages = [
  'OWNER_CAPTURE', 'OWNER_DNA', 'QUERY_PLAN', 'SERP_DISCOVERY', 'COMPETITOR_SELECTION',
  'COMPETITOR_EVIDENCE', 'COMPETITOR_DOSSIERS', 'OPPORTUNITY_MATRIX', 'TREND_QUERY_PLAN',
  'GOOGLE_TRENDS_RESEARCH', 'TREND_GATE', 'SYNTHESIS_PACKET', 'IDEA_EXPANSION',
  'IDEA_CLUSTERING', 'IDEA_EVALUATION', 'FINAL_SHORTLIST',
]

test.beforeEach(async ({ page }) => {
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
      health: { commander: 'ok' }, pending_reviews: 0,
      jobs: { active: 0, blocked: 0, last_deploy: null }, laval_runs: { total: 1, active: 0, completed: 1 },
    })
    if (url.pathname === '/api/v1/laval/providers') return json({
      llm_provider: 'bridge', search_provider: 'fixture', trend_provider: 'fixture',
      search_live_ready: false, trends_live_ready: false, demo_available: true,
      default_evidence_mode: 'demo_fixture', max_spend_usd: .05, reserved_spend_usd: .04,
      missing: ['dataforseo_credentials', 'google_trends_alpha_bridge'],
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
    if (url.pathname.endsWith('/show')) return json({ output: { proof: 'visible artifact' } })
    if (url.pathname.endsWith('/export')) return route.fulfill({ status: 200, contentType: url.searchParams.get('format') === 'md' ? 'text/markdown' : 'application/json', body: url.searchParams.get('format') === 'md' ? '# DEMO — NO LIVE RESEARCH' : '{"mode":"demo_fixture"}' })
    if (url.pathname.endsWith('/notify')) return json({ queued: 1 })
    if (route.request().method() === 'POST') return json({ ok: true })
    return json({})
  })
})

test('renders the authenticated owner console without horizontal overflow', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByText('sgolovaschuk@gmail.com')).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
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
  await page.getByRole('button', { name: /Створити чітко позначене демо/ }).click()
  await expect(page.getByText(/Демо-запуск створено/)).toBeVisible()

  await page.getByRole('button', { name: /OWNER CAPTURE/ }).click()
  await expect(page.getByText(/visible artifact/)).toBeVisible()
  await expect(page.locator('.laval-inspector')).toBeInViewport()
  await page.getByRole('button', { name: /Перезапустити/ }).click()

  await page.getByRole('button', { name: 'MD' }).click()
  const preview = page.getByRole('dialog', { name: 'Перегляд експорту' })
  await expect(preview).toBeVisible()
  if (browserName === 'webkit') await expect(page.getByText(/DEMO — NO LIVE RESEARCH/).last()).toBeVisible()
  await preview.getByRole('button', { name: 'Закрити' }).click()
  await page.getByRole('button', { name: /Статус у Telegram/ }).click()
  await expect(page.getByText(/всі 16 етапів поставлено в чергу Telegram/)).toBeVisible()
  await page.getByRole('button', { name: /Схвалити й продовжити/ }).click()
  await page.getByRole('button', { name: 'Пости' }).last().click()
  await expect(page.getByRole('heading', { name: 'Пости' })).toBeVisible()
})
