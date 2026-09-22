import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { TemplatesView } from './TemplatesView'
vi.mock('../firebase', () => ({ appCheck: {} }))

const preview = { sha256: 'a'.repeat(64), definition_sha256: 'b'.repeat(64) }
const item = { surface: 'post', template_id: 'phone_metrics', template_version: 27, template_sha256: 'b'.repeat(64), name: 'Phone & metrics', description: 'Reusable phone', builtin: true, status: 'registered', preview_status: 'ready', previews: { desktop: preview } }
const proposed = { run_id: '018f07ea-7f20-7000-8000-000000000010', scope: 'combined', status: 'proposed', state_sha256: 'c'.repeat(64), phase: 'compare', iterations: 2, error: null, previews: { 'post:desktop': preview }, comparison: { differences: [] }, capability_gap: null, invocations: [{ phase: 'compare', contract_bytes: { total: 10000 }, response_bytes: 500, attempt_count: 1 }], accepted_versions: [] }
const failedDraft = { ...proposed, run_id: '018f07ea-7f20-7000-8000-000000000011', scope: 'post', status: 'failed', iterations: 1, error: 'Template Agent timed out', failure: { phase: 'compare', category: 'timeout', model: 'codex-cli-default', reasoning_effort: 'xhigh', attempt_count: 1, validation_error: '' } }
const pausedDraft = { ...proposed, run_id: '018f07ea-7f20-7000-8000-000000000012', scope: 'post', status: 'paused', phase: 'adjust', iterations: 4, error: 'Review checkpoint reached', can_restore: true, checkpoint: { reason: 'segment_checkpoint', recommendation: 'continue', pending_edits: 3, remaining_iterations: 8, meaningful_differences: [{ surface: 'post', role: 'decoration', category: 'component_style' }] }, comparison: { differences: [{ surface: 'post', role: 'decoration', category: 'component_style', issue: 'Faint motif shape differs', severity: 'meaningful', solvable: true }] } }
function client() { return { get: vi.fn(async (path: string): Promise<unknown> => path.endsWith('/runs') ? { items: [] } : path.includes('/versions/') ? item : { items: [item] }), image: vi.fn(async () => new Blob(['png'], { type: 'image/png' })), post: vi.fn(async (_path: string, _body: unknown, _options?: unknown) => proposed) } }
beforeEach(() => {
  const storage = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
    clear: () => storage.clear(),
  } })
  Element.prototype.scrollIntoView = vi.fn(); window.history.replaceState(null, '', '/?page=templates'); vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() }))
})
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

it('keeps a built-in Landing available when its preview renderer fails', async () => {
  const landing = { ...item, surface: 'landing', template_id: 'project_landing', template_version: 5,
    template_sha256: '6bd068332255e5bf294341f85f46d31f3708b933282cb4bf09497b3511466d7a',
    name: 'Project landing', preview_status: 'failed', previews: {} }
  const api = client()
  api.get.mockImplementation(async path => path.endsWith('/runs') ? { items: [] }
    : path.includes('/versions/') ? landing : { items: [landing] })
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open template' }))
  expect(await screen.findByText('This template is available, but its preview could not be rendered. Retry the preview or edit from your instruction.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Edit template' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry preview' }))
  await waitFor(() => expect(api.get.mock.calls.filter(([path]) => path.includes('/versions/5?sha256='))).toHaveLength(2))
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

it('keeps two selected template assets in order and sends both references to the edit agent', async () => {
  const api = client()
  let number = 0
  api.post.mockImplementation(async path => path.endsWith('/references')
    ? { reference_id: `018f07ea-7f20-7000-8000-0000000000${++number}` } as unknown as typeof proposed
    : proposed)
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open template' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Edit template' }))
  const input = screen.getByLabelText('Visual references (up to 2)') as HTMLInputElement
  expect(input.accept).toContain('.svg')
  expect(input.multiple).toBe(true)
  const apple = new File(['png'], 'apple.png', { type: 'image/png' })
  const google = new File(['png'], 'google.png', { type: 'image/png' })
  fireEvent.change(input, { target: { files: [apple, google] } })
  expect(screen.getByText('1. apple.png')).toBeVisible()
  expect(screen.getByText('2. google.png')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Design instruction'), { target: { value: 'Use both attached badge assets' } })
  fireEvent.click(screen.getByRole('button', { name: 'Start creation' }))
  await waitFor(() => expect(api.post.mock.calls.filter(([path]) => path.endsWith('/references'))).toHaveLength(2))
  await waitFor(() => expect(api.post.mock.calls.find(([path]) => path.endsWith('/runs'))?.[1]).toMatchObject({
    reference_ids: ['018f07ea-7f20-7000-8000-00000000001', '018f07ea-7f20-7000-8000-00000000002'],
  }))
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
  expect((await screen.findAllByText('Worker stopped'))[0]).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Accept template version' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Continue saved changes' })).toBeEnabled()
})

it('shows failed work as a localized draft with its persisted preview and Continue action', async () => {
  const api = client(); api.get.mockImplementation(async path => path.endsWith('/runs') ? { items: [failedDraft] } : path.includes('/runs/') ? failedDraft : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  expect(await screen.findByRole('heading', { name: 'Чернетки' })).toBeVisible()
  expect(screen.getByText('Помилка')).toBeVisible()
  expect(screen.getByText('Порівняння перевищило час. Продовжте, щоб повторити зі збереженим прев’ю.')).toBeVisible()
  await waitFor(() => expect(api.image).toHaveBeenCalledWith('/api/v1/templates/media/' + preview.sha256, 'image/png', preview.sha256))
  fireEvent.click(screen.getByRole('button', { name: 'Переглянути наступну дію' }))
  expect(await screen.findByRole('button', { name: 'Продовжити збережені зміни' })).toBeEnabled()
  expect(screen.queryByRole('button', { name: 'Прийняти версію шаблону' })).not.toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Робоча область шаблону · Post' })).toHaveFocus()
  expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior: 'auto' })
})

it('moves a proposed draft into a clear review panel with the decision first', async () => {
  const postProposal = { ...proposed, scope: 'post' }
  const api = client(); api.get.mockImplementation(async path => path.endsWith('/runs') ? { items: [postProposal] } : path.includes('/runs/') ? postProposal : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Відкрити для перевірки' }))
  const panel = await screen.findByRole('region', { name: 'Перевірка шаблону · Post' })
  expect(panel).toHaveFocus()
  expect(screen.getByText('Перевірте прев’ю. Прийняття створить незмінну версію та зробить її доступною у проєктах.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Прийняти версію шаблону' })).toBeEnabled()
  expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior: 'auto' })
})

it('shows a localized checkpoint and continues pending edits with one action', async () => {
  const api = client(); api.get.mockImplementation(async path => path.endsWith('/runs') ? { items: [pausedDraft] } : path.includes('/runs/') ? pausedDraft : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Переглянути наступну дію' }))
  expect(await screen.findByText('Можна продовжувати')).toBeVisible()
  expect(screen.getByText(/Підготовлено змін: 3/)).toBeVisible()
  expect(screen.getByText('Вигляд компонента')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Прийняти версію шаблону' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Продовжити збережені зміни' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/resume'), expect.objectContaining({ mode: 'continue', instruction: '', base_sha256: pausedDraft.state_sha256 }), expect.anything()))
})

it('supports focused refine and append-only proposal restore actions', async () => {
  window.history.replaceState(null, '', '/?page=templates&template_run=' + pausedDraft.run_id)
  const api = client(); api.get.mockImplementation(async path => path.includes('/runs/') ? pausedDraft : path.endsWith('/runs') ? { items: [] } : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  await screen.findByText('Можна продовжувати')
  fireEvent.click(screen.getByRole('button', { name: 'Додати уточнення' }))
  fireEvent.change(screen.getByLabelText('Уточнення'), { target: { value: 'Залишити композицію та використати два символи Natal' } })
  fireEvent.click(screen.getByRole('button', { name: 'Застосувати уточнення' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/resume'), expect.objectContaining({ mode: 'refine', instruction: 'Залишити композицію та використати два символи Natal' }), expect.anything()))

  const restoreApi = client(); restoreApi.get.mockImplementation(async path => path.includes('/runs/') ? pausedDraft : path.endsWith('/runs') ? { items: [] } : { items: [item] })
  render(<TemplatesView api={restoreApi as unknown as ApiClient} language="uk" />)
  await screen.findAllByText('Можна продовжувати')
  fireEvent.click(screen.getAllByRole('button', { name: 'Повернути останню готову версію' }).at(-1)!)
  await waitFor(() => expect(restoreApi.post).toHaveBeenCalledWith(expect.stringContaining('/corrections/discard'), expect.objectContaining({ base_sha256: pausedDraft.state_sha256 }), expect.anything()))
})

it('shows the exact failed correction, hides stale acceptance, and retries that correction', async () => {
  const correction = { correction_id: '018f07ea-7f20-7000-8000-000000000099', instruction: 'Зменшити два Natal-знаки та повернути їх під різними кутами', status: 'failed', submitted_revision: 98, result_revision: null, reference: { sha256: 'd'.repeat(64), mime_type: 'image/png', byte_count: 1024 }, failure: failedDraft.failure, retry_count: 0 }
  const failed = { ...failedDraft, can_restore: true, latest_correction: correction, correction_history: [correction] }
  window.history.replaceState(null, '', '/?page=templates&template_run=' + failed.run_id)
  const api = client(); api.get.mockImplementation(async path => path.includes('/runs/') ? failed : path.endsWith('/runs') ? { items: [failed] } : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  expect(await screen.findByRole('heading', { name: 'Ваш запит' })).toBeVisible()
  expect(screen.getByText(correction.instruction)).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Прийняти версію шаблону' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Повторити моє уточнення' }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/corrections/retry'), expect.objectContaining({ base_sha256: failed.state_sha256 }), expect.anything()))
})

it('separates a service contract failure from the previous comparison and gates retry readiness', async () => {
  const correction = { correction_id: '018f07ea-7f20-7000-8000-000000000091', instruction: 'Remove the extra pill and enlarge the badges', status: 'failed', submitted_revision: 16, result_revision: null, reference: null, failure: null, retry_count: 2 }
  const blocked = { ...failedDraft, phase: 'compose', latest_correction: correction, comparison: { differences: [], applied_correction_id: 'older-correction' }, retry_ready: false,
    failure: { ...failedDraft.failure, phase: 'compose', category: 'contract', validation_error: 'template_creation system prompt exceeds its compact byte budget' },
    checkpoint: { reason: 'provider_failure', recommendation: 'continue', pending_edits: 0, remaining_iterations: 11, meaningful_differences: [] } }
  window.history.replaceState(null, '', '/?page=templates&template_run=' + blocked.run_id)
  const api = client(); api.get.mockImplementation(async path => path.includes('/runs/') ? blocked : path.endsWith('/runs') ? { items: [blocked] } : { items: [item] })
  const view = render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  expect(await screen.findByText(correction.instruction)).toBeVisible()
  expect(screen.queryByText('No unresolved visual differences reported.')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Retry my correction' })).toBeDisabled()
  expect(screen.getAllByText(/service rejected its own agent request/i).length).toBeGreaterThan(0)
  view.unmount()
  const ready = { ...blocked, retry_ready: true }
  api.get.mockImplementation(async path => path.includes('/runs/') ? ready : path.endsWith('/runs') ? { items: [ready] } : { items: [item] })
  render(<TemplatesView api={api as unknown as ApiClient} language="en" />)
  expect(await screen.findByText('The service is ready to retry this saved edit.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Retry my correction' })).toBeEnabled()
})

it('recovers an unconfirmed correction text from browser storage after refresh', async () => {
  window.history.replaceState(null, '', '/?page=templates&template_run=' + pausedDraft.run_id)
  const api = client(); api.get.mockImplementation(async path => path.includes('/runs/') ? pausedDraft : path.endsWith('/runs') ? { items: [] } : { items: [item] }); api.post.mockRejectedValueOnce(new Error('Connection lost'))
  const first = render(<TemplatesView api={api as unknown as ApiClient} language="uk" />)
  await screen.findByText('Можна продовжувати')
  fireEvent.click(screen.getByRole('button', { name: 'Додати уточнення' }))
  fireEvent.change(screen.getByLabelText('Уточнення'), { target: { value: 'Мій точний незбережений запит' } })
  fireEvent.click(screen.getByRole('button', { name: 'Застосувати уточнення' }))
  expect((await screen.findAllByText('Мій точний незбережений запит'))[0]).toBeVisible()
  first.unmount()

  const earlierCorrection = { correction_id: '018f07ea-7f20-7000-8000-000000000098', instruction: 'Попередній запит', status: 'applied', submitted_revision: 90, result_revision: 95, reference: null, failure: null, retry_count: 0 }
  const refreshedApi = client(); refreshedApi.get.mockImplementation(async path => path.includes('/runs/') ? { ...proposed, latest_correction: earlierCorrection } : path.endsWith('/runs') ? { items: [] } : { items: [item] })
  render(<TemplatesView api={refreshedApi as unknown as ApiClient} language="uk" />)
  expect((await screen.findAllByText('Мій точний незбережений запит'))[0]).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Прийняти версію шаблону' })).not.toBeInTheDocument()
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
