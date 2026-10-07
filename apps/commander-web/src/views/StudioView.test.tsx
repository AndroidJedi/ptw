import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { StudioPhoneMetricsDetail } from '../types'
import { StudioView } from './StudioView'

vi.mock('../components/studio/PhoneMetricsStudio', () => ({
  PhoneMetricsStudio: ({ detail }: { detail: StudioPhoneMetricsDetail }) => (
    <section aria-label="Phone Metrics editor">{detail.template_id}</section>
  ),
}))
vi.mock('../components/PostPublishing', () => ({ PostPublishing: () => null }))
vi.mock('../components/studio/DaddyStudio', () => ({ DaddyStudio: () => <section aria-label="Daddy editor" /> }))
vi.mock('../components/studio/StudioTuneWizard', () => ({
  StudioTuneWizard: ({ open }: { open: boolean }) => open ? <div>Local Tune wizard</div> : null,
}))

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const briefId = '33333333-3333-4333-8333-333333333333'
const basePath = `/api/v1/studio/projects/${projectId}/creatives/${creativeId}`

const detail = {
  creative_id: creativeId,
  project_id: projectId,
  source_brief_id: briefId,
  ordinal: 1,
  origin: 'brief_generation',
  status: 'draft',
  generation: {
    stage: 'draft',
    creative_direction: {
      schema: 'ptw.studio.phone-hero-direction.v1',
      style: 'cinematic',
      background: 'scene',
    },
  },
  approved_version_count: 0,
  schema: 'ptw.studio.workspace.v8',
  template_id: 'phone_metrics',
  templates: [{
    template_id: 'phone_metrics', name: 'Phone & metrics',
    description: 'Phone composition', canvas: { width: 1080, height: 1350 },
  }],
  catalog: { template_version: 27 },
  state_sha256: 'a'.repeat(64),
  template_sha256: 'b'.repeat(64),
  configuration: {},
  content: {},
  component_settings: { sha256: 'c'.repeat(64) },
  assets: [],
  phone_screen_history: [],
  phone_screen_generation_available: true,
  versions: [],
} as unknown as StudioPhoneMetricsDetail

function apiFor(options: { items?: unknown[]; selected?: StudioPhoneMetricsDetail } = {}) {
  const items = options.items ?? [{
    creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
    ordinal: 1, origin: 'brief_generation', template_id: 'phone_metrics',
    template_version: 27, template_sha256: 'b'.repeat(64), status: 'draft',
    state_sha256: 'a'.repeat(64), approved_version_count: 0,
    generation: detail.generation, created_at: '2026-09-20T00:00:00Z',
    updated_at: '2026-09-20T00:00:00Z',
  }]
  const post = vi.fn(async (path: string) => {
    if (path === `/api/v1/studio/projects/${projectId}/creatives`) {
      return { creative: { creative_id: '44444444-4444-4444-8444-444444444444' } }
    }
    if (path.startsWith('/api/v1/briefs/')) {
      return { creative: { creative_id: '55555555-5555-4555-8555-555555555555' } }
    }
    if (path.endsWith('/retry')) return {}
    throw new Error(`Unexpected POST ${path}`)
  })
  const get = vi.fn(async (path: string) => {
    if (path === `/api/v1/studio/projects/${projectId}/creatives`) return { items }
    if (path === basePath) return structuredClone(options.selected ?? detail)
    if (path.startsWith('/api/v1/briefs?')) return { items: [{
      brief_id: briefId, project_id: projectId, approved: true, status: 'completed',
      document: { product: 'Natal' }, product: 'Natal',
    }] }
    if (path === '/api/v1/templates?surface=post') return { items: [{
      surface: 'post', template_id: 'phone_metrics', name: 'Phone & metrics',
      description: 'Phone composition', template_version: 27,
      template_sha256: 'b'.repeat(64), previews: {},
    }, {
      surface: 'post', template_id: 'design_aaaaaaaaaaaaaaaaaaaa', name: 'Editorial Post',
      description: 'Accepted layout', template_version: 3,
      template_sha256: 'd'.repeat(64), previews: {},
    }] }
    throw new Error(`Unexpected GET ${path}`)
  })
  return {
    api: {
      get, post, postMedia: vi.fn(), media: vi.fn(), image: vi.fn(),
      websocketUrl: vi.fn(), request: vi.fn(),
    } as unknown as ApiClient,
    get, post,
  }
}

describe('Post Studio shell', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  it('labels the incomplete image failure and preserves Retry UUID after a lost response', async () => {
    const selected = structuredClone(detail)
    selected.template_id = 'daddy'
    selected.status = 'failed'
    selected.generation.daddy = { phase: 'asset:scene', corrections: 0, failure: { code: 'invalid_png_structure', slot: 'scene', provider_request_id: 1347 }, asset_operations: { scene: { slot: 'scene', attempt: 1, max_attempt: 1, attempts: {} } } }
    const { api, post } = apiFor({ selected })
    post.mockRejectedValueOnce(new Error('Connection lost'))
    const view = render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    expect(await screen.findByRole('heading', { name: 'Background image failed; your text and layout are saved' })).toBeVisible()
    expect(screen.getByText(/This preview is incomplete. The saved image file is incomplete./)).toBeVisible()
    expect(screen.getByText('Image attempt 2 · Failure code invalid_png_structure')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Retry image' }))
    await screen.findByText('Connection lost')
    const request = post.mock.calls[0]
    view.unmount()
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Retry image' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[1]).toEqual(request)
    expect(await screen.findByText('Image request #1347')).toBeVisible()
  })

  it('explains exhausted temporary image storage without calling an incomplete preview finished', async () => {
    const selected = structuredClone(detail)
    selected.template_id = 'daddy'
    selected.status = 'failed'
    selected.generation.daddy = { phase: 'asset:scene', corrections: 0, failure: { code: 'temporary_storage_full', slot: 'scene', provider_request_id: 1434 } }
    const { api } = apiFor({ selected })
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    expect(await screen.findByText(/This preview is incomplete. The image worker ran out of temporary storage./)).toBeVisible()
    expect(screen.getByText('Image request #1434')).toBeVisible()
  })

  it('opens the registered Phone Metrics editor', async () => {
    const { api } = apiFor()
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    expect(await screen.findByRole('region', { name: 'Phone Metrics editor' })).toHaveTextContent('phone_metrics')
  })

  it('reviews a retained Universal draft without opening an active editor', async () => {
    const selected = {
      ...detail, template_id: 'universal_ad', editor_key: 'post.legacy.readonly',
      legacy_read_only: true, legacy_sample_content: true,
    } as StudioPhoneMetricsDetail
    const items = [{
      creative_id: creativeId, project_id: projectId, source_brief_id: briefId,
      ordinal: 1, origin: 'brief_generation', template_id: 'universal_ad',
      template_version: 13, template_sha256: 'b'.repeat(64), status: 'draft',
      state_sha256: 'a'.repeat(64), approved_version_count: 0,
      generation: detail.generation, created_at: '2026-09-19T00:00:00Z',
      updated_at: '2026-09-19T00:00:00Z',
    }]
    const { api, post } = apiFor({ items, selected })
    vi.mocked(api.postMedia).mockReturnValue(new Promise(() => {}))
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    expect(await screen.findByRole('heading', { name: 'Retained Universal Post' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Phone Metrics editor' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Legacy Universal/ })).toBeInTheDocument()
    expect(screen.getByText(/still contains the retired template’s sample copy/)).toBeVisible()
    await waitFor(() => expect(api.postMedia).toHaveBeenCalledWith(
      `${basePath}/preview`, { state_sha256: 'a'.repeat(64) }, 'image/png',
      { deadlineMs: 90_000 },
    ))
    fireEvent.click(screen.getByRole('button', { name: 'Create current Post from Brief' }))
    const dialog = await screen.findByRole('dialog', { name: 'Choose the creative template' })
    fireEvent.click(await screen.findByRole('button', { name: /Phone & metrics/ }))
    fireEvent.click(screen.getByRole('radio', { name: /Cinematic/i }))
    fireEvent.click(screen.getByRole('radio', { name: /Keep a scene background/i }))
    fireEvent.click(dialog.querySelector('button.primary')!)
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/studio/projects/${projectId}/creatives`,
      expect.objectContaining({ source_brief_id: briefId, template_id: 'phone_metrics' }),
    ))
  })

  it('shows creation progress for a composing Post', async () => {
    const composing = { ...detail, status: 'composing', generation: { stage: 'composing' } } as StudioPhoneMetricsDetail
    const { api } = apiFor({ selected: composing })
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    expect(await screen.findByRole('heading', { name: 'Building the creative' })).toBeInTheDocument()
  })

  it('uses the registered template when creating the first Post', async () => {
    const onCreative = vi.fn()
    const { api, post } = apiFor({ items: [] })
    render(<StudioView api={api} language="en" projectId={projectId} onCreative={onCreative} />)
    fireEvent.click(await screen.findByRole('button', { name: /Phone & metrics/i }))
    fireEvent.click(screen.getByRole('radio', { name: /Cinematic/i }))
    fireEvent.click(screen.getByRole('radio', { name: /Keep a scene background/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Create creative' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/briefs/${briefId}/approve`,
      expect.objectContaining({ template_id: 'phone_metrics', template_reference: {
        surface: 'post', template_id: 'phone_metrics', template_version: 27, template_sha256: 'b'.repeat(64),
      } }),
    ))
    expect(onCreative).toHaveBeenCalledWith('55555555-5555-4555-8555-555555555555')
  })

  it('chooses the accepted layout before generating another Post from a Brief', async () => {
    const selected = { ...detail, approved_version_count: 1, versions: [{ version: 1 }] } as StudioPhoneMetricsDetail
    const { api, post } = apiFor({ selected })
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    await screen.findByRole('region', { name: 'Phone Metrics editor' })
    fireEvent.click(screen.getByText('More actions'))
    fireEvent.click(screen.getByRole('button', { name: 'Generate another from Brief' }))
    const dialog = await screen.findByRole('dialog', { name: 'Choose the creative template' })
    fireEvent.click(await screen.findByRole('button', { name: /Editorial Post/ }))
    fireEvent.click(screen.getByRole('radio', { name: /Cinematic/i }))
    fireEvent.click(screen.getByRole('radio', { name: /Keep a scene background/i }))
    fireEvent.click(dialog.querySelector('button.primary')!)
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/studio/projects/${projectId}/creatives`,
      expect.objectContaining({
        source_brief_id: briefId,
        template_id: 'design_aaaaaaaaaaaaaaaaaaaa',
        template_reference: { surface: 'post', template_id: 'design_aaaaaaaaaaaaaaaaaaaa', template_version: 3, template_sha256: 'd'.repeat(64) },
      }),
    ))
  })

  it('keeps Tune available against the active Post editor', async () => {
    const { api } = apiFor()
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} tuneMode />)
    fireEvent.click(await screen.findByRole('button', { name: 'Feedback & iterations' }))
    expect(screen.getByText('Local Tune wizard')).toBeInTheDocument()
  })
})
