import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../../api'
import { StudioManualAgent } from './StudioManualAgent'

describe('Studio Manual Agent', () => {
  const storage = new Map<string, string>()
  beforeEach(() => {
    storage.clear()
    Object.defineProperty(window, 'localStorage', { configurable: true, value: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      clear: () => storage.clear(),
      key: (index: number) => [...storage.keys()][index] ?? null,
      get length() { return storage.size },
    } })
  })

  it('sends bounded draft state and ephemeral screenshots, then applies the returned controls', async () => {
    const post = vi.fn().mockResolvedValue({
      request_id: '11111111-1111-4111-8111-111111111111',
      base_sha256: 'a'.repeat(64),
      configuration: { color: '#222222' },
      content: { title: 'Adjusted title' },
      image_actions: [], changed_paths: ['configuration.color', 'content.title'],
      reply: 'Adjusted the hierarchy and contrast.',
    })
    const api = { post } as unknown as ApiClient
    const onApply = vi.fn()
    const view = render(<StudioManualAgent
      api={api} language="en" endpoint="/api/v1/studio/example/agent"
      stateSha256={'a'.repeat(64)} configuration={{ color: '#111111' }}
      content={{ title: 'Original title' }} onApply={onApply}
    />)

    fireEvent.click(screen.getByRole('button', { name: 'Agent mode' }))
    fireEvent.change(screen.getByLabelText('Task'), { target: { value: 'Improve the hierarchy' } })
    const file = new File([new Uint8Array([1, 2, 3])], 'reference.png', { type: 'image/png' })
    fireEvent.change(view.container.querySelector('input[type="file"]')!, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply task' }))

    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1))
    expect(post).toHaveBeenCalledWith('/api/v1/studio/example/agent', expect.objectContaining({
      base_sha256: 'a'.repeat(64), message: 'Improve the hierarchy',
      configuration: { color: '#111111' }, content: { title: 'Original title' },
      history: [], screenshots: [expect.objectContaining({ mime_type: 'image/png' })],
    }), { deadlineMs: 480_000 })
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({
      content: { title: 'Adjusted title' },
    }), [file])
    expect(await screen.findByText('Adjusted the hierarchy and contrast.')).toBeInTheDocument()
    expect(screen.getByText(/cannot change code, Save, Approve, or Publish/)).toBeInTheDocument()
    const saved = window.localStorage.getItem('ptw-studio-agent-requests-v1:/api/v1/studio/example/agent') || ''
    expect(saved).toContain('Improve the hierarchy')
    expect(saved).not.toContain('reference.png')
  })

  it('retains only the latest two failed text requests per Project and restores the current draft', async () => {
    const post = vi.fn().mockRejectedValue(new Error('The Studio Agent timed out.'))
    const api = { post } as unknown as ApiClient
    const endpoint = '/api/v1/studio/projects/project-a/creatives/creative-a/agent'
    const props = {
      api, language: 'en' as const, endpoint,
      stateSha256: 'a'.repeat(64), configuration: { color: '#111111' },
      content: { title: 'Original title' }, onApply: vi.fn(),
    }
    const view = render(<StudioManualAgent {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Agent mode' }))
    for (const [index, message] of ['First request', 'Second request', 'Third request'].entries()) {
      fireEvent.change(screen.getByLabelText('Task'), { target: { value: message } })
      fireEvent.click(screen.getByRole('button', { name: 'Apply task' }))
      await waitFor(() => expect(post).toHaveBeenCalledTimes(index + 1))
      await screen.findByText('The Studio Agent timed out.')
    }

    const stored = JSON.parse(window.localStorage.getItem('ptw-studio-agent-requests-v1:project-a') || '[]')
    expect(stored.map((item: { message: string }) => item.message)).toEqual(['Third request', 'Second request'])
    expect(stored.every((item: { status: string }) => item.status === 'failed')).toBe(true)

    view.unmount()
    render(<StudioManualAgent {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Agent mode' }))
    expect(screen.getByLabelText('Task')).toHaveValue('Third request')
    expect(screen.getByRole('button', { name: /Third request/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Second request/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /First request/ })).not.toBeInTheDocument()
  })
})
