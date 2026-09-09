import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { CommanderChat } from './CommanderChat'
import { SettingsView } from '../views/SettingsView'

const base = '/api/v1/settings/commander'
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

it('restores a persisted running conversation and keeps Stop available', async () => {
  const { api, post } = fixture()
  await post(base + '/chats/chat-1/messages', { message: 'Continue work' })
  render(<CommanderChat api={api} language="uk" />)
  fireEvent.click(screen.getByRole('button', { name: 'Відкрити чат Commander' }))
  expect(await screen.findByText('Continue work')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Зупинити' })).toBeEnabled()
})

it('does not expose the coding mode or call its API in production Settings', async () => {
  const get = vi.fn().mockResolvedValue({ status: 'authorized', test_status: 'passed' })
  render(<SettingsView api={{ get } as never} language="en" />)
  expect(await screen.findByText('Authorized and verified')).toBeInTheDocument()
  expect(screen.queryByText(/GOD mode/)).not.toBeInTheDocument()
  expect(get).toHaveBeenCalledTimes(1)
  expect(get).toHaveBeenCalledWith('/api/v1/settings/chatgpt-authorization')
})

it('keeps authorization alongside Commander and moves the language action into Settings', async () => {
  const get = vi.fn(async (path: string) => path.includes('chatgpt-authorization')
    ? { status: 'authorized', test_status: null }
    : { target: 'local', available: true, chats: [], active_turn: null })
  const onLanguage = vi.fn()
  render(<SettingsView api={{ get } as never} language="uk" localMode onLanguage={onLanguage} />)
  expect(await screen.findByRole('heading', { name: 'ChatGPT Authorization' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Commander/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Змінити мову' }))
  expect(onLanguage).toHaveBeenCalledOnce()
})
