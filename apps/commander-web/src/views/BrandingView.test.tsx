import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { BrandDirection } from '../types'
import { BrandingView } from './BrandingView'

describe('BrandingView', () => {
  it('anchors the canonical kit beside paused Draft v2 and reviews immutable before/after', async () => {
    const ideaId = '01234567-89ab-7def-8123-456789abcdef'
    const kitRun = '11234567-89ab-7def-8123-456789abcdef'
    const draftRun = '21234567-89ab-7def-8123-456789abcdef'
    const revisionId = '31234567-89ab-7def-8123-456789abcdef'
    const baseRun = {
      source_laval_run_id: ideaId, source_snapshot: { owner_idea: 'Prove them wrong', theses: [], mechanisms: [] },
      source_stale: false, constraints_text: '', provider_snapshot: {}, created_at: '2026-08-21T10:00:00Z',
      updated_at: '2026-08-21T11:00:00Z',
    }
    const completed = { ...baseRun, id: kitRun, project_version: 1, status: 'completed', current_stage: 'KIT_ASSEMBLY', completed_stages: 10, commander_brand_kit_id: 'kit-graph-id' }
    const paused = { ...baseRun, id: draftRun, project_version: 2, status: 'paused', current_stage: 'DESIGN_PRINCIPLES', completed_stages: 3 }
    const project = {
      id: ideaId, status: 'revision_review', source_idea: { run_id: ideaId, owner_idea: 'Prove them wrong', created_at: baseRun.created_at },
      active_kit: { id: 'kit-local', commander_brand_kit_id: 'kit-graph-id', name: 'Proofrise', status: 'approved', zip_digest: 'a'.repeat(64), source_stale: false, approved_at: baseRun.updated_at, project_version: 1, run_id: kitRun, logo_asset: { digest: 'b'.repeat(64), mime_type: 'image/png', url: '/asset/before', cache: 'private, no-store', generation_provenance: {} }, manifest: {} },
      kits: [], runs: [completed, paused], logo_revisions: [{
        id: revisionId, source_laval_run_id: ideaId, base_kit_id: 'kit-local', proposed_project_version: 2,
        client_request_id: 'recovery', status: 'completed', attempt: 1, strategy: 'lettermark', literal_text: 'PTW',
        requested_change: 'use just letters PTW, play around them', feedback: 'use just letters PTW, play around them',
        reference_used: true, reference_trace: { renderer: 'bundled-font-lettermark-v1' }, compliance: { passed: true },
        before_asset: { digest: 'b'.repeat(64), mime_type: 'image/png', url: '/asset/before', cache: 'private, no-store', generation_provenance: {} },
        after_asset: { digest: 'c'.repeat(64), mime_type: 'image/png', url: '/asset/after', cache: 'private, no-store', generation_provenance: {} },
        created_at: baseRun.updated_at,
      }], created_at: baseRun.created_at, updated_at: baseRun.updated_at,
    }
    const post = vi.fn().mockResolvedValue({ status: 'approved' })
    const api = {
      get: vi.fn().mockImplementation((path: string) => {
        if (path === '/api/v1/branding/cases?limit=50') return Promise.resolve({ items: [] })
        if (path === '/api/v1/branding/runs?limit=50') return Promise.resolve({ items: [paused, completed] })
        if (path === '/api/v1/branding/projects?limit=50') return Promise.resolve({ items: [project] })
        if (path === `/api/v1/branding/projects/${ideaId}`) return Promise.resolve(project)
        if (path === '/api/v1/branding/providers') return Promise.resolve({ ready: true, revision_ready: true, provider: 'codex_brand_bridge' })
        if (path === `/api/v1/branding/runs/${kitRun}`) return Promise.resolve({ run: completed, stages: [], directions: [], cost: { items: [], total_usd: 0 } })
        if (path === '/api/v1/branding/kits/kit-graph-id') return Promise.resolve(project.active_kit)
        return Promise.resolve({})
      }),
      post, blob: vi.fn().mockResolvedValue(new Blob(['png'], { type: 'image/png' })),
    } as unknown as ApiClient

    render(<BrandingView api={api} language="uk" />)

    expect(await screen.findByText('КАНОНІЧНИЙ BRAND KIT')).toBeInTheDocument()
    expect(screen.getByText('Draft v2')).toBeInTheDocument()
    expect(screen.getByText(/Призупинено · DESIGN PRINCIPLES · 3\/10/)).toBeInTheDocument()
    expect(screen.getByText('ДО · KIT V1')).toBeInTheDocument()
    expect(screen.getByText('ПІСЛЯ · КАНДИДАТ V2')).toBeInTheDocument()
    expect(api.blob).toHaveBeenCalledWith('/asset/before')
    expect(api.blob).toHaveBeenCalledWith('/asset/after')
    expect(screen.getByText('use just letters PTW, play around them')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith(`/api/v1/branding/runs/${kitRun}`)
    fireEvent.click(screen.getByRole('button', { name: 'Схвалити новий Brand Kit' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/branding/projects/${ideaId}/logo-revisions/${revisionId}/decision`,
      { decision: 'approve' },
    ))
  })

  it('shows a friendly completed-Idea picker without exposing UUIDs', async () => {
    const ideaRunId = '01234567-89ab-7def-8123-456789abcdef'
    const api = {
      get: vi.fn().mockImplementation((path: string) => {
        if (path.startsWith('/api/v1/branding/cases')) return Promise.resolve({ items: [{
          idea_run_id: ideaRunId,
          owner_idea: 'Зробити щоденний прогрес видимим і достовірним.',
          created_at: '2026-08-20T10:00:00Z',
          theses: [{
            id: 'internal-thesis', title: { en: 'Proof journey', uk: 'Шлях доказів' },
            target_user: { en: 'People with doubted goals', uk: 'Люди з метою, у яку не вірять' },
            loop_steps: [{ en: 'Log credible proof', uk: 'Додати достовірний доказ' }],
            recommended: true, verdict: 'survives',
          }],
          mechanisms: [], quality: { successful: 9, attempted: 10 },
          surviving_thesis_count: 1,
          recommended_thesis_id: 'internal-thesis', active_brand_kit: null,
        }] })
        if (path.startsWith('/api/v1/branding/runs')) return Promise.resolve({ items: [] })
        if (path === '/api/v1/branding/providers') return Promise.resolve({ ready: true, provider: 'codex_brand_bridge', configured_provider: 'bridge', paid_seo_enabled: false })
        return Promise.resolve({})
      }),
      post: vi.fn(), blob: vi.fn(),
    } as unknown as ApiClient

    render(<BrandingView api={api} language="uk" />)
    fireEvent.click(await screen.findByRole('button', { name: /Новий бренд/ }))

    expect(await screen.findByText('Зробити щоденний прогрес видимим і достовірним.')).toBeInTheDocument()
    expect(screen.getByText(/★ Шлях доказів/)).toBeInTheDocument()
    expect(screen.getByText('Люди з метою, у яку не вірять')).toBeInTheDocument()
    expect(screen.queryByText('Додати достовірний доказ')).not.toBeInTheDocument()
    expect(screen.getByText('Докази 90%')).toBeInTheDocument()
    expect(screen.queryByText(ideaRunId)).not.toBeInTheDocument()
    expect(screen.getByText(/SEO вимкнено/)).toBeInTheDocument()
  })

  it('keeps a completed rejected-thesis case selectable and explains a missing provider', async () => {
    const api = {
      get: vi.fn().mockImplementation((path: string) => {
        if (path.startsWith('/api/v1/branding/cases')) return Promise.resolve({ items: [{
          idea_run_id: '01234567-89ab-7def-8123-456789abcdef',
          owner_idea: 'Завершена Idea справа без тези, що вижила.',
          created_at: '2026-08-20T10:00:00Z',
          theses: [{
            id: 'rejected-thesis', title: { en: 'Assessed route', uk: 'Оцінений напрям' },
            target_user: { en: 'Teams', uk: 'Команди' }, loop_steps: [],
            recommended: false, verdict: 'rejected',
          }],
          mechanisms: [], quality: { successful: 10, attempted: 10 },
          surviving_thesis_count: 0, recommended_thesis_id: null, active_brand_kit: null,
        }] })
        if (path.startsWith('/api/v1/branding/runs')) return Promise.resolve({ items: [] })
        if (path === '/api/v1/branding/providers') return Promise.resolve({
          ready: false, configured_provider: 'bridge', provider: 'codex_brand_bridge',
          missing: ['codex_brand_bridge_contract'], paid_seo_enabled: false,
        })
        return Promise.resolve({})
      }),
      post: vi.fn(), blob: vi.fn(),
    } as unknown as ApiClient

    render(<BrandingView api={api} language="uk" />)
    fireEvent.click(await screen.findByRole('button', { name: /Новий бренд/ }))

    expect(screen.getByText(/Використаємо оригінальну ідею/)).toBeInTheDocument()
    expect(screen.queryByText('ВІДХИЛЕНА')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Створити бренд' })).toBeDisabled()
    expect(screen.getByText(/Окремий OpenAI API key не потрібен/)).toBeInTheDocument()
  })

  it('offers a real safe retry and explains that owner review is not a stuck run', async () => {
    const run = {
      id: 'brand-run', source_laval_run_id: 'idea-run', status: 'awaiting_review', current_stage: 'OWNER_REVIEW',
      source_snapshot: { owner_idea: 'Зробити прогрес видимим.', theses: [], mechanisms: [] },
      source_stale: false, constraints_text: '', provider_snapshot: {}, created_at: '2026-08-21T12:45:00Z',
      updated_at: '2026-08-21T12:52:00Z', completed_stages: 8,
    }
    let statusRequests = 0
    const api = {
      get: vi.fn().mockImplementation((path: string) => {
        if (path === '/api/v1/branding/cases?limit=50') return Promise.resolve({ items: [] })
        if (path === '/api/v1/branding/runs?limit=50') return Promise.resolve({ items: [run] })
        if (path === '/api/v1/branding/providers') return Promise.resolve({ ready: true, provider: 'codex_brand_bridge' })
        if (path === '/api/v1/branding/runs/brand-run') {
          statusRequests += 1
          if (statusRequests === 1) return Promise.reject(new Error('API не відповідає протягом 15 секунд.'))
          return Promise.resolve({
            run,
            stages: [{ stage: 'OWNER_REVIEW', ordinal: 8, status: 'paused', attempt: 1, metrics: {} }],
            directions: [], cost: { items: [], total_usd: 0 },
          })
        }
        return Promise.resolve({})
      }),
      post: vi.fn(), blob: vi.fn(),
    } as unknown as ApiClient

    render(<BrandingView api={api} language="uk" />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('API не відповідає')
    fireEvent.click(screen.getByRole('button', { name: 'Повторити' }))

    expect(await screen.findByText(/0 з 3 логотипів схвалено/)).toBeInTheDocument()
    expect(screen.getByText(/Чекає на ваш відгук · спроба 1/)).toBeInTheDocument()
    expect(statusRequests).toBe(2)
  })

  it('turns text feedback into visible regeneration and stays on the same logo', async () => {
    const run = {
      id: 'brand-run', source_laval_run_id: 'idea-run', status: 'awaiting_review', current_stage: 'OWNER_REVIEW',
      source_snapshot: { owner_idea: 'Зробити прогрес видимим.', theses: [], mechanisms: [] },
      source_stale: false, constraints_text: '', provider_snapshot: {}, created_at: '', updated_at: '', completed_stages: 8,
    }
    const directions: BrandDirection[] = ['Перший', 'Другий', 'Третій'].map((name, index) => ({
      id: `direction-${index}`, ordinal: index + 1, name, status: 'awaiting_review',
      manifest: {
        name, tagline: { uk: `Слоган ${index + 1}`, en: `Tagline ${index + 1}` },
        positioning: { uk: 'Позиціонування', en: 'Positioning' }, personality: [],
        palette: { light: {}, dark: {} }, typography: { display: 'Inter', body: 'Inter', mono: 'IBM Plex Mono' },
        design_principles: [], retention_patterns: [], ui_system: {},
      },
      evaluation: { passed: true, checks: {} }, latest_feedback_id: null,
      review_state: 'pending', revision: 1,
    }))
    const post = vi.fn().mockImplementation(() => {
      directions[0].latest_feedback_id = 'feedback-1'
      directions[0].overall_comment = 'Зробіть знак простішим'
      directions[0].review_state = 'changes_requested'
      directions[0].regeneration_feedback_id = 'feedback-1'
      directions[0].regeneration_status = 'running'
      run.status = 'running'
      return Promise.resolve({ feedback_id: 'feedback-1', decision: 'changes', regeneration: { status: 'running' } })
    })
    const api = {
      get: vi.fn().mockImplementation((path: string) => {
        if (path === '/api/v1/branding/cases?limit=50') return Promise.resolve({ items: [] })
        if (path === '/api/v1/branding/runs?limit=50') return Promise.resolve({ items: [run] })
        if (path === '/api/v1/branding/providers') return Promise.resolve({ ready: true, provider: 'codex_brand_bridge' })
        if (path === '/api/v1/branding/runs/brand-run') return Promise.resolve({
          run, stages: [], directions: [...directions], cost: { items: [], total_usd: 0 },
        })
        return Promise.resolve({})
      }),
      post, blob: vi.fn(),
    } as unknown as ApiClient

    const { container } = render(<BrandingView api={api} language="uk" />)
    fireEvent.change(await screen.findByLabelText('Що змінити?'), { target: { value: 'Зробіть знак простішим' } })
    expect(container.querySelectorAll('.brand-review-step .brand-single-cta')).toHaveLength(1)
    expect(screen.queryByText('Оцінка лого')).not.toBeInTheDocument()
    expect(container.querySelector('.annotation-editor')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Переробити за коментарем' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/branding/runs/brand-run/directions/direction-0/review',
      { decision: 'changes', comment: 'Зробіть знак простішим' },
    ))
    expect(await screen.findByText(/Створюю нову версію за вашим коментарем/)).toBeInTheDocument()
    expect(screen.getByText(/ЛОГО 1 З 3 · ВЕРСІЯ 1/)).toBeInTheDocument()
    expect(container.querySelectorAll('.brand-review-step .brand-single-cta')).toHaveLength(0)
  })

  it('approves with an empty field and advances with one CTA', async () => {
    const run = {
      id: 'brand-run', source_laval_run_id: 'idea-run', status: 'awaiting_review', current_stage: 'OWNER_REVIEW',
      source_snapshot: { owner_idea: 'Зробити прогрес видимим.', theses: [], mechanisms: [] },
      source_stale: false, constraints_text: '', provider_snapshot: {}, created_at: '', updated_at: '', completed_stages: 8,
    }
    const directions = ['Перший', 'Другий', 'Третій'].map((name, index) => ({
      id: `direction-${index}`, ordinal: index + 1, revision: 1, name, status: 'awaiting_review',
      review_state: 'pending' as const, latest_feedback_id: null,
      manifest: {
        name, tagline: { uk: `Слоган ${index + 1}`, en: `Tagline ${index + 1}` },
        positioning: { uk: 'Позиціонування', en: 'Positioning' }, personality: [],
        palette: { light: {}, dark: {} }, typography: { display: 'Inter', body: 'Inter', mono: 'IBM Plex Mono' },
        design_principles: [], retention_patterns: [], ui_system: {},
      },
      evaluation: { passed: true, checks: {} },
    })) as BrandDirection[]
    const post = vi.fn().mockImplementation(() => {
      directions[0].review_state = 'approved'
      directions[0].latest_feedback_id = 'approval-1'
      return Promise.resolve({ feedback_id: 'approval-1', decision: 'approve' })
    })
    const api = {
      get: vi.fn().mockImplementation((path: string) => {
        if (path === '/api/v1/branding/cases?limit=50') return Promise.resolve({ items: [] })
        if (path === '/api/v1/branding/runs?limit=50') return Promise.resolve({ items: [run] })
        if (path === '/api/v1/branding/providers') return Promise.resolve({ ready: true, provider: 'codex_brand_bridge' })
        if (path === '/api/v1/branding/runs/brand-run') return Promise.resolve({
          run, stages: [], directions: [...directions], cost: { items: [], total_usd: 0 },
        })
        return Promise.resolve({})
      }),
      post, blob: vi.fn(),
    } as unknown as ApiClient

    const { container } = render(<BrandingView api={api} language="uk" />)
    expect(await screen.findByRole('button', { name: 'Схвалити й далі' })).toBeEnabled()
    expect(container.querySelectorAll('.brand-review-step .brand-single-cta')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Схвалити й далі' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/branding/runs/brand-run/directions/direction-0/review',
      { decision: 'approve', comment: '' },
    ))
    expect(await screen.findByText(/ЛОГО 2 З 3/)).toBeInTheDocument()
  })
})
