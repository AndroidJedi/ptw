import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { StudioView } from './StudioView'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const briefId = '018f07ea-7f20-7000-8000-000000000002'
const kitId = '018f07ea-7f20-7000-8000-000000000003'
const batchId = '018f07ea-7f20-7000-8000-000000000004'
const now = '2026-08-25T12:00:00Z'
const validation = (recreation_count = 0) => ({
  validation_id: `validation-${recreation_count}`, recipe_id: recipe(1).recipe_id,
  status: 'approved', attempt_count: recreation_count + 1, recreation_count,
  skill_sha256: '9'.repeat(64), attempts: [], final_summary: 'Ready', created_at: now,
})

beforeAll(() => {
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:studio') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
})

const frame = (tool_id: string, text: string, z_index: number) => ({
  instance_id: `018f07ea-7f20-7000-8000-00000000001${z_index}`, tool_id,
  frame: { x: .08, y: .1 + z_index * .2, width: .84, height: .16 }, z_index,
  params: { text, color: '#FFFFFF', font_size: 36 }, timeline: null, source_asset_ids: [],
})
const renderItem = (ordinal: number) => ({
  render_id: `018f07ea-7f20-7000-8000-0000000002${ordinal}`, recipe_id: `018f07ea-7f20-7000-8000-0000000001${ordinal}`,
  mime_type: 'image/jpeg', width: 1080, height: 1080, bytes_sha256: String(ordinal).repeat(64), manifest: {}, manifest_sha256: 'a'.repeat(64), renderer_version: 'studio-v2', published: false, created_at: now,
  asset_url: `/api/v1/ad-studio/renders/render-${ordinal}/asset`, manifest_url: `/api/v1/ad-studio/renders/render-${ordinal}/manifest`,
})
const recipe = (ordinal: number) => ({
  recipe_id: `018f07ea-7f20-7000-8000-0000000001${ordinal}`, project_id: projectId, brief_id: briefId, brand_kit_id: kitId, parent_recipe_id: null,
  placement_tool_id: 'studio.placement.instagram.feed_square.v1', document: {
    schema_version: 2, parent_recipe_id: null, placement_tool_id: 'studio.placement.instagram.feed_square.v1', duration_seconds: null, frame_rate: null,
    frames: [frame('studio.frame.headline.v1', `Real headline ${ordinal}`, 1), frame('studio.frame.offer.v1', 'Free consultation', 2), frame('studio.frame.cta.v1', 'Book now', 3)], modifiers: [], strategy_ids: ['studio.strategy.one_message.v1'], validation_ids: [], source_reference_ids: [], share: { caption: `Real caption ${ordinal}`, alt_text: `Accessible post ${ordinal}` },
    width: 1080, height: 1080, source_asset_ids: [], renderer_version: 'studio-v2',
  }, document_sha256: 'b'.repeat(64), renderer_version: 'studio-v2', created_by: 'owner', created_at: now,
})
const names = ['Вікно ясності', 'Одне питання — три кроки', 'Прихований маршрут', 'Прозорий процес', 'Не загальний гороскоп']
const angles = ['emotional', 'practical', 'curiosity', 'authority', 'problem_first'] as const
const sampleSet = {
  sample_set_id: '018f07ea-7f20-7000-8000-000000000099', project_id: projectId, brief_id: briefId, batch_id: batchId, brand_kit_id: kitId,
  status: 'completed', created_at: now, download_url: '/api/v1/ad-studio/sample-sets/set/download', download_sha256: 'f'.repeat(64), download_mime_type: 'application/zip',
  items: names.map((name, index) => ({ ordinal: index, angle: angles[index], name, template_id: `template-${index}`, recipe_id: recipe(index + 1).recipe_id, render_id: renderItem(index + 1).render_id, caption: `Real caption ${index + 1}`, alt_text: `Accessible post ${index + 1}`, template: { template_id: `template-${index}` }, recipe: recipe(index + 1), render: renderItem(index + 1), creative_validation: validation(index === 0 ? 0 : 1) })),
}
const persistedProposal = {
  proposal_id: 'proposal-persisted', recipe_id: recipe(1).recipe_id, status: 'previewed',
  instruction: 'Move the headline away from the face', target_instance_id: null,
  patch: { frames: [{ op: 'replace', path: '/0/frame/x', value: .06 }] },
  before_sha256: '4'.repeat(64), after_sha256: '5'.repeat(64),
  preview_url: '/wizard/persisted-preview', preview_sha256: '6'.repeat(64),
  preview_mime_type: 'image/jpeg', created_at: now,
  creative_validation: validation(2),
}

function api(withSamples = false, withRecoveredProposal = false) {
  const post = vi.fn(async (path: string, body: any) => {
    if (path === '/api/v1/ad-studio/sample-sets') return sampleSet
    if (path.endsWith('/wizard-proposals')) return {
      proposal_id: 'proposal-1', recipe_id: recipe(1).recipe_id, status: 'previewed',
      instruction: body.instruction, target_instance_id: body.target_instance_id,
      patch: { frames: [{ op: 'replace', path: '/0/params/font_size', value: 64 }] },
      before_sha256: '1'.repeat(64), after_sha256: '2'.repeat(64),
      preview_url: '/wizard/preview', preview_sha256: '3'.repeat(64), preview_mime_type: 'image/jpeg', created_at: now,
      creative_validation: validation(1),
    }
    if (path === '/api/v1/ad-studio/wizard-proposals/proposal-1/apply') return {
      proposal: { proposal_id: 'proposal-1', recipe_id: recipe(1).recipe_id, status: 'applied', instruction: 'Make it calmer', patch: {}, before_sha256: '1'.repeat(64), after_sha256: '2'.repeat(64), preview_url: '/wizard/preview', applied_recipe_id: recipe(9).recipe_id, created_at: now, creative_validation: validation(1) },
      recipe: recipe(9), render: renderItem(9),
    }
    throw new Error(`unexpected POST ${path}`)
  })
  return {
    get: vi.fn(async (path: string) => {
      if (path.startsWith('/api/v1/briefs?')) return { items: [{ brief_id: briefId, project_id: projectId, project_name: 'Project', request_id: projectId, owner_idea_source_id: projectId, raw_idea: 'Idea', status: 'completed', approved: true, product: 'Product', promise: 'A clear promise', offer: 'Free consultation', cta: 'Book now', creative_batch_id: batchId, failure_count: 0, created_at: now }] }
      if (path.startsWith('/api/v1/ad-studio/sample-sets')) return { items: withSamples ? [sampleSet] : [] }
      if (path.endsWith('/wizard-proposals')) return { items: withRecoveredProposal && path.includes(recipe(1).recipe_id) ? [persistedProposal] : [] }
      throw new Error(`unexpected GET ${path}`)
    }),
    post,
    media: vi.fn(async () => new Blob(['image'], { type: 'image/jpeg' })),
  }
}

describe('StudioView', () => {
  it('shows five simple post choices and no manual editor or technical controls', async () => {
    const client = api(true)
    render(<StudioView api={client as any} projectId={projectId} />)
    const gallery = await screen.findByLabelText('Your five Studio posts')
    expect(within(gallery).getAllByRole('button', { name: /Change .* with AI/ })).toHaveLength(5)
    expect(within(gallery).getByText('Вікно ясності')).toBeInTheDocument()
    expect(within(screen.getByLabelText('Post preview')).getByRole('heading', { name: 'Вікно ясності' })).toBeInTheDocument()
    for (const hidden of ['Edit', 'Share copy', 'Source library', 'Reusable templates', 'Render UUID', 'Download JSON manifest', 'Publish training example']) {
      expect(screen.queryByText(hidden, { exact: true })).not.toBeInTheDocument()
    }
    expect(client.get).not.toHaveBeenCalledWith('/api/v1/ad-studio/tools')
    fireEvent.click(within(gallery).getByRole('button', { name: 'Change Одне питання — три кроки with AI' }))
    expect(await within(screen.getByLabelText('Post preview')).findByRole('heading', { name: 'Одне питання — три кроки' })).toBeInTheDocument()
  })

  it('uses one whole-post Wizard flow to preview and save a new version', async () => {
    const client = api(true)
    render(<StudioView api={client as any} projectId={projectId} />)
    const wizard = await screen.findByLabelText('AI wizard')
    fireEvent.change(within(wizard).getByLabelText('What should change?'), { target: { value: 'Make it calmer' } })
    fireEvent.click(within(wizard).getByRole('button', { name: 'Preview change' }))
    expect(await within(wizard).findByText('New preview ready.')).toBeInTheDocument()
    expect(within(wizard).getByText(/improved and rechecked for 1 round/)).toBeInTheDocument()
    expect(client.post).toHaveBeenCalledWith(expect.stringContaining('/wizard-proposals'), { instruction: 'Make it calmer', target_instance_id: null }, { deadlineMs: 2_400_000 })
    expect(await screen.findByAltText('Preview of proposed change')).toBeInTheDocument()
    expect(within(screen.getByLabelText('Post preview')).getByText('NEW PREVIEW · NOT SAVED')).toBeInTheDocument()
    fireEvent.click(within(wizard).getByRole('button', { name: 'Use this version' }))
    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/wizard-proposals/proposal-1/apply', {}, { deadlineMs: 2_400_000 }))
    expect(await screen.findByText('New version saved.')).toBeInTheDocument()
    expect(within(screen.getByLabelText('Post preview')).getByText('CURRENT VERSION')).toBeInTheDocument()
  })

  it('shows concise honest progress and locks the submitted instruction', async () => {
    const client = api(true)
    const post = client.post.getMockImplementation()!
    let release = () => {}
    client.post.mockImplementation(async (path: string, body: any) => {
      if (path.endsWith('/wizard-proposals')) await new Promise<void>((resolve) => { release = resolve })
      return post(path, body)
    })
    render(<StudioView api={client as any} projectId={projectId} />)
    const wizard = await screen.findByLabelText('AI wizard')
    fireEvent.change(within(wizard).getByLabelText('What should change?'), { target: { value: 'Make it calmer' } })
    fireEvent.click(within(wizard).getByRole('button', { name: 'Preview change' }))
    expect(within(wizard).getByRole('button', { name: 'Creating preview…' })).toBeDisabled()
    expect(within(wizard).getByRole('status')).toHaveTextContent('Working on your preview')
    expect(within(wizard).getByRole('progressbar')).toHaveAttribute('aria-valuetext', 'In progress')
    expect(within(wizard).getByLabelText('What should change?')).toBeDisabled()
    release()
    expect(await within(wizard).findByText('New preview ready.')).toBeInTheDocument()
  })

  it('uses the bounded generation deadline for the five-post build', async () => {
    const client = api()
    render(<StudioView api={client as any} projectId={projectId} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Create 5 posts' }))
    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/sample-sets', { batch_id: batchId }, { deadlineMs: 7_200_000 }))
    expect(await screen.findByLabelText('Your five Studio posts')).toBeInTheDocument()
  })

  it('restores the newest saved preview directly into the simple review flow', async () => {
    const client = api(true, true)
    render(<StudioView api={client as any} projectId={projectId} />)
    const wizard = await screen.findByLabelText('AI wizard')
    expect(await within(wizard).findByText('New preview ready.')).toBeInTheDocument()
    expect(within(wizard).getByLabelText('What should change?')).toHaveValue('Move the headline away from the face')
    expect(await screen.findByAltText('Preview of proposed change')).toBeInTheDocument()
    expect(client.post).not.toHaveBeenCalled()
  })

  it('preserves the instruction and offers one retry when preview creation fails', async () => {
    const client = api(true)
    client.post.mockRejectedValueOnce(new Error('Wizard unavailable'))
    render(<StudioView api={client as any} projectId={projectId} />)
    const wizard = await screen.findByLabelText('AI wizard')
    const instruction = within(wizard).getByLabelText('What should change?')
    fireEvent.change(instruction, { target: { value: 'Use a stronger horoscope visual' } })
    fireEvent.click(within(wizard).getByRole('button', { name: 'Preview change' }))
    expect(await within(wizard).findByRole('alert')).toHaveTextContent('Wizard unavailable')
    expect(instruction).toHaveValue('Use a stronger horoscope visual')
    expect(within(wizard).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
