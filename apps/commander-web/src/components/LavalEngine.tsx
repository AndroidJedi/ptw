import { Check, CirclePause, Download, Eye, FlaskConical, Play, Plus, RefreshCcw, RotateCcw, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { I18n, LavalRun, LavalStage, LavalStatus } from '../types'

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

export function LavalEngine({ api, language }: { api: ApiClient; language: Language }) {
  const [runs, setRuns] = useState<LavalRun[] | null>(null)
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
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadRuns = async () => {
    try {
      const result = await api.get<{ items: LavalRun[] }>('/api/v1/laval/runs?limit=30')
      setRuns(result.items)
      if (!selected && result.items[0]) setSelected(result.items[0].id)
    } catch (cause) { setError((cause as Error).message) }
  }
  const loadStatus = async (runId = selected) => {
    if (!runId) return
    try { setStatus(await api.get<LavalStatus>(`/api/v1/laval/runs/${runId}`)) }
    catch (cause) { setError((cause as Error).message) }
  }

  useEffect(() => { void loadRuns() }, [api])
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
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const create = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.post<{ run_id: string }>('/api/v1/laval/runs', {
        text: idea,
        config: { countries: countries(countryText), approval_mode: automatic ? 'automatic' : 'manual' },
      })
      setIdea(''); setShowCreate(false); setSelected(result.run_id)
      await loadRuns()
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const inspect = async (stage: LavalStage, selectedView = view, country = countryFilter) => {
    if (!selected) return
    setStageName(stage.stage); setView(selectedView); setCountryFilter(country); setError('')
    const params = new URLSearchParams({ stage: stage.stage })
    if (selectedView) params.set('view', selectedView)
    if (country) params.set('country', country)
    try { setStageOutput(await api.get(`/api/v1/laval/runs/${selected}/show?${params}`)) }
    catch (cause) { setError((cause as Error).message) }
  }
  const download = async (format: 'json' | 'md') => {
    if (!selected) return
    try {
      const params = new URLSearchParams({ format })
      if (stageName) params.set('stage', stageName)
      const blob = await api.blob(`/api/v1/laval/runs/${selected}/export?${params}`)
      const href = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = href; anchor.download = `laval-${selected}-${stageName || 'all'}.${format}`; anchor.click()
      URL.revokeObjectURL(href)
    } catch (cause) { setError((cause as Error).message) }
  }

  const current = status?.stages.find((item) => item.stage === status.run.current_stage)
  const approval = Boolean(status?.run.status === 'paused' && current && ['completed', 'partial'].includes(current.status) && status.run.approval_gates.includes(current.stage))
  const configuredCountries = useMemo(() => ((status?.run.config.countries as Array<{ code: string }> | undefined) || []).map((item) => item.code), [status])

  return <section className="laval-engine">
    <div className="laval-toolbar">
      <div><small>IDEA LAVAL ENGINE</small><h2>Evidence → opportunity → trend → ideas</h2></div>
      <button className="primary" onClick={() => setShowCreate(true)}><Plus />Нова Laval-ідея</button>
    </div>
    {error && <div className="laval-error" role="alert">{error}<button onClick={() => setError('')} aria-label="Закрити"><X /></button></div>}
    {showCreate && <div className="laval-create">
      <div><strong>Нова ідея власника</strong><button onClick={() => setShowCreate(false)} aria-label="Закрити"><X /></button></div>
      <label>Повний текст ідеї<textarea rows={9} value={idea} onChange={(event) => setIdea(event.target.value)} placeholder="Проблема, користувач, механізм і те, що не можна втратити…" /></label>
      <label>Країна:мова[:друга мова]<input value={countryText} onChange={(event) => setCountryText(event.target.value)} /></label>
      <label className="check-row"><input type="checkbox" checked={automatic} onChange={(event) => setAutomatic(event.target.checked)} /><span>Автоматично проходити контрольні точки</span></label>
      <button className="primary large" disabled={busy || !idea.trim()} onClick={create}><FlaskConical />Створити інспектований запуск</button>
    </div>}
    <div className="laval-layout">
      <aside className="laval-runs" aria-label="Laval-запуски">
        {runs === null && <p className="muted">Завантаження…</p>}
        {runs?.length === 0 && <p className="muted">Ще немає Laval-запусків.</p>}
        {runs?.map((run) => <button key={run.id} className={selected === run.id ? 'selected' : ''} onClick={() => setSelected(run.id)}>
          <span><StatusDot status={run.status} />{run.status}</span><strong>{run.owner_preview || 'Owner idea'}</strong><small>{short(run.id)} · {run.completed_stages ?? 0}/16</small>
        </button>)}
      </aside>
      <div className="laval-workspace">
        {!status && selected && <p className="muted">Завантаження запуску…</p>}
        {!selected && <div className="state"><FlaskConical /><h2>Створіть перший запуск</h2><p>Кожний етап буде видимим, відновлюваним і пов’язаним із доказами.</p></div>}
        {status && <>
          <header className="laval-run-head">
            <div><small>RUN {short(status.run.id)} · OWNER {short(status.run.owner_idea_id)}</small><h3>{status.run.current_stage ? humanStage(status.run.current_stage) : 'CREATED'}</h3><p><StatusDot status={status.run.status} />{status.run.status} · {status.stages.filter((item) => ['completed', 'partial'].includes(item.status)).length}/16 · ${status.cost.total_usd.toFixed(4)}</p></div>
            <div className="laval-actions">
              {['pending', 'failed'].includes(status.run.status) && <button className="primary" disabled={busy} onClick={() => act(status.run.status === 'failed' ? 'resume' : 'run')}><Play />{status.run.status === 'failed' ? 'Повторити' : 'Запустити'}</button>}
              {status.run.status === 'running' && <button className="secondary" disabled={busy} onClick={() => act('pause')}><CirclePause />Пауза</button>}
              {status.run.status === 'paused' && !approval && <button className="primary" disabled={busy} onClick={() => act('resume')}><Play />Продовжити</button>}
              {approval && current && <button className="primary" disabled={busy} onClick={() => act('approve', { stage: current.stage })}><Check />Схвалити й продовжити</button>}
              <button className="secondary" onClick={() => download('json')}><Download />JSON</button>
              <button className="secondary" onClick={() => download('md')}>MD</button>
            </div>
          </header>
          {status.run.error_text && <p className="laval-failure">{status.run.error_text}</p>}
          <div className="laval-stages">
            {status.stages.map((stage) => <button key={stage.stage} className={`${stage.status} ${stageName === stage.stage ? 'selected' : ''}`} onClick={() => inspect(stage)} disabled={stage.status === 'pending' && !stage.input_hash}>
              <span>S{String(stage.ordinal).padStart(2, '0')}</span><strong>{humanStage(stage.stage)}</strong><small>{stage.status} · #{stage.attempt}{stage.provider ? ` · ${stage.provider}` : ''}</small>
            </button>)}
          </div>
          {stageName && <section className="laval-inspector">
            <div className="laval-inspector-head"><div><small>АРТЕФАКТ ЕТАПУ</small><h3>{humanStage(stageName)}</h3></div><div>
              {stageName === 'TREND_GATE' && <select aria-label="Trend view" value={view} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, value, countryFilter) }}><option value="">Усе</option><option value="scores">Trend Scores</option><option value="discoveries">Trend Discoveries</option></select>}
              {['SERP_DISCOVERY', 'COMPETITOR_SELECTION'].includes(stageName) && <select aria-label="Country filter" value={countryFilter} onChange={(event) => { const value = event.target.value; const stage = status.stages.find((item) => item.stage === stageName); if (stage) void inspect(stage, view, value) }}><option value="">Усі країни</option>{configuredCountries.map((code) => <option key={code}>{code}</option>)}</select>}
              <button className="secondary" onClick={() => act('rerun', { stage: stageName, ...(stageName === 'SERP_DISCOVERY' && countryFilter ? { country: countryFilter } : {}) })}><RotateCcw />Перезапустити</button>
            </div></div>
            <StageArtifact value={stageOutput} language={language} />
            <OverridePanel apiAction={(body) => act('override', body)} stage={stageName} countries={configuredCountries} />
          </section>}
        </>}
      </div>
    </div>
  </section>
}

function StatusDot({ status }: { status: string }) { return <i className={`status-dot ${status}`} aria-hidden="true" /> }

function StageArtifact({ value, language }: { value: unknown; language: Language }) {
  const output = value && typeof value === 'object' && 'output' in value ? (value as { output: unknown }).output : value
  if (!output) return <p className="muted">Артефакт ще не створено.</p>
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
  useEffect(() => { if (suggested) { setType(suggested); setAction(suggested === 'competitor' ? 'reject' : 'disable') } }, [suggested])
  return <details className="laval-override"><summary>Ручне виправлення · audit log</summary><div>
    <label>Тип<select value={type} onChange={(event) => { const value = event.target.value; setType(value); setAction(value === 'competitor' ? 'reject' : 'disable') }}><option value="competitor">Competitor</option><option value="opportunity">Opportunity</option><option value="trend">Trend</option></select></label>
    {type === 'competitor' && <label>Дія<select value={action} onChange={(event) => setAction(event.target.value)}><option value="reject">Reject</option><option value="add">Add URL</option></select></label>}
    {type === 'competitor' && action === 'add' && <label>Країна<select value={country} onChange={(event) => setCountry(event.target.value)}>{countries.map((code) => <option key={code}>{code}</option>)}</select></label>}
    <label>{action === 'add' ? 'URL' : 'UUID'}<input value={target} onChange={(event) => setTarget(event.target.value)} /></label>
    <label>Причина<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    <button className="secondary" disabled={!target} onClick={() => apiAction({ type, action, target_id: target, reason, ...(action === 'add' ? { payload: { url: target, country } } : {}) })}><Eye />Застосувати й позначити downstream stale</button>
  </div></details>
}
