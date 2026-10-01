import { Check, RefreshCcw, Send, Sparkles, Target, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { BriefContent, MarketingApproachSelect } from '../components/MarketingApproach'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { PhoneHeroDirectionPicker, creativeDirectionFromDraft, type PhoneHeroDirectionDraft } from '../components/studio/PhoneHeroDirectionPicker'
import { translate, type Language } from '../i18n'
import { operationFailureMessage } from '../operation-errors'
import { TemplateImage } from '../components/TemplateImage'
import type {
  ProductBrief, MarketingApproach, StudioCreativeSummary, AcceptedPostTemplate,
  ValidationProject,
} from '../types'

const activeStatuses = new Set(['queued', 'generating'])

export function ProductBriefView({ api, projectId, onProjectCreated, onProjectBriefChanged, onProjectsRefresh, onCreative = () => {}, language }: {
  api: ApiClient
  projectId: string | null
  onProjectCreated: (project: ValidationProject) => void
  onProjectBriefChanged: (projectId: string, name: string, briefId: string, status: ProductBrief['status']) => void
  onProjectsRefresh: (preferredId?: string) => Promise<void>
  onCreative?: (projectId: string, creativeId: string) => void
  language: Language
}) {
  const [items, setItems] = useState<ProductBrief[] | null>(null)
  const [selected, setSelected] = useState<ProductBrief | null>(null)
  const [projectName, setProjectName] = useState('')
  const [rawIdea, setRawIdea] = useState('')
  const [correction, setCorrection] = useState('')
  const [marketingApproach, setMarketingApproach] = useState<MarketingApproach>('benefit_led')
  const [correctionApproach, setCorrectionApproach] = useState<MarketingApproach>('benefit_led')
  const pendingRequest = useRef<{ fingerprint: string; request_id: string } | null>(null)
  const requestId = (input: unknown) => {
    const fingerprint = JSON.stringify(input)
    if (pendingRequest.current?.fingerprint !== fingerprint) pendingRequest.current = { fingerprint, request_id: crypto.randomUUID() }
    return pendingRequest.current.request_id
  }
  const sourceApproach = selected?.document?.positioning?.marketing_approach || 'benefit_led'
  const approachChanged = correctionApproach !== sourceApproach
  useEffect(() => { setCorrectionApproach(sourceApproach) }, [selected?.brief_id, sourceApproach])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [approvalOpen, setApprovalOpen] = useState(false)
  const [templates, setTemplates] = useState<AcceptedPostTemplate[] | null>(null)
  const [template, setTemplate] = useState<AcceptedPostTemplate | null>(null)
  const [templateError, setTemplateError] = useState('')
  const [creativeDirection, setCreativeDirection] = useState<PhoneHeroDirectionDraft>({ style: '', background: '' })
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const load = async (preferredId?: string, targetProjectId = projectId) => {
    if (!targetProjectId) { setItems([]); setSelected(null); return }
    const value = await api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(targetProjectId)}`)
    setItems(value.items)
    const id = preferredId || (value.items.some((item) => item.brief_id === selected?.brief_id) ? selected?.brief_id : undefined) || value.items[0]?.brief_id
    if (!id) { setSelected(null); return }
    const detail = await api.get<ProductBrief>(`/api/v1/briefs/${id}`)
    setSelected(detail)
    onProjectBriefChanged(detail.project_id, detail.project_name, detail.brief_id, detail.status)
  }
  useEffect(() => {
    setItems(null); setSelected(null); setError(''); setMarketingApproach('benefit_led'); setCorrection(''); pendingRequest.current = null
    void load().catch((cause: Error) => setError(cause.message))
  }, [api, projectId])
  useEffect(() => {
    if (!selected || !activeStatuses.has(selected.status)) return
    const timer = window.setInterval(() => void load(selected.brief_id).catch((cause: Error) => setError(cause.message)), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.brief_id, selected?.status])

  const createProject = async () => {
    if (!projectName.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ project: ValidationProject }>('/api/v1/projects', {
        request_id: crypto.randomUUID(), name: projectName.trim(),
      })
      onProjectCreated(result.project)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const createBrief = async () => {
    if (!projectId || !rawIdea.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ project: ValidationProject; brief: ProductBrief }>(`/api/v1/projects/${encodeURIComponent(projectId)}/briefs`, {
        request_id: requestId([projectId, rawIdea.trim(), language, marketingApproach]), raw_idea: rawIdea.trim(), language, marketing_approach: marketingApproach,
      })
      pendingRequest.current = null; setRawIdea(''); setNotice(tr('The first Product Brief is being generated from the idea.', 'З ідеї генерується перший продуктовий бриф.')); await load(result.brief.brief_id, result.project.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const correct = async () => {
    if (!selected || (!correction.trim() && !approachChanged)) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ brief: ProductBrief }>(`/api/v1/briefs/${selected.brief_id}/correct`, {
        request_id: requestId([selected.brief_id, correction.trim(), correctionApproach, language]),
        instruction: correction.trim() || tr('Apply the selected marketing approach to the same idea.', 'Застосуй обраний маркетинговий підхід до тієї самої ідеї.'),
        marketing_approach: correctionApproach,
      })
      pendingRequest.current = null; setCorrection(''); setNotice(tr('A complete immutable replacement Brief is being generated.', 'Генерується повний незмінний бриф на заміну.')); await load(result.brief.brief_id)
      await onProjectsRefresh(result.brief.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const openApproval = async () => {
    setApprovalOpen(true); setTemplates(null); setTemplate(null); setCreativeDirection({ style: '', background: '' }); setError(''); setTemplateError('')
    try {
      const value = await api.get<{ items: AcceptedPostTemplate[] }>('/api/v1/templates?surface=post', { deadlineMs: 120_000 })
      setTemplates(value.items)
    } catch (cause) { setTemplateError((cause as Error).message) }
  }
  const openOrCreateCreative = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const value = await api.get<{ items: StudioCreativeSummary[] }>(
        `/api/v1/studio/projects/${encodeURIComponent(selected.project_id)}/creatives`,
      )
      const existing = value.items.find((item) => item.source_brief_id === selected.brief_id && item.ordinal === 1)
      if (existing) {
        onCreative(selected.project_id, existing.creative_id)
        return
      }
      await openApproval()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    if (!selected || !template) return
    const direction = creativeDirectionFromDraft(creativeDirection)
    if (!direction) return
    const alreadyApproved = selected.approved
    setBusy(true); setError('')
    try {
      const result = await api.post<{ creative: StudioCreativeSummary }>(`/api/v1/briefs/${selected.brief_id}/approve`, {
        honor_confirmed: true, template_id: template.template_id,
        template_reference: { surface: 'post', template_id: template.template_id,
          template_version: template.template_version, template_sha256: template.template_sha256 },
        creative_direction: direction,
      })
      setApprovalOpen(false)
      setNotice(alreadyApproved
        ? tr('Creative reserved. Studio AI is composing it.', 'Креатив зарезервовано. Studio AI створює його.')
        : tr('Product Brief approved. Studio AI is composing the creative.', 'Продуктовий бриф схвалено. Studio AI створює креатив.'))
      await onProjectsRefresh(selected.project_id)
      onCreative(selected.project_id, result.creative.creative_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try { await api.post(`/api/v1/briefs/${selected.brief_id}/retry`, {}); await load(selected.brief_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  if (!projectId) return <>
    <PageHeader title={tr('New Project', 'Новий проєкт')} />
    {error && <ErrorState message={error} language={language} />}{notice && <p className="notice" role="status">{notice}</p>}
    <section className="panel brief-create"><div><h2>{tr('Name the Project', 'Назвіть проєкт')}</h2><p>{tr('The name is permanent owner input and will not be replaced by Brief generation.', 'Назва задається власником і не буде замінена під час генерації брифу.')}</p></div>
      <input id="new-project-name" maxLength={120} value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder={tr('Project name', 'Назва проєкту')} />
      <button className="primary large" disabled={busy || !projectName.trim()} onClick={createProject}>{tr('Create Project', 'Створити проєкт')}</button>
    </section>
  </>
  if (!items) return error ? <ErrorState message={error} retry={() => void load()} language={language} /> : <Loading language={language} />
  return <>
    <PageHeader title={tr('Brief', 'Бриф')} />
    {error && <ErrorState message={error} language={language} />}{notice && <p className="notice" role="status">{notice}</p>}
    {!items.length ? <section className="panel brief-create"><Target className="empty-mark" /><div><h2>{tr('What do you want to validate?', 'Що ви хочете перевірити?')}</h2><p>{tr('This creates the first immutable Product Brief inside the Project.', 'Це створить перший незмінний продуктовий бриф усередині проєкту.')}</p></div>
      <textarea id="new-project-idea" rows={5} maxLength={10000} value={rawIdea} onChange={(event) => setRawIdea(event.target.value)} placeholder={tr('Describe one product idea…', 'Опишіть одну продуктову ідею…')} />
      <MarketingApproachSelect value={marketingApproach} onChange={setMarketingApproach} language={language} disabled={busy} />
      <button className="primary large" disabled={busy || !rawIdea.trim()} onClick={createBrief}><Sparkles />{tr('Generate first Product Brief', 'Згенерувати перший продуктовий бриф')}</button>
    </section> : <div className="brief-workspace">
      <aside className="panel brief-list"><small>{tr('BRIEF HISTORY', 'ІСТОРІЯ БРИФІВ')}</small>{items.map((item, index) => <button key={item.brief_id} className={selected?.brief_id === item.brief_id ? 'selected' : ''} onClick={() => void load(item.brief_id)}><strong>{index === 0 ? tr('Current Brief', 'Поточний бриф') : tr('Earlier Brief', 'Попередній бриф')} · {item.product || item.raw_idea.slice(0, 70)}</strong><span>{item.status} · {item.language?.toUpperCase() || '—'} · {item.approved ? tr('approved', 'схвалено') : tr('not approved', 'не схвалено')} · {new Date(item.created_at).toLocaleDateString(language === 'uk' ? 'uk-UA' : 'en-US')}</span></button>)}</aside>
      {selected && <div className="panel brief-detail"><small>{selected.base_brief_id ? tr('REPLACEMENT BRIEF', 'БРИФ НА ЗАМІНУ') : tr('CURRENT IMMUTABLE BRIEF', 'ПОТОЧНИЙ НЕЗМІННИЙ БРИФ')}</small>
        {activeStatuses.has(selected.status) && <p className="generation-state"><RefreshCcw className="spin" /> {tr('Generating one testable hypothesis…', 'Генерується одна перевірювана гіпотеза…')}</p>}
        {selected.status === 'failed' && <ErrorState message={operationFailureMessage({ operation: 'brief', detail: selected.error_message, code: selected.error_code, reference: selected.brief_id }, language)} retry={() => void retry()} language={language} />}
        {selected.document && <><BriefContent value={selected.document} language={language} />
          <div className="approval-row">{selected.approved ? <><p><Check /> {tr('Product Brief approved', 'Продуктовий бриф схвалено')}</p><button className="secondary" data-contract="approved-brief-existing-creative-v1" disabled={busy} onClick={() => void openOrCreateCreative()}><Sparkles />{tr('Open or create its creative', 'Відкрити або створити креатив')}</button></> : <button className="primary" disabled={busy} onClick={() => void openApproval()}><Check />{tr('I can honor this promise and offer — approve', 'Я можу виконати цю обіцянку та пропозицію — схвалити')}</button>}</div>
          <section className="brief-correction"><h2>{tr('Correct this hypothesis', 'Виправити цю гіпотезу')}</h2><p>{tr('Creates a new immutable Brief that must be approved again.', 'Створює новий незмінний бриф, який потрібно схвалити повторно.')}</p><MarketingApproachSelect value={correctionApproach} onChange={setCorrectionApproach} language={language} disabled={busy} replacement /><textarea rows={4} maxLength={2000} value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder={tr('One correction for the complete Brief…', 'Одне виправлення для всього брифу…')} /><button className="secondary" disabled={busy || (!correction.trim() && !approachChanged)} onClick={correct}>{tr('Create replacement', 'Створити заміну')} <Send /></button></section>
        </>}
      </div>}
    </div>}
    {approvalOpen && <div className="modal-backdrop" role="presentation"><section className="panel brief-template-dialog" role="dialog" aria-modal="true" aria-labelledby="brief-template-title">
      <header><div><small>{selected?.approved ? tr('CREATE CREATIVE', 'СТВОРИТИ КРЕАТИВ') : tr('APPROVE & CREATE', 'СХВАЛИТИ Й СТВОРИТИ')}</small><h2 id="brief-template-title">{tr('Choose the creative template', 'Оберіть шаблон креативу')}</h2></div><button className="icon-button" aria-label={tr('Close', 'Закрити')} onClick={() => setApprovalOpen(false)}><X /></button></header>
      <p>{tr('Choose the layout for this creative. It will be composed directly from this Brief.', 'Оберіть макет креативу. Він буде створений безпосередньо з цього брифу.')}</p>
      {error && <p role="alert">{error}</p>}
      {templateError && <p role="alert">{templateError} <button className="secondary" onClick={() => void openApproval()}>{tr('Retry', 'Повторити')}</button></p>}
      {!templates && !templateError && <p role="status">{tr('Loading templates…', 'Завантаження шаблонів…')}</p>}
      <div className="post-template-choices">{templates?.map((choice) => <article key={`${choice.template_id}:${choice.template_version}`} className={template?.template_sha256 === choice.template_sha256 ? 'is-selected' : ''}>
        <TemplateImage api={api} preview={choice.previews?.desktop} label={choice.name} language={language} />
        <button type="button" className="secondary" aria-pressed={template?.template_sha256 === choice.template_sha256} disabled={busy} onClick={() => setTemplate(choice)}>{choice.name} · v{choice.template_version}</button>
        <small>{choice.description}</small>
      </article>)}</div>
      {templates?.length === 1 && <p>{tr('Accept another Post design in Templates to add it here.', 'Прийміть інший дизайн допису в Шаблонах, щоб додати його сюди.')}</p>}
      {templates?.length === 0 && <p>{tr('No accepted Post templates are available.', 'Немає доступних прийнятих шаблонів дописів.')}</p>}
      {template && <PhoneHeroDirectionPicker language={language} value={creativeDirection} onChange={setCreativeDirection} disabled={busy} idPrefix="brief-creative-direction" />}
      <button className="primary large" disabled={busy || !template || !creativeDirectionFromDraft(creativeDirection)} onClick={() => void approve()}><Check />{selected?.approved ? tr('Create creative', 'Створити креатив') : tr('Approve Brief & generate creative', 'Схвалити бриф і згенерувати креатив')}</button>
    </section></div>}
  </>
}
