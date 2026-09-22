import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiFailure, type ApiClient } from '../api'
import type { Language } from '../i18n'
import { imageReferencePayload, referenceAccept, supportedReference } from '../components/ImageReferenceInput'
import './TemplatesView.css'

type Surface = 'post' | 'landing'
type Identity = { surface: Surface; template_id: string; template_version: number; template_sha256: string }
type Preview = { sha256: string; definition_sha256: string; render_contract_sha256?: string; applied_correction_id?: string; failures?: Array<{ issue: string; role: string }>; failure_count?: number }
type Template = Identity & { name: string; description: string; builtin: boolean; status: string; preview_status: string; previews: Record<string, Preview>; document?: { components: Array<{ id: string; type: string; role: string }> }; post_reference?: Omit<Identity, 'surface'> }
type Difference = { surface: string; role: string; issue: string; severity: string; solvable: boolean; category?: string }
type Gap = { capability: string; evidence: string; proposed_abstraction: string; why_composition_insufficient: string }
type Failure = { phase: string; category: string; model: string; reasoning_effort: string; attempt_count: number; validation_error?: string }
type CheckpointDifference = { surface: string; role: string; category: string }
type Checkpoint = { reason: string; recommendation: string; pending_edits: number; remaining_iterations: number; meaningful_differences: CheckpointDifference[] }
type Correction = { correction_id: string; instruction: string; status: 'working' | 'failed' | 'applied' | 'discarded'; submitted_revision: number; result_revision?: number | null; reference?: { sha256: string; mime_type: string; byte_count: number } | null; failure?: Failure | null; retry_count: number }
type Run = { run_id: string; scope: string; status: string; state_sha256: string; phase: string; iterations: number; error: string | null; failure?: Failure; checkpoint?: Checkpoint; can_restore?: boolean; retry_ready?: boolean; previews: Record<string, Preview>; comparison: { differences: Difference[]; applied_correction_id?: string } | null; capability_gap: Gap | null; accepted_versions: Identity[]; invocations: Array<{ phase: string; contract_bytes: { total: number }; response_bytes: number; attempt_count: number }>; latest_correction?: Correction | null; correction_history?: Correction[] }
type RunSummary = Pick<Run, 'run_id' | 'scope' | 'status' | 'state_sha256' | 'phase' | 'iterations' | 'error' | 'failure' | 'checkpoint' | 'previews'> & { latest_correction_status?: string | null }
type Pending = { path: string; body: Record<string, unknown> }
type LocalCorrection = Pick<Correction, 'correction_id' | 'instruction' | 'status'>
function TemplateReferences({ files, onChange, disabled, language }: { files: File[]; onChange: (files: File[]) => void; disabled: boolean; language: Language }) {
  const [error, setError] = useState('')
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  return <div className="template-references">
    <label>{tr('Visual references (up to 2)', 'Візуальні референси (до 2)')}
      <input type="file" accept={referenceAccept} multiple disabled={disabled || files.length >= 2} onChange={event => {
        const selected = Array.from(event.target.files || [])
        event.currentTarget.value = ''
        if (files.length + selected.length > 2 || selected.some(file => !supportedReference(file) || !file.size || file.size > 8 * 1024 * 1024)) {
          setError(tr('Add up to two PNG, JPEG, WebP, or SVG files, each up to 8 MB.', 'Додайте до двох PNG, JPEG, WebP або SVG, кожен до 8 МБ.'))
          return
        }
        setError(''); onChange([...files, ...selected])
      }} />
    </label>
    <small>{tr('Files are visual context in the order shown. SVG is converted to safe PNG before the agent sees it.', 'Файли слугують візуальним контекстом у вказаному порядку. SVG перетворюється на безпечний PNG перед передачею агенту.')}</small>
    {files.map((file, index) => <div className="template-reference-file" key={`${file.name}:${index}`}><span>{index + 1}. {file.name}</span><button type="button" className="secondary" disabled={disabled} onClick={() => onChange(files.filter((_, at) => at !== index))}>{tr('Remove', 'Видалити')}</button></div>)}
    {error && <p role="alert">{error}</p>}
  </div>
}
const base = '/api/v1/templates'
const activeStates = ['queued', 'analyzing', 'composing', 'rendering', 'comparing']
const correctionStorageKey = (runId: string) => `ptw:template-corrections:${runId}`
function readLocalCorrections(runId: string): LocalCorrection[] {
  try { const value = JSON.parse(window.localStorage.getItem(correctionStorageKey(runId)) || '[]'); return Array.isArray(value) ? value.slice(0, 2) : [] } catch { return [] }
}
function writeLocalCorrections(runId: string, values: LocalCorrection[]) {
  try { window.localStorage.setItem(correctionStorageKey(runId), JSON.stringify(values.slice(0, 2))) } catch { /* Browser storage is optional. */ }
}
function identity(item: Identity): Identity { return { surface: item.surface, template_id: item.template_id, template_version: item.template_version, template_sha256: item.template_sha256 } }
function versionPath(item: Identity) { return `${base}/${item.surface}/${item.template_id}/versions/${item.template_version}` }

export function TemplateImage({ api, preview, label, language = 'en' }: { api: ApiClient; preview?: Preview; label: string; language?: Language }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let cancelled = false, objectUrl = ''
    setUrl(''); setError('')
    if (preview) void api.image(`${base}/media/${preview.sha256}`, 'image/png', preview.sha256).then(blob => {
      if (cancelled) return
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl)
    }).catch((cause: Error) => { if (!cancelled) setError(cause.message) })
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, preview?.sha256, retry])
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  return <div className="template-image">{url ? <a href={url} target="_blank" rel="noreferrer" aria-label={`${tr('Open full resolution', 'Відкрити повний розмір')}: ${label}`}><img src={url} alt={label} /></a> : error ? <div role="alert"><p>{error}</p><button onClick={() => setRetry(value => value + 1)}>{tr('Retry preview', 'Повторити прев’ю')}</button></div> : <p role="status">{preview ? tr('Loading preview…', 'Завантаження прев’ю…') : tr('Preview appears after the first render.', 'Прев’ю з’явиться після першого рендера.')}</p>}</div>
}

export function TemplatesView({ api, language }: { api: ApiClient; language: Language }) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const [filter, setFilter] = useState<'all' | Surface>('all')
  const [items, setItems] = useState<Template[] | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [selected, setSelected] = useState<Template | null>(null)
  const [versions, setVersions] = useState<Identity[]>([])
  const [creating, setCreating] = useState(false)
  const [source, setSource] = useState<Identity | null>(null)
  const [scope, setScope] = useState<'post' | 'landing' | 'combined'>('post')
  const [instruction, setInstruction] = useState('')
  const [references, setReferences] = useState<File[]>([])
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [openingRunId, setOpeningRunId] = useState<string | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [handoff, setHandoff] = useState('')
  const [refining, setRefining] = useState(false)
  const [localCorrections, setLocalCorrections] = useState<LocalCorrection[]>([])
  const generation = useRef(0)
  const mounted = useRef(true)
  const pollGeneration = useRef(0)
  const galleryGeneration = useRef(0)
  const runPanel = useRef<HTMLElement>(null)
  const revealRun = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current++; pollGeneration.current++; galleryGeneration.current++ } }, [])

  const refresh = useCallback(async () => {
    const current = ++galleryGeneration.current
    try {
      const [gallery, history] = await Promise.all([api.get<{ items: Template[] }>(base + (filter === 'all' ? '' : `?surface=${filter}`), { deadlineMs: 120_000 }), api.get<{ items: RunSummary[] }>(`${base}/runs`)])
      if (!mounted.current || current !== galleryGeneration.current) return
      setItems(gallery.items); setRuns(history.items)
    } catch (cause) { if (mounted.current && current === galleryGeneration.current) setError((cause as Error).message) }
  }, [api, filter])
  useEffect(() => { setItems(null); setError(''); void refresh() }, [refresh])
  useEffect(() => {
    if (!runs.some(item => activeStates.includes(item.status))) return
    const timer = setTimeout(() => void refresh(), 1500)
    return () => clearTimeout(timer)
  }, [runs, refresh])

  const openRun = useCallback(async (id: string) => {
    const current = ++generation.current
    revealRun.current = true
    setOpeningRunId(id)
    setError(''); setSelected(null); setCreating(false); setRefining(false); setReferences([]); setInstruction(''); setHandoff('')
    try {
      const value = await api.get<Run>(`${base}/runs/${id}`)
      if (!mounted.current || current !== generation.current) return
      setRun(value)
      const saved = readLocalCorrections(id)
      const remaining = value.latest_correction ? saved.filter(item => item.correction_id !== value.latest_correction?.correction_id) : saved
      writeLocalCorrections(id, remaining); setLocalCorrections(remaining)
      const url = new URL(window.location.href); url.searchParams.set('template_run', id); window.history.replaceState(null, '', url)
    } catch (cause) {
      if (current === generation.current) { revealRun.current = false; setError((cause as Error).message) }
    } finally {
      if (mounted.current && current === generation.current) setOpeningRunId(null)
    }
  }, [api])
  useEffect(() => { const id = new URLSearchParams(window.location.search).get('template_run'); if (id) void openRun(id) }, [openRun])
  useEffect(() => {
    if (!run || !revealRun.current || !runPanel.current) return
    revealRun.current = false
    runPanel.current.focus({ preventScroll: true })
    runPanel.current.scrollIntoView({
      block: 'start',
      behavior: 'auto',
    })
  }, [run])
  useEffect(() => {
    if (!run || !activeStates.includes(run.status)) return
    const current = ++pollGeneration.current
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const value = await api.get<Run>(`${base}/runs/${run.run_id}`)
        if (current !== pollGeneration.current || !mounted.current) return
        setRun(value)
        if (value.latest_correction) setLocalCorrections(currentValues => {
          const remaining = currentValues.filter(item => item.correction_id !== value.latest_correction?.correction_id)
          writeLocalCorrections(value.run_id, remaining); return remaining
        })
        if (activeStates.includes(value.status)) timer = setTimeout(() => void poll(), 1500)
        else void refresh()
      } catch (cause) { if (current === pollGeneration.current) setError((cause as Error).message) }
    }
    timer = setTimeout(() => void poll(), 1000)
    return () => { pollGeneration.current++; clearTimeout(timer) }
  }, [api, run?.run_id, run?.status, refresh])

  const mutate = async (operation: Pending) => {
    setPending(operation); setBusy(true); setError('')
    const id = String(operation.body.request_id)
    // Only the reconciliation ID survives refresh, never screenshots or owner text.
    if (operation.path === `${base}/runs`) {
      const url = new URL(window.location.href); url.searchParams.set('template_run', id); window.history.replaceState(null, '', url)
    }
    try {
      const value = await api.post<Run>(operation.path, operation.body, { deadlineMs: 30_000 })
      if (!mounted.current) return
      setPending(null); setRun(value); setCreating(false); setRefining(false); setSelected(null); setInstruction(''); setReferences([])
      if (value.latest_correction) setLocalCorrections(currentValues => {
        const remaining = currentValues.filter(item => item.correction_id !== value.latest_correction?.correction_id)
        writeLocalCorrections(value.run_id, remaining); return remaining
      })
      const url = new URL(window.location.href); url.searchParams.set('template_run', value.run_id); window.history.replaceState(null, '', url)
      void refresh()
    } catch (cause) {
      if (mounted.current) {
        setError((cause as Error).message)
        if (cause instanceof ApiFailure && [400, 404, 409, 413, 422].includes(cause.details.status || 0)) setPending(null)
      }
    }
    finally { if (mounted.current) setBusy(false) }
  }
  const submit = async () => {
    setBusy(true); setError('')
    const referenceIds: string[] = []
    const requestId = crypto.randomUUID()
    if (run) {
      const next = [{ correction_id: requestId, instruction: instruction.trim(), status: 'working' as const }, ...localCorrections].slice(0, 2)
      setLocalCorrections(next); writeLocalCorrections(run.run_id, next)
    }
    try {
      for (const file of references) {
        const uploaded = await api.post<{ reference_id: string }>(`${base}/references`, { request_id: crypto.randomUUID(), image: await imageReferencePayload(file) })
        referenceIds.push(uploaded.reference_id)
      }
      const body = { request_id: requestId, instruction, ...(run ? { mode: 'refine' } : {}), ...(referenceIds.length ? { reference_ids: referenceIds } : {}) }
      await mutate(run ? { path: `${base}/runs/${run.run_id}/resume`, body: { ...body, base_sha256: run.state_sha256 } }
        : { path: `${base}/runs`, body: { ...body, scope, ...(source ? { source } : {}) } })
    } catch (cause) {
      if (mounted.current) { setError((cause as Error).message); setBusy(false) }
      if (run) setLocalCorrections(currentValues => {
        const failed = currentValues.map(item => item.correction_id === requestId ? { ...item, status: 'failed' as const } : item)
        writeLocalCorrections(run.run_id, failed); return failed
      })
      for (const referenceId of referenceIds) void api.post(`${base}/references/${referenceId}/discard`, {}).catch(() => {})
    }
  }
  const inspect = async (item: Identity) => {
    const current = ++generation.current
    setError(''); setBusy(true); setRun(null); setCreating(false); setReferences([])
    try {
      const [value, history] = await Promise.all([api.get<Template>(`${versionPath(item)}?sha256=${item.template_sha256}`), api.get<{ items: Identity[] }>(`${base}/${item.surface}/${item.template_id}/versions`)])
      if (mounted.current && current === generation.current) { setSelected(value); setVersions(history.items) }
    } catch (cause) { if (current === generation.current) setError((cause as Error).message) }
    finally { if (current === generation.current) setBusy(false) }
  }
  const begin = (item?: Template) => {
    generation.current++; pollGeneration.current++
    setSource(item ? identity(item) : null); setScope(item?.surface || 'post'); setInstruction(''); setReferences([])
    setRun(null); setSelected(null); setCreating(true); setRefining(false); setError(''); setHandoff('')
    const url = new URL(window.location.href); url.searchParams.delete('template_run'); window.history.replaceState(null, '', url)
  }
  const working = !!run && activeStates.includes(run.status)
  const canCorrect = !!run && !working && !['accepted', 'rejected'].includes(run.status)
  const localCorrection = localCorrections[0]
  // An unconfirmed browser-side request is newer than the last server record.
  // Keep it visible and keep Accept hidden until the server acknowledges its ID.
  const currentCorrection: Correction | LocalCorrection | null = localCorrection || run?.latest_correction || null
  const unresolvedCorrection = currentCorrection?.status === 'working' || currentCorrection?.status === 'failed'
  const canAccept = !!run && run.status === 'proposed' && !unresolvedCorrection
  const currentComparison = !!run?.comparison && (!currentCorrection || (currentCorrection.status === 'applied' && run.comparison.applied_correction_id === currentCorrection.correction_id))
  const drafts = runs.filter(item => !['accepted', 'rejected'].includes(item.status))
  const history = runs.filter(item => ['accepted', 'rejected'].includes(item.status))
  const statusLabel = (status: string) => ({
    queued: tr('Queued', 'У черзі'), analyzing: tr('Analyzing', 'Аналіз'), composing: tr('Composing', 'Компонування'),
    rendering: tr('Rendering', 'Рендеринг'), comparing: tr('Comparing', 'Порівняння'), failed: tr('Failed', 'Помилка'),
    interrupted: tr('Interrupted', 'Перервано'), paused: tr('Paused', 'Призупинено'),
    capability_gap: tr('Capability needed', 'Потрібне розширення'), proposed: tr('Ready for review', 'Готово до перевірки'),
    accepted: tr('Accepted', 'Прийнято'), rejected: tr('Rejected', 'Відхилено'),
  } as Record<string, string>)[status] || status
  const phaseLabel = (phase: string) => ({
    analyze: tr('Analysis', 'Аналіз'), compose: tr('Composition', 'Компонування'), render: tr('Rendering', 'Рендеринг'), compare: tr('Comparison', 'Порівняння'), adjust: tr('Saved changes', 'Збережені зміни'),
  } as Record<string, string>)[phase] || phase
  const failureLabel = (failure?: Failure, fallback?: string | null) => failure ? ({
    timeout: tr('Comparison timed out. Continue to retry the saved preview.', 'Порівняння перевищило час. Продовжте, щоб повторити зі збереженим прев’ю.'),
    validation: tr('The comparison response was invalid. Continue to retry it.', 'Відповідь порівняння не пройшла перевірку. Продовжте, щоб повторити.'),
    cancelled: tr('The agent was stopped. Continue from the saved state.', 'Агента зупинено. Продовжте зі збереженого стану.'),
    provider: tr('The agent call failed. Continue from the saved state.', 'Виклик агента завершився помилкою. Продовжте зі збереженого стану.'),
    contract: tr('The service rejected its own agent request before completion. Your edit is saved; retry after the service is repaired.', 'Сервіс відхилив власний запит до агента. Ваше уточнення збережено; повторіть його після виправлення сервісу.'),
  } as Record<string, string>)[failure.category] || fallback || '' : fallback === 'Iteration limit reached; resume the saved composition'
    ? tr('Review checkpoint reached. The current preview and suggested changes are saved.', 'Досягнуто контрольної точки. Поточне прев’ю та запропоновані зміни збережено.')
    : fallback || ''
  const categoryLabel = (category?: string) => ({
    component_missing: tr('Missing reusable component', 'Бракує багаторазового компонента'),
    image_fixture: tr('Preview image', 'Зображення у прев’ю'), typography: tr('Typography', 'Типографіка'),
    appearance: tr('Color and appearance', 'Колір і вигляд'), image_crop: tr('Image crop', 'Кадрування зображення'),
    layout: tr('Layout and spacing', 'Композиція та відступи'), component_style: tr('Component appearance', 'Вигляд компонента'),
    visual_match: tr('Visual match', 'Візуальна відповідність'),
  } as Record<string, string>)[category || ''] || tr('Visual match', 'Візуальна відповідність')
  const roleLabel = (role: string) => ({
    decoration: tr('Decoration', 'Декор'), cta: tr('Actions', 'Кнопки дії'), hero: tr('Hero image', 'Головне зображення'),
    headline: tr('Headline', 'Заголовок'), description: tr('Supporting text', 'Допоміжний текст'), brand: tr('Brand', 'Бренд'),
  } as Record<string, string>)[role] || role
  const checkpointLabel = (checkpoint?: Checkpoint) => {
    if (!checkpoint) return ''
    return ({
      segment_checkpoint: tr('The current preview is saved. The agent has prepared useful changes for the next comparison.', 'Поточне прев’ю збережено. Агент підготував корисні зміни для наступного порівняння.'),
      no_progress: tr('The same visual issue repeated. Restore the last ready version or add a focused clarification.', 'Та сама візуальна проблема повторилася. Поверніть останню готову версію або додайте точне уточнення.'),
      needs_clarification: tr('The agent needs a focused clarification before it can continue.', 'Агенту потрібне точне уточнення перед продовженням.'),
      total_budget: tr('The bounded run budget is exhausted. Restore the last ready version.', 'Обмежений бюджет запуску вичерпано. Поверніть останню готову версію.'),
      time_budget: tr('The time checkpoint was reached. The saved phase can continue safely.', 'Досягнуто часової контрольної точки. Збережену фазу можна безпечно продовжити.'),
      interrupted: tr('The process restarted. Continue from the saved phase.', 'Процес перезапустився. Продовжте зі збереженої фази.'),
      provider_failure: tr('The model request failed, but the composition and preview are saved.', 'Запит до моделі не виконався, але композицію та прев’ю збережено.'),
      contract_failure: tr('The agent service needs repair before this saved request can continue.', 'Сервіс агента потребує виправлення, перш ніж продовжити збережений запит.'),
      capability_gap: tr('A reusable renderer capability is required before comparison can finish.', 'Для завершення порівняння потрібна нова багаторазова можливість рендера.'),
    } as Record<string, string>)[checkpoint.reason] || tr('The current result is saved and needs your action.', 'Поточний результат збережено й очікує вашої дії.')
  }
  const continueRun = () => run && mutate({ path: `${base}/runs/${run.run_id}/resume`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256, instruction: '', mode: 'continue' } })
  const retryCorrection = () => run && mutate({ path: `${base}/runs/${run.run_id}/corrections/retry`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256 } })
  const discardCorrection = () => run && mutate({ path: `${base}/runs/${run.run_id}/corrections/discard`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256 } })
  return <section className="templates-view">
    <header className="page-header"><div><h1>{tr('Templates', 'Шаблони')}</h1><p>{tr('Reusable Post and Landing designs', 'Багаторазові дизайни дописів і лендінгів')}</p></div><button onClick={() => begin()} disabled={busy || !!pending}>{tr('Create Template Agent', 'Агент створення шаблону')}</button></header>
    {error && <div role="alert" className="notice"><p>{error}</p>{pending ? <button disabled={busy} onClick={() => void mutate(pending)}>{tr('Retry same request', 'Повторити той самий запит')}</button> : <button onClick={() => { setError(''); if (run) void openRun(run.run_id); else void refresh() }}>{tr('Retry', 'Повторити')}</button>}</div>}
    {creating && <form className="template-form" onSubmit={event => { event.preventDefault(); void submit() }}>
      <h2>{source ? tr('Edit as a new version', 'Редагувати як нову версію') : tr('Create Template Agent', 'Агент створення шаблону')}</h2>
      <label>{tr('Creation scope', 'Тип створення')}<select value={scope} disabled={!!source || busy || !!pending} onChange={event => setScope(event.target.value as typeof scope)}><option value="post">Post</option><option value="landing">Landing</option><option value="combined">Post + Landing</option></select></label>
      {source && <p>{tr('Source', 'Джерело')}: {source.template_id} · v{source.template_version}</p>}
      <label>{tr('Design instruction', 'Інструкція дизайну')}<textarea value={instruction} maxLength={3000} rows={4} disabled={busy || !!pending} onChange={event => setInstruction(event.target.value)} placeholder={tr('Describe the layout, or upload a visual reference', 'Опишіть композицію або додайте референс')} /></label>
      <TemplateReferences files={references} onChange={setReferences} disabled={busy || !!pending} language={language} />
      <p>{tr('Reference analysis is saved, while raw pixels are temporary. Reattaching the same image after a restart is optional and enables direct image comparison.', 'Аналіз референсу зберігається, а сирі пікселі — тимчасові. Після перезапуску те саме зображення можна додати знову для прямого порівняння, але це необов’язково.')}</p>
      <button type="submit" disabled={busy || !!pending || (!instruction.trim() && !references.length)}>{busy ? tr('Submitting…', 'Надсилання…') : tr('Start creation', 'Почати створення')}</button>
    </form>}
    {run && <section ref={runPanel} className="template-run" tabIndex={-1} aria-live="polite" aria-labelledby="template-run-title">
      <header className="template-run-header"><div><span className="template-run-status" data-status={run.status}>{statusLabel(run.status)}</span><h2 id="template-run-title">{run.status === 'proposed' ? tr('Review template', 'Перевірка шаблону') : tr('Template workspace', 'Робоча область шаблону')} · {run.scope === 'combined' ? 'Post + Landing' : run.scope === 'post' ? 'Post' : 'Landing'}</h2></div><p>{tr('Step', 'Етап')}: {phaseLabel(run.phase)} · {run.iterations} {tr('comparisons', 'порівнянь')}</p></header>
      <div className="template-workspace">
        <div className="template-workspace-preview"><h3>{tr('Current preview', 'Поточне прев’ю')}</h3><div className="template-preview-grid">{Object.entries(run.previews).map(([key, preview]) => <figure key={key}><TemplateImage api={api} preview={preview} label={key} language={language} /><figcaption>{key}</figcaption></figure>)}</div></div>
        <aside className="template-workspace-panel">
          {currentCorrection && <section className="template-owner-request" aria-labelledby="template-owner-request-title">
            <div><h3 id="template-owner-request-title">{tr('Your request', 'Ваш запит')}</h3><span data-status={currentCorrection.status}>{currentCorrection.status === 'working' ? tr('In progress', 'Виконується') : currentCorrection.status === 'failed' ? tr('Needs retry', 'Потрібен повтор') : currentCorrection.status === 'applied' ? tr('Applied', 'Застосовано') : tr('Discarded', 'Відкинуто')}</span></div>
            <p>{currentCorrection.instruction}</p>
            <ol className="template-correction-steps" aria-label={tr('Correction progress', 'Хід уточнення')}>
              {['compose', 'render', 'compare'].map((phase, index) => { const phaseIndex = ['compose', 'render', 'compare'].indexOf(run.phase); const state = currentCorrection.status === 'applied' ? 'complete' : currentCorrection.status === 'failed' && phase === run.phase ? 'failed' : phaseIndex > index ? 'complete' : phaseIndex === index ? 'active' : 'pending'; return <li key={phase} data-state={state}>{phase === 'compose' ? tr('Composition', 'Компонування') : phase === 'render' ? tr('Rendering', 'Рендеринг') : tr('Comparison', 'Порівняння')}</li> })}
            </ol>
            {currentCorrection.status === 'failed' && <div className="template-actions">{run.failure?.category === 'contract' && <p role="alert">{run.retry_ready ? tr('The service is ready to retry this saved edit.', 'Сервіс готовий повторити збережене уточнення.') : failureLabel(run.failure)}</p>}<button disabled={busy || !!pending || !run.latest_correction || (run.failure?.category === 'contract' && !run.retry_ready)} onClick={() => void retryCorrection()}>{tr('Retry my correction', 'Повторити моє уточнення')}</button>{run.can_restore && <button className="secondary" disabled={busy || !!pending} onClick={() => void discardCorrection()}>{tr('Discard this correction and restore the previous version', 'Відкинути це уточнення і повернути попередню версію')}</button>}</div>}
          </section>}
          {working && <div className="template-action-card"><h3>{tr('Agent is working', 'Агент працює')}</h3><p>{tr('The saved preview will update after the next comparison.', 'Збережене прев’ю оновиться після наступного порівняння.')}</p></div>}
          {!working && canAccept && <div className="template-action-card template-action-ready"><h3>{tr('Ready for your review', 'Готово до вашої перевірки')}</h3><p>{tr('Check the preview. Accepting creates an immutable version and makes it available in Projects.', 'Перевірте прев’ю. Прийняття створить незмінну версію та зробить її доступною у проєктах.')}</p><div className="template-actions"><button disabled={busy || !!pending} onClick={() => void mutate({ path: `${base}/runs/${run.run_id}/decision`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256, decision: 'accept' } })}>{tr('Accept template version', 'Прийняти версію шаблону')}</button><button className="secondary" disabled={busy || !!pending} onClick={() => setRefining(true)}>{tr('Request changes', 'Запросити зміни')}</button></div></div>}
          {!working && canCorrect && run.status !== 'proposed' && <div className="template-action-card"><h3>{run.checkpoint?.recommendation === 'continue' || (!run.checkpoint && run.phase === 'adjust') ? tr('Safe to continue', 'Можна продовжувати') : tr('Your action is needed', 'Потрібна ваша дія')}</h3><p role="alert">{run.failure?.category === 'contract' ? failureLabel(run.failure, run.error) : checkpointLabel(run.checkpoint) || failureLabel(run.failure, run.error)}</p>{run.checkpoint && <p className="template-budget">{run.checkpoint.pending_edits > 0 ? tr(`${run.checkpoint.pending_edits} saved changes are ready. `, `Підготовлено змін: ${run.checkpoint.pending_edits}. `) : ''}{tr(`${run.checkpoint.remaining_iterations} comparisons remain in this run.`, `У цьому запуску залишилось порівнянь: ${run.checkpoint.remaining_iterations}.`)}</p>}<div className="template-actions">{!currentCorrection && (run.checkpoint?.recommendation === 'continue' || (!run.checkpoint && ['adjust', 'compare'].includes(run.phase))) && <button disabled={busy || !!pending} onClick={() => void continueRun()}>{tr('Continue saved changes', 'Продовжити збережені зміни')}</button>}<button className="secondary" disabled={busy || !!pending} onClick={() => setRefining(value => !value)}>{tr('Add clarification', 'Додати уточнення')}</button>{run.can_restore && !currentCorrection && <button className="secondary" disabled={busy || !!pending} onClick={() => void discardCorrection()}>{tr('Restore last ready version', 'Повернути останню готову версію')}</button>}</div></div>}
          {currentComparison && ((run.checkpoint?.meaningful_differences?.length || run.comparison?.differences.some(item => item.severity === 'meaningful')) ? <div className="template-findings"><h3>{tr('What remains', 'Що ще відрізняється')}</h3><ul>{(run.checkpoint?.meaningful_differences || run.comparison?.differences.filter(item => item.severity === 'meaningful') || []).map((item, index) => <li key={`${item.surface}-${item.role}-${index}`}><strong>{roleLabel(item.role)}</strong><span>{categoryLabel(item.category)}</span></li>)}</ul></div> : run.status === 'proposed' && <p className="template-complete">{tr('No unresolved visual differences reported.', 'Невирішених візуальних розбіжностей немає.')}</p>)}
          {refining && canCorrect && <form className="template-refine-form" onSubmit={event => { event.preventDefault(); void submit() }}><h3>{tr('Clarify the requested change', 'Уточніть потрібну зміну')}</h3><label>{tr('Instruction', 'Уточнення')}<textarea value={instruction} maxLength={3000} rows={4} disabled={busy || !!pending} onChange={event => setInstruction(event.target.value)} placeholder={tr('Describe only what should change from this preview', 'Опишіть лише те, що потрібно змінити в цьому прев’ю')} /></label><TemplateReferences files={references} onChange={setReferences} disabled={busy || !!pending} language={language} /><p>{tr('Attach up to two assets or screenshots. They guide this edit and do not overwrite registered assets.', 'Додайте до двох assets або скриншотів. Вони спрямовують це редагування й не перезаписують зареєстровані assets.')}</p><div className="template-actions"><button type="submit" disabled={busy || !!pending || !instruction.trim()}>{busy ? tr('Submitting…', 'Надсилання…') : tr('Apply clarification', 'Застосувати уточнення')}</button><button type="button" className="secondary" onClick={() => setRefining(false)}>{tr('Cancel', 'Скасувати')}</button></div></form>}
          {run.capability_gap && <div className="notice"><h3>{tr('Reusable capability needed', 'Потрібна багаторазова можливість')}</h3><p>{run.capability_gap.evidence}</p><button onClick={() => void api.get(`${base}/runs/${run.run_id}/capability-handoff`).then(value => setHandoff(JSON.stringify(value, null, 2))).catch(cause => setError(cause.message))}>{tr('Prepare development handoff', 'Підготувати завдання розробки')}</button>{handoff && <textarea aria-label="Development handoff" readOnly value={handoff} rows={10} />}</div>}
          {run.accepted_versions.map(item => <button key={item.surface} onClick={() => void inspect(item)}>{tr('Open', 'Відкрити')} {item.surface} · v{item.template_version}</button>)}
        </aside>
      </div>
      <details className="template-technical"><summary>{tr('Technical details', 'Технічні деталі')}</summary><p className="template-id">{run.run_id}</p>{run.error && <p>{failureLabel(run.failure, run.error)}</p>}{run.comparison?.differences.length ? <ul>{run.comparison.differences.map((d, i) => <li key={i}>{d.surface} / {d.role}: {d.issue} ({d.severity})</li>)}</ul> : null}<h3>{tr('Operation measurements', 'Вимірювання операції')}</h3><ul>{run.invocations.map((v, i) => <li key={i}>{v.phase}: {v.contract_bytes.total.toLocaleString()} B input · {v.response_bytes.toLocaleString()} B response · {v.attempt_count} attempt(s)</li>)}</ul>{!working && !['accepted', 'rejected'].includes(run.status) && <button className="secondary template-reject" disabled={busy || !!pending} onClick={() => void mutate({ path: `${base}/runs/${run.run_id}/decision`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256, decision: 'reject' } })}>{tr('Reject this draft', 'Відхилити цю чернетку')}</button>}</details>
    </section>}
    {selected && <section className="template-detail"><h2>{selected.name} · v{selected.template_version}</h2><p>{selected.description}</p><p>{selected.builtin ? tr('Built-in · edits create a derivative', 'Вбудований · редагування створює похідний шаблон') : tr('Immutable registered version', 'Незмінна зареєстрована версія')}</p><small className="template-id">{selected.template_id} · {selected.template_sha256}</small>
      {versions.length > 1 && <label>{tr('Version', 'Версія')}<select value={selected.template_version} onChange={event => { const item = versions.find(v => v.template_version === Number(event.target.value)); if (item) void inspect(item) }}>{versions.map(item => <option key={item.template_version} value={item.template_version}>v{item.template_version}</option>)}</select></label>}
      {selected.preview_status === 'failed' && Object.keys(selected.previews).length === 0 && <div className="notice" role="status"><p>{tr('This template is available, but its preview could not be rendered. Retry the preview or edit from your instruction.', 'Шаблон доступний, але прев’ю не вдалося створити. Повторіть спробу або редагуйте за своїм описом.')}</p><button className="secondary" disabled={busy} onClick={() => void inspect(selected)}>{tr('Retry preview', 'Повторити прев’ю')}</button></div>}
      <div className="template-preview-grid">{Object.entries(selected.previews).map(([key, preview]) => <figure key={key}><TemplateImage api={api} preview={preview} label={`${selected.name} ${key}`} language={language} /><figcaption>{key}</figcaption></figure>)}</div>
      {selected.document && <details><summary>{tr('Structured components', 'Структуровані компоненти')}</summary><ul>{selected.document.components.map(c => <li key={c.id}>{c.id} · {c.type} · {c.role}</li>)}</ul></details>}
      {selected.post_reference && <p className="template-id">Post: {selected.post_reference.template_id} · v{selected.post_reference.template_version} · {selected.post_reference.template_sha256}</p>}
      <button disabled={busy || !!pending} onClick={() => begin(selected)}>{tr('Edit template', 'Редагувати шаблон')}</button>
    </section>}
    {drafts.length > 0 && <section className="template-drafts" aria-labelledby="template-drafts-title"><div className="template-drafts-heading"><div><h2 id="template-drafts-title">{tr('Drafts', 'Чернетки')}</h2><p>{tr('Reference analysis is saved. Raw reference pixels are temporary; reattaching the same image is optional and enables direct image comparison after a restart.', 'Аналіз референсу збережено. Сирі пікселі референсу тимчасові; повторне додавання того самого зображення необов’язкове, але дає пряме порівняння зображень після перезапуску.')}</p></div></div><div className="template-draft-grid">{drafts.map(item => { const previewEntry = Object.entries(item.previews).find(([key]) => key.endsWith(':desktop')) || Object.entries(item.previews)[0]; const opening = openingRunId === item.run_id; return <article className="template-draft-card" key={item.run_id}><TemplateImage api={api} preview={previewEntry?.[1]} label={`${item.scope} draft`} language={language} /><div className="template-draft-body"><div className="template-draft-meta"><span>{item.scope === 'combined' ? 'Post + Landing' : item.scope === 'post' ? 'Post' : 'Landing'}</span><strong data-status={item.status}>{statusLabel(item.status)}</strong></div><p>{tr('Comparisons', 'Порівнянь')}: {item.iterations}</p>{item.checkpoint ? <p className="template-draft-error">{checkpointLabel(item.checkpoint)}</p> : (item.failure || item.error) && <p className="template-draft-error">{failureLabel(item.failure, item.error)}</p>}<details><summary>{tr('Details', 'Деталі')}</summary><small>{item.run_id}</small></details><button aria-busy={opening} disabled={busy || !!pending || opening} onClick={() => void openRun(item.run_id)}>{opening ? tr('Opening…', 'Відкриття…') : item.status === 'proposed' ? tr('Open for review', 'Відкрити для перевірки') : activeStates.includes(item.status) ? tr('Open', 'Відкрити') : tr('Review next action', 'Переглянути наступну дію')}</button></div></article> })}</div></section>}
    <div className="template-filter" role="group" aria-label={tr('Template surface', 'Тип шаблону')}>{(['all', 'post', 'landing'] as const).map(value => <button key={value} className="secondary" aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'all' ? tr('All templates', 'Усі шаблони') : value === 'post' ? 'Post' : 'Landing'}</button>)}</div>
    {items === null ? <p role="status">{tr('Loading templates…', 'Завантаження шаблонів…')}</p> : items.length === 0 ? <p>{tr('No templates for this surface yet.', 'Шаблонів цього типу ще немає.')}</p> : <div className="template-gallery">{items.map(item => <article key={`${item.surface}:${item.template_id}`} className="template-card"><TemplateImage api={api} preview={item.previews.desktop} label={`${item.name} preview`} language={language} /><div><h2>{item.name}</h2><p>{item.surface} · v{item.template_version} · {item.status}</p>{item.preview_status !== 'ready' && <button onClick={() => void refresh()}>{tr('Retry preview generation', 'Повторити створення прев’ю')}</button>}<button className="secondary" disabled={busy || !!pending} onClick={() => void inspect(item)}>{tr('Open template', 'Відкрити шаблон')}</button></div></article>)}</div>}
    {history.length > 0 && <details className="template-history"><summary>{tr('Accepted and rejected runs', 'Прийняті та відхилені створення')}</summary>{history.map(item => <button key={item.run_id} disabled={busy || !!pending} onClick={() => void openRun(item.run_id)}><span>{item.scope} · {statusLabel(item.status)}</span><small>{item.run_id}</small></button>)}</details>}
  </section>
}
