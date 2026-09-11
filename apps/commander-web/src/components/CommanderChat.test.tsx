import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { CommanderChat } from './CommanderChat'

const base = '/api/v1/settings/commander'
const preferences = { mode: 'build', model: 'available', effort: 'medium' }
const capabilities = { models: [
  { id: 'available', name: 'Available model', default: true, default_effort: 'medium', efforts: ['low', 'medium', 'high'] },
  { id: 'fast', name: 'Fast model', default: false, default_effort: 'low', efforts: ['low'] },
], modes: ['build', 'plan'] }
Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:commander-image') })
Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) || null, setItem: (key: string, value: string) => values.set(key, value) })
})

function fixture(turns: Record<string, unknown>[] = [], hosted = false) {
  let chat = { id: 'chat-1', turns, preferences, questions: [] as Record<string, unknown>[] }
  let deployment: Record<string, unknown> | null = null
  const get = vi.fn(async (path: string) => {
    if (path === base) return { target: hosted ? 'hosted' : 'local', available: true, chats: [{ id: chat.id, title: 'Build a carousel' }], active_turn: chat.turns.some(t => t.status === 'running') ? { id: 'turn-1', chat_id: chat.id } : null }
    if (path.endsWith('/capabilities')) return capabilities
    if (path.includes('/events?')) return { cursor: 0, events: [] }
    if (path.includes('/deployments')) return { candidate: { available: true, deployable: !deployment, changed_files: ['Dockerfile'] }, deployment }
    return chat
  })
  const post = vi.fn(async (path: string, body: Record<string, unknown>) => {
    if (path.endsWith('/messages')) chat = { ...chat, turns: [...chat.turns, { id: `turn-${chat.turns.length + 1}`, message: body.message, reply: '', status: chat.turns.some(t => t.status === 'running') ? 'steered' : 'running', mode: body.mode }] }
    if (path.endsWith('/stop')) chat = { ...chat, turns: chat.turns.map(t => ({ ...t, status: 'cancelled' })) }
    if (path.endsWith('/deploy')) deployment = { id: 'release-1', status: 'queued', chat_id: chat.id }
    return chat
  })
  return { api: { get, post } as never, get, post, question: (value: Record<string, unknown>) => { chat.questions = [value] } }
}

async function ready() {
  await waitFor(() => expect(screen.getByLabelText('Model')).toHaveValue('available'))
  await waitFor(() => expect(screen.queryByText('Loading Commander…')).not.toBeInTheDocument())
}

it('opens directly, sends settings, permits live replies, and stops separately', async () => {
  const { api, post } = fixture()
  render(<CommanderChat api={api} language="en" />)
  await ready()
  expect(screen.queryByRole('button', { name: 'Open Commander chat' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'Build feature' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText('Build feature')
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'Also make it blue' } })
  expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText('Also make it blue')
  expect(post).toHaveBeenCalledWith(base + '/chats/chat-1/messages', expect.objectContaining({ message: 'Also make it blue', ...preferences, request_id: expect.any(String) }), { deadlineMs: 60_000 })
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
  await screen.findAllByText(/This task stopped before completion/)
})

it('retains draft and request UUID after an uncertain submission', async () => {
  const { api, post } = fixture()
  post.mockRejectedValueOnce(new Error('Request timed out'))
  render(<CommanderChat api={api} language="en" />)
  await ready()
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'Fix layout' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('Message Commander')).toHaveValue('Fix layout')
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
  expect(post.mock.calls[0]).toEqual(post.mock.calls[1])
})

it('renders Markdown and sends a targeted reply in the same conversation', async () => {
  const { api, post } = fixture([{ id: 'first', message: 'Discuss', reply: '**A useful answer**', status: 'completed' }])
  render(<CommanderChat api={api} language="en" />)
  await ready()
  expect(screen.getByText('A useful answer').tagName).toBe('STRONG')
  fireEvent.click(screen.getByRole('button', { name: 'Reply to message' }))
  expect(screen.getByText('Replying to Commander')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'Explain this part' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(expect.stringContaining('/chat-1/messages'), expect.objectContaining({ reply_to_message_id: 'first' }), expect.anything()))
})

it('implements the selected plan in Build without adding deployment intent', async () => {
  const { api, post } = fixture([{ id: 'plan', message: 'Plan it', reply: 'Selected plan', status: 'completed', mode: 'plan' }])
  render(<CommanderChat api={api} language="en" />)
  await ready()
  fireEvent.click(screen.getByRole('button', { name: 'Implement plan' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(expect.stringContaining('/messages'), expect.objectContaining({ mode: 'build', reply_to_message_id: 'plan', message: 'Implement this plan.' }), expect.anything()))
})

it('offers only compatible efforts and persists mode/model preferences', async () => {
  const { api, post } = fixture()
  render(<CommanderChat api={api} language="en" />)
  await ready()
  fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'fast' } })
  expect(screen.getByLabelText('Effort')).toHaveValue('low')
  expect(screen.queryByRole('option', { name: 'high' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Mode'), { target: { value: 'plan' } })
  expect(post).toHaveBeenLastCalledWith(base + '/chats/chat-1/preferences', { mode: 'plan', model: 'fast', effort: 'low' })
})

it('starts hosted deployment with one click and no extra confirmation', async () => {
  const { api, post } = fixture([], true)
  render(<CommanderChat api={api} language="en" />)
  await ready()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Deploy' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Deploy' }))
  await screen.findByText('Building, checking and deploying…')
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  expect(post).toHaveBeenCalledWith(base + '/chats/chat-1/deploy', { request_id: expect.any(String) }, expect.anything())
})

it('submits suggested question answers and supports free text', async () => {
  const setup = fixture()
  setup.question({ id: 'question', status: 'pending', payload: { questions: [{ id: 'colour', question: 'Which colour?', options: [{ label: 'Blue', description: 'Cool colour' }] }] } })
  render(<CommanderChat api={setup.api} language="en" />)
  await ready()
  fireEvent.click(screen.getByRole('radio', { name: /Blue/ }))
  fireEvent.change(screen.getByLabelText('Your answer: Which colour?'), { target: { value: 'Dark blue' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send answer' }))
  await waitFor(() => expect(setup.post).toHaveBeenCalledWith(base + '/chats/chat-1/questions/question/answers', { request_id: expect.any(String), answers: { colour: ['Dark blue'] } }))
})

it('restores per-conversation draft after navigation', async () => {
  const { api } = fixture()
  const view = render(<CommanderChat api={api} language="en" />)
  await ready()
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'My unfinished question' } })
  view.unmount()
  render(<CommanderChat api={api} language="en" />)
  await ready()
  expect(screen.getByLabelText('Message Commander')).toHaveValue('My unfinished question')
})
