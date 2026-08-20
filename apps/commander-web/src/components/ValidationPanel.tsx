import { Check, ClipboardList, Play, RefreshCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import type { MarketProbe, ValidationWorkspace } from '../types'

type ValidationList = { items: ValidationWorkspace[] }

export function ValidationPanel({ api }: { api: ApiClient }) {
  const [items, setItems] = useState<ValidationWorkspace[] | null>(null)
  const [selected, setSelected] = useState('')
  const [current, setCurrent] = useState<ValidationWorkspace | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async (workspaceId = selected) => {
    try {
      const list = await api.get<ValidationList>('/api/v1/validations')
      setItems(list.items)
      const id = workspaceId || list.items[0]?.workspace.id || ''
      setSelected(id)
      setCurrent(id ? await api.get<ValidationWorkspace>(`/api/v1/validations/${id}`) : null)
      setError('')
    } catch (cause) { setError((cause as Error).message) }
  }
  useEffect(() => { void load() }, [api])
  const act = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key); setError(''); setNotice('')
    try { await action(); await load(); setNotice('Збережено. Жодної зовнішньої дії PTW не виконав.') }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy('') }
  }

  return <section className="validation-panel">
    <header><div><small>MANUAL MARKET VALIDATION</small><h2>Валідація тези</h2><p>PTW зберігає план і докази. Публікацію, контакти та витрати виконуєте лише ви — поза системою.</p></div><button className="secondary" onClick={() => void load()}><RefreshCcw />Оновити</button></header>
    {error && <p className="laval-failure" role="alert">{error}</p>}
    {notice && <p className="laval-notice-inline">{notice}</p>}
    {items?.length === 0 && <div className="state"><ClipboardList /><h2>Ще немає workspace</h2><p>У вкладці «Дослідження» виберіть тезу, яка пережила фальсифікацію.</p></div>}
    {items && items.length > 0 && <div className="validation-layout">
      <aside>{items.map((item) => <button key={item.workspace.id} className={selected === item.workspace.id ? 'selected' : ''} onClick={() => { setSelected(item.workspace.id); void load(item.workspace.id) }}><strong>{String(item.hypothesis.attributes.claim || 'Product thesis')}</strong><small>{item.probes.length} probes · {item.insights.length} insights</small></button>)}</aside>
      {current && <div className="validation-workspace">
        <h3>{String(current.hypothesis.attributes.claim || 'Product thesis')}</h3>
        <p className="manual-boundary">Автоматичні зовнішні дії вимкнено. «Почати» лише фіксує ваш намір виконати probe вручну.</p>
        <div className="probe-grid">{current.probes.map((probe) => <ProbeCard key={probe.id} probe={probe} busy={busy} onStart={() => act(`start-${probe.id}`, () => api.post(`/api/v1/probes/${probe.id}/start`, {}))} onRevise={(body) => act(`revise-${probe.id}`, () => api.post(`/api/v1/validations/${current.workspace.id}/probes`, body))} onComplete={(body) => act(`complete-${probe.id}`, () => api.post(`/api/v1/probes/${probe.id}/complete`, body))} />)}</div>
        <DecisionForm disabled={Boolean(busy)} hasInsight={current.insights.length > 0} mechanisms={current.mechanisms || []} onSubmit={(body) => act('decision', () => api.post(`/api/v1/validations/${current.workspace.id}/decision`, body))} />
        {current.decisions.some((item) => item.attributes.action === 'continue') && <button className="primary" disabled={Boolean(busy)} onClick={() => act('plan', () => api.post(`/api/v1/validations/${current.workspace.id}/plan`, { request: 'Створи план продукту з валідованої тези.' }))}><ClipboardList />Створити Plan із контекстом</button>}
        <details><summary>Технічні деталі workspace</summary><pre>{JSON.stringify(current, null, 2)}</pre></details>
      </div>}
    </div>}
  </section>
}

function ProbeCard({ probe, busy, onStart, onRevise, onComplete }: { probe: MarketProbe; busy: string; onStart: () => void; onRevise: (body: Record<string, unknown>) => void; onComplete: (body: Record<string, unknown>) => void }) {
  const [value, setValue] = useState('')
  const [sample, setSample] = useState('')
  const [timeframe, setTimeframe] = useState('')
  const [notes, setNotes] = useState('')
  const [editing, setEditing] = useState(false)
  const [assumption, setAssumption] = useState(probe.attributes.assumption)
  const [procedure, setProcedure] = useState(probe.attributes.procedure)
  const [segment, setSegment] = useState(probe.attributes.target_segment)
  const metric = probe.attributes.success_criterion.metric
  return <article className={`probe ${probe.status}`}><header><span>{probe.status}</span><small>{probe.attributes.probe_type}</small></header><h4>{probe.attributes.assumption}</h4><p>{probe.attributes.procedure}</p><dl><div><dt>Сегмент</dt><dd>{probe.attributes.target_segment}</dd></div><div><dt>Критерій</dt><dd>{metric} ≥ {probe.attributes.success_criterion.threshold}</dd></div><div><dt>Вибірка / час</dt><dd>{probe.attributes.sample_target} / {probe.attributes.duration_days} днів</dd></div></dl>
    {probe.status === 'proposed' && !editing && <div className="probe-actions"><button className="secondary" disabled={Boolean(busy)} onClick={() => setEditing(true)}>Редагувати proposal</button><button className="secondary" disabled={Boolean(busy)} onClick={onStart}><Play />Почати вручну</button></div>}
    {probe.status === 'proposed' && editing && <div className="probe-observation"><label>Припущення<textarea value={assumption} onChange={(event) => setAssumption(event.target.value)} /></label><label>Процедура<textarea value={procedure} onChange={(event) => setProcedure(event.target.value)} /></label><label>Сегмент<input value={segment} onChange={(event) => setSegment(event.target.value)} /></label><button className="primary" disabled={Boolean(busy) || !assumption.trim() || !procedure.trim()} onClick={() => onRevise({ supersedes_probe_id: probe.id, probe_type: probe.attributes.probe_type, assumption_id: probe.attributes.assumption_id, assumption, procedure, target_segment: segment, metric, threshold: probe.attributes.success_criterion.threshold, sample_target: probe.attributes.sample_target, duration_days: probe.attributes.duration_days, budget_minor: probe.attributes.budget_minor })}>Зберегти нову ревізію</button></div>}
    {probe.status === 'running' && <div className="probe-observation"><label>{metric}<input type="number" value={value} onChange={(event) => setValue(event.target.value)} /></label><label>Розмір вибірки<input type="number" min="0" value={sample} onChange={(event) => setSample(event.target.value)} /></label><label>Період<input value={timeframe} onChange={(event) => setTimeframe(event.target.value)} placeholder="7 днів, 2026-08-20…" /></label><label>Фактичні нотатки<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label><button className="primary" disabled={Boolean(busy) || value === '' || sample === '' || !timeframe.trim()} onClick={() => onComplete({ values: { [metric]: Number(value) }, sample_size: Number(sample), timeframe, notes, limitations: '' })}><Check />Записати факт і завершити</button></div>}
  </article>
}

function DecisionForm({ disabled, hasInsight, mechanisms, onSubmit }: { disabled: boolean; hasInsight: boolean; mechanisms: ValidationWorkspace['mechanisms']; onSubmit: (body: Record<string, unknown>) => void }) {
  const [action, setAction] = useState('continue')
  const [rationale, setRationale] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [loop, setLoop] = useState('')
  const loopSteps = loop.split('\n').map((item) => item.trim()).filter(Boolean)
  const validRevision = action !== 'mutate' || selected.length > 0
  const validPivot = action !== 'pivot' || (loopSteps.length >= 5 && loopSteps.length <= 8)
  return <section className="validation-decision"><h3>Рішення власника</h3><p>Рішення та наступні ревізії додаються до історії; старі записи не переписуються.</p><label>Дія<select value={action} onChange={(event) => setAction(event.target.value)}><option value="continue" disabled={!hasInsight}>Continue — перейти до планування</option><option value="mutate">Mutate — ревізія з вибраних механізмів</option><option value="pivot">Pivot — матеріально інша петля</option><option value="reject">Reject — закрити тезу</option></select></label>
    {action === 'mutate' && <fieldset className="mechanism-picker"><legend>Механізми нової ревізії</legend>{mechanisms.map((item) => <label key={item.id}><input type="checkbox" checked={selected.includes(item.id)} onChange={(event) => setSelected((values) => event.target.checked ? [...values, item.id] : values.filter((id) => id !== item.id))} />{String(item.attributes.name?.uk || item.attributes.name?.en || item.id)}</label>)}</fieldset>}
    {action === 'pivot' && <label>Нова петля — 5–8 кроків, кожний з нового рядка<textarea rows={7} value={loop} onChange={(event) => setLoop(event.target.value)} /></label>}
    <label>Обґрунтування<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} /></label><button className="secondary" disabled={disabled || !rationale.trim() || !validRevision || !validPivot} onClick={() => onSubmit({ action, rationale, selected_mechanism_ids: selected, product_loop: loopSteps })}>Зафіксувати рішення</button></section>
}
