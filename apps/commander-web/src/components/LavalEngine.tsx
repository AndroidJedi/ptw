import { Check, CirclePause, Download, Eye, FlaskConical, Play, Plus, RefreshCcw, RotateCcw, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { I18n, LavalEvidenceMode, LavalProviderReadiness, LavalRun, LavalStage, LavalStatus } from '../types'

const DEFAULT_COUNTRIES = 'US:en, GB:en, DE:de:en, NO:no:en, DK:da:en'

function countries(value: string) {
  return value.split(',').map((part) => {
    const [code, language, secondary_language] = part.trim().split(':')
    if (!/^[A-Za-z]{2}$/.test(code || '') || !/^[a-z]{2,3}$/.test(language || '')) throw new Error('Країни: використовуйте формат US:en, DE:de:en')
    return { code: code.toUpperCase(), language, ...(secondary_language ? { secondary_language } : {}) }
  })
}

function short(value?: string) { return value ? `${value.slice(0, 8)}…${value.slice(-4)}` : '—' }
function humanStage(value: string) { return value.replaceAll('_', ' ') }
function isI18n(value: unknown): value is I18n { return Boolean(value && typeof value === 'object' && 'en' in value && 'uk' in value) }
function evidenceLabel(mode?: LavalEvidenceMode) {
  if (mode === 'live_complete') return 'LIVE COMPLETE'
  if (mode === 'live_search_pending_trends') return 'LIVE SEARCH — WAITING FOR TRENDS'
  return 'DEMO — NO LIVE RESEARCH'
}

export function LavalEngine({ api, language }: { api: ApiClient; language: Language }) {
  const [runs, setRuns] = useState<LavalRun[] | null>(null)
  const [providers, setProviders] = useState<LavalProviderReadiness | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [status, setStatus] = useState<LavalStatus | null>(null)
  const [stageName, setStageName] = useState('')
  const [stageOutput, setStageOutput] = useState<unknown>(null)
  const [countryFilter, setCountryFilter] = useState('')
  const [view, setView] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [idea, setIdea] = useState('')
  const [countryText, setCountryText] = useState(DEFAULT_COUNTRIES)
  const [automatic, setAutomatic] = useState(false)
  const [requestedMode, setRequestedMode] = useState<'demo' | 'live'>('demo')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [stageLoading, setStageLoading] = useState(false)
  const [stageLoadError, setStageLoadError] = useState('')
  const [exportPreview, setExportPreview] = useState<{ filename: string; text: string } | null>(null)
  const inspectorRef = useRef<HTMLElement>(null)

  const loadRuns = async () => {
    try {
      const result = await api.get<{ items: LavalRun[] }>('/api/v1/laval/runs?limit=30')
      setRuns(result.items)
      if (!selected && result.items[0]) setSelected(result.items[0].id)
    } catch (cause) { setError((cause as Error).message) }
  }
  const loadProviders = async () => {
    try {
      const result = await api.get<LavalProviderReadiness>('/api/v1/laval/providers')
      setProviders(result)
      if (!result.demo_available && result.search_live_ready) setRequestedMode('live')
    } catch (cause) { setError((cause as Error).message) }
  }
  const loadStatus = async (runId = selected) => {
    if (!runId) return
    try { setStatus(await api.get<LavalStatus>(`/api/v1/laval/runs/${runId}`)) }
    catch (cause) { setError((cause as Error).message) }
  }

  useEffect(() => { void loadRuns(); void loadProviders() }, [api])
  useEffect(() => {
    setStageOutput(null); setStageName(''); setCountryFilter(''); setView('')
    void loadStatus(selected)
  }, [api, selected])
  useEffect(() => {
    if (!selected || !status || !['pending', 'running'].includes(status.run.status)) return
    const timer = window.setInterval(() => { void loadStatus(selected); void loadRuns() }, 2000)
    return () => window.clearInterval(timer)
  }, [api, selected, status?.run.status])

  const act = async (action: string, body: Record<string, unknown> = {}) => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/laval/runs/${selected}/${action}`, body)
      await loadStatus(selected); await loadRuns()
      setNotice('Дію виконано.')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const create = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.post<{ run_id: string }>('/api/v1/laval/runs', {
        text: idea,
        mode: requestedMode,
        config: { countries: countries(countryText), approval_mode: automatic ? 'automatic' : 'manual' },
      })
      setIdea(''); setShowCreate(false); setSelected(result.run_id)
      await loadRuns()
      setNotice(requestedMode === 'demo' ? 'Демо-запуск створено. Його дані не є живим дослідженням.' : 'Живий запуск створено.')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const inspect = async (stage: LavalStage, selectedView = view, country = countryFilter) => {
    if (!selected) return
    setStageName(stage.stage); setView(selectedView); setCountryFilter(country); setError(''); setStageLoadError(''); setStageLoading(true); setStageOutput(null)
    const params = new URLSearchParams({ stage: stage.stage })
    if (selectedView) params.set('view', selectedView)
    if (country) params.set('country', country)
    window.setTimeout(() => inspectorRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }), 0)
    try { setStageOutput(await api.get(`/api/v1/laval/runs/${selected}/show?${params}`)) }
    catch (cause) { const message = (cause as Error).message; setStageLoadError(message); setError(message) }
    finally { setStageLoading(false) }
  }
  const download = async (format: 'json' | 'md') => {
    if (!selected) return
    setBusy(true); setError(''); setNotice(`Підготовка ${format.toUpperCase()} експорту…`)
    try {
      const params = new URLSearchParams({ format })
      if (stageName) params.set('stage', stageName)
      const blob = await api.blob(`/api/v1/laval/runs/${selected}/export?${params}`)
      const filename = `laval-${selected}-${stageName || 'all'}.${format}`
      const file = typeof File === 'function' ? new File([blob], filename, { type: blob.type || (format === 'md' ? 'text/markdown' : 'application/json') }) : null
      const shareNavigator = navigator as Navigator & { canShare?: (data: ShareData) => boolean }
      if (file && shareNavigator.canShare?.({ files: [file] }) && navigator.share) {
        try {
          await navigator.share({ files: [file], title: filename })
          setNotice('Експорт передано до меню Поділитися / Зберегти.')
          return
        } catch (cause) {
          if ((cause as DOMException).name === 'AbortError') { setNotice('Експорт скасовано.'); return }
        }
      }
      const href = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = href; anchor.download = filename; anchor.rel = 'noopener'; document.body.append(anchor); anchor.click(); anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(href), 60_000)
      setExportPreview({ filename, text: await blob.text() })
      setNotice('Файл підготовлено. Якщо Safari не зберіг його, використайте перегляд нижче.')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const copyExport = async () => {
    if (!exportPreview) return
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(exportPreview.text)
      else {
        const area = document.createElement('textarea')
        area.value = exportPreview.text; area.style.position = 'fixed'; area.style.opacity = '0'; document.body.append(area); area.select()
        if (!document.execCommand('copy')) throw new Error('Browser copy command failed')
        area.remove()
      }
      setNotice('Експорт скопійовано.')
    } catch (cause) { setError(`Не вдалося скопіювати експорт: ${(cause as Error).message}`) }
  }

  const current = status?.stages.find((item) => item.stage === status.run.current_stage)
  const approval = Boolean(status?.run.status === 'paused' && current && ['completed', 'partial'].includes(current.status) && status.run.approval_gates.includes(current.stage))
  const configuredCountries = useMemo(() => ((status?.run.config.countries as Array<{ code: string }> | undefined) || []).map((item) => item.code), [status])

  return <section className="laval-engine">
    <div className="laval-toolbar">
      <div><small>IDEA LAVAL ENGINE</small><h2>Evidence → opportunity → trend → ideas</h2></div>
      <button className="primary" disabled={!providers} onClick={() => setShowCreate(true)}><Plus />Нова Laval-ідея</button>
    </div>
    {error && <div className="laval-error" role="alert"><span>{error}</span><button onClick={() => { setError(''); void loadProviders(); void loadRuns(); void loadStatus() }} aria-label="Повторити"><RefreshCcw /> Повторити</button><button onClick={() => setError('')} aria-label="Закрити"><X /></button></div>}
    {notice && <div className="laval-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Закрити"><X /></button></div>}
    {showCreate && <div className="laval-create">
      <div><strong>Нова ідея власника</strong><button onClick={() => setShowCreate(false)} aria-label="Закрити"><X /></button></div>
      <label>Повний текст ідеї<textarea rows={9} value={idea} onChange={(event) => setIdea(event.target.value)} placeholder="Проблема, користувач, механізм і те, що не можна втратити…" /></label>
      <label>Країна:мова[:друга мова]<input value={countryText} onChange={(event) => setCountryText(event.target.value)} /></label>
      <fieldset className="laval-mode"><legend>Режим доказів</legend>
        <label><input type="radio" name="evidence-mode" value="demo" checked={requestedMode === 'demo'} disabled={!providers?.demo_available} onChange={() => setRequestedMode('demo')} /><span><strong>Демо</strong> — deterministic fixture, не ринкове дослідження</span></label>
        <label><input type="radio" name="evidence-mode" value="live" checked={requestedMode === 'live'} disabled={!providers?.search_live_ready} onChange={() => setRequestedMode('live')} /><span><strong>Живе дослідження</strong> — DataForSEO, максимум $0.05</span></label>
        {!providers?.search_live_ready && <p>DataForSEO ще не налаштовано. Живий запуск заблоковано.</p>}
        {providers?.search_live_ready && !providers.trends_live_ready && <p>Запуск зупиниться після Opportunity Matrix до підключення Google Trends.</p>}
      </fieldset>
      <label className="check-row"><input type="checkbox" checked={automatic} onChange={(event) => setAutomatic(event.target.checked)} /><span>Автоматично проходити контрольні точки</span></label>
      <button className="primary large" disabled={busy || !idea.trim() || (requestedMode === 'demo' ? !providers?.demo_available : !providers?.search_live_ready)} onClick={create}><FlaskConical />{busy ? 'Створення…' : requestedMode === 'demo' ? 'Створити чітко позначене демо' : 'Створити живий запуск'}</button>
    </div>}
    <div className="laval-layout">
      <aside className="laval-runs" aria-label="Laval-запуски">
        {runs === null && <p className="muted">Завантаження…</p>}
        {runs?.length === 0 && <p className="muted">Ще немає Laval-запусків.</p>}
        {runs?.map((run) => <button key={run.id} className={selected === run.id ? 'selected' : ''} onClick={() => setSelected(run.id)}>
          <span><StatusDot status={run.status} />{run.status}</span><em className={`evidence-badge ${run.evidence_mode || 'demo_fixture'}`}>{evidenceLabel(run.evidence_mode)}</em><strong>{run.owner_preview || 'Owner idea'}</strong><small>{short(run.id)} · {run.completed_stages ?? 0}/16</small>
        </button>)}
      </aside>
      <div className="laval-workspace">
        {!status && selected && <p className="muted">Завантаження запуску…</p>}
        {!selected && <div className="state"><FlaskConical /><h2>Створіть перший запуск</h2><p>Кожний етап буде видимим, відновлюваним і пов’язаним із доказами.</p></div>}
        {status && <>
          <header className="laval-run-head">
            <div><small>RUN {short(status.run.id)} · OWNER {short(status.run.owner_idea_id)}</small><em className={`evidence-badge ${status.run.evidence_mode}`}>{evidenceLabel(status.run.evidence_mode)}</em><h3>{status.run.current_stage ? humanStage(status.run.current_stage) : 'CREATED'}</h3><p><StatusDot status={status.run.status} />{status.run.status} · {status.stages.filter((item) => ['completed', 'partial'].includes(item.status)).length}/16</p><p className="laval-cost">projected ${(status.cost.provider_projected_usd ?? 0).toFixed(4)} · reserved ${(status.cost.provider_reserved_usd ?? 0).toFixed(4)} · actual ${(status.cost.provider_actual_usd ?? status.cost.total_usd).toFixed(4)} · max ${(status.cost.max_spend_usd ?? .05).toFixed(2)}</p>{status.run.awaiting_reason && <p className="laval-waiting">Google Trends access required before synthesis and shortlist.</p>}</div>
            <div className="laval-actions">
              {['pending', 'failed'].includes(status.run.status) && <button className="primary" disabled={busy} onClick={() => act(status.run.status === 'failed' ? 'resume' : 'run')}><Play />{status.run.status === 'failed' ? 'Повторити' : 'Запустити'}</button>}
              {status.run.status === 'running' && <button className="secondary" disabled={busy} onClick={() => act('pause')}><CirclePause />Пауза</button>}
              {status.run.status === 'paused' && !approval && !status.run.awaiting_reason && <button className="primary" disabled={busy} onClick={() => act('resume')}><Play />Продовжити</button>}
              {status.run.awaiting_reason && <button className="secondary" disabled><CirclePause />Очікує Google Trends</button>}
              {approval && current && <button className="primary" disabled={busy} onClick={() => act('approve', { stage: current.stage })}><Check />Схвалити й продовжити</button>}
              <button className="secondary" disabled={busy} onClick={() => download('json')}><Download />JSON</button>
              <button className="secondary" disabled={busy} onClick={() => download('md')}>MD</button>
            </div>
          </header>
          {status.run.error_text && <p className="laval-failure">{status.run.error_text}</p>}
          <div className="laval-stages">
            {status.stages.map((stage) => <button key={stage.stage} className={`${stage.status} ${stageName === stage.stage ? 'selected' : ''}`} onClick={() => inspect(stage)}>
              <span>S{String(stage.ordinal).padStart(2, '0')}</span><strong>{humanStage(stage.stage)}</strong><small>{stage.status} · #{stage.attempt}{stage.provider ? ` · ${stage.provider}` : ''}</small>
            </button>)}
          </div>
          {stageName && <section className="laval-inspector" ref={inspectorRef} tabIndex={-1}>
            <div className="laval-inspector-head"><div><small>АРТЕФАКТ ЕТАПУ</small><h3>{humanStage(stageName)}</h3></div><div>
              {stageName === 'TREND_GATE' && <select aria-label="Trend view" value={view} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, value, countryFilter) }}><option value="">Усе</option><option value="scores">Trend Scores</option><option value="discoveries">Trend Discoveries</option></select>}
              {['SERP_DISCOVERY', 'COMPETITOR_SELECTION'].includes(stageName) && <select aria-label="Country filter" value={countryFilter} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, view, value) }}><option value="">Усі країни</option>{configuredCountries.map((code) => <option key={code}>{code}</option>)}</select>}
              <button className="secondary" disabled={busy} onClick={() => act('rerun', { stage: stageName, ...(stageName === 'SERP_DISCOVERY' && countryFilter ? { country: countryFilter } : {}) })}><RotateCcw />{busy ? 'Виконується…' : 'Перезапустити'}</button>
            </div></div>
            <StageArtifact value={stageOutput} language={language} loading={stageLoading} error={stageLoadError} />
            <OverridePanel apiAction={(body) => act('override', body)} stage={stageName} countries={configuredCountries} />
          </section>}
        </>}
      </div>
    </div>
    {exportPreview && <div className="laval-export-preview" role="dialog" aria-modal="true" aria-label="Перегляд експорту"><div><strong>{exportPreview.filename}</strong><button onClick={() => setExportPreview(null)} aria-label="Закрити"><X /></button></div><button className="secondary" onClick={() => void copyExport()}>Копіювати</button><pre>{exportPreview.text}</pre></div>}
  </section>
}

function StatusDot({ status }: { status: string }) { return <i className={`status-dot ${status}`} aria-hidden="true" /> }

function StageArtifact({ value, language, loading, error }: { value: unknown; language: Language; loading: boolean; error: string }) {
  if (loading) return <p className="muted" role="status">Завантаження артефакту…</p>
  if (error) return <p className="laval-failure">Не вдалося завантажити артефакт: {error}</p>
  const output = value && typeof value === 'object' && 'output' in value ? (value as { output: unknown }).output : value
  if (output === null || output === undefined) return <p className="muted">Артефакт ще не створено для незавершеного етапу.</p>
  if (output && typeof output === 'object' && 'shortlist' in output) {
    const items = (output as { shortlist: Array<Record<string, unknown>> }).shortlist || []
    return <div className="laval-shortlist">{items.map((item) => {
      const title = item.title as I18n | undefined; const one = item.one_liner as I18n | undefined
      return <article key={String(item.idea_id)}><span>#{String(item.rank)}</span><div><small>{short(String(item.idea_id))} · {String(item.operator)}{item.finalist ? ' · FINALIST' : ''}</small><h4>{title && isI18n(title) ? String(local(title, language)) : String(item.idea_id)}</h4><p>{one && isI18n(one) ? String(local(one, language)) : ''}</p></div><strong>{(Number(item.final_score) * 100).toFixed(1)}</strong></article>
    })}</div>
  }
  return <pre className="laval-json">{JSON.stringify(output, null, 2)}</pre>
}

function OverridePanel({ apiAction, stage, countries }: { apiAction: (body: Record<string, unknown>) => Promise<void>; stage: string; countries: string[] }) {
  const suggested = stage === 'COMPETITOR_SELECTION' ? 'competitor' : stage === 'OPPORTUNITY_MATRIX' ? 'opportunity' : stage === 'TREND_GATE' ? 'trend' : ''
  const [type, setType] = useState(suggested || 'opportunity')
  const [action, setAction] = useState(suggested === 'competitor' ? 'reject' : 'disable')
  const [target, setTarget] = useState('')
  const [country, setCountry] = useState(countries[0] || 'US')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  useEffect(() => { if (suggested) { setType(suggested); setAction(suggested === 'competitor' ? 'reject' : 'disable') } }, [suggested])
  return <details className="laval-override"><summary>Ручне виправлення · audit log</summary><div>
    <label>Тип<select value={type} onChange={(event) => { const value = event.target.value; setType(value); setAction(value === 'competitor' ? 'reject' : 'disable') }}><option value="competitor">Competitor</option><option value="opportunity">Opportunity</option><option value="trend">Trend</option></select></label>
    {type === 'competitor' && <label>Дія<select value={action} onChange={(event) => setAction(event.target.value)}><option value="reject">Reject</option><option value="add">Add URL</option></select></label>}
    {type === 'competitor' && action === 'add' && <label>Країна<select value={country} onChange={(event) => setCountry(event.target.value)}>{countries.map((code) => <option key={code}>{code}</option>)}</select></label>}
    <label>{action === 'add' ? 'URL' : 'UUID'}<input value={target} onChange={(event) => setTarget(event.target.value)} /></label>
    <label>Причина<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    <button className="secondary" disabled={!target || submitting} onClick={async () => { setSubmitting(true); try { await apiAction({ type, action, target_id: target, reason, ...(action === 'add' ? { payload: { url: target, country } } : {}) }) } finally { setSubmitting(false) } }}><Eye />{submitting ? 'Застосування…' : 'Застосувати й позначити downstream stale'}</button>
  </div></details>
}
