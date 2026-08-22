import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { LandingBrief } from '../types'
import { LandingView } from './LandingView'

const runId = '01234567-89ab-7def-8123-456789abcdef'
const thesisId = '11234567-89ab-7def-8123-456789abcdef'
const brief: LandingBrief = {
  schema_version: 1, brand: 'Natal', language: 'uk',
  source: { laval_run_id: runId, thesis_id: thesisId },
  business_idea: 'Автоматичне утримання клієнтів',
  target_audience: 'Власники сервісного бізнесу',
  pain: 'Клієнти зникають непомітно',
  promise: 'Natal показує наступну дію',
  key_features: [{ title: 'Сигнали ризику', description: 'Помічає зміни раніше' }],
  steps: [{ title: '01', description: 'Підключіть дані' }, { title: '02', description: 'Побачте ризик' }],
  proof_points: [], faq: [], cta: { label: 'Спробувати Natal', url: '#contact' },
}

describe('LandingView', () => {
  it('prefills a completed evaluation, permits template override, and creates a builder plan', async () => {
    const post = vi.fn().mockResolvedValue({
      id: 'job-1', mode: 'plan', title: 'Natal build', status: 'planning', created_at: '', created_by: 'firebase:owner',
      landing: { build_id: 'build-1', idea_run_id: runId, template_id: 'community', recommended_template_id: 'product', output_path: 'output/landings/build-1', brief },
    })
    const api = {
      get: vi.fn((path: string) => path.includes('/templates') ? Promise.resolve({ items: [
        { id: 'product', version: 1, name: { uk: 'Продукт', en: 'Product' }, description: { uk: 'Функції', en: 'Features' }, best_for: [], adapted_from: 'natal_landing' },
        { id: 'community', version: 1, name: { uk: 'Спільнота / подія', en: 'Community / event' }, description: { uk: 'Участь', en: 'Participation' }, best_for: [], adapted_from: 'sesh' },
        { id: 'waitlist', version: 1, name: { uk: 'Waitlist / концепт', en: 'Waitlist / concept' }, description: { uk: 'Попит', en: 'Demand' }, best_for: [], adapted_from: 'ofc' },
      ] }) : Promise.resolve({ items: [{ idea_run_id: runId, recommended_template_id: 'product', brief, quality: { successful: 8, attempted: 9 }, verdict: 'survives' }] })),
      post,
    } as unknown as ApiClient
    const openJobs = vi.fn()
    render(<LandingView api={api} language="uk" onOpenJobs={openJobs} />)

    expect(await screen.findByDisplayValue('Автоматичне утримання клієнтів')).toBeInTheDocument()
    expect(screen.getByText('РЕКОМЕНДОВАНО')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText(/Спільнота \/ подія/))
    fireEvent.change(screen.getByLabelText('Бізнес-ідея'), { target: { value: 'Нова перевірена теза' } })
    fireEvent.click(screen.getByRole('button', { name: /Передати Natal builder agent/ }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post.mock.calls[0][0]).toBe('/api/v1/landings/builder-jobs')
    expect(post.mock.calls[0][1]).toMatchObject({
      idea_run_id: runId,
      template_id: 'community',
      brief: { business_idea: 'Нова перевірена теза', brand: 'Natal' },
    })
    expect(await screen.findByText('Builder plan створено')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Відкрити Завдання' }))
    expect(openJobs).toHaveBeenCalledOnce()
  })
})
