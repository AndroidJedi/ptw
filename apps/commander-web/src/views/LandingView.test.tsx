import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { LandingDetail } from '../types'
import { LandingView } from './LandingView'

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const landingId = '33333333-3333-4333-8333-333333333333'

function landingDetail(status: LandingDetail['status'] = 'draft'): LandingDetail {
  return {
    schema: 'ptw.landing.workspace.v1', landing_id: landingId, project_id: projectId,
    source_brief_id: '44444444-4444-4444-8444-444444444444', source_creative_id: creativeId,
    source_version: 2, source_version_sha256: 'a'.repeat(64), ordinal: 1, origin: 'post_generation',
    status, state_sha256: 'b'.repeat(64), approved_version_count: 0, generation: {}, created_at: '', updated_at: '',
    template_id: 'project_landing', catalog: { section_order: [], font_families: ['Inter'] },
    configuration: {
      schema: 'ptw.landing.configuration.v1',
      theme: { background_color: '#ffffff', surface_color: '#eeeeee', text_color: '#111111', accent_color: '#ff0000', font_family: 'Inter', heading_font_family: 'Inter', corner_radius: 8 },
      hero: { alignment: 'left', image_position: 'right' }, features: { layout: 'three_columns' }, social_proof: { layout: 'cards' }, visual_break: { height: 'medium' }, contacts: { alignment: 'left' }, faq: { style: 'divided' },
    },
    content: {
      schema: 'ptw.landing.content.v1', hero: { title: 'A clear promise', supporting_text: 'Helpful details', cta_label: 'Start now', visual_direction: '' },
      features: [{ title: 'One', description: 'First' }, { title: 'Two', description: 'Second' }, { title: 'Three', description: 'Third' }],
      social_proof: { heading: 'Evidence', items: [] }, visual_break: { visual_direction: '' },
      contacts: { heading: 'Contact', supporting_text: '', email: '', phone: '', url: '' }, faq: [{ question: 'One?', answer: 'Yes.' }, { question: 'Two?', answer: 'Yes.' }, { question: 'Three?', answer: 'Yes.' }],
    }, assets: [], image_generation_available: true, versions: [],
  }
}

function landingApi(detail: LandingDetail) {
  return {
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/pages')) return { items: [detail] }
      if (path.endsWith('/source-posts')) return { items: [] }
      if (path.endsWith(`/pages/${landingId}`)) return detail
      throw new Error(`unexpected GET ${path}`)
    }), post: vi.fn(), image: vi.fn(),
  } as unknown as ApiClient
}

it('offers only immutable approved Post versions as Landing sources', async () => {
  const post = vi.fn(async (path: string) => {
    expect(path).toBe(`/api/v1/landings/projects/${projectId}/pages`)
    return { landing: { landing_id: '33333333-3333-4333-8333-333333333333' } }
  })
  const api = {
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/pages')) return { items: [] }
      if (path.endsWith('/source-posts')) return { items: [{
        creative_id: creativeId, version: 2, version_sha256: 'a'.repeat(64),
        template_id: 'universal_ad', source_brief_id: '44444444-4444-4444-8444-444444444444',
      }] }
      throw new Error(`unexpected GET ${path}`)
    }),
    post,
    image: vi.fn(),
  } as unknown as ApiClient
  const onLanding = vi.fn()

  render(<LandingView api={api} language="en" projectId={projectId} onLanding={onLanding} />)
  const source = await screen.findByRole('button', { name: /universal_ad.*v2/i })
  fireEvent.click(source)

  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/landings/projects/${projectId}/pages`,
    { source_creative_id: creativeId, source_version: 2 },
  ))
  expect(onLanding).toHaveBeenCalledWith('33333333-3333-4333-8333-333333333333')
})

it('opens a dismissible full-screen Landing view', async () => {
  const api = landingApi(landingDetail())
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)

  fireEvent.click(await screen.findByRole('button', { name: 'View Landing' }))
  expect(screen.getByRole('dialog', { name: 'Full-screen Landing preview' })).toBeInTheDocument()
  fireEvent.keyDown(window, { key: 'Escape' })
  expect(screen.queryByRole('dialog', { name: 'Full-screen Landing preview' })).not.toBeInTheDocument()
})

it('refreshes an in-progress Landing until it reaches a terminal state', async () => {
  vi.useFakeTimers()
  const api = landingApi(landingDetail('composing'))
  const view = render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
  expect(screen.getByText('Building the Landing')).toBeInTheDocument()

  await act(async () => { await vi.advanceTimersByTimeAsync(2_500) })
  expect(api.get).toHaveBeenCalledTimes(4)

  view.unmount()
  vi.useRealTimers()
})
