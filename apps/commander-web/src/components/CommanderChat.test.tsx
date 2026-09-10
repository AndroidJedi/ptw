import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { CommanderChat } from './CommanderChat'
import { SettingsView } from '../views/SettingsView'

const base = '/api/v1/settings/commander'
Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:commander-image') })
Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
function fixture() {
  let chat = { id: 'chat-1', turns: [] as Record<string, unknown>[] }
  const get = vi.fn(async (path: string) => path === base ? {
    target: 'local', available: true, chats: [{ id: chat.id, title: 'Build a carousel' }],
    active_turn: chat.turns.some(t => t.status === 'running') ? { id: 'turn-1', chat_id: chat.id } : null,
  } : chat)
  const post = vi.fn(async (path: string, body: Record<string, unknown>) => {
    if (path.endsWith('/messages')) chat = { ...chat, turns: [{ id: 'turn-1', message: body.message, reply: '', status: 'running', error_code: null }] }
    if (path.endsWith('/stop')) chat = { ...chat, turns: chat.turns.map(t => ({ ...t, status: 'cancelled', error_code: 'stopped' })) }
    return chat
  })
  return { api: { get, post } as never, get, post }
}

it('opens the mode, sends a real request contract, and stops the active turn', async () => {
  const { api, post } = fixture()
  render(<CommanderChat api={api} language="en" />)
  fireEvent.click(screen.getByRole('button', { name: 'Open Commander chat' }))
  await waitFor(() => expect(screen.queryByText('Loading Commander…')).not.toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'Add a carousel tab' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('Add a carousel tab')).toBeInTheDocument()
  expect(post).toHaveBeenCalledWith(base + '/chats/chat-1/messages', {
    message: 'Add a carousel tab', request_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
  })
  const stop = await screen.findByRole('button', { name: 'Stop' })
  await waitFor(() => expect(stop).toBeEnabled())
  fireEvent.click(stop)
  expect(await screen.findByText(/Request stopped\./)).toBeInTheDocument()
  expect(post).toHaveBeenCalledWith(base + '/chats/chat-1/turns/turn-1/stop', {})
})

it('retains the draft and reuses the request ID after an uncertain response', async () => {
  const { api, post } = fixture()
  post.mockRejectedValueOnce(new Error('Request timed out. Refresh before retrying.'))
  render(<CommanderChat api={api} language="en" />)
  fireEvent.click(screen.getByRole('button', { name: 'Open Commander chat' }))
  await waitFor(() => expect(screen.queryByText('Loading Commander…')).not.toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Message Commander'), { target: { value: 'Fix Telegram' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Request timed out')
  expect(screen.getByLabelText('Message Commander')).toHaveValue('Fix Telegram')
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
  expect(post.mock.calls[0]).toEqual(post.mock.calls[1])
})

it('removes redundant mode copy and sends temporary image attachments', async () => {
  const { api, post } = fixture()
  render(<CommanderChat api={api} language="uk" />)
  expect(screen.queryByText(/Спілкуйтеся з Commander/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Зміни вносяться в ізольовану/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Commander підтримує навички/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Відкрити чат Commander' }))
  await waitFor(() => expect(screen.queryByText('Завантаження Commander…')).not.toBeInTheDocument())
  const file = new File([new Uint8Array([1, 2, 3, 4])], 'settings-screen.png', { type: 'image/png', lastModified: 7 })
  fireEvent.change(screen.getByLabelText('Додати зображення до розмови Commander'), { target: { files: [file] } })
  expect(screen.getByText('settings-screen.png')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Надіслати' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(base + '/chats/chat-1/messages', {
    message: '', request_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
    attachments: [{ name: 'settings-screen.png', mime_type: 'image/png', bytes_base64: 'AQIDBA==' }],
  }, { deadlineMs: 60_000 }))
})

it('restores a persisted running conversation and keeps Stop available', async () => {
  const { api, post } = fixture()
  await post(base + '/chats/chat-1/messages', { message: 'Continue work' })
  render(<CommanderChat api={api} language="uk" />)
  fireEvent.click(screen.getByRole('button', { name: 'Відкрити чат Commander' }))
  expect(await screen.findByText('Continue work')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Зупинити' })).toBeEnabled()
})

it('exposes hosted coding mode alongside authorization in production Settings', async () => {
  const get = vi.fn(async (path: string) => path.includes('chatgpt-authorization')
    ? { status: 'authorized', test_status: 'passed' }
    : path.endsWith('/deployments')
      ? { candidate: { available: true, deployable: false, changed_files: [], protected_files: [] }, deployment: null }
      : { target: 'hosted', available: true, chats: [], active_turn: null })
  render(<SettingsView api={{ get } as never} language="en" />)
  expect(await screen.findByText('Authorized and verified')).toBeInTheDocument()
  expect(screen.getByText(/GOD mode/)).toBeInTheDocument()
  expect(await screen.findByText('Hosted checkout')).toBeInTheDocument()
  expect(get).toHaveBeenCalledWith('/api/v1/settings/commander')
  expect(get).toHaveBeenCalledWith('/api/v1/settings/chatgpt-authorization')
})

it('requires a second mobile confirmation and submits an idempotent production release', async () => {
  const release = { candidate: { available: true, deployable: true, changed_files: ['apps/commander-web/src/change.tsx'], protected_files: [] }, deployment: null }
  const get = vi.fn(async (path: string) => path === base
    ? { target: 'hosted', available: true, chats: [], active_turn: null }
    : path.endsWith('/deployments') ? release : { id: 'chat-1', turns: [] })
  const post = vi.fn(async (path: string) => path.endsWith('/deployments') ? {
    candidate: { ...release.candidate, deployable: false },
    deployment: { id: 'deploy-1', base_revision: 'a'.repeat(40), revision: 'b'.repeat(40), branch: 'god-deploy/1', status: 'queued', error_code: null, workflow_url: null, updated_at: 'now' },
  } : { id: 'chat-1', turns: [] })
  render(<CommanderChat api={{ get, post } as never} language="en" />)
  fireEvent.click(screen.getByRole('button', { name: 'Open Commander chat' }))
  const deploy = await screen.findByRole('button', { name: 'DEPLOY NEW CHANGES' })
  fireEvent.click(deploy)
  expect(screen.getByRole('alertdialog')).toHaveTextContent('Deploy these changes to production?')
  fireEvent.click(screen.getByRole('button', { name: 'Confirm deployment' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith(base + '/deployments', {
    confirmation: 'DEPLOY NEW CHANGES', request_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
  }, { deadlineMs: 30_000 }))
  expect(await screen.findByText('Waiting for the off-server build runner…')).toBeInTheDocument()
})

it('keeps authorization alongside Commander and moves the language action into Settings', async () => {
  const get = vi.fn(async (path: string) => path.includes('chatgpt-authorization')
    ? { status: 'authorized', test_status: null }
    : { target: 'local', available: true, chats: [], active_turn: null })
  const onLanguage = vi.fn()
  render(<SettingsView api={{ get } as never} language="uk" onLanguage={onLanguage} />)
  expect(await screen.findByRole('heading', { name: 'ChatGPT Authorization' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Commander/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Змінити мову' }))
  expect(onLanguage).toHaveBeenCalledOnce()
})
