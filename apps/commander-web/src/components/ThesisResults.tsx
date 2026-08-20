import { Check, FlaskConical, RefreshCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { ProductMechanism, ThesisCollection } from '../types'

function verdictLabel(verdict: string, recommended: boolean) {
  if (recommended) return 'Рекомендована теза'
  if (verdict === 'survives') return 'Пройшла фальсифікацію'
  if (verdict === 'weak') return 'Слабка'
  return 'Відхилена'
}

export function ThesisResults({ api, runId, language, ready }: { api: ApiClient; runId: string; language: Language; ready: boolean }) {
  const [collection, setCollection] = useState<ThesisCollection | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const mechanisms = useMemo(() => new Map((collection?.mechanisms || []).map((item) => [item.id, item])), [collection])

  const load = async () => {
    if (!ready) return
    try { setCollection(await api.get<ThesisCollection>(`/api/v1/laval/runs/${runId}/theses`)); setError('') }
    catch (cause) { setError((cause as Error).message) }
  }
  useEffect(() => { setCollection(null); void load() }, [api, runId, ready])
  if (!ready) return null

  return <section className="thesis-results">
    <header><div><small>ПРОДУКТОВІ ТЕЗИ</small><h3>Що саме варто перевірити на ринку</h3><p>Варіанти ідей були проміжним матеріалом. Нижче — повні продуктові петлі, зібрані з механізмів і перевірені на заперечення.</p></div><button className="secondary" onClick={() => void load()}><RefreshCcw />Оновити</button></header>
    {error && <p className="laval-failure">{error}</p>}
    {!collection && !error && <p className="muted">Завантаження тез…</p>}
    {collection?.status === 'no_surviving_thesis' && <div className="thesis-empty"><FlaskConical /><strong>Жодна теза не пережила фальсифікацію</strong><p>Запуск завершено чесно: рекомендацію та гіпотезу не створено.</p></div>}
    <div className="thesis-grid">{collection?.items.map((thesis) => <article key={thesis.id} className={`${thesis.verdict} ${thesis.recommended ? 'recommended' : ''}`}>
      <header><span>{verdictLabel(thesis.verdict, thesis.recommended)}</span><small>{thesis.mechanism_ids.length} механізмів · {thesis.evidence_ids.length} evidence IDs</small></header>
      <h3>{local(thesis.title, language)}</h3>
      <p><strong>Для кого:</strong> {local(thesis.target_user, language)}</p>
      <p><strong>Проблема:</strong> {local(thesis.problem, language)}</p>
      <div className="thesis-loop"><strong>Петля продукту</strong><ol>{thesis.loop_steps.map((step, index) => <li key={`${thesis.id}-loop-${index}`}>{local(step, language)}</li>)}</ol></div>
      <p><strong>Момент цінності:</strong> {local(thesis.value_moment, language)}</p>
      <p><strong>Поведінка без аудиторії:</strong> {local(thesis.zero_audience_behavior, language)}</p>
      <Mechanisms values={thesis.mechanism_ids.map((id) => mechanisms.get(id)).filter((item): item is ProductMechanism => Boolean(item))} language={language} />
      <div className="thesis-risks"><strong>Небезпечні припущення</strong><ul>{thesis.dangerous_assumptions.map((item) => <li key={item.id}><em>{item.severity}</em>{local(item.statement, language)}</li>)}</ul></div>
      <p className="thesis-verdict">Фальсифікація: {verdictLabel(thesis.verdict, false)} · непідтриманих критичних припущень: {thesis.unsupported_high_severity_count}</p>
      {thesis.recommendation_reason && <p className="thesis-reason"><strong>Чому рекомендовано:</strong> {thesis.recommendation_reason}</p>}
      {thesis.validation_stale && <p className="laval-failure">Цей validation workspace базується на старішій ревізії тези. Його записи збережено, але дослідження було перебудоване.</p>}
      <details><summary>Технічні деталі та UUID</summary><pre>{JSON.stringify(thesis, null, 2)}</pre></details>
      {thesis.verdict === 'survives' && <button className="primary" disabled={Boolean(busy) || Boolean(thesis.validation_workspace_id)} onClick={async () => {
        setBusy(thesis.id); setError('')
        try {
          await api.post(`/api/v1/laval/runs/${runId}/theses/${thesis.id}/select`, {})
          await load()
        } catch (cause) { setError((cause as Error).message) }
        finally { setBusy('') }
      }}><Check />{thesis.validation_workspace_id ? 'Вибрано для валідації' : busy === thesis.id ? 'Створюємо workspace…' : 'Вибрати для валідації'}</button>}
    </article>)}</div>
  </section>
}

function Mechanisms({ values, language }: { values: ProductMechanism[]; language: Language }) {
  return <div className="thesis-mechanisms"><strong>Механізми</strong>{values.map((item) => <div key={item.id}><span>{item.mechanism_type}</span><h4>{local(item.name, language)}</h4><p>{local(item.description, language)}</p><small>{Object.entries(item.support_dimensions).map(([name, value]) => `${name}: ${value}`).join(' · ')}</small></div>)}</div>
}
