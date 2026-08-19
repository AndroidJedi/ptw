import { Check, CirclePause, Download, FlaskConical, Play, Plus, RefreshCcw, RotateCcw, X } from 'lucide-react'
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
  if (mode === 'live_market_signals') return 'LIVE · MARKET SIGNALS'
  if (mode === 'live_search_pending_trends') return 'LIVE SEARCH — WAITING FOR TRENDS'
  return 'DEMO — NO LIVE RESEARCH'
}

type OverrideTarget = {
  id: string
  kind: 'competitor' | 'opportunity' | 'trend_score' | 'trend_discovery'
  name?: string
  domain?: string
  statement?: string
  term?: string
  country?: string
  time_window?: string
  discovered_term?: string
  discovery_type?: string
  growth_label?: string
}

const CORRECTABLE_STAGES = ['COMPETITOR_SELECTION', 'OPPORTUNITY_MATRIX', 'TREND_GATE']

function correctionTargets(value: unknown): OverrideTarget[] {
  if (!value || typeof value !== 'object' || !('override_targets' in value)) return []
  const targets = (value as { override_targets?: unknown }).override_targets
  return Array.isArray(targets) ? targets.filter((item): item is OverrideTarget => Boolean(item && typeof item === 'object' && 'id' in item && 'kind' in item)) : []
}

function correctionTargetLabel(target: OverrideTarget) {
  if (target.kind === 'competitor') return `${target.name || target.domain || 'Competitor'}${target.domain && target.name !== target.domain ? ` — ${target.domain}` : ''}`
  if (target.kind === 'opportunity') return target.statement || 'Можливість'
  if (target.kind === 'trend_discovery') return `Відкриття · ${target.discovered_term || target.term || '—'} · ${target.country || '—'} / ${target.time_window || '—'}`
  return `Оцінка тренду · ${target.term || '—'} · ${target.country || '—'} / ${target.time_window || '—'}`
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
  const [busyAction, setBusyAction] = useState('')
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
    if (!selected) return false
    setBusy(true); setBusyAction(action); setError(''); setNotice(action.includes('resume') ? 'Відновлення збереженої роботи…' : '')
    try {
      const result = await api.post<{ started?: boolean; queued?: number }>(`/api/v1/laval/runs/${selected}/${action}`, body)
      await loadStatus(selected); await loadRuns()
      if (action.includes('resume')) setNotice(result.started === false ? 'Запуск уже виконується.' : 'Відновлення запущено: збережені remote task IDs повторно не надсилаються і повторно не оплачуються.')
      else setNotice('Дію виконано.')
      return true
    } catch (cause) { setError((cause as Error).message); return false }
    finally { setBusy(false); setBusyAction('') }
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
      <div><small>IDEA LAVAL ENGINE</small><h2>Evidence → opportunity → market signals → ideas</h2></div>
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
        <label><input type="radio" name="evidence-mode" value="live" checked={requestedMode === 'live'} disabled={!providers?.search_live_ready} onChange={() => setRequestedMode('live')} /><span><strong>Живе дослідження</strong> — DataForSEO, максимум ${(providers?.max_spend_usd ?? .05).toFixed(2)}</span></label>
        {!providers?.search_live_ready && <p>DataForSEO ще не налаштовано. Живий запуск заблоковано.</p>}
        {providers?.search_live_ready && !providers.trends_live_ready && <p>Google Trends не підключено — це необов’язкове джерело і запуск продовжиться без нього.</p>}
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
            <div><small>RUN {short(status.run.id)} · OWNER {short(status.run.owner_idea_id)}</small><em className={`evidence-badge ${status.run.evidence_mode}`}>{evidenceLabel(status.run.evidence_mode)}</em><h3>{status.run.current_stage ? humanStage(status.run.current_stage) : 'CREATED'}</h3><p><StatusDot status={status.run.status} />{status.run.status} · {status.stages.filter((item) => ['completed', 'partial'].includes(item.status)).length}/16</p><p className="laval-cost">projected ${(status.cost.provider_projected_usd ?? 0).toFixed(4)} · reserved ${(status.cost.provider_reserved_usd ?? 0).toFixed(4)} · actual ${(status.cost.provider_actual_usd ?? status.cost.total_usd).toFixed(4)} · max ${(status.cost.max_spend_usd ?? .05).toFixed(2)}</p>{status.run.awaiting_reason && <p className="laval-waiting">{status.resume_with_market_signals_available ? 'Цей legacy-run можна продовжити через Market Signals без Google Trends.' : 'Запуск очікує дії провайдера.'}</p>}</div>
            <div className="laval-actions">
              {status.run.status === 'pending' && <button className="primary" disabled={busy} onClick={() => act('run')}><Play />{busyAction === 'run' ? 'Запуск…' : 'Запустити'}</button>}
              {status.run.status === 'running' && <button className="secondary" disabled={busy} onClick={() => act('pause')}><CirclePause />Пауза</button>}
              {status.run.status === 'paused' && !approval && !status.run.awaiting_reason && !status.resume_with_market_signals_available && <button className="primary" disabled={busy} onClick={() => act('resume')}><Play />Продовжити</button>}
              {status.resume_with_market_signals_available && <button className="primary" disabled={busy} onClick={() => act('resume-market-signals')}><Play />{busyAction === 'resume-market-signals' ? 'Відновлення…' : 'Resume with Market Signals'}</button>}
              {status.run.awaiting_reason && !status.resume_with_market_signals_available && <button className="secondary" disabled><CirclePause />Очікує провайдера</button>}
              {approval && current && <button className="primary" disabled={busy} onClick={() => act('approve', { stage: current.stage })}><Check />Схвалити й продовжити</button>}
              <button className="secondary" disabled={busy} onClick={() => download('json')}><Download />JSON</button>
              <button className="secondary" disabled={busy} onClick={() => download('md')}>MD</button>
            </div>
          </header>
          {status.run.status === 'failed' && status.recovery && <section className="laval-recovery" role="alert">
            <small>ЗВІТ ПРО ПОМИЛКУ ТА ВІДНОВЛЕННЯ</small>
            <h4>{humanStage(status.recovery.stage || status.run.current_stage || 'UNKNOWN')} · спроба #{status.recovery.attempt}</h4>
            <p><strong>{status.recovery.failure?.type || 'StageError'}:</strong> {status.recovery.failure?.message || status.run.error_text || 'Невідома помилка'}</p>
            {status.recovery.failed_at && <p>Час помилки: {new Date(status.recovery.failed_at).toLocaleString()}</p>}
            <dl>
              <div><dt>Provider tasks</dt><dd>{status.recovery.provider_tasks.total}</dd></div>
              <div><dt>Завершено</dt><dd>{status.recovery.provider_tasks.completed}</dd></div>
              <div><dt>Ще в черзі</dt><dd>{status.recovery.provider_tasks.submitted}</dd></div>
              <div><dt>Remote IDs збережено</dt><dd>{status.recovery.provider_tasks.persisted_remote_ids}</dd></div>
              <div><dt>Вартість записано</dt><dd>{status.recovery.provider_tasks.cost_recorded} · ${status.recovery.provider_tasks.actual_cost_usd.toFixed(4)}</dd></div>
            </dl>
            <p className="laval-recovery-safe">Відновлення використовує вже збережені remote task IDs. Submitted-задачі не публікуються і не оплачуються повторно.</p>
            {!status.resume_with_market_signals_available && <button className="primary" disabled={busy} onClick={() => act('resume')}><Play />{busyAction === 'resume' ? 'Відновлення…' : 'Відновити збережену роботу'}</button>}
          </section>}
          {status.run.status === 'failed' && !status.recovery && status.run.error_text && <p className="laval-failure">{status.run.error_text}</p>}
          {status.recovery?.history && status.recovery.history.length > 0 && <details className="laval-recovery-history">
            <summary>Історія помилок і відновлень ({status.recovery.history.length})</summary>
            {status.recovery.failure && <p>Останній збій: {humanStage(status.recovery.stage || 'UNKNOWN')} · {status.recovery.failure.type || 'StageError'} · provider tasks {status.recovery.provider_tasks.completed}/{status.recovery.provider_tasks.total} · ${status.recovery.provider_tasks.actual_cost_usd.toFixed(4)}</p>}
            <ol>{status.recovery.history.map((item, index) => <li key={`${item.created_at}-${index}`}><strong>{humanStage(item.action)}</strong> · {item.stage ? humanStage(item.stage) : 'RUN'} · {item.outcome}<small>{new Date(item.created_at).toLocaleString()} · {item.actor}</small></li>)}</ol>
          </details>}
          <div className="laval-stages">
            {status.stages.map((stage) => <button key={stage.stage} className={`${stage.status} ${stageName === stage.stage ? 'selected' : ''}`} onClick={() => inspect(stage)}>
              <span>S{String(stage.ordinal).padStart(2, '0')}</span><strong>{humanStage(stage.stage)}</strong><small>{stage.status} · #{stage.attempt}{stage.provider ? ` · ${stage.provider}` : ''}</small>
            </button>)}
          </div>
          {stageName && <section className="laval-inspector" ref={inspectorRef} tabIndex={-1}>
            <div className="laval-inspector-head"><div><small>АРТЕФАКТ ЕТАПУ</small><h3>{humanStage(stageName)}</h3></div><div>
              {stageName === 'TREND_GATE' && <select aria-label="Trend view" value={view} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, value, countryFilter) }}><option value="">Усе</option><option value="scores">Trend Scores</option><option value="discoveries">Trend Discoveries</option></select>}
              {stageName === 'MARKET_SIGNAL_GATE' && <select aria-label="Market signal view" value={view} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, value, countryFilter) }}><option value="">Усе</option><option value="scores">MarketSignalScore</option></select>}
              {['SERP_DISCOVERY', 'COMPETITOR_SELECTION'].includes(stageName) && <select aria-label="Country filter" value={countryFilter} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, view, value) }}><option value="">Усі країни</option>{configuredCountries.map((code) => <option key={code}>{code}</option>)}</select>}
              <button className="secondary" disabled={busy} onClick={() => act('rerun', { stage: stageName, ...(stageName === 'SERP_DISCOVERY' && countryFilter ? { country: countryFilter } : {}) })}><RotateCcw />{busy ? 'Виконується…' : 'Перезапустити'}</button>
            </div></div>
            <StageArtifact value={stageOutput} language={language} loading={stageLoading} error={stageLoadError} />
            {CORRECTABLE_STAGES.includes(stageName) && !stageLoading && !stageLoadError && Boolean(stageOutput) && <OverridePanel
              apiAction={async (body) => {
                const applied = await act('override', body)
                const stage = status.stages.find((item) => item.stage === stageName)
                if (applied && stage) await inspect(stage, view, countryFilter)
                return applied
              }}
              stage={stageName}
              countries={configuredCountries}
              targets={correctionTargets(stageOutput)}
            />}
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
  if (Array.isArray(output) && output.some((item) => item && typeof item === 'object' && 'normalization_version' in item)) return <MarketSignalScores scores={output as Array<Record<string, unknown>>} />
  if (output && typeof output === 'object' && 'scores' in output && Array.isArray((output as { scores: unknown[] }).scores) && (output as { scores: Array<Record<string, unknown>> }).scores.some((item) => item.normalization_version)) return <MarketSignalScores scores={(output as { scores: Array<Record<string, unknown>> }).scores} />
  if (output && typeof output === 'object' && 'shortlist' in output) {
    const items = (output as { shortlist: Array<Record<string, unknown>> }).shortlist || []
    return <div className="laval-shortlist">{items.map((item) => {
      const title = item.title as I18n | undefined; const one = item.one_liner as I18n | undefined
      return <article key={String(item.idea_id)}><span>#{String(item.rank)}</span><div><small>{short(String(item.idea_id))} · {String(item.operator)}{item.finalist ? ' · FINALIST' : ''}</small><h4>{title && isI18n(title) ? String(local(title, language)) : String(item.idea_id)}</h4><p>{one && isI18n(one) ? String(local(one, language)) : ''}</p></div><strong>{(Number(item.final_score) * 100).toFixed(1)}</strong></article>
    })}</div>
  }
  return <pre className="laval-json">{JSON.stringify(output, null, 2)}</pre>
}

function MarketSignalScores({ scores }: { scores: Array<Record<string, unknown>> }) {
  return <div className="market-signal-scores">{scores.map((score) => {
    const components = (score.components || {}) as Record<string, number>
    const raw = (score.raw_counts || {}) as Record<string, number>
    const status = (score.data_status || {}) as { overall?: string; components?: Record<string, string> }
    const evidence = (score.evidence_ids || []) as string[]
    return <article key={String(score.id)}>
      <header><div><small>{String(score.normalization_version)} · {status.overall === 'no_data' ? 'ДАНИХ НЕМАЄ' : 'ДАНІ НАЯВНІ'}</small><h4>MarketSignalScore</h4></div><strong>{(Number(score.aggregate_score || 0) * 100).toFixed(1)}</strong></header>
      <p><code>{String(score.formula)}</code></p>
      <dl>{Object.entries(components).map(([name, value]) => <div key={name}><dt>{humanStage(name)}</dt><dd>{(Number(value) * 100).toFixed(1)}% · {status.components?.[name] === 'no_data' ? 'даних немає' : 'виміряно'}</dd></div>)}</dl>
      <details><summary>Сирі лічильники</summary><pre>{JSON.stringify(raw, null, 2)}</pre></details>
      <details><summary>Evidence IDs ({evidence.length})</summary><ul>{evidence.map((id) => <li key={id}><code>{id}</code></li>)}</ul></details>
    </article>
  })}</div>
}

function OverridePanel({ apiAction, stage, countries, targets }: { apiAction: (body: Record<string, unknown>) => Promise<boolean>; stage: string; countries: string[]; targets: OverrideTarget[] }) {
  const type = stage === 'COMPETITOR_SELECTION' ? 'competitor' : stage === 'OPPORTUNITY_MATRIX' ? 'opportunity' : 'trend'
  const [action, setAction] = useState(type === 'competitor' ? 'reject' : 'disable')
  const [target, setTarget] = useState('')
  const [country, setCountry] = useState(countries[0] || 'US')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const invalidatedFrom = type === 'competitor' ? 'збору доказів про конкурентів' : type === 'opportunity' ? 'планування тренд-запитів' : 'пакета синтезу'
  const title = type === 'competitor' ? 'Скоригувати список конкурентів' : type === 'opportunity' ? 'Вимкнути можливість' : 'Вимкнути тренд-сигнал'
  useEffect(() => { setAction(type === 'competitor' ? 'reject' : 'disable'); setTarget(''); setReason('') }, [stage, type])
  return <details className="laval-override"><summary>{title}</summary><div>
    <p>Оберіть зрозумілий елемент — його внутрішній UUID буде підставлено автоматично. Причина та автор потраплять у журнал аудиту; етапи, починаючи з {invalidatedFrom}, будуть позначені для перебудови.</p>
    {type === 'competitor' && <label>Що змінити<select aria-label="Що змінити" value={action} onChange={(event) => { setAction(event.target.value); setTarget('') }}><option value="reject">Відхилити знайденого конкурента</option><option value="add">Додати конкурента за URL</option></select></label>}
    {action === 'add' ? <>
      <label>URL конкурента<input type="url" inputMode="url" value={target} onChange={(event) => setTarget(event.target.value)} placeholder="https://example.com" /></label>
      <label>Країна<select value={country} onChange={(event) => setCountry(event.target.value)}>{countries.map((code) => <option key={code}>{code}</option>)}</select></label>
    </> : <label>{type === 'competitor' ? 'Конкурент' : type === 'opportunity' ? 'Можливість' : 'Тренд-сигнал або відкриття'}<select value={target} onChange={(event) => setTarget(event.target.value)}>
      <option value="">Оберіть зі списку…</option>
      {targets.map((item) => <option key={item.id} value={item.id}>{correctionTargetLabel(item)}</option>)}
    </select>{targets.length === 0 && <span className="muted">Немає активних елементів для корекції.</span>}</label>}
    <label>Причина<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Чому цей елемент треба змінити?" /></label>
    <button className="secondary" disabled={!target.trim() || !reason.trim() || submitting} onClick={async () => {
      setSubmitting(true)
      try {
        const applied = await apiAction({ type, action, target_id: target.trim(), reason: reason.trim(), ...(action === 'add' ? { payload: { url: target.trim(), country } } : {}) })
        if (applied) { setTarget(''); setReason('') }
      } finally { setSubmitting(false) }
    }}><Check />{submitting ? 'Застосування…' : 'Застосувати корекцію'}</button>
  </div></details>
}
