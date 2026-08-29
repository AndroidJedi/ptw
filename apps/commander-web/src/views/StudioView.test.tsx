import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { StudioTuneRun, StudioUniversalDetail } from '../types'
import { StudioView } from './StudioView'

const detail: StudioUniversalDetail = {
  schema: 'ptw.studio.universal-ad-workspace.v1',
  catalog: {
    schema: 'ptw.studio.universal-ad-catalog.v1',
    template_id: 'universal_ad', template_version: 1,
    semantic_roles: ['background', 'sticker', 'hero_title', 'supporting_text', 'bullet_list', 'cta', 'logo'],
    asset_slots: {},
    variation: {
      background_modes: ['solid', 'texture', 'image'], image_layouts: ['full', 'left', 'right', 'top', 'bottom'],
      texture_presets: ['paper', 'grain'], font_families: ['Inter', 'Roboto Condensed'],
      optional_elements: ['sticker', 'bullet_list', 'logo'],
    },
    sha256: 'b'.repeat(64),
  },
  state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
  configuration: {
    schema: 'ptw.studio.universal-ad-config.v1',
    background: {
      mode: 'image', color: '#10233F', texture: 'paper', image_layout: 'full', image_fit: 'cover',
      focal_x: 0.5, focal_y: 0.5, overlay_color: '#07182E', overlay_opacity: 0.56,
    },
    typography: {
      font_family: 'Inter', hero_size: 94, hero_weight: 800, supporting_size: 30,
      text_color: '#FFFFFF', alignment: 'left',
    },
    layout: { content_x: 76, content_y: 128, content_width: 650, gap: 20 },
    bullets: { enabled: true, marker: '✓' },
    cta: { background_color: '#FFD84D', text_color: '#10233F', radius: 24 },
    sticker: {
      enabled: true, position: 'bottom_right', rotation: 5, paper_width: 300,
      paper_color: '#FFF5D1', object_scale: 0.9,
    },
    logo: { enabled: false, position: 'top_left', width: 160 },
  },
  content: {
    hero_title: 'ІНВЕСТУВАТИ В УКРАЇНІ — ПРОСТІШЕ',
    supporting_text: 'Аналізуємо ваші цілі й підказуємо інструменти, що відповідають саме вам.',
    bullets: ['Персональний підбір інструментів', 'Зрозуміле порівняння ризику', 'Наступний крок без зайвого шуму'],
    cta: 'ЗНАЙТИ СВОЄ',
  },
  assets: [
    {
      slot: 'background_image', role: 'background', description: 'Background',
      allowed_mime_types: ['image/jpeg', 'image/png', 'image/webp'], available: true,
      mime_type: 'image/png', sha256: 'f'.repeat(64), byte_count: 1000,
      source: { origin: 'bundled_tune_asset' },
    },
    {
      slot: 'sticker_object', role: 'sticker', description: 'Sticker',
      allowed_mime_types: ['image/png', 'image/webp'], available: true,
      mime_type: 'image/png', sha256: 'e'.repeat(64), byte_count: 1000,
      source: { origin: 'bundled_tune_asset' },
    },
    {
      slot: 'logo', role: 'logo', description: 'Logo',
      allowed_mime_types: ['image/png', 'image/webp'], available: false,
      mime_type: null, sha256: null, byte_count: null, source: null,
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
  })

  it('renders one fixed semantic workflow and persists bounded configuration', async () => {
    const { api, post } = studioApi()
    render(<StudioView api={api} language="en" />)

    expect(await screen.findByText('universal_ad · v1')).toBeInTheDocument()
    expect(screen.queryByText('ONE TEMPLATE · CONFIGURATION-FIRST')).not.toBeInTheDocument()
    expect(screen.queryByText('Universal Ad Studio')).not.toBeInTheDocument()
    expect(screen.getByText('7 stable semantic roles')).toBeInTheDocument()
    expect(screen.getByAltText('Current universal advertising creative')).toHaveAttribute('src', 'blob:studio-preview')
    expect(screen.queryByText('Reference image')).not.toBeInTheDocument()
    expect(screen.queryByText('Primitive tree')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Feedback & iterations' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Build the composition at a glance' })).toBeInTheDocument()
    expect(screen.getAllByText('ALWAYS ON')).toHaveLength(4)
    expect(screen.getByLabelText('Enable sticker')).toBeChecked()
    expect(screen.getByLabelText('Enable logo')).not.toBeChecked()
    expect(screen.getByLabelText('Enable logo')).toBeDisabled()
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
