import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { InstagramWorkspace } from '../types'
import { PostPublishing } from './PostPublishing'

const projectId = '11111111-1111-4111-8111-111111111111'
const creativeId = '22222222-2222-4222-8222-222222222222'
const versions = [1, 2].map(version => ({ version, change_note: `Approved ${version}`, render_sha256: String(version).repeat(64) }))
const workspace = (ready: boolean): InstagramWorkspace => ({
  connection: { configured: ready, verified: ready, media_ready: ready, graph_version: 'v26.0', instagram: ready ? { id: '789', username: 'example' } : undefined },
  sources: versions.map(item => ({ ...item, creative_id: creativeId, creative_ordinal: 1, template_id: 'phone_metrics', version_sha256: 'a'.repeat(64), defaults: { headline: `Title ${item.version}`, primary_text: 'Approved copy', welcome_message: '' } })),
  publications: [], landing: { publication_id: 'landing', event_id: 'event', landing_version: 1, landing_version_sha256: 'b'.repeat(64), canonical_url: 'https://natal-service.com/la/example' },
})
function setup(ready = true) {
  const get = vi.fn(async (path: string) => path.endsWith('/publications') ? { items: [] } : workspace(ready))
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
  await waitFor(() => expect(post).toHaveBeenCalledWith(`/api/v1/instagram/projects/${projectId}/publications`, expect.objectContaining({ creative_id: creativeId, version: 1, caption: 'Reviewed caption' }), { deadlineMs: 120_000 }))
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
