import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { ValidationPanel } from './ValidationPanel'

describe('ValidationPanel', () => {
  it('makes external-action boundaries explicit and starts only the persisted probe state', async () => {
    const workspaceId = '01234567-89ab-7def-8123-456789abcdef'
    const probeId = '11234567-89ab-7def-8123-456789abcdef'
    const snapshot = {
      workspace: { id: workspaceId, kind: 'validation_workspace', created_at: '', attributes: { hypothesis_id: 'h1', idea_laval_run_id: 'r1', idea_laval_thesis_id: 't1', status: 'probe_planning', external_actions_automatic: false } },
      hypothesis: { id: 'h1', kind: 'hypothesis', created_at: '', attributes: { claim: 'Manual thesis', success_criterion: { metric: 'interest', operator: '>=', threshold: .2 } } },
      mechanisms: [], observations: [], insights: [], decisions: [],
      probes: [{ id: probeId, kind: 'experiment', created_at: '', status: 'proposed', attributes: { experiment_type: 'market_probe', probe_type: 'landing_page', assumption_id: 'a1', assumption: 'Visitors opt in', procedure: 'Owner publishes manually.', target_segment: 'Creators', success_criterion: { metric: 'interest', operator: '>=', threshold: .2 }, sample_target: 10, duration_days: 7, budget_minor: 0, external_execution: 'manual_owner_only' } }],
    }
    const get = vi.fn((path: string) => Promise.resolve(path === '/api/v1/validations' ? { items: [snapshot] } : snapshot))
    const post = vi.fn().mockResolvedValue({})
    const api = { get, post } as unknown as ApiClient
    render(<ValidationPanel api={api} />)
    expect(await screen.findByText(/Автоматичні зовнішні дії вимкнено/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Почати вручну' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/probes/${probeId}/start`, {}))
    expect(screen.getByText(/Жодної зовнішньої дії PTW не виконав/)).toBeInTheDocument()
  })
})
