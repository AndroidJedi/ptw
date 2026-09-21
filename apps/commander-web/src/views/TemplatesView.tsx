import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiFailure, type ApiClient } from '../api'
import type { Language } from '../i18n'
import { ImageReferenceInput, imageReferencePayload } from '../components/ImageReferenceInput'
import './TemplatesView.css'

type Surface = 'post' | 'landing'
type Identity = { surface: Surface; template_id: string; template_version: number; template_sha256: string }
type Preview = { sha256: string; definition_sha256: string; failures?: Array<{ issue: string; role: string }>; failure_count?: number }
type Template = Identity & { name: string; description: string; builtin: boolean; status: string; preview_status: string; previews: Record<string, Preview>; document?: { components: Array<{ id: string; type: string; role: string }> }; post_reference?: Omit<Identity, 'surface'> }
type Difference = { surface: string; role: string; issue: string; severity: string; solvable: boolean }
type Gap = { capability: string; evidence: string; proposed_abstraction: string; why_composition_insufficient: string }
type Failure = { phase: string; category: string; model: string; reasoning_effort: string; attempt_count: number; validation_error?: string }
type Run = { run_id: string; scope: string; status: string; state_sha256: string; phase: string; iterations: number; error: string | null; failure?: Failure; previews: Record<string, Preview>; comparison: { differences: Difference[] } | null; capability_gap: Gap | null; accepted_versions: Identity[]; invocations: Array<{ phase: string; contract_bytes: { total: number }; response_bytes: number; attempt_count: number }> }
type RunSummary = Pick<Run, 'run_id' | 'scope' | 'status' | 'state_sha256' | 'phase' | 'iterations' | 'error' | 'failure' | 'previews'>
type Pending = { path: string; body: Record<string, unknown> }
const base = '/api/v1/templates'
const activeStates = ['queued', 'analyzing', 'composing', 'rendering', 'comparing']
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
  const [reference, setReference] = useState<File | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const [handoff, setHandoff] = useState('')
  const generation = useRef(0)
  const mounted = useRef(true)
  const pollGeneration = useRef(0)
  const galleryGeneration = useRef(0)
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
    setError(''); setSelected(null); setCreating(false); setReference(null); setInstruction(''); setHandoff('')
    try {
      const value = await api.get<Run>(`${base}/runs/${id}`)
      if (!mounted.current || current !== generation.current) return
      setRun(value)
      const url = new URL(window.location.href); url.searchParams.set('template_run', id); window.history.replaceState(null, '', url)
    } catch (cause) { if (current === generation.current) setError((cause as Error).message) }
  }, [api])
  useEffect(() => { const id = new URLSearchParams(window.location.search).get('template_run'); if (id) void openRun(id) }, [openRun])
  useEffect(() => {
    if (!run || !activeStates.includes(run.status)) return
    const current = ++pollGeneration.current
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const value = await api.get<Run>(`${base}/runs/${run.run_id}`)
        if (current !== pollGeneration.current || !mounted.current) return
        setRun(value)
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
      setPending(null); setRun(value); setCreating(false); setSelected(null); setInstruction(''); setReference(null)
      const url = new URL(window.location.href); url.searchParams.set('template_run', value.run_id); window.history.replaceState(null, '', url)
      void refresh()
    } catch (cause) {
      if (mounted.current) {
        setError((cause as Error).message)
        if (cause instanceof ApiFailure && [400, 404, 409, 413, 422].includes(cause.details.status || 0)) setPending(null)
      }
    }
    finally { if (mounted.current) { setBusy(false); setReference(null) } }
  }
  const submit = async () => {
    setBusy(true); setError('')
    let referenceId: string | undefined
    try {
      if (reference) {
        const uploaded = await api.post<{ reference_id: string }>(`${base}/references`, { request_id: crypto.randomUUID(), image: await imageReferencePayload(reference) })
        referenceId = uploaded.reference_id
      }
      const body = { request_id: crypto.randomUUID(), instruction, ...(referenceId ? { reference_id: referenceId } : {}) }
      await mutate(run ? { path: `${base}/runs/${run.run_id}/resume`, body: { ...body, base_sha256: run.state_sha256 } }
        : { path: `${base}/runs`, body: { ...body, scope, ...(source ? { source } : {}) } })
    } catch (cause) {
      if (mounted.current) { setError((cause as Error).message); setBusy(false); setReference(null) }
      if (referenceId) void api.post(`${base}/references/${referenceId}/discard`, {}).catch(() => {})
    }
  }
  const inspect = async (item: Identity) => {
    const current = ++generation.current
    setError(''); setBusy(true); setRun(null); setCreating(false); setReference(null)
    try {
      const [value, history] = await Promise.all([api.get<Template>(`${versionPath(item)}?sha256=${item.template_sha256}`), api.get<{ items: Identity[] }>(`${base}/${item.surface}/${item.template_id}/versions`)])
      if (mounted.current && current === generation.current) { setSelected(value); setVersions(history.items) }
    } catch (cause) { if (current === generation.current) setError((cause as Error).message) }
    finally { if (current === generation.current) setBusy(false) }
  }
  const begin = (item?: Template) => {
    generation.current++; pollGeneration.current++
    setSource(item ? identity(item) : null); setScope(item?.surface || 'post'); setInstruction(''); setReference(null)
    setRun(null); setSelected(null); setCreating(true); setError(''); setHandoff('')
    const url = new URL(window.location.href); url.searchParams.delete('template_run'); window.history.replaceState(null, '', url)
  }
  const working = !!run && activeStates.includes(run.status)
  const canCorrect = !!run && !working && !['accepted', 'rejected'].includes(run.status)
  const drafts = runs.filter(item => !['accepted', 'rejected'].includes(item.status))
  const history = runs.filter(item => ['accepted', 'rejected'].includes(item.status))
  const statusLabel = (status: string) => ({
    queued: tr('Queued', 'У черзі'), analyzing: tr('Analyzing', 'Аналіз'), composing: tr('Composing', 'Компонування'),
    rendering: tr('Rendering', 'Рендеринг'), comparing: tr('Comparing', 'Порівняння'), failed: tr('Failed', 'Помилка'),
    interrupted: tr('Interrupted', 'Перервано'), paused: tr('Paused', 'Призупинено'),
    capability_gap: tr('Capability needed', 'Потрібне розширення'), proposed: tr('Ready for review', 'Готово до перевірки'),
    accepted: tr('Accepted', 'Прийнято'), rejected: tr('Rejected', 'Відхилено'),
  } as Record<string, string>)[status] || status
  const failureLabel = (failure?: Failure, fallback?: string | null) => failure ? ({
    timeout: tr('Comparison timed out. Continue to retry the saved preview.', 'Порівняння перевищило час. Продовжте, щоб повторити зі збереженим прев’ю.'),
    validation: tr('The comparison response was invalid. Continue to retry it.', 'Відповідь порівняння не пройшла перевірку. Продовжте, щоб повторити.'),
    cancelled: tr('The agent was stopped. Continue from the saved state.', 'Агента зупинено. Продовжте зі збереженого стану.'),
    provider: tr('The agent call failed. Continue from the saved state.', 'Виклик агента завершився помилкою. Продовжте зі збереженого стану.'),
  } as Record<string, string>)[failure.category] || fallback || '' : fallback || ''
  return <section className="templates-view">
    <header className="page-header"><div><h1>{tr('Templates', 'Шаблони')}</h1><p>{tr('Reusable Post and Landing designs', 'Багаторазові дизайни дописів і лендінгів')}</p></div><button onClick={() => begin()} disabled={busy || !!pending}>{tr('Create Template Agent', 'Агент створення шаблону')}</button></header>
    {error && <div role="alert" className="notice"><p>{error}</p>{pending ? <button disabled={busy} onClick={() => void mutate(pending)}>{tr('Retry same request', 'Повторити той самий запит')}</button> : <button onClick={() => { setError(''); if (run) void openRun(run.run_id); else void refresh() }}>{tr('Retry', 'Повторити')}</button>}</div>}
    {(creating || canCorrect) && <form className="template-form" onSubmit={event => { event.preventDefault(); void submit() }}>
      <h2>{run ? tr('Refine this template', 'Уточнити шаблон') : source ? tr('Edit as a new version', 'Редагувати як нову версію') : tr('Create Template Agent', 'Агент створення шаблону')}</h2>
      {!run && <label>{tr('Creation scope', 'Тип створення')}<select value={scope} disabled={!!source || busy || !!pending} onChange={event => setScope(event.target.value as typeof scope)}><option value="post">Post</option><option value="landing">Landing</option><option value="combined">Post + Landing</option></select></label>}
      {source && <p>{tr('Source', 'Джерело')}: {source.template_id} · v{source.template_version}</p>}
      <label>{tr('Design instruction', 'Інструкція дизайну')}<textarea value={instruction} maxLength={3000} rows={4} disabled={busy || !!pending} onChange={event => setInstruction(event.target.value)} placeholder={tr('Describe the layout, or upload a visual reference', 'Опишіть композицію або додайте референс')} /></label>
      <ImageReferenceInput value={reference} onChange={setReference} disabled={busy || !!pending} language={language} />
      <p>{tr('Reference analysis is saved, while raw pixels are temporary. Reattaching the same image after a restart is optional and enables direct image comparison.', 'Аналіз референсу зберігається, а сирі пікселі — тимчасові. Після перезапуску те саме зображення можна додати знову для прямого порівняння, але це необов’язково.')}</p>
      <button type="submit" disabled={busy || !!pending || (!run && !instruction.trim() && !reference)}>{busy ? tr('Submitting…', 'Надсилання…') : run ? tr('Resume / apply correction', 'Продовжити / уточнити') : tr('Start creation', 'Почати створення')}</button>
    </form>}
    {run && <section className="template-run" aria-live="polite"><h2>{tr('Creation run', 'Створення')} · {run.scope}</h2><p className="template-status">{run.status} · {run.phase} · {tr('comparisons', 'порівнянь')}: {run.iterations}</p><small className="template-id">{run.run_id}</small>
      {run.error && <p role="alert">{failureLabel(run.failure, run.error)}</p>}
      <div className="template-preview-grid">{Object.entries(run.previews).map(([key, preview]) => <figure key={key}><TemplateImage api={api} preview={preview} label={key} language={language} /><figcaption>{key}</figcaption></figure>)}</div>
      {run.comparison && <div><h3>{tr('Visual comparison', 'Візуальне порівняння')}</h3>{run.comparison.differences.length ? <ul>{run.comparison.differences.map((d, i) => <li key={i}>{d.surface} / {d.role}: {d.issue} ({d.severity})</li>)}</ul> : <p>{tr('No unresolved visual differences reported.', 'Невирішених візуальних розбіжностей немає.')}</p>}</div>}
      {run.capability_gap && <div className="notice"><h3>{tr('Reusable capability needed', 'Потрібна багаторазова можливість')}</h3><p>{run.capability_gap.evidence}</p><p>{run.capability_gap.proposed_abstraction}</p><p>{run.capability_gap.why_composition_insufficient}</p><button onClick={() => void api.get(`${base}/runs/${run.run_id}/capability-handoff`).then(value => setHandoff(JSON.stringify(value, null, 2))).catch(cause => setError(cause.message))}>{tr('Prepare development handoff', 'Підготувати завдання розробки')}</button>{handoff && <textarea aria-label="Development handoff" readOnly value={handoff} rows={10} />}</div>}
      {!working && !['accepted', 'rejected'].includes(run.status) && <div className="template-actions"><button disabled={busy || !!pending || run.status !== 'proposed'} onClick={() => void mutate({ path: `${base}/runs/${run.run_id}/decision`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256, decision: 'accept' } })}>{tr('Accept template version', 'Прийняти версію шаблону')}</button><button className="secondary" disabled={busy || !!pending} onClick={() => void mutate({ path: `${base}/runs/${run.run_id}/decision`, body: { request_id: crypto.randomUUID(), base_sha256: run.state_sha256, decision: 'reject' } })}>{tr('Reject proposal', 'Відхилити пропозицію')}</button></div>}
      {run.accepted_versions.map(item => <button key={item.surface} onClick={() => void inspect(item)}>{tr('Open', 'Відкрити')} {item.surface} · v{item.template_version}</button>)}
      <details><summary>{tr('Operation measurements', 'Вимірювання операції')}</summary><ul>{run.invocations.map((v, i) => <li key={i}>{v.phase}: {v.contract_bytes.total.toLocaleString()} B input · {v.response_bytes.toLocaleString()} B response · {v.attempt_count} attempt(s)</li>)}</ul></details>
    </section>}
    {selected && <section className="template-detail"><h2>{selected.name} · v{selected.template_version}</h2><p>{selected.description}</p><p>{selected.builtin ? tr('Built-in · edits create a derivative', 'Вбудований · редагування створює похідний шаблон') : tr('Immutable registered version', 'Незмінна зареєстрована версія')}</p><small className="template-id">{selected.template_id} · {selected.template_sha256}</small>
      {versions.length > 1 && <label>{tr('Version', 'Версія')}<select value={selected.template_version} onChange={event => { const item = versions.find(v => v.template_version === Number(event.target.value)); if (item) void inspect(item) }}>{versions.map(item => <option key={item.template_version} value={item.template_version}>v{item.template_version}</option>)}</select></label>}
      <div className="template-preview-grid">{Object.entries(selected.previews).map(([key, preview]) => <figure key={key}><TemplateImage api={api} preview={preview} label={`${selected.name} ${key}`} language={language} /><figcaption>{key}</figcaption></figure>)}</div>
      {selected.document && <details><summary>{tr('Structured components', 'Структуровані компоненти')}</summary><ul>{selected.document.components.map(c => <li key={c.id}>{c.id} · {c.type} · {c.role}</li>)}</ul></details>}
      {selected.post_reference && <p className="template-id">Post: {selected.post_reference.template_id} · v{selected.post_reference.template_version} · {selected.post_reference.template_sha256}</p>}
      <button disabled={busy || !!pending} onClick={() => begin(selected)}>{tr('Edit template', 'Редагувати шаблон')}</button>
    </section>}
    {drafts.length > 0 && <section className="template-drafts" aria-labelledby="template-drafts-title"><div className="template-drafts-heading"><div><h2 id="template-drafts-title">{tr('Drafts', 'Чернетки')}</h2><p>{tr('Reference analysis is saved. Raw reference pixels are temporary; reattaching the same image is optional and enables direct image comparison after a restart.', 'Аналіз референсу збережено. Сирі пікселі референсу тимчасові; повторне додавання того самого зображення необов’язкове, але дає пряме порівняння зображень після перезапуску.')}</p></div></div><div className="template-draft-grid">{drafts.map(item => { const previewEntry = Object.entries(item.previews).find(([key]) => key.endsWith(':desktop')) || Object.entries(item.previews)[0]; return <article className="template-draft-card" key={item.run_id}><TemplateImage api={api} preview={previewEntry?.[1]} label={`${item.scope} draft`} language={language} /><div className="template-draft-body"><div className="template-draft-meta"><span>{item.scope === 'combined' ? 'Post + Landing' : item.scope === 'post' ? 'Post' : 'Landing'}</span><strong data-status={item.status}>{statusLabel(item.status)}</strong></div><p>{tr('Comparisons', 'Порівнянь')}: {item.iterations}</p>{(item.failure || item.error) && <p className="template-draft-error">{failureLabel(item.failure, item.error)}</p>}<small>{item.run_id}</small><button disabled={busy || !!pending} onClick={() => void openRun(item.run_id)}>{item.status === 'proposed' ? tr('Open for review', 'Відкрити для перевірки') : activeStates.includes(item.status) ? tr('Open', 'Відкрити') : tr('Open / Continue', 'Відкрити / Продовжити')}</button></div></article> })}</div></section>}
    <div className="template-filter" role="group" aria-label={tr('Template surface', 'Тип шаблону')}>{(['all', 'post', 'landing'] as const).map(value => <button key={value} className="secondary" aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'all' ? tr('All templates', 'Усі шаблони') : value === 'post' ? 'Post' : 'Landing'}</button>)}</div>
    {items === null ? <p role="status">{tr('Loading templates…', 'Завантаження шаблонів…')}</p> : items.length === 0 ? <p>{tr('No templates for this surface yet.', 'Шаблонів цього типу ще немає.')}</p> : <div className="template-gallery">{items.map(item => <article key={`${item.surface}:${item.template_id}`} className="template-card"><TemplateImage api={api} preview={item.previews.desktop} label={`${item.name} preview`} language={language} /><div><h2>{item.name}</h2><p>{item.surface} · v{item.template_version} · {item.status}</p>{item.preview_status !== 'ready' && <button onClick={() => void refresh()}>{tr('Retry preview generation', 'Повторити створення прев’ю')}</button>}<button className="secondary" disabled={busy || !!pending} onClick={() => void inspect(item)}>{tr('Open template', 'Відкрити шаблон')}</button></div></article>)}</div>}
    {history.length > 0 && <details className="template-history"><summary>{tr('Accepted and rejected runs', 'Прийняті та відхилені створення')}</summary>{history.map(item => <button key={item.run_id} disabled={busy || !!pending} onClick={() => void openRun(item.run_id)}><span>{item.scope} · {statusLabel(item.status)}</span><small>{item.run_id}</small></button>)}</details>}
  </section>
}
