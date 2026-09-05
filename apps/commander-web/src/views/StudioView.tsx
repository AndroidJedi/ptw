import {
  Check, Download, ImagePlus, Plus, RefreshCcw, Save, Search, Sparkles, Upload, WandSparkles, X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { StudioTuneWizard } from '../components/studio/StudioTuneWizard'
import { PhoneMetricsStudio } from '../components/studio/PhoneMetricsStudio'
import { PhoneHeroDirectionPicker, creativeDirectionFromDraft, type PhoneHeroDirectionDraft } from '../components/studio/PhoneHeroDirectionPicker'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type {
  StudioUniversalComponentSettings, StudioUniversalConfiguration, StudioUniversalContent,
  StudioCheckpointResponse, StudioCreativeSummary, StudioLearningProposal,
  ProductBrief, StudioTemplateSummary, StudioUniversalDetail, StudioUniversalFontFamily,
  StudioPhoneHeroCreativeDirection,
} from '../types'

function LearningDialog({ proposal, summary, projectLesson, busy, language, onDecision }: {
  proposal: StudioLearningProposal
  summary: string
  projectLesson: string
  busy: boolean
  language: Language
  onDecision: (decision: 'global' | 'project_only') => void
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <div className="modal-backdrop" role="presentation"><section className="panel studio-learning-dialog" role="alertdialog" aria-modal="true" aria-labelledby="studio-learning-title">
    <header><div><small>{tr('CREATIVE LEARNING', 'НАВЧАННЯ НА КРЕАТИВІ')}</small><h2 id="studio-learning-title">{tr('Project skill updated', 'Навичку проєкту оновлено')}</h2></div></header>
    <dl><dt>{tr('Saved edits', 'Збережені зміни')}</dt><dd>{summary}</dd><dt>{tr('Project lesson', 'Урок проєкту')}</dt><dd>{projectLesson}</dd><dt>{tr('Proposed global rule', 'Запропоноване глобальне правило')}</dt><dd>{proposal.global_rule}</dd></dl>
    <div className="studio-learning-actions"><button className="secondary" disabled={busy} onClick={() => onDecision('project_only')}><X />{tr('Keep project-only', 'Лише для проєкту')}</button><button className="primary" disabled={busy} onClick={() => onDecision('global')}><Check />{tr('Apply globally', 'Застосувати глобально')}</button></div>
  </section></div>
}

function fileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error || new Error('File could not be read.'))
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '')
    reader.readAsDataURL(file)
  })
}

function downloadJson(filename: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function normalizedPreviewContent(value: StudioUniversalContent): StudioUniversalContent {
  if (!Array.isArray((value as unknown as { bullets?: unknown }).bullets)) return value
  return {
    ...value,
    bullets: value.bullets.map((item) => item.trim()).filter(Boolean),
  }
}

function NumberField({ label, value, min, max, step = 1, onChange }: {
  label: string
  value: number
  min: number
  max: number
  step?: number
  onChange: (value: number) => void
}) {
  const [draft, setDraft] = useState(String(value))
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (!editing) setDraft(String(value))
  }, [editing, value])

  const parsedDraft = draft.trim() === '' ? Number.NaN : Number(draft)
  const draftIsValid = Number.isFinite(parsedDraft)
    && parsedDraft >= min && parsedDraft <= max
    && (step !== 1 || Number.isInteger(parsedDraft))

  const finishEditing = () => {
    setEditing(false)
    if (!Number.isFinite(parsedDraft)) {
      setDraft(String(value))
      return
    }
    const bounded = Math.min(max, Math.max(min, parsedDraft))
    const normalized = step === 1 ? Math.round(bounded) : bounded
    setDraft(String(normalized))
    if (normalized !== value) onChange(normalized)
  }

  return <label><span>{label}</span><input
    aria-label={label} aria-invalid={editing && !draftIsValid}
    type="number" value={draft} min={min} max={max} step={step}
    onFocus={() => setEditing(true)}
    onChange={(event) => {
      const nextDraft = event.target.value
      setDraft(nextDraft)
      const nextValue = nextDraft.trim() === '' ? Number.NaN : Number(nextDraft)
      if (
        Number.isFinite(nextValue) && nextValue >= min && nextValue <= max
        && (step !== 1 || Number.isInteger(nextValue))
      ) onChange(nextValue)
    }}
    onBlur={finishEditing}
    onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }}
  /></label>
}

function ColorField({ label, value, onChange }: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return <label className="universal-color-field">
    <span>{label}<code>{value.toUpperCase()}</code></span>
    <input aria-label={label} type="color" value={value} onChange={(event) => onChange(event.target.value)} />
  </label>
}

function RangeField({ label, value, min, max, step, onChange }: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
}) {
  return <label className="universal-range-field">
    <span>{label}<code>{Math.round(value * 100)}%</code></span>
    <input
      aria-label={label} type="range" value={value} min={min} max={max} step={step}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  </label>
}

export function StudioView({ api, language, projectId = null, creativeId = null, onCreative = () => {}, tuneMode = false }: {
  api: ApiClient
  language: Language
  projectId?: string | null
  creativeId?: string | null
  onCreative?: (creativeId: string) => void
  tuneMode?: boolean
}) {
  const [detail, setDetail] = useState<StudioUniversalDetail | null>(null)
  const [configuration, setConfiguration] = useState<StudioUniversalConfiguration | null>(null)
  const [content, setContent] = useState<StudioUniversalContent | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [backgroundQuery, setBackgroundQuery] = useState('')
  const [stickerQuery, setStickerQuery] = useState(
    'single light bulb photographed on a plain white background isolated object',
  )
  const [changeNote, setChangeNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [draftPreviewed, setDraftPreviewed] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [tuneOpen, setTuneOpen] = useState(false)
  const [creatives, setCreatives] = useState<StudioCreativeSummary[] | null>(null)
  const [approvedBriefs, setApprovedBriefs] = useState<ProductBrief[] | null>(null)
  const [initialTemplates, setInitialTemplates] = useState<StudioTemplateSummary[] | null>(null)
  const [learning, setLearning] = useState<{
    proposal: StudioLearningProposal; summary: string; projectLesson: string
  } | null>(null)
  const [firstCreativeSelection, setFirstCreativeSelection] = useState<{
    brief: ProductBrief; templateId: 'phone_metrics'; direction: PhoneHeroDirectionDraft
  } | null>(null)
  const [variantDirection, setVariantDirection] = useState<PhoneHeroDirectionDraft>({ style: '', background: '' })
  const [variantDirectionOpen, setVariantDirectionOpen] = useState(false)
  const importRef = useRef<HTMLInputElement>(null)
  const draftPreviewGeneration = useRef(0)
  const previewMode = useRef<'saved' | 'draft'>('saved')
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const basePath = projectId && creativeId
    ? `/api/v1/studio/projects/${projectId}/creatives/${creativeId}`
    : ''

  const applyDetail = (value: StudioUniversalDetail) => {
    setDetail(value)
    setConfiguration(structuredClone(value.configuration))
    setContent(structuredClone(value.content))
  }

  const renderPreview = async (value: StudioUniversalDetail) => {
    draftPreviewGeneration.current += 1
    const blob = await api.postMedia(
      `${basePath}/preview`, { state_sha256: value.state_sha256 },
      'image/png', { deadlineMs: 90_000 },
    )
    setPreviewUrl(URL.createObjectURL(blob))
    previewMode.current = 'saved'
    setPreviewError('')
    setPreviewBusy(false)
    setDraftPreviewed(false)
  }

  const load = async () => {
    if (!projectId) { setCreatives([]); setApprovedBriefs([]); setInitialTemplates([]); setDetail(null); return }
    setBusy(true)
    setError('')
    setApprovedBriefs(null)
    setInitialTemplates(null)
    try {
      const list = await api.get<{ items: StudioCreativeSummary[] }>(
        `/api/v1/studio/projects/${projectId}/creatives`,
      )
      setCreatives(list.items)
      const selectedId = list.items.some((item) => item.creative_id === creativeId)
        ? creativeId
        : list.items[0]?.creative_id || null
      if (!selectedId) {
        const [briefs, templates] = await Promise.all([
          api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?project_id=${projectId}&limit=100`),
          api.get<{ items: StudioTemplateSummary[] }>('/api/v1/studio/templates'),
        ])
        setApprovedBriefs(briefs.items.filter((brief) => (
          brief.approved && brief.status === 'completed' && Boolean(brief.document)
        )))
        setInitialTemplates(templates.items)
        setDetail(null)
        return
      }
      if (selectedId !== creativeId) onCreative(selectedId)
      const path = `/api/v1/studio/projects/${projectId}/creatives/${selectedId}`
      const value = await api.get<StudioUniversalDetail>(path, { deadlineMs: 60_000 })
      applyDetail(value)
      try {
        if (value.status === 'draft') {
          const blob = await api.postMedia(
            `${path}/preview`, { state_sha256: value.state_sha256 },
            'image/png', { deadlineMs: 90_000 },
          )
          setPreviewUrl(URL.createObjectURL(blob))
        }
      } catch (cause) {
        setError((cause as Error).message)
      }
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { setDetail(null); void load() }, [api, projectId, creativeId])
  useEffect(() => {
    const status = detail?.status
    if (!status || !['queued', 'composing', 'generating_image'].includes(status)) return
    const timer = window.setInterval(() => void load(), 1500)
    return () => window.clearInterval(timer)
  }, [detail?.status, projectId, creativeId])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  useEffect(() => {
    const generation = ++draftPreviewGeneration.current
    if (!detail || !configuration || !content || busy) {
      setPreviewBusy(false)
      return
    }
    const normalizedContent = normalizedPreviewContent(content)
    const matchesPersisted = (
      JSON.stringify(configuration) === JSON.stringify(detail.configuration)
      && JSON.stringify(normalizedContent) === JSON.stringify(detail.content)
    )
    window.sessionStorage.setItem('ptw.studio.unsaved', matchesPersisted ? '0' : '1')
    if (matchesPersisted) {
      if (previewMode.current === 'draft') {
        setPreviewBusy(true)
        setPreviewError('')
        const timer = window.setTimeout(async () => {
          try {
            const blob = await api.postMedia(
              `${basePath}/preview`, { state_sha256: detail.state_sha256 },
              'image/png', { deadlineMs: 90_000 },
            )
            if (draftPreviewGeneration.current !== generation) return
            setPreviewUrl(URL.createObjectURL(blob))
            previewMode.current = 'saved'
            setDraftPreviewed(false)
          } catch (cause) {
            if (draftPreviewGeneration.current !== generation) return
            setPreviewError((cause as Error).message)
          } finally {
            if (draftPreviewGeneration.current === generation) setPreviewBusy(false)
          }
        }, 180)
        return () => window.clearTimeout(timer)
      }
      setPreviewBusy(false)
      setPreviewError('')
      setDraftPreviewed(false)
      return
    }
    if (!normalizedContent.hero_title.trim() || !normalizedContent.supporting_text.trim() || !normalizedContent.offer.trim() || !normalizedContent.cta.trim()) {
      setPreviewBusy(false)
      setPreviewError(tr(
        'Complete the title, supporting text, offer, and CTA to refresh the preview.',
        'Заповніть заголовок, пояснення, пропозицію та CTA, щоб оновити прев’ю.',
      ))
      return
    }
    setPreviewBusy(true)
    setPreviewError('')
    setDraftPreviewed(false)
    const timer = window.setTimeout(async () => {
      try {
        const blob = await api.postMedia(`${basePath}/preview`, {
          state_sha256: detail.state_sha256,
          configuration,
          content: normalizedContent,
        }, 'image/png', { deadlineMs: 90_000 })
        if (draftPreviewGeneration.current !== generation) return
        setPreviewUrl(URL.createObjectURL(blob))
        previewMode.current = 'draft'
        setDraftPreviewed(true)
      } catch (cause) {
        if (draftPreviewGeneration.current !== generation) return
        setPreviewError((cause as Error).message)
      } finally {
        if (draftPreviewGeneration.current === generation) setPreviewBusy(false)
      }
    }, 180)
    return () => window.clearTimeout(timer)
  }, [api, busy, configuration, content, detail, language])

  const patchConfig = <K extends keyof StudioUniversalConfiguration>(
    group: K, patch: Partial<StudioUniversalConfiguration[K]>,
  ) => setConfiguration((current) => current ? ({
    ...current,
    [group]: { ...(current[group] as object), ...patch },
  }) as StudioUniversalConfiguration : current)

  const saveConfiguration = async (
    nextConfiguration = configuration, nextContent = content,
  ) => {
    if (!detail || !nextConfiguration || !nextContent) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const normalizedContent = normalizedPreviewContent(nextContent)
      const result = await api.post<StudioCheckpointResponse<StudioUniversalDetail>>(`${basePath}/save`, {
        base_sha256: detail.state_sha256,
        configuration: nextConfiguration,
        content: normalizedContent,
      }, { deadlineMs: 60_000 })
      const value = result.creative
      applyDetail(value)
      await renderPreview(value)
      if (result.learning_proposal && result.checkpoint) setLearning({
        proposal: result.learning_proposal,
        summary: result.checkpoint.edit_summary,
        projectLesson: result.checkpoint.project_lesson || '',
      })
      setNotice(!result.checkpoint_created
        ? tr('Creative is already saved; no new learning was created.', 'Креатив уже збережено; нового навчання не створено.')
        : result.checkpoint?.status === 'queued'
          ? tr('Creative saved. Learning is queued for retry.', 'Креатив збережено. Навчання поставлено в чергу на повтор.')
          : tr('Creative saved and the Project skill was updated.', 'Креатив збережено, навичку проєкту оновлено.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const applyTemplate = async (templateId: 'universal_ad' | 'phone_metrics') => {
    if (!detail || templateId === (detail as unknown as { template_id?: string }).template_id) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const value = await api.post<StudioUniversalDetail>(`${basePath}/templates/apply`, {
        base_sha256: detail.state_sha256, template_id: templateId,
      }, { deadlineMs: 60_000 })
      applyDetail(value)
      setNotice(tr('Template replaced the complete editable draft.', 'Шаблон повністю замінив редаговану чернетку.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const uploadAsset = async (slot: string, file: File) => {
    if (!detail) return
    const draftConfiguration = configuration ? structuredClone(configuration) : null
    const draftContent = content ? structuredClone(content) : null
    const asset = detail.assets.find((item) => item.slot === slot)
    if (!asset?.allowed_mime_types.includes(file.type)) {
      setError(tr(`Unsupported file type for ${slot}.`, `Непідтримуваний тип файлу для ${slot}.`))
      return
    }
    setBusy(true)
    setError('')
    try {
      const value = await api.post<StudioUniversalDetail>(`${basePath}/assets/${slot}`, {
        base_sha256: detail.state_sha256,
        mime_type: file.type,
        bytes_base64: await fileAsBase64(file),
      }, { deadlineMs: 90_000 })
      if (draftConfiguration && draftContent) {
        const nextConfiguration = slot === 'background_image' ? {
          ...draftConfiguration,
          background: { ...draftConfiguration.background, mode: 'image' as const },
        } : draftConfiguration
        setDetail(value)
        setConfiguration(nextConfiguration)
        setContent(draftContent)
      } else {
        applyDetail(value)
      }
      try { await renderPreview(value) } catch { /* Disabled optional slots need no immediate render. */ }
      setNotice(tr(`${slot} saved.`, `${slot} збережено.`))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const sourcePexels = async (slot: 'background_image' | 'sticker_object', query: string) => {
    if (!detail) return
    setBusy(true)
    setError('')
    try {
      const value = await api.post<StudioUniversalDetail>(`${basePath}/pexels`, {
        base_sha256: detail.state_sha256,
        slot,
        query,
        isolate: slot === 'sticker_object',
      }, { deadlineMs: 90_000 })
      applyDetail(value)
      await renderPreview(value)
      setNotice(tr('Pexels asset sourced with provenance and rendered.', 'Ресурс Pexels отримано з походженням і відрендерено.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const importConfiguration = async (file: File) => {
    if (!detail) return
    setBusy(true)
    setError('')
    try {
      const value = JSON.parse(await file.text()) as {
        configuration?: StudioUniversalConfiguration
        content?: StudioUniversalContent
      }
      if (!value.configuration || !value.content) throw new Error(tr(
        'Import requires configuration and content objects.',
        'Імпорт потребує об’єкти configuration і content.',
      ))
      await saveConfiguration(value.configuration, value.content)
    } catch (cause) {
      setError((cause as Error).message)
      setBusy(false)
    }
  }

  const exportConfiguration = async () => {
    if (!detail || !configuration || !content) return
    setBusy(true)
    setError('')
    try {
      const normalizedContent = normalizedPreviewContent(content)
      const componentSettings = await api.post<StudioUniversalComponentSettings>(
        `${basePath}/component-settings`, {
          state_sha256: detail.state_sha256,
          configuration,
          content: normalizedContent,
        },
      )
      downloadJson('universal_ad_configuration.json', {
        schema: 'ptw.studio.universal-ad-export.v4',
        template_id: detail.catalog.template_id,
        template_version: detail.catalog.template_version,
        base_state_sha256: detail.state_sha256,
        catalog_sha256: detail.catalog.sha256,
        component_settings: componentSettings,
        configuration,
        content: normalizedContent,
      })
      setNotice(tr(
        'Configuration and component ID metadata exported.',
        'Конфігурацію та метадані ID компонентів експортовано.',
      ))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const approve = async () => {
    if (!detail || !configuration || !content || !changeNote.trim()) return
    setBusy(true)
    setError('')
    try {
      const result = await api.post<StudioCheckpointResponse<StudioUniversalDetail>>(`${basePath}/approve`, {
        base_sha256: detail.state_sha256,
        configuration,
        content: normalizedPreviewContent(content),
        change_note: changeNote.trim(),
      }, { deadlineMs: 90_000 })
      const value = result.creative
      applyDetail(value)
      if (result.learning_proposal && result.checkpoint) setLearning({
        proposal: result.learning_proposal,
        summary: result.checkpoint.edit_summary,
        projectLesson: result.checkpoint.project_lesson || '',
      })
      setChangeNote('')
      setNotice(result.checkpoint?.status === 'queued'
        ? tr(
          'Immutable creative version saved. Learning is queued for retry.',
          'Незмінну версію креативу збережено. Навчання поставлено в чергу на повтор.',
        )
        : tr('Immutable creative and configuration version saved.', 'Незмінну версію креативу й конфігурації збережено.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const showVersion = async (version: number, digest: string) => {
    setBusy(true)
    setError('')
    try {
      const blob = await api.media(`${basePath}/versions/${version}/render`, 'image/png', digest)
      setPreviewUrl(URL.createObjectURL(blob))
      setNotice(tr(`Showing immutable version ${version}.`, `Показано незмінну версію ${version}.`))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const decideLearning = async (decision: 'global' | 'project_only') => {
    if (!learning || !basePath) return
    setBusy(true); setError('')
    try {
      await api.post(`${basePath}/learning/${learning.proposal.proposal_id}`, { decision })
      setNotice(decision === 'global'
        ? tr('The reusable rule was added to the global Studio skill.', 'Повторно використовуване правило додано до глобальної навички Studio.')
        : tr('The lesson remains Project-only.', 'Урок залишено лише для цього проєкту.'))
      setLearning(null)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryGeneration = async () => {
    if (!basePath) return
    setBusy(true); setError('')
    try { await api.post(`${basePath}/retry`, {}); await load() }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryPhoneImage = async () => {
    if (!basePath) return
    setBusy(true); setError('')
    try { await api.post(`${basePath}/phone-screen/retry`, {}); await load() }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const createVariant = async () => {
    if (!projectId || !detail?.source_brief_id || !detail.template_id) return
    const variantTemplateId = (detail as unknown as { template_id: StudioTemplateSummary['template_id'] }).template_id
    if (variantTemplateId === 'phone_metrics' && !variantDirectionOpen) {
      setVariantDirection({ style: '', background: '' }); setVariantDirectionOpen(true); return
    }
    const direction = creativeDirectionFromDraft(variantDirection)
    if (variantTemplateId === 'phone_metrics' && !direction) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ creative: StudioCreativeSummary }>(`/api/v1/studio/projects/${projectId}/creatives`, {
        source_brief_id: detail.source_brief_id, template_id: variantTemplateId,
        ...(variantTemplateId === 'phone_metrics' ? { creative_direction: direction } : {}),
      })
      setVariantDirectionOpen(false)
      onCreative(result.creative.creative_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const createFirstCreative = async (
    brief: ProductBrief, templateId: StudioTemplateSummary['template_id'],
    direction: StudioPhoneHeroCreativeDirection | null = null,
  ) => {
    if (templateId === 'phone_metrics' && !direction) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ creative: StudioCreativeSummary }>(`/api/v1/briefs/${brief.brief_id}/approve`, {
        honor_confirmed: true, template_id: templateId,
        ...(templateId === 'phone_metrics' ? { creative_direction: direction } : {}),
      })
      onCreative(result.creative.creative_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const creativePicker = creatives && creatives.length > 0 && <section className="panel studio-creative-picker" aria-label={tr('Project creatives', 'Креативи проєкту')}>
    <div><small>{tr('PROJECT CREATIVES', 'КРЕАТИВИ ПРОЄКТУ')}</small><strong>{tr('Creative history', 'Історія креативів')}</strong></div>
    <div>{creatives.map((item) => <button key={item.creative_id} className={item.creative_id === creativeId ? 'is-active' : ''} onClick={() => onCreative(item.creative_id)}><strong>#{item.ordinal} · {item.template_id}</strong><small>{item.status} · {item.approved_version_count} {tr('approved', 'схвалено')}</small></button>)}</div>
    {detail?.source_brief_id && (detail.approved_version_count || 0) > 0 && <button className="secondary" disabled={busy} onClick={() => void createVariant()}><Plus />{tr('New creative from this Brief', 'Новий креатив із цього брифу')}</button>}
  </section>

  if (!projectId) return <Empty><ImagePlus className="empty-mark" /><h2>{tr('Choose a Project', 'Оберіть проєкт')}</h2><p>{tr('Every Studio creative belongs to one Project.', 'Кожен креатив Studio належить одному проєкту.')}</p></Empty>
  if (creatives === null) return error
    ? <ErrorState message={error} retry={() => void load()} language={language} />
    : <Loading language={language} />
  if (!creatives.length) {
    if (error) return <ErrorState message={error} retry={() => void load()} language={language} />
    if (approvedBriefs === null || initialTemplates === null) return <Loading language={language} />
    if (!approvedBriefs.length) return <Empty><ImagePlus className="empty-mark" /><h2>{tr('No approved Brief to create from', 'Немає схваленого брифу для створення')}</h2><p>{tr('Complete and approve a Product Brief to unlock the Studio templates.', 'Завершіть і схваліть продуктовий бриф, щоб відкрити шаблони Studio.')}</p></Empty>
    return <div className="studio-page"><section className="panel studio-template-selector" aria-label={tr('Create first creative', 'Створити перший креатив')}><small>{tr('APPROVED BRIEF · FIRST CREATIVE', 'СХВАЛЕНИЙ БРИФ · ПЕРШИЙ КРЕАТИВ')}</small><h2>{tr('Choose a template for your first creative', 'Оберіть шаблон для першого креативу')}</h2><p>{tr('Your Brief is already approved. Selecting a template only reserves and starts its first creative.', 'Ваш бриф уже схвалено. Вибір шаблону лише резервує та запускає його перший креатив.')}</p>{approvedBriefs.map((brief) => <section key={brief.brief_id} className="studio-initial-creative-brief"><h3>{brief.product || brief.document?.product || tr('Approved Product Brief', 'Схвалений продуктовий бриф')}</h3><div className="studio-template-grid">{initialTemplates.map((template) => <button key={template.template_id} type="button" className="studio-template-card" disabled={busy} onClick={() => {
      if (template.template_id === 'phone_metrics') setFirstCreativeSelection({ brief, templateId: 'phone_metrics', direction: { style: '', background: '' } })
      else void createFirstCreative(brief, template.template_id)
    }}><strong>{template.name}</strong><small>{template.canvas.width}×{template.canvas.height}</small><span>{template.description}</span></button>)}</div>
      {firstCreativeSelection?.brief.brief_id === brief.brief_id && <div className="studio-inline-direction"><PhoneHeroDirectionPicker language={language} value={firstCreativeSelection.direction} onChange={(direction) => setFirstCreativeSelection({ ...firstCreativeSelection, direction })} disabled={busy} idPrefix={`first-${brief.brief_id}`} /><button className="primary" disabled={busy || !creativeDirectionFromDraft(firstCreativeSelection.direction)} onClick={() => void createFirstCreative(brief, 'phone_metrics', creativeDirectionFromDraft(firstCreativeSelection.direction))}><Sparkles />{tr('Create Phone Metrics creative', 'Створити креатив Phone Metrics')}</button></div>}
    </section>)}</section></div>
  }

  if (!detail || !configuration || !content) {
    return error
      ? <ErrorState message={error} retry={() => void load()} language={language} />
      : <Loading language={language} />
  }

  const creativeStatus = detail.status || 'draft'
  if (['queued', 'composing', 'generating_image'].includes(creativeStatus)) {
    const stages = ['queued', 'composing', 'generating_image', 'draft']
    const current = stages.indexOf(creativeStatus)
    return <div className="studio-page">{creativePicker}<section className="panel studio-generation-progress" aria-live="polite"><RefreshCcw className="spin" /><small>STUDIO AI</small><h2>{tr('Building the creative', 'Створюємо креатив')}</h2><ol>{stages.map((stage, index) => <li key={stage} className={index <= current ? 'is-active' : ''}>{({ queued: tr('Queued', 'У черзі'), composing: tr('Composing template', 'Наповнення шаблону'), generating_image: tr('Generating iPhone image', 'Генерація зображення iPhone'), draft: tr('Editable draft', 'Редагована чернетка') } as Record<string, string>)[stage]}</li>)}</ol></section></div>
  }

  if (detail.status === 'failed' && !(
    (detail as unknown as { template_id?: string }).template_id === 'phone_metrics'
    && !detail.generation?.creative_direction
  )) return <div className="studio-page">{creativePicker}<ErrorState message={detail.generation?.error_message || tr('Studio composition failed.', 'Не вдалося створити креатив Studio.')} language={language} /><button className="primary" disabled={busy} onClick={() => void retryGeneration()}>{tr('Retry composition', 'Повторити створення')}</button></div>

  if ((detail as unknown as { template_id?: string }).template_id === 'phone_metrics') {
    const phoneFailure = detail.generation?.phone_image?.status === 'failed'
    const hasCreativeDirection = Boolean(detail.generation?.creative_direction)
    return <>{creativePicker}{phoneFailure && <section className="panel studio-phone-retry" role="alert">
      <div><strong>{tr('The creative is ready with fallback artwork', 'Креатив готовий із резервним зображенням')}</strong><p>{detail.generation?.phone_image?.error_message || tr('The automatic iPhone image could not be generated.', 'Не вдалося автоматично згенерувати зображення iPhone.')}</p></div>
      <button className="secondary" disabled={busy || !hasCreativeDirection} onClick={() => void retryPhoneImage()}><RefreshCcw />{tr('Retry iPhone image', 'Повторити зображення iPhone')}</button>
    </section>}<PhoneMetricsStudio
      api={api} language={language}
      basePath={basePath}
      detail={detail as unknown as import('../types').StudioPhoneMetricsDetail}
      onDetail={(value) => applyDetail(value as StudioUniversalDetail)}
      onCheckpoint={(result) => {
        applyDetail(result.creative as unknown as StudioUniversalDetail)
        if (result.learning_proposal && result.checkpoint) setLearning({
          proposal: result.learning_proposal, summary: result.checkpoint.edit_summary,
          projectLesson: result.checkpoint.project_lesson || '',
        })
      }}
    />{variantDirectionOpen && <div className="modal-backdrop" role="presentation"><section className="panel brief-template-dialog" role="dialog" aria-modal="true" aria-label={tr('Choose a direction for the new creative', 'Оберіть напрям нового креативу')}><header><div><small>{tr('NEW PHONE METRICS CREATIVE', 'НОВИЙ КРЕАТИВ PHONE METRICS')}</small><h2>{tr('Choose image direction', 'Оберіть напрям зображення')}</h2></div><button className="icon-button" aria-label={tr('Close', 'Закрити')} onClick={() => setVariantDirectionOpen(false)}><X /></button></header><PhoneHeroDirectionPicker language={language} value={variantDirection} onChange={setVariantDirection} disabled={busy} idPrefix="variant-creative-direction" /><button className="primary large" disabled={busy || !creativeDirectionFromDraft(variantDirection)} onClick={() => void createVariant()}><Plus />{tr('Create creative', 'Створити креатив')}</button></section></div>}{learning && <LearningDialog proposal={learning.proposal} summary={learning.summary} projectLesson={learning.projectLesson} busy={busy} language={language} onDecision={(decision) => void decideLearning(decision)} />}</>
  }

  const setBullet = (index: number, value: string) => setContent((current) => {
    if (!current) return current
    const bullets = [...current.bullets]
    while (bullets.length <= index) bullets.push('')
    bullets[index] = value
    return { ...current, bullets }
  })
  const stickerAvailable = detail.assets.some((asset) => asset.slot === 'sticker_object' && asset.available)
  const backgroundAsset = detail.assets.find((asset) => asset.slot === 'background_image')
  const fontOptions: Array<{ value: StudioUniversalFontFamily; label: string }> = [
    { value: 'Inter', label: tr('Inter — neutral & clear', 'Inter — нейтральний і чіткий') },
    { value: 'Roboto Condensed', label: tr('Roboto Condensed — compact & direct', 'Roboto Condensed — компактний і прямий') },
    { value: 'Manrope', label: tr('Manrope — friendly & modern', 'Manrope — дружній і сучасний') },
    { value: 'Montserrat', label: tr('Montserrat — geometric & bold', 'Montserrat — геометричний і сміливий') },
    { value: 'Source Sans 3', label: tr('Source Sans 3 — clean & readable', 'Source Sans 3 — чистий і читабельний') },
    { value: 'Oswald', label: tr('Oswald — bold & urgent', 'Oswald — сміливий і динамічний') },
    { value: 'Cormorant Garamond', label: tr('Cormorant Garamond — editorial & premium', 'Cormorant Garamond — редакційний і преміальний') },
    { value: 'Cormorant Garamond Italic', label: tr('Cormorant Garamond Italic — expressive editorial', 'Cormorant Garamond Italic — виразний редакційний') },
    { value: 'Lora', label: tr('Lora — warm editorial', 'Lora — теплий редакційний') },
    { value: 'Lora Italic', label: tr('Lora Italic — elegant & human', 'Lora Italic — елегантний і людяний') },
  ]

  return <div className="studio-page universal-studio-page">
    {creativePicker}
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}

    <section className="panel studio-template-selector" aria-label={tr('Post template selector', 'Вибір шаблону допису')}>
      <small>{tr('TEMPLATE', 'ШАБЛОН')}</small><h2>{tr('Choose a preset composition', 'Оберіть готову композицію')}</h2>
      <p>{tr('Changing template replaces all editable copy and assets. Immutable saved versions remain intact.', 'Зміна шаблону замінює весь редагований текст і ресурси. Незмінні збережені версії залишаються цілими.')}</p>
      <div className="studio-template-grid">
        <button type="button" className="studio-template-card is-active" disabled={busy} onClick={() => void applyTemplate('universal_ad')}><strong>{tr('Universal ad', 'Універсальна реклама')}</strong><small>1080×1080</small><span>{tr('Square, flexible post composition.', 'Квадратна гнучка композиція допису.')}</span></button>
        <button type="button" className="studio-template-card" disabled={busy} onClick={() => void applyTemplate('phone_metrics')}><strong>{tr('Phone & metrics', 'Телефон і метрики')}</strong><small>1080×1350</small><span>{tr('Fixed Natal phone, three metrics, and a CTA band.', 'Фіксований телефон Natal, три метрики та CTA-смуга.')}</span></button>
      </div>
    </section>
    <section className="studio-commandbar universal-commandbar" aria-label={tr('Post editor controls', 'Керування редактором допису')}>
        <div><small>{tr('FIXED STRUCTURE', 'ФІКСОВАНА СТРУКТУРА')}</small><strong>universal_ad · v{detail.catalog.template_version}</strong></div>
      {tuneMode && <button className="secondary studio-tune-trigger" disabled={busy} onClick={() => setTuneOpen(true)}><WandSparkles />{tr('Feedback & iterations', 'Відгук та ітерації')}</button>}
      <button className="secondary" disabled={busy} onClick={() => importRef.current?.click()}><Upload />{tr('Import config', 'Імпорт конфігурації')}</button>
      <input ref={importRef} className="visually-hidden" type="file" accept="application/json,.json" onChange={(event) => {
        const file = event.target.files?.[0]
        if (file) void importConfiguration(file)
        event.currentTarget.value = ''
      }} />
      <button className="secondary" disabled={busy} onClick={() => void exportConfiguration()}><Download />{tr('Export config + IDs', 'Експорт конфігурації + ID')}</button>
      <button className="primary" disabled={busy} onClick={() => void saveConfiguration()}><Save />{tr('Save creative', 'Зберегти креатив')}</button>
    </section>

    <div className="studio-meta">
      <span>{detail.catalog.semantic_roles.length} {tr('stable semantic roles', 'сталих семантичних ролей')}</span>
      <code title={detail.state_sha256}>{detail.state_sha256.slice(0, 12)}</code>
      {busy && <span><RefreshCcw className="spin" /> {tr('Working…', 'Обробка…')}</span>}
      {previewBusy && <span><RefreshCcw className="spin" /> {tr('Updating live preview…', 'Оновлення живого прев’ю…')}</span>}
      {!previewBusy && draftPreviewed && <span className="studio-live-state">{tr('Live preview up to date', 'Живе прев’ю оновлено')}</span>}
      {previewError && <span className="studio-preview-error">{previewError}</span>}
    </div>

    <section className="panel universal-component-dock" aria-labelledby="studio-components-title">
      <header>
        <div><small>{tr('CREATIVE COMPONENTS', 'КОМПОНЕНТИ КРЕАТИВУ')}</small><h2 id="studio-components-title">{tr('Build the composition at a glance', 'Керуйте композицією з одного погляду')}</h2></div>
        <p>{tr('Required roles stay visible. Toggle optional roles here and judge the result immediately in the live preview.', 'Обов’язкові ролі завжди видимі. Перемикайте необов’язкові ролі тут і одразу оцінюйте результат у живому прев’ю.')}</p>
      </header>
      <div className="universal-component-grid">
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Background', 'Фон')}</strong><small>{tr('Mood & contrast', 'Настрій і контраст')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Headline', 'Заголовок')}</strong><small>{tr('Primary hook', 'Головний хук')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Supporting copy', 'Пояснення')}</strong><small>{tr('Reason to care', 'Причина зупинитись')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Offer', 'Пропозиція')}</strong><small>{tr('Protected value', 'Захищена цінність')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>CTA</strong><small>{tr('Next action', 'Наступна дія')}</small></div>
        <label className={`universal-component-card is-toggle ${configuration.bullets.enabled ? 'is-active' : ''}`}>
          <input aria-label="Enable bullets" type="checkbox" checked={configuration.bullets.enabled} onChange={(event) => patchConfig('bullets', { enabled: event.target.checked })} />
          <span>{tr('OPTIONAL', 'ОПЦІЙНО')}</span><strong>{tr('Benefits', 'Переваги')}</strong><small>{configuration.bullets.enabled ? tr('Visible', 'Видимі') : tr('Hidden', 'Приховані')}</small><b className="universal-component-switch" aria-hidden="true"><i /></b>
        </label>
        <label className={`universal-component-card is-toggle ${configuration.sticker.enabled ? 'is-active' : ''} ${!stickerAvailable && !detail.pexels_available ? 'is-unavailable' : ''}`}>
          <input aria-label="Enable sticker" type="checkbox" checked={configuration.sticker.enabled} disabled={busy || (!stickerAvailable && !detail.pexels_available)} onChange={(event) => {
            if (event.target.checked && !stickerAvailable) {
              void sourcePexels('sticker_object', stickerQuery)
            } else {
              patchConfig('sticker', { enabled: event.target.checked })
            }
          }} />
          <span>{tr('OPTIONAL', 'ОПЦІЙНО')}</span><strong>{tr('Sticker', 'Стікер')}</strong><small>{!stickerAvailable ? detail.pexels_available ? tr('Click to source object', 'Натисніть, щоб знайти об’єкт') : tr('Pexels unavailable', 'Pexels недоступний') : configuration.sticker.enabled ? tr('Visible', 'Видимий') : tr('Hidden', 'Прихований')}</small><b className="universal-component-switch" aria-hidden="true"><i /></b>
        </label>
        <div className="universal-component-card is-required"><span>{tr('FIXED', 'ФІКСОВАНО')}</span><strong>Natal</strong><small>{tr('Canonical brand lock-up', 'Канонічний бренд-локап')}</small></div>
      </div>
    </section>

    <section className="universal-studio-workspace">
      <main className="studio-canvas-panel universal-canvas-panel">
        <header><div><small>{tr('LIVE POST RENDER', 'ЖИВИЙ РЕНДЕР ДОПИСУ')}</small><h2>{tr('Every control updates this creative', 'Кожне налаштування оновлює цей креатив')}</h2></div><span className="studio-live-badge">{tr('LIVE PREVIEW', 'ЖИВЕ ПРЕВ’Ю')}</span></header>
        <div className={`studio-preview-feedback ${previewError ? 'is-error' : ''}`} aria-live="polite">
          {previewBusy && <><RefreshCcw className="spin" /> {tr('Rendering your changes…', 'Рендеримо ваші зміни…')}</>}
          {!previewBusy && previewError && <>{tr('Preview could not update:', 'Не вдалося оновити прев’ю:')} {previewError}</>}
          {!previewBusy && !previewError && draftPreviewed && <>{tr('Preview matches your unsaved changes', 'Прев’ю відповідає незбереженим змінам')}</>}
          {!previewBusy && !previewError && !draftPreviewed && <>{tr('Preview matches the saved setup', 'Прев’ю відповідає збереженим налаштуванням')}</>}
        </div>
        <div className="studio-preview-grid">
          <figure aria-busy={previewBusy}>{previewUrl
            ? <img src={previewUrl} alt={tr('Current universal advertising creative', 'Поточний універсальний рекламний креатив')} />
            : <div className="studio-preview-empty"><ImagePlus /><span>{tr('Render unavailable', 'Рендер недоступний')}</span></div>}
          </figure>
        </div>
      </main>

      <aside className="universal-controls">
        <section className="panel universal-section">
          <small>{tr('SEMANTIC CONTENT', 'СЕМАНТИЧНИЙ ВМІСТ')}</small><h2>{tr('Compact ad message', 'Компактне рекламне повідомлення')}</h2>
          <label><span>{tr('Hero Title', 'Головний заголовок')}</span><textarea aria-label="Hero Title" rows={3} value={content.hero_title} onChange={(event) => setContent({ ...content, hero_title: event.target.value })} /></label>
          <label><span>{tr('Supporting Text', 'Пояснювальний текст')}</span><textarea aria-label="Supporting Text" rows={3} value={content.supporting_text} onChange={(event) => setContent({ ...content, supporting_text: event.target.value })} /></label>
          <label><span>{tr('Offer', 'Пропозиція')}</span><textarea aria-label="Offer" rows={2} maxLength={160} value={content.offer} onChange={(event) => setContent({ ...content, offer: event.target.value })} /></label>
          <label><span>CTA</span><input aria-label="CTA" value={content.cta} onChange={(event) => setContent({ ...content, cta: event.target.value })} /></label>
          {configuration.bullets.enabled && <div className="universal-bullets">
            <label><span>{tr('Bullet style', 'Стиль маркера')}</span><select
              aria-label="Bullet style" value={configuration.bullets.style}
              onChange={(event) => patchConfig('bullets', { style: event.target.value as StudioUniversalConfiguration['bullets']['style'] })}
            >
              <option value="check">{tr('Check mark', 'Позначка')}</option>
              <option value="circle">{tr('Filled circle', 'Заповнене коло')}</option>
              <option value="circle_outline">{tr('Outlined circle', 'Контурне коло')}</option>
            </select></label>
            {[0, 1, 2].map((index) => <input key={index} aria-label={`Bullet ${index + 1}`} placeholder={`${tr('Bullet', 'Пункт')} ${index + 1}`} value={content.bullets[index] || ''} onChange={(event) => setBullet(index, event.target.value)} />)}
          </div>}
          {!configuration.bullets.enabled && <p className="universal-section-note">{tr('Benefits are hidden. Enable that component above when the message needs scannable proof points.', 'Переваги приховані. Увімкніть цей компонент вище, коли повідомленню потрібні короткі докази.')}</p>}
        </section>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('BACKGROUND', 'ФОН')}</small><strong>{tr('Mood and contrast', 'Настрій і контраст')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body"><div className="universal-field-grid">
            <label><span>{tr('Mode', 'Режим')}</span><select aria-label="Background mode" value={configuration.background.mode} onChange={(event) => patchConfig('background', { mode: event.target.value as StudioUniversalConfiguration['background']['mode'] })}><option value="solid">solid</option><option value="texture">texture</option><option value="image">image</option></select></label>
            <ColorField label={tr('Background color', 'Базовий колір')} value={configuration.background.color} onChange={(value) => patchConfig('background', { color: value })} />
            {configuration.background.mode === 'texture' && <>
              <label><span>{tr('Texture', 'Текстура')}</span><select aria-label="Texture" value={configuration.background.texture} onChange={(event) => patchConfig('background', { texture: event.target.value as StudioUniversalConfiguration['background']['texture'] })}>
                {detail.catalog.variation.texture_presets.map((texture) => <option key={texture} value={texture}>{texture}</option>)}
              </select></label>
              <RangeField label={tr('Texture intensity', 'Інтенсивність текстури')} value={configuration.background.texture_intensity} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { texture_intensity: value })} />
            </>}
            {configuration.background.mode === 'image' && <>
              <label><span>{tr('Image layout', 'Розміщення зображення')}</span><select value={configuration.background.image_layout} onChange={(event) => patchConfig('background', { image_layout: event.target.value as StudioUniversalConfiguration['background']['image_layout'] })}>{['full', 'left', 'right', 'top', 'bottom'].map((item) => <option key={item}>{item}</option>)}</select></label>
              {configuration.background.image_layout !== 'full' && <label><span>{tr('Image / background mix', 'Співвідношення зображення / фону')}</span><select
                aria-label="Image background mix" value={configuration.background.image_percent}
                onChange={(event) => patchConfig('background', { image_percent: Number(event.target.value) as 25 | 75 })}
              ><option value={75}>75% image · 25% background</option><option value={25}>25% image · 75% background</option></select></label>}
              <label><span>{tr('Fit', 'Вписування')}</span><select value={configuration.background.image_fit} onChange={(event) => patchConfig('background', { image_fit: event.target.value as 'cover' | 'contain' })}><option>cover</option><option>contain</option></select></label>
              <NumberField label="Focal X" value={configuration.background.focal_x} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { focal_x: value })} />
              <NumberField label="Focal Y" value={configuration.background.focal_y} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { focal_y: value })} />
              <div className="universal-inline-upload universal-field-span">
                <div><strong>{tr('Sample image', 'Тестове зображення')}</strong><span>{backgroundAsset?.available ? `${backgroundAsset.mime_type} · ${String(backgroundAsset.source?.origin || 'stored')}` : tr('No image supplied', 'Зображення не додано')}</span></div>
                <label className="secondary"><Upload />{tr('Upload sample', 'Завантажити приклад')}<input
                  aria-label="Upload sample background image" type="file"
                  accept={backgroundAsset?.allowed_mime_types.join(',') || 'image/jpeg,image/png,image/webp'}
                  onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset('background_image', file); event.currentTarget.value = '' }}
                /></label>
              </div>
            </>}
            <ColorField label={tr('Overlay color', 'Колір накладення')} value={configuration.background.overlay_color} onChange={(value) => patchConfig('background', { overlay_color: value })} />
            <RangeField label={tr('Overlay opacity', 'Прозорість накладення')} value={configuration.background.overlay_opacity} min={0} max={0.85} step={0.05} onChange={(value) => patchConfig('background', { overlay_opacity: value })} />
          </div></div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('HIERARCHY & CTA', 'ІЄРАРХІЯ ТА CTA')}</small><strong>{tr('Type, layout and action', 'Типографіка, макет і дія')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body"><div className="universal-field-grid">
            <label><span>{tr('Headline font', 'Шрифт заголовка')}</span><select aria-label="Headline font family" value={configuration.typography.font_family} onChange={(event) => patchConfig('typography', { font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <label><span>{tr('Supporting font', 'Шрифт пояснення')}</span><select aria-label="Supporting font family" value={configuration.typography.supporting_font_family} onChange={(event) => patchConfig('typography', { supporting_font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <label><span>{tr('Offer font', 'Шрифт пропозиції')}</span><select aria-label="Offer font family" value={configuration.typography.offer_font_family} onChange={(event) => patchConfig('typography', { offer_font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <label><span>{tr('Benefits font mood', 'Настрій шрифту переваг')}</span><select aria-label="Benefits font family" value={configuration.typography.benefits_font_family} onChange={(event) => patchConfig('typography', { benefits_font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <label><span>{tr('Alignment', 'Вирівнювання')}</span><select aria-label="Text alignment" value={configuration.typography.alignment} onChange={(event) => patchConfig('typography', { alignment: event.target.value as 'left' | 'center' })}><option>left</option><option>center</option></select></label>
            <NumberField label="Hero size" value={configuration.typography.hero_size} min={64} max={180} onChange={(value) => patchConfig('typography', { hero_size: value })} />
            <NumberField label="Hero weight" value={configuration.typography.hero_weight} min={400} max={900} step={100} onChange={(value) => patchConfig('typography', { hero_weight: value })} />
            <NumberField label="Supporting size" value={configuration.typography.supporting_size} min={22} max={52} onChange={(value) => patchConfig('typography', { supporting_size: value })} />
            <NumberField label="Offer size" value={configuration.typography.offer_size} min={18} max={52} onChange={(value) => patchConfig('typography', { offer_size: value })} />
            <NumberField label="Benefits size" value={configuration.typography.benefits_size} min={16} max={48} onChange={(value) => patchConfig('typography', { benefits_size: value })} />
            <ColorField label={tr('Text color', 'Колір тексту')} value={configuration.typography.text_color} onChange={(value) => patchConfig('typography', { text_color: value })} />
            <NumberField label="Content X" value={configuration.layout.content_x} min={48} max={520} onChange={(value) => patchConfig('layout', { content_x: value })} />
            <NumberField label="Content Y" value={configuration.layout.content_y} min={72} max={360} onChange={(value) => patchConfig('layout', { content_y: value })} />
            <NumberField label="Content width" value={configuration.layout.content_width} min={420} max={936} onChange={(value) => patchConfig('layout', { content_width: value })} />
            <NumberField label="Vertical gap" value={configuration.layout.gap} min={8} max={56} onChange={(value) => patchConfig('layout', { gap: value })} />
            <label><span>{tr('CTA style', 'Стиль CTA')}</span><select aria-label="CTA style" value={configuration.cta.style} onChange={(event) => patchConfig('cta', { style: event.target.value as StudioUniversalConfiguration['cta']['style'] })}>
              <option value="filled">filled</option><option value="gradient">gradient</option><option value="reverse">reverse</option><option value="link">link</option><option value="outlined">outlined</option>
            </select></label>
            <label><span>{tr('CTA placement', 'Розміщення CTA')}</span><select aria-label="CTA placement" value={configuration.cta.position} onChange={(event) => patchConfig('cta', { position: event.target.value as StudioUniversalConfiguration['cta']['position'] })}>
              <option value="below_text">{tr('Below text', 'Під текстом')}</option>
              <option value="bottom_left">{tr('Bottom left', 'Знизу ліворуч')}</option>
              <option value="bottom_right">{tr('Bottom right', 'Знизу праворуч')}</option>
            </select></label>
            <ColorField label={tr('CTA background color', 'Колір фону CTA')} value={configuration.cta.background_color} onChange={(value) => patchConfig('cta', { background_color: value })} />
            <ColorField label={tr('CTA text color', 'Колір тексту CTA')} value={configuration.cta.text_color} onChange={(value) => patchConfig('cta', { text_color: value })} />
            <label><span>{tr('CTA font', 'Шрифт CTA')}</span><select aria-label="CTA font family" value={configuration.cta.font_family} onChange={(event) => patchConfig('cta', { font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <NumberField label={tr('CTA font size', 'Розмір шрифту CTA')} value={configuration.cta.font_size} min={18} max={42} onChange={(value) => patchConfig('cta', { font_size: value })} />
            <NumberField label="CTA radius" value={configuration.cta.radius} min={0} max={40} onChange={(value) => patchConfig('cta', { radius: value })} />
          </div></div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('OPTIONAL SETTINGS', 'НАЛАШТУВАННЯ ОПЦІЙ')}</small><strong>{tr('Sticker placement', 'Розміщення стікера')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body">
          {configuration.sticker.enabled && <div className="universal-field-grid">
            <label><span>{tr('Position', 'Позиція')}</span><select aria-label="Sticker position" value={configuration.sticker.position} onChange={(event) => patchConfig('sticker', { position: event.target.value as StudioUniversalConfiguration['sticker']['position'] })}>
              <option value="top_left">{tr('Top left', 'Зверху ліворуч')}</option><option value="top_right">{tr('Top right', 'Зверху праворуч')}</option>
              <option value="bottom_left">{tr('Bottom left', 'Знизу ліворуч')}</option><option value="bottom_right">{tr('Bottom right', 'Знизу праворуч')}</option>
              <option value="right_edge">{tr('Sticks from right', 'Виступає справа')}</option><option value="bottom_edge">{tr('Sticks from bottom', 'Виступає знизу')}</option>
              <option value="bullet_list">{tr('Sticks to benefits', 'Кріпиться до переваг')}</option><option value="hero_title">{tr('Sticks to hero title', 'Кріпиться до заголовка')}</option>
              <option value="cta">{tr('Sticks to CTA', 'Кріпиться до CTA')}</option>
            </select></label>
            <NumberField label="Sticker rotation" value={configuration.sticker.rotation} min={-18} max={18} onChange={(value) => patchConfig('sticker', { rotation: value })} />
            <NumberField label="Sticker width" value={configuration.sticker.width} min={120} max={720} onChange={(value) => patchConfig('sticker', { width: value })} />
            <NumberField label="Object scale" value={configuration.sticker.object_scale} min={0.35} max={1.5} step={0.05} onChange={(value) => patchConfig('sticker', { object_scale: value })} />
            <NumberField label="Adjust from right" value={configuration.sticker.offset_right} min={-720} max={720} onChange={(value) => patchConfig('sticker', { offset_right: value })} />
            <NumberField label="Adjust from bottom" value={configuration.sticker.offset_bottom} min={-720} max={720} onChange={(value) => patchConfig('sticker', { offset_bottom: value })} />
          </div>}
          {!configuration.sticker.enabled && <p className="universal-section-note">{tr('Enable Sticker in the component dock to reveal its placement controls.', 'Увімкніть «Стікер» у панелі компонентів, щоб побачити налаштування розміщення.')}</p>}
          </div>
        </details>
      </aside>
    </section>

    <section className="panel universal-assets-panel">
      <small>{tr('FIXED ASSET SLOTS', 'ФІКСОВАНІ МІСЦЯ ДЛЯ РЕСУРСІВ')}</small><h2>{tr('Background and sticker object · Natal is fixed', 'Фон і об’єкт стікера · Natal зафіксовано')}</h2>
      <div className="studio-asset-list">{detail.assets.filter((asset) => asset.slot !== 'logo').map((asset) => <div key={asset.slot}><div><strong>{asset.slot}</strong><span>{asset.available ? `${asset.mime_type} · ${Math.round((asset.byte_count || 0) / 1024)} KB · ${String(asset.source?.origin || 'stored')}` : tr('Optional · not supplied', 'Необов’язково · не надано')}</span></div>{asset.slot === 'sticker_object' ? <span className="studio-note">{tr('Pexels photograph only', 'Лише фотографія Pexels')}</span> : <label className="secondary"><Upload />{tr('Upload', 'Завантажити')}<input aria-label={`Upload ${asset.slot} asset`} type="file" accept={asset.allowed_mime_types.join(',')} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset(asset.slot, file); event.currentTarget.value = '' }} /></label>}</div>)}</div>
      <div className="universal-pexels-grid">
        <label><span>{tr('Pexels background query', 'Запит фону Pexels')}</span><input aria-label="Pexels background query" value={backgroundQuery} onChange={(event) => setBackgroundQuery(event.target.value)} /></label>
        <button className="secondary" disabled={busy || !detail.pexels_available || backgroundQuery.trim().length < 2} onClick={() => void sourcePexels('background_image', backgroundQuery)}><Search />{tr('Source background', 'Знайти фон')}</button>
        <label><span>{tr('Pexels sticker object query', 'Запит об’єкта стікера Pexels')}</span><input aria-label="Pexels sticker query" value={stickerQuery} onChange={(event) => setStickerQuery(event.target.value)} /></label>
        <button className="secondary" disabled={busy || !detail.pexels_available || stickerQuery.trim().length < 2} onClick={() => void sourcePexels('sticker_object', stickerQuery)}><Search />{tr('Source & isolate object', 'Знайти й ізолювати об’єкт')}</button>
      </div>
      {!detail.pexels_available && <p className="studio-note">{tr('Pexels is not configured in this local runtime. The sticker stays unavailable; background upload remains available.', 'Pexels не налаштовано в цьому локальному середовищі. Стікер недоступний; завантаження фону доступне.')}</p>}
    </section>

    <section className="panel studio-approval universal-approval">
      <div><small>{tr('IMMUTABLE EXPERIMENT ASSET', 'НЕЗМІННИЙ РЕСУРС ЕКСПЕРИМЕНТУ')}</small><h2>{tr('Store exact creative + configuration', 'Зберегти точний креатив і конфігурацію')}</h2><p>{tr('Approval stores the rendered PNG, universal configuration, semantic content, asset digests, and internal template digest together.', 'Схвалення разом зберігає PNG, універсальну конфігурацію, семантичний вміст, digest ресурсів і внутрішній digest шаблону.')}</p></div>
      <label><span>{tr('Version note', 'Примітка до версії')}</span><input value={changeNote} onChange={(event) => setChangeNote(event.target.value)} /></label>
      <button className="primary large" disabled={busy || !changeNote.trim()} onClick={() => void approve()}><Check />{tr('Approve creative', 'Схвалити креатив')}</button>
      {detail.versions.length > 0 && <ol className="universal-version-list">{detail.versions.map((version) => <li key={version.version}><strong>v{version.version}</strong><span>{version.change_note}</span><button className="secondary" onClick={() => void showVersion(version.version, version.render_sha256)}>{tr('View', 'Переглянути')}</button></li>)}</ol>}
    </section>
    {tuneMode && <StudioTuneWizard api={api} language={language} open={tuneOpen} studioPreviewUrl={previewUrl} onClose={() => setTuneOpen(false)} />}
    {learning && <LearningDialog proposal={learning.proposal} summary={learning.summary} projectLesson={learning.projectLesson} busy={busy} language={language} onDecision={(decision) => void decideLearning(decision)} />}
  </div>
}
