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
    if (path === '/api/v1/studio/templates') return { items: detail.templates }
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
  beforeEach(() => vi.clearAllMocks())

  it('opens the registered Phone Metrics editor', async () => {
    const { api } = apiFor()
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} />)
    expect(await screen.findByRole('region', { name: 'Phone Metrics editor' })).toHaveTextContent('phone_metrics')
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
    fireEvent.click(screen.getByRole('button', { name: 'Create Phone Metrics creative' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/briefs/${briefId}/approve`,
      expect.objectContaining({ template_id: 'phone_metrics' }),
    ))
    expect(onCreative).toHaveBeenCalledWith('55555555-5555-4555-8555-555555555555')
  })

  it('keeps Tune available against the active Post editor', async () => {
    const { api } = apiFor()
    render(<StudioView api={api} language="en" projectId={projectId} creativeId={creativeId} tuneMode />)
    fireEvent.click(await screen.findByRole('button', { name: 'Feedback & iterations' }))
    expect(screen.getByText('Local Tune wizard')).toBeInTheDocument()
  })
})
