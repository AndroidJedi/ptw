import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { StudioTuneRun, StudioUniversalDetail } from '../types'
import { StudioView } from './StudioView'

const componentRoles = [
  ['background', ['canvas', 'background_media', 'readability_overlay'], ['background_image']],
  ['sticker', ['sticker_object'], ['sticker_object']],
  ['hero_title', ['hero_title'], []],
  ['supporting_text', ['supporting_text'], []],
  ['offer', ['offer'], []],
  ['bullet_list', ['bullet_marker_1', 'bullet_1', 'bullet_marker_2', 'bullet_2', 'bullet_marker_3', 'bullet_3'], []],
  ['cta', ['cta'], []],
  ['logo', ['logo'], ['logo']],
] as const

const componentDefinitions = componentRoles.map(([role, nodeIds, assetSlotIds]) => ({
  component_id: `universal_ad.${role}`,
  role,
  node_ids: [...nodeIds],
  asset_slot_ids: [...assetSlotIds],
  setting_ids: [`configuration.${role}.enabled`],
}))

const detail: StudioUniversalDetail = {
  schema: 'ptw.studio.universal-ad-workspace.v5',
  catalog: {
    schema: 'ptw.studio.universal-ad-catalog.v5',
    template_id: 'universal_ad', template_version: 11,
    semantic_roles: ['background', 'sticker', 'hero_title', 'supporting_text', 'offer', 'bullet_list', 'cta', 'logo'],
    components: componentDefinitions,
    asset_slots: {},
    variation: {
      background_modes: ['solid', 'texture', 'image'], image_layouts: ['full', 'left', 'right', 'top', 'bottom'],
      image_percents: [25, 75],
      texture_presets: ['grain', 'stone', 'marble', 'concrete', 'granite', 'slate', 'travertine'],
      bullet_styles: ['check', 'circle', 'circle_outline'],
      cta_styles: ['filled', 'gradient', 'reverse', 'link', 'outlined'],
      cta_positions: ['below_text', 'bottom_left', 'bottom_right'],
      cta_font_size: { minimum: 18, maximum: 42, default: 27 },
      sticker_positions: ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'right_edge', 'bottom_edge', 'bullet_list', 'hero_title', 'cta'],
      font_families: ['Inter', 'Manrope', 'Oswald', 'Cormorant Garamond'],
      optional_elements: ['sticker', 'bullet_list', 'logo'],
    },
    sha256: 'b'.repeat(64),
  },
  state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
  configuration: {
    schema: 'ptw.studio.universal-ad-config.v5',
    background: {
      mode: 'image', color: '#10233F', texture: 'stone', texture_intensity: 0.7,
      image_layout: 'full', image_percent: 75, image_fit: 'cover',
      focal_x: 0.5, focal_y: 0.5, overlay_color: '#07182E', overlay_opacity: 0.56,
    },
    typography: {
      font_family: 'Inter', benefits_font_family: 'Manrope',
      hero_size: 94, hero_weight: 800, supporting_size: 30,
      text_color: '#FFFFFF', alignment: 'left',
    },
    layout: { content_x: 76, content_y: 128, content_width: 650, gap: 20 },
    bullets: { enabled: true, style: 'check' },
    cta: {
      style: 'filled', position: 'below_text', background_color: '#FFD84D',
      text_color: '#10233F', radius: 24, font_size: 27,
    },
    sticker: {
      enabled: true, position: 'bottom_right', rotation: 5, width: 300,
      object_scale: 0.9, offset_right: 0, offset_bottom: 0,
    },
    logo: {
      enabled: true, position: 'top_right', width: 180,
      background_enabled: false, background_color: '#FFFFFF',
    },
  },
  content: {
    schema: 'ptw.studio.universal-ad-content.v2',
    hero_title: 'ІНВЕСТУВАТИ В УКРАЇНІ — ПРОСТІШЕ',
    supporting_text: 'Аналізуємо ваші цілі й підказуємо інструменти, що відповідають саме вам.',
    offer: 'Безкоштовна 15-хвилинна консультація',
    bullets: ['Персональний підбір інструментів', 'Зрозуміле порівняння ризику', 'Наступний крок без зайвого шуму'],
    cta: 'ЗНАЙТИ СВОЄ',
  },
  component_settings: {
    schema: 'ptw.studio.universal-ad-component-settings.v2',
    template_id: 'universal_ad', template_version: 11,
    configuration_schema: 'ptw.studio.universal-ad-config.v5',
    components: componentDefinitions.map(({ setting_ids, ...component }) => ({
      ...component,
      settings: setting_ids.map((setting_id) => ({ setting_id, value: true })),
    })),
    sha256: '9'.repeat(64),
  },
  assets: [
    {
      slot: 'background_image', role: 'background', description: 'Background',
      allowed_mime_types: ['image/jpeg', 'image/png', 'image/webp'], available: true,
      mime_type: 'image/png', sha256: 'f'.repeat(64), byte_count: 1000,
      source: { origin: 'pexels', provider: 'pexels', external_id: '4100' },
    },
    {
      slot: 'sticker_object', role: 'sticker', description: 'Sticker',
      allowed_mime_types: ['image/png', 'image/webp'], available: true,
      mime_type: 'image/png', sha256: 'e'.repeat(64), byte_count: 1000,
      source: {
        origin: 'pexels', provider: 'pexels', external_id: '4101',
        transformation: 'edge_color_soft_alpha_v1',
      },
    },
    {
      slot: 'logo', role: 'logo', description: 'Logo',
      allowed_mime_types: ['image/png', 'image/webp'], available: true,
      mime_type: 'image/png', sha256: '4'.repeat(64), byte_count: 1000,
      source: { origin: 'canonical_natal_brand_asset', filename: 'logo-natal.png' },
    },
  ],
  pexels_available: false,
  versions: [],
}

function studioApi(tuneRuns: StudioTuneRun[] = []) {
  let current = structuredClone(detail)
  const post = vi.fn(async (path: string, body: unknown) => {
    if (path.endsWith('/rules')) return {
      schema: 'ptw.studio.tune-rule-approval.v1',
      run_id: path.split('/').at(-2),
      rule: (body as { rule: string }).rule,
      rule_sha256: '7'.repeat(64),
      skill_path: 'skills/studio-tune-local/references/owner-approved-rules.md',
      created: true,
    }
    if (path === '/api/v1/studio/configuration') {
      const request = body as { configuration: StudioUniversalDetail['configuration']; content: StudioUniversalDetail['content'] }
      current = {
        ...current,
        state_sha256: 'd'.repeat(64),
        configuration: structuredClone(request.configuration),
        content: structuredClone(request.content),
      }
      return structuredClone(current)
    }
    if (path === '/api/v1/studio/component-settings') {
      return structuredClone(current.component_settings)
    }
    if (path === '/api/v1/studio/assets/background_image') {
      current = {
        ...current,
        state_sha256: '6'.repeat(64),
        configuration: {
          ...current.configuration,
          background: { ...current.configuration.background, mode: 'image' },
        },
        assets: current.assets.map((asset) => asset.slot === 'background_image' ? {
          ...asset, available: true, mime_type: 'image/png', sha256: '5'.repeat(64),
          byte_count: 12, source: { origin: 'owner_upload' },
        } : asset),
      }
      return structuredClone(current)
    }
    if (path === '/api/v1/studio/assets/logo') {
      current = {
        ...current,
        state_sha256: '3'.repeat(64),
        configuration: {
          ...current.configuration,
          logo: { ...current.configuration.logo, enabled: true },
        },
        assets: current.assets.map((asset) => asset.slot === 'logo' ? {
          ...asset, available: true, mime_type: 'image/png', sha256: '2'.repeat(64),
          byte_count: 12, source: { origin: 'owner_upload' },
        } : asset),
      }
      return structuredClone(current)
    }
    if (path === '/api/v1/studio/tune-runs') return {
      schema: 'ptw.studio.tune-run.v1', run_id: '11111111-1111-4111-8111-111111111111',
      iteration: 1, status: 'queued', stage: 'queued',
      project_idea: (body as { project_idea: string }).project_idea,
      implementation: (body as { implementation: string }).implementation,
      feedback: (body as { feedback: string }).feedback,
      request_sha256: 'e'.repeat(64), changed_files: [], verification: [],
      summary: null, error: null, preview: null, created_at: '2026-08-29T10:00:00+00:00',
      updated_at: '2026-08-29T10:00:00+00:00', started_at: null, completed_at: null,
    } satisfies StudioTuneRun
    throw new Error(`Unexpected POST ${path}`)
  })
  const api = {
    get: vi.fn(async (path: string) => {
      if (path === '/api/v1/studio') return structuredClone(current)
      if (path === '/api/v1/studio/tune') return {
        schema: 'ptw.studio.tune-service.v1', mode: 'local_only', available: true,
        unavailable_reason: null, active_run_id: null, allowed_paths: [], runs: tuneRuns,
      }
      throw new Error(`Unexpected GET ${path}`)
    }),
    post,
    postMedia: vi.fn().mockResolvedValue(new Blob(['preview'], { type: 'image/png' })),
    image: vi.fn(), media: vi.fn().mockResolvedValue(new Blob(['generated'], { type: 'image/png' })), websocketUrl: vi.fn(), request: vi.fn(),
  } as unknown as ApiClient
  return { api, post }
}

describe('Universal Ad Studio', () => {
  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:studio-preview') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    Object.defineProperty(HTMLAnchorElement.prototype, 'click', {
      configurable: true, value: vi.fn(),
    })
  })

  it('renders one fixed semantic workflow and persists bounded configuration', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    expect(await screen.findByText('universal_ad · v11')).toBeInTheDocument()
    expect(screen.getByLabelText('CTA font size')).toHaveValue(27)
    expect(screen.queryByText('ONE TEMPLATE · CONFIGURATION-FIRST')).not.toBeInTheDocument()
    expect(screen.queryByText('Universal Ad Studio')).not.toBeInTheDocument()
    expect(screen.getByText('8 stable semantic roles')).toBeInTheDocument()
    expect(screen.getByAltText('Current universal advertising creative')).toHaveAttribute('src', 'blob:studio-preview')
    expect(screen.queryByText('Reference image')).not.toBeInTheDocument()
    expect(screen.queryByText('Primitive tree')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Feedback & iterations' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Build the composition at a glance' })).toBeInTheDocument()
    expect(screen.getAllByText('ALWAYS ON')).toHaveLength(5)
    expect(screen.getByLabelText('Enable sticker')).toBeChecked()
    expect(screen.queryByLabelText('Upload sticker_object asset')).not.toBeInTheDocument()
    expect(screen.getByText('Pexels photograph only')).toBeInTheDocument()
    expect(screen.getByLabelText('Enable logo')).toBeChecked()
    expect(screen.getByLabelText('Enable logo')).toBeEnabled()
    expect(screen.getByLabelText('Bullet 3')).toHaveValue('Наступний крок без зайвого шуму')

    fireEvent.change(screen.getByLabelText('Hero Title'), { target: { value: 'TEST A CLEAR PROMISE' } })
    fireEvent.change(screen.getByLabelText('Background mode'), { target: { value: 'texture' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/configuration',
      expect.objectContaining({
        base_sha256: 'a'.repeat(64),
        configuration: expect.objectContaining({ background: expect.objectContaining({ mode: 'texture' }) }),
        content: expect.objectContaining({ hero_title: 'TEST A CLEAR PROMISE' }),
      }),
      { deadlineMs: 60_000 },
    ))
    expect(await screen.findByRole('status')).toHaveTextContent('Studio setup saved.')
  })

  it('renders unsaved component toggles through the live draft preview', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    expect(await screen.findByText('LIVE PREVIEW')).toBeInTheDocument()
    expect(screen.getByLabelText('Enable sticker')).toBeChecked()
    fireEvent.click(screen.getByLabelText('Enable sticker'))

    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        state_sha256: 'a'.repeat(64),
        configuration: expect.objectContaining({
          sticker: expect.objectContaining({ enabled: false }),
        }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))
    expect(await screen.findByText('Live preview up to date')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalledWith(
      '/api/v1/studio/configuration', expect.anything(), expect.anything(),
    )
  })

  it('replaces the default Natal logo and reenables the logo slot on upload', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    expect(await screen.findByLabelText('Enable logo')).toBeChecked()
    fireEvent.click(screen.getByLabelText('Enable logo'))
    expect(screen.getByLabelText('Enable logo')).not.toBeChecked()

    fireEvent.change(screen.getByLabelText('Upload logo'), {
      target: { files: [new File(['custom-logo'], 'custom-logo.png', { type: 'image/png' })] },
    })
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/assets/logo',
      expect.objectContaining({ mime_type: 'image/png' }),
      { deadlineMs: 90_000 },
    ))
    expect(await screen.findByRole('status')).toHaveTextContent('logo saved.')
    expect(screen.getByLabelText('Enable logo')).toBeChecked()
    expect(screen.getAllByText(/owner_upload/).length).toBeGreaterThan(0)
  })

  it('keeps logo visibility, position, size, and upload together without a backing control', async () => {
    const { api } = studioApi()
    render(<StudioView api={api} language="en" />)

    await screen.findByText('Preview matches the saved setup')
    fireEvent.click(screen.getByText('Brand mark'))
    expect(screen.getByLabelText('Upload logo')).toBeInTheDocument()
    expect(screen.getByLabelText('Show logo')).toBeChecked()
    expect(screen.queryByLabelText('Show logo background')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Logo background color')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Logo position')).toHaveValue('top_right')
    expect(screen.getByLabelText('Logo width')).toHaveValue(180)

    fireEvent.click(screen.getByLabelText('Show logo'))
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        configuration: expect.objectContaining({
          logo: expect.objectContaining({ enabled: false }),
        }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))
    expect(await screen.findByText('Live preview up to date')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Enable logo'))
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      { state_sha256: 'a'.repeat(64) },
      'image/png',
      { deadlineMs: 90_000 },
    ))
    expect(screen.getByLabelText('Enable logo')).toBeChecked()
    expect(await screen.findByText('Preview matches the saved setup')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Logo position'), { target: { value: 'top_left' } })
    fireEvent.change(screen.getByLabelText('Logo width'), { target: { value: '240' } })
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        configuration: expect.objectContaining({
          logo: expect.objectContaining({ position: 'top_left', width: 240 }),
        }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))

    fireEvent.click(screen.getByLabelText('Show logo'))
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        configuration: expect.objectContaining({
          logo: expect.objectContaining({ enabled: false }),
        }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))
    expect(screen.getByLabelText('Enable logo')).not.toBeChecked()
  })

  it('names the sticker placement section and live previews every sticker control', async () => {
    const { api } = studioApi()
    render(<StudioView api={api} language="uk" />)

    await screen.findByText('Прев’ю відповідає збереженим налаштуванням')
    expect(screen.getByText('Розміщення стікера', { exact: true })).toBeInTheDocument()
    expect(screen.queryByText('Розміщення стікера й логотипа', { exact: true })).not.toBeInTheDocument()

    const changes: Array<[string, string, string, number]> = [
      ['Sticker rotation', '7', 'rotation', 7],
      ['Sticker width', '700', 'width', 700],
      ['Object scale', '1.25', 'object_scale', 1.25],
      ['Adjust from right', '500', 'offset_right', 500],
      ['Adjust from bottom', '-240', 'offset_bottom', -240],
    ]
    for (const [label, inputValue, setting, expected] of changes) {
      fireEvent.change(screen.getByLabelText(label), { target: { value: inputValue } })
      await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
        '/api/v1/studio/preview',
        expect.objectContaining({
          configuration: expect.objectContaining({
            sticker: expect.objectContaining({ [setting]: expected }),
          }),
        }),
        'image/png',
        { deadlineMs: 90_000 },
      ))
    }
    expect(await screen.findByText('Прев’ю відповідає незбереженим змінам')).toBeInTheDocument()
  })

  it('exposes the requested visual controls and uploads a sample image from Image mode', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    await screen.findByText('Preview matches the saved setup')
    expect(screen.getByLabelText('Background color')).toHaveValue('#10233f')
    expect(screen.getByLabelText('Overlay color')).toHaveValue('#07182e')
    expect(screen.getByLabelText('CTA background color')).toHaveValue('#ffd84d')
    expect(screen.getByLabelText('CTA text color')).toHaveValue('#10233f')
    expect(screen.getByLabelText('Font family')).toHaveValue('Inter')
    expect(screen.getByLabelText('Benefits font family')).toHaveValue('Manrope')
    expect(screen.getByLabelText('CTA placement')).toHaveValue('below_text')

    fireEvent.change(screen.getByLabelText('Background mode'), { target: { value: 'texture' } })
    expect(within(screen.getByLabelText('Texture')).queryByRole('option', { name: 'paper' })).not.toBeInTheDocument()
    expect(within(screen.getByLabelText('Texture')).getAllByRole('option')).toHaveLength(7)
    fireEvent.change(screen.getByLabelText('Texture'), { target: { value: 'stone' } })
    fireEvent.change(screen.getByLabelText('Texture intensity'), { target: { value: '0.9' } })
    fireEvent.change(screen.getByLabelText('Overlay opacity'), { target: { value: '0.2' } })
    fireEvent.change(screen.getByLabelText('Bullet style'), { target: { value: 'circle_outline' } })
    fireEvent.change(screen.getByLabelText('Font family'), { target: { value: 'Oswald' } })
    fireEvent.change(screen.getByLabelText('Benefits font family'), { target: { value: 'Cormorant Garamond' } })
    fireEvent.change(screen.getByLabelText('CTA style'), { target: { value: 'gradient' } })
    fireEvent.change(screen.getByLabelText('CTA placement'), { target: { value: 'bottom_right' } })
    fireEvent.change(screen.getByLabelText('Sticker position'), { target: { value: 'cta' } })
    fireEvent.change(screen.getByLabelText('Sticker width'), { target: { value: '650' } })
    fireEvent.change(screen.getByLabelText('Adjust from right'), { target: { value: '35' } })
    fireEvent.change(screen.getByLabelText('Adjust from bottom'), { target: { value: '20' } })

    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        configuration: expect.objectContaining({
          background: expect.objectContaining({
            mode: 'texture', texture: 'stone', texture_intensity: 0.9, overlay_opacity: 0.2,
          }),
          bullets: expect.objectContaining({ style: 'circle_outline' }),
          typography: expect.objectContaining({
            font_family: 'Oswald', benefits_font_family: 'Cormorant Garamond',
          }),
          cta: expect.objectContaining({ style: 'gradient', position: 'bottom_right' }),
          sticker: expect.objectContaining({
            position: 'cta', width: 650, offset_right: 35, offset_bottom: 20,
          }),
        }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))

    fireEvent.change(screen.getByLabelText('Background mode'), { target: { value: 'image' } })
    const upload = screen.getByLabelText('Upload sample background image')
    fireEvent.change(upload, { target: { files: [new File(['sample'], 'sample.png', { type: 'image/png' })] } })
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/assets/background_image',
      expect.objectContaining({ mime_type: 'image/png' }),
      { deadlineMs: 90_000 },
    ))
    expect(await screen.findByRole('status')).toHaveTextContent('background_image saved.')
    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        state_sha256: '6'.repeat(64),
        configuration: expect.objectContaining({
          background: expect.objectContaining({ mode: 'image', texture: 'stone' }),
          typography: expect.objectContaining({
            font_family: 'Oswald', benefits_font_family: 'Cormorant Garamond',
          }),
          cta: expect.objectContaining({ style: 'gradient', position: 'bottom_right' }),
          sticker: expect.objectContaining({ position: 'cta', width: 650 }),
        }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))
  })

  it('exports canonical component IDs and exact draft settings metadata', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    await screen.findByText('Preview matches the saved setup')
    fireEvent.change(screen.getByLabelText('CTA style'), { target: { value: 'outlined' } })
    fireEvent.click(screen.getByRole('button', { name: 'Export config + IDs' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/component-settings',
      expect.objectContaining({
        state_sha256: 'a'.repeat(64),
        configuration: expect.objectContaining({
          cta: expect.objectContaining({ style: 'outlined' }),
        }),
      }),
    ))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Configuration and component ID metadata exported.',
    )
    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    const exportedBlob = vi.mocked(URL.createObjectURL).mock.calls.at(-1)?.[0] as Blob
    const exportedText = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onerror = () => reject(reader.error)
      reader.onload = () => resolve(String(reader.result))
      reader.readAsText(exportedBlob)
    })
    const exported = JSON.parse(exportedText)
    expect(exported).toMatchObject({
      schema: 'ptw.studio.universal-ad-export.v4',
      template_id: 'universal_ad',
      component_settings: {
        schema: 'ptw.studio.universal-ad-component-settings.v2',
        sha256: '9'.repeat(64),
      },
      configuration: { cta: { style: 'outlined' } },
    })
  })

  it('renders unsaved text and background edits through the live draft preview', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    await screen.findByText('Preview matches the saved setup')
    fireEvent.change(screen.getByLabelText('Hero Title'), { target: { value: 'A NEW LIVE PROMISE' } })
    fireEvent.change(screen.getByLabelText('Background mode'), { target: { value: 'texture' } })

    await waitFor(() => expect(api.postMedia).toHaveBeenLastCalledWith(
      '/api/v1/studio/preview',
      expect.objectContaining({
        state_sha256: 'a'.repeat(64),
        configuration: expect.objectContaining({
          background: expect.objectContaining({ mode: 'texture' }),
        }),
        content: expect.objectContaining({ hero_title: 'A NEW LIVE PROMISE' }),
      }),
      'image/png',
      { deadlineMs: 90_000 },
    ))
    expect(await screen.findByText('Preview matches your unsaved changes')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalledWith(
      '/api/v1/studio/configuration', expect.anything(), expect.anything(),
    )
  })

  it('opens the local-only Tune wizard and submits idea, implementation, and feedback', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" tuneMode />)

    fireEvent.click(await screen.findByRole('button', { name: 'Feedback & iterations' }))
    const wizard = await screen.findByRole('dialog', { name: 'Test generation' })
    expect(within(wizard).getByText('LOCAL ONLY · TUNE MODE')).toBeInTheDocument()
    expect(within(wizard).getByText('It can improve its Studio code.')).toBeInTheDocument()

    fireEvent.change(within(wizard).getByLabelText('Project idea'), {
      target: { value: 'A calm planning tool for independent founders.' },
    })
    fireEvent.change(within(wizard).getByLabelText('Desired implementation'), {
      target: { value: 'Use an editorial card layout with one clear test action.' },
    })
    fireEvent.change(within(wizard).getByLabelText('Your feedback'), {
      target: { value: 'Make the hierarchy quieter and reduce the number of controls.' },
    })
    fireEvent.click(within(wizard).getByRole('button', { name: 'Apply feedback' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/studio/tune-runs', {
      project_idea: 'A calm planning tool for independent founders.',
      implementation: 'Use an editorial card layout with one clear test action.',
      feedback: 'Make the hierarchy quieter and reduce the number of controls.',
    }, { deadlineMs: 30_000 }))
    expect(within(wizard).getByText('Queued')).toBeInTheDocument()
    expect(within(wizard).getByRole('progressbar', { name: 'Tune generation progress' })).toBeInTheDocument()
  })

  it('shows the exact generated creative inside a completed Tune iteration', async () => {
    const completed: StudioTuneRun = {
      schema: 'ptw.studio.tune-run.v1', run_id: '11111111-1111-4111-8111-111111111111',
      iteration: 1, status: 'completed', stage: 'completed',
      project_idea: 'A planning product for independent founders.',
      implementation: 'Use one clear editorial advertising composition.',
      feedback: 'Keep every Studio CTA singular and visually dominant.',
      request_sha256: 'e'.repeat(64), changed_files: [], verification: [],
      summary: 'Rendered and verified the requested creative.', error: null,
      preview: { mime_type: 'image/png', sha256: 'f'.repeat(64), width: 1080, height: 1080 },
      created_at: '2026-08-29T10:00:00+00:00', updated_at: '2026-08-29T10:01:00+00:00',
      started_at: '2026-08-29T10:00:00+00:00', completed_at: '2026-08-29T10:01:00+00:00',
    }
    const { api, post } = studioApi([completed])
    render(<StudioView api={api} language="en" tuneMode />)

    fireEvent.click(await screen.findByRole('button', { name: 'Feedback & iterations' }))
    const image = await screen.findByAltText('Generated creative for iteration 1')
    expect(image).toHaveAttribute('src', 'blob:studio-preview')
    expect(screen.getByText('GENERATED CREATIVE · 1080×1080')).toBeInTheDocument()
    expect(api.media).toHaveBeenCalledWith(
      '/api/v1/studio/tune-runs/11111111-1111-4111-8111-111111111111/preview',
      'image/png', 'f'.repeat(64),
    )
    expect(screen.getByRole('button', { name: 'Back to Studio' })).toBeInTheDocument()
    expect(screen.getByLabelText('Feedback for next iteration')).toHaveValue('')
    expect(screen.getByText(completed.feedback)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save as reusable rule' })).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Feedback for next iteration'), {
      target: { value: 'Remove the paper and use a thick white Apple-style sticker outline.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save as reusable rule' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/v1/studio/tune-runs/11111111-1111-4111-8111-111111111111/rules',
      { rule: 'Remove the paper and use a thick white Apple-style sticker outline.' },
      { deadlineMs: 30_000 },
    ))
    expect(await screen.findByRole('status')).toHaveTextContent('Saved as a reusable rule for future Tune runs.')
    expect(screen.getByRole('button', { name: 'Reusable rule saved' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Apply feedback' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/studio/tune-runs', {
      project_idea: completed.project_idea,
      implementation: completed.implementation,
      feedback: 'Remove the paper and use a thick white Apple-style sticker outline.',
    }, { deadlineMs: 30_000 }))
  })

  it('shows the current creative for failed iteration feedback without exposing the traceback', async () => {
    const failed: StudioTuneRun = {
      schema: 'ptw.studio.tune-run.v1', run_id: '22222222-2222-4222-8222-222222222222',
      iteration: 2, status: 'failed', stage: 'failed',
      project_idea: 'A planning product for independent founders.',
      implementation: 'Use one clear editorial advertising composition.',
      feedback: 'Use a thick white die-cut outline around the sticker.',
      request_sha256: 'd'.repeat(64), changed_files: [], verification: [],
      summary: 'The automated attempt stopped before copyback.',
      error: 'Traceback (most recent call last):\nNameError: ImageFilter is not defined',
      preview: null,
      created_at: '2026-08-29T10:02:00+00:00', updated_at: '2026-08-29T10:03:00+00:00',
      started_at: '2026-08-29T10:02:00+00:00', completed_at: '2026-08-29T10:03:00+00:00',
    }
    const { api } = studioApi([failed])
    render(<StudioView api={api} language="en" tuneMode />)

    fireEvent.click(await screen.findByRole('button', { name: 'Feedback & iterations' }))
    expect(await screen.findByAltText('Current Studio creative for feedback')).toHaveAttribute('src', 'blob:studio-preview')
    expect(screen.getByText('CURRENT STUDIO CREATIVE · 1080×1080')).toBeInTheDocument()
    expect(screen.getByLabelText('Feedback for next iteration')).toHaveValue(failed.feedback)
    expect(screen.getByRole('button', { name: 'Retry feedback' })).toBeEnabled()
    expect(screen.queryByText('Technical failure details')).not.toBeInTheDocument()
    expect(screen.queryByText(/ImageFilter is not defined/)).not.toBeInTheDocument()
  })
})
