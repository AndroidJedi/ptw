import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Shell } from './Shell'

it('shows Product Briefs, Post, and Landing destinations without a separate Studio destination', () => {
  const props = {
    page: 'briefs' as const, onPage: vi.fn(), language: 'en' as const,
    onLanguage: vi.fn(), onSettings: vi.fn(), children: <p>content</p>,
  }
  const view = render(<Shell {...props} />)
  expect(screen.getAllByRole('button', { name: /^Post$/ })).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: /^Landing$/ })).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: 'Brief' })).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: 'Settings' })).toHaveLength(2)
  expect(screen.queryByRole('button', { name: /^Studio$/ })).not.toBeInTheDocument()

  view.rerender(<Shell {...props} language="uk" />)
  expect(screen.getAllByRole('button', { name: /^Допис$/ })).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: /^Лендінг$/ })).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: 'Бриф' })).toHaveLength(2)
  expect(screen.queryByRole('button', { name: /^Студія$/ })).not.toBeInTheDocument()
})
