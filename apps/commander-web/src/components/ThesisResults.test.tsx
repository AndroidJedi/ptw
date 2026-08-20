import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { ThesisResults } from './ThesisResults'

describe('ThesisResults', () => {
  it('shows a complete surviving thesis and resolves selection without owner UUID input', async () => {
    const runId = '01234567-89ab-7def-8123-456789abcdef'
    const thesisId = '11234567-89ab-7def-8123-456789abcdef'
    const mechanismId = '21234567-89ab-7def-8123-456789abcdef'
    const collection = {
      run_id: runId, status: 'ready', recommended_thesis_id: thesisId,
      mechanisms: [{ id: mechanismId, name: { en: 'Proof loop', uk: 'Цикл доказу' }, description: { en: 'Proof', uk: 'Доказ' }, mechanism_type: 'proof', support_dimensions: { source_diversity: .8 }, evidence_ids: ['e1'] }],
      items: [{
        id: thesisId, title: { en: 'Thesis', uk: 'Теза' }, target_user: { en: 'Creator', uk: 'Автор' }, problem: { en: 'Return', uk: 'Повернення' },
        loop_steps: ['Прихід', 'Обіцянка', 'Дія', 'Доказ', 'Повернення'].map((uk) => ({ en: uk, uk })),
        value_moment: { en: 'Proof', uk: 'Доказ' }, zero_audience_behavior: { en: 'Private log', uk: 'Приватний журнал' }, substitutes: [],
        dangerous_assumptions: [{ id: 'a1', statement: { en: 'Repeat', uk: 'Повторення' }, severity: 'high' }],
        success_criterion: { metric: 'interest', operator: '>=', threshold: .2, sample_target: 10 },
        mechanism_ids: [mechanismId], evidence_ids: ['e1'], verdict: 'survives', recommended: true,
        risks: [], unsupported_high_severity_count: 0, weakest_mechanism_coverage: .5,
        recommendation_reason: 'No fatal objection.',
      }],
    }
    const api = { get: vi.fn().mockResolvedValue(collection), post: vi.fn().mockResolvedValue({}) } as unknown as ApiClient
    render(<ThesisResults api={api} runId={runId} language="uk" ready />)
    expect(await screen.findByText('Теза')).toBeInTheDocument()
    expect(screen.getByText('Цикл доказу')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Вибрати для валідації' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(`/api/v1/laval/runs/${runId}/theses/${thesisId}/select`, {}))
  })
})
