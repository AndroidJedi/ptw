import { Check, CirclePause, Download, FlaskConical, Play, Plus, RefreshCcw, RotateCcw, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { I18n, LavalEvidenceMode, LavalProviderReadiness, LavalQualityCount, LavalRun, LavalRunQuality, LavalStage, LavalStatus } from '../types'

const DEFAULT_COUNTRIES = 'US:en, GB:en, DE:de:en, NO:no:en, DK:da:en'

function countries(value: string) {
  return value.split(',').map((part) => {
    const [code, language, secondary_language] = part.trim().split(':')
    if (!/^[A-Za-z]{2}$/.test(code || '') || !/^[a-z]{2,3}$/.test(language || '')) throw new Error('Країни: використовуйте формат US:en, DE:de:en')
    return { code: code.toUpperCase(), language, ...(secondary_language ? { secondary_language } : {}) }
  })
}

function short(value?: string) { return value ? `${value.slice(0, 8)}…${value.slice(-4)}` : '—' }
const STAGE_LABELS: Record<string, string> = {
  OWNER_CAPTURE: 'Початкова ідея', OWNER_DNA: 'Суть ідеї', QUERY_PLAN: 'План пошуку',
  SERP_DISCOVERY: 'Результати пошуку', COMPETITOR_SELECTION: 'Відбір конкурентів',
  COMPETITOR_EVIDENCE: 'Докази про конкурентів', COMPETITOR_DOSSIERS: 'Досьє конкурентів',
  OPPORTUNITY_MATRIX: 'Матриця можливостей', MARKET_SIGNAL_PLAN: 'План ринкових сигналів',
  MARKET_SIGNAL_COLLECTION: 'Релевантність доказів', MARKET_SIGNAL_GATE: 'Оцінка ринкових сигналів',
  TREND_QUERY_PLAN: 'План тренд-запитів', GOOGLE_TRENDS_RESEARCH: 'Дослідження Google Trends',
  TREND_GATE: 'Оцінка трендів', SYNTHESIS_PACKET: 'Пакет синтезу',
  IDEA_EXPANSION: 'Варіанти ідей', IDEA_CLUSTERING: 'Дедуплікація ідей',
  IDEA_EVALUATION: 'Оцінка ідей', FINAL_SHORTLIST: 'Фінальний список',
  cross_country_recurrence: 'Повторюваність між країнами', query_family_recurrence: 'Повторюваність типів запитів',
  recent_content_activity: 'Свіжа активність', community_activity: 'Активність спільнот',
  negative_pain_recurrence: 'Повторювані скарги', semantic_relevance: 'Семантична релевантність',
}
function humanStage(value: string) { return STAGE_LABELS[value] || value.replaceAll('_', ' ') }
function isI18n(value: unknown): value is I18n { return Boolean(value && typeof value === 'object' && 'en' in value && 'uk' in value) }
function runStatusLabel(status: LavalRun['status']) {
  return {
    pending: 'НЕ ЗАПУЩЕНО', running: 'ВИКОНУЄТЬСЯ', paused: 'ПРИЗУПИНЕНО',
    completed: 'ЗАВЕРШЕНО', failed: 'ПОМИЛКА', cancelled: 'СКАСОВАНО',
  }[status]
}
function runModeLabel(mode: LavalRun['approval_mode']) { return mode === 'automatic' ? 'АВТО · БЕЗ ЗУПИНОК' : 'З ПЕРЕВІРКОЮ' }
function runCreatedLabel(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)
}
function evidenceLabel(mode?: LavalEvidenceMode) {
  if (mode === 'live_complete') return 'LIVE COMPLETE'
  if (mode === 'live_market_signals') return 'LIVE · MARKET SIGNALS'
  if (mode === 'live_search_pending_trends') return 'LIVE · LEGACY PIPELINE'
  return 'DEMO — NO LIVE RESEARCH'
}
function stageTrustLabel(quality: LavalRunQuality | undefined, stage: string) {
  const item = quality?.by_stage.find((candidate) => candidate.stage === stage)
  if (!item) return ''
  if (item.failed || item.fallback) return ' · MODEL FAILED'
  if (item.success) return ' · MODEL ✓'
  return ''
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

export function LavalEngine({ api, language, initialRunId }: { api: ApiClient; language: Language; initialRunId?: string }) {
  const [runs, setRuns] = useState<LavalRun[] | null>(null)
  const [providers, setProviders] = useState<LavalProviderReadiness | null>(null)
  const [selected, setSelected] = useState<string | null>(initialRunId || null)
  const [status, setStatus] = useState<LavalStatus | null>(null)
  const [stageName, setStageName] = useState('')
  const [stageOutput, setStageOutput] = useState<unknown>(null)
  const [countryFilter, setCountryFilter] = useState('')
  const [view, setView] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [idea, setIdea] = useState('')
  const [countryText, setCountryText] = useState(DEFAULT_COUNTRIES)
  const [approvalMode, setApprovalMode] = useState<'automatic' | 'manual'>('automatic')
  const [requestedMode, setRequestedMode] = useState<'demo' | 'live'>('demo')
  const [busy, setBusy] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [stageLoading, setStageLoading] = useState(false)
  const [stageLoadError, setStageLoadError] = useState('')
  const [exportPreview, setExportPreview] = useState<{ filename: string; text: string } | null>(null)
  const inspectorRef = useRef<HTMLElement>(null)

  const loadRuns = async (preferredRunId?: string) => {
    try {
      const result = await api.get<{ items: LavalRun[] }>('/api/v1/laval/runs?limit=30')
      setRuns(result.items)
      setSelected((current) => {
        const requested = preferredRunId || current
        if (requested && result.items.some((item) => item.id === requested)) return requested
        return result.items[0]?.id || null
      })
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
    setBusy(true); setBusyAction('create'); setError(''); setNotice('')
    try {
      const result = await api.post<{ run_id: string }>('/api/v1/laval/runs', {
        text: idea,
        mode: requestedMode,
        config: { countries: countries(countryText), approval_mode: approvalMode },
      })
      setIdea(''); setShowCreate(false); setSelected(result.run_id)
      try {
        const launch = await api.post<{ started?: boolean }>(`/api/v1/laval/runs/${result.run_id}/run`, {})
        setNotice(launch.started === false
          ? 'Дослідження вже виконується.'
          : requestedMode === 'demo'
            ? 'Демо запущено. Воно чітко позначене як неживе дослідження.'
            : 'Живе дослідження запущено. Етапи оновлюються автоматично.')
      } catch (cause) {
        setError(`Ідею збережено, але запуск не розпочався: ${(cause as Error).message}`)
      }
      await loadStatus(result.run_id); await loadRuns(result.run_id)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false); setBusyAction('') }
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
  const approval = Boolean(
    status?.run.status === 'paused'
    && !status.run.awaiting_reason
    && !status.resume_with_market_signals_available
    && current
    && ['completed', 'partial'].includes(current.status)
    && status.run.approval_gates.includes(current.stage),
  )
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
      <fieldset className="laval-mode"><legend>Проходження етапів</legend>
        <label><input type="radio" name="approval-mode" value="automatic" checked={approvalMode === 'automatic'} onChange={() => setApprovalMode('automatic')} /><span><strong>Автоматично · рекомендовано</strong> — пройти всі 16 етапів без зупинок</span></label>
        <label><input type="radio" name="approval-mode" value="manual" checked={approvalMode === 'manual'} onChange={() => setApprovalMode('manual')} /><span><strong>З перевіркою</strong> — пауза на трьох контрольних точках</span></label>
      </fieldset>
      <button className="primary large" disabled={busy || !idea.trim() || (requestedMode === 'demo' ? !providers?.demo_available : !providers?.search_live_ready)} onClick={create}><FlaskConical />{busyAction === 'create' ? 'Запускаємо…' : requestedMode === 'demo' ? 'Запустити демо' : 'Запустити живе дослідження'}</button>
    </div>}
    <div className="laval-layout">
      <aside className="laval-runs" aria-label="Laval-запуски">
        {runs === null && <p className="muted">Завантаження…</p>}
        {runs?.length === 0 && <p className="muted">Ще немає Laval-запусків.</p>}
        {runs?.map((run) => <button key={run.id} className={selected === run.id ? 'selected' : ''} aria-current={selected === run.id ? 'true' : undefined} onClick={() => setSelected(run.id)}>
          <span><StatusDot status={run.status} />{runStatusLabel(run.status)}</span><div className="laval-run-badges"><em className={`evidence-badge ${run.evidence_mode || 'demo_fixture'}`}>{evidenceLabel(run.evidence_mode)}</em><em className={`run-mode-badge ${run.approval_mode}`}>{runModeLabel(run.approval_mode)}</em></div><strong>{run.owner_preview || 'Owner idea'}</strong><small>{short(run.id)} · {run.completed_stages ?? 0}/16{runCreatedLabel(run.created_at) ? ` · ${runCreatedLabel(run.created_at)}` : ''}</small>
        </button>)}
      </aside>
      <div className="laval-workspace">
        {!status && selected && <p className="muted">Завантаження запуску…</p>}
        {!selected && <div className="state"><FlaskConical /><h2>Створіть перший запуск</h2><p>Кожний етап буде видимим, відновлюваним і пов’язаним із доказами.</p></div>}
        {status && <>
          <header className="laval-run-head">
            <div><small>ВИБРАНИЙ RUN {short(status.run.id)} · OWNER {short(status.run.owner_idea_id)}</small><div className="laval-run-badges"><em className={`evidence-badge ${status.run.evidence_mode}`}>{evidenceLabel(status.run.evidence_mode)}</em><em className={`run-mode-badge ${status.run.approval_mode}`}>{runModeLabel(status.run.approval_mode)}</em></div><h3>{status.run.current_stage ? humanStage(status.run.current_stage) : 'CREATED'}</h3><p><StatusDot status={status.run.status} />{runStatusLabel(status.run.status)} · {status.stages.filter((item) => ['completed', 'partial'].includes(item.status)).length}/16</p>{status.run.status === 'pending' && <p className="laval-pending-note">Цей запуск створено, але він ще не почався.</p>}<p className="laval-cost">projected ${(status.cost.provider_projected_usd ?? 0).toFixed(4)} · reserved ${(status.cost.provider_reserved_usd ?? 0).toFixed(4)} · actual ${(status.cost.provider_actual_usd ?? status.cost.total_usd).toFixed(4)} · max ${(status.cost.max_spend_usd ?? .05).toFixed(2)}</p>{status.run.awaiting_reason && <p className="laval-waiting">{status.resume_with_market_signals_available ? 'Готово до продовження через Market Signals. Google Trends не потрібен; всі вже оплачені дані будуть збережені.' : 'Запуск очікує дії провайдера.'}</p>}</div>
            <div className="laval-actions">
              {status.run.status === 'pending' && <button className="primary" disabled={busy} onClick={() => act('run')}><Play />{busyAction === 'run' ? 'Запускаємо…' : 'Почати дослідження'}</button>}
              {status.run.status === 'running' && <button className="secondary" disabled={busy} onClick={() => act('pause')}><CirclePause />Пауза</button>}
              {status.run.status === 'paused' && !approval && !status.run.awaiting_reason && !status.resume_with_market_signals_available && <button className="primary" disabled={busy} onClick={() => act('resume')}><Play />Продовжити</button>}
              {status.resume_with_market_signals_available && <button className="primary" disabled={busy} onClick={() => act('resume-market-signals')}><Play />{busyAction === 'resume-market-signals' ? 'Продовжуємо…' : 'Продовжити дослідження'}</button>}
              {status.run.awaiting_reason && !status.resume_with_market_signals_available && <button className="secondary" disabled><CirclePause />Очікує провайдера</button>}
              {approval && current && <button className="primary" disabled={busy} onClick={() => act('approve', { stage: current.stage })}><Check />Схвалити й продовжити</button>}
              <button className="secondary" disabled={busy} onClick={() => download('json')}><Download />JSON</button>
              <button className="secondary" disabled={busy} onClick={() => download('md')}>MD</button>
            </div>
          </header>
          {status.quality && <RunQuality quality={status.quality} />}
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
              <span>S{String(stage.ordinal).padStart(2, '0')}</span><strong>{humanStage(stage.stage)}</strong><small>{stage.stage.replaceAll('_', ' ')} · {stage.status} · #{stage.attempt}{stage.provider ? ` · ${stage.provider}` : ''}{stageTrustLabel(status.quality, stage.stage)}</small>
            </button>)}
          </div>
          {stageName && <section className="laval-inspector" ref={inspectorRef} tabIndex={-1}>
            <div className="laval-inspector-head"><div><small>РЕЗУЛЬТАТ ЕТАПУ</small><h3>{humanStage(stageName)}</h3></div><div>
              {stageName === 'TREND_GATE' && <select aria-label="Trend view" value={view} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, value, countryFilter) }}><option value="">Усе</option><option value="scores">Trend Scores</option><option value="discoveries">Trend Discoveries</option></select>}
              {stageName === 'MARKET_SIGNAL_GATE' && <select aria-label="Market signal view" value={view} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, value, countryFilter) }}><option value="">Усе</option><option value="scores">MarketSignalScore</option></select>}
              {['SERP_DISCOVERY', 'COMPETITOR_SELECTION'].includes(stageName) && <select aria-label="Country filter" value={countryFilter} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, view, value) }}><option value="">Усі країни</option>{configuredCountries.map((code) => <option key={code}>{code}</option>)}</select>}
              <button className="secondary" disabled={busy} onClick={() => act('rerun', { stage: stageName, ...(stageName === 'SERP_DISCOVERY' && countryFilter ? { country: countryFilter } : {}) })}><RotateCcw />{busy ? 'Виконується…' : 'Перезапустити'}</button>
            </div></div>
            <StageArtifact stage={stageName} value={stageOutput} language={language} loading={stageLoading} error={stageLoadError} />
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

function RunQuality({ quality }: { quality: LavalRunQuality }) {
  if (quality.verdict === 'invalid') return <section className="laval-quality invalid" role="alert">
    <div><small>ЯКІСТЬ РЕЗУЛЬТАТУ · НЕДІЙСНИЙ</small><h4>Цей результат не можна використовувати</h4></div>
    <p>Автоматичний запуск завершив етапи, але модель не створила надійний аналіз. UI раніше показав технічний fallback як фінальний результат.</p>
    <dl><div><dt>Успішні відповіді моделі</dt><dd>{quality.success}/{quality.attempted}</dd></div><div><dt>Fallback</dt><dd>{quality.fallback}</dd></div><div><dt>Помилки</dt><dd>{quality.failed}</dd></div></dl>
    <p>Не приймайте рішення за shortlist і його балами. Потрібен новий запуск після виправлення; цей запуск збережено як історію.</p>
  </section>
  if (quality.verdict === 'verified') return <section className="laval-quality verified"><small>ЯКІСТЬ РЕЗУЛЬТАТУ · MODEL-BACKED</small><p>Усі обов’язкові мовні етапи виконані моделлю: {quality.success}/{quality.attempted}. Ринкові докази все одно слід перевірити.</p></section>
  if (quality.verdict === 'fixture') return <section className="laval-quality fixture"><small>ЯКІСТЬ РЕЗУЛЬТАТУ · DEMO</small><p>Детермінований fixture для перевірки процесу; це не ринковий висновок.</p></section>
  return <section className="laval-quality pending"><small>ЯКІСТЬ РЕЗУЛЬТАТУ · ЩЕ НЕ ГОТОВО</small><p>Мовні етапи, підтверджені моделлю: {quality.success}/{quality.attempted}.</p></section>
}

type ArtifactQuality = { run?: Omit<LavalRunQuality, 'by_stage'>; stage?: LavalQualityCount }
function record(value: unknown): Record<string, unknown> { return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} }
function rows(value: unknown): Array<Record<string, unknown>> { return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item))) : [] }
function text(value: unknown, language: Language) { return isI18n(value) ? String(local(value, language)) : String(value ?? '') }

function StageArtifact({ stage, value, language, loading, error }: { stage: string; value: unknown; language: Language; loading: boolean; error: string }) {
  if (loading) return <p className="muted" role="status">Завантаження артефакту…</p>
  if (error) return <p className="laval-failure">Не вдалося завантажити артефакт: {error}</p>
  const envelope = record(value)
  const output = 'output' in envelope ? envelope.output : value
  const quality = record(envelope.quality) as ArtifactQuality
  if (output === null || output === undefined) return <p className="muted">Артефакт ще не створено для незавершеного етапу.</p>
  return <>
    <ArtifactTrust quality={quality} />
    <ReadableArtifact stage={stage} output={output} language={language} quality={quality} />
    <RawArtifact output={output} />
  </>
}

function RawArtifact({ output }: { output: unknown }) {
  const [open, setOpen] = useState(false)
  return <details className="laval-raw" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}><summary>Технічні дані · raw JSON</summary>{open && <pre className="laval-json">{JSON.stringify(output, null, 2)}</pre>}</details>
}

function ArtifactTrust({ quality }: { quality: ArtifactQuality }) {
  const stage = quality.stage
  const run = quality.run
  if (stage?.verdict === 'invalid') return <p className="artifact-trust invalid"><strong>FALLBACK, НЕ РЕЗУЛЬТАТ МОДЕЛІ.</strong> Успішно {stage.success}/{stage.attempted}; fallback {stage.fallback}; помилок {stage.failed}.</p>
  if (run?.verdict === 'invalid') return <p className="artifact-trust invalid"><strong>НЕДІЙСНИЙ RUN.</strong> Цей етап залежить від невдалих model/fallback етапів вище.</p>
  if (stage?.verdict === 'verified') return <p className="artifact-trust verified"><strong>MODEL-BACKED.</strong> Успішно {stage.success}/{stage.attempted} відповідей.</p>
  if (run?.verdict === 'fixture') return <p className="artifact-trust fixture"><strong>DEMO FIXTURE.</strong> Лише перевірка механіки процесу.</p>
  return null
}

function ReadableArtifact({ stage, output, language, quality }: { stage: string; output: unknown; language: Language; quality: ArtifactQuality }) {
  const data = record(output)
  if (Array.isArray(output) && rows(output).some((item) => item.normalization_version)) return <MarketSignalScores scores={rows(output)} />
  if (rows(data.scores).some((item) => item.normalization_version)) return <MarketSignalScores scores={rows(data.scores)} />
  if (stage === 'OWNER_CAPTURE') return <div className="artifact-readable"><h4>Початкова ідея</h4><p>{String(data.raw_text || '—')}</p></div>
  if (stage === 'OWNER_DNA') {
    const dna = record(data.owner_dna)
    return <div className="artifact-readable"><h4>Що система зрозуміла з ідеї</h4><dl className="artifact-facts"><Fact label="Проблема" value={dna.problem} /><Fact label="Для кого" value={dna.target_user} /><Fact label="Механізм" value={dna.core_mechanism} /><Fact label="Емоція" value={dna.core_emotion} /><Fact label="Чому зараз" value={dna.why_now} /></dl><NamedList title="Що треба зберегти" values={dna.must_preserve} /><NamedList title="Невідоме" values={dna.unknowns} /></div>
  }
  if (stage === 'QUERY_PLAN') return <div className="artifact-readable"><h4>Пошукові наміри</h4><p>{rows(data.query_intents).length} запитів для {Array.isArray(data.countries) ? data.countries.length : 'заданих'} ринків.</p><div className="artifact-list">{rows(data.query_intents).map((item, index) => <article key={String(item.query_intent_id || index)}><small>{String(item.family || 'query')}</small><h5>{String(item.base_query || '—')}</h5><p>{rows(item.variants).map((variant) => `${String(variant.country)}:${String(variant.language)} — ${String(variant.query)}`).join(' · ')}</p></article>)}</div></div>
  if (stage === 'SERP_DISCOVERY') return <div className="artifact-readable"><h4>Що повернув пошук</h4><p>Провайдер: {String(data.provider || '—')}. Невдалих запитів: {rows(data.failures).length}.</p><div className="artifact-stats">{Object.entries(record(data.countries)).map(([country, searches]) => <div key={country}><strong>{Array.isArray(searches) ? searches.reduce((total, item) => total + rows(record(item).results).length, 0) : 0}</strong><span>{country} результатів</span></div>)}</div></div>
  if (stage === 'COMPETITOR_SELECTION') return <RankedEvidence title="Відібрані кандидати в конкуренти" items={rows(data.global_deduplicated)} language={language} />
  if (stage === 'COMPETITOR_EVIDENCE') return <div className="artifact-readable"><h4>Покриття доказами</h4><p>{rows(data.competitors).length} конкурентів · {rows(data.failures).length} збоїв джерел.</p><div className="artifact-list">{rows(data.competitors).map((item) => <article key={String(item.competitor_id)}><h5>{String(item.name || 'Конкурент')}</h5><p>{Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0} evidence items</p></article>)}</div></div>
  if (stage === 'COMPETITOR_DOSSIERS') return <div className="artifact-readable"><h4>Досьє конкурентів</h4><div className="artifact-list">{rows(data.competitors).map((item) => <article key={String(item.competitor_id)}><small>{String(item.type || 'competitor')} · confidence {(Number(item.confidence || 0) * 100).toFixed(0)}%</small><h5>{String(item.name || item.url || 'Конкурент')}</h5><NamedList title="Позиціонування" values={item.positioning} compact /><NamedList title="Скарги" values={item.complaints} compact /><NamedList title="Прогалини" values={item.gaps} compact /></article>)}</div></div>
  if (stage === 'OPPORTUNITY_MATRIX') return <Opportunities items={rows(data.opportunities)} />
  if (stage === 'MARKET_SIGNAL_PLAN') return <div className="artifact-readable"><h4>План Market Signals</h4><p>Нових платних пошуків: {record(data.additional_search).executed === true ? 'так' : '0'}. Використано вже збережені докази.</p><Opportunities items={rows(data.opportunities)} /></div>
  if (stage === 'MARKET_SIGNAL_COLLECTION') {
    const classifications = rows(data.classifications)
    return <div className="artifact-readable"><h4>Релевантність доказів</h4><div className="artifact-stats"><div><strong>{classifications.length}</strong><span>перевірено пар</span></div><div><strong>{classifications.filter((item) => item.relevant === true).length}</strong><span>релевантні</span></div></div><p>Режим: {String(data.classification_mode || '—')}</p></div>
  }
  if (stage === 'SYNTHESIS_PACKET') return <div className="artifact-readable"><h4>Пакет для генерації</h4><ArtifactCounts data={data} /><NamedList title="Повторювані болі" values={data.negative_pain_clusters} /><NamedList title="Патерни дистрибуції" values={data.distribution_patterns} /></div>
  if (stage === 'IDEA_EXPANSION') return <IdeaRows title="Згенеровані варіанти" items={rows(data.variants)} language={language} trusted={quality.run?.verdict !== 'invalid'} />
  if (stage === 'IDEA_CLUSTERING') return <div className="artifact-readable"><h4>Дедуплікація ідей</h4><div className="artifact-stats"><div><strong>{rows(data.clusters).length}</strong><span>унікальних кластерів</span></div><div><strong>{Array.isArray(data.representative_ids) ? data.representative_ids.length : 0}</strong><span>представників</span></div></div></div>
  if (stage === 'IDEA_EVALUATION') return <IdeaScores items={rows(data.scores)} language={language} />
  if (stage === 'FINAL_SHORTLIST') return <Shortlist items={rows(data.shortlist)} language={language} verdict={quality.run?.verdict} />
  if (stage === 'TREND_GATE') return <div className="artifact-readable"><h4>Trend Gate</h4><ArtifactCounts data={data} /></div>
  return <div className="artifact-readable"><h4>Короткий огляд</h4><ArtifactCounts data={data} /></div>
}

function Fact({ label, value }: { label: string; value: unknown }) { return <div><dt>{label}</dt><dd>{String(value || '—')}</dd></div> }
function NamedList({ title, values, compact = false }: { title: string; values: unknown; compact?: boolean }) {
  const items = Array.isArray(values) ? values.map((item) => typeof item === 'string' ? item : String(record(item).statement || record(item).name || JSON.stringify(item))).filter(Boolean) : []
  if (!items.length) return null
  return <div className={compact ? 'named-list compact' : 'named-list'}><strong>{title}</strong><ul>{items.slice(0, compact ? 3 : 8).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div>
}
function ArtifactCounts({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, value]) => Array.isArray(value) || ['string', 'number', 'boolean'].includes(typeof value)).slice(0, 10)
  return <div className="artifact-stats">{entries.map(([name, value]) => <div key={name}><strong>{Array.isArray(value) ? value.length : String(value)}</strong><span>{humanStage(name)}</span></div>)}</div>
}
function RankedEvidence({ title, items }: { title: string; items: Array<Record<string, unknown>>; language: Language }) {
  return <div className="artifact-readable"><h4>{title}</h4><div className="artifact-list">{items.map((item, index) => <article key={String(item.id || item.competitor_id || index)}><small>#{index + 1} · {String(item.result_type || item.type || 'candidate')}</small><h5>{String(item.name || item.domain || item.url || '—')}</h5><p>{String(item.domain || item.url || '')}{typeof item.score === 'number' ? ` · score ${(item.score * 100).toFixed(1)}` : ''}</p></article>)}</div></div>
}
function Opportunities({ items }: { items: Array<Record<string, unknown>> }) {
  return <div className="artifact-readable"><h4>Можливості</h4><div className="artifact-list">{items.map((item, index) => { const evidenceCount = Array.isArray(item.evidence_ids) ? item.evidence_ids.length : rows(item.evidence).length; return <article key={String(item.id || item.opportunity_id || index)}><small>#{index + 1}{typeof item.aggregate_score === 'number' ? ` · ${(item.aggregate_score * 100).toFixed(1)}` : ''} · {evidenceCount} доказів</small><h5>{String(item.statement || '—')}</h5><p>{String(item.affected_segment || item.pain || '')}</p></article> })}</div></div>
}
function IdeaRows({ title, items, language, trusted }: { title: string; items: Array<Record<string, unknown>>; language: Language; trusted: boolean }) {
  return <div className="artifact-readable"><h4>{title}</h4><div className="artifact-list">{items.map((item, index) => <article key={String(item.id || item.idea_id || index)}><small>{String(item.operator || 'idea')} · {trusted ? 'MODEL OUTPUT' : 'INVALID FALLBACK'}</small><h5>{text(item.title, language)}</h5><p>{text(item.one_liner, language)}</p></article>)}</div></div>
}
function IdeaScores({ items, language }: { items: Array<Record<string, unknown>>; language: Language }) {
  return <div className="artifact-readable"><h4>Незалежна оцінка</h4><div className="artifact-list">{items.map((item, index) => { const evaluator = record(item.evaluator); return <article key={String(item.idea_id || index)}><small>#{index + 1} · final {(Number(item.final_score || 0) * 100).toFixed(1)}</small><h5>{text(item.title, language)}</h5><p><strong>Критика:</strong> {String(evaluator.critique || '—')}</p><p><strong>Сильна сторона:</strong> {String(evaluator.strengths || '—')}</p></article> })}</div></div>
}
function Shortlist({ items, language, verdict }: { items: Array<Record<string, unknown>>; language: Language; verdict?: string }) {
  const trusted = verdict === 'verified'
  return <div className="laval-shortlist">{items.map((item) => <article key={String(item.idea_id)}><span>#{String(item.rank)}</span><div><small>{short(String(item.idea_id))} · {String(item.operator)} · {trusted && item.finalist ? 'FINALIST' : verdict === 'fixture' ? 'DEMO CANDIDATE' : 'INVALID FALLBACK'}</small><h4>{text(item.title, language) || String(item.idea_id)}</h4><p>{text(item.one_liner, language)}</p></div><strong>{(Number(item.final_score) * 100).toFixed(1)}</strong></article>)}</div>
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
