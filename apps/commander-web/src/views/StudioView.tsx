import { MarketingApproachBadge } from '../components/MarketingApproach'
import { ImagePlus, Plus, RefreshCcw, Sparkles, WandSparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { PhoneMetricsStudio } from '../components/studio/PhoneMetricsStudio'
import { PhoneHeroDirectionPicker, creativeDirectionFromDraft, type PhoneHeroDirectionDraft } from '../components/studio/PhoneHeroDirectionPicker'
import { StudioTuneWizard } from '../components/studio/StudioTuneWizard'
import { PostPublishing } from '../components/PostPublishing'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import { operationFailureMessage } from '../operation-errors'
import { TemplateImage } from '../components/TemplateImage'
import type {
  ProductBrief, StudioCreativeSummary, StudioPhoneHeroCreativeDirection, AcceptedPostTemplate,
  StudioPhoneMetricsDetail,
} from '../types'

export function StudioView({
  api, language, projectId = null, creativeId = null, onCreative = () => {}, tuneMode = false,
}: {
  api: ApiClient
  language: Language
  projectId?: string | null
  creativeId?: string | null
  onCreative?: (creativeId: string) => void
  tuneMode?: boolean
}) {
  const [detail, setDetail] = useState<StudioPhoneMetricsDetail | null>(null)
  const [creatives, setCreatives] = useState<StudioCreativeSummary[] | null>(null)
  const [approvedBriefs, setApprovedBriefs] = useState<ProductBrief[] | null>(null)
  const [templates, setTemplates] = useState<AcceptedPostTemplate[] | null>(null)
  const [firstSelection, setFirstSelection] = useState<{
    brief: ProductBrief; template: AcceptedPostTemplate; direction: PhoneHeroDirectionDraft
  } | null>(null)
  const [variantDirection, setVariantDirection] = useState<PhoneHeroDirectionDraft>({ style: '', background: '' })
  const [variantTemplates, setVariantTemplates] = useState<AcceptedPostTemplate[] | null>(null)
  const [variantTemplate, setVariantTemplate] = useState<AcceptedPostTemplate | null>(null)
  const [variantError, setVariantError] = useState('')
  const [variantDirectionOpen, setVariantDirectionOpen] = useState(false)
  const [tuneOpen, setTuneOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const loadGeneration = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const basePath = projectId && detail
    ? `/api/v1/studio/projects/${projectId}/creatives/${detail.creative_id}`
    : ''

  const load = async () => {
    const generation = ++loadGeneration.current
    if (!projectId) {
      setCreatives([]); setApprovedBriefs([]); setTemplates([]); setDetail(null)
      return
    }
    setBusy(true); setError('')
    try {
      const list = await api.get<{ items: StudioCreativeSummary[] }>(
        `/api/v1/studio/projects/${projectId}/creatives`,
      )
      if (generation !== loadGeneration.current) return
      setCreatives(list.items)
      const selectedId = list.items.some((item) => item.creative_id === creativeId)
        ? creativeId : list.items[0]?.creative_id || null
      if (!selectedId) {
        const [briefResult, templateResult] = await Promise.all([
          api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?project_id=${projectId}&limit=100`),
          api.get<{ items: AcceptedPostTemplate[] }>('/api/v1/templates?surface=post', { deadlineMs: 120_000 }),
        ])
        if (generation !== loadGeneration.current) return
        setApprovedBriefs(briefResult.items.filter((brief) => (
          brief.approved && brief.status === 'completed' && Boolean(brief.document)
        )))
        setTemplates(templateResult.items)
        setDetail(null)
        return
      }
      if (selectedId !== creativeId) onCreative(selectedId)
      const value = await api.get<StudioPhoneMetricsDetail>(
        `/api/v1/studio/projects/${projectId}/creatives/${selectedId}`,
        { deadlineMs: 60_000 },
      )
      if (generation !== loadGeneration.current) return
      setDetail(value)
    } catch (cause) {
      if (generation === loadGeneration.current) setError((cause as Error).message)
    } finally {
      if (generation === loadGeneration.current) setBusy(false)
    }
  }

  useEffect(() => {
    setCreatives(null); setApprovedBriefs(null); setTemplates(null); setDetail(null); setError('')
    void load()
    return () => { loadGeneration.current += 1 }
  }, [api, projectId, creativeId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const status = detail?.status
    if (!status || !['queued', 'composing', 'generating_image'].includes(status)) return
    const timer = window.setInterval(() => void load(), 1500)
    return () => window.clearInterval(timer)
  }, [detail?.status, projectId, creativeId]) // eslint-disable-line react-hooks/exhaustive-deps

  const createCreative = async (
    brief: ProductBrief, template: AcceptedPostTemplate, direction: StudioPhoneHeroCreativeDirection | null,
  ) => {
    if (!direction) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ creative: StudioCreativeSummary }>(
        `/api/v1/briefs/${brief.brief_id}/approve`, {
          honor_confirmed: true,
          template_id: template.template_id,
          template_reference: { surface: 'post', template_id: template.template_id,
            template_version: template.template_version, template_sha256: template.template_sha256 },
          creative_direction: direction,
        },
      )
      onCreative(result.creative.creative_id)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const createVariant = async () => {
    if (!projectId || !detail?.source_brief_id) return
    if (!variantDirectionOpen) {
      setVariantDirection({ style: '', background: '' }); setVariantTemplate(null); setVariantTemplates(null); setVariantError(''); setVariantDirectionOpen(true)
      try {
        const value = await api.get<{ items: AcceptedPostTemplate[] }>('/api/v1/templates?surface=post', { deadlineMs: 120_000 })
        setVariantTemplates(value.items)
      } catch (cause) { setVariantError((cause as Error).message) }
      return
    }
    const direction = creativeDirectionFromDraft(variantDirection)
    if (!direction || !variantTemplate) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ creative: StudioCreativeSummary }>(
        `/api/v1/studio/projects/${projectId}/creatives`, {
          source_brief_id: detail.source_brief_id,
          template_id: variantTemplate.template_id,
          template_reference: { surface: 'post', template_id: variantTemplate.template_id,
            template_version: variantTemplate.template_version, template_sha256: variantTemplate.template_sha256 },
          creative_direction: direction,
        },
      )
      setVariantDirectionOpen(false)
      onCreative(result.creative.creative_id)
    } catch (cause) { setVariantError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const cloneApprovedPost = async () => {
    if (!projectId || !detail?.versions.length) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ creative: StudioCreativeSummary }>(
        `/api/v1/studio/projects/${projectId}/creatives/clones`, {
          request_id: crypto.randomUUID(),
          source_creative_id: detail.creative_id,
          source_version: Math.max(...detail.versions.map((item) => item.version)),
        },
      )
      onCreative(result.creative.creative_id)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const retry = async (path: string) => {
    setBusy(true); setError('')
    try { await api.post(path, {}); await load() }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const creativePicker = creatives && creatives.length > 0 && <section className="post-contextbar" aria-label={tr('Project creatives', 'Креативи проєкту')}>
    <label>{tr('Post', 'Допис')} <select aria-label={tr('Select Post', 'Обрати допис')} value={detail?.creative_id || creativeId || ''} onChange={event => onCreative(event.target.value)}>{creatives.map(item => <option key={item.creative_id} value={item.creative_id}>#{item.ordinal} · {item.status === 'draft' ? tr('Draft', 'Чернетка') : item.status}</option>)}</select></label>
    {detail && <MarketingApproachBadge value={detail.marketing_approach} language={language} />}
    {detail?.source_brief_id && detail.approved_version_count > 0 && <details className="post-more"><summary>{tr('More actions', 'Інші дії')}</summary><button className="secondary" disabled={busy} onClick={() => void cloneApprovedPost()}><Plus />{tr('Clone latest approved Post', 'Клонувати останній затверджений допис')}</button><button className="secondary" disabled={busy} onClick={() => void createVariant()}><Sparkles />{tr('Generate another from Brief', 'Згенерувати інший із брифу')}</button></details>}
    {tuneMode && <button className="ghost studio-tune-trigger" disabled={busy} onClick={() => setTuneOpen(true)}><WandSparkles />{tr('Feedback & iterations', 'Відгук та ітерації')}</button>}
  </section>

  if (!projectId) return <Empty><ImagePlus className="empty-mark" /><h2>{tr('Choose a Project', 'Оберіть проєкт')}</h2><p>{tr('Every Studio creative belongs to one Project.', 'Кожен креатив Studio належить одному проєкту.')}</p></Empty>
  if (creatives === null) return error
    ? <ErrorState message={error} retry={() => void load()} language={language} />
    : <Loading language={language} />
  if (!creatives.length) {
    if (error) return <ErrorState message={error} retry={() => void load()} language={language} />
    if (approvedBriefs === null || templates === null) return <Loading language={language} />
    if (!approvedBriefs.length) return <Empty><ImagePlus className="empty-mark" /><h2>{tr('No approved Brief to create from', 'Немає схваленого брифу для створення')}</h2><p>{tr('Complete and approve a Product Brief to unlock Post Studio.', 'Завершіть і схваліть продуктовий бриф, щоб відкрити Post Studio.')}</p></Empty>
    if (!templates.length) return <ErrorState message={tr('No accepted Post templates are available.', 'Немає доступних прийнятих шаблонів дописів.')} retry={() => void load()} language={language} />
    return <div className="studio-page"><section className="panel studio-template-selector">
      <small>{tr('APPROVED BRIEF · FIRST CREATIVE', 'СХВАЛЕНИЙ БРИФ · ПЕРШИЙ КРЕАТИВ')}</small>
      <h2>{tr('Create your first Post', 'Створіть перший допис')}</h2>
      {approvedBriefs.map((brief) => <section key={brief.brief_id} className="studio-initial-creative-brief">
        <h3>{brief.product || brief.document?.product || tr('Approved Product Brief', 'Схвалений продуктовий бриф')}</h3>
        <div className="post-template-choices">{templates.map((template) => <article key={`${template.template_id}:${template.template_version}`} className={firstSelection?.brief.brief_id === brief.brief_id && firstSelection.template.template_sha256 === template.template_sha256 ? 'is-selected' : ''}>
          <TemplateImage api={api} preview={template.previews?.desktop} label={template.name} language={language} />
          <button type="button" className="secondary" aria-pressed={firstSelection?.brief.brief_id === brief.brief_id && firstSelection.template.template_sha256 === template.template_sha256} disabled={busy} onClick={() => setFirstSelection({ brief, template, direction: { style: '', background: '' } })}>{template.name} · v{template.template_version}</button>
          <small>{template.description}</small>
        </article>)}</div>
        {firstSelection?.brief.brief_id === brief.brief_id && <div className="studio-inline-direction">
          <PhoneHeroDirectionPicker language={language} value={firstSelection.direction} onChange={(direction) => setFirstSelection({ ...firstSelection, direction })} disabled={busy} idPrefix={`first-${brief.brief_id}`} />
          <button className="primary" disabled={busy || !creativeDirectionFromDraft(firstSelection.direction)} onClick={() => void createCreative(brief, firstSelection.template, creativeDirectionFromDraft(firstSelection.direction))}><Sparkles />{tr('Create creative', 'Створити креатив')}</button>
        </div>}
      </section>)}
    </section></div>
  }
  if (!detail) return error
    ? <ErrorState message={error} retry={() => void load()} language={language} />
    : <Loading language={language} />

  if (['queued', 'composing', 'generating_image'].includes(detail.status)) {
    return <div className="studio-page">{creativePicker}<section className="panel studio-generation-progress" aria-live="polite"><RefreshCcw className="spin" /><small>STUDIO AI</small><h2>{tr('Building the creative', 'Створюємо креатив')}</h2></section></div>
  }
  if (detail.status === 'failed' && detail.generation?.creative_direction) {
    return <div className="studio-page">{creativePicker}<ErrorState
      message={operationFailureMessage({ operation: 'studio', detail: detail.generation?.error_message, code: detail.generation?.error_type, reference: detail.creative_id }, language)}
      retry={() => void retry(`${basePath}/retry`)} language={language}
    /></div>
  }

  const phoneFailure = detail.generation?.phone_image?.status === 'failed'
  return <>
    {creativePicker}
    {phoneFailure && <section className="panel studio-phone-retry" role="alert">
      <div><strong>{tr('The creative is ready with fallback artwork', 'Креатив готовий із резервним зображенням')}</strong><p>{operationFailureMessage({ operation: 'phone_image', detail: detail.generation?.phone_image?.error_message, reference: detail.creative_id }, language)}</p></div>
      <button className="secondary" disabled={busy || !detail.generation?.creative_direction} onClick={() => void retry(`${basePath}/phone-screen/retry`)}><RefreshCcw />{detail.template_id === 'phone_metrics' ? tr('Retry iPhone image', 'Повторити зображення iPhone') : tr('Retry artwork', 'Повторити зображення')}</button>
    </section>}
    <PhoneMetricsStudio
      api={api} language={language} basePath={basePath} detail={detail}
      onDetail={(value) => {
        const next = value as StudioPhoneMetricsDetail
        setDetail(next)
        setCreatives(current => current?.map(item => item.creative_id === next.creative_id ? { ...item, template_id: next.template_id } : item) || null)
      }}
      onCheckpoint={(result) => setDetail(result.creative)}
    />
    <PostPublishing key={`${projectId}:${detail.creative_id}:${detail.versions.length}`} api={api} language={language} projectId={projectId} creativeId={detail.creative_id} versions={detail.versions} />
    {variantDirectionOpen && <div className="modal-backdrop" role="presentation"><section className="panel brief-template-dialog" role="dialog" aria-modal="true" aria-label={tr('Choose the creative template', 'Оберіть шаблон креативу')}>
      <header><div><small>{tr('NEW CREATIVE', 'НОВИЙ КРЕАТИВ')}</small><h2>{tr('Choose the creative template', 'Оберіть шаблон креативу')}</h2></div><button className="icon-button" aria-label={tr('Close', 'Закрити')} onClick={() => setVariantDirectionOpen(false)}><X /></button></header>
      {variantError && <p role="alert">{variantError}</p>}
      {!variantTemplates && !variantError && <p role="status">{tr('Loading templates…', 'Завантаження шаблонів…')}</p>}
      <div className="post-template-choices">{variantTemplates?.map((choice) => <article key={`${choice.template_id}:${choice.template_version}`} className={variantTemplate?.template_sha256 === choice.template_sha256 ? 'is-selected' : ''}>
        <TemplateImage api={api} preview={choice.previews?.desktop} label={choice.name} language={language} />
        <button type="button" className="secondary" aria-pressed={variantTemplate?.template_sha256 === choice.template_sha256} disabled={busy} onClick={() => setVariantTemplate(choice)}>{choice.name} · v{choice.template_version}</button>
        <small>{choice.description}</small>
      </article>)}</div>
      {variantTemplates?.length === 0 && <p>{tr('No accepted Post templates are available.', 'Немає доступних прийнятих шаблонів дописів.')}</p>}
      {variantTemplate && <PhoneHeroDirectionPicker language={language} value={variantDirection} onChange={setVariantDirection} disabled={busy} idPrefix="variant-creative-direction" />}
      <button className="primary large" disabled={busy || !variantTemplate || !creativeDirectionFromDraft(variantDirection)} onClick={() => void createVariant()}><Plus />{tr('Create creative', 'Створити креатив')}</button>
    </section></div>}
    {tuneMode && <StudioTuneWizard api={api} language={language} open={tuneOpen} studioPreviewUrl="" onClose={() => setTuneOpen(false)} />}
  </>
}
