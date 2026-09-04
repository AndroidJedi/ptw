import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../../api'
import type { StudioPhoneMetricsDetail } from '../../types'
import { PhoneMetricsStudio } from './PhoneMetricsStudio'

const basePath = '/api/v1/studio/projects/11111111-1111-4111-8111-111111111111/creatives/22222222-2222-4222-8222-222222222222'

const detail = {
  creative_id: '22222222-2222-4222-8222-222222222222',
  project_id: '11111111-1111-4111-8111-111111111111',
  source_brief_id: '33333333-3333-4333-8333-333333333333',
  ordinal: 1,
  origin: 'brief_generation',
  status: 'draft',
  generation: { stage: 'draft' },
  approved_version_count: 0,
  schema: 'ptw.studio.workspace.v8',
  template_id: 'phone_metrics',
  templates: [
    {
      template_id: 'phone_metrics', name: 'Phone & metrics',
      description: 'Phone composition', canvas: { width: 1080, height: 1350 },
    },
  ],
  catalog: {
    schema: 'ptw.studio.phone-metrics-catalog.v2', template_id: 'phone_metrics',
    template_version: 22, canvas: { width: 1080, height: 1350 },
    semantic_roles: [], components: [], asset_slots: {},
    variation: {
      optional_elements: ['offer'], brand: 'Natal',
      device_pose: 'front_facing_upright', device_rotation_degrees: 0,
      background_textures: ['none', 'grain', 'concrete', 'travertine'],
      copy_background_textures: ['none', 'grain', 'concrete', 'travertine'],
      phone_screen_textures: ['none', 'grain', 'paper', 'frosted'],
      metric_card_styles: ['filled', 'outlined'],
      metric_card_shapes: ['square', 'rounded', 'pill'],
      phone_button_styles: ['filled', 'elevated', 'outlined', 'text'],
      phone_button_shapes: ['square', 'rounded', 'pill'],
      font_families: ['Inter', 'Roboto Condensed', 'Manrope', 'Montserrat', 'Source Sans 3', 'Oswald', 'Cormorant Garamond', 'Cormorant Garamond Italic', 'Lora', 'Lora Italic'],
      typography: {
        offer: { minimum: 16, maximum: 42, default: 23 },
        hero_title: { minimum: 42, maximum: 110, default: 76 },
        supporting_text: { minimum: 20, maximum: 46, default: 29 },
        cta: { minimum: 20, maximum: 52, default: 34 },
        metric_value: { minimum: 20, maximum: 56, default: 43 },
        metric_label: { minimum: 14, maximum: 36, default: 22 },
        phone_title: { minimum: 24, maximum: 72, default: 55 },
        phone_buttons: { minimum: 16, maximum: 36, default: 28 },
      },
    },
    sha256: 'b'.repeat(64),
  },
  state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
  configuration: {
    schema: 'ptw.studio.phone-metrics-config.v8',
    background: { color: '#F4F5F2', texture: 'concrete', texture_intensity: 0.13 },
    copy_background: { texture: 'none' },
    offer: { enabled: true },
    supporting_text: { highlight_color: '#1675F8' },
    typography: {
      offer: { font_family: 'Manrope', font_size: 23 },
      hero_title: { font_family: 'Manrope', font_size: 76 },
      supporting_text: { font_family: 'Manrope', font_size: 29 },
      cta: { font_family: 'Manrope', font_size: 34 },
      metric_value: { font_family: 'Manrope', font_size: 43 },
      metric_label: { font_family: 'Manrope', font_size: 22 },
      phone_title: { font_family: 'Manrope', font_size: 55 },
      phone_buttons: { font_family: 'Manrope', font_size: 28 },
    },
    phone_screen: { texture: 'grain' },
    metric_cards: [1, 2, 3].map(() => ({
      style: 'filled' as const, text_color: '#FFFFFF',
      background_color: '#2457C8', shape: 'rounded' as const,
    })),
    phone_buttons: [
      { style: 'filled', text_color: '#FFFFFF', background_color: '#1675F8', shape: 'pill' },
      { style: 'elevated', text_color: '#1675F8', background_color: '#FFFFFF', shape: 'pill' },
      { style: 'text', text_color: '#1675F8', background_color: '#FFFFFF', shape: 'pill' },
    ],
    device: { x: 610, y: 90, width: 410, rotation: 0 },
  },
  content: {
    schema: 'ptw.studio.phone-metrics-content.v2', offer: 'NATAL',
    hero_title: 'Ваш головний меседж тут',
    supporting_text: 'Коротке пояснення.', cta: 'ДІЗНАТИСЯ БІЛЬШЕ',
    stats: [
      { value: '1', label: 'перша' },
      { value: '2', label: 'друга' },
      { value: '3', label: 'третя' },
    ],
    phone_hero_title: '',
    phone_buttons: ['Створити новий акаунт', 'Увійти', 'Можливо пізніше'],
  },
  component_settings: { sha256: 'd'.repeat(64) }, assets: [], phone_screen_history: [],
  pexels_available: false, phone_screen_generation_available: true, versions: [],
} as unknown as StudioPhoneMetricsDetail

function studioApi(initialDetail: StudioPhoneMetricsDetail = detail) {
  let savedDetail = structuredClone(initialDetail)
  const post = vi.fn(async (path: string, body: unknown) => {
    if (path === `${basePath}/phone-screen/generate`) {
      const generatedSha256 = '1'.repeat(64)
      const generatedSource = {
        visual_direction: (body as { visual_direction: string }).visual_direction,
        generation_mode: (body as { enhance_current: boolean }).enhance_current ? 'enhance_current' : 'generate_new',
      }
      savedDetail = {
        ...savedDetail, state_sha256: 'f'.repeat(64),
        assets: [{
          slot: 'phone_screen', role: 'device_screen',
          description: 'Generated phone hero', allowed_mime_types: ['image/png'],
          editable: false, available: true, mime_type: 'image/png',
          sha256: generatedSha256, byte_count: 128, source: generatedSource,
        }],
        phone_screen_history: [{
          mime_type: 'image/png' as const, sha256: generatedSha256,
          width: 1024, height: 1024, byte_count: 128,
          source: generatedSource, selected: true,
        }, ...savedDetail.phone_screen_history.filter((item) => item.sha256 !== generatedSha256)
          .map((item) => ({ ...item, selected: false }))].slice(0, 3),
      }
      return structuredClone(savedDetail)
    }
    if (path === `${basePath}/phone-screen/select`) {
      const sha256 = (body as { sha256: string }).sha256
      const selected = savedDetail.phone_screen_history.find((item) => item.sha256 === sha256)
      savedDetail = {
        ...savedDetail, state_sha256: '9'.repeat(64),
        assets: savedDetail.assets.map((asset) => asset.slot === 'phone_screen' && selected
          ? { ...asset, sha256: selected.sha256, source: selected.source }
          : asset),
        phone_screen_history: savedDetail.phone_screen_history.map((item) => ({
          ...item, selected: item.sha256 === sha256,
        })),
      }
      return structuredClone(savedDetail)
    }
    const request = body as {
      configuration: StudioPhoneMetricsDetail['configuration']
      content: StudioPhoneMetricsDetail['content']
    }
    savedDetail = {
      ...savedDetail, state_sha256: 'e'.repeat(64),
      configuration: structuredClone(request.configuration),
      content: structuredClone(request.content),
    }
    if (path === `${basePath}/save` || path === `${basePath}/approve`) return {
      creative: structuredClone(savedDetail), checkpoint_created: true,
      version_created: path.endsWith('/approve'), checkpoint: null, learning_proposal: null,
    }
    return structuredClone(savedDetail)
  })
  return {
    api: {
      post,
      postMedia: vi.fn().mockResolvedValue(new Blob(['preview'], { type: 'image/png' })),
      media: vi.fn().mockResolvedValue(new Blob(['history'], { type: 'image/png' })),
    } as unknown as ApiClient,
    post,
  }
}

describe('Phone & metrics Studio', () => {
  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true, value: vi.fn(() => 'blob:phone-preview'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true, value: vi.fn(),
    })
  })

  it('removes the eyebrow control from the draft while preserving its copy', async () => {
    const { api, post } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    expect(screen.getByLabelText('Show eyebrow')).toBeChecked()
    expect(screen.getByLabelText('Eyebrow')).toHaveValue('NATAL')
    fireEvent.click(screen.getByLabelText('Show eyebrow'))

    expect(screen.getByText('Eyebrow removed')).toBeInTheDocument()
    expect(screen.queryByLabelText('Eyebrow')).not.toBeInTheDocument()
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      `${basePath}/preview`,
      expect.objectContaining({
        state_sha256: 'a'.repeat(64),
        configuration: expect.objectContaining({ offer: { enabled: false } }),
        content: expect.objectContaining({ offer: 'NATAL' }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByRole('button', { name: 'Save creative' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `${basePath}/save`,
      expect.objectContaining({
        configuration: expect.objectContaining({ offer: { enabled: false } }),
        content: expect.objectContaining({ offer: 'NATAL' }),
      }),
      { deadlineMs: 60_000 },
    ))
  })

  it('formats selected supporting words and previews size and colour controls', async () => {
    const { api } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    for (const role of [
      'Eyebrow', 'Headline', 'Supporting text', 'CTA', 'Metric values',
      'Metric labels', 'In-phone title', 'In-phone buttons',
    ]) {
      expect(screen.getByLabelText(`${role} font family`)).toBeInTheDocument()
      expect(screen.getByLabelText(`${role} font size`)).toBeInTheDocument()
    }

    const supporting = screen.getByLabelText('Supporting text') as HTMLTextAreaElement
    supporting.focus()
    supporting.setSelectionRange(0, 'Коротке'.length)
    fireEvent.click(screen.getByRole('button', { name: 'Bold selected words' }))
    expect(supporting).toHaveValue('**Коротке** пояснення.')

    const colourStart = supporting.value.indexOf('пояснення')
    supporting.setSelectionRange(colourStart, colourStart + 'пояснення'.length)
    fireEvent.click(screen.getByRole('button', { name: 'Highlight selected words' }))
    expect(supporting).toHaveValue('**Коротке** ==пояснення==.')

    fireEvent.change(screen.getByLabelText('Supporting text font size'), {
      target: { value: '36' },
    })
    fireEvent.change(screen.getByLabelText('Supporting text font family'), {
      target: { value: 'Source Sans 3' },
    })
    fireEvent.change(screen.getByLabelText('Highlight color'), {
      target: { value: '#d12f7a' },
    })

    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      `${basePath}/preview`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          supporting_text: { highlight_color: '#D12F7A' },
          typography: expect.objectContaining({
            supporting_text: { font_family: 'Source Sans 3', font_size: 36 },
          }),
        }),
        content: expect.objectContaining({
          supporting_text: '**Коротке** ==пояснення==.',
        }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))
  })

  it('previews and saves independent full, left-copy, and iPhone textures', async () => {
    const { api, post } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    fireEvent.change(screen.getByLabelText('Full post background texture'), {
      target: { value: 'travertine' },
    })
    fireEvent.change(screen.getByLabelText('Left copy area texture'), {
      target: { value: 'concrete' },
    })
    fireEvent.change(screen.getByLabelText('iPhone screen texture'), {
      target: { value: 'frosted' },
    })

    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      `${basePath}/preview`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          background: expect.objectContaining({ texture: 'travertine' }),
          copy_background: { texture: 'concrete' },
          phone_screen: { texture: 'frosted' },
        }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByRole('button', { name: 'Save creative' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `${basePath}/save`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          background: expect.objectContaining({ texture: 'travertine' }),
          copy_background: { texture: 'concrete' },
          phone_screen: { texture: 'frosted' },
        }),
      }),
      { deadlineMs: 60_000 },
    ))
  })

  it('previews and saves each metric button text, style, colours, and shape', async () => {
    const { api, post } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    expect(screen.getByLabelText('Metric 1 style')).toHaveValue('filled')
    expect(screen.getByLabelText('Metric 1 shape')).toHaveValue('rounded')
    expect(screen.getByLabelText('Metric 1 text color')).toHaveValue('#ffffff')
    expect(screen.getByLabelText('Metric 1 background color')).toHaveValue('#2457c8')

    fireEvent.change(screen.getByLabelText('Metric 1 value'), {
      target: { value: '42%' },
    })
    fireEvent.change(screen.getByLabelText('Metric 1 label'), {
      target: { value: 'conversion' },
    })
    fireEvent.change(screen.getByLabelText('Metric 1 style'), {
      target: { value: 'outlined' },
    })
    fireEvent.change(screen.getByLabelText('Metric 1 shape'), {
      target: { value: 'pill' },
    })
    fireEvent.change(screen.getByLabelText('Metric 1 text color'), {
      target: { value: '#101b31' },
    })
    fireEvent.change(screen.getByLabelText('Metric 1 background color'), {
      target: { value: '#cedd3c' },
    })

    const expectedCard = {
      style: 'outlined', text_color: '#101B31',
      background_color: '#CEDD3C', shape: 'pill',
    }
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      `${basePath}/preview`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          metric_cards: [expectedCard, expect.any(Object), expect.any(Object)],
        }),
        content: expect.objectContaining({
          stats: [
            { value: '42%', label: 'conversion' },
            expect.any(Object), expect.any(Object),
          ],
        }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByRole('button', { name: 'Save creative' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `${basePath}/save`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          metric_cards: [expectedCard, expect.any(Object), expect.any(Object)],
        }),
        content: expect.objectContaining({
          stats: [
            { value: '42%', label: 'conversion' },
            expect.any(Object), expect.any(Object),
          ],
        }),
      }),
      { deadlineMs: 60_000 },
    ))
  })

  it('previews and saves all in-phone bottom-button controls', async () => {
    const { api, post } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    expect(screen.getByLabelText('Phone button 1 style')).toHaveValue('filled')
    expect(screen.getByLabelText('Phone button 2 style')).toHaveValue('elevated')
    expect(screen.getByLabelText('Phone button 3 style')).toHaveValue('text')
    expect(screen.getByLabelText('Phone button 2 shape')).toHaveValue('pill')

    fireEvent.change(screen.getByLabelText('Phone button 2 text'), {
      target: { value: 'Sign in now' },
    })
    fireEvent.change(screen.getByLabelText('Phone button 2 style'), {
      target: { value: 'outlined' },
    })
    fireEvent.change(screen.getByLabelText('Phone button 2 shape'), {
      target: { value: 'rounded' },
    })
    fireEvent.change(screen.getByLabelText('Phone button 2 text color'), {
      target: { value: '#101b31' },
    })
    fireEvent.change(screen.getByLabelText('Phone button 2 background color'), {
      target: { value: '#cedd3c' },
    })

    const expectedButton = {
      style: 'outlined', text_color: '#101B31',
      background_color: '#CEDD3C', shape: 'rounded',
    }
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      `${basePath}/preview`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          phone_buttons: [expect.any(Object), expectedButton, expect.any(Object)],
        }),
        content: expect.objectContaining({
          phone_buttons: ['Створити новий акаунт', 'Sign in now', 'Можливо пізніше'],
        }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByRole('button', { name: 'Save creative' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `${basePath}/save`,
      expect.objectContaining({
        configuration: expect.objectContaining({
          phone_buttons: [expect.any(Object), expectedButton, expect.any(Object)],
        }),
        content: expect.objectContaining({
          phone_buttons: ['Створити новий акаунт', 'Sign in now', 'Можливо пізніше'],
        }),
      }),
      { deadlineMs: 60_000 },
    ))
  })

  it('saves draft copy before generating and applying a new iPhone visual', async () => {
    const { api, post } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    fireEvent.change(screen.getByLabelText('Headline'), {
      target: { value: 'A newly edited headline' },
    })
    fireEvent.change(screen.getByLabelText('iPhone visual direction'), {
      target: { value: 'Translucent glass steps in soft blue light with one lime accent.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Generate & apply' }))

    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      1, `${basePath}/configuration`,
      expect.objectContaining({ content: expect.objectContaining({ hero_title: 'A newly edited headline' }) }),
      { deadlineMs: 60_000 },
    ))
    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      2, `${basePath}/phone-screen/generate`, {
        base_sha256: 'e'.repeat(64),
        visual_direction: 'Translucent glass steps in soft blue light with one lime accent.',
        enhance_current: false,
      }, { deadlineMs: 360_000 },
    ))
    expect(await screen.findByText('New iPhone hero visual generated and applied.')).toBeInTheDocument()
    expect(screen.getByLabelText('Enhance current image')).toBeChecked()
  })

  it('enhances the current raw iPhone hero by default when one is available', async () => {
    const current = structuredClone(detail)
    current.assets = [{
      slot: 'phone_screen', role: 'device_screen', description: 'Current phone hero',
      allowed_mime_types: ['image/png'], editable: false, available: true,
      mime_type: 'image/png', sha256: '9'.repeat(64), byte_count: 128,
      source: { visual_direction: 'A colorful unicorn balloon on a soft field.' },
    }]
    const { api, post } = studioApi(current)
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={current} onDetail={vi.fn()}
    />)

    const enhance = screen.getByLabelText('Enhance current image')
    expect(enhance).toBeEnabled()
    expect(enhance).toBeChecked()
    fireEvent.change(screen.getByLabelText('iPhone visual direction'), {
      target: { value: 'Keep the unicorn and improve the balloon material and lighting.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Generate & apply' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `${basePath}/phone-screen/generate`, {
        base_sha256: 'a'.repeat(64),
        visual_direction: 'Keep the unicorn and improve the balloon material and lighting.',
        enhance_current: true,
      }, { deadlineMs: 360_000 },
    ))
    expect(await screen.findByText('Current iPhone hero visual enhanced and applied.')).toBeInTheDocument()
  })

  it('shows the last three raw heroes and applies the selected image', async () => {
    const current = structuredClone(detail)
    current.assets = [{
      slot: 'phone_screen', role: 'device_screen', description: 'Current phone hero',
      allowed_mime_types: ['image/png'], editable: false, available: true,
      mime_type: 'image/png', sha256: '1'.repeat(64), byte_count: 128,
      source: { visual_direction: 'Direction 1' },
    }]
    current.phone_screen_history = [1, 2, 3].map((position) => ({
      mime_type: 'image/png' as const,
      sha256: String(position).repeat(64), width: 1024, height: 1024, byte_count: 128,
      source: { visual_direction: `Direction ${position}` }, selected: position === 1,
    }))
    const { api, post } = studioApi(current)
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={current} onDetail={vi.fn()}
    />)

    expect(screen.getByRole('radiogroup', { name: 'Recent iPhone images' })).toBeInTheDocument()
    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByRole('radio', { name: 'iPhone image 1, current' })).toHaveAttribute('aria-checked', 'true')
    await waitFor(() => expect(api.media).toHaveBeenCalledTimes(3))

    fireEvent.change(screen.getByLabelText('Headline'), {
      target: { value: 'Keep this pending headline' },
    })
    fireEvent.click(screen.getByRole('radio', { name: 'Select iPhone image 2' }))
    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      1, `${basePath}/configuration`,
      expect.objectContaining({
        content: expect.objectContaining({ hero_title: 'Keep this pending headline' }),
      }),
      { deadlineMs: 60_000 },
    ))
    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      2, `${basePath}/phone-screen/select`,
      { base_sha256: 'e'.repeat(64), sha256: '2'.repeat(64) },
      { deadlineMs: 60_000 },
    ))
    expect(await screen.findByText('Selected iPhone image applied.')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'iPhone image 2, current' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByLabelText('iPhone visual direction')).toHaveValue('Direction 2')
    expect(screen.getByLabelText('Enhance current image')).toBeChecked()
  })

  it('keeps generation disabled and explains the deterministic fallback without a provider', () => {
    const unavailable = structuredClone(detail)
    unavailable.phone_screen_generation_available = false
    const { api } = studioApi()
    render(<PhoneMetricsStudio
      api={api} basePath={basePath} language="en" detail={unavailable} onDetail={vi.fn()}
    />)

    fireEvent.change(screen.getByLabelText('iPhone visual direction'), {
      target: { value: 'Translucent glass steps in soft blue light with one lime accent.' },
    })
    expect(screen.getByLabelText('Enhance current image')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Generate & apply' })).toBeDisabled()
    expect(screen.getByText(/Sign in to Codex and restart the Post editor/)).toBeInTheDocument()
  })
})
