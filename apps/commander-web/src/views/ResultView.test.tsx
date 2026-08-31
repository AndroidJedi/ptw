import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import type { ApiClient } from '../api'
import type { ContentResult, ContentRun, ProductBrief, ValidationProject } from '../types'
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
const project: ValidationProject = {
  project_id: projectId,
  request_id: '018f07ea-7f20-7000-8000-000000000011',
  owner_idea_source_id: brief.owner_idea_source_id,
  name: 'Horoscope', name_source: 'owner', requested_by: 'owner',
  result_creation_enabled: true, latest_brief_id: brief.brief_id,
  latest_brief_status: 'completed', brief_count: 1, result_run_count: 1,
  created_at: '2026-08-26T10:00:00Z', updated_at: '2026-08-26T10:00:00Z',
}
const run: ContentRun = {
  run_id: '018f07ea-7f20-7000-8000-000000000005',
  request_id: '018f07ea-7f20-7000-8000-000000000006',
  project_id: projectId,
  brief_id: brief.brief_id,
  output_profile: 'instagram_static_ad_v1', platform: 'instagram',
  task: 'Server-owned Instagram task', review_state: 'unreviewed', revision_number: 0,
  status: 'completed', current_stage: 'completed', progress_percent: 100,
  maximum_minutes: 45, final_result_id: '018f07ea-7f20-7000-8000-000000000007',
  created_at: '2026-08-26T10:05:00Z', updated_at: '2026-08-26T10:45:00Z',
}
const result: ContentResult = {
  creative_id: run.final_result_id!, run_id: run.run_id,
  selected_candidate_id: '018f07ea-7f20-7000-8000-000000000008',
  decision_summary: ['bounded decision'], result_sha256: 'b'.repeat(64),
  content_sha256: 'c'.repeat(64), asset_sha256: 'a'.repeat(64),
  asset_mime_type: 'image/jpeg', asset_width: 1080, asset_height: 1080,
  asset_url: `/api/v1/content-runs/${run.run_id}/asset`,
  content: {
    hook: 'REDUNDANT HOOK MUST NOT APPEAR', headline: 'REDUNDANT HEADLINE MUST NOT APPEAR',
    primary_text: 'REDUNDANT BODY MUST NOT APPEAR', supporting_text: 'REDUNDANT SUPPORT MUST NOT APPEAR',
    offer: 'Offer inside the rendered post', cta: 'CTA inside the rendered post',
    caption: 'One conversation can make the next step clearer.',
    alt_text: 'A calm branded square post inviting a first conversation.',
    desired_emotion: 'calm', visual_concept: 'quiet first step',
  },
  created_at: '2026-08-26T10:45:00Z',
}

function props(api: ApiClient, extras: Partial<ComponentProps<typeof ResultView>> = {}) {
  return {
    api, projectId, projects: [project], language: 'en' as const,
    onProjectSelect: vi.fn(), onNewProject: vi.fn(), onRenameProject: vi.fn(async () => undefined),
    onRunSelect: vi.fn(), onOpenBriefs: vi.fn(), ...extras,
  }
}

beforeEach(() => {
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:social-post') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn(async () => undefined) } })
})

describe('Social Posts workspace', () => {
  it('creates either platform from the latest approved Brief without redundant setup fields', async () => {
    const queued = { ...run, status: 'queued', current_stage: 'queued', progress_percent: 0 } as ContentRun
    const post = vi.fn().mockResolvedValue(queued)
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [] }
        if (path === `/api/v1/content-runs/${queued.run_id}`) return queued
        throw new Error(`Unexpected GET ${path}`)
      }),
      post, image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    render(<ResultView {...props(api)} />)
    await screen.findByRole('heading', { name: 'Create the first social post' })
    fireEvent.click(screen.getAllByRole('button', { name: 'New post' })[0])

    expect(await screen.findByText(brief.product!)).toBeInTheDocument()
    expect(screen.queryByLabelText('Task')).not.toBeInTheDocument()
    expect(screen.queryByText('PROJECT BRAND KIT')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: /TikTok/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Create post' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/content-runs', {
      request_id: expect.any(String), brief_id: brief.brief_id, platform: 'tiktok',
    }, { deadlineMs: 60_000 }))
  })

  it('explains the missing approved Brief instead of silently disabling creation', async () => {
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [] }
        throw new Error(`Unexpected GET ${path}`)
      }),
      post: vi.fn(), image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient
    const onOpenBriefs = vi.fn()
    render(<ResultView {...props(api, { onOpenBriefs })} />)
    await screen.findByRole('heading', { name: 'Create the first social post' })
    fireEvent.click(screen.getAllByRole('button', { name: 'New post' })[0])

    expect(await screen.findByText('Approve a completed Product Brief before creating a post.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Create post' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Open Product Briefs' }))
    expect(onOpenBriefs).toHaveBeenCalledOnce()
  })

  it('shows a native post, gates export behind Ready, and does not transcribe rendered fields', async () => {
    let reviewState: ContentRun['review_state'] = 'unreviewed'
    const currentRun = () => ({ ...run, review_state: reviewState })
    const post = vi.fn(async (path: string) => {
      if (path.endsWith('/feedback')) { reviewState = 'ready'; return { feedback_id: 'feedback' } }
      throw new Error(`Unexpected POST ${path}`)
    })
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [currentRun()] }
        if (path === `/api/v1/content-runs/${run.run_id}`) return currentRun()
        if (path === `/api/v1/content-runs/${run.run_id}/result`) return result
        throw new Error(`Unexpected GET ${path}`)
      }),
      post, image: vi.fn(async () => new Blob(['image'], { type: 'image/jpeg' })),
      media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    render(<ResultView {...props(api, { runId: run.run_id })} />)

    const preview = await screen.findByRole('article', { name: 'instagram post preview' })
    expect(within(preview).getByText(result.content.caption)).toBeInTheDocument()
    expect(screen.queryByText(result.content.hook)).not.toBeInTheDocument()
    expect(screen.queryByText(result.content.headline)).not.toBeInTheDocument()
    expect(screen.queryByText('SOURCE')).not.toBeInTheDocument()
    expect(screen.queryByText('WHY THIS DIRECTION')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download image' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Ready' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/content-runs/${run.run_id}/feedback`, { decision: 'accepted' },
    ))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download image' })).toBeEnabled())
  })

  it('requires a bounded change comment and starts a child revision', async () => {
    const child = {
      ...run, run_id: '018f07ea-7f20-7000-8000-000000000009',
      request_id: '018f07ea-7f20-7000-8000-000000000010', parent_run_id: run.run_id,
      revision_number: 1, status: 'queued', current_stage: 'queued', progress_percent: 0,
      final_result_id: null,
    } as ContentRun
    const post = vi.fn().mockResolvedValue(child)
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [run] }
        if (path === `/api/v1/content-runs/${run.run_id}`) return run
        if (path === `/api/v1/content-runs/${run.run_id}/result`) return result
        throw new Error(`Unexpected GET ${path}`)
      }),
      post, image: vi.fn(async () => new Blob(['image'], { type: 'image/jpeg' })),
      media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    render(<ResultView {...props(api, { runId: run.run_id })} />)
    await screen.findByRole('article', { name: 'instagram post preview' })
    const improve = screen.getByRole('button', { name: 'Improve' })
    expect(improve).toBeDisabled()
    fireEvent.change(screen.getByLabelText('What should change?'), { target: { value: 'Move the CTA higher.' } })
    expect(improve).toBeEnabled()
    fireEvent.click(improve)

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/content-runs/${run.run_id}/revisions`,
      { request_id: expect.any(String), comment: 'Move the CTA higher.' },
      { deadlineMs: 60_000 },
    ))
  })

  it('filters the navigator, groups revision labels, and preserves per-artifact drafts', async () => {
    const child = {
      ...run, run_id: '018f07ea-7f20-7000-8000-000000000021',
      request_id: '018f07ea-7f20-7000-8000-000000000022', parent_run_id: run.run_id,
      revision_number: 1, created_at: '2026-08-26T10:06:00Z',
      status: 'queued', current_stage: 'queued', progress_percent: 0,
    } as ContentRun
    const tiktok = {
      ...run, run_id: '018f07ea-7f20-7000-8000-000000000023',
      request_id: '018f07ea-7f20-7000-8000-000000000024',
      output_profile: 'tiktok_photo_post_v1', platform: 'tiktok',
      created_at: '2026-08-26T10:07:00Z',
    } as ContentRun
    const runs = [tiktok, child, run]
    const byId = Object.fromEntries(runs.map((item) => [item.run_id, item]))
    const resultFor = (item: ContentRun): ContentResult => ({
      ...result, run_id: item.run_id, creative_id: `${item.run_id.slice(0, -3)}101`,
      asset_url: `/api/v1/content-runs/${item.run_id}/result/asset`,
      asset_height: item.platform === 'tiktok' ? 1920 : 1080,
    })
    const otherProject = { ...project, project_id: '018f07ea-7f20-7000-8000-000000000025', name: 'Other Project' }
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: runs }
        const resultMatch = path.match(/^\/api\/v1\/content-runs\/([^/]+)\/result$/)
        if (resultMatch) return resultFor(byId[resultMatch[1]])
        const runMatch = path.match(/^\/api\/v1\/content-runs\/([^/]+)$/)
        if (runMatch) return byId[runMatch[1]]
        throw new Error(`Unexpected GET ${path}`)
      }),
      post: vi.fn(), image: vi.fn(async () => new Blob(['image'], { type: 'image/jpeg' })),
      media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient
    const base = props(api, { projects: [project, otherProject], runId: run.run_id })
    const view = render(<ResultView {...base} />)
    const navigator = await screen.findByLabelText('Projects and artifacts')
    await screen.findByRole('article', { name: 'instagram post preview' })
    expect(within(navigator).getByText('Instagram · R2')).toBeInTheDocument()
    expect(within(navigator).getByText('TikTok · R1')).toBeInTheDocument()

    fireEvent.change(within(navigator).getByPlaceholderText('Search projects'), { target: { value: 'Other' } })
    expect(within(navigator).getByText('Other Project')).toBeInTheDocument()
    expect(within(navigator).queryByRole('button', { name: /Horoscope/ })).not.toBeInTheDocument()
    fireEvent.change(within(navigator).getByPlaceholderText('Search projects'), { target: { value: '' } })
    fireEvent.change(within(navigator).getByLabelText('Filter by platform'), { target: { value: 'tiktok' } })
    expect(within(navigator).getByText('TikTok · R1')).toBeInTheDocument()
    expect(within(navigator).queryByText('Instagram · R2')).not.toBeInTheDocument()
    fireEvent.change(within(navigator).getByLabelText('Filter by platform'), { target: { value: 'all' } })
    fireEvent.change(within(navigator).getByLabelText('Filter by generation status'), { target: { value: 'active' } })
    expect(within(navigator).getByText('Instagram · R2')).toBeInTheDocument()
    expect(within(navigator).queryByText('Instagram · R1')).not.toBeInTheDocument()
    expect(within(navigator).queryByText('TikTok · R1')).not.toBeInTheDocument()
    fireEvent.change(within(navigator).getByLabelText('Filter by generation status'), { target: { value: 'all' } })

    fireEvent.change(screen.getByLabelText('What should change?'), { target: { value: 'Keep this draft for the square artifact.' } })
    view.rerender(<ResultView {...props(api, { projects: [project, otherProject], runId: tiktok.run_id })} />)
    await screen.findByRole('article', { name: 'tiktok post preview' })
    expect(screen.getByLabelText('What should change?')).toHaveValue('')
    view.rerender(<ResultView {...props(api, { projects: [project, otherProject], runId: run.run_id })} />)
    await screen.findByRole('article', { name: 'instagram post preview' })
    expect(screen.getByLabelText('What should change?')).toHaveValue(
      'Keep this draft for the square artifact.',
    )
  })
})
