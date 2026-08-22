import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { LandingBrief, LandingBuild, LandingFeedback } from '../types'
import { LandingView } from './LandingView'

const runId = '01234567-89ab-7def-8123-456789abcdef'
const thesisId = '11234567-89ab-7def-8123-456789abcdef'
const buildId = '21234567-89ab-7def-8123-456789abcdef'
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

function build(status: LandingBuild['status'], currentBrief = brief): LandingBuild {
  return {
    id: buildId, request_id: '31234567-89ab-7def-8123-456789abcdef',
    idea_run_id: runId, thesis_id: thesisId, template_id: 'community', brief: currentBrief,
    parent_build_id: null, revision_number: 1, input_brief: currentBrief,
    skill_memory_feedback_ids: [], revision_summary: 'Скорочено hero.', revision_invocation: null,
    status, build_manifest: null, artifact_sha256: status === 'published' ? 'a'.repeat(64) : null,
    firebase_site_id: 'natal-landings-86123',
    firebase_version: status === 'published' ? 'version-1' : null,
    public_url: status === 'published' ? `https://natal-landings-86123.web.app/builds/${buildId}/` : null,
    error_code: null, error_message: null,
    created_at: '2026-08-22T00:00:00Z', updated_at: '2026-08-22T00:00:00Z',
    completed_at: status === 'published' ? '2026-08-22T00:00:01Z' : null,
  }
}

describe('LandingView', () => {
  it('starts, polls, and exposes the published landing without opening global Jobs', async () => {
    let submittedBrief = brief
    const get = vi.fn((path: string) => {
      if (path.includes('/templates')) return Promise.resolve({ items: [
        { id: 'product', version: 1, name: { uk: 'Продукт', en: 'Product' }, description: { uk: 'Функції', en: 'Features' }, best_for: [], adapted_from: 'natal_landing' },
        { id: 'community', version: 1, name: { uk: 'Спільнота / подія', en: 'Community / event' }, description: { uk: 'Участь', en: 'Participation' }, best_for: [], adapted_from: 'sesh' },
        { id: 'waitlist', version: 1, name: { uk: 'Waitlist / концепт', en: 'Waitlist / concept' }, description: { uk: 'Попит', en: 'Demand' }, best_for: [], adapted_from: 'ofc' },
      ] })
      if (path.includes('/candidates')) return Promise.resolve({ items: [
        { idea_run_id: runId, recommended_template_id: 'product', brief, quality: { successful: 8, attempted: 9 }, verdict: 'survives' },
      ] })
      if (path.includes(`/builds/${buildId}`)) return Promise.resolve(build('published', submittedBrief))
      if (path.includes('/skill-memory')) return Promise.resolve({ items: [] })
      if (path.includes('/builds')) return Promise.resolve({ items: [] })
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const savedFeedback: LandingFeedback = {
      id: '41234567-89ab-7def-8123-456789abcdef', build_id: buildId,
      idea_run_id: runId, template_id: 'community', revision_number: 1,
      comment: 'Скоротіть hero', weight_update_id: '51234567-89ab-7def-8123-456789abcdef',
      created_at: '2026-08-22T00:00:02Z',
    }
    const post = vi.fn((path: string, body: { brief?: LandingBrief; comment?: string }) => {
      if (path.endsWith('/feedback')) return Promise.resolve({ ...savedFeedback, comment: body.comment || '' })
      submittedBrief = body.brief || brief
      return Promise.resolve(build('queued', submittedBrief))
    })
    const api = { get, post } as unknown as ApiClient
    render(<LandingView api={api} language="uk" />)

    expect(await screen.findByDisplayValue('Автоматичне утримання клієнтів')).toBeInTheDocument()
    expect(screen.getByText(/РЕКОМЕНДОВАНО/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText(/Спільнота \/ подія/))
    fireEvent.change(screen.getByLabelText('Бізнес-ідея'), { target: { value: 'Нова перевірена теза' } })
    fireEvent.click(screen.getByRole('button', { name: /Застосувати community і опублікувати/ }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post.mock.calls[0][0]).toBe('/api/v1/landings/builds')
    expect(post.mock.calls[0][1]).toMatchObject({
      idea_run_id: runId,
      template_id: 'community',
      brief: { business_idea: 'Нова перевірена теза', brand: 'Natal' },
    })
    expect(await screen.findByRole('heading', { name: 'Версію опубліковано' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Відкрити окремо/ })).toHaveAttribute(
      'href', `https://natal-landings-86123.web.app/builds/${buildId}/`,
    )
    expect(screen.getByTitle('Natal landing version 1')).toHaveAttribute(
      'src', `https://natal-landings-86123.web.app/builds/${buildId}/`,
    )
    fireEvent.change(screen.getByLabelText('Що змінити в наступній версії?'), { target: { value: 'Скоротіть hero' } })
    fireEvent.click(screen.getByRole('button', { name: /Зберегти відгук у Natal skill/ }))
    expect(await screen.findByText('Скоротіть hero')).toBeInTheDocument()
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[1][0]).toBe(`/api/v1/landings/builds/${buildId}/feedback`)
    fireEvent.click(screen.getByLabelText(/Waitlist \/ концепт/))
    fireEvent.click(screen.getByRole('button', { name: /Застосувати waitlist і опублікувати/ }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(3))
    expect(post.mock.calls[2][1]).toMatchObject({
      idea_run_id: runId,
      template_id: 'waitlist',
      parent_build_id: buildId,
    })
    expect(screen.queryByText('Відкрити Завдання')).not.toBeInTheDocument()
    expect(screen.getByText('Усі шаблони й версії')).toBeInTheDocument()
  })
})
