import { render, screen } from '@testing-library/react'
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
})
