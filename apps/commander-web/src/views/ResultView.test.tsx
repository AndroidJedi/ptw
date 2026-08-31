import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import type { ApiClient } from '../api'
import type { ContentDebug, ContentResult, ContentRun, ProductBrief, ValidationProject } from '../types'
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
    onProjectSelect: vi.fn(), onRunSelect: vi.fn(), onOpenBriefs: vi.fn(), ...extras,
  }
}

beforeEach(() => {
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:social-post') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn(async () => undefined) } })
})

describe('Social Posts workspace', () => {
  it('keeps an empty Project focused on project selection and one create action', async () => {
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [] }
        throw new Error(`Unexpected GET ${path}`)
      }),
      post: vi.fn(), image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    render(<ResultView {...props(api, { localDemo: true })} />)

    expect(await screen.findByRole('heading', { name: 'Create the first social post' })).toBeInTheDocument()
    expect(screen.getByLabelText('Project')).toHaveValue(projectId)
    expect(screen.getAllByRole('button', { name: 'New post' })).toHaveLength(1)
    expect(screen.queryByRole('heading', { name: 'Social posts' })).not.toBeInTheDocument()
    expect(screen.queryByText('CREATE · REVIEW · IMPROVE')).not.toBeInTheDocument()
    expect(screen.queryByText(/Local evaluation and learning only/)).not.toBeInTheDocument()
    expect(screen.queryByText('LOCAL QUALITY EVIDENCE')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Learning & evidence' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Filter by platform')).not.toBeInTheDocument()
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining('/assets'))
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining('/learning-summary'))
  })

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
    fireEvent.click(screen.getByRole('button', { name: 'New post' }))

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
    fireEvent.click(screen.getByRole('button', { name: 'New post' }))

    expect(await screen.findByText('Approve a completed Product Brief before creating a post.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Create post' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Open Product Briefs' }))
    expect(onOpenBriefs).toHaveBeenCalledOnce()
  })

  it('replaces the retired photo-preflight instruction on an immutable failed run', async () => {
    const failed = {
      ...run, status: 'failed', current_stage: 'failed', final_result_id: null,
      error_code: 'ValueError',
      error_message: 'asset preflight needs 4 more distinct approved real photo(s); upload and approve them or configure PEXELS_API_KEY before starting the run',
    } as ContentRun
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [failed] }
        if (path === `/api/v1/content-runs/${failed.run_id}`) return failed
        throw new Error(`Unexpected GET ${path}`)
      }),
      post: vi.fn(), image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    render(<ResultView {...props(api, { runId: failed.run_id })} />)

    expect(await screen.findByText('This attempt used the retired photo preflight. Retry now—approved photos and Pexels are optional.')).toBeVisible()
    expect(screen.queryByText(/asset preflight needs/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry as a child artifact' })).toBeEnabled()
  })

  it('turns the old local Codex timeout into actionable retry guidance', async () => {
    const failed = {
      ...run, status: 'failed', current_stage: 'failed', final_result_id: null,
      error_code: 'LocalCodexError',
      error_message: 'local Codex structured call failed after two attempts: TimeoutExpired',
    } as ContentRun
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [failed] }
        if (path === `/api/v1/content-runs/${failed.run_id}`) return failed
        throw new Error(`Unexpected GET ${path}`)
      }),
      post: vi.fn(), image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    const view = render(<ResultView {...props(api, { runId: failed.run_id })} />)

    expect(await screen.findByText('This is the immutable record of the earlier five-image timeout. The restarted app now uses smaller analysis artifacts and grouped 3–2–2 critic calls. Retry as a child artifact.')).toBeVisible()
    expect(screen.queryByText(/TimeoutExpired/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry as a child artifact' })).toBeEnabled()

    view.rerender(<ResultView {...props(api, { runId: failed.run_id, language: 'uk' })} />)
    expect(await screen.findByText('Це незмінний запис попереднього тайм-ауту з п’ятьма зображеннями. Перезапущений застосунок тепер використовує зменшені артефакти аналізу та згруповані виклики критика 3–2–2. Натисніть «Повторити як дочірній артефакт».')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Повторити як дочірній артефакт' })).toBeEnabled()
  })

  it('automatically exposes persisted intermediate evidence for a failed local run', async () => {
    const failed = {
      ...run, status: 'failed', current_stage: 'failed', progress_percent: 84,
      final_result_id: null, error_code: 'ValueError',
      error_message: 'critic selected no eligible Universal Result; correct the Brief/assets/layout and retry',
    } as ContentRun
    const debug = {
      candidates: [{
        candidate_id: result.selected_candidate_id, alias: 'C1', round: 0,
        generation_kind: 'initial', template_id: 'mechanism_proof', template_version: 3,
        parameters: {
          hook_pressure: 50, emotional_intensity: 50, conceptual_novelty: 50,
          information_density: 50, visual_complexity: 50,
        },
        document: result.content,
        preview: {
          asset_url: `/api/v1/content-runs/${failed.run_id}/candidates/${result.selected_candidate_id}/asset`,
          sha256: 'd'.repeat(64), mime_type: 'image/jpeg', width: 1080, height: 1080,
        },
      }],
      critic_passes: [],
    } as ContentDebug
    const api = {
      get: vi.fn(async (path: string) => {
        if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
        if (path.startsWith('/api/v1/content-runs?')) return { items: [failed] }
        if (path === `/api/v1/content-runs/${failed.run_id}`) return failed
        if (path === `/api/v1/content-runs/${failed.run_id}/debug`) return debug
        throw new Error(`Unexpected GET ${path}`)
      }),
      post: vi.fn(), image: vi.fn(async () => new Blob(['image'], { type: 'image/jpeg' })),
      media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient

    render(<ResultView {...props(api, { runId: failed.run_id, localDemo: true })} />)

    expect(await screen.findByRole('heading', { name: 'Everything produced before the final rejection' })).toBeVisible()
    expect(screen.getByText('The critic completed all three stages, but neither finalist passed every eligibility rule. The complete intermediate evidence is shown below.')).toBeVisible()
    expect(screen.queryByText(/correct the Brief\/assets\/layout/)).not.toBeInTheDocument()
    expect(screen.getByText('Every image and its exact generation parameters')).toBeVisible()
    expect(api.get).toHaveBeenCalledWith(`/api/v1/content-runs/${failed.run_id}/debug`)
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

  it('selects Projects and posts while preserving per-post drafts', async () => {
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
    const onProjectSelect = vi.fn()
    const onRunSelect = vi.fn()
    const base = props(api, { projects: [project, otherProject], runId: run.run_id, onProjectSelect, onRunSelect })
    const view = render(<ResultView {...base} />)
    await screen.findByRole('article', { name: 'instagram post preview' })
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: otherProject.project_id } })
    expect(onProjectSelect).toHaveBeenCalledWith(otherProject.project_id)
    const postPicker = screen.getByLabelText('Post')
    expect(within(postPicker).getByRole('option', { name: 'Instagram · R2' })).toBeInTheDocument()
    expect(within(postPicker).getByRole('option', { name: 'TikTok · R1' })).toBeInTheDocument()
    fireEvent.change(postPicker, { target: { value: tiktok.run_id } })
    expect(onRunSelect).toHaveBeenCalledWith(tiktok.run_id)
    expect(screen.queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Filter by generation status')).not.toBeInTheDocument()

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
