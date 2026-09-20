import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { AdsView } from './AdsView'

const projectId = '11111111-1111-4111-8111-111111111111'
const testId = '22222222-2222-4222-8222-222222222222'
const sources = [1, 2].map(ordinal => ({
  creative_id: `${ordinal}1111111-1111-4111-8111-111111111111`, creative_ordinal: ordinal,
  template_id: 'phone_metrics', version: 1, version_id: `${ordinal}2222222-2222-4222-8222-222222222222`,
  version_sha256: String(ordinal).repeat(64), render_sha256: String(ordinal + 2).repeat(64),
  change_note: `Approved ${ordinal}`, defaults: {
    headline: `Idea ${ordinal}`, primary_text: 'Support\n\nOffer',
    instagram_caption: `Idea ${ordinal}\n\nSupport\n\nOffer`, welcome_message: '',
  },
}))

function workspace(withTest = false) {
  return {
    schema: 'ptw.instagram-validation.workspace.v1', project_id: projectId, project_name: 'Idea',
    sources, landing: {
      publication_id: '33333333-3333-4333-8333-333333333333',
      event_id: '44444444-4444-4444-8444-444444444444', landing_version: 1,
      landing_version_sha256: 'a'.repeat(64), canonical_url: 'https://natal-service.com/ai/idea',
    },
    ads_manager_url: 'https://adsmanager.facebook.com/adsmanager/manage/campaigns',
    tests: withTest ? [{
      test_id: testId, name: 'Two Posts', state: 'active', total_budget_minor: 5000,
      daily_budget_minor: 1000, currency: 'USD', duration_days: 5,
      campaign_name: 'PTW-test', ad_set_name: 'PTW-test-ADSET', current_leader_arm_id: null,
      imports: [], arms: sources.map((source, index) => ({
        arm_id: `${index + 5}1111111-1111-4111-8111-111111111111`, ordinal: index + 1,
        source_creative_id: source.creative_id, source_version: 1,
        ad_name: `PTW-test-AD-0${index + 1}`, headline: source.defaults.headline,
        primary_text: `${source.defaults.instagram_caption}\n\nhttps://natal-service.com/ai/idea?ptw_attribution=token${index}`,
        tracked_url: `https://natal-service.com/ai/idea?ptw_attribution=token${index}`,
        paid: {}, funnel: { landing_view: index + 2, primary_cta_click: index, contact_click: 0 },
        cost_per_primary_cta_minor: null,
      })),
    }] : [],
  }
}

function setup(withTest = false) {
  const value = workspace(withTest)
  const get = vi.fn(async (path: string) => {
    expect(path).toBe(`/api/v1/instagram-tests/projects/${projectId}`)
    return value
  })
  const post = vi.fn(async (path: string) => {
    if (path.endsWith('/imports/preview')) return {
      csv_sha256: 'b'.repeat(64), headers: ['Ad name', 'Amount spent (USD)'],
      mapping: { ad_name: 'Ad name', spend: 'Amount spent (USD)', impressions: null, link_clicks: null, landing_page_views: null },
      matched_rows: [{ row: 2, ad_name: 'PTW-test-AD-01', matched_arm_id: value.tests[0].arms[0].arm_id }],
      ignored_rows: [], can_import: true,
    }
    return { created: true, test: value.tests[0] }
  })
  const download = vi.fn(async () => new Blob(['zip'], { type: 'application/zip' }))
  const api = { get, post, download } as unknown as ApiClient
  render(<AdsView api={api} language="en" projectId={projectId} />)
  return { get, post, download }
}

beforeEach(() => {
  Object.defineProperty(globalThis.crypto, 'randomUUID', {
    configurable: true, value: vi.fn(() => '99999999-9999-4999-8999-999999999999'),
  })
})

it('prepares two approved Posts to compete inside one manual Instagram campaign', async () => {
  const { post } = setup()
  expect(await screen.findByRole('heading', { name: 'Instagram tests' })).toBeVisible()
  expect(screen.getByText(/Do not use “Boost post”/)).toBeVisible()
  expect(screen.getByText('Instagram Feed only')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /Post 1 · v1/ }))
  fireEvent.click(screen.getByRole('button', { name: /Post 2 · v1/ }))
  fireEvent.change(screen.getByLabelText('Test name'), { target: { value: 'Fast validation' } })
  fireEvent.click(screen.getByRole('button', { name: 'Prepare launch kit' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/instagram-tests/projects/${projectId}/tests`, {
      request_id: '99999999-9999-4999-8999-999999999999', name: 'Fast validation',
      total_budget_minor: 5000, currency: 'USD', duration_days: 5,
      arms: sources.map(source => ({ creative_id: source.creative_id, version: 1 })),
    }, { deadlineMs: 120_000 },
  ))
})

it('previews CSV mapping and completes only after explicit Meta stop confirmation', async () => {
  const { post } = setup(true)
  expect(await screen.findByText('ACTIVE · PTW-test')).toBeVisible()
  const csv = { text: vi.fn(async () => 'Ad name,Amount spent (USD)\nPTW-test-AD-01,10') }
  fireEvent.change(screen.getByLabelText('Meta Ads Manager CSV'), { target: { files: [csv] } })
  expect(await screen.findByText('Matched: 1 · Ignored: 0')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Import results' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/instagram-tests/projects/${projectId}/tests/${testId}/imports`,
    expect.objectContaining({ accept_ignored_rows: true }),
  ))

  vi.spyOn(window, 'confirm').mockReturnValue(true)
  fireEvent.click(screen.getByRole('button', { name: 'Stopped in Meta · complete' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/instagram-tests/projects/${projectId}/tests/${testId}/completed`, {
      request_id: '99999999-9999-4999-8999-999999999999', campaign_stopped: true,
    },
  ))
})
