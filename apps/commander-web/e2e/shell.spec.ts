import { expect, test } from '@playwright/test'

const projectId = '01234567-89ab-7def-8123-456789abcdef'
const revision1 = '11234567-89ab-7def-8123-456789abcdef'
const revision2 = '21234567-89ab-7def-8123-456789abcdef'
const sourceId = '31234567-89ab-7def-8123-456789abcdef'
const draftId = '41234567-89ab-7def-8123-456789abcdef'
const snapshots = {
  product: '51234567-89ab-7def-8123-456789abcdef',
  community: '61234567-89ab-7def-8123-456789abcdef',
  waitlist: '71234567-89ab-7def-8123-456789abcdef',
}
const editedSnapshot = '81234567-89ab-7def-8123-456789abcdef'
const buildId = '91234567-89ab-7def-8123-456789abcdef'
const leadId = 'a1234567-89ab-7def-8123-456789abcdef'
const positioningProposalId = 'b1234567-89ab-7def-8123-456789abcdef'
const landingProposalId = 'c1234567-89ab-7def-8123-456789abcdef'

const claim = (text: string, sourced = true) => ({ text, source_ids: sourced ? [sourceId] : [], assumption: !sourced })
const document = {
  schema_version: 1, output_language: 'uk',
  positioning_foundation: {
    category: claim('Платформа доказового прогресу'), competitive_alternatives: [claim('Нотатки та таблиці')],
    definitive_audience: claim('Люди, яким важливо показувати перевірений прогрес'),
    jobs: [claim('Зібрати докази виконаної роботи')], pains: [claim('Прогрес важко перевірити')],
    gains: [claim('Зрозумілий наступний крок')], uvp: claim('Natal перетворює роботу на видимі докази.'),
  },
  messaging_matrix: [{ feature: claim('Стрічка доказів'), functional_benefit: claim('Зберігає результати в одному місці'), emotional_reward: claim('Дає впевненість у прогресі') }],
  landing_copy: {
    hero: { eyebrow: claim('Для людей із метою'), headline: claim('Зробіть прогрес видимим'), subheadline: claim('Natal збирає перевірені докази роботи.'), cta: claim('Залишити контакти') },
    value_sections: [1, 2, 3].map((number) => ({ title: claim(`Цінність ${number}`), body: claim(`Перевірена теза ${number}`) })),
    honest_limitation: claim('Результати для клієнтів ще не перевірені.', false),
    lead_capture_strategy: claim('Запросити контакт для раннього доступу.', false),
  },
  ad_concepts: [
    { kind: 'contextual_relatable', hook: claim('Коли прогрес розсипаний по вкладках'), body: claim('Зберіть його в Natal.'), visual_direction: claim('Спокійна сцена щоденної роботи.') },
    { kind: 'direct_problem_solution', hook: claim('Прогрес важко довести?'), body: claim('Natal збирає докази в одну стрічку.'), visual_direction: claim('Проблема та рішення поруч.') },
  ],
  aeo_faqs: [1, 2, 3].map((number) => ({ question: claim(`Питання ${number}?`), definition: claim('Natal — платформа доказового прогресу.'), data: claim('Вона збирає надані користувачем докази.'), context: claim('Результати ще потребують перевірки.', false) })),
  evidence_references: [sourceId], assumptions: ['Результати ще потребують перевірки.'],
}

test.beforeEach(async ({ page }) => {
  let created = false
  let corrected = false
  let approved = false
  let draftCreated = false
  let edited = false
  let published = false
  let leadSubmitted = false

  const revision = () => ({
    id: corrected ? revision2 : revision1, project_id: projectId,
    request_id: corrected ? revision2 : revision1, revision_number: corrected ? 2 : 1,
    base_revision_id: corrected ? revision1 : null, feedback_id: corrected ? revision2 : null,
    status: 'completed', document, document_sha256: 'd'.repeat(64), quality_gates: { passed: true },
    failure_count: 0, error_code: null, error_message: null, approved,
    created_at: '2026-08-23T10:00:00Z',
  })
  const project = () => ({
    id: projectId, request_id: projectId, owner_idea_source_id: sourceId,
    raw_idea: 'Natal makes credible progress visible.', target_country: 'US', research_language: 'en', output_language: 'uk',
    active_approved_revision_id: approved ? revision().id : null,
    latest_revision_id: revision().id, latest_revision_status: 'completed', revisions: [revision()],
    sources: [{ id: sourceId, source_type: 'owner_idea', title: 'Owner idea', source_uri: null, publisher: null, content: 'Natal makes credible progress visible.', provider: 'owner', metadata: {} }],
    created_at: '2026-08-23T10:00:00Z',
  })
  const pageContent = (templateId: keyof typeof snapshots) => ({
    schema_version: 2, template_id: templateId, language: 'uk', blocks: {
      hero: { eyebrow: 'Для людей із метою', title: 'Зробіть прогрес видимим', body: 'Natal збирає докази.', cta_label: 'Залишити контакти' },
      problem: { eyebrow: 'Проблема', title: 'Прогрес важко перевірити', body: 'Розрізнені докази створюють тертя.' },
      features: { eyebrow: 'Можливості', title: 'Одна стрічка', items: [{ title: 'Докази', description: 'Зберігайте результати.' }] },
      steps: { eyebrow: 'Кроки', title: 'Як це працює', items: [{ title: '01', description: 'Додайте доказ.' }, { title: '02', description: 'Покажіть прогрес.' }] },
      proof: { eyebrow: 'Докази', title: 'Що підтверджено', items: ['Перевірена теза 1'], empty_text: 'Результати ще не перевірені.' },
      faq: { eyebrow: 'FAQ', title: 'Перед початком', items: [{ question: 'Що таке Natal?', answer: 'Платформа доказового прогресу.' }] },
      final_cta: { title: 'Готові?', body: 'Залиште контакти.', cta_label: 'Залишити контакти' },
      lead_form: { form_id: templateId === 'product' ? 'contact_request' : templateId === 'community' ? 'community_interest' : 'waitlist', heading: 'Залиште контакти', body: 'Результати ще не перевірені.' },
    },
  })
  const draft = () => {
    const current = Object.fromEntries((Object.keys(snapshots) as Array<keyof typeof snapshots>).map((templateId) => {
      const isEdited = edited && templateId === 'community'
      return [templateId, { id: isEdited ? editedSnapshot : snapshots[templateId], draft_set_id: draftId, template_id: templateId, snapshot_number: isEdited ? 2 : 1, page_content: pageContent(templateId), page_content_sha256: 'e'.repeat(64), is_current: true }]
    }))
    return {
      id: draftId, request_id: draftId, positioning_project_id: projectId, positioning_revision_id: revision().id,
      privacy_policy_url: 'https://example.com/privacy', brief: {}, status: 'completed',
      population_summary: 'Three private variants populated.', error_message: null,
      snapshots: Object.values(current), current_snapshots: current,
    }
  }

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname === '/api/v1/positionings/catalog') return json({ default_country: 'US', default_research_language: 'en', countries: [{ code: 'US', name: 'United States' }, { code: 'UA', name: 'Ukraine' }], research_languages: [{ code: 'en', name: 'English' }, { code: 'uk', name: 'Ukrainian' }], output_languages: [{ code: 'uk', name: 'Українська' }, { code: 'en', name: 'English' }] })
    if (url.pathname === '/api/v1/positionings' && method === 'GET') return json({ items: created ? [project()] : [], next_cursor: null })
    if (url.pathname === '/api/v1/positionings' && method === 'POST') { created = true; return json({ project: project(), revision: revision(), created: true }, 202) }
    if (url.pathname === `/api/v1/positionings/${projectId}` && method === 'GET') return json(project())
    if (url.pathname === `/api/v1/positionings/${projectId}/skill-proposals`) return json({ items: corrected ? [{ id: positioningProposalId, feedback_id: revision2, revision_id: revision2, lesson: 'Lead with the exact outcome when relevant.', status: 'pending', command_session_id: null, created_at: '2026-08-23T10:01:00Z', updated_at: '2026-08-23T10:01:00Z' }] : [] })
    if (url.pathname === `/api/v1/positionings/${projectId}/revisions` && method === 'POST') { corrected = true; return json({ revision: revision(), created: true }, 202) }
    if (url.pathname === `/api/v1/positioning-revisions/${revision2}/approve` && method === 'POST') { approved = true; return json(revision()) }
    if (url.pathname.endsWith('/export.md')) return route.fulfill({ status: 200, contentType: 'text/markdown', body: '# Marketing Positioning' })

    if (url.pathname === '/api/v1/landings/templates') return json({ items: [
      { id: 'product', name: { uk: 'Продукт', en: 'Product' }, description: { uk: 'Функції та дія.', en: 'Features and action.' } },
      { id: 'community', name: { uk: 'Спільнота', en: 'Community' }, description: { uk: 'Участь і контакт.', en: 'Participation.' } },
      { id: 'waitlist', name: { uk: 'Список очікування', en: 'Waitlist' }, description: { uk: 'Перевірка попиту.', en: 'Demand test.' } },
    ] })
    if (url.pathname === '/api/v1/landings/draft-sets/latest') return draftCreated ? json(draft()) : json({ detail: 'Landing draft set not found' }, 404)
    if (url.pathname === '/api/v1/landings/draft-sets' && method === 'POST') { draftCreated = true; return json(draft(), 202) }
    if (url.pathname === `/api/v1/landings/draft-sets/${draftId}`) return json(draft())
    if (url.pathname === `/api/v1/landings/draft-sets/${draftId}/skill-proposals`) return json({ items: edited ? [{ id: landingProposalId, feedback_id: revision2, lesson: 'Tailor form context to the selected landing.', status: 'pending', command_session_id: null, created_at: '2026-08-23T10:06:00Z', updated_at: '2026-08-23T10:06:00Z' }] : [] })
    if (url.pathname.endsWith('/preview')) {
      const snapshotId = url.pathname.split('/').at(-2)
      const templateId = snapshotId === snapshots.product ? 'product' : snapshotId === snapshots.waitlist ? 'waitlist' : 'community'
      return json({ snapshot_id: snapshotId, template_id: templateId, snapshot_number: snapshotId === editedSnapshot ? 2 : 1, artifact_sha256: 'f'.repeat(64), html: `<!doctype html><html><body><section data-landing-block="hero">Hero</section><form><input disabled><button disabled>Inert preview</button></form></body></html>` })
    }
    if (url.pathname.endsWith('/edits') && method === 'POST') { edited = true; return json({ request_id: revision2, draft_set_id: draftId, template_id: 'community', block_id: 'lead_form', instruction: 'Make the form context specific.', status: 'queued' }, 202) }
    if (url.pathname === `/api/v1/landings/draft-edits/${revision2}`) return json({ request_id: revision2, draft_set_id: draftId, template_id: 'community', block_id: 'lead_form', instruction: 'Make the form context specific.', status: 'completed', result_snapshot_id: editedSnapshot })
    if (url.pathname.endsWith('/publish') && method === 'POST') { published = true; return json({ id: buildId, request_id: buildId, positioning_project_id: projectId, positioning_revision_id: revision().id, source_draft_snapshot_id: editedSnapshot, template_id: 'community', status: 'published', public_url: `https://natal-landings-86123.web.app/builds/${buildId}/`, created_at: '2026-08-23T10:10:00Z' }, 202) }
    if (url.pathname === '/api/v1/landings') return json({ items: published ? [{ id: buildId, request_id: buildId, positioning_project_id: projectId, positioning_revision_id: revision().id, source_draft_snapshot_id: editedSnapshot, template_id: 'community', status: 'published', public_url: `https://natal-landings-86123.web.app/builds/${buildId}/`, created_at: '2026-08-23T10:10:00Z' }] : [] })
    if (url.pathname === '/api/v1/landing-leads') return json({ items: leadSubmitted ? [{ id: leadId, build_id: buildId, form_id: 'community_interest', fields: { name: 'Owner', email: 'owner@example.com' }, submitted_at: '2026-08-23T10:11:00Z', notification_attempts: [{ status: 'sent' }] }] : [] })
    if (url.pathname === `/api/v1/public/landings/${buildId}/leads` && method === 'POST') { leadSubmitted = true; return json({ accepted: true, lead_id: leadId }, 202) }

    if (url.pathname === '/api/v1/ads') return json({ positionings: approved ? [project()] : [], selected_revision: url.searchParams.has('positioning_project_id') ? revision() : null, ad_concepts: url.searchParams.has('positioning_project_id') ? document.ad_concepts : [], implemented: false, message: 'Generation and publishing are not implemented' })
    if (url.pathname === '/api/v1/jobs') return json({ items: [], next_cursor: null })
    if (url.pathname === '/api/v1/system/health') return json({ git_revision: 'v2-fixture', services: { gateway: 'ok', positioning: { ready: true }, root_broker: 'ok' }, emergency_stop: false, reset: { permitted: true, target: 'ptw_commander.public only' } })
    if (url.pathname === '/api/v1/docs') return json({ items: [{ path: 'docs/README.md', title: 'PTW docs', body: '# PTW v2' }] })
    return json({ detail: 'not found' }, 404)
  })
})

test('owner completes Positioning, Landing, lead, Ads, and Admin journey', async ({ page }) => {
  await page.goto('/?e2e=1')
  await expect(page.getByText('No positioning yet')).toBeVisible()
  await page.getByPlaceholder(/Describe the product idea/).fill('Natal makes credible progress visible.')
  await page.getByRole('button', { name: /Build positioning/ }).click()
  await expect(page.getByText(/Revision 1 · completed/)).toBeVisible()
  await page.getByText(/Sources \(1\)/).click()
  await expect(page.getByText(sourceId, { exact: false })).toBeVisible()

  await page.getByPlaceholder(/One correction/).fill('Lead with the exact outcome.')
  await page.getByRole('button', { name: /Create complete revision/ }).click()
  await expect(page.getByText(/Revision 2 · completed/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Owner lesson proposals' })).toBeVisible()
  await page.getByRole('button', { name: /Approve for Landing/ }).click()
  await expect(page.getByText(/Revision 2 · completed/)).toBeVisible()

  await page.getByRole('button', { name: 'Лендинг' }).first().click()
  await page.getByLabel('HTTPS privacy policy').fill('https://example.com/privacy')
  await page.getByRole('button', { name: /Populate three templates/ }).click()
  await expect(page.getByText(/Three private variants populated/)).toBeVisible()
  for (const label of ['Продукт', 'Спільнота', 'Список очікування']) await expect(page.getByRole('button', { name: new RegExp(label) })).toBeVisible()
  await page.getByRole('button', { name: /Спільнота/ }).click()
  await page.getByRole('button', { name: 'Lead form' }).click()
  await page.getByPlaceholder(/One instruction for Lead form/).fill('Make the form context specific.')
  await page.getByRole('button', { name: /Edit only this block/ }).click()
  await expect(page.getByRole('status')).toContainText('Only Lead form')
  await page.getByRole('button', { name: /Publish exact snapshot/ }).click()
  await expect(page.getByText(/community · published/)).toBeVisible()

  const leadResponse = await page.evaluate(async (id) => {
    const response = await fetch(`https://commander.proove-them-wrong.com/api/v1/public/landings/${id}/leads`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ form_id: 'community_interest', name: 'Owner', email: 'owner@example.com', website: '' }),
    })
    return { status: response.status, body: await response.json() }
  }, buildId)
  expect(leadResponse).toEqual({ status: 202, body: { accepted: true, lead_id: leadId } })

  await page.getByRole('button', { name: 'Позиціонування' }).first().click()
  await page.getByRole('button', { name: 'Лендинг' }).first().click()
  await expect(page.getByText(leadId, { exact: false })).toBeVisible()
  await expect(page.getByText(/Notification: sent/)).toBeVisible()

  await page.getByRole('button', { name: 'Реклама' }).first().click()
  await expect(page.getByText('Generation and publishing are not implemented')).toBeVisible()
  await expect(page.getByText('Коли прогрес розсипаний по вкладках')).toBeVisible()
  await expect(page.getByText('Прогрес важко довести?')).toBeVisible()

  await page.getByRole('button', { name: 'Адмін' }).first().click()
  await expect(page.getByRole('heading', { name: 'Завдання' })).toBeVisible()
  await page.getByRole('button', { name: /Docs \/ System/ }).click()
  await expect(page.getByText('ptw_commander.public only')).toBeVisible()
  await expect(page.getByRole('button', { name: /# Root/ })).toBeVisible()
  await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll')
})

test('retired page query redirects to the v2 Positioning empty state', async ({ page }) => {
  await page.goto('/?e2e=1&page=branding&run=legacy')
  await expect(page).not.toHaveURL(/page=branding|run=legacy/)
  await expect(page.getByText('No positioning yet')).toBeVisible()
})
