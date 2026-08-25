import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { CreativeBatch } from '../types'
import { AdsView } from './AdsView'

const completed: CreativeBatch = {
  project_id: '01a03327-1111-7111-8111-111111111111',
  project_name: 'Online psychologist consultations',
  batch_id: '01a03327-a038-72a6-85ae-e50983b0e6f4',
  brief_id: '01a03327-3006-7449-848e-7153ec4d572e',
  status: 'completed', failure_count: 0, creatives: [],
  lesson_status_counts: { promoted: 4 }, created_at: '2026-08-24T09:43:50Z',
}

function client() {
  const next = { ...completed, batch_id: '01a03328-a038-72a6-85ae-e50983b0e6f4', status: 'queued' as const }
  return {
    get: vi.fn(async (path: string) => {
      if (path.startsWith('/api/v1/skill-proposals/')) return { items: [] }
      if (path.includes(next.batch_id)) return next
      if (path === `/api/v1/ad-batches?limit=100&project_id=${completed.project_id}`) return { items: [completed] }
      return completed
    }),
    post: vi.fn().mockResolvedValue({ batch: next, generation_started: true }),
    websocketUrl: vi.fn(),
  } as unknown as ApiClient
}

describe('Ads feedback rerun action', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows one confirmed action and starts a separate batch using feedback', async () => {
    const api = client()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<AdsView api={api} projectId={completed.project_id} />)
    const action = await screen.findByRole('button', { name: 'Generate new Ads with feedback' })
    expect(screen.getByRole('heading', { name: 'Run the Ad agent again' })).toBeVisible()

    fireEvent.click(action)
    expect(api.post).not.toHaveBeenCalled()

    confirm.mockReturnValue(true)
    fireEvent.click(action)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      `/api/v1/ad-batches/${completed.batch_id}/rerun`,
      { request_id: expect.any(String), confirmation: 'GENERATE NEW BATCH' },
    ))
  })
})
