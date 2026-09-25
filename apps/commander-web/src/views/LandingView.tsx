import { LandingOperationOverlay } from '../landing/LandingOperationOverlay'
import { useLandingOperation } from '../landing/useLandingOperation'
import { useLandingImages } from '../landing/useLandingImages'
import { imageReferencePayload } from '../components/ImageReferenceInput'
import { Check, ExternalLink, Globe2, History, LayoutTemplate, Maximize2, Monitor, MoreHorizontal, RefreshCcw, Save, Smartphone, Sparkles, Tablet } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading } from '../components/State'
import { StudioManualAgent } from '../components/studio/StudioManualAgent'
import { translate, type Language } from '../i18n'
import { operationFailureMessage } from '../operation-errors'
import type { LandingVisualSlot, LandingTemplateReference, ImageInstructionContext, LandingConfiguration, LandingContent, LandingDetail, LandingPublication, LandingSummary, StudioManualAgentResult } from '../types'
import { LandingPage } from '../landing/LandingPage'
import { LandingInspector, LandingField } from '../landing/LandingInspector'
import { LandingCanvas, LandingDialog } from '../landing/LandingCanvas'
import { LandingTemplatePicker, type LandingTemplateRequest } from '../landing/LandingTemplatePicker'
import { labels, landingIssues, sections, type Section } from '../landing/model'
import '../landing/editor.css'

type SourcePost = { creative_id: string; version: number; version_sha256: string; template_id: string; source_brief_id: string }
type CheckpointResult = { checkpoint: { checkpoint_id: string; status: string } | null; learning_proposal: null }
function clone<T>(value: T): T { return structuredClone(value) }
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
type PendingDraft = { base_sha256: string; configuration: LandingConfiguration; content: LandingContent; imageInstructions: Record<string, ImageInstructionContext> }
function suggestedSlug(name: string) {
  if (!name || !/^[\x00-\x7f]+$/.test(name)) return ''
  const suggestion = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return suggestion.length >= 3 && suggestion.length <= 63 ? suggestion : ''
}

export function LandingView({ api, language, projectId = null, projectName = '', landingId = null, onLanding = () => {} }: { api: ApiClient; language: Language; projectId?: string | null; projectName?: string; landingId?: string | null; onLanding?: (landingId: string) => void }) {
  const [templates, setTemplates] = useState<Array<LandingTemplateReference & { name: string }>>([])
  const [templateError, setTemplateError] = useState('')
  const [templateRetry, setTemplateRetry] = useState(0)
  const [templateId, setTemplateId] = useState('project_landing')
  const [templateOpen, setTemplateOpen] = useState(false)
  const [panel, setPanel] = useState<'history' | 'publication' | null>(null)
  const drafts = useRef(new Map<string, PendingDraft>())
  const [referenceImage, setReferenceImage] = useState<File | null>(null)
  const [pages, setPages] = useState<LandingSummary[] | null>(null)
  const [sources, setSources] = useState<SourcePost[] | null>(null)
  const [detail, setDetail] = useState<LandingDetail | null>(null)
  const [configuration, setConfiguration] = useState<LandingConfiguration | null>(null)
  const [content, setContent] = useState<LandingContent | null>(null)
  const [imageInstructions, setImageInstructions] = useState<Record<string, ImageInstructionContext>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dismissedGeneration, setDismissedGeneration] = useState('')
  const [landingViewOpen, setLandingViewOpen] = useState(false)
  const [note, setNote] = useState('Landing design and copy approved')
  const [section, setSection] = useState<Section>('hero')
  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [width, setWidth] = useState(() => window.innerWidth <= 700 ? 360 : window.innerWidth <= 1100 ? 768 : 1280)
  const [notice, setNotice] = useState('')
  const [checkpointPending, setCheckpointPending] = useState(false)
  const [publication, setPublication] = useState<LandingPublication | null>(null)
  const [publicationLoaded, setPublicationLoaded] = useState(false)
  const [slug, setSlug] = useState('')
  const [slugConfirmed, setSlugConfirmed] = useState(false)
  const [publishVersion, setPublishVersion] = useState(0)
  const requestEpoch = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const base = projectId ? `/api/v1/landings/projects/${projectId}` : ''

  useEffect(() => {
    let active = true
    setTemplateError('')
    api.get<{ items: Array<LandingTemplateReference & { name: string }> }>('/api/v1/landings/templates').then(value => { if (active) setTemplates(value.items) }).catch((cause: Error) => { if (active) setTemplateError(cause.message) })
    return () => { active = false }
  }, [api, templateRetry])
  const templateReference = () => {
    const template = templates.find(item => item.template_id === templateId)
    return template ? { template_id: template.template_id, template_version: template.template_version, template_sha256: template.template_sha256 } : undefined
  }
  const templateCatalogError = templateError && <div className="landing-inline-error" role="alert">{templateError}<button className="secondary" onClick={() => setTemplateRetry(value => value + 1)}>{tr('Reload templates', 'Оновити шаблони')}</button></div>
  const templatePicker = <>{templateCatalogError}<label className="landing-field"><span>{tr('Landing template', 'Шаблон лендінгу')}</span><select aria-label={tr('Landing template', 'Шаблон лендінгу')} value={templateId} disabled={busy || !templates.length} onChange={event => setTemplateId(event.target.value)}>{templates.length ? templates.map(item => <option key={item.template_id} value={item.template_id}>{item.name}</option>) : <option value="project_landing">{tr('Loading templates…', 'Завантаження шаблонів…')}</option>}</select></label></>
  const draftKey = (id: string) => `ptw:landing-draft:${projectId}:${id}`
  const stashDraft = () => {
    if (!detail || !configuration || !content || !dirty) return
    const pending = { base_sha256: detail.state_sha256, configuration: clone(configuration), content: clone(content), imageInstructions }
    drafts.current.set(draftKey(detail.landing_id), pending)
    try { sessionStorage.setItem(draftKey(detail.landing_id), JSON.stringify(pending)) } catch { /* Retain edits in this mounted workspace. */ }
  }
  const applyDetail = (value: LandingDetail, restoreDraft = false) => {
    setDetail(value); setConfiguration(clone(value.configuration)); setContent(clone(value.content)); setError('')
    const key = draftKey(value.landing_id)
    if (restoreDraft && value.status === 'draft') {
      let pending = drafts.current.get(key)
      try { pending ||= JSON.parse(sessionStorage.getItem(key) || 'null') as PendingDraft } catch { /* Browser storage is optional. */ }
      if (pending?.configuration?.schema === value.configuration.schema && pending?.content?.schema === value.content.schema && typeof pending.base_sha256 === 'string') {
        setDetail({ ...value, state_sha256: pending.base_sha256 }); setConfiguration(clone(pending.configuration)); setContent(clone(pending.content)); setImageInstructions(pending.imageInstructions || {})
        setNotice(tr('Your pending edits are restored.', 'Незбережені зміни відновлено.'))
      }
    } else {
      drafts.current.delete(key)
      try { sessionStorage.removeItem(key) } catch { /* Browser storage is optional. */ }
    }
    setPages(current => current?.map(page => page.landing_id === value.landing_id ? { ...page, ...value } : page) || current)
  }
  const reload = async () => {
    if (!projectId) return
    const epoch = ++requestEpoch.current
    setError(''); setNotice(''); setImageInstructions({}); setPanel(null); setTemplateOpen(false); setBusy(false); setPages(null); setSources(null); setDetail(null); setCheckpointPending(false); setPublicationLoaded(false)
    try {
      const [pageList, sourceList] = await Promise.all([
        api.get<{ items: LandingSummary[] }>(`${base}/pages`), api.get<{ items: SourcePost[] }>(`${base}/source-posts`),
      ])
      if (epoch !== requestEpoch.current) return
      setPages(pageList.items); setSources(sourceList.items)
      if (pageList.items.some((item) => item.approved_version_count > 0)) {
        const result = await api.get<{ publication: LandingPublication | null }>(`${base}/publication`)
        if (epoch !== requestEpoch.current) return
        setPublication(result.publication)
      } else setPublication(null)
      setPublicationLoaded(true)
      const selected = pageList.items.find((item) => item.landing_id === landingId) || pageList.items[0]
      if (selected) {
        const value = await api.get<LandingDetail>(`${base}/pages/${selected.landing_id}`)
        if (epoch !== requestEpoch.current) return
        applyDetail(value, true)
        if (selected.landing_id !== landingId) onLanding(selected.landing_id)
      }
    } catch (cause) { if (epoch !== requestEpoch.current) return; setPages([]); setSources([]); setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  useEffect(() => { void reload() }, [projectId, landingId]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setSlug(suggestedSlug(projectName)); setSlugConfirmed(false)
  }, [projectId, projectName])
  useEffect(() => {
    setPublishVersion(detail?.versions[detail.versions.length - 1]?.version || 0)
  }, [detail?.landing_id, detail?.versions.length])

  useEffect(() => {
    if (!detail || !projectId || !['queued', 'composing', 'generating_images'].includes(detail.status)) return
    let active = true
    let timer: number | undefined
    const refreshProgress = async () => {
      try {
        const value = await api.get<LandingDetail>(`${base}/pages/${detail.landing_id}`)
        if (active) applyDetail(value)
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        if (active) timer = window.setTimeout(refreshProgress, 2_500)
      }
    }
    timer = window.setTimeout(refreshProgress, 2_500)
    return () => { active = false; if (timer !== undefined) window.clearTimeout(timer) }
  }, [api, base, detail?.landing_id, detail?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const pagePath = detail && projectId ? `${base}/pages/${detail.landing_id}` : ''
  const imageState = useLandingImages(api, detail, pagePath, section)
  const images = imageState.images
  const localRetry = useRef<(() => Promise<void>) | null>(null)
  useEffect(() => { localRetry.current = null }, [pagePath, projectId])
  const operation = useLandingOperation(api, pagePath, applyDetail, result => { setConfiguration(clone(result.configuration as LandingConfiguration)); setContent(clone(result.content as LandingContent)) })
  const initialGeneration = useRef(false)
  useEffect(() => {
    if (detail && ['queued', 'composing', 'generating_images'].includes(detail.status)) initialGeneration.current = true
    else if (detail?.status === 'draft' && initialGeneration.current) { initialGeneration.current = false; operation.preview() }
  }, [detail?.status]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (operation.visible && operation.phase === 'preview' && imageState.ready) { operation.ready(); setBusy(false) }
  }, [operation.visible, operation.phase, imageState.ready]) // eslint-disable-line react-hooks/exhaustive-deps
  const overlay = operation.visible && <LandingOperationOverlay language={language} operation={operation.operation} phase={operation.phase}
    error={operation.error || (operation.phase === 'preview' ? imageState.error : '')}
    retry={references => { if (operation.phase === 'preview' && imageState.error) imageState.retry(); else if (localRetry.current) void localRetry.current().catch(() => {}); else void operation.retry(references) }}
    close={() => { operation.dismiss(); setBusy(false) }} />

  const persist = async () => {
    if (!detail || !configuration || !content) throw new Error('Landing draft is not ready')
    const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/configuration`, { base_sha256: detail.state_sha256, configuration, content })
    applyDetail(value)
    setCheckpointPending(true)
    return value
  }
  const create = async (source: SourcePost) => {
    localRetry.current = () => create(source)
    setBusy(true); setError(''); operation.begin()
    try {
      const value = await api.post<{ landing: LandingSummary }>(`${base}/pages`, { source_creative_id: source.creative_id, source_version: source.version, ...(templateReference() ? { template_reference: templateReference() } : {}) })
      onLanding(value.landing.landing_id)
    } catch (cause) { operation.fail(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const createVariant = async (request: LandingTemplateRequest) => {
    if (!detail) return
    const epoch = requestEpoch.current
    stashDraft()
    localRetry.current = () => createVariant(request)
    setBusy(true); setError(''); operation.begin()
    try {
      const value = await api.post<{ landing: LandingSummary }>(`${base}/pages/variants`, request)
      if (epoch !== requestEpoch.current) return
      setNotice(''); setTemplateOpen(false)
      onLanding(value.landing.landing_id)
    } catch (cause) {
      if (epoch === requestEpoch.current) operation.fail(cause instanceof Error ? cause.message : String(cause))
      throw cause
    } finally { if (epoch === requestEpoch.current) setBusy(false) }
  }
  const save = async (approve = false) => {
    if (!detail || !configuration || !content) return
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingDetail } & CheckpointResult>(`${base}/pages/${detail.landing_id}/${approve ? 'approve' : 'save'}`, approve
        ? { base_sha256: detail.state_sha256, configuration, content, change_note: note }
        : { base_sha256: detail.state_sha256, configuration, content }, { deadlineMs: 480_000 })
      applyDetail(value.landing)
      setCheckpointPending(false)
      setNotice(approve ? tr('Landing approved. Private version saved.', 'Лендінг затверджено. Приватну версію збережено.') : tr('Landing saved.', 'Лендінг збережено.'))
    } catch (cause) {
      const failure = cause && typeof cause === 'object' && 'details' in cause
        ? (cause as { details?: { status?: number; detail?: string } }).details : undefined
      if (failure?.status === 409 && failure.detail === 'Landing changed; reload before saving') {
        try {
          const latest = await api.get<LandingDetail>(`${base}/pages/${detail.landing_id}`)
          if (JSON.stringify(latest.configuration) === JSON.stringify(configuration) && JSON.stringify(latest.content) === JSON.stringify(content)) {
            applyDetail(latest)
            setCheckpointPending(false)
            setNotice(approve
              ? tr('Landing was already saved. Review it before approving again.', 'Лендінг уже збережено. Перевірте його перед повторним затвердженням.')
              : tr('Landing was already saved.', 'Лендінг уже збережено.'))
            return
          }
        } catch { /* Keep the original conflict guidance and pending owner input. */ }
      }
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally { setBusy(false) }
  }
  useEffect(() => { setReferenceImage(null) }, [detail?.landing_id, section, projectId])
  const editContent = (next: LandingContent) => {
    if (content) {
      if (next.hero.visual_direction !== content.hero.visual_direction) setImageInstructions(current => ({ ...current, hero_visual: { origin: 'owner' } }))
      if (next.visual_break.visual_direction !== content.visual_break.visual_direction) setImageInstructions(current => ({ ...current, visual_break_visual: { origin: 'owner' } }))
    }
    if (next.marketing?.walkthrough_visual_direction !== content?.marketing?.walkthrough_visual_direction) setImageInstructions(current => ({ ...current, walkthrough_visual: { origin: 'owner' } }))
    next.app_screens?.forEach((screen, index) => {
      if (screen.visual_direction !== content?.app_screens?.[index].visual_direction) setImageInstructions(current => ({ ...current, [`app_screen_${index + 1}`]: { origin: 'owner' } }))
    })
    setContent(next)
  }
  const changedImageSettings = (slot: LandingVisualSlot, next: LandingConfiguration) => {
    const old = detail?.configuration
    return [
      ...(['style', 'background'] as const).filter(key => (slot === 'hero_visual' || slot === 'visual_break_visual') && next.image_directions?.[slot]?.[key] !== old?.image_directions?.[slot]?.[key]),
      ...(JSON.stringify(next.theme) !== JSON.stringify(old?.theme) ? ['palette'] : []),
    ]
  }
  const generate = async (slot: LandingVisualSlot, enhance = false) => {
    if (!detail || !content || !configuration) return
    localRetry.current = null
    setBusy(true); setError(''); operation.begin()
    try {
      const reference = referenceImage ? await imageReferencePayload(referenceImage) : null
      const changed = changedImageSettings(slot, configuration)
      const instruction = imageInstructions[slot]
      const direction = slot === 'walkthrough_visual' ? content.marketing!.walkthrough_visual_direction : slot.startsWith('app_screen_') ? content.app_screens![Number(slot.slice(-1)) - 1].visual_direction : slot === 'hero_visual' ? content.hero.visual_direction : content.visual_break.visual_direction
      await operation.run('image', { request_id: crypto.randomUUID(), slot, configuration, content, base_sha256: detail.state_sha256,
        visual_direction: direction, ...(instruction ? { instruction_context: instruction } : {}), ...(changed.length ? { changed_image_settings: changed } : {}),
        ...(reference ? { reference_image: reference } : enhance ? { enhance_current: true } : {}) })
      setCheckpointPending(true)
    } catch (cause) { if (!(cause instanceof Error && cause.message === 'Landing operation needs attention')) operation.fail(cause instanceof Error ? cause.message : String(cause)) }
    finally { setReferenceImage(null); setBusy(false) }
  }
  const selectVisual = async (slot: LandingVisualSlot, sha256: string) => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const saved = await persist()
      const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/visuals/${slot}/select`, {
        base_sha256: saved.state_sha256, sha256,
      })
      setImageInstructions(current => { const next = { ...current }; delete next[slot]; return next })
      applyDetail(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const reusePhoto = async () => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const saved = await persist()
      applyDetail(await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/visuals/visual_break_visual/reuse`, { base_sha256: saved.state_sha256, asset_id: 'showcase_lifestyle' }))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const latest = await api.get<LandingDetail>(`${base}/pages/${detail.landing_id}`)
      applyDetail(latest)
      if (latest.status === 'failed') await api.post(`${base}/pages/${detail.landing_id}/retry`, {})
      await reload()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const applyAgentResult = async (result: StudioManualAgentResult<LandingConfiguration, LandingContent>) => {
    if (!detail) return
    setConfiguration(clone(result.configuration)); setContent(clone(result.content))
    if (result.image_actions.length) setCheckpointPending(true)
    setNotice(tr(`Agent adjusted ${result.changed_paths.length} editor fields and completed ${result.image_actions.length} images. Review before saving.`,
      `Агент змінив ${result.changed_paths.length} полів і завершив ${result.image_actions.length} зображень. Перевірте перед збереженням.`))
    setBusy(false)
  }
  const status = detail?.status
  const dirty = Boolean(detail && configuration && content && (JSON.stringify(configuration) !== JSON.stringify(detail.configuration) || JSON.stringify(content) !== JSON.stringify(detail.content)))
  const issues = configuration && content && detail ? landingIssues(configuration, content, detail.assets) : []
  const refreshPublication = async () => {
    if (!projectId) return null
    const value = await api.get<{ publication: LandingPublication | null }>(`${base}/publication`)
    setPublication(value.publication); setPublicationLoaded(true)
    return value.publication
  }
  const publish = async (targetLandingId = detail?.landing_id, version = publishVersion) => {
    if (!projectId || !targetLandingId || !version) return
    setBusy(true); setError('')
    try {
      const first = publication === null
      if (first) {
        if (!slugConfirmed || slug.length < 3 || slug.length > 63 || !slugPattern.test(slug)) {
          throw new Error(tr('Enter a valid slug and confirm the complete public URL.', 'Введіть коректний slug і підтвердьте повну публічну URL-адресу.'))
        }
        const availability = await api.get<{ available: boolean }>(`${base}/publication/availability?slug=${encodeURIComponent(slug)}`)
        if (!availability.available) throw new Error(tr('That public URL is already reserved. Choose another slug.', 'Цю публічну URL-адресу вже зарезервовано. Оберіть інший slug.'))
      }
      await api.post(`${base}/publication/publish`, {
        request_id: crypto.randomUUID(), landing_id: targetLandingId, version,
        ...(first ? { slug } : {}),
      })
      await refreshPublication()
      setNotice(tr('The stable Natal URL now serves the selected approved version.', 'Стабільна URL-адреса Natal тепер показує обрану затверджену версію.'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const unpublish = async () => {
    if (!projectId || !publication || publication.status !== 'published') return
    setBusy(true); setError('')
    try {
      await api.post(`${base}/publication/unpublish`, { request_id: crypto.randomUUID() })
      await refreshPublication()
      setNotice(tr('The Natal page is unpublished. Its URL remains permanently reserved.', 'Сторінку Natal знято з публікації. Її URL-адреса залишається назавжди зарезервованою.'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  if (!projectId) return <Empty><h2>{tr('Choose a Project', 'Оберіть проєкт')}</h2><p>{tr('A Landing is always scoped to one Project.', 'Лендінг завжди належить одному проєкту.')}</p></Empty>
  if (pages === null || sources === null) return <Loading language={language} />
  if (error && !detail) return <ErrorState message={error} retry={() => void reload()} language={language} />
  if (!detail) return <section className="panel landing-source-picker">{overlay}<small>{tr('PRIVATE LANDING', 'ПРИВАТНИЙ ЛЕНДІНГ')}</small><h1>{tr('Create a Landing from an approved Post', 'Створіть лендінг із затвердженого допису')}</h1><p>{tr('Landing captures the selected Post version’s design, then remains independently editable.', 'Лендінг зафіксує дизайн обраної версії допису та далі редагуватиметься окремо.')}</p>{templatePicker}{sources.length ? <div className="landing-source-list">{sources.map((source) => <button key={`${source.creative_id}:${source.version}`} className="panel" disabled={busy} onClick={() => void create(source)}><Sparkles /><span>{source.template_id} · v{source.version}</span><small>{source.creative_id.slice(0, 8)}</small></button>)}</div> : <Empty><h2>{tr('Approve a Post first', 'Спершу затвердьте допис')}</h2><p>{tr('Landing starts only from an immutable approved Post version.', 'Лендінг створюється лише з незмінної затвердженої версії допису.')}</p></Empty>}</section>
  const templateName = (page: LandingSummary) => {
    const id = page.template_reference?.template_id || ('template_id' in page ? page.template_id : 'project_landing')
    return templates.find(item => item.template_id === id)?.name || (id === 'app_showcase' ? 'App Showcase' : 'Project landing')
  }
  const templateChooser = templateOpen && <LandingTemplatePicker api={api} language={language} items={templates} currentId={detail.template_id} requestKey={`ptw:landing-template-request:${projectId}:${detail.landing_id}`} source={{ source_creative_id: detail.source_creative_id, source_version: detail.source_version }} onApply={createVariant} onClose={() => setTemplateOpen(false)} />
  if (status !== 'draft' || !configuration || !content) {
    const generation = detail.generation as { error_message?: string; error_type?: string }
    const initialAssets = detail.assets.filter(asset => asset.slot !== 'walkthrough_visual' || detail.configuration.marketing?.walkthrough_enabled)
    const generatingSlot = initialAssets.find(asset => !asset.available)?.slot
    const initialJobs = initialAssets.map(asset => ({ slot: asset.slot, status: asset.available ? 'completed' : status === 'failed' ? 'failed' : status === 'generating_images' && asset.slot === generatingSlot ? 'generating' : 'queued' }))
    const previous = pages.find(item => item.landing_id !== detail.landing_id && item.source_creative_id === detail.source_creative_id && item.source_version === detail.source_version)
    return <section className="panel landing-progress">{dismissedGeneration !== detail.landing_id && <LandingOperationOverlay language={language} phase={status} jobs={initialJobs} startedAt={detail.created_at} error={error || (status === 'failed' ? operationFailureMessage({ operation: 'landing', detail: generation.error_message, code: generation.error_type, reference: detail.landing_id }, language) : undefined)} retry={() => void retry()} close={() => setDismissedGeneration(detail.landing_id)} />}<small>{templateName(detail)}</small><h1>{status === 'failed' ? tr('Landing generation needs attention', 'Створення лендінгу потребує уваги') : tr('Building the Landing', 'Створюємо лендінг')}</h1>{status === 'failed' ? <ErrorState message={operationFailureMessage({ operation: 'landing', detail: generation.error_message, code: generation.error_type, reference: detail.landing_id }, language)} retry={() => void retry()} language={language} /> : <p>{status === 'composing' ? tr('Writing the page sections…', 'Готуємо текст сторінки…') : status === 'generating_images' ? tr('Generating app screens and page images…', 'Створюємо екрани застосунку та зображення…') : tr('Queued for generation…', 'У черзі на створення…')}</p>}
      <div className="landing-progress-actions">{previous && <button className="secondary" onClick={() => onLanding(previous.landing_id)}>{tr('Back to previous Landing', 'Повернутися до попереднього лендінгу')}</button>}{status === 'failed' && <button className="secondary" disabled={busy || !templates.length} onClick={() => setTemplateOpen(true)}>{tr('Change template', 'Змінити шаблон')}</button>}</div>{templateChooser}</section>
  }

  const pageSections = content.app_screens ? ['theme', 'hero', 'features', 'app_screen_1', 'app_screen_2', 'app_screen_3', 'comparison', 'walkthrough', 'visual_break', 'social_proof', 'values', 'cta', 'downloads', 'faq', 'contacts'] as Section[] : [...sections, 'comparison', 'walkthrough', 'values', 'cta', 'downloads'] as Section[]
  const viewportControls = <div className="landing-device-controls" aria-label={tr('Preview width', 'Ширина прев’ю')}>{([[1280, Monitor, tr('Desktop', 'Комп’ютер')], [768, Tablet, tr('Tablet', 'Планшет')], [360, Smartphone, tr('Mobile', 'Телефон')]] as const).map(([size, Icon, name]) => <button key={size} className={width === size ? 'active' : ''} aria-label={`${name} ${size}`} aria-pressed={width === size} onClick={() => setWidth(size)}><Icon /><span>{size}</span></button>)}</div>
  const preview = (editing: boolean) => <LandingCanvas width={width}><LandingPage showDraftHints configuration={configuration} content={content} imageUrls={images} editing={editing} selected={section} onSelect={value => { setSection(value); setMode('edit') }} /></LandingCanvas>
  const publicUrl = publication?.canonical_url || `https://natal-service.com/${slug}`
  return <section className="landing-studio">
    {overlay}<header className="landing-action-bar"><div><h1>{templateName(detail)}</h1><p role="status">{busy ? tr('Working…', 'Виконуємо…') : dirty ? tr('Unsaved changes', 'Незбережені зміни') : checkpointPending ? tr('Draft updated · Save to capture your changes', 'Чернетку оновлено · Збережіть свої зміни') : notice || tr('Private draft', 'Приватна чернетка')}</p></div><div className="landing-actions">
      <button className="secondary" disabled={busy || !templates.length} onClick={() => setTemplateOpen(true)}><LayoutTemplate />{tr('Change template', 'Змінити шаблон')}</button>
      <button className="primary" aria-label={tr('Save Landing', 'Зберегти лендінг')} disabled={busy} onClick={() => void save(false)}><Save />{tr('Save', 'Зберегти')}</button>
      <details className="landing-more"><summary aria-label={tr('More actions', 'Інші дії')}><MoreHorizontal /></summary><div>
        <button disabled={busy} onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); setPanel('history') }}><History />{tr('History', 'Історія')}</button>
        <button disabled={busy} onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); setPanel('publication') }}><Globe2 />{tr('Approve & publish', 'Затвердити й опублікувати')}</button>
      </div></details>
    </div></header>
    {templateCatalogError}
    {error && <div className="landing-inline-error" role="alert">{error}<button className="ghost" onClick={() => setError('')}>{tr('Dismiss', 'Закрити')}</button></div>}
    {templateChooser}
    {panel === 'history' && <LandingDialog title={tr('Landing history', 'Історія лендінгів')} onClose={() => setPanel(null)} className="landing-history-dialog"><div className="landing-history-list">{pages.map(item => <button key={item.landing_id} aria-current={item.landing_id === detail.landing_id ? 'true' : undefined} disabled={busy} onClick={() => { stashDraft(); setPanel(null); if (item.landing_id !== detail.landing_id) onLanding(item.landing_id) }}><strong>{templateName(item)}</strong><span>{tr('Draft', 'Варіант')} {item.ordinal} · {item.status === 'failed' ? tr('Needs retry', 'Потрібен повтор') : item.approved_version_count ? tr('Has approved version', 'Є затверджена версія') : tr('Not approved', 'Не затверджено')}{item.landing_id === detail.landing_id ? ` · ${tr('Current', 'Поточний')}` : ''}</span></button>)}</div></LandingDialog>}
    {panel === 'publication' && <LandingDialog title={tr('Approve & publish', 'Затвердити й опублікувати')} onClose={() => { if (!busy) setPanel(null) }} className="landing-publish-dialog">
      <div className="landing-approval-panel"><p>{tr('Approve a private version when you like the result. Publishing is a separate action.', 'Затвердьте приватну версію, коли результат вас влаштовує. Публікація — окрема дія.')}</p>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {issues.length > 0 && <div className="landing-approval-issues">{issues.map(issue => <button key={issue.path} onClick={() => { setPanel(null); setMode('edit'); setSection(issue.section) }}>{issue[language]}</button>)}</div>}
        <details><summary>{tr('Approval note', 'Нотатка затвердження')}</summary><LandingField label={tr('Approval note', 'Нотатка затвердження')} value={note} max={240} onChange={setNote} /></details>
        <button className="primary" disabled={busy || issues.length > 0 || !note.trim()} onClick={() => void save(true)}><Check />{tr('Approve Landing', 'Затвердити лендінг')}</button>
      </div>
    {(detail.versions.length > 0 || publication) && <section className="panel landing-publication-panel" aria-labelledby="landing-publication-title">
      <header><div><small>PUBLIC NATAL PAGE</small><h2 id="landing-publication-title"><Globe2 /> {tr('Publication', 'Публікація')}</h2></div>{publication && <span className={`landing-publication-status is-${publication.status}`}>{publication.status}</span>}</header>
      {!publication ? <>
        <p>{tr('The first Publish permanently reserves this slug for the Project.', 'Перша публікація назавжди резервує цей slug для проєкту.')}</p>
        <div className="landing-publication-fields"><label>{tr('Latin slug', 'Латинський slug')}<input value={slug} minLength={3} maxLength={63} pattern="[a-z0-9]+(-[a-z0-9]+)*" spellCheck={false} onChange={event => { setSlug(event.target.value); setSlugConfirmed(false) }} /></label><label>{tr('Approved version', 'Затверджена версія')}<select value={publishVersion} onChange={event => setPublishVersion(Number(event.target.value))}>{detail.versions.map(item => <option key={item.version} value={item.version}>v{item.version} · {item.change_note}</option>)}</select></label></div>
        <output className="landing-public-url">{publicUrl}</output>
        <label className="landing-public-confirm"><input type="checkbox" checked={slugConfirmed} onChange={event => setSlugConfirmed(event.target.checked)} />{tr('I confirm this complete public URL and understand it cannot be changed or released.', 'Я підтверджую цю повну публічну URL-адресу й розумію, що її не можна змінити або звільнити.')}</label>
        <button className="primary" disabled={busy || dirty || !publishVersion || !slugConfirmed || slug.length < 3 || slug.length > 63 || !slugPattern.test(slug)} onClick={() => void publish()}><Globe2 />{tr('Publish approved version', 'Опублікувати затверджену версію')}</button>
      </> : <>
        <a className="landing-public-url" href={publication.canonical_url} target="_blank" rel="noreferrer">{publication.canonical_url} <ExternalLink /></a>
        <div className="landing-publication-fields"><label>{tr('Approved version from this Landing', 'Затверджена версія цього лендінгу')}<select value={publishVersion} onChange={event => setPublishVersion(Number(event.target.value))}>{detail.versions.map(item => <option key={item.version} value={item.version}>v{item.version} · {item.change_note}</option>)}</select></label><button className="primary" disabled={busy || dirty || !publishVersion} onClick={() => void publish()}>{publication.status === 'published' ? tr('Republish selected version', 'Перепублікувати обрану версію') : tr('Publish selected version', 'Опублікувати обрану версію')}</button>{publication.status === 'published' && <button className="secondary" disabled={busy} onClick={() => void unpublish()}>{tr('Unpublish', 'Зняти з публікації')}</button>}</div>
        <details><summary>{tr('Append-only publication history', 'Незмінна історія публікацій')}</summary><div className="landing-publication-history">{publication.events.map(event => <div key={event.event_id}><span>#{event.sequence} · {event.action}{event.landing_version ? ` · v${event.landing_version}` : ''} · {new Date(event.created_at).toLocaleString(language === 'uk' ? 'uk-UA' : 'en-US')}</span>{event.action === 'publish' && event.landing_id && event.landing_version && <button className="ghost" disabled={busy || (publication.status === 'published' && publication.current_event_id === event.event_id)} onClick={() => void publish(event.landing_id!, event.landing_version!)}>{tr('Restore', 'Відновити')}</button>}</div>)}</div></details>
      </>}
      {!publicationLoaded && <small>{tr('Loading publication…', 'Завантаження публікації…')}</small>}
    </section>}
    </LandingDialog>}
    <div className="landing-workspace-toolbar"><div className="landing-mode-controls"><button className={mode === 'edit' ? 'active' : ''} aria-pressed={mode === 'edit'} onClick={() => setMode('edit')}>{tr('Edit', 'Редагувати')}</button><button className={mode === 'preview' ? 'active' : ''} aria-pressed={mode === 'preview'} onClick={() => setMode('preview')}>{tr('Preview', 'Перегляд')}</button></div>
      <select className="landing-width-select" aria-label={tr('Preview width', 'Ширина прев’ю')} value={width} onChange={event => setWidth(Number(event.target.value))}><option value={1280}>{tr('Desktop', 'Комп’ютер')}</option><option value={768}>{tr('Tablet', 'Планшет')}</option><option value={360}>{tr('Mobile', 'Телефон')}</option></select>
      <button className="ghost landing-expand" aria-label={tr('View Landing', 'Переглянути лендінг')} onClick={event => { event.currentTarget.focus(); setLandingViewOpen(true) }}><Maximize2 /></button>
      <StudioManualAgent compact onBegin={() => { localRetry.current = null; setBusy(true); operation.begin() }}
        onFailure={message => { setBusy(false); if (message !== 'Landing operation needs attention') operation.fail(message) }}
        onRequest={async request => await operation.run('agent', request) as unknown as StudioManualAgentResult<LandingConfiguration, LandingContent>} api={api} language={language} endpoint={`${base}/pages/${detail.landing_id}/agent`} stateSha256={detail.state_sha256} configuration={configuration} content={content} disabled={busy} onApply={applyAgentResult} />
    </div>
    <div className={`landing-workbench is-${mode}`}>
      <aside className="landing-editor"><nav className="landing-section-nav" aria-label={tr('Page sections', 'Секції сторінки')}><select aria-label={tr('Page section', 'Секція сторінки')} value={section} onChange={event => setSection(event.target.value as Section)}>{pageSections.map(key => <option key={key} value={key}>{labels[language][key]}</option>)}</select></nav>
        <div className="landing-inspector">
          <LandingInspector onReuseImage={() => void reusePhoto()} referenceImage={referenceImage} onReferenceImage={setReferenceImage} section={section} configuration={configuration} content={content} detail={detail} onConfiguration={setConfiguration} onContent={editContent} language={language} busy={busy} issues={issues} imageUrls={images} onGenerate={(slot, enhance) => void generate(slot, enhance)} onSelectImage={(slot, sha) => void selectVisual(slot, sha)} />
        </div>
      </aside>
      <div className="landing-preview-area">{preview(mode === 'edit')}</div>
    </div>
    {landingViewOpen && <LandingDialog title={tr('Full-screen Landing preview', 'Повноекранне прев’ю лендінгу')} onClose={() => setLandingViewOpen(false)} className="landing-fullscreen"><div className="landing-dialog-toolbar">{viewportControls}<small>{tr('PRIVATE LANDING', 'ПРИВАТНИЙ ЛЕНДІНГ')}</small></div>{preview(false)}</LandingDialog>}
  </section>
}
