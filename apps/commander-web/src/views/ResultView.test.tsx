import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { ContentRun, ProductBrief } from '../types'
import { ResultView } from './ResultView'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const brief: ProductBrief = {
  brief_id: '018f07ea-7f20-7000-8000-000000000002',
  project_id: projectId,
  project_name: 'Horoscope',
  request_id: '018f07ea-7f20-7000-8000-000000000003',
  owner_idea_source_id: '018f07ea-7f20-7000-8000-000000000004',
  raw_idea: 'Personalized horoscope for job seekers',
  status: 'completed', failure_count: 0, approved: true,
  product: 'Event-based personalized horoscope for job seekers',
  promise: 'Receive personalized guidance for the next move.',
  created_at: '2026-08-26T10:00:00Z',
}
const run: ContentRun = {
  run_id: '018f07ea-7f20-7000-8000-000000000005',
  request_id: '018f07ea-7f20-7000-8000-000000000006',
  project_id: projectId,
  brief_id: brief.brief_id,
  output_profile: 'instagram_static_ad_v1',
  task: 'Server-owned Instagram task',
  status: 'queued', current_stage: 'queued', progress_percent: 0,
  maximum_minutes: 45,
  created_at: '2026-08-26T10:05:00Z', updated_at: '2026-08-26T10:05:00Z',
}

function apiWith(post = vi.fn().mockResolvedValue(run)) {
  return {
    get: vi.fn(async (path: string) => {
      if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
      if (path.startsWith('/api/v1/content-runs?')) return { items: [] }
      if (path === `/api/v1/content-runs/${run.run_id}`) return run
      throw new Error(`Unexpected GET ${path}`)
    }),
    post, image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
  } as unknown as ApiClient
}

describe('Instagram Result owner flow', () => {
  it('requires no task, text-mode choice, asset, or brand-kit input', async () => {
    const post = vi.fn().mockResolvedValue(run)
    render(<ResultView api={apiWith(post)} projectId={projectId} language="en" />)

    await screen.findByText(brief.product!)
    expect(screen.queryByText('PROJECT BRAND KIT')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Task')).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: 'Text' })).not.toBeInTheDocument()
    expect(screen.getByText('Natal branding is applied automatically. Nothing else is required.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Create Instagram post' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/content-runs', {
      request_id: expect.any(String), brief_id: brief.brief_id,
    }, { deadlineMs: 60_000 }))
    expect(await screen.findByRole('status')).toHaveTextContent('Instagram post creation started.')
  })
})
