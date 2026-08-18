import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { IdeasView } from './IdeasView'

describe('IdeasView', () => {
  it('exposes only Idea Laval and no legacy generation controls', async () => {
    const api = {
      get: vi.fn().mockResolvedValue({ items: [] }),
      post: vi.fn(),
      blob: vi.fn(),
    } as unknown as ApiClient

    render(<IdeasView api={api} language="uk" />)

    expect(await screen.findByText('Ще немає Laval-запусків.')).toBeInTheDocument()
    expect(screen.queryByText(/Покоління C01/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Нове покоління/ })).not.toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/api/v1/laval/runs?limit=30')
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining('/api/v1/ideas'))
  })
})
