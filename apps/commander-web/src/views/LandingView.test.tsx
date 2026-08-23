import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type {
  LandingBlockEdit, LandingBrief, LandingBuild, LandingDraftSet, LandingPageContent,
  LandingSkillProposal, LandingTemplate,
} from '../types'
import { LandingView } from './LandingView'

const runId = '01234567-89ab-7def-8123-456789abcdef'
const thesisId = '11234567-89ab-7def-8123-456789abcdef'
const draftId = '21234567-89ab-7def-8123-456789abcdef'
const snapshotIds = {
  product: '31234567-89ab-7def-8123-456789abcdef',
  community: '41234567-89ab-7def-8123-456789abcdef',
  waitlist: '51234567-89ab-7def-8123-456789abcdef',
}
const editedSnapshotId = '61234567-89ab-7def-8123-456789abcdef'
const editId = '71234567-89ab-7def-8123-456789abcdef'
const proposalId = '81234567-89ab-7def-8123-456789abcdef'
const buildId = '91234567-89ab-7def-8123-456789abcdef'

const brief: LandingBrief = {
  schema_version: 1, brand: 'Natal', language: 'uk',
  source: { laval_run_id: runId, thesis_id: thesisId },
  business_idea: 'Автоматичне утримання клієнтів',
  target_audience: 'Власники сервісного бізнесу', pain: 'Клієнти зникають непомітно',
  promise: 'Natal показує наступну дію',
  key_features: [{ title: 'Сигнали ризику', description: 'Помічає зміни раніше' }],
  steps: [{ title: '01', description: 'Підключіть дані' }, { title: '02', description: 'Побачте ризик' }],
  proof_points: [], faq: [], cta: { label: 'Спробувати Natal', url: '#contact' },
}

const templates: LandingTemplate[] = [
  { id: 'product', version: 1, name: { uk: 'Продукт', en: 'Product' }, description: { uk: 'Функції', en: 'Features' }, best_for: [], adapted_from: 'natal_landing' },
  { id: 'community', version: 1, name: { uk: 'Спільнота / подія', en: 'Community / event' }, description: { uk: 'Участь', en: 'Participation' }, best_for: [], adapted_from: 'sesh' },
  { id: 'waitlist', version: 1, name: { uk: 'Waitlist / концепт', en: 'Waitlist / concept' }, description: { uk: 'Попит', en: 'Demand' }, best_for: [], adapted_from: 'ofc' },
]

function pageContent(templateId: LandingTemplate['id']): LandingPageContent {
  return {
    schema_version: 1, template_id: templateId, language: 'uk', blocks: {
      hero: { eyebrow: 'Для команд', title: 'Видимий прогрес', body: 'Працюйте ясніше', cta_label: 'Почати' },
      problem: { eyebrow: 'Проблема', title: 'Немає ясності', body: 'Прогрес губиться' },
      features: { eyebrow: 'Переваги', title: 'Менше тертя', items: [{ title: 'Сигнал', description: 'Раніше' }] },
      steps: { eyebrow: 'Кроки', title: 'Як це працює', items: [{ title: '1', description: 'Почніть' }, { title: '2', description: 'Перевірте' }] },
      proof: { eyebrow: 'Докази', title: 'Перевірені факти', items: [], empty_text: 'Без непідтверджених заяв' },
      faq: { eyebrow: 'FAQ', title: 'Питання', items: [] },
      final_cta: { title: 'Готові?', body: 'Наступний крок', cta_label: 'Почати' },
    },
  }
}

function draft(status: LandingDraftSet['status'] = 'ready', edited = false): LandingDraftSet {
  return {
    id: draftId, request_id: 'a1234567-89ab-7def-8123-456789abcdef', idea_run_id: runId,
    thesis_id: thesisId, brief, recommended_template_id: 'product', skill_memory_feedback_ids: [],
    status, population_summary: status === 'ready' ? 'Три моделі підготовлено.' : null,
    population_invocation: null, error_code: null, error_message: null, requested_by: 'firebase:owner',
    variants: status === 'ready' ? templates.map((template) => ({
      id: edited && template.id === 'community' ? editedSnapshotId : snapshotIds[template.id],
      draft_set_id: draftId, template_id: template.id,
      snapshot_number: edited && template.id === 'community' ? 2 : 1,
      parent_snapshot_id: edited && template.id === 'community' ? snapshotIds.community : null,
      source_feedback_id: edited && template.id === 'community' ? 'b1234567-89ab-7def-8123-456789abcdef' : null,
      page_content: pageContent(template.id), page_content_sha256: 'a'.repeat(64),
      artifact_sha256: 'b'.repeat(64), is_current: true, application_summary: 'Готово',
      invocation: null, created_at: '2026-08-22T00:00:00Z',
    })) : [],
    edits: edited ? [completedEdit()] : [],
    created_at: '2026-08-22T00:00:00Z', updated_at: edited ? '2026-08-22T00:00:02Z' : '2026-08-22T00:00:00Z',
    completed_at: status === 'ready' ? '2026-08-22T00:00:01Z' : null,
  }
}

function queuedEdit(): LandingBlockEdit {
  return {
    request_id: editId, draft_set_id: draftId, template_id: 'community',
    base_snapshot_id: snapshotIds.community, block_id: 'features',
    instruction: 'Почніть з конкретного результату',
    feedback_id: 'b1234567-89ab-7def-8123-456789abcdef', proposal_id: proposalId,
    result_snapshot_id: null, status: 'queued', error_code: null, error_message: null,
    created_at: '2026-08-22T00:00:01Z', updated_at: '2026-08-22T00:00:01Z', completed_at: null,
  }
}

function completedEdit(): LandingBlockEdit {
  return { ...queuedEdit(), status: 'completed', result_snapshot_id: editedSnapshotId, completed_at: '2026-08-22T00:00:02Z' }
}

function proposal(status: LandingSkillProposal['status'] = 'pending_review'): LandingSkillProposal {
  return {
    id: proposalId, feedback_id: queuedEdit().feedback_id, draft_set_id: draftId,
    template_id: 'community', block_id: 'features', proposed_lesson: 'Починайте features з конкретного результату.',
    reviewed_lesson: null, status, command_session_id: status === 'planning' ? 'plan-1' : null,
    comment: queuedEdit().instruction, created_at: '2026-08-22T00:00:01Z', updated_at: '2026-08-22T00:00:02Z',
  }
}

function build(status: LandingBuild['status']): LandingBuild {
  return {
    id: buildId, request_id: 'c1234567-89ab-7def-8123-456789abcdef', idea_run_id: runId,
    thesis_id: thesisId, template_id: 'community', parent_build_id: null, revision_number: 1,
    input_brief: brief, brief, skill_memory_feedback_ids: [], revision_summary: 'Exact snapshot',
    revision_invocation: null, source_draft_snapshot_id: editedSnapshotId,
    page_content: pageContent('community'), page_content_sha256: 'a'.repeat(64), status,
    build_manifest: null, artifact_sha256: status === 'published' ? 'c'.repeat(64) : null,
    firebase_site_id: 'natal-landings-86123', firebase_version: status === 'published' ? 'version-1' : null,
    public_url: status === 'published' ? `https://natal-landings-86123.web.app/builds/${buildId}/` : null,
    error_code: null, error_message: null, created_at: '2026-08-22T00:00:03Z',
    updated_at: '2026-08-22T00:00:03Z', completed_at: status === 'published' ? '2026-08-22T00:00:04Z' : null,
  }
}

describe('LandingView', () => {
  it('switches sandboxed previews, selects a block, persists its edit, promotes the lesson, and publishes the exact snapshot', async () => {
    let currentDraft = draft()
    let proposals: LandingSkillProposal[] = []
    const get = vi.fn((path: string) => {
      if (path.includes('/templates')) return Promise.resolve({ items: templates })
      if (path.includes('/candidates')) return Promise.resolve({ items: [{ idea_run_id: runId, recommended_template_id: 'product', brief, quality: { successful: 8, attempted: 9 }, verdict: 'survives' }] })
      if (path === '/api/v1/landings/builds?limit=100') return Promise.resolve({ items: [] })
      if (path.includes('/draft-sets/latest')) return Promise.resolve(currentDraft)
      if (path === `/api/v1/landings/draft-sets/${draftId}`) {
        currentDraft = draft('ready', true)
        proposals = [proposal()]
        return Promise.resolve(currentDraft)
      }
      if (path.includes('/draft-snapshots/') && path.endsWith('/preview')) {
        const id = path.split('/').at(-2)
        return Promise.resolve({ snapshot_id: id, template_id: id === snapshotIds.product ? 'product' : 'community', snapshot_number: id === editedSnapshotId ? 2 : 1, artifact_sha256: 'b'.repeat(64), html: '<!doctype html><html><body><section data-landing-block="features">Preview</section></body></html>' })
      }
      if (path.includes('/skill-proposals')) return Promise.resolve({ items: proposals })
      if (path === `/api/v1/landings/builds/${buildId}`) return Promise.resolve(build('published'))
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const post = vi.fn((path: string) => {
      if (path.endsWith('/edits')) return Promise.resolve(queuedEdit())
      if (path.endsWith('/plan')) return Promise.resolve({ proposal: proposal('planning'), job: { id: 'plan-1' } })
      if (path === '/api/v1/landings/builds') return Promise.resolve(build('queued'))
      return Promise.reject(new Error(`unexpected POST ${path}`))
    })
    render(<LandingView api={{ get, post } as unknown as ApiClient} language="uk" />)

    expect(await screen.findByRole('heading', { name: 'Три приватні превʼю готові' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Продукт/ })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('tab', { name: /Спільнота/ }))
    const iframe = await screen.findByTitle('Natal community private preview')
    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts')
    expect(iframe).toHaveAttribute('srcdoc', expect.stringContaining('data-landing-block="features"'))
    fireEvent.click(screen.getByRole('button', { name: '360 px' }))
    expect(screen.getByRole('button', { name: '360 px' })).toHaveAttribute('aria-pressed', 'true')

    const selectionMessage = new MessageEvent('message', {
      data: { type: 'natal.select-block', templateId: 'community', blockId: 'features' },
    })
    Object.defineProperty(selectionMessage, 'source', { value: (iframe as HTMLIFrameElement).contentWindow })
    fireEvent(window, selectionMessage)
    const instruction = await screen.findByLabelText('Інструкція для блоку «Переваги»')
    fireEvent.change(instruction, { target: { value: 'Почніть з конкретного результату' } })
    fireEvent.click(screen.getByRole('button', { name: /Застосувати лише до блоку/ }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/landings/draft-snapshots/${snapshotIds.community}/edits`,
      expect.objectContaining({ block_id: 'features', instruction: 'Почніть з конкретного результату' }),
    ))
    expect(await screen.findByText('Починайте features з конкретного результату.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Узагальнений урок'), { target: { value: 'Показуйте конкретний результат на початку features.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Promote через Plan' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      `/api/v1/landings/skill-proposals/${proposalId}/plan`,
      { lesson: 'Показуйте конкретний результат на початку features.' },
    ))

    fireEvent.click(screen.getByRole('button', { name: /Publish this version/ }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/landings/builds', expect.objectContaining({ draft_snapshot_id: editedSnapshotId })))
    expect(await screen.findByRole('heading', { name: 'Версію опубліковано' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Відкрити опубліковану версію/ })).toHaveAttribute('href', `https://natal-landings-86123.web.app/builds/${buildId}/`)
  })

  it('starts one durable population action when no draft exists', async () => {
    const queued = draft('queued')
    const get = vi.fn((path: string) => {
      if (path.includes('/templates')) return Promise.resolve({ items: templates })
      if (path.includes('/candidates')) return Promise.resolve({ items: [{ idea_run_id: runId, recommended_template_id: 'product', brief, quality: {} }] })
      if (path === '/api/v1/landings/builds?limit=100') return Promise.resolve({ items: [] })
      if (path.includes('/draft-sets/latest')) return Promise.reject(new Error('Natal draft set not found'))
      if (path === `/api/v1/landings/draft-sets/${draftId}`) return Promise.resolve(draft())
      if (path.includes('/draft-snapshots/')) return Promise.resolve({ snapshot_id: snapshotIds.product, template_id: 'product', snapshot_number: 1, artifact_sha256: 'b'.repeat(64), html: '<html></html>' })
      if (path.includes('/skill-proposals')) return Promise.resolve({ items: [] })
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const post = vi.fn(() => Promise.resolve(queued))
    render(<LandingView api={{ get, post } as unknown as ApiClient} language="uk" />)
    fireEvent.click(await screen.findByRole('button', { name: /Заповнити три превʼю/ }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/landings/draft-sets', expect.objectContaining({ idea_run_id: runId })))
    expect(await screen.findByRole('heading', { name: 'Три приватні превʼю готові' })).toBeInTheDocument()
  })
})
