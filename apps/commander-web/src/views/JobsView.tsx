import { Check, Play, Square, TerminalSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import type { Job } from '../types'
import { ErrorState, Loading, PageHeader } from '../components/State'

export function JobsView({ api }: { api: ApiClient }) {
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [prompt, setPrompt] = useState('')
  const [mode, setMode] = useState<'plan' | 'execute'>('plan')
  const [events, setEvents] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => api.get<{ items: Job[] }>('/api/v1/jobs?limit=30').then((data) => setJobs(data.items)).catch((cause: Error) => setError(cause.message))
  useEffect(() => { void load() }, [api])
  const watch = async (jobId: string) => {
    const ws = new WebSocket(await api.websocketUrl(`/api/v1/jobs/${jobId}/events`))
    ws.onmessage = (event) => setEvents((current) => [...current.slice(-199), event.data])
    ws.onclose = () => { setBusy(false); void load() }
  }
  const submit = async () => {
    if (!prompt.trim()) return
    setBusy(true); setEvents([])
    try {
      const job = await api.post<Job>('/api/v1/jobs', { mode, instruction: prompt })
      setPrompt(''); await load()
      await watch(job.id)
    } catch (cause) { setError((cause as Error).message); setBusy(false) }
  }
  const approve = async (job: Job) => {
    let gate = {}
    if (job.destructive) {
      const confirmation = window.prompt('Введіть: EXECUTE DESTRUCTIVE PLAN')?.trim()
      if (confirmation !== 'EXECUTE DESTRUCTIVE PLAN') return
      gate = { destructive_confirmation: confirmation }
    }
    setBusy(true); setEvents([])
    await api.post(`/api/v1/command-sessions/${job.id}/approve`, { plan_digest: job.plan_digest, ...gate })
    await load(); await watch(job.id)
  }
  const cancel = async (job: Job) => { await api.post(`/api/v1/jobs/${job.id}/cancel`, {}); await load() }
  if (!jobs && !error) return <Loading />
  return <>
    <PageHeader eyebrow="КЕРУВАННЯ CODEX" title="Завдання" />
    {error && <ErrorState message={error} retry={load} />}
    <section className="command-pane">
      <div className="mode-switch" role="group" aria-label="Режим команди"><button className={mode === 'plan' ? 'selected' : ''} onClick={() => setMode('plan')}>План · лише читання</button><button className={mode === 'execute' ? 'selected' : ''} onClick={() => setMode('execute')}>Виконання</button></div>
      <label htmlFor="instruction">Інструкція Commander</label>
      <textarea id="instruction" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Наприклад: перегенеруй усі контексти ідей за новими правилами…" rows={5} />
      <button className="primary large" onClick={submit} disabled={!prompt.trim() || busy}><TerminalSquare />{busy ? 'Виконується…' : mode === 'plan' ? 'Побудувати план' : 'Виконати'}</button>
      {events.length > 0 && <pre className="event-log" aria-live="polite">{events.join('\n')}</pre>}
    </section>
    <section className="jobs-list">{jobs?.map((job) => <article key={job.id}>
      <div className={`job-state ${job.status}`}>{job.status === 'completed' ? <Check /> : <Play />}</div>
      <div><small>{job.id} · {job.mode === 'plan' ? 'план' : 'виконання'}{job.destructive ? ' · РУЙНІВНЕ' : ''} · {statusLabel(job.status)}</small><h2>{job.title}</h2><p>{job.plan_digest ? `План ${job.plan_digest.slice(0, 12)}…` : 'Очікуємо відбиток плану'}</p>{job.plan && <details className="job-plan"><summary>Перегляд затверджуваного плану</summary><pre>{job.plan}</pre></details>}{job.deployment_revision && <p>Розгортання {job.deployment_revision}</p>}</div>
      <div className="job-actions">{job.status === 'awaiting_approval' && <button onClick={() => approve(job)}>Затвердити й виконати</button>}{!['completed', 'failed', 'cancelled'].includes(job.status) && <button className="icon-button" aria-label="Скасувати завдання" onClick={() => cancel(job)}><Square /></button>}</div>
    </article>)}</section>
  </>
}

function statusLabel(status: string) {
  return ({ queued: 'у черзі', planning: 'планування', awaiting_approval: 'очікує затвердження', running: 'виконується', completed: 'завершено', failed: 'помилка', cancelled: 'скасовано', cancel_requested: 'скасування запитано' } as Record<string, string>)[status] || status
}
