import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { StudioView } from './StudioView'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const briefId = '018f07ea-7f20-7000-8000-000000000002'
const kitId = '018f07ea-7f20-7000-8000-000000000003'
const batchId = '018f07ea-7f20-7000-8000-000000000004'
const now = '2026-08-25T12:00:00Z'

beforeAll(() => {
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:studio') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
})

const tool = (tool_id: string, kind: string, label: string, media = ['static', 'motion']) => ({
  tool_id, kind, label, parameter_schema: {}, supported_placements: media,
  renderer_handler: 'test', defaults: {}, bounds: {}, source_refs: ['https://example.test'], deprecated: false,
})
const frame = (tool_id: string, text: string, z_index: number) => ({
  instance_id: `018f07ea-7f20-7000-8000-00000000001${z_index}`, tool_id,
  frame: { x: .08, y: .1 + z_index * .2, width: .84, height: .16 }, z_index,
  params: { text, color: '#FFFFFF', font_size: tool_id.includes('headline') ? 72 : 36, font_weight: 800, line_height: 1.05, align: 'left', max_lines: 4 }, timeline: null, source_asset_ids: [],
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
  items: names.map((name, index) => ({ ordinal: index, angle: angles[index], name, template_id: `template-${index}`, recipe_id: recipe(index + 1).recipe_id, render_id: renderItem(index + 1).render_id, caption: `Real caption ${index + 1}`, alt_text: `Accessible post ${index + 1}`, template: { template_id: `template-${index}` }, recipe: recipe(index + 1), render: renderItem(index + 1) })),
}
const persistedProposal = {
  proposal_id: 'proposal-persisted', recipe_id: recipe(1).recipe_id, status: 'previewed',
  instruction: 'Move the headline away from the face', target_instance_id: null,
  patch: { frames: [{ op: 'replace', path: '/0/frame/x', value: .06 }] },
  before_sha256: '4'.repeat(64), after_sha256: '5'.repeat(64),
  preview_url: '/wizard/persisted-preview', preview_sha256: '6'.repeat(64),
  preview_mime_type: 'image/jpeg', created_at: now,
}

function api(withSamples = false, withRecoveredProposal = false) {
  const post = vi.fn(async (path: string, body: any) => {
    if (path === '/api/v1/ad-studio/sample-sets') return sampleSet
    if (path === '/api/v1/ad-studio/templates') return { template_id: 'template-new', project_id: projectId, name: body.name, placement_tool_id: body.document.placement_tool_id, document: body.document, document_sha256: 'a'.repeat(64), created_by: 'owner', created_at: now }
    if (path === '/api/v1/ad-studio/templates/template-new/apply') return { template_id: 'template-new', project_id: projectId, brief_id: body.brief_id, creative_id: body.creative_id, brand_kit_id: body.brand_kit_id, recipe: recipe(7), created: true }
    if (path === '/api/v1/ad-studio/recipes') return { ...recipe(8), document: body.document }
    if (path.endsWith('/wizard-proposals')) return { proposal_id: 'proposal-1', recipe_id: recipe(1).recipe_id, status: 'previewed', instruction: body.instruction, target_instance_id: body.target_instance_id, patch: { frames: [{ op: 'replace', path: '/0/params/font_size', value: 64 }] }, before_sha256: '1'.repeat(64), after_sha256: '2'.repeat(64), preview_url: '/wizard/preview', preview_sha256: '3'.repeat(64), preview_mime_type: 'image/jpeg', created_at: now }
    if (path === '/api/v1/ad-studio/wizard-proposals/proposal-1/apply') return { proposal: { proposal_id: 'proposal-1', recipe_id: recipe(1).recipe_id, status: 'applied', instruction: 'Make it calmer', patch: {}, before_sha256: '1'.repeat(64), after_sha256: '2'.repeat(64), preview_url: '/wizard/preview', applied_recipe_id: recipe(9).recipe_id, created_at: now }, recipe: recipe(9), render: renderItem(9) }
    throw new Error(`unexpected POST ${path}`)
  })
  return {
    get: vi.fn(async (path: string) => {
      if (path === '/api/v1/ad-studio/tools') return { items: [
        tool('studio.placement.instagram.feed_square.v1', 'placement', 'Square', ['static']), tool('studio.frame.media.v1', 'frame', 'Media'), tool('studio.frame.shape.v1', 'frame', 'Shape'), tool('studio.frame.logo.v1', 'frame', 'Logo'), tool('studio.frame.headline.v1', 'frame', 'Headline'), tool('studio.frame.body.v1', 'frame', 'Body'), tool('studio.frame.offer.v1', 'frame', 'Offer'), tool('studio.frame.cta.v1', 'frame', 'CTA'), tool('studio.layout.editorial_product_split.v1', 'layout', 'Split'), tool('studio.strategy.one_message.v1', 'strategy', 'One message'),
        ...['safe_zone', 'small_screen_hierarchy', 'contrast', 'brand_consistency', 'claim_integrity', 'source_lineage'].map((name) => tool(`studio.guard.${name}.v1`, 'guard', name)),
      ] }
      if (path.startsWith('/api/v1/briefs?')) return { items: [{ brief_id: briefId, project_id: projectId, project_name: 'Project', request_id: projectId, owner_idea_source_id: projectId, raw_idea: 'Idea', status: 'completed', approved: true, product: 'Product', promise: 'A clear promise', offer: 'Free consultation', cta: 'Book now', creative_batch_id: batchId, failure_count: 0, created_at: now }] }
      if (path.startsWith('/api/v1/ad-studio/brand-kits')) return { items: [{ brand_kit_id: kitId, project_id: projectId, document: { name: 'Natal', colors: ['#06090D', '#FFFFFF', '#00D8FF', '#59616C'], fonts: ['Inter'], tone_notes: '', logo_source_asset_id: null }, document_sha256: 'b'.repeat(64), created_by: 'owner', created_at: now }] }
      if (path.startsWith('/api/v1/ad-studio/templates')) return { items: [] }
      if (path.startsWith('/api/v1/ad-studio/sources')) return { items: [] }
      if (path.includes('/renders')) return { items: [renderItem(1)] }
      if (path.endsWith('/wizard-proposals')) return { items: withRecoveredProposal ? [persistedProposal] : [] }
      if (path.startsWith('/api/v1/ad-studio/recipes')) return { items: [] }
      if (path.startsWith('/api/v1/ad-studio/sample-sets')) return { items: withSamples ? [sampleSet] : [] }
      if (path === '/api/v1/skill-proposals/ad_studio') return { items: [] }
      throw new Error(`unexpected GET ${path}`)
    }), post, media: vi.fn(async () => new Blob(['image'], { type: 'image/jpeg' })),
  }
}

describe('StudioView', () => {
  it('keeps Preview clean and opens a dismissible side inspector in Edit mode', async () => {
    render(<StudioView api={api() as any} projectId={projectId} />)
    const canvas = await screen.findByLabelText('Constrained Ad Studio canvas')
    expect(within(canvas).queryByText('studio.frame.headline.v1')).not.toBeInTheDocument()
    expect(canvas.querySelector('.studio-safe-zone')).not.toBeInTheDocument()
    expect(canvas.querySelector('small, code, .studio-resize-handle')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    const frameButton = await within(canvas).findByRole('button', { name: 'studio.frame.headline.v1 frame' })
    fireEvent.pointerDown(frameButton, { pointerId: 1 }); fireEvent.pointerUp(frameButton, { pointerId: 1 })
    expect(canvas).toBeInTheDocument(); expect(screen.getByLabelText('Selected component inspector')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close component inspector' }))
    expect(screen.queryByLabelText('Selected component inspector')).not.toBeInTheDocument(); expect(canvas).toBeInTheDocument()
  })

  it('shows exactly five real share-ready sample cards and opens their caption and alt text', async () => {
    render(<StudioView api={api(true) as any} projectId={projectId} />)
    const gallery = await screen.findByLabelText('Five ready-to-share Studio posts')
    expect(within(gallery).getAllByRole('button', { name: /Open .* editable post/ })).toHaveLength(5)
    expect(within(gallery).getAllByRole('button', { name: /Download .* JPEG/ })).toHaveLength(5)
    expect(within(gallery).getByText('Вікно ясності')).toBeInTheDocument(); expect(within(gallery).getByText('Не загальний гороскоп')).toBeInTheDocument()
    fireEvent.click(within(gallery).getByRole('button', { name: 'Open Вікно ясності editable post' }))
    expect(await screen.findByLabelText('Caption')).toHaveValue('Real caption 1'); expect(screen.getByLabelText('Alt text')).toHaveValue('Accessible post 1')
  })

  it('saves a V2 reusable template with fresh frames and protected Brief bindings', async () => {
    const client = api(); render(<StudioView api={client as any} projectId={projectId} />)
    const name = await screen.findByPlaceholderText('e.g. Cinematic clarity'); fireEvent.change(name, { target: { value: 'Cinematic clarity' } }); fireEvent.click(screen.getByRole('button', { name: /Save current template/ }))
    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/templates', expect.anything()))
    const body = client.post.mock.calls.find(([path]) => path === '/api/v1/ad-studio/templates')?.[1]
    expect(body.document.schema_version).toBe(2); const offer = body.document.frames.find((item: any) => item.tool_id === 'studio.frame.offer.v1'); expect(offer.params.text).toBe('{{offer}}'); expect(body.document.frames.find((item: any) => item.tool_id === 'studio.frame.cta.v1').params.text).toBe('{{cta}}'); expect(body.document.bindings.offer).toEqual({ target: `/frames/${offer.instance_id}/params/text`, source: 'brief.offer' })
    fireEvent.click(screen.getByRole('button', { name: /Cinematic clarity/ })); await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/templates/template-new/apply', expect.objectContaining({ request_id: expect.any(String), brief_id: briefId, creative_id: null, brand_kit_id: kitId }), { deadlineMs: 300_000 }))
  })

  it('persists editable share copy and typography in a V2 recipe', async () => {
    const client = api(); render(<StudioView api={client as any} projectId={projectId} />)
    await screen.findByLabelText('Caption'); fireEvent.change(screen.getByLabelText('Caption'), { target: { value: 'Updated caption' } }); fireEvent.change(screen.getByLabelText('Alt text'), { target: { value: 'Updated alt' } }); fireEvent.click(screen.getByRole('button', { name: 'Edit' })); const headline = screen.getByRole('button', { name: 'studio.frame.headline.v1 frame' }); fireEvent.pointerDown(headline, { pointerId: 2 }); fireEvent.pointerUp(headline, { pointerId: 2 }); fireEvent.change(screen.getByLabelText('Font size'), { target: { value: '64' } }); fireEvent.click(screen.getByRole('button', { name: /Save version/ }))
    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/recipes', expect.anything()))
    const body = client.post.mock.calls.find(([path]) => path === '/api/v1/ad-studio/recipes')?.[1]
    expect(body.document.share).toEqual({ caption: 'Updated caption', alt_text: 'Updated alt' }); expect(body.document.frames.find((item: any) => item.tool_id === 'studio.frame.headline.v1').params.font_size).toBe(64)
  })

  it('reviews a targetable wizard diff before applying a new immutable recipe', async () => {
    const client = api(true); render(<StudioView api={client as any} projectId={projectId} />)
    const gallery = await screen.findByLabelText('Five ready-to-share Studio posts'); fireEvent.click(within(gallery).getByRole('button', { name: 'Open Вікно ясності editable post' })); const wizard = await screen.findByLabelText('AI wizard')
    fireEvent.change(within(wizard).getByLabelText('Instruction'), { target: { value: 'Make it calmer' } }); fireEvent.click(within(wizard).getByRole('button', { name: /Create review preview/ }))
    expect(await within(wizard).findByText('Review typed diff')).toBeInTheDocument(); expect(client.post).toHaveBeenCalledWith(expect.stringContaining('/wizard-proposals'), { instruction: 'Make it calmer', target_instance_id: null }, { deadlineMs: 600_000 })
    expect(within(wizard).getByText('Preview ready — nothing changed yet.')).toBeInTheDocument()
    fireEvent.click(within(wizard).getByRole('button', { name: /Apply preview as new version/ })); await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/wizard-proposals/proposal-1/apply', {}, { deadlineMs: 600_000 }))
  })

  it('shows durable, honest progress while the wizard request is running', async () => {
    const client = api(true)
    const post = client.post.getMockImplementation()!
    let release = () => {}
    client.post.mockImplementation(async (path: string, body: any) => {
      if (path.endsWith('/wizard-proposals')) await new Promise<void>((resolve) => { release = resolve })
      return post(path, body)
    })
    render(<StudioView api={client as any} projectId={projectId} />)
    const gallery = await screen.findByLabelText('Five ready-to-share Studio posts')
    fireEvent.click(within(gallery).getByRole('button', { name: 'Open Вікно ясності editable post' }))
    const wizard = await screen.findByLabelText('AI wizard')
    expect(within(wizard).getByLabelText('Scope')).toHaveValue('post')
    expect(within(wizard).getByText('This revises only the post open above. The other four posts and your saved templates stay unchanged.')).toBeInTheDocument()
    fireEvent.change(within(wizard).getByLabelText('Instruction'), { target: { value: 'Make it calmer' } })
    fireEvent.click(within(wizard).getByRole('button', { name: /Create review preview/ }))
    expect(within(wizard).getByRole('button', { name: /Creating preview/ })).toBeDisabled()
    expect(within(wizard).getByRole('status')).toHaveTextContent('Creating your review preview')
    expect(within(wizard).getByRole('progressbar')).toHaveAttribute('aria-valuetext', 'In progress')
    expect(within(wizard).getByLabelText('Instruction')).toBeDisabled()
    release()
    expect(await within(wizard).findByText('Preview ready — nothing changed yet.')).toBeInTheDocument()
  })

  it('uses the bounded generation deadline for the five-post build', async () => {
    const client = api(); render(<StudioView api={client as any} projectId={projectId} />)
    fireEvent.click(await screen.findByRole('button', { name: /Generate 5 editable posts/ }))
    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/api/v1/ad-studio/sample-sets', { batch_id: batchId }, { deadlineMs: 300_000 }))
  })

  it('restores the newest persisted wizard preview when a recipe is reopened after reload', async () => {
    const client = api(true, true); render(<StudioView api={client as any} projectId={projectId} />)
    const gallery = await screen.findByLabelText('Five ready-to-share Studio posts'); fireEvent.click(within(gallery).getByRole('button', { name: 'Open Вікно ясності editable post' }))
    const wizard = await screen.findByLabelText('AI wizard')
    expect(await within(wizard).findByText('Review typed diff')).toBeInTheDocument()
    expect(within(wizard).getByLabelText('Instruction')).toHaveValue('Move the headline away from the face')
    expect(client.get).toHaveBeenCalledWith(`/api/v1/ad-studio/recipes/${recipe(1).recipe_id}/wizard-proposals`)
    expect(client.post).not.toHaveBeenCalled()
  })
})
