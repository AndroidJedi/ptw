import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ApiClient } from '../../api'
import type { StudioPhoneMetricsDetail } from '../../types'
import { PostTemplatePicker } from './PostTemplatePicker'
vi.mock('../../firebase', () => ({ appCheck: {} }))
vi.mock('../../views/TemplatesView', () => ({ TemplateImage: ({ label }: { label: string }) => <span>{label} preview</span> }))

it('applies an exact accepted version with current unsaved edits and reconciles response loss', async () => {
  const item = { surface: 'post', template_id: 'design_123', template_version: 2, template_sha256: 'a'.repeat(64), name: 'Clean design', previews: {} }
  const api = { get: vi.fn(async () => ({ items: [item] })), post: vi.fn().mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValue({ template_id: item.template_id }) }
  const onApply = vi.fn()
  const detail = { state_sha256: 'b'.repeat(64) } as StudioPhoneMetricsDetail
  const configuration = { logo: { symbol_color: '#123456' } } as StudioPhoneMetricsDetail['configuration']
  const content = { hero_title: 'Pending owner headline' } as StudioPhoneMetricsDetail['content']
  render(<PostTemplatePicker api={api as unknown as ApiClient} language="en" basePath="/post" detail={detail} configuration={configuration} content={content} disabled={false} onApply={onApply} />)
  fireEvent.click(screen.getByRole('button', { name: 'Change template' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Clean design · v2' }))
  fireEvent.click(screen.getByRole('button', { name: 'Apply to this Post' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Retry same request' }))
  await waitFor(() => expect(onApply).toHaveBeenCalledWith({ template_id: item.template_id }))
  expect(api.post.mock.calls[0]).toEqual(api.post.mock.calls[1])
  expect(api.post.mock.calls[0][1]).toMatchObject({ base_sha256: detail.state_sha256, configuration, content,
    template_reference: { surface: 'post', template_id: item.template_id, template_version: 2, template_sha256: item.template_sha256 } })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
