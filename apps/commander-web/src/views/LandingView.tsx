import { Check, Maximize2, Monitor, Plus, RefreshCcw, Save, Smartphone, Sparkles, Tablet } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type { LandingConfiguration, LandingContent, LandingDetail, LandingSummary } from '../types'
import { LandingPage } from '../landing/LandingPage'
import { LandingInspector, LandingField } from '../landing/LandingInspector'
import { LandingCanvas, LandingDialog } from '../landing/LandingCanvas'
import { labels, landingIssues, sections, type Section } from '../landing/model'
import '../landing/editor.css'

type SourcePost = { creative_id: string; version: number; version_sha256: string; template_id: string; source_brief_id: string }
type LearningResult = { checkpoint: { checkpoint_id: string; status: string; edit_summary?: string; project_lesson?: string; after_snapshot?: unknown; error_message?: string } | null; learning_proposal: { proposal_id: string; global_rule: string; status: string } | null }
function clone<T>(value: T): T { return structuredClone(value) }

export function LandingView({ api, language, projectId = null, landingId = null, onLanding = () => {} }: { api: ApiClient; language: Language; projectId?: string | null; landingId?: string | null; onLanding?: (landingId: string) => void }) {
  const [pages, setPages] = useState<LandingSummary[] | null>(null)
  const [sources, setSources] = useState<SourcePost[] | null>(null)
  const [detail, setDetail] = useState<LandingDetail | null>(null)
  const [configuration, setConfiguration] = useState<LandingConfiguration | null>(null)
  const [content, setContent] = useState<LandingContent | null>(null)
  const [images, setImages] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [landingViewOpen, setLandingViewOpen] = useState(false)
  const [note, setNote] = useState('Landing design and copy approved')
  const [section, setSection] = useState<Section>('hero')
  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [width, setWidth] = useState(() => window.innerWidth <= 700 ? 360 : 1280)
  const [learning, setLearning] = useState<LearningResult | null>(null)
  const [notice, setNotice] = useState('')
  const [checkpointPending, setCheckpointPending] = useState(false)
  const requestEpoch = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const base = projectId ? `/api/v1/landings/projects/${projectId}` : ''

  const applyDetail = (value: LandingDetail) => {
    setDetail(value); setConfiguration(clone(value.configuration)); setContent(clone(value.content)); setError('')
    setPages(current => current?.map(page => page.landing_id === value.landing_id ? { ...page, ...value } : page) || current)
  }
  const reload = async () => {
    if (!projectId) return
    const epoch = ++requestEpoch.current
    setError(''); setPages(null); setSources(null); setDetail(null); setLearning(null); setCheckpointPending(false)
    try {
      const [pageList, sourceList] = await Promise.all([
        api.get<{ items: LandingSummary[] }>(`${base}/pages`), api.get<{ items: SourcePost[] }>(`${base}/source-posts`),
      ])
      if (epoch !== requestEpoch.current) return
      setPages(pageList.items); setSources(sourceList.items)
      const selected = pageList.items.find((item) => item.landing_id === landingId) || pageList.items[0]
      if (selected) {
        const value = await api.get<LandingDetail>(`${base}/pages/${selected.landing_id}`)
        if (epoch !== requestEpoch.current) return
        applyDetail(value)
        if (selected.landing_id !== landingId) onLanding(selected.landing_id)
      }
    } catch (cause) { if (epoch !== requestEpoch.current) return; setPages([]); setSources([]); setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  useEffect(() => { void reload() }, [projectId, landingId]) // eslint-disable-line react-hooks/exhaustive-deps

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

  useEffect(() => {
    let active = true
    const urls: string[] = []
    const load = async () => {
      if (!detail || !projectId) { setImages({}); return }
      const next: Record<string, string> = {}
      await Promise.all(detail.assets.flatMap(item => item.history.map(async entry => {
        try {
          const blob = await api.image(`${base}/pages/${detail.landing_id}/visuals/${item.slot}/history/${entry.sha256}`, 'image/png', entry.sha256)
          if (!active) return
          const url = URL.createObjectURL(blob); urls.push(url); next[entry.sha256] = url
          if (entry.selected) next[item.slot] = url
        } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : String(cause)) }
      })))
      if (active) setImages(next)
    }
    void load().catch((cause) => active && setError(cause instanceof Error ? cause.message : String(cause)))
    return () => { active = false; urls.forEach((url) => URL.revokeObjectURL(url)) }
  }, [detail?.landing_id, JSON.stringify(detail?.assets), projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const persist = async () => {
    if (!detail || !configuration || !content) throw new Error('Landing draft is not ready')
    const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/configuration`, { base_sha256: detail.state_sha256, configuration, content })
    applyDetail(value)
    setCheckpointPending(true)
    return value
  }
  const create = async (source: SourcePost) => {
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingSummary }>(`${base}/pages`, { source_creative_id: source.creative_id, source_version: source.version })
      onLanding(value.landing.landing_id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const createVariant = async () => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingSummary }>(`${base}/pages/variants`, {
        source_creative_id: detail.source_creative_id, source_version: detail.source_version,
      })
      onLanding(value.landing.landing_id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const save = async (approve = false) => {
    if (!detail || !configuration || !content) return
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingDetail } & LearningResult>(`${base}/pages/${detail.landing_id}/${approve ? 'approve' : 'save'}`, approve
        ? { base_sha256: detail.state_sha256, configuration, content, change_note: note }
        : { base_sha256: detail.state_sha256, configuration, content })
      applyDetail(value.landing)
      setCheckpointPending(false)
      setNotice(approve ? tr('Landing approved. Private version saved.', 'Лендінг затверджено. Приватну версію збережено.') : tr('Landing saved.', 'Лендінг збережено.'))
      if (value.checkpoint) setLearning(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const generate = async (slot: 'hero_visual' | 'visual_break_visual', enhance = false) => {
    if (!detail || !content) return
    setBusy(true); setError('')
    try {
      const saved = await persist()
      const direction = slot === 'hero_visual' ? content.hero.visual_direction : content.visual_break.visual_direction
      const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/visuals/${slot}/generate`, { base_sha256: saved.state_sha256, visual_direction: direction, ...(enhance ? { enhance_current: true } : {}) }, { deadlineMs: 480_000 })
      applyDetail(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const selectVisual = async (slot: 'hero_visual' | 'visual_break_visual', sha256: string) => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const saved = await persist()
      const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/visuals/${slot}/select`, {
        base_sha256: saved.state_sha256, sha256,
      })
      applyDetail(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!detail) return
    setBusy(true)
    try { await api.post(`${base}/pages/${detail.landing_id}/retry`, {}); await reload() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const status = detail?.status
  const dirty = Boolean(detail && configuration && content && (JSON.stringify(configuration) !== JSON.stringify(detail.configuration) || JSON.stringify(content) !== JSON.stringify(detail.content)))
  const issues = configuration && content && detail ? landingIssues(configuration, content, detail.assets) : []
  const decideLearning = async (decision: string) => {
    if (!learning?.learning_proposal || !detail) return
    setBusy(true)
    try {
      await api.post(`${base}/pages/${detail.landing_id}/learning/${learning.learning_proposal.proposal_id}`, { decision })
      setLearning(null); setNotice(tr('Learning preference saved.', 'Налаштування навчання збережено.'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const retryLearning = async () => {
    if (!learning?.checkpoint || !detail) return
    setBusy(true)
    try { setLearning(await api.post<LearningResult>(`${base}/pages/${detail.landing_id}/learning/${learning.checkpoint.checkpoint_id}/retry`, {})) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
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
  if (!detail) return <section className="panel landing-source-picker"><small>{tr('PRIVATE LANDING', 'ПРИВАТНИЙ ЛЕНДІНГ')}</small><h1>{tr('Create a Landing from an approved Post', 'Створіть лендінг із затвердженого допису')}</h1><p>{tr('Landing captures the selected Post version’s design, then remains independently editable.', 'Лендінг зафіксує дизайн обраної версії допису та далі редагуватиметься окремо.')}</p>{sources.length ? <div className="landing-source-list">{sources.map((source) => <button key={`${source.creative_id}:${source.version}`} className="panel" disabled={busy} onClick={() => void create(source)}><Sparkles /><span>{source.template_id} · v{source.version}</span><small>{source.creative_id.slice(0, 8)}</small></button>)}</div> : <Empty><h2>{tr('Approve a Post first', 'Спершу затвердьте допис')}</h2><p>{tr('Landing starts only from an immutable approved Post version.', 'Лендінг створюється лише з незмінної затвердженої версії допису.')}</p></Empty>}</section>
  if (status !== 'draft' || !configuration || !content) return <section className="panel landing-progress"><small>LANDING · {detail.template_id}</small><h1>{status === 'failed' ? tr('Landing generation needs attention', 'Створення лендінгу потребує уваги') : tr('Building the Landing', 'Створюємо лендінг')}</h1><p>{status === 'composing' ? tr('Writing the fixed page sections…', 'Заповнюємо фіксовані секції сторінки…') : status === 'generating_images' ? tr('Generating matching page visuals…', 'Створюємо візуали в стилі допису…') : tr('Queued for generation…', 'У черзі на створення…')}</p>{status === 'failed' && <button className="primary" disabled={busy} onClick={() => void retry()}><RefreshCcw />{tr('Retry', 'Повторити')}</button>}</section>

  const siblings = pages.filter(item => item.source_creative_id === detail.source_creative_id && item.source_version === detail.source_version)
  const isLatestSibling = siblings[0]?.landing_id === detail.landing_id
  const viewportControls = <div className="landing-device-controls" aria-label={tr('Preview width', 'Ширина прев’ю')}>{([[1280, Monitor, tr('Desktop', 'Комп’ютер')], [768, Tablet, tr('Tablet', 'Планшет')], [360, Smartphone, tr('Mobile', 'Телефон')]] as const).map(([size, Icon, name]) => <button key={size} className={width === size ? 'active' : ''} aria-label={`${name} ${size}`} aria-pressed={width === size} onClick={() => setWidth(size)}><Icon /><span>{size}</span></button>)}</div>
  const preview = (editing: boolean) => <LandingCanvas width={width}><LandingPage configuration={configuration} content={content} imageUrls={images} editing={editing} selected={section} onSelect={value => { setSection(value); setMode('edit') }} /></LandingCanvas>
  return <section className="landing-studio">
    <header className="landing-action-bar"><div><small>PRIVATE LANDING · POST v{detail.source_version}</small><h1>{tr('Landing Studio', 'Landing Studio')}</h1><p role="status">{busy ? tr('Working…', 'Виконуємо…') : dirty ? tr('Unsaved changes', 'Незбережені зміни') : checkpointPending ? tr('Draft updated · Save to capture your changes', 'Чернетку оновлено · Збережіть свої зміни') : notice || tr('Your private product page', 'Ваша приватна продуктова сторінка')}</p></div><div className="landing-actions">
      {pages.length > 1 && <select aria-label={tr('Landing variant', 'Варіант лендінгу')} value={detail.landing_id} disabled={busy || dirty} onChange={event => onLanding(event.target.value)}>{pages.map(item => <option key={item.landing_id} value={item.landing_id}>{tr('Landing', 'Лендінг')} {item.ordinal} · {item.approved_version_count ? tr('approved', 'затверджено') : tr('draft', 'чернетка')}</option>)}</select>}
      {isLatestSibling && detail.approved_version_count > 0 && <button className="secondary" disabled={busy || dirty} onClick={() => void createVariant()}><Plus />{tr('New variant', 'Новий варіант')}</button>}
      <button className="secondary" onClick={event => { event.currentTarget.focus(); setLandingViewOpen(true) }}><Maximize2 />{tr('View Landing', 'Переглянути лендінг')}</button>
      <button className="secondary" disabled={busy} onClick={() => void save(false)}><Save />{tr('Save Landing', 'Зберегти лендінг')}</button>
      <button className="primary" disabled={busy || issues.length > 0 || !note.trim()} onClick={() => void save(true)}><Check />{tr('Approve Landing', 'Затвердити лендінг')}</button>
    </div></header>
    {error && !learning && <div className="landing-inline-error" role="alert">{error}<button className="ghost" onClick={() => setError('')}>{tr('Dismiss', 'Закрити')}</button></div>}
    <div className="landing-workspace-toolbar"><div className="landing-mode-controls"><button className={mode === 'edit' ? 'active' : ''} aria-pressed={mode === 'edit'} onClick={() => setMode('edit')}>{tr('Edit', 'Редагувати')}</button><button className={mode === 'preview' ? 'active' : ''} aria-pressed={mode === 'preview'} onClick={() => setMode('preview')}>{tr('Preview', 'Перегляд')}</button></div>{viewportControls}<button className="landing-readiness-trigger" onClick={() => { setMode('edit'); setSection(issues[0]?.section || 'theme') }}>{issues.length ? tr(`${issues.length} to finish`, `${issues.length} до завершення`) : tr('Ready for approval', 'Готово до затвердження')}</button></div>
    <div className={`landing-workbench is-${mode}`}>
      <aside className="landing-editor"><nav className="landing-section-nav" aria-label={tr('Page sections', 'Секції сторінки')}>{sections.map(key => <button key={key} aria-label={labels[language][key]} className={section === key ? 'active' : ''} aria-current={section === key ? 'true' : undefined} onClick={() => setSection(key)}>{labels[language][key]}{issues.some(issue => issue.section === key) && <span aria-label={tr('Needs attention', 'Потребує уваги')}>·</span>}</button>)}</nav>
        <div className="landing-inspector"><header><small>{tr('SECTION EDITOR', 'РЕДАКТОР СЕКЦІЇ')}</small><h2>{labels[language][section]}</h2></header>
          <LandingInspector section={section} configuration={configuration} content={content} detail={detail} onConfiguration={setConfiguration} onContent={setContent} language={language} busy={busy} issues={issues} imageUrls={images} onGenerate={(slot, enhance) => void generate(slot, enhance)} onSelectImage={(slot, sha) => void selectVisual(slot, sha)} />
          <details className="landing-readiness"><summary>{issues.length ? tr(`${issues.length} items before approval`, `${issues.length} пунктів до затвердження`) : tr('Ready for approval', 'Готово до затвердження')}</summary>{issues.map(issue => <button key={issue.path} onClick={() => setSection(issue.section)}>{issue[language]}</button>)}<LandingField label={tr('Approval note', 'Нотатка затвердження')} value={note} max={240} onChange={setNote} /></details>
        </div>
      </aside>
      <div className="landing-preview-area">{preview(mode === 'edit')}</div>
    </div>
    {landingViewOpen && <LandingDialog title={tr('Full-screen Landing preview', 'Повноекранне прев’ю лендінгу')} onClose={() => setLandingViewOpen(false)} className="landing-fullscreen"><div className="landing-dialog-toolbar">{viewportControls}<small>{tr('PRIVATE LANDING', 'ПРИВАТНИЙ ЛЕНДІНГ')}</small></div>{preview(false)}</LandingDialog>}
    {learning?.checkpoint && <LandingDialog title={tr('Landing saved · Project learning', 'Лендінг збережено · Навчання проєкту')} onClose={() => setLearning(null)} className="landing-learning"><div className="landing-learning-content">{error && <p role="alert">{error}</p>}
      {learning.checkpoint.status === 'failed' ? <><p>{tr('Your Landing is saved. Learning can be retried.', 'Лендінг збережено. Навчання можна повторити.')}</p><button className="secondary" disabled={busy} onClick={() => void retryLearning()}>{tr('Retry learning', 'Повторити навчання')}</button></> : <><p>{learning.checkpoint.edit_summary}</p><p>{learning.checkpoint.project_lesson || tr('Your changes have been saved as a Project lesson.', 'Ваші зміни збережено як урок для проєкту.')}</p>{learning.learning_proposal && <><h3>{tr('Suggested global rule', 'Запропоноване глобальне правило')}</h3><p>{learning.learning_proposal.global_rule}</p><div className="landing-actions"><button className="primary" disabled={busy} onClick={() => void decideLearning('apply_global')}>{tr('Apply globally', 'Застосувати глобально')}</button><button className="secondary" disabled={busy} onClick={() => void decideLearning('keep_project')}>{tr('Keep project-only', 'Лише для проєкту')}</button></div></>}</>}
    </div></LandingDialog>}
  </section>
}
