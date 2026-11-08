import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { AgentBotView } from './AgentBotView'

const conversation = { id: 'conversation-1', title: 'Research an idea', status: 'idle' }
const agents = [
  { id: 'commander', name: 'Commander', role: 'Coordinator', description: 'Coordinates.' },
  { id: 'business_researcher', name: 'Business Researcher', role: 'Specialist', description: 'Researches.' },
]
const permissions = [
  { agent_id: 'business_researcher', capability: 'research', mode: 'allowed', reason: 'Can research.' },
  { agent_id: 'business_researcher', capability: 'system_expansion', mode: 'denied', reason: 'Cannot expand.' },
]

function detail(messages: Record<string, unknown>[] = [], status = 'idle'): {
  conversation: typeof conversation & { status: string }
  messages: Record<string, unknown>[]
  tasks: unknown[]
  runs: unknown[]
  actions: Array<Record<string, unknown>>
  agents: typeof agents
  permissions: typeof permissions
} {
  return { conversation: { ...conversation, status }, messages, tasks: [], runs: [], actions: [], agents, permissions }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() })
  vi.stubGlobal('crypto', { randomUUID: () => 'request-1' })
})

it('shows the two agents and sends a business idea through the bot workspace', async () => {
  let current = detail()
  const get = vi.fn(async (path: string) => {
    if (path === '/api/v1/agent-bot') return { available: true, agents, permissions, conversations: [] }
    return current
  })
  const post = vi.fn(async (path: string, body: Record<string, unknown>) => {
    if (path === '/api/v1/agent-bot/conversations') return { conversation: current.conversation }
    current = detail([{ id: 'message-1', sender: 'user', recipient: 'commander', kind: 'user_input', text: body.message, data: {} }], 'working')
    return current
  })
  render(<AgentBotView api={{ get, post } as never} language="en" />)
  expect(await screen.findByText('Business Researcher')).toBeInTheDocument()
  expect(screen.getByRole('complementary', { name: 'Agents pane' })).toBeInTheDocument()
  expect(screen.getByText('Pane 02 · Hub-and-spoke')).toBeInTheDocument()
  expect(screen.getByRole('complementary', { name: 'Task and permissions pane' })).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Message Commander Bot'), { target: { value: 'A service for family meal planning' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/agent-bot/conversations/conversation-1/messages', expect.objectContaining({ message: 'A service for family meal planning', request_id: 'request-1' })))
  expect(await screen.findByText('A service for family meal planning')).toBeInTheDocument()
})

it('exposes an approval card without allowing a specialist to bypass policy', async () => {
  const current = detail([], 'waiting_approval')
  current.actions = [{ id: 'action-1', action_type: 'system_expansion', mode: 'approval_required', status: 'pending', reason: 'Owner approval is required.', payload: {} }]
  const get = vi.fn(async (path: string) => path === '/api/v1/agent-bot' ? { available: true, agents, permissions, conversations: [conversation] } : current)
  const post = vi.fn(async () => current)
  render(<AgentBotView api={{ get, post } as never} language="en" />)
  expect(await screen.findByText('Owner approval required')).toBeInTheDocument()
  expect(screen.getByText('denied')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Approve' })).toBeEnabled()
})
