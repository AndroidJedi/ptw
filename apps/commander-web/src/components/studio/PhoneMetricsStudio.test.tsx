import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../../api'
import type { StudioPhoneMetricsDetail } from '../../types'
import { PhoneMetricsStudio } from './PhoneMetricsStudio'

const detail = {
  schema: 'ptw.studio.workspace.v6',
  template_id: 'phone_metrics',
  templates: [
    {
      template_id: 'phone_metrics', name: 'Phone & metrics',
      description: 'Phone composition', canvas: { width: 1080, height: 1350 },
    },
  ],
  catalog: {
    schema: 'ptw.studio.phone-metrics-catalog.v1', template_id: 'phone_metrics',
    template_version: 10, canvas: { width: 1080, height: 1350 },
    semantic_roles: [], components: [], asset_slots: {},
    variation: {
      optional_elements: ['offer'], brand: 'Natal',
      device_pose: 'front_facing_upright', device_rotation_degrees: 0,
      background_textures: ['none', 'grain', 'concrete', 'travertine'],
      copy_background_textures: ['none', 'grain', 'concrete', 'travertine'],
      phone_screen_textures: ['none', 'grain', 'paper', 'frosted'],
      supporting_text_font_size: { minimum: 20, maximum: 38, default: 29 },
    },
    sha256: 'b'.repeat(64),
  },
  state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
  configuration: {
    schema: 'ptw.studio.phone-metrics-config.v5',
    background: { color: '#F4F5F2', texture: 'concrete', texture_intensity: 0.13 },
    copy_background: { texture: 'none' },
    offer: { enabled: true },
    supporting_text: { font_size: 29, highlight_color: '#1675F8' },
    phone_screen: { texture: 'grain' },
    device: { x: 610, y: 90, width: 410, rotation: 0 },
  },
  content: {
    schema: 'ptw.studio.phone-metrics-content.v1', offer: 'NATAL',
    hero_title: 'Ваш головний меседж тут',
    supporting_text: 'Коротке пояснення.', cta: 'ДІЗНАТИСЯ БІЛЬШЕ',
    stats: [
      { value: '1', label: 'перша' },
      { value: '2', label: 'друга' },
      { value: '3', label: 'третя' },
    ],
    phone_hero_title: '',
  },
  component_settings: { sha256: 'd'.repeat(64) }, assets: [],
  pexels_available: false, versions: [],
} as unknown as StudioPhoneMetricsDetail

function studioApi() {
  const post = vi.fn(async (_path: string, body: unknown) => {
    const request = body as {
      configuration: StudioPhoneMetricsDetail['configuration']
      content: StudioPhoneMetricsDetail['content']
    }
    return {
      ...structuredClone(detail), state_sha256: 'e'.repeat(64),
      configuration: structuredClone(request.configuration),
      content: structuredClone(request.content),
    }
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
})
