import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import type { ApiClient } from '../api'
import type {
  ContentCreative, ContentReview, ContentRun, ProductBrief, ValidationProject,
} from '../types'
import { ResultView } from './ResultView'

const project: ValidationProject = {
  project_id: '018f07ea-7f20-7000-8000-000000000001',
  request_id: '018f07ea-7f20-7000-8000-000000000002',
  owner_idea_source_id: '018f07ea-7f20-7000-8000-000000000003',
  name: 'Natal', name_source: 'owner', requested_by: 'owner', result_creation_enabled: true,
  brief_count: 1, result_run_count: 1, created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
}

const brief: ProductBrief = {
  brief_id: '018f07ea-7f20-7000-8000-000000000004', project_id: project.project_id,
  project_name: project.name, request_id: '018f07ea-7f20-7000-8000-000000000005',
  owner_idea_source_id: project.owner_idea_source_id, raw_idea: 'Idea', product: 'Natal',
  status: 'completed', approved: true, failure_count: 0, created_at: '2026-09-01T10:00:00Z',
}

const run: ContentRun = {
  run_id: '018f07ea-7f20-7000-8000-000000000100',
  request_id: '018f07ea-7f20-7000-8000-000000000101',
  project_id: project.project_id, brief_id: brief.brief_id,
  output_profile: 'instagram_static_ad_v1', platform: 'instagram', task: 'Server task',
  status: 'awaiting_review', current_stage: 'awaiting_review', progress_percent: 100,
  maximum_minutes: 45, generation_kind: 'initial', generated_creative_ids: [],
  review_creative_ids: [], notification_state: 'delivered',
  created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
}

function creative(index: number): ContentCreative {
  return {
    creative_id: `018f07ea-7f20-7000-8000-00000000011${index}`,
    run_id: run.run_id, slot: `C${index}`, round: 0, generation_kind: 'initial',
    template_id: `strategy-${index}`, template_version: 1,
    parameters: {
      hook_pressure: 20, emotional_intensity: 30, conceptual_novelty: 40,
      information_density: 50, visual_complexity: 60,
    },
    document: {
      hook: `Hook ${index}`, headline: `Headline ${index}`, primary_text: `Primary ${index}`,
      supporting_text: `Support ${index}`, offer: `Offer ${index}`, cta: `CTA ${index}`,
      caption: `Caption ${index}`, alt_text: `Alt ${index}`, desired_emotion: 'calm',
      visual_concept: `Concept ${index}`,
    },
    document_sha256: String(index).repeat(64),
    preview: {
      asset_url: `/api/v1/content-runs/${run.run_id}/creatives/creative-${index}/asset`,
      sha256: String(index).repeat(64), mime_type: 'image/jpeg', width: 1080, height: 1080,
    },
    created_at: '2026-09-01T10:00:00Z',
  }
}

const creatives = [1, 2, 3, 4, 5].map(creative)
run.generated_creative_ids = creatives.map((item) => item.creative_id)
run.review_creative_ids = creatives.map((item) => item.creative_id)

function review(overrides: Partial<ContentReview> = {}): ContentReview {
  return {
    schema: 'ptw.owner-creative-review.v1', run, creatives, owner_actions: [],
    notification: {
      receipt_id: '018f07ea-7f20-7000-8000-000000000180', status: 'delivered',
      attempt_count: 1, created_at: '2026-09-01T10:01:00Z', updated_at: '2026-09-01T10:01:00Z',
    },
    applied_project_rules: [], ...overrides,
  }
}

function client(reviewValue = review()) {
  const post = vi.fn(async (path: string) => {
    if (path.endsWith('/review/approve')) return { run: { ...run, status: 'approved' } }
    if (path.endsWith('/review/tune') || path.endsWith('/review/regenerate-all')) {
      return { ...run, run_id: '018f07ea-7f20-7000-8000-000000000200', status: 'queued', current_stage: 'queued' }
    }
    if (path.endsWith('/review-notification/retry')) return { status: 'delivered' }
    throw new Error(`Unexpected POST ${path}`)
  })
  const get = vi.fn(async (path: string) => {
    if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
    if (path.startsWith('/api/v1/content-runs?')) return { items: [run] }
    if (path === `/api/v1/content-runs/${run.run_id}`) return run
    if (path === `/api/v1/content-runs/${run.run_id}/review`) return reviewValue
    throw new Error(`Unexpected GET ${path}`)
  })
  const api = {
    get, post,
    image: vi.fn().mockResolvedValue(new Blob(['image'], { type: 'image/jpeg' })),
    download: vi.fn().mockResolvedValue(new Blob(['zip'], { type: 'application/zip' })),
  } as unknown as ApiClient
  return { api, get, post }
}

function renderView(api: ApiClient, localDemo = false) {
  const onRunSelect = vi.fn()
  render(<ResultView
    api={api} projectId={project.project_id} projects={[project]} runId={run.run_id}
    onProjectSelect={vi.fn()} onRunSelect={onRunSelect} onOpenBriefs={vi.fn()} language="en"
    localDemo={localDemo}
  />)
  return onRunSelect
}

beforeEach(() => vi.restoreAllMocks())

describe('owner-reviewed Result workspace', () => {
  test('shows exactly five selectable Creatives without an automatic decision trace', async () => {
    const { api } = client()
    renderView(api)
    expect(await screen.findAllByRole('radio')).toHaveLength(5)
    expect(screen.getByRole('heading', { name: 'Five verified creative directions' })).toBeVisible()
    expect(screen.queryByText(/final selection/i)).not.toBeInTheDocument()
  })

  test('keeps asset management, debug history, and integrity disclaimers out of local Social posts', async () => {
    const { api, get } = client()
    renderView(api, true)
    await screen.findAllByRole('radio')

    expect(screen.queryByText('Local Project evidence')).not.toBeInTheDocument()
    expect(screen.queryByText('Approved asset pool')).not.toBeInTheDocument()
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining('/assets'))
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining('/learning-summary'))

    fireEvent.click(screen.getByRole('button', { name: 'New set' }))
    expect(screen.queryByText(/Five distinct verified renders/)).not.toBeInTheDocument()
    expect(screen.queryByText(/automatic evaluation or selection/)).not.toBeInTheDocument()
  })

  test('approves the selected Creative through the review endpoint', async () => {
    const { api, post } = client()
    renderView(api)
    await screen.findAllByRole('radio')
    fireEvent.click(screen.getByRole('radio', { name: /Headline 3/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/content-runs/${run.run_id}/review/approve`,
      expect.objectContaining({ creative_id: creatives[2].creative_id, request_id: expect.any(String) }),
    ))
  })

  test('requires a bounded comment and tunes only the selected Creative', async () => {
    const { api, post } = client()
    renderView(api)
    await screen.findAllByRole('radio')
    const tune = screen.getByRole('button', { name: 'Tune selected' })
    expect(tune).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Tune comment for the selected post'), { target: { value: 'Make the CTA quieter.' } })
    fireEvent.click(tune)
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/content-runs/${run.run_id}/review/tune`,
      expect.objectContaining({ creative_id: creatives[0].creative_id, comment: 'Make the CTA quieter.' }),
      { deadlineMs: 60_000 },
    ))
  })

  test('regenerates the complete review set', async () => {
    const { api, post } = client()
    renderView(api)
    await screen.findAllByRole('radio')
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate all' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/content-runs/${run.run_id}/review/regenerate-all`,
      { request_id: expect.any(String) }, { deadlineMs: 60_000 },
    ))
  })

  test('keeps review available and exposes manual retry after a definite notification failure', async () => {
    const failedNotification = review({
      notification: {
        receipt_id: '018f07ea-7f20-7000-8000-000000000180', status: 'definite_failure',
        attempt_count: 3, error_message: 'relay unavailable',
        created_at: '2026-09-01T10:01:00Z', updated_at: '2026-09-01T10:01:00Z',
      },
    })
    const { api, post } = client(failedNotification)
    renderView(api)
    expect(await screen.findAllByRole('radio')).toHaveLength(5)
    fireEvent.click(screen.getByRole('button', { name: 'Retry notification' }))
    expect(post).toHaveBeenCalledWith(
      `/api/v1/content-runs/${run.run_id}/review-notification/retry`, {},
    )
  })
})
