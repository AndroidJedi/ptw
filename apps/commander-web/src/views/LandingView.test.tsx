import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { LandingDetail, LandingPublication } from '../types'
import { LandingView } from './LandingView'
import { LandingPage } from '../landing/LandingPage'

vi.mock('../firebase', () => ({ appCheck: {} }))

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const landingId = '33333333-3333-4333-8333-333333333333'
beforeEach(() => sessionStorage.clear())
afterEach(() => vi.useRealTimers())
async function openPublication() {
  fireEvent.click(await screen.findByLabelText('More actions'))
  fireEvent.click(screen.getByRole('button', { name: 'Approve & publish' }))
}

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
  }), { deadlineMs: 480_000 }))
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
      if (path.endsWith('/landings/templates')) return { items: [] }
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
        template_id: 'phone_metrics', source_brief_id: '44444444-4444-4444-8444-444444444444',
      }] }
      throw new Error(`unexpected GET ${path}`)
    }),
    post,
    image: vi.fn(),
  } as unknown as ApiClient
  const onLanding = vi.fn()

  render(<LandingView api={api} language="en" projectId={projectId} onLanding={onLanding} />)
  const source = await screen.findByRole('button', { name: /phone_metrics.*v2/i })
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
  expect(vi.mocked(api.get).mock.calls.filter(([path]) => path.endsWith(`/pages/${landingId}`))).toHaveLength(2)

  view.unmount()
  vi.useRealTimers()
})

it('explains a persisted Landing generation failure returned over HTTP 200', async () => {
  const detail = landingDetail('failed')
  detail.generation = { error_type: 'RuntimeError', error_message: 'structured bridge request 438 failed' }
  const api = landingApi(detail)
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)

  const overlay = await screen.findByRole('dialog', { name: 'This request needs attention' })
  expect(overlay).toHaveTextContent('The Landing could not be generated.')
  expect(overlay).toHaveTextContent('Explanation: The ChatGPT/Codex service')
  expect(overlay).toHaveTextContent(`bridge job 438 · ID ${landingId}`)
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

it('shows a failed template catalog and reloads App Showcase without losing pending edits', async () => {
  const detail = landingDetail()
  const api = landingApi(detail)
  const originalGet = vi.mocked(api.get).getMockImplementation()!
  let unavailable = true
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith('/landings/templates')) {
      if (unavailable) throw new Error('Template list temporarily unavailable')
      return { items: [{ template_id: 'app_showcase', template_version: 2, template_sha256: 'c'.repeat(64), name: 'App Showcase' }] } as never
    }
    return originalGet(path)
  })
  render(<LandingView api={api as unknown as ApiClient} language="en" projectId={projectId} landingId={landingId} />)
  fireEvent.change(await screen.findByLabelText('Hero title'), { target: { value: 'Keep this draft' } })
  expect(screen.getByRole('alert')).toHaveTextContent('Template list temporarily unavailable')
  unavailable = false
  fireEvent.click(screen.getByRole('button', { name: 'Reload templates' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Change template' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Change template' }))
  expect(screen.getByRole('button', { name: 'App Showcase' })).toBeEnabled()
  expect(screen.getByLabelText('Hero title')).toHaveValue('Keep this draft')
  expect(api.post).not.toHaveBeenCalled()
})

it('reconciles an equivalent completed save after a stale-state response', async () => {
  const detail = landingDetail()
  const saved = {
    ...detail, state_sha256: 'd'.repeat(64),
    content: { ...detail.content, hero: { ...detail.content.hero, title: 'Saved despite an uncertain response' } },
  }
  const api = landingApi(detail)
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith('/landings/templates')) return { items: [] } as never
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
    if (path.endsWith('/landings/templates')) return { items: [] } as never
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

it('saves a lightweight edit checkpoint without invoking learning', async () => {
  const detail = landingDetail()
  const api = landingApi(detail)
  vi.mocked(api.post).mockResolvedValueOnce({ landing: detail, checkpoint: { checkpoint_id: 'checkpoint', status: 'saved' }, learning_proposal: null })
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save Landing' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Landing saved.')
  expect(api.post).toHaveBeenCalledTimes(1)
  expect(vi.mocked(api.post).mock.calls[0][0]).toMatch(/\/save$/)
  expect(screen.queryByText(/lesson|learning preference/i)).not.toBeInTheDocument()
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

  await openPublication()
  expect(await screen.findByText('https://natal-service.com/sample-project')).toBeVisible()
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
    expect.objectContaining({ landing_id: landingId, version: 1, slug: 'valid-slug' }),
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
    slug: 'stable-page', status: 'published', current_event_id: 'event-2',
    canonical_url: 'https://natal-service.com/stable-page', requested_by: 'owner',
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

  await openPublication()
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


it('shows three static app screens and targets the selected screen for generation', async () => {
  const detail = landingDetail()
  detail.template_id = 'app_showcase'
  detail.configuration.showcase = { gradient_end: '#08cbb5', screen_scale: 1, screen_offset: 32 }
  detail.content.app_screens = [1, 2, 3].map(i => ({ title: `Screen ${i}`, description: 'A project-specific task', visual_direction: `A polished app interface ${i}` }))
  const api = landingApi(detail)
  vi.mocked(api.post).mockImplementation(async (_path, body) => ({ operation_id: 'operation-screen', request_id: (body as { request: { request_id: string } }).request.request_id, status: 'completed', phase: 'completed', started_at: new Date().toISOString(), jobs: [{ slot: 'app_screen_2', status: 'completed' }], result: { configuration: detail.configuration, content: detail.content } }) as never)
  const view = render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} />)
  await screen.findByLabelText('Hero title')
  expect(view.container.querySelectorAll('.as-phone')).toHaveLength(5)
  expect(view.container.querySelector('.lp-phone-row')).toBeNull()
  fireEvent.change(screen.getByLabelText('Page section'), { target: { value: 'app_screen_2' } })
  fireEvent.change(screen.getByLabelText('Visual direction'), { target: { value: 'A new inventory screen with an Add photo action' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/operations'), { kind: 'image', request: expect.objectContaining({ slot: 'app_screen_2', visual_direction: 'A new inventory screen with an Add photo action' }) }, expect.anything()))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Updating your Landing' })).toBeNull())
})

it('passes the exact selected template reference when reserving a Landing', async () => {
  const reference = { template_id: 'app_showcase', template_version: 1, template_sha256: 'c'.repeat(64) }
  const api = {
    get: vi.fn(async (path: string) => path.endsWith('/templates') ? { items: [{ ...reference, name: 'App Showcase' }] } : path.endsWith('/source-posts') ? { items: [{ creative_id: creativeId, version: 1, version_sha256: 'a'.repeat(64), template_id: 'phone_metrics' }] } : { items: [] }),
    post: vi.fn(async () => ({ landing: { landing_id: landingId } })), image: vi.fn(),
  } as unknown as ApiClient
  render(<LandingView api={api} language="en" projectId={projectId} />)
  fireEvent.change(await screen.findByLabelText('Landing template'), { target: { value: 'app_showcase' } })
  fireEvent.click(screen.getByRole('button', { name: /phone_metrics/ }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/pages'), expect.objectContaining({ template_reference: reference })))
})

it('tries a selected template from an incomplete draft without Save or Approve and restores pending edits from history', async () => {
  const old = landingDetail()
  const reference = { template_id: 'app_showcase', template_version: 2, template_sha256: 'c'.repeat(64) }
  const next = { ...landingDetail(), landing_id: '55555555-5555-4555-8555-555555555555', ordinal: 2, template_reference: reference, template_id: 'app_showcase' as const }
  next.configuration.showcase = { gradient_end: '#08cbb5', screen_scale: 1, screen_offset: 32 }
  next.content.app_screens = [1, 2, 3].map(i => ({ title: `Screen ${i}`, description: 'A task', visual_direction: 'A readable app screen' }))
  let created = false
  const api = {
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/landings/templates')) return { items: [{ ...reference, name: 'App Showcase' }] }
      if (path.endsWith('/pages')) return { items: created ? [next, old] : [old] }
      if (path.endsWith(`/pages/${old.landing_id}`)) return old
      if (path.endsWith(`/pages/${next.landing_id}`)) return next
      return { items: [] }
    }),
    post: vi.fn(async () => { created = true; return { landing: next, created: true } }), image: vi.fn(),
  } as unknown as ApiClient
  const onLanding = vi.fn()
  const view = render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} onLanding={onLanding} />)
  fireEvent.change(await screen.findByLabelText('Hero title'), { target: { value: 'Keep this unfinished copy' } })
  fireEvent.click(screen.getByRole('button', { name: 'Change template' }))
  fireEvent.click(screen.getByRole('button', { name: 'App Showcase' }))
  fireEvent.click(screen.getByRole('button', { name: 'Apply template' }))
  await waitFor(() => expect(onLanding).toHaveBeenCalledWith(next.landing_id))
  expect(api.post).toHaveBeenCalledTimes(1)
  expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/\/pages\/variants$/), {
    request_id: expect.any(String), source_creative_id: creativeId, source_version: old.source_version, template_reference: reference,
  })
  view.rerender(<LandingView api={api} language="en" projectId={projectId} landingId={next.landing_id} onLanding={onLanding} />)
  await waitFor(() => expect(view.container.querySelector('.as-page')).not.toBeNull())
  expect(screen.getByRole('heading', { name: 'App Showcase', level: 1 })).toBeVisible()
  view.rerender(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} onLanding={onLanding} />)
  expect(await screen.findByLabelText('Hero title')).toHaveValue('Keep this unfinished copy')
  expect(api.post).toHaveBeenCalledTimes(1)
})

it('retries an uncertain template change from the blocking overlay with the identical request', async () => {
  const old = landingDetail()
  const reference = { template_id: 'app_showcase', template_version: 2, template_sha256: 'c'.repeat(64) }
  const api = landingApi(old)
  const originalGet = api.get
  api.get = vi.fn(async (path: string) => path.endsWith('/landings/templates') ? { items: [{ ...reference, name: 'App Showcase' }] } : path.startsWith('/api/v1/templates?') ? { items: [] } : originalGet(path)) as ApiClient['get']
  vi.mocked(api.post).mockRejectedValueOnce(new Error('Response lost')).mockResolvedValueOnce({ landing: { landing_id: 'new-page' } })
  const onLanding = vi.fn()
  render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} onLanding={onLanding} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Change template' }))
  fireEvent.click(screen.getByRole('button', { name: 'App Showcase' }))
  fireEvent.click(screen.getByRole('button', { name: 'Apply template' }))
  expect(await screen.findByRole('dialog', { name: 'This request needs attention' })).toHaveTextContent('Response lost')
  fireEvent.click(await screen.findByRole('button', { name: 'Retry unfinished work' }))
  await waitFor(() => expect(onLanding).toHaveBeenCalledWith('new-page'))
  expect(vi.mocked(api.post).mock.calls[1]).toEqual(vi.mocked(api.post).mock.calls[0])
})

it('does not navigate into an old project when a template response arrives after switching projects', async () => {
  const old = landingDetail()
  const otherProject = '66666666-6666-4666-8666-666666666666'
  const reference = { template_id: 'app_showcase', template_version: 2, template_sha256: 'c'.repeat(64) }
  let complete!: (value: unknown) => void
  const api = {
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/landings/templates')) return { items: [{ ...reference, name: 'App Showcase' }] }
      if (path.includes(otherProject)) return { items: [] }
      if (path.endsWith('/pages')) return { items: [old] }
      if (path.endsWith(`/pages/${landingId}`)) return old
      return { items: [] }
    }),
    post: vi.fn(() => new Promise(resolve => { complete = resolve })), image: vi.fn(),
  } as unknown as ApiClient
  const onLanding = vi.fn()
  const view = render(<LandingView api={api} language="en" projectId={projectId} landingId={landingId} onLanding={onLanding} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Change template' }))
  fireEvent.click(screen.getByRole('button', { name: 'App Showcase' }))
  fireEvent.click(screen.getByRole('button', { name: 'Apply template' }))
  view.rerender(<LandingView api={api} language="en" projectId={otherProject} onLanding={onLanding} />)
  await waitFor(() => expect(api.get).toHaveBeenCalledWith(`/api/v1/landings/projects/${otherProject}/pages`))
  await act(async () => complete({ landing: { landing_id: 'old-project-result' } }))
  expect(onLanding).not.toHaveBeenCalled()
})
