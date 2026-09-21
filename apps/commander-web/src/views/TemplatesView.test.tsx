import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { TemplatesView } from './TemplatesView'
vi.mock('../firebase', () => ({ appCheck: {} }))

const preview = { sha256: 'a'.repeat(64), definition_sha256: 'b'.repeat(64) }
const item = { surface: 'post', template_id: 'phone_metrics', template_version: 27, template_sha256: 'b'.repeat(64), name: 'Phone & metrics', description: 'Reusable phone', builtin: true, status: 'registered', preview_status: 'ready', previews: { desktop: preview } }
const proposed = { run_id: '018f07ea-7f20-7000-8000-000000000010', scope: 'combined', status: 'proposed', state_sha256: 'c'.repeat(64), phase: 'compare', iterations: 2, error: null, previews: { 'post:desktop': preview }, comparison: { differences: [] }, capability_gap: null, invocations: [{ phase: 'compare', contract_bytes: { total: 10000 }, response_bytes: 500, attempt_count: 1 }], accepted_versions: [] }
const failedDraft = { ...proposed, run_id: '018f07ea-7f20-7000-8000-000000000011', scope: 'post', status: 'failed', iterations: 1, error: 'Template Agent timed out', failure: { phase: 'compare', category: 'timeout', model: 'codex-cli-default', reasoning_effort: 'xhigh', attempt_count: 1, validation_error: '' } }
function client() { return { get: vi.fn(async (path: string): Promise<unknown> => path.endsWith('/runs') ? { items: [] } : path.includes('/versions/') ? item : { items: [item] }), image: vi.fn(async () => new Blob(['png'], { type: 'image/png' })), post: vi.fn(async (_path: string, _body: unknown, _options?: unknown) => proposed) } }
beforeEach(() => { window.history.replaceState(null, '', '/?page=templates'); vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() })) })
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

it('loads authenticated gallery previews, filters surfaces, and opens immutable details', async () => {
  const api = client(); render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  expect(await screen.findByText('Phone & metrics')).toBeVisible()
  await waitFor(() => expect(api.image).toHaveBeenCalledWith('/api/v1/templates/media/' + preview.sha256, 'image/png', preview.sha256))
  fireEvent.click(screen.getByRole('button', { name: /^Landing$/ }))
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/v1/templates?surface=landing', expect.anything()))
  fireEvent.click(await screen.findByRole('button', { name: 'Open template' }))
  expect(await screen.findByText('Built-in · edits create a derivative')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Edit template' }))
  expect(screen.getByLabelText('Creation scope')).toBeDisabled()
})

it('supports coordinated creation, owner acceptance, and measured comparison results', async () => {
  const api = client(); render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  fireEvent.click(screen.getByRole('button', { name: 'Create Template Agent' }))
  fireEvent.change(screen.getByLabelText('Creation scope'), { target: { value: 'combined' } })
  fireEvent.change(screen.getByLabelText('Design instruction'), { target: { value: 'A title and larger photo' } })
  fireEvent.click(screen.getByRole('button', { name: 'Start creation' }))
  expect(await screen.findByText('No unresolved visual differences reported.')).toBeVisible()
  expect(api.post.mock.calls[0][0]).toBe('/api/v1/templates/runs')
  expect(api.post.mock.calls[0][1]).toMatchObject({ scope: 'combined', instruction: 'A title and larger photo' })
  expect(screen.getByRole('button', { name: 'Accept template version' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Accept template version' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/decision'), expect.objectContaining({ decision: 'accept', base_sha256: proposed.state_sha256 }), expect.anything()))
})

it('retains the exact mutation request UUID after uncertain transport failure', async () => {
  const api = client(); api.post.mockRejectedValueOnce(new Error('Connection lost'))
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  fireEvent.click(screen.getByRole('button', { name: 'Create Template Agent' }))
  fireEvent.change(screen.getByLabelText('Design instruction'), { target: { value: 'Simple template' } })
  fireEvent.click(screen.getByRole('button', { name: 'Start creation' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Retry same request' }))
  await screen.findByText('No unresolved visual differences reported.')
  expect(api.post.mock.calls[0]).toEqual(api.post.mock.calls[1])
})

it('restores interrupted run from URL and keeps acceptance disabled until convergence', async () => {
  window.history.replaceState(null, '', '/?page=templates&template_run=' + proposed.run_id)
  const api = client(); api.get.mockImplementation(async path => path.includes('/runs/') ? { ...proposed, status: 'interrupted', error: 'Worker stopped' } : { items: [] })
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  expect(await screen.findByText('Worker stopped')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Accept template version' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Resume / apply correction' })).toBeEnabled()
})

it('shows failed work as a localized draft with its persisted preview and Continue action', async () => {
  const api = client(); api.get.mockImplementation(async path => path.endsWith('/runs') ? { items: [failedDraft] } : path.includes('/runs/') ? failedDraft : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  expect(await screen.findByRole('heading', { name: 'Чернетки' })).toBeVisible()
  expect(screen.getByText('Помилка')).toBeVisible()
  expect(screen.getByText('Порівняння перевищило час. Продовжте, щоб повторити зі збереженим прев’ю.')).toBeVisible()
  await waitFor(() => expect(api.image).toHaveBeenCalledWith('/api/v1/templates/media/' + preview.sha256, 'image/png', preview.sha256))
  fireEvent.click(screen.getByRole('button', { name: 'Відкрити / Продовжити' }))
  expect(await screen.findByRole('button', { name: 'Продовжити / уточнити' })).toBeEnabled()
})

it('refreshes active draft summaries without requiring the draft to be open', async () => {
  vi.useFakeTimers()
  const active = { ...failedDraft, status: 'comparing', error: null, failure: undefined }
  const api = client(); api.get.mockImplementation(async path => path.endsWith('/runs') ? { items: [active] } : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
  const initial = api.get.mock.calls.filter(([path]) => String(path).endsWith('/runs')).length
  await act(async () => { vi.advanceTimersByTime(1600); await Promise.resolve(); await Promise.resolve() })
  expect(api.get.mock.calls.filter(([path]) => String(path).endsWith('/runs')).length).toBeGreaterThan(initial)
})

it('has loading, gallery failure retry and empty states without fabricating content', async () => {
  const api = client(); api.get.mockRejectedValueOnce(new Error('Unavailable'))
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  expect(screen.getByText('Loading templates…')).toBeVisible()
  expect(await screen.findByText('Unavailable')).toBeVisible()
  api.get.mockResolvedValue({ items: [] })
  fireEvent.click(screen.getByRole('button', { name: /^Retry$/ }))
  expect(await screen.findByText('No templates for this surface yet.')).toBeVisible()
})
