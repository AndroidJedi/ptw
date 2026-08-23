import { expect, test } from '@playwright/test'

const runId = '01234567-89ab-7def-8123-456789abcdef'
const brandRunId = '11234567-89ab-7def-8123-456789abcdef'
const brandKitId = '21234567-89ab-7def-8123-456789abcdef'
const brandDraftRunId = '91234567-89ab-7def-8123-456789abcdef'
const landingDraftId = 'a1234567-89ab-7def-8123-456789abcdef'
const landingSnapshots = {
  product: 'b1234567-89ab-7def-8123-456789abcdef',
  community: 'c1234567-89ab-7def-8123-456789abcdef',
  waitlist: 'd1234567-89ab-7def-8123-456789abcdef',
}
const landingEditedSnapshotId = 'e1234567-89ab-7def-8123-456789abcdef'
const landingEditId = 'f1234567-89ab-7def-8123-456789abcdef'
const landingProposalId = '61234567-89ab-7def-8123-456789abcdef'
const landingBuildId = '71234567-89ab-7def-8123-456789abcdef'
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
  let landingBuild: Record<string, unknown> | null = null
  let landingDraftCreated = false
  let landingEdited = false
  let landingProposalPlanning = false
  const landingBrief = {
    schema_version: 1, brand: 'Natal', language: 'uk', source: { laval_run_id: runId, thesis_id: runId },
    business_idea: 'Make credible progress visible.', target_audience: 'Goal setters',
    pain: 'Progress is hard to trust', promise: 'Natal turns work into visible proof.',
    key_features: [{ title: 'Proof timeline', description: 'Shows completed evidence.' }],
    steps: [{ title: '01', description: 'Choose a goal.' }, { title: '02', description: 'Record proof.' }],
    proof_points: [], faq: [], cta: { label: 'Спробувати Natal', url: '#contact' },
  }
  const landingPage = (templateId: string) => ({
    schema_version: 1, template_id: templateId, language: 'uk', blocks: {
      hero: { eyebrow: 'Goal setters', title: 'Make progress visible', body: 'Natal turns work into visible proof.', cta_label: 'Спробувати Natal' },
      problem: { eyebrow: 'Проблема', title: 'Progress is hard to trust', body: 'Goal setters need clarity.' },
      features: { eyebrow: 'Переваги', title: 'Visible proof', items: [{ title: 'Proof timeline', description: 'Shows completed evidence.' }] },
      steps: { eyebrow: 'Кроки', title: 'How it works', items: landingBrief.steps },
      proof: { eyebrow: 'Докази', title: 'Verified proof only', items: [], empty_text: 'No results claimed yet.' },
      faq: { eyebrow: 'FAQ', title: 'Questions', items: [] },
      final_cta: { title: 'Ready?', body: 'Make the next step clear.', cta_label: 'Спробувати Natal' },
    },
  })
  const landingEdit = (status: 'queued' | 'completed') => ({
    request_id: landingEditId, draft_set_id: landingDraftId, template_id: 'community',
    base_snapshot_id: landingSnapshots.community, block_id: 'features',
    instruction: 'Почніть з конкретного результату', feedback_id: '81234567-89ab-7def-8123-456789abcdef',
    proposal_id: landingProposalId, result_snapshot_id: status === 'completed' ? landingEditedSnapshotId : null,
    status, error_code: null, error_message: null, created_at: '2026-08-22T00:00:01Z',
    updated_at: '2026-08-22T00:00:02Z', completed_at: status === 'completed' ? '2026-08-22T00:00:02Z' : null,
  })
  const landingDraft = (status: 'queued' | 'ready') => ({
    id: landingDraftId, request_id: '91234567-89ab-7def-8123-456789abcdef', idea_run_id: runId,
    thesis_id: runId, brief: landingBrief, recommended_template_id: 'product', skill_memory_feedback_ids: [],
    status, population_summary: status === 'ready' ? 'Three private variants populated.' : null,
    population_invocation: null, error_code: null, error_message: null, requested_by: 'firebase:e2e-owner',
    variants: status === 'ready' ? (['product', 'community', 'waitlist'] as const).map((templateId) => ({
      id: landingEdited && templateId === 'community' ? landingEditedSnapshotId : landingSnapshots[templateId],
      draft_set_id: landingDraftId, template_id: templateId,
      snapshot_number: landingEdited && templateId === 'community' ? 2 : 1,
      parent_snapshot_id: landingEdited && templateId === 'community' ? landingSnapshots.community : null,
      source_feedback_id: landingEdited && templateId === 'community' ? '81234567-89ab-7def-8123-456789abcdef' : null,
      page_content: landingPage(templateId), page_content_sha256: 'a'.repeat(64), artifact_sha256: 'b'.repeat(64),
      is_current: true, application_summary: 'Fixture snapshot', invocation: null, created_at: '2026-08-22T00:00:00Z',
    })) : [],
    edits: landingEdited ? [landingEdit('completed')] : [], created_at: '2026-08-22T00:00:00Z',
    updated_at: landingEdited ? '2026-08-22T00:00:02Z' : '2026-08-22T00:00:00Z',
    completed_at: status === 'ready' ? '2026-08-22T00:00:01Z' : null,
  })
  const brandState = new Map<string, {
    revision: number
    reviewState: 'pending' | 'changes_requested' | 'approved'
    feedback: string
    feedbackId: string | null
    regenerationStatus: 'running' | 'completed' | null
    regenerationPolls: number
  }>()
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
      ready: true, revision_ready: true, provider: 'openai_brand', image_model: 'gpt-image-2', paid_seo_enabled: false,
    })
    if (url.pathname === '/api/v1/landings/templates') return json({ items: [
      { id: 'product', version: 1, name: { en: 'Product', uk: 'Продукт' }, description: { en: 'Feature-led conversion.', uk: 'Функції та перша дія.' }, best_for: ['saas'], adapted_from: 'natal_landing' },
      { id: 'community', version: 1, name: { en: 'Community / event', uk: 'Спільнота / подія' }, description: { en: 'Participation and registration.', uk: 'Участь і простий запис.' }, best_for: ['event'], adapted_from: 'sesh' },
      { id: 'waitlist', version: 1, name: { en: 'Waitlist / concept', uk: 'Waitlist / концепт' }, description: { en: 'Lean demand validation.', uk: 'Коротка перевірка попиту.' }, best_for: ['waitlist'], adapted_from: 'ofc_landing' },
    ] })
    if (url.pathname === '/api/v1/landings/candidates') return json({ items: [{
      idea_run_id: runId, recommended_template_id: 'product', quality: { successful: 9, attempted: 10 }, verdict: 'survives',
      brief: landingBrief,
    }] })
    if (url.pathname === '/api/v1/landings/draft-sets/latest') {
      return landingDraftCreated ? json(landingDraft('ready')) : json({ detail: 'Natal draft set not found' }, 404)
    }
    if (url.pathname === '/api/v1/landings/draft-sets' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({ idea_run_id: runId })
      landingDraftCreated = true
      return json(landingDraft('queued'), 202)
    }
    if (url.pathname === `/api/v1/landings/draft-sets/${landingDraftId}`) {
      if (landingDraftCreated && !landingEdited && route.request().method() === 'GET') return json(landingDraft('ready'))
      return json(landingDraft('ready'))
    }
    if (url.pathname.startsWith('/api/v1/landings/draft-snapshots/') && url.pathname.endsWith('/preview')) {
      const snapshotId = url.pathname.split('/').at(-2) || ''
      const templateId = snapshotId === landingSnapshots.product ? 'product' : snapshotId === landingSnapshots.waitlist ? 'waitlist' : 'community'
      const html = `<!doctype html><html><body style="margin:0"><section data-landing-block="hero" tabindex="0">Hero</section><section data-landing-block="features" tabindex="0">Features</section><a href="#preview-action">CTA</a><script>document.querySelectorAll('[data-landing-block]').forEach((node)=>node.addEventListener('click',(event)=>{event.preventDefault();parent.postMessage({type:'natal.select-block',templateId:'${templateId}',blockId:node.dataset.landingBlock},'*')}));document.querySelectorAll('a').forEach((a)=>a.addEventListener('click',(event)=>event.preventDefault()))<\/script></body></html>`
      return json({ snapshot_id: snapshotId, template_id: templateId, snapshot_number: snapshotId === landingEditedSnapshotId ? 2 : 1, artifact_sha256: 'b'.repeat(64), html })
    }
    if (url.pathname.endsWith('/edits') && route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({ block_id: 'features', instruction: 'Почніть з конкретного результату' })
      landingEdited = true
      return json(landingEdit('queued'), 202)
    }
    if (url.pathname === '/api/v1/landings/skill-proposals') return json({ items: landingEdited ? [{
      id: landingProposalId, feedback_id: '81234567-89ab-7def-8123-456789abcdef', draft_set_id: landingDraftId,
      template_id: 'community', block_id: 'features', proposed_lesson: 'Lead features with a concrete result.',
      reviewed_lesson: landingProposalPlanning ? 'Lead features with a concrete result.' : null,
      status: landingProposalPlanning ? 'planning' : 'pending_review', command_session_id: landingProposalPlanning ? 'fixture-plan' : null,
      comment: 'Почніть з конкретного результату', created_at: '2026-08-22T00:00:01Z', updated_at: '2026-08-22T00:00:02Z',
    }] : [] })
    if (url.pathname === `/api/v1/landings/skill-proposals/${landingProposalId}/plan`) {
      landingProposalPlanning = true
      return json({ proposal: { id: landingProposalId, draft_set_id: landingDraftId, template_id: 'community', block_id: 'features', status: 'planning', command_session_id: 'fixture-plan', comment: 'Почніть з конкретного результату' }, job: { id: 'fixture-plan', status: 'planning' } }, 202)
    }
    if (url.pathname === '/api/v1/landings/builds' && route.request().method() === 'GET') {
      return json({ items: landingBuild ? [landingBuild] : [] })
    }
    if (url.pathname === '/api/v1/landings/builds' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({ draft_snapshot_id: landingEditedSnapshotId })
      landingBuild = {
        id: landingBuildId, request_id: body.request_id, idea_run_id: runId, thesis_id: runId,
        template_id: 'community', parent_build_id: null, revision_number: 1,
        input_brief: landingBrief, brief: landingBrief, skill_memory_feedback_ids: [],
        revision_summary: 'Published exact draft snapshot.', revision_invocation: { mode: 'natal_landing_revision' },
        source_draft_snapshot_id: landingEditedSnapshotId, page_content: landingPage('community'),
        page_content_sha256: 'a'.repeat(64), status: 'queued', build_manifest: null, artifact_sha256: null,
        firebase_site_id: 'natal-landings-86123', firebase_version: null, public_url: null,
        error_code: null, error_message: null,
        created_at: '2026-08-22T00:00:00Z',
        updated_at: '2026-08-22T00:00:00Z',
        completed_at: null,
      }
      return json(landingBuild, 202)
    }
    if (url.pathname === `/api/v1/landings/builds/${landingBuildId}`) {
      landingBuild = {
        ...(landingBuild || {}),
        status: 'published',
        artifact_sha256: 'a'.repeat(64),
        firebase_version: 'fixture-version-1',
        public_url: `https://natal-landings-86123.web.app/builds/${landingBuildId}/`,
        updated_at: '2026-08-22T00:00:01Z',
        completed_at: '2026-08-22T00:00:01Z',
      }
      return json(landingBuild)
    }
    if (url.pathname === '/api/v1/branding/cases') return json({ items: [{
      idea_run_id: runId, owner_idea: 'Make credible progress visible.', created_at: '2026-08-20T00:00:00Z',
      theses: [{ id: runId, title: { en: 'Proof journey', uk: 'Шлях доказів' }, target_user: { en: 'Goal setters', uk: 'Люди з метою' }, recommended: true, verdict: 'survives' }],
      mechanisms: [], quality: { successful: 9, attempted: 10 }, recommended_thesis_id: runId, active_brand_kit: null,
    }] })
    if (url.pathname === '/api/v1/branding/runs' && route.request().method() === 'POST') return json({ run_id: brandRunId, status: 'running' })
    const canonicalRun = {
      id: brandRunId, source_laval_run_id: runId, status: brandApproved ? 'completed' : 'awaiting_review',
      current_stage: brandApproved ? 'KIT_ASSEMBLY' : 'OWNER_REVIEW', owner_preview: 'Make credible progress visible.',
      completed_stages: brandApproved ? 10 : 8, created_at: '', updated_at: '', source_stale: false,
      source_snapshot: { owner_idea: 'Make credible progress visible.', theses: [], mechanisms: [] }, constraints_text: '', provider_snapshot: {},
      project_version: 1,
    }
    const pausedDraft = {
      ...canonicalRun, id: brandDraftRunId, status: 'paused', current_stage: 'DESIGN_PRINCIPLES',
      completed_stages: 3, commander_brand_kit_id: null, project_version: 2,
    }
    if (url.pathname === '/api/v1/branding/runs') return json({
      items: brandApproved ? [pausedDraft, canonicalRun] : [canonicalRun],
    })
    if (url.pathname === '/api/v1/branding/projects') return json({ items: [{
      id: runId, status: brandApproved ? 'active' : 'draft',
      source_idea: { run_id: runId, owner_idea: 'Make credible progress visible.', created_at: '2026-08-20T00:00:00Z' },
      active_kit: brandApproved ? {
        id: brandKitId, commander_brand_kit_id: brandKitId, run_id: brandRunId,
        name: 'Proofrise', status: 'approved', source_stale: false,
        zip_digest: 'a'.repeat(64), approved_at: '2026-08-20T00:00:00Z',
        project_version: 1, manifest: {}, logo_artifact_digest: '1'.repeat(64),
        logo_asset: { digest: '1'.repeat(64), mime_type: 'image/png', width: 1024, height: 1024, url: `/api/v1/branding/assets/${'1'.repeat(64)}`, cache: 'private, no-store' },
      } : null,
      kits: [], runs: brandApproved ? [canonicalRun, pausedDraft] : [canonicalRun],
      logo_revisions: [], versions: [], created_at: '2026-08-20T00:00:00Z', updated_at: '2026-08-20T00:00:00Z',
    }] })
    const palette = {
      light: { primary: '#1457d9', secondary: '#6938b8', accent: '#d34100', background: '#ffffff', surface: '#f1f5fb', text: '#111827', muted: '#566174', success: '#087a55', warning: '#855400', error: '#b42336' },
      dark: { primary: '#79a7ff', secondary: '#c3a6ff', accent: '#ff9564', background: '#08101e', surface: '#121d31', text: '#f8faff', muted: '#b0bdd2', success: '#58d9aa', warning: '#ffd16e', error: '#ff7b8b' },
    }
    const directions = ['Proofrise', 'Momentum', 'Verity Loop'].map((name, index) => {
      const id = `${index + 3}1234567-89ab-7def-8123-456789abcdef`
      const state = brandState.get(id) || {
        revision: 1, reviewState: 'pending' as const, feedback: '', feedbackId: null,
        regenerationStatus: null, regenerationPolls: 0,
      }
      brandState.set(id, state)
      return {
      id, ordinal: index + 1, revision: state.revision, name,
      status: state.reviewState === 'approved' ? 'reviewed' : 'awaiting_review',
      manifest: { name, tagline: { en: 'Make progress visible.', uk: 'Зробіть прогрес видимим.' }, positioning: { en: 'Credible momentum.', uk: 'Достовірний прогрес.' }, personality: ['credible'], palette, typography: { display: 'Manrope', body: 'Inter', mono: 'IBM Plex Mono' }, design_principles: ['Visible momentum', 'Earned anticipation', 'Calm action'], retention_patterns: ['proof timeline'], ui_system: {} },
      evaluation: { passed: true, checks: { contrast: { passed: true }, font_coverage: { passed: true }, evidence_lineage: { passed: true } } },
      artifact_digest: `${state.revision}${index + 1}`.repeat(32), logo_asset: { digest: `${state.revision}${index + 1}`.repeat(32), mime_type: 'image/png', width: 1024, height: 1024, url: `/api/v1/branding/assets/${`${state.revision}${index + 1}`.repeat(32)}`, cache: 'private, no-store' },
      latest_feedback_id: state.feedbackId, feedback_type: state.reviewState === 'approved' ? 'owner_logo_approval' : state.feedbackId ? 'owner_text_review' : null,
      review_state: state.reviewState, regeneration_feedback_id: state.feedbackId,
      regeneration_status: state.regenerationStatus, overall_comment: state.feedback || null,
      rating: null, reviewed_at: state.feedbackId ? '2026-08-20T00:00:00Z' : null,
    }})
    if (url.pathname === `/api/v1/branding/runs/${brandRunId}`) {
      for (const state of brandState.values()) {
        if (state.regenerationStatus !== 'running') continue
        if (state.regenerationPolls > 0) state.regenerationPolls -= 1
        else {
          state.revision += 1
          state.reviewState = 'pending'
          state.feedbackId = null
          state.feedback = ''
          state.regenerationStatus = 'completed'
        }
      }
      const freshDirections = directions.map((direction) => {
        const state = brandState.get(direction.id)!
        const digest = `${state.revision}${direction.ordinal}`.repeat(32)
        return {
          ...direction, revision: state.revision, review_state: state.reviewState,
          latest_feedback_id: state.feedbackId,
          feedback_type: state.reviewState === 'approved' ? 'owner_logo_approval' : state.feedbackId ? 'owner_text_review' : null,
          overall_comment: state.feedback || null,
          regeneration_feedback_id: state.feedbackId,
          regeneration_status: state.regenerationStatus,
          artifact_digest: digest,
          logo_asset: { ...direction.logo_asset, digest, url: `/api/v1/branding/assets/${digest}` },
        }
      })
      const regenerationActive = [...brandState.values()].some((state) => state.regenerationStatus === 'running')
      return json({
      run: { id: brandRunId, source_laval_run_id: runId, status: brandApproved ? 'completed' : regenerationActive ? 'running' : 'awaiting_review', current_stage: brandApproved ? 'KIT_ASSEMBLY' : 'OWNER_REVIEW', source_snapshot: { owner_idea: 'Make credible progress visible.', theses: [], mechanisms: [] }, source_stale: false, constraints_text: '', provider_snapshot: {}, commander_brand_kit_id: brandApproved ? brandKitId : null, created_at: '', updated_at: '' },
      stages: brandStages.map((stage, ordinal) => ({ stage, ordinal, status: ordinal < 8 || brandApproved ? 'completed' : ordinal === 8 ? 'paused' : 'pending', attempt: ordinal < 8 ? 1 : 0, metrics: ordinal === 2 ? { paid_seo_calls: 0 } : {} })),
      directions: freshDirections, cost: { items: [], total_usd: 0 }, runner_active: regenerationActive,
    })
    }
    if (url.pathname === `/api/v1/branding/runs/${brandRunId}/show`) return json({ stage: url.searchParams.get('stage'), artifact: { paid_seo_calls: 0 } })
    if (url.pathname.includes(`/api/v1/branding/runs/${brandRunId}/directions/`) && url.pathname.endsWith('/review') && route.request().method() === 'POST') {
      const directionId = url.pathname.split('/').at(-2) || ''
      const body = route.request().postDataJSON() as Record<string, unknown>
      const state = brandState.get(directionId)!
      if (body.decision === 'changes') {
        expect(body).toEqual({ decision: 'changes', comment: expect.any(String) })
        state.reviewState = 'changes_requested'
        state.feedback = String(body.comment)
        state.feedbackId = `7${directionId.slice(1)}`
        state.regenerationStatus = 'running'
        state.regenerationPolls = 1
        return json({ feedback_id: state.feedbackId, decision: 'changes', regeneration: { status: 'running' } })
      }
      expect(body).toEqual({ decision: 'approve', comment: '' })
      state.reviewState = 'approved'
      state.feedbackId = `8${directionId.slice(1)}`
      return json({ feedback_id: state.feedbackId, decision: 'approve' })
    }
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
  await expect(page.locator('.bottom-nav button')).toHaveCount(6)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('populates three Natal previews, edits one block, promotes its lesson, and publishes the exact snapshot', async ({ page }) => {
  await page.goto('/?e2e=1&page=landings')
  await expect(page.getByRole('heading', { name: 'Лендинги' })).toBeVisible()
  await page.getByRole('button', { name: /Заповнити три превʼю/ }).click()
  await expect(page.getByRole('heading', { name: 'Три приватні превʼю готові' })).toBeVisible()
  await expect(page.getByRole('tab')).toHaveCount(3)
  await expect(page.getByText(/РЕКОМЕНДОВАНО/)).toBeVisible()
  await page.getByRole('tab', { name: /Спільнота \/ подія/ }).click()
  const preview = page.getByTitle('Natal community private preview')
  await expect(preview).toHaveAttribute('sandbox', 'allow-scripts')
  await page.getByRole('button', { name: '360 px' }).click()
  await expect(page.getByRole('button', { name: '360 px' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Проблема', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByLabel('Інструкція для блоку «Проблема»')).toBeVisible()
  await page.frameLocator('iframe[title="Natal community private preview"]').locator('[data-landing-block="features"]').click()
  await page.getByLabel('Інструкція для блоку «Переваги»').fill('Почніть з конкретного результату')
  await page.getByRole('button', { name: /Застосувати лише до блоку/ }).click()
  await expect(page.getByText('Почніть з конкретного результату')).toBeVisible()
  await expect(page.getByLabel('Узагальнений урок')).toHaveValue('Lead features with a concrete result.')
  await page.getByLabel('Узагальнений урок').fill('Lead features with a concrete result.')
  await page.getByRole('button', { name: 'Promote через Plan' }).click()
  await expect(page.getByText(/Plan fixture-plan/)).toBeVisible()
  await page.getByRole('button', { name: /Publish this version/ }).click()
  await expect(page.getByRole('heading', { name: 'Версію опубліковано' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Відкрити опубліковану версію/ })).toHaveAttribute(
    'href', `https://natal-landings-86123.web.app/builds/${landingBuildId}/`,
  )
  await expect(page.getByText('Нумеровані immutable revisions')).toBeVisible()
  await expect(page.getByText('Відкрити Завдання')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('regenerates each commented logo, explicitly approves it, then builds the kit', async ({ page }) => {
  await page.goto(`/?e2e=1&page=branding&run=${brandRunId}`)
  await expect(page.getByRole('heading', { name: 'Брендинг' })).toBeVisible()
  await expect(page.locator('.annotation-editor')).toHaveCount(0)
  await expect(page.getByText('Оцінка лого')).toHaveCount(0)
  await expect(page.locator('.brand-review-step .brand-single-cta')).toHaveCount(1)
  for (const [index, comment] of ['Спростіть форму', 'Посильте контраст', 'Збережіть ритм'].entries()) {
    await expect(page.getByText(`ЛОГО ${index + 1} З 3 · ВЕРСІЯ 1`)).toBeVisible()
    await page.getByLabel('Що змінити?').fill(comment)
    await page.getByRole('button', { name: 'Переробити за коментарем' }).click()
    await expect(page.getByText(/Створюю нову версію за вашим коментарем/)).toBeVisible()
    await expect(page.getByText(`ЛОГО ${index + 1} З 3 · ВЕРСІЯ 2`)).toBeVisible()
    await expect(page.getByText(/Оновлено за вашим коментарем/)).toBeVisible()
    await page.getByRole('button', { name: index === 2 ? 'Схвалити й обрати бренд' : 'Схвалити й далі' }).click()
  }
  await expect(page.getByText(/Domain and trademark clearance are not performed/)).toBeVisible()
  await page.getByRole('radio', { name: /Proofrise/ }).click()
  await page.getByRole('button', { name: /Затвердити Proofrise/ }).click()
  await expect(page.getByText('КАНОНІЧНИЙ BRAND KIT')).toBeVisible()
  await expect(page.getByRole('button', { name: /Draft v2/ })).toBeVisible()
  await expect(page.getByText(/Призупинено · DESIGN PRINCIPLES · 3\/10/)).toBeVisible()
  await expect(page.getByText(/React\/TypeScript UI kit/)).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: /Завантажити Brand Kit/ }).click()
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
