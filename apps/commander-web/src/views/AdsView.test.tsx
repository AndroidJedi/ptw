import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { MetaAdsDeployment, MetaAdsProjectWorkspace } from '../types'
import { AdsView } from './AdsView'

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const presetId = '33333333-3333-4333-8333-333333333333'

function fixture(verified = true): MetaAdsProjectWorkspace {
  return {
    schema: 'ptw.meta-ads.workspace.v1', project_id: projectId, project_name: 'Natal idea',
    connection: verified ? {
      configured: true, verified: true, graph_version: 'v26.0',
      account: { id: 'act_123', name: 'Local Ads', currency: 'USD', minimum_daily_budget_minor: 100 },
      page: { id: '456', name: 'Natal' }, instagram: { id: '789', username: 'natal' },
      pixel: { id: '101', name: 'Natal Website' },
    } : {
      configured: false, verified: false, graph_version: 'v26.0',
      explanation: 'Add the Meta system-user token and assigned asset IDs to the local secrets file.',
      required_permissions: ['ads_management', 'ads_read'],
    },
    presets: [{
      preset_id: presetId, version: 1, specification_sha256: 'b'.repeat(64), created_at: '',
      specification: {
        schema: 'ptw.meta-ads.preset.v1', name: 'Ukraine women', countries: ['UA'],
        age_min: 25, age_max: 44, gender: 'women', daily_budget_minor: 500,
        publisher_platforms: ['instagram'], instagram_positions: ['stream'], location_types: ['home'],
      },
    }],
    sources: [{
      creative_id: creativeId, creative_ordinal: 1, template_id: 'universal_ad', version: 2,
      version_sha256: 'a'.repeat(64), render_sha256: 'c'.repeat(64), change_note: 'Approved',
      defaults: { headline: 'Natal headline', primary_text: 'Guidance\n\nOffer', welcome_message: 'Вітаю! Хочу дізнатися більше.' },
    }],
    experiment: null, deployments: [], ads_manager_url: 'https://adsmanager.facebook.com/test',
  }
}

function deployment(status: MetaAdsDeployment['status'] = 'queued'): MetaAdsDeployment {
  return {
    deployment_id: '55555555-5555-4555-8555-555555555555',
    request_id: '44444444-4444-4444-8444-444444444444',
    project_id: projectId, source_creative_id: creativeId, source_version: 2,
    render_sha256: 'c'.repeat(64), status,
    specification: {
      headline: 'Natal headline', primary_text: 'Guidance\n\nOffer',
      special_ad_categories: ['NONE'], preset: fixture().presets[0].specification,
    },
    created_at: '', updated_at: '',
  }
}

function apiFor(workspace: MetaAdsProjectWorkspace) {
  const get = vi.fn(async (path: string): Promise<unknown> => {
    expect(path).toBe(`/api/v1/ads/projects/${projectId}`)
    return workspace
  })
  const post = vi.fn(async () => ({
    deployment: deployment(),
    created: true,
  }))
  const image = vi.fn(async () => new Blob(['png'], { type: 'image/png' }))
  return { api: { get, post, image } as unknown as ApiClient, get, post, image }
}

it('stages the selected approved artifact with deterministic defaults and a fresh request ID', async () => {
  const { api, post, image } = apiFor(fixture())
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:approved-post') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  Object.defineProperty(globalThis.crypto, 'randomUUID', { configurable: true, value: vi.fn(() => '44444444-4444-4444-8444-444444444444') })
  render(<AdsView api={api} language="uk" projectId={projectId} />)

  expect(await screen.findByText('Активи Meta перевірено')).toBeVisible()
  fireEvent.click(screen.getByText('Налаштування Meta'))
  expect(screen.getByText('Затверджено для Ads')).toBeVisible()
  expect(screen.getByRole('link', { name: /Відкрити в Post Studio/ })).toHaveAttribute(
    'href', `?page=posts&project=${projectId}&creative=${creativeId}`,
  )
  expect(screen.getByRole('link', { name: /Системні користувачі/ })).toHaveAttribute(
    'href', 'https://business.facebook.com/settings/system-users',
  )
  expect(screen.getByRole('link', { name: /Статуси Campaign, Ad Set/ })).toHaveAttribute(
    'href', 'https://adsmanager.facebook.com/test',
  )
  await waitFor(() => expect(screen.getByLabelText('Заголовок')).toHaveValue('Natal headline'))
  expect(screen.getByLabelText('Основний текст')).toHaveValue('Guidance\n\nOffer')
  await waitFor(() => expect(image).toHaveBeenCalledWith(
    `/api/v1/studio/projects/${projectId}/creatives/${creativeId}/versions/2/render`,
    'image/png', 'c'.repeat(64),
  ))
  fireEvent.click(screen.getByRole('button', { name: 'Створити повну PAUSED-рекламу в Meta' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/ads/projects/${projectId}/deployments`, {
    request_id: '44444444-4444-4444-8444-444444444444', creative_id: creativeId,
    version: 2, preset_id: presetId, headline: 'Natal headline',
    primary_text: 'Guidance\n\nOffer', welcome_message: 'Вітаю! Хочу дізнатися більше.',
    special_ad_categories: ['NONE'],
  }, { deadlineMs: 120_000 }))
})

it('disables staging and explains safe local configuration when Meta is missing', async () => {
  const disconnected = fixture(false)
  const { api } = apiFor(disconnected)
  render(<AdsView api={api} language="en" projectId={projectId} />)
  expect(await screen.findByText('Meta staging disabled')).toBeVisible()
  expect(screen.getByText(/Add the Meta system-user token/)).toBeVisible()
  expect(screen.getByText('Secure system-user token')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Create complete PAUSED ad in Meta' })).toBeDisabled()
})

it('links an empty Ads source list back to Post Studio and exposes the generic Ads Manager', async () => {
  const disconnected = fixture(false)
  disconnected.sources = []
  disconnected.ads_manager_url = null
  const { api } = apiFor(disconnected)
  render(<AdsView api={api} language="en" projectId={projectId} />)
  await screen.findByText('Meta staging disabled')
  expect(screen.getByRole('link', { name: 'Open Post Studio' })).toHaveAttribute(
    'href', `?page=posts&project=${projectId}`,
  )
  expect(screen.getByRole('link', { name: /Token debugger/ })).toHaveAttribute(
    'href', 'https://developers.facebook.com/tools/debug/accesstoken/',
  )
  expect(screen.getByRole('link', { name: /Campaign, Ad Set/ })).toHaveAttribute(
    'href', 'https://adsmanager.facebook.com/adsmanager/manage/campaigns',
  )
})

it('creates a versioned audience preset', async () => {
  const { api, post } = apiFor(fixture())
  render(<AdsView api={api} language="en" projectId={projectId} />)
  fireEvent.click(await screen.findByRole('button', { name: 'New preset' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Kyiv test' } })
  fireEvent.change(screen.getByLabelText('Countries (ISO, comma-separated)'), { target: { value: 'ua, pl' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save immutable version' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/ads/presets', {
    name: 'Kyiv test', countries: ['UA', 'PL'], age_min: 25, age_max: 55,
    gender: 'all', daily_budget_minor: 500,
  }))
})

it('normalizes leading-zero audience numbers and blocks an invalid preset before the API call', async () => {
  const { api, post } = apiFor(fixture())
  render(<AdsView api={api} language="en" projectId={projectId} />)
  fireEvent.click(await screen.findByRole('button', { name: 'New preset' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Leading zeros' } })
  fireEvent.change(screen.getByLabelText('Minimum age'), { target: { value: '020' } })
  fireEvent.change(screen.getByLabelText('Maximum age'), { target: { value: '035' } })
  fireEvent.change(screen.getByLabelText(/^Daily budget \(Meta minor units\)/), { target: { value: '0200' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save immutable version' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/ads/presets', expect.objectContaining({ age_min: 20, age_max: 35, daily_budget_minor: 200 })))

  post.mockClear()
  fireEvent.change(screen.getByLabelText('Maximum age'), { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save immutable version' }))
  expect(await screen.findByText('Maximum age must be an integer from the minimum age to 65.')).toBeVisible()
  expect(post).not.toHaveBeenCalled()
})

it('shows the live Meta budget minimum and prepares a compliant immutable preset', async () => {
  const workspace = fixture()
  workspace.connection.account!.minimum_daily_budget_minor = 4491
  workspace.deployments = [{
    ...deployment('failed'), meta_campaign_id: 'campaign-1',
    error: { error_message: 'Meta request failed.', provider_context: { subcode: '1885272' } },
  }]
  const { api, post } = apiFor(workspace)
  render(<AdsView api={api} language="en" projectId={projectId} />)

  expect(await screen.findByText(/This preset cannot be staged/)).toBeVisible()
  expect(screen.getAllByText('Creation stopped at Ad Set. Nothing was activated.')).toHaveLength(2)
  expect(screen.getByText(/Meta rejected the Ad Set because/)).toBeVisible()
  expect(screen.getAllByText(/below Meta's current minimum of \$44\.91 \(4491 minor units\)/)).toHaveLength(2)
  expect(screen.getByRole('button', { name: 'Create complete PAUSED ad in Meta' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Prepare a compliant preset version' }))
  expect(screen.getByLabelText(/^Daily budget \(Meta minor units\)/)).toHaveValue(4491)
  fireEvent.click(screen.getByRole('button', { name: 'Save immutable version' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/ads/presets', expect.objectContaining({
    daily_budget_minor: 4491,
  })))
})

it('serializes slow deployment polling and applies the completed response', async () => {
  vi.useFakeTimers()
  try {
    const running = fixture()
    running.deployments = [deployment('creating_ad_set')]
    const failed = fixture()
    failed.deployments = [{
      ...deployment('failed'),
      meta_campaign_id: 'campaign-1',
      error: { error_message: 'Meta rejected the Ad Set.', provider_context: { subcode: 'other' } },
    }]
    let finishPoll: (value: MetaAdsProjectWorkspace) => void = () => undefined
    const slowPoll = new Promise<MetaAdsProjectWorkspace>(resolve => { finishPoll = resolve })
    const { api, get } = apiFor(running)
    get.mockResolvedValueOnce(running).mockImplementation(() => slowPoll)

    render(<AdsView api={api} language="en" projectId={projectId} />)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getAllByText('Request accepted — creating Ad Set…')).toHaveLength(2)

    await act(async () => { await vi.advanceTimersByTimeAsync(2_500) })
    expect(get).toHaveBeenCalledTimes(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(get).toHaveBeenCalledTimes(2)

    await act(async () => { finishPoll(failed); await slowPoll; await Promise.resolve() })
    expect(screen.getAllByText('Creation stopped at Ad Set. Nothing was activated.')).toHaveLength(2)
    expect(screen.getAllByText('Meta rejected the Ad Set.')).toHaveLength(2)
    const progress = screen.getByRole('list', { name: 'Meta creation progress' })
    expect(within(progress).getAllByRole('listitem')).toHaveLength(5)
    expect(within(progress).getByText(/Created · PAUSED/)).toBeVisible()
    expect(within(progress).getByText('Stopped here')).toBeVisible()
  } finally {
    vi.useRealTimers()
  }
})

it('searches Meta and saves an immutable city-radius preset without country broadening', async () => {
  const workspace = fixture()
  const { api, get, post } = apiFor(workspace)
  get.mockImplementation(async (path: string) => {
    if (path === `/api/v1/ads/projects/${projectId}`) return workspace
    if (path === '/api/v1/ads/locations?query=Kyiv&country_code=UA') return { items: [{
      key: '2420605', name: 'Kyiv', type: 'city', country_code: 'UA',
      country_name: 'Ukraine', region: 'Kyiv',
    }] }
    throw new Error(`Unexpected path ${path}`)
  })

  render(<AdsView api={api} language="en" projectId={projectId} />)
  fireEvent.click(await screen.findByRole('button', { name: 'New preset' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Kyiv 25 km' } })
  fireEvent.change(screen.getByLabelText('Geography'), { target: { value: 'cities' } })
  fireEvent.click(screen.getByRole('button', { name: 'Search Meta' }))
  fireEvent.click(await screen.findByRole('button', { name: /Kyiv.*Add/ }))
  fireEvent.change(screen.getByLabelText('Radius, km'), { target: { value: '25' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save immutable version' }))

  await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/ads/presets', {
    name: 'Kyiv 25 km', countries: [], cities: [{
      key: '2420605', name: 'Kyiv', country_code: 'UA', radius_km: 25,
    }],
    age_min: 25, age_max: 55, gender: 'all', daily_budget_minor: 500,
  }))
})

it('creates a website ad using the published landing and omits Direct copy', async () => {
  sessionStorage.clear()
  const value = fixture()
  value.landing = { publication_id: 'landing', event_id: 'event', landing_version: 1, landing_version_sha256: 'd'.repeat(64), canonical_url: 'https://natal-service.com/la/example' }
  const { api, post } = apiFor(value)
  render(<AdsView api={api} language="en" projectId={projectId} />)
  await screen.findByText('Meta assets verified')
  fireEvent.change(screen.getByLabelText('Destination'), { target: { value: 'WEBSITE' } })
  expect(screen.getByText('LANDING_PAGE_VIEWS')).toBeVisible()
  expect(screen.getAllByText('Natal Website')).toHaveLength(2)
  expect(screen.queryByLabelText('Initial Direct message')).not.toBeInTheDocument()
  const requestReview = screen.getByRole('group', { name: 'Details PTW will send to Meta' })
  expect(within(requestReview).getByText(/approved PNG/)).toBeVisible()
  expect(within(requestReview).getByRole('link', { name: value.landing.canonical_url })).toHaveAttribute('href', value.landing.canonical_url)
  expect(screen.getAllByRole('link', { name: value.landing.canonical_url })[0]).toHaveAttribute('href', value.landing.canonical_url)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Create complete PAUSED ad in Meta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Create complete PAUSED ad in Meta' }))
  await waitFor(() => expect(post).toHaveBeenCalled())
  expect((post.mock.calls as unknown[][])[0]?.[1]).toEqual(expect.objectContaining({ destination_type: 'WEBSITE', landing_event_id: 'event', version: 2 }))
  expect((post.mock.calls as unknown[][])[0]?.[1]).not.toHaveProperty('welcome_message')
})

it('blocks website staging without a published landing while keeping export available', async () => {
  const { api, post } = apiFor(fixture(false))
  render(<AdsView api={api} language="en" projectId={projectId} />)
  await screen.findByText('Meta staging disabled')
  fireEvent.change(screen.getByLabelText('Destination'), { target: { value: 'WEBSITE' } })
  expect(screen.getByRole('button', { name: 'Create complete PAUSED ad in Meta' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Download image' })).toBeEnabled()
  expect(post).not.toHaveBeenCalled()
})
