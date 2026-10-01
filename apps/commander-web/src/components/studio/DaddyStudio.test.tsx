import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DaddyStudio, type DaddyDetail } from './DaddyStudio'
import fixture from '../../../e2e/daddy-fixture.json'
import type { ApiClient } from '../../api'
vi.mock('../../firebase', () => ({ appCheck: {} }))

describe('Daddy editor', () => {
  beforeEach(() => {
    sessionStorage.clear()
    URL.createObjectURL = vi.fn(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn()
  })
  const setup = () => {
    const api = { postMedia: vi.fn().mockResolvedValue(new Blob()), download: vi.fn().mockResolvedValue(new Blob()), post: vi.fn() }
    const detail = structuredClone(fixture) as unknown as DaddyDetail
    detail.asset_generation_available = true
    const view = render(<DaddyStudio api={api as unknown as ApiClient} language="en" basePath="/creative" detail={detail} onDetail={vi.fn()} />)
    return { api, detail, view }
  }
  it('keeps grouped panels collapsed and waits for Update preview after copy edits', async () => {
    const { api } = setup()
    await waitFor(() => expect(api.postMedia).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('heading', { name: 'Copy' }).closest('details')).not.toHaveAttribute('open')
    fireEvent.click(screen.getByRole('heading', { name: 'Copy' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Headline' }), { target: { value: 'Owner copy' } })
    expect(api.postMedia).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Update preview' }))
    await waitFor(() => expect(api.postMedia).toHaveBeenCalledTimes(2))
    expect(api.postMedia.mock.calls[1][1].content.hero_title).toBe('Owner copy')
  })
  it('switches composition without replacing owner copy or making image calls', async () => {
    const { api } = setup()
    fireEvent.click(screen.getByRole('heading', { name: 'Copy' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Headline' }), { target: { value: 'Keep this headline' } })
    fireEvent.click(screen.getByRole('heading', { name: 'Composition' }))
    fireEvent.click(screen.getByRole('button', { name: 'Phone on a blurred scene' }))
    expect(screen.getByRole('textbox', { name: 'Headline' })).toHaveValue('Keep this headline')
    expect(screen.getByRole('heading', { name: 'App screen' })).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })
  it('proposes only reusable settings through Templates', async () => {
    const { api } = setup()
    api.post.mockResolvedValue({ run_id: 'proposal' })
    fireEvent.click(screen.getByRole('heading', { name: 'Composition' }))
    fireEvent.click(screen.getByRole('button', { name: 'Propose as reusable template' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [path, body] = api.post.mock.calls[0]
    expect(path).toBe('/api/v1/templates/runs')
    expect(body.daddy_configuration.preset).toBe('bold_poster')
    expect(body).not.toHaveProperty('content')
    expect(body).not.toHaveProperty('assets')
  })
  it('retries an uncertain asset response with the same request and retains it across remount', async () => {
    const { api, detail, view } = setup()
    api.post.mockImplementation(async (path: string, body: Record<string, unknown>) => {
      if (path.endsWith('/configuration')) return { ...detail, configuration: body.configuration, content: body.content }
      throw new Error('Response was lost')
    })
    fireEvent.click(screen.getByRole('heading', { name: 'Composition' }))
    fireEvent.click(screen.getByRole('button', { name: 'Phone on a blurred scene' }))
    fireEvent.click(screen.getByRole('heading', { name: 'App screen' }))
    fireEvent.change(await screen.findByRole('textbox', { name: 'Image direction' }), { target: { value: 'A readable booking screen without hands' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry image request' })).toBeEnabled())
    const first = api.post.mock.calls.find(call => String(call[0]).endsWith('/assets/screen'))!
    expect(JSON.parse(sessionStorage.getItem('ptw:daddy:asset:/creative')!).body.request_id).toBe(first[1].request_id)
    view.unmount()
    render(<DaddyStudio api={api as unknown as ApiClient} language="en" basePath="/creative" detail={detail} onDetail={vi.fn()} />)
    api.post.mockResolvedValue(detail)
    fireEvent.click(screen.getByRole('button', { name: 'Retry image request' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Retry image request' })).not.toBeInTheDocument())
    expect(api.post.mock.calls.at(-1)).toEqual(first)
    expect(sessionStorage.getItem('ptw:daddy:asset:/creative')).toBeNull()
  })
})
