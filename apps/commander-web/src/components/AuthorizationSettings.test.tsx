import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { AuthorizationSettings } from './AuthorizationSettings'

it('renders only the device-login fields from the safe authorization contract', async () => {
  const api = {
    get: vi.fn().mockResolvedValue({
      status: 'authorizing', test_status: null,
      authorization_url: 'https://auth.openai.com/codex/device', device_code: 'ABCD-1234',
      access_token: 'must-never-render', refresh_token: 'must-never-render',
    }),
    post: vi.fn(),
  }
  render(<AuthorizationSettings api={api as never} language="en" />)
  expect(await screen.findByText('ABCD-1234')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Open authorization page' })).toHaveAttribute(
    'href', 'https://auth.openai.com/codex/device',
  )
  expect(screen.queryByText('must-never-render')).not.toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
