import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Shell } from './Shell'

it('shows the Post destination only for the loopback local app', () => {
  const props = {
    page: 'briefs' as const, onPage: vi.fn(), language: 'en' as const,
    onLanguage: vi.fn(), children: <p>content</p>,
  }
  const view = render(<Shell {...props} postsAvailable={false} />)
  expect(screen.queryByRole('button', { name: /^Post$/ })).not.toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Product Briefs' })).toHaveLength(2)

  view.rerender(<Shell {...props} postsAvailable />)
  expect(screen.getAllByRole('button', { name: /^Post$/ })).toHaveLength(2)
})
