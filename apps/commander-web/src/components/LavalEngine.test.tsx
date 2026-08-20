import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { LavalEngine } from './LavalEngine'

describe('LavalEngine', () => {
  const readiness = {
    llm_provider: 'bridge', search_provider: 'fixture', trend_provider: 'fixture',
    search_live_ready: false, trends_live_ready: false, demo_available: true,
    default_evidence_mode: 'demo_fixture', max_spend_usd: .05, reserved_spend_usd: .04,
    missing: ['dataforseo_credentials'],
    optional_sources: { google_trends: { ready: false, required: false as const } },
  }

  it('shows a web-native empty state and create action', async () => {
    const api = {
      get: vi.fn((path: string) => Promise.resolve(path.includes('/providers') ? readiness : { items: [] })),
      post: vi.fn(),
      blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)
    expect(await screen.findByText('Ще немає Laval-запусків.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Нова Laval-ідея/ })).toBeInTheDocument()
    expect(screen.getByText('Evidence → mechanisms → product theses')).toBeInTheDocument()
  })

  it('creates and starts the owner idea in one click with automatic progression by default', async () => {
    const runId = '01234567-89ab-7def-8123-456789abcdef'
    const post = vi.fn()
      .mockResolvedValueOnce({ run_id: runId })
      .mockResolvedValueOnce({ started: true })
    const api = {
      get: vi.fn((path: string) => Promise.resolve(path.includes('/providers') ? readiness : path.includes(runId) ? {
        run: {
          id: runId, owner_idea_id: runId, status: 'running', current_stage: 'OWNER_DNA', approval_mode: 'automatic', approval_gates: [],
          config: {}, evidence_mode: 'demo_fixture', provider_snapshot: {}, max_spend_usd: .05, reserved_spend_usd: .04,
        },
        stages: [], cost: { items: [], total_usd: 0 },
      } : { items: [] })),
      post,
      blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: /Нова Laval-ідея/ }))
    fireEvent.change(screen.getByLabelText('Повний текст ідеї'), { target: { value: 'A fully formed owner idea' } })
    fireEvent.click(await screen.findByRole('button', { name: /Запустити демо/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/laval/runs', {
      text: 'A fully formed owner idea',
      mode: 'demo',
      config: {
        approval_mode: 'automatic',
        countries: [
          { code: 'US', language: 'en' },
          { code: 'GB', language: 'en' },
          { code: 'DE', language: 'de', secondary_language: 'en' },
          { code: 'NO', language: 'no', secondary_language: 'en' },
          { code: 'DK', language: 'da', secondary_language: 'en' },
        ],
      },
    }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/laval/runs/${runId}/run`, {}))
    expect(await screen.findByText(/Демо запущено/)).toBeInTheDocument()
  })

  it('shows one Market Signals recovery action for an eligible legacy run', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'paused', current_stage: 'OPPORTUNITY_MATRIX', approval_mode: 'manual', approval_gates: ['OPPORTUNITY_MATRIX'],
      owner_preview: 'Saved live research', completed_stages: 8, variant_count: 0, config: {},
      evidence_mode: 'live_search_pending_trends', pipeline_version: 'legacy-trends-v2',
      provider_snapshot: { search: 'dataforseo', trends: 'unavailable' }, awaiting_reason: 'awaiting_trends_provider',
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '2026-08-18T14:22:22Z', updated_at: '',
    }
    const status = {
      run,
      stages: [{ stage: 'OPPORTUNITY_MATRIX', ordinal: 7, status: 'completed', attempt: 1, metrics: {} }],
      cost: { items: [], total_usd: .0372, provider_actual_usd: .0372 },
      resume_with_market_signals_available: true,
    }
    const post = vi.fn(() => Promise.resolve({ started: true }))
    const api = {
      get: vi.fn((path: string) => Promise.resolve(path.includes('/providers') ? readiness : path.includes(run.id) ? status : { items: [run] })),
      post, blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    expect(await screen.findByText('LIVE · LEGACY PIPELINE')).toBeInTheDocument()
    expect(await screen.findByText(/Google Trends не потрібен/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Схвалити й продовжити/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Продовжити дослідження' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/laval/runs/${run.id}/resume-market-signals`, {}))
  })

  it('labels fixture runs and shows stage API failures instead of claiming the artifact is absent', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'completed', current_stage: 'FINAL_SHORTLIST', approval_mode: 'automatic', approval_gates: [],
      owner_preview: 'Demo idea', completed_stages: 16, variant_count: 21, config: {},
      evidence_mode: 'demo_fixture', provider_snapshot: { search: 'fixture', trends: 'fixture' },
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '', updated_at: '',
    }
    const status = {
      run, stages: [{ stage: 'OWNER_DNA', ordinal: 1, status: 'completed', attempt: 1, provider: 'codex-bridge', metrics: {} }],
      cost: { items: [], total_usd: 0, provider_actual_usd: 0, max_spend_usd: .05 },
    }
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve(readiness)
        if (path.includes('/show?')) return Promise.reject(new Error('API offline'))
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post: vi.fn(), blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)
    await waitFor(() => expect(screen.getAllByText('DEMO — NO LIVE RESEARCH')).toHaveLength(2))
    fireEvent.click(screen.getByRole('button', { name: /OWNER DNA/ }))
    expect(await screen.findByText(/Не вдалося завантажити артефакт: API offline/)).toBeInTheDocument()
    expect(screen.queryByText('Артефакт ще не створено.')).not.toBeInTheDocument()
  })

  it('offers a one-click Ukrainian PDF only for a completed run', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'completed', current_stage: 'THESIS_SHORTLIST', approval_mode: 'automatic', approval_gates: [],
      owner_preview: 'Completed report', completed_stages: 22, processed_stages: 22, partial_stages: 0, variant_count: 24,
      config: {}, evidence_mode: 'live_market_signals', pipeline_version: 'mechanism_thesis_v1',
      provider_snapshot: { search: 'dataforseo', youtube: 'youtube_data_api' },
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '', updated_at: '',
    }
    const status = { run, stages: [], cost: { items: [], total_usd: .0372 } }
    const blob = vi.fn(() => Promise.reject(new Error('test download stop')))
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve(readiness)
        if (path.includes('/theses')) return Promise.resolve({ run_id: run.id, status: 'ready', items: [], mechanisms: [] })
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post: vi.fn(), blob,
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Завантажити PDF' }))
    await waitFor(() => expect(blob).toHaveBeenCalledWith(`/api/v1/laval/runs/${run.id}/export?format=pdf`))
  })

  it('edits a competitor directly in its readable list without asking for a UUID', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'paused', current_stage: 'COMPETITOR_SELECTION', approval_mode: 'manual', approval_gates: ['COMPETITOR_SELECTION'],
      owner_preview: 'Correction UX', completed_stages: 5, variant_count: 0, config: { countries: [{ code: 'US' }] },
      evidence_mode: 'demo_fixture', provider_snapshot: { search: 'fixture', trends: 'fixture' },
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '', updated_at: '',
    }
    const stages = [
      { stage: 'OWNER_CAPTURE', ordinal: 0, status: 'completed', attempt: 1, metrics: {} },
      { stage: 'COMPETITOR_SELECTION', ordinal: 4, status: 'completed', attempt: 1, metrics: {} },
    ]
    const status = { run, stages, cost: { items: [], total_usd: 0 } }
    const competitorId = '21234567-89ab-7def-8123-456789abcdef'
    const post = vi.fn(() => Promise.resolve({ ok: true }))
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve(readiness)
        if (path.includes('/show?')) {
          if (path.includes('COMPETITOR_SELECTION')) return Promise.resolve({
            output: { global_deduplicated: [] },
            override_targets: [{ id: competitorId, kind: 'competitor', name: 'Clear Rival', domain: 'rival.example', url: 'https://rival.example', score: .78 }],
          })
          return Promise.resolve({ output: { raw_text: 'Owner idea' }, override_targets: [] })
        }
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post, blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: /OWNER CAPTURE/ }))
    await screen.findByText(/Owner idea/)
    expect(screen.queryByText(/Скоригувати список конкурентів/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /COMPETITOR SELECTION/ }))
    expect(await screen.findByText('Clear Rival')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Деталі'))
    expect(screen.getByRole('link', { name: 'https://rival.example' })).toBeInTheDocument()
    expect(screen.queryByLabelText('UUID')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Вилучити' }))
    fireEvent.change(screen.getByLabelText('Причина для Clear Rival'), { target: { value: 'Not a direct product' } })
    fireEvent.click(screen.getByRole('button', { name: 'Підтвердити' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/laval/runs/${run.id}/override`, {
      type: 'competitor', action: 'reject', target_id: competitorId, reason: 'Not a direct product',
    }))
  })

  it('disables an opportunity directly beside its details', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'paused', current_stage: 'OPPORTUNITY_MATRIX', approval_mode: 'manual', approval_gates: ['OPPORTUNITY_MATRIX'],
      owner_preview: 'Opportunity corrections', completed_stages: 10, processed_stages: 10, partial_stages: 0, variant_count: 0,
      config: { countries: [{ code: 'US' }] }, evidence_mode: 'demo_fixture', provider_snapshot: { search: 'fixture', trends: 'fixture' },
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '', updated_at: '',
    }
    const opportunityId = '31234567-89ab-7def-8123-456789abcdef'
    const status = { run, stages: [{ stage: 'OPPORTUNITY_MATRIX', ordinal: 9, status: 'completed', attempt: 1, metrics: {} }], cost: { items: [], total_usd: 0 } }
    const post = vi.fn(() => Promise.resolve({ ok: true }))
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve(readiness)
        if (path.includes('/show?')) return Promise.resolve({
          output: { opportunities: [{ id: opportunityId, statement: 'Private proof before public pressure', pain: 'Public accountability can become harmful.', evidence_ids: ['evidence-1'] }] },
          override_targets: [{ id: opportunityId, kind: 'opportunity', statement: 'Private proof before public pressure', pain: 'Public accountability can become harmful.', aggregate_score: .72 }],
        })
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post, blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: /OPPORTUNITY MATRIX/ }))
    expect(await screen.findByText('Private proof before public pressure')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Вимкнути' }))
    fireEvent.change(screen.getByLabelText('Причина для Private proof before public pressure'), { target: { value: 'Outside the intended segment' } })
    fireEvent.click(screen.getByRole('button', { name: 'Підтвердити' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/laval/runs/${run.id}/override`, {
      type: 'opportunity', action: 'disable', target_id: opportunityId, reason: 'Outside the intended segment',
    }))
  })

  it('explains safe recovery without offering retired Telegram notifications', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'failed', current_stage: 'SERP_DISCOVERY', approval_mode: 'manual', approval_gates: ['COMPETITOR_SELECTION'],
      owner_preview: 'Live idea', completed_stages: 3, variant_count: 0, config: {},
      evidence_mode: 'live_search_pending_trends', provider_snapshot: { search: 'dataforseo', trends: 'unavailable' },
      max_spend_usd: .05, reserved_spend_usd: .04, error_text: 'one queued task is still pending', created_at: '', updated_at: '',
    }
    const stages = Array.from({ length: 16 }, (_, ordinal) => ({
      stage: ordinal === 3 ? 'SERP_DISCOVERY' : `STAGE_${ordinal}`, ordinal,
      status: ordinal < 3 ? 'completed' : ordinal === 3 ? 'failed' : 'pending', attempt: ordinal === 3 ? 1 : 0, metrics: {},
    }))
    const status = {
      run, stages, cost: { items: [], total_usd: .0186, provider_actual_usd: .0192, max_spend_usd: .05 },
      quality: {
        verdict: 'invalid', message: 'failed safely', attempted: 2, success: 0, fallback: 0, failed: 2,
        recovered_failures: 0, unresolved_failures: 2, missing_stages: ['OWNER_DNA'],
        by_stage: [{ stage: 'SERP_DISCOVERY', verdict: 'invalid', attempted: 2, success: 0, fallback: 0, failed: 2, recovered_failures: 0, unresolved_failures: 2 }],
      },
      recovery: {
        available: true, stage: 'SERP_DISCOVERY', stage_status: 'failed', attempt: 1, failed_at: '2026-08-18T15:00:00Z',
        failure: { type: 'TimeoutError', message: 'one queued task is still pending' },
        provider_tasks: { total: 32, reserved: 0, submitted: 1, completed: 31, failed: 0, persisted_remote_ids: 32, cost_recorded: 31, actual_cost_usd: .0192 },
        resume_behavior: { reuses_persisted_remote_ids: true, reposts_submitted_tasks: false, duplicates_recorded_cost: false },
        history: [],
      },
    }
    const post = vi.fn(() => Promise.resolve({ started: true }))
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve({ ...readiness, search_live_ready: true, search_provider: 'dataforseo' })
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post, blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    expect(await screen.findByText('ЗВІТ ПРО ПОМИЛКУ ТА ВІДНОВЛЕННЯ')).toBeInTheDocument()
    expect(screen.getByText('Запуск безпечно зупинено')).toBeInTheDocument()
    expect(screen.getByText(/навіть після однієї автоматичної повторної спроби/)).toBeInTheDocument()
    expect(screen.getByText(/Submitted-задачі не публікуються і не оплачуються повторно/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Відновити збережену роботу/ }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/laval/runs/${run.id}/resume`, {}))
    expect(screen.queryByRole('button', { name: /Статус у Telegram/ })).not.toBeInTheDocument()
  })

  it('shows the MarketSignalScore formula, raw counters, data status, and evidence IDs', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'completed', current_stage: 'FINAL_SHORTLIST', approval_mode: 'automatic', approval_gates: [],
      owner_preview: 'Market signal idea', completed_stages: 16, variant_count: 24, config: {},
      evidence_mode: 'live_market_signals', pipeline_version: 'market_signals_v2', provider_snapshot: { search: 'dataforseo', trends: 'unavailable' },
      max_spend_usd: .05, reserved_spend_usd: .04, created_at: '', updated_at: '',
    }
    const status = {
      run,
      stages: [{ stage: 'MARKET_SIGNAL_GATE', ordinal: 10, status: 'completed', attempt: 1, metrics: {} }],
      cost: { items: [], total_usd: .0192 },
    }
    const score = {
      id: 'score-1', normalization_version: 'market-signal-v1',
      formula: '0.20 × cross_country_recurrence + 0.20 × query_family_recurrence', aggregate_score: .42,
      components: { cross_country_recurrence: .4, recent_content_activity: 0 },
      raw_counts: { target_countries: 5, recent_dated_sources_365d: 0 },
      data_status: { overall: 'available', components: { cross_country_recurrence: 'available', recent_content_activity: 'no_data' } },
      evidence_ids: ['evidence-1'],
    }
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve(readiness)
        if (path.includes('/show?')) return Promise.resolve({ output: { scores: [score], google_trends_required: false } })
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post: vi.fn(), blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: /MARKET SIGNAL GATE/ }))
    expect(await screen.findByText('MarketSignalScore')).toBeInTheDocument()
    expect(screen.getByText(/0.20 × cross_country_recurrence/)).toBeInTheDocument()
    expect(screen.getByText(/даних немає/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Сирі лічильники'))
    expect(screen.getByText(/recent_dated_sources_365d/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Evidence IDs (1)'))
    expect(screen.getByText('evidence-1')).toBeInTheDocument()
  })

  it('marks a completed live fallback run invalid and renders a readable shortlist before raw JSON', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'completed', current_stage: 'FINAL_SHORTLIST', approval_mode: 'automatic', approval_gates: [],
      owner_preview: 'Public proof challenge', completed_stages: 16, variant_count: 24, config: {},
      evidence_mode: 'live_market_signals', pipeline_version: 'market_signals_v2', provider_snapshot: { search: 'dataforseo', llm: 'bridge' },
      max_spend_usd: .05, reserved_spend_usd: .0372, created_at: '', updated_at: '',
    }
    const quality = {
      verdict: 'invalid', message: 'fallback', attempted: 16, success: 0, fallback: 16, failed: 0,
      recovered_failures: 0, unresolved_failures: 0,
      missing_stages: ['OWNER_DNA'], by_stage: [{ stage: 'IDEA_EXPANSION', verdict: 'invalid', attempted: 1, success: 0, fallback: 1, failed: 0 }],
    }
    const status = {
      run, quality,
      stages: [{ stage: 'FINAL_SHORTLIST', ordinal: 15, status: 'completed', attempt: 1, metrics: {} }],
      cost: { items: [], total_usd: .0372, provider_actual_usd: .0372 },
    }
    const show = {
      output: { shortlist: [{
        idea_id: 'idea-1', rank: 1, finalist: true, operator: 'distribution_first', final_score: .667,
        title: { en: 'Distribution First 1', uk: 'Спершу дистрибуція 1' },
        one_liner: { en: 'Fallback text', uk: 'Fallback-текст' },
      }], graph_sync: { hypotheses: { 'idea-1': 'published-before-fix' } } },
      quality: { run: { ...quality, by_stage: undefined }, stage: { stage: 'FINAL_SHORTLIST', verdict: 'not_applicable', attempted: 0, success: 0, fallback: 0, failed: 0 } },
    }
    const api = {
      get: vi.fn((path: string) => {
        if (path.includes('/providers')) return Promise.resolve(readiness)
        if (path.includes('/show?')) return Promise.resolve(show)
        if (path.includes(run.id)) return Promise.resolve(status)
        return Promise.resolve({ items: [run] })
      }),
      post: vi.fn(), blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    expect(await screen.findByText('Цей результат не можна використовувати')).toBeInTheDocument()
    expect(screen.getByText('Успішні відповіді моделі').parentElement).toHaveTextContent('0')
    expect(screen.getByText('Усього спроб').parentElement).toHaveTextContent('16')
    fireEvent.click(screen.getByRole('button', { name: /FINAL SHORTLIST/ }))
    expect(await screen.findByText('Спершу дистрибуція 1')).toBeInTheDocument()
    expect(screen.getByText(/INVALID FALLBACK/)).toBeInTheDocument()
    expect(screen.queryByText('FINALIST')).not.toBeInTheDocument()
    expect(screen.queryByText(/published-before-fix/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Технічні дані · raw JSON'))
    expect(await screen.findByText(/published-before-fix/)).toBeInTheDocument()
  })
})
