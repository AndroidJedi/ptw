import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Shell } from './Shell'

it('shows one Post destination and no separate Studio destination', () => {
  const props = {
    page: 'briefs' as const, onPage: vi.fn(), language: 'en' as const,
    onLanguage: vi.fn(), children: <p>content</p>,
  }
  const view = render(<Shell {...props} />)
  expect(screen.getAllByRole('button', { name: /^Post$/ })).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: 'Product Briefs' })).toHaveLength(2)
  expect(screen.queryByRole('button', { name: /^Studio$/ })).not.toBeInTheDocument()

  view.rerender(<Shell {...props} language="uk" />)
  expect(screen.getAllByRole('button', { name: /^Допис$/ })).toHaveLength(2)
  expect(screen.queryByRole('button', { name: /^Студія$/ })).not.toBeInTheDocument()
})
