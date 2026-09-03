import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../../api'
import type { StudioPhoneMetricsDetail } from '../../types'
import { PhoneMetricsStudio } from './PhoneMetricsStudio'

const detail = {
  schema: 'ptw.studio.workspace.v7',
  template_id: 'phone_metrics',
  templates: [
    {
      template_id: 'phone_metrics', name: 'Phone & metrics',
      description: 'Phone composition', canvas: { width: 1080, height: 1350 },
    },
  ],
  catalog: {
    schema: 'ptw.studio.phone-metrics-catalog.v1', template_id: 'phone_metrics',
    template_version: 15, canvas: { width: 1080, height: 1350 },
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
      supporting_text_font_size: { minimum: 20, maximum: 38, default: 29 },
    },
    sha256: 'b'.repeat(64),
  },
  state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
  configuration: {
    schema: 'ptw.studio.phone-metrics-config.v7',
    background: { color: '#F4F5F2', texture: 'concrete', texture_intensity: 0.13 },
    copy_background: { texture: 'none' },
    offer: { enabled: true },
    supporting_text: { font_size: 29, highlight_color: '#1675F8' },
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
  component_settings: { sha256: 'd'.repeat(64) }, assets: [],
  pexels_available: false, phone_screen_generation_available: true, versions: [],
} as unknown as StudioPhoneMetricsDetail

function studioApi() {
  let savedDetail = structuredClone(detail)
  const post = vi.fn(async (path: string, body: unknown) => {
    if (path === '/api/v1/studio/phone-screen/generate') {
      savedDetail = {
        ...savedDetail, state_sha256: 'f'.repeat(64),
        assets: [{
          slot: 'phone_screen', role: 'device_screen',
          description: 'Generated phone hero', allowed_mime_types: ['image/png'],
          editable: false, available: true, mime_type: 'image/png',
          sha256: '1'.repeat(64), byte_count: 128,
          source: { visual_direction: (body as { visual_direction: string }).visual_direction },
        }],
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
    return structuredClone(savedDetail)
  })
  return {
    api: {
      post,
      postMedia: vi.fn().mockResolvedValue(new Blob(['preview'], { type: 'image/png' })),
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
      api={api} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    expect(screen.getByLabelText('Show eyebrow')).toBeChecked()
    expect(screen.getByLabelText('Eyebrow')).toHaveValue('NATAL')
    fireEvent.click(screen.getByLabelText('Show eyebrow'))

    expect(screen.getByText('Eyebrow removed')).toBeInTheDocument()
    expect(screen.queryByLabelText('Eyebrow')).not.toBeInTheDocument()
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        state_sha256: 'a'.repeat(64),
        configuration: expect.objectContaining({ offer: { enabled: false } }),
        content: expect.objectContaining({ offer: 'NATAL' }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/configuration',
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
      api={api} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

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
    fireEvent.change(screen.getByLabelText('Highlight color'), {
      target: { value: '#d12f7a' },
    })

    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        configuration: expect.objectContaining({
          supporting_text: { font_size: 36, highlight_color: '#D12F7A' },
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
      api={api} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
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
      '/api/v1/studio/preview',
      expect.objectContaining({
        configuration: expect.objectContaining({
          background: expect.objectContaining({ texture: 'travertine' }),
          copy_background: { texture: 'concrete' },
          phone_screen: { texture: 'frosted' },
        }),
      }),
      'image/png', { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/configuration',
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
      api={api} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
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
      '/api/v1/studio/preview',
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

    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/configuration',
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
      api={api} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
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
      '/api/v1/studio/preview',
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

    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/configuration',
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
      api={api} language="en" detail={structuredClone(detail)} onDetail={vi.fn()}
    />)

    fireEvent.change(screen.getByLabelText('Headline'), {
      target: { value: 'A newly edited headline' },
    })
    fireEvent.change(screen.getByLabelText('iPhone visual direction'), {
      target: { value: 'Translucent glass steps in soft blue light with one lime accent.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Generate & apply' }))

    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      1, '/api/v1/studio/configuration',
      expect.objectContaining({ content: expect.objectContaining({ hero_title: 'A newly edited headline' }) }),
      { deadlineMs: 60_000 },
    ))
    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      2, '/api/v1/studio/phone-screen/generate', {
        base_sha256: 'e'.repeat(64),
        visual_direction: 'Translucent glass steps in soft blue light with one lime accent.',
      }, { deadlineMs: 360_000 },
    ))
    expect(await screen.findByText('New iPhone hero visual generated and applied.')).toBeInTheDocument()
  })

  it('keeps generation disabled and explains the deterministic fallback without a provider', () => {
    const unavailable = structuredClone(detail)
    unavailable.phone_screen_generation_available = false
    const { api } = studioApi()
    render(<PhoneMetricsStudio
      api={api} language="en" detail={unavailable} onDetail={vi.fn()}
    />)

    fireEvent.change(screen.getByLabelText('iPhone visual direction'), {
      target: { value: 'Translucent glass steps in soft blue light with one lime accent.' },
    })
    expect(screen.getByRole('button', { name: 'Generate & apply' })).toBeDisabled()
    expect(screen.getByText(/Sign in to Codex and restart Studio/)).toBeInTheDocument()
  })
})
