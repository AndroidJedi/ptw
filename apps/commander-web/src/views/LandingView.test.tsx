import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { LandingDetail, LandingPublication } from '../types'
import { LandingView } from './LandingView'
import { LandingPage } from '../landing/LandingPage'

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const landingId = '33333333-3333-4333-8333-333333333333'

it('renders the hero image without phone controls in both editor and public image mode', () => {
  const detail = landingDetail()
  for (const editing of [true, false]) {
    const props = { configuration: { ...detail.configuration, visual_mode: 'image' as const }, content: detail.content, imageUrls: { hero_visual: '/hero.png' }, editing }
    const view = render(<LandingPage {...props} />)
    expect(view.container.querySelector('.lp-phone')).toBeNull()
    expect(view.container.querySelector('.lp-hero-art > img')).toHaveAttribute('src', '/hero.png')
    view.rerender(<LandingPage {...props} configuration={{ ...detail.configuration, visual_mode: 'phone' }} />)
    expect(view.container.querySelector('.lp-phone')).not.toBeNull()
    view.unmount()
  }
})

it('saves the selected Landing visual mode together with the existing screen settings', async () => {
  const detail = landingDetail()
  const api = landingApi(detail)
  vi.mocked(api.post).mockImplementation(async (_path, body) => ({ landing: { ...detail, ...(body as object) }, checkpoint: null }) as never)
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  fireEvent.change(await screen.findByRole('combobox', { name: 'Visual mode' }), { target: { value: 'image' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save Landing' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/save'), expect.objectContaining({
    configuration: { ...detail.configuration, visual_mode: 'image' }, content: detail.content,
  })))
})

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
  fireEvent(screen.getByRole('dialog', { name: 'Full-screen Landing preview' }), new Event('cancel', { bubbles: false, cancelable: true }))
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

it('explains a persisted Landing generation failure returned over HTTP 200', async () => {
  const detail = landingDetail('failed')
  detail.generation = { error_type: 'RuntimeError', error_message: 'structured bridge request 438 failed' }
  const api = landingApi(detail)
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)

  expect(await screen.findByText('The Landing could not be generated.')).toBeVisible()
  expect(screen.getByText(/Explanation: The ChatGPT\/Codex service/)).toBeVisible()
  expect(screen.getByText(/What to do: In Settings/)).toBeVisible()
  expect(screen.getByText(new RegExp(`bridge job 438 · ID ${landingId}`))).toBeVisible()
  expect(screen.queryByText('structured bridge request 438 failed')).not.toBeInTheDocument()
})

it('keeps pending copy when Save fails and displays an inline error', async () => {
  const detail = landingDetail()
  const api = landingApi(detail)
  vi.mocked(api.post).mockRejectedValue(new Error('Save unavailable'))
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  const input = await screen.findByLabelText('Hero title')
  fireEvent.change(input, { target: { value: 'My unsaved headline' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save Landing' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Save unavailable')
  expect(screen.getByLabelText('Hero title')).toHaveValue('My unsaved headline')
})

it('waits for bounded Landing learning and reconciles an equivalent completed save after a stale-state response', async () => {
  const detail = landingDetail()
  const saved = {
    ...detail, state_sha256: 'd'.repeat(64),
    content: { ...detail.content, hero: { ...detail.content.hero, title: 'Saved despite an uncertain response' } },
  }
  const api = landingApi(detail)
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith('/pages')) return { items: [detail] } as never
    if (path.endsWith('/source-posts')) return { items: [] } as never
    if (path.endsWith(`/pages/${landingId}`)) return saved as never
    throw new Error(`unexpected GET ${path}`)
  })
  vi.mocked(api.post).mockRejectedValue(Object.assign(new Error('The server data has already changed'), {
    details: { status: 409, detail: 'Landing changed; reload before saving' },
  }))
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  const input = await screen.findByLabelText('Hero title')
  fireEvent.change(input, { target: { value: saved.content.hero.title } })
  fireEvent.click(screen.getByRole('button', { name: 'Save Landing' }))

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    expect.stringContaining('/save'), expect.any(Object), { deadlineMs: 480_000 },
  ))
  expect(await screen.findByRole('status')).toHaveTextContent('Landing was already saved')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(input).toHaveValue(saved.content.hero.title)
})

it('keeps owner input and the original conflict when the latest Landing differs', async () => {
  const detail = landingDetail()
  const api = landingApi(detail)
  const conflict = Object.assign(new Error('The server data has already changed'), {
    details: { status: 409, detail: 'Landing changed; reload before saving' },
  })
  vi.mocked(api.post).mockRejectedValue(conflict)
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith('/pages')) return { items: [detail] } as never
    if (path.endsWith('/source-posts')) return { items: [] } as never
    if (path.endsWith(`/pages/${landingId}`)) return {
      ...detail, state_sha256: 'd'.repeat(64),
      content: { ...detail.content, contacts: { ...detail.content.contacts, email: 'newer@example.test' } },
    } as never
    throw new Error(`unexpected GET ${path}`)
  })
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  const input = await screen.findByLabelText('Hero title')
  fireEvent.change(input, { target: { value: 'Keep this pending headline' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save Landing' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('The server data has already changed')
  expect(input).toHaveValue('Keep this pending headline')
})

it('persists pending content before selecting another raw image', async () => {
  const detail = landingDetail()
  const sha = 'c'.repeat(64)
  detail.assets = [{ slot: 'hero_visual', available: true, sha256: 'a'.repeat(64), history: [
    { sha256: 'a'.repeat(64), selected: true, mime_type: 'image/png', width: 100, height: 100, visual_direction: '' },
    { sha256: sha, selected: false, mime_type: 'image/png', width: 100, height: 100, visual_direction: '' },
  ] }]
  const api = landingApi(detail)
  vi.mocked(api.image).mockRejectedValue(new Error('Test image unavailable'))
  vi.mocked(api.post).mockImplementation(async (path, body) => {
    if (path.endsWith('/configuration')) return { ...detail, state_sha256: 'd'.repeat(64), content: (body as { content: LandingDetail['content'] }).content } as never
    if (path.endsWith('/select')) return { ...detail, state_sha256: 'e'.repeat(64), content: { ...detail.content, hero: { ...detail.content.hero, title: 'Preserved copy' } } } as never
    throw new Error('Unexpected request')
  })
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  fireEvent.change(await screen.findByLabelText('Hero title'), { target: { value: 'Preserved copy' } })
  fireEvent.click(screen.getByRole('button', { name: 'Select image 2' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2))
  expect(vi.mocked(api.post).mock.calls[0][0]).toMatch(/configuration$/)
  expect(vi.mocked(api.post).mock.calls[1][1]).toEqual({ base_sha256: 'd'.repeat(64), sha256: sha })
  expect(screen.getByLabelText('Hero title')).toHaveValue('Preserved copy')
})

it('shows the saved Project lesson and submits the bounded global decision', async () => {
  const detail = landingDetail()
  const api = landingApi(detail)
  vi.mocked(api.post).mockResolvedValueOnce({ landing: detail, checkpoint: { checkpoint_id: 'checkpoint', status: 'completed', edit_summary: 'Shortened the headline.', project_lesson: 'Keep this page concise.' }, learning_proposal: { proposal_id: 'proposal', global_rule: 'Prefer a concise action label.', status: 'pending' } })
  vi.mocked(api.post).mockResolvedValueOnce({ status: 'keep_project' })
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save Landing' }))
  expect(await screen.findByText('Keep this page concise.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Keep project-only' }))
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith(`/api/v1/landings/projects/${projectId}/pages/${landingId}/learning/proposal`, { decision: 'keep_project' }))
  expect(screen.getByRole('status')).toHaveTextContent('Learning preference saved')
})

it('validates and confirms the complete permanent URL before first Publish', async () => {
  const detail = landingDetail()
  detail.approved_version_count = 1
  detail.versions = [{ version: 1, state_sha256: 'b'.repeat(64), version_sha256: 'c'.repeat(64), change_note: 'Approved' }]
  const post = vi.fn(async () => ({ created: true }))
  const api = {
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/pages')) return { items: [detail] }
      if (path.endsWith('/source-posts')) return { items: [] }
      if (path.endsWith('/publication')) return { publication: null }
      if (path.includes('/publication/availability?')) return { available: true }
      if (path.endsWith(`/pages/${landingId}`)) return detail
      throw new Error(`unexpected GET ${path}`)
    }), post, image: vi.fn(),
  } as unknown as ApiClient
  render(<LandingView api={api} language="en" projectId={projectId} projectName="Sample Project" landingId={landingId} />)

  expect(await screen.findByText('https://natal-service.com/ai/sample-project')).toBeVisible()
  const publish = screen.getByRole('button', { name: 'Publish approved version' })
  expect(publish).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Latin slug'), { target: { value: 'Bad Slug' } })
  fireEvent.click(screen.getByRole('checkbox'))
  expect(publish).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Latin slug'), { target: { value: 'valid-slug' } })
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(publish)

  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/landings/projects/${projectId}/publication/publish`,
    expect.objectContaining({ landing_id: landingId, version: 1, namespace: 'ai', slug: 'valid-slug' }),
  ))
})

it('republishes old approved events and unpublishes without releasing the URL', async () => {
  const detail = landingDetail()
  detail.approved_version_count = 2
  detail.versions = [
    { version: 1, state_sha256: 'b'.repeat(64), version_sha256: 'c'.repeat(64), change_note: 'First' },
    { version: 2, state_sha256: 'd'.repeat(64), version_sha256: 'e'.repeat(64), change_note: 'Second' },
  ]
  const publication: LandingPublication = {
    schema: 'ptw.landing.publication.v1', publication_id: 'publication', project_id: projectId,
    namespace: 'wa', slug: 'stable-page', status: 'published', current_event_id: 'event-2',
    canonical_url: 'https://natal-service.com/wa/stable-page', requested_by: 'owner',
    created_at: '2026-09-08T00:00:00Z', updated_at: '2026-09-08T00:00:00Z',
    events: [{
      event_id: 'event-2', publication_id: 'publication', request_id: 'request-2', sequence: 2,
      action: 'publish', landing_id: landingId, landing_version_id: 'version-2', landing_version: 2,
      landing_version_sha256: 'e'.repeat(64), requested_by: 'owner', created_at: '2026-09-08T00:00:00Z',
    }, {
      event_id: 'event-1', publication_id: 'publication', request_id: 'request-1', sequence: 1,
      action: 'publish', landing_id: landingId, landing_version_id: 'version-1', landing_version: 1,
      landing_version_sha256: 'c'.repeat(64), requested_by: 'owner', created_at: '2026-09-07T00:00:00Z',
    }],
  }
  const post = vi.fn(async () => ({ created: true }))
  const api = {
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/pages')) return { items: [detail] }
      if (path.endsWith('/source-posts')) return { items: [] }
      if (path.endsWith('/publication')) return { publication }
      if (path.endsWith(`/pages/${landingId}`)) return detail
      throw new Error(`unexpected GET ${path}`)
    }), post, image: vi.fn(),
  } as unknown as ApiClient
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)

  expect(await screen.findByRole('link', { name: /stable-page/ })).toHaveAttribute('href', publication.canonical_url)
  const restore = screen.getAllByRole('button', { name: 'Restore' })
  expect(restore).toHaveLength(2)
  expect(restore[0]).toBeDisabled()
  fireEvent.click(restore[1])
  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/landings/projects/${projectId}/publication/publish`,
    expect.objectContaining({ landing_id: landingId, version: 1 }),
  ))
  fireEvent.click(screen.getByRole('button', { name: 'Unpublish' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/landings/projects/${projectId}/publication/unpublish`,
    expect.objectContaining({ request_id: expect.any(String) }),
  ))
})
