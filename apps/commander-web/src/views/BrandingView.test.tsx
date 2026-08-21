import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { BrandingView } from './BrandingView'

describe('BrandingView', () => {
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
    expect(screen.getByText(/★ РЕКОМЕНДОВАНО · Шлях доказів/)).toBeInTheDocument()
    expect(screen.getByText('Люди з метою, у яку не вірять')).toBeInTheDocument()
    expect(screen.getByText('Додати достовірний доказ')).toBeInTheDocument()
    expect(screen.getByText('Якість доказів 90%')).toBeInTheDocument()
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

    expect(screen.getByText(/Жодна теза не пройшла оцінювання/)).toBeInTheDocument()
    expect(screen.getByText('ВІДХИЛЕНА')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Спочатку налаштуйте провайдер' })).toBeDisabled()
    expect(screen.getByText(/Окремий OpenAI API key не потрібен/)).toBeInTheDocument()
  })
})
