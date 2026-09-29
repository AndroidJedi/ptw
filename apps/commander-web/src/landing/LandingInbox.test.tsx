import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { LandingInbox } from './LandingInbox'

it('keeps visitor contacts private plain text and exposes exact receipt IDs for the owner', async () => {
  const get = vi.fn(async () => ({ items: [{ request_id: 'receipt-id', landing_version_id: 'version-id', created_at: '2026-09-29T00:00:00Z', source: 'apple', slug: 'example', question: 'Could I suggest a source?', contact_channel: 'instagram', contact: '@visitor' }] }))
  render(<LandingInbox api={{ get } as unknown as ApiClient} projectId="project-id" language="en" />)
  expect(await screen.findByText('Could I suggest a source?')).toBeVisible()
  expect(screen.getByText('@visitor')).toBeVisible()
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('Technical details'))
  expect(screen.getByText(/receipt-id/)).toBeVisible()
  expect(get).toHaveBeenCalledWith('/api/v1/landings/projects/project-id/inquiries')
})

it('offers a retry after a failed inbox request without exposing raw server output', async () => {
  const get = vi.fn().mockRejectedValueOnce(new Error('raw server output')).mockResolvedValueOnce({ items: [] })
  render(<LandingInbox api={{ get } as unknown as ApiClient} projectId="project-id" language="en" />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load inquiries.')
  expect(screen.queryByText('raw server output')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('No inquiries yet.')).toBeVisible()
})
