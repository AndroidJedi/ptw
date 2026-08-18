import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { LavalEngine } from './LavalEngine'

describe('LavalEngine', () => {
  const readiness = {
    llm_provider: 'bridge', search_provider: 'fixture', trend_provider: 'fixture',
    search_live_ready: false, trends_live_ready: false, demo_available: true,
    default_evidence_mode: 'demo_fixture', max_spend_usd: .005, reserved_spend_usd: .004,
    missing: ['dataforseo_credentials', 'google_trends_alpha_bridge'],
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
    expect(screen.getByText('Evidence → opportunity → trend → ideas')).toBeInTheDocument()
  })

  it('submits the owner idea through the Laval API', async () => {
    const post = vi.fn().mockReturnValue(new Promise(() => undefined))
    const api = {
      get: vi.fn((path: string) => Promise.resolve(path.includes('/providers') ? readiness : { items: [] })),
      post,
      blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: /Нова Laval-ідея/ }))
    fireEvent.change(screen.getByLabelText('Повний текст ідеї'), { target: { value: 'A fully formed owner idea' } })
    fireEvent.click(await screen.findByRole('button', { name: /Створити чітко позначене демо/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/laval/runs', {
      text: 'A fully formed owner idea',
      mode: 'demo',
      config: {
        approval_mode: 'manual',
        countries: [
          { code: 'US', language: 'en' },
          { code: 'GB', language: 'en' },
          { code: 'DE', language: 'de', secondary_language: 'en' },
          { code: 'NO', language: 'no', secondary_language: 'en' },
          { code: 'DK', language: 'da', secondary_language: 'en' },
        ],
      },
    }))
  })

  it('labels fixture runs and shows stage API failures instead of claiming the artifact is absent', async () => {
    const run = {
      id: '01234567-89ab-7def-8123-456789abcdef', owner_idea_id: '11234567-89ab-7def-8123-456789abcdef',
      status: 'completed', current_stage: 'FINAL_SHORTLIST', approval_mode: 'automatic', approval_gates: [],
      owner_preview: 'Demo idea', completed_stages: 16, variant_count: 21, config: {},
      evidence_mode: 'demo_fixture', provider_snapshot: { search: 'fixture', trends: 'fixture' },
      max_spend_usd: .005, reserved_spend_usd: .004, created_at: '', updated_at: '',
    }
    const status = {
      run, stages: [{ stage: 'OWNER_DNA', ordinal: 1, status: 'completed', attempt: 1, provider: 'codex-bridge', metrics: {} }],
      cost: { items: [], total_usd: 0, provider_actual_usd: 0, max_spend_usd: .005 },
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
})
