import { Activity, AlertTriangle, ArrowUpRight, BriefcaseBusiness, Clock, FlaskConical, Palette } from 'lucide-react'
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
  return <>
    <PageHeader eyebrow="MISSION_20M_3Y" title={String(local(data.mission.name, language))} />
    <section className="mission-strip">
      <div><Clock /><span>До дедлайну</span><strong>{remaining} днів</strong></div>
      <div><Activity /><span>Система</span><strong>{Object.values(data.health).every((value) => value === 'ok') ? 'Здорова' : 'Увага'}</strong></div>
    </section>
    <section className="panel">
      <div className="section-title"><div><p>BRANDING V1</p><h2>Бренд-напрями та кити</h2></div><Palette /></div>
      <div className="metric-grid" aria-label="Статус Branding">
        <article><span>Усього</span><strong>{data.branding_runs.total}</strong></article>
        <article><span>Активні</span><strong>{data.branding_runs.active}</strong></article>
        <article><span>Завершені</span><strong>{data.branding_runs.completed}</strong></article>
      </div>
    </section>
    <section className="metric-grid" aria-label="Ключові показники">
      <article><BriefcaseBusiness /><span>Активні завдання</span><strong>{data.jobs.active}</strong></article>
      <article className={data.jobs.blocked ? 'warn' : ''}><AlertTriangle /><span>Заблоковано</span><strong>{data.jobs.blocked}</strong></article>
      <article><ArrowUpRight /><span>Останнє розгортання</span><strong>{data.jobs.last_deploy || '—'}</strong></article>
    </section>
    <section className="panel">
      <div className="section-title"><div><p>IDEA LAVAL ENGINE</p><h2>Інспектовані запуски</h2></div><FlaskConical /></div>
      <div className="metric-grid" aria-label="Статус Idea Laval">
        <article><span>Усього</span><strong>{data.laval_runs.total}</strong></article>
        <article><span>Активні</span><strong>{data.laval_runs.active}</strong></article>
        <article><span>Завершені</span><strong>{data.laval_runs.completed}</strong></article>
      </div>
      {data.laval_runs.total === 0 && <p className="muted">Ще немає ідей власника або Laval-запусків.</p>}
    </section>
  </>
}
