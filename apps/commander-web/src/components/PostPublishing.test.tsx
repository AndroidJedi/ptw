import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { InstagramPublication, InstagramWorkspace, TikTokWorkspace } from '../types'
import { PostPublishing } from './PostPublishing'

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const versions = [1, 2].map(version => ({ version, change_note: `Approved ${version}`, render_sha256: String(version).repeat(64) }))
const workspace = (ready: boolean, publications: InstagramPublication[] = []): InstagramWorkspace => ({
  connection: { configured: ready, verified: ready, media_ready: ready, graph_version: 'v26.0', instagram: ready ? { id: '789', username: 'example' } : undefined },
  sources: versions.map(item => ({ ...item, creative_id: creativeId, creative_ordinal: 1, template_id: 'phone_metrics', version_sha256: 'a'.repeat(64), defaults: { headline: `Title ${item.version}`, primary_text: 'Approved copy', welcome_message: '' } })),
  publications, landing: { publication_id: 'landing', event_id: 'event', landing_version: 1, landing_version_sha256: 'b'.repeat(64), canonical_url: 'https://natal-service.com/la/example' },
})
function setup(ready = true, publications: InstagramPublication[] = []) {
  const get = vi.fn(async (path: string) => path.endsWith('/publications') ? { items: publications } : workspace(ready, publications))
  const post = vi.fn(async () => ({ publication: { publication_id: 'publication' }, created: true }))
  const image = vi.fn(async () => new Blob(['approved png'], { type: 'image/png' }))
  render(<PostPublishing api={{ get, post, image } as unknown as ApiClient} language="en" projectId={projectId} creativeId={creativeId} versions={versions} />)
  return { get, post, image }
}
beforeEach(() => {
  sessionStorage.clear()
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:approved') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn(async () => {}) } })
})
it('selects exact approved version for preview, publication, and ad handoff', async () => {
  const { post, image } = setup()
  fireEvent.change(screen.getByLabelText('Approved version'), { target: { value: '1' } })
  expect(screen.getByRole('link', { name: 'Create Instagram ad' }).getAttribute('href')).toContain('ad_version=1&destination=WEBSITE')
  fireEvent.click(screen.getByRole('button', { name: 'Publish to Instagram' }))
  await waitFor(() => expect(screen.getByLabelText('Instagram caption')).toHaveValue('Title 1\n\nApproved copy'))
  expect(image).toHaveBeenCalledWith(expect.stringContaining('/versions/1/render'), 'image/png', '1'.repeat(64))
  fireEvent.change(screen.getByLabelText('Instagram caption'), { target: { value: 'Reviewed caption' } })
  fireEvent.click(screen.getByRole('button', { name: 'Publish now' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/instagram/projects/${projectId}/publications`, expect.objectContaining({ source: { creative_id: creativeId, version: 1 }, content: { title: '', description: 'Reviewed caption' } }), { deadlineMs: 120_000 }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Publish now' })).toBeDisabled())
})
it('keeps export and landing-copy available without publishing credentials', async () => {
  const { post } = setup(false)
  fireEvent.click(screen.getByRole('button', { name: 'Publish to Instagram' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Download image' })).toBeEnabled())
  expect(screen.getByRole('button', { name: 'Publish now' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Copy landing URL' }))
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://natal-service.com/la/example')
  expect(post).not.toHaveBeenCalled()
})
it('shows the publication-specific tracked Landing URL without changing the caption', async () => {
  const trackedUrl = 'https://natal-service.com/la/example?ptw_attribution=opaque-token'
  const publication: InstagramPublication = {
    publication_id: '33333333-3333-4333-8333-333333333333', project_id: projectId,
    request_id: '44444444-4444-4444-8444-444444444444', publish_started: true,
    specification: { creative_id: creativeId, version: 2, caption: 'Original caption', render_sha256: '2'.repeat(64), delivery_sha256: 'd'.repeat(64), instagram_actor_id: '789' },
    status: 'published', phase: 'published', source: { creative_id: creativeId, version: 2 },
    analytics: { readiness: { provider: 'instagram', available: true }, freshness: null, capture_kind: null, attribution_token: 'opaque-token', attribution_source_id: '55555555-5555-4555-8555-555555555555', tracked_url: trackedUrl },
    created_at: '2026-09-13T10:00:00Z',
  }
  setup(true, [publication])
  fireEvent.click(screen.getByRole('button', { name: 'Publish to Instagram' }))
  expect(await screen.findByText('Tracked Landing URL · caption unchanged')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: trackedUrl })).toHaveAttribute('href', trackedUrl)
  fireEvent.click(screen.getByRole('button', { name: 'Copy tracked URL' }))
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(trackedUrl)
})
it('reuses the request ID after an uncertain HTTP response', async () => {
  const { post } = setup()
  post.mockRejectedValueOnce(new Error('Response lost'))
  fireEvent.click(screen.getByRole('button', { name: 'Publish to Instagram' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Publish now' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Publish now' }))
  await screen.findByText('Error: Response lost')
  fireEvent.click(screen.getByRole('button', { name: 'Publish now' }))
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
  expect(post.mock.calls[0]).toEqual(post.mock.calls[1])
})
it('uses the shared shell with explicit TikTok review and consent', async () => {
  const tiktok: TikTokWorkspace = {
    provider: 'tiktok', sources: workspace(true).sources, publications: [], landing: null,
    connection: { provider: 'tiktok', configured: true, verified: true, media_ready: true, direct_post_audited: true, expected_username: 'natal_cast', account: { open_id: 'open-1', username: 'natal_cast' }, creator: { open_id: 'open-1', username: 'natal_cast', privacy_level_options: ['PUBLIC_TO_EVERYONE', 'SELF_ONLY'], comment_disabled: false }, creator_snapshot_sha256: 'c'.repeat(64) },
  }
  const get = vi.fn(async (path: string) => path.endsWith('/publications') ? { items: [] } : path === '/api/v1/tiktok/connection' ? tiktok.connection : path.includes('/tiktok/') ? tiktok : workspace(true))
  const post = vi.fn(async () => ({ publication: { publication_id: 'publication' }, created: true }))
  const image = vi.fn(async () => new Blob(['approved png'], { type: 'image/png' }))
  render(<PostPublishing api={{ get, post, image } as unknown as ApiClient} language="en" projectId={projectId} creativeId={creativeId} versions={versions} />)
  fireEvent.click(screen.getByRole('button', { name: 'Publish to TikTok' }))
  await waitFor(() => expect(screen.getByText('@natal_cast')).toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Privacy (choose manually)'), { target: { value: 'PUBLIC_TO_EVERYONE' } })
  fireEvent.change(screen.getByLabelText('Commercial-content disclosure (choose manually)'), { target: { value: 'own' } })
  fireEvent.click(screen.getByLabelText("By posting, you agree to TikTok's Music Usage Confirmation."))
  const publish = screen.getByRole('button', { name: 'Publish now' })
  await waitFor(() => expect(publish).toBeEnabled())
  fireEvent.click(publish)
  await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/tiktok/projects/${projectId}/publications`, expect.objectContaining({ source: { creative_id: creativeId, version: 2 }, creator_snapshot_sha256: 'c'.repeat(64), settings: expect.objectContaining({ privacy_level: 'PUBLIC_TO_EVERYONE' }) }), { deadlineMs: 120_000 }))
})
