import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { LavalEngine } from './LavalEngine'

describe('LavalEngine', () => {
  it('shows a web-native empty state and create action', async () => {
    const api = {
      get: vi.fn().mockResolvedValue({ items: [] }),
      post: vi.fn(),
      blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)
    expect(await screen.findByText('Ще немає Laval-запусків.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Нова Laval-ідея/ })).toBeInTheDocument()
    expect(screen.getByText('Evidence → opportunity → trend → ideas')).toBeInTheDocument()
  })

  it('submits the owner idea through the Laval API', async () => {
    const post = vi.fn().mockReturnValue(new Promise(() => undefined))
    const api = {
      get: vi.fn().mockResolvedValue({ items: [] }),
      post,
      blob: vi.fn(),
    } as unknown as ApiClient
    render(<LavalEngine api={api} language="uk" />)

    fireEvent.click(await screen.findByRole('button', { name: /Нова Laval-ідея/ }))
    fireEvent.change(screen.getByLabelText('Повний текст ідеї'), { target: { value: 'A fully formed owner idea' } })
    fireEvent.click(screen.getByRole('button', { name: /Створити інспектований запуск/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/laval/runs', {
      text: 'A fully formed owner idea',
      config: {
        approval_mode: 'manual',
        countries: [
          { code: 'US', language: 'en' },
          { code: 'GB', language: 'en' },
          { code: 'DE', language: 'de', secondary_language: 'en' },
          { code: 'NO', language: 'no', secondary_language: 'en' },
          { code: 'DK', language: 'da', secondary_language: 'en' },
        ],
      },
    }))
  })
})
