import { Activity, AlertTriangle, ArrowUpRight, BriefcaseBusiness, Clock, MessageSquareMore } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { Overview } from '../types'
import { ErrorState, Loading, PageHeader } from '../components/State'

export function OverviewView({ api, language }: { api: ApiClient; language: Language }) {
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')
  const load = () => { setError(''); api.get<Overview>('/api/v1/overview').then(setData).catch((cause: Error) => setError(cause.message)) }
  useEffect(load, [api])
  if (error) return <ErrorState message={error} retry={load} />
  if (!data) return <Loading />
  const remaining = Math.max(0, Math.ceil((new Date(data.mission.deadline_at).getTime() - Date.now()) / 86_400_000))
  const trend = data.idea_score_trend
  const points = trend.length ? trend.map((item, index) => `${(index / Math.max(1, trend.length - 1)) * 100},${100 - item.best}`).join(' ') : ''
  return <>
    <PageHeader eyebrow="MISSION_20M_3Y" title={String(local(data.mission.name, language))} />
    <section className="mission-strip">
      <div><Clock /><span>До дедлайну</span><strong>{remaining} днів</strong></div>
      <div><Activity /><span>Система</span><strong>{Object.values(data.health).every((value) => value === 'ok') ? 'Здорова' : 'Увага'}</strong></div>
    </section>
    <section className="metric-grid" aria-label="Ключові показники">
      <article><MessageSquareMore /><span>Очікують перевірки</span><strong>{data.pending_reviews}</strong></article>
      <article><BriefcaseBusiness /><span>Активні завдання</span><strong>{data.jobs.active}</strong></article>
      <article className={data.jobs.blocked ? 'warn' : ''}><AlertTriangle /><span>Заблоковано</span><strong>{data.jobs.blocked}</strong></article>
      <article><ArrowUpRight /><span>Останнє розгортання</span><strong>{data.jobs.last_deploy || '—'}</strong></article>
    </section>
    <section className="panel trend">
      <div className="section-title"><div><p>ЕВОЛЮЦІЯ ІДЕЙ</p><h2>Динаміка оцінки</h2></div><span>Шкала 100 балів</span></div>
      {trend.length ? <><svg viewBox="0 0 100 100" role="img" aria-label="Графік найкращих оцінок за поколіннями"><polyline points={points} /></svg><div className="trend-labels"><span>G{trend[0].generation}</span><strong>{trend.at(-1)?.best.toFixed(1)}</strong><span>G{trend.at(-1)?.generation}</span></div></> : <p className="muted">Покоління 1 ще не запускалося.</p>}
    </section>
  </>
}
