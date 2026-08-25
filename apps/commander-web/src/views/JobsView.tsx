import { AlertTriangle, Ban, Check, Clock3, LoaderCircle, Play, RotateCcw, StopCircle, TerminalSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import type { Job } from '../types'
import { ErrorState, Loading, PageHeader } from '../components/State'

const activeStatuses = new Set(['planning', 'queued', 'running', 'cancel_requested'])

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
    setBusy(true); setEvents([]); setError('')
    try {
      const job = await api.post<Job>('/api/v1/jobs', { mode, instruction: prompt })
      setPrompt(''); await load()
      await watch(job.id)
    } catch (cause) { setError((cause as Error).message); setBusy(false) }
  }
  const approve = async (job: Job) => {
    let gate = {}
    if (job.destructive) {
      const confirmation = window.prompt('Type: EXECUTE DESTRUCTIVE PLAN')?.trim()
      if (confirmation !== 'EXECUTE DESTRUCTIVE PLAN') return
      gate = { destructive_confirmation: confirmation }
    }
    setBusy(true); setEvents([]); setError('')
    try {
      await api.post(`/api/v1/command-sessions/${job.id}/approve`, { plan_digest: job.plan_digest, ...gate })
      await load(); await watch(job.id)
    } catch (cause) { setError((cause as Error).message); setBusy(false) }
  }
  const restore = async (job: Job) => {
    setBusy(true); setEvents([]); setError('')
    try {
      const restored = await api.post<Job>(`/api/v1/jobs/${job.id}/restore`, {})
      await load()
      if (restored.status === 'planning') await watch(job.id)
      else setBusy(false)
    } catch (cause) { setError((cause as Error).message); setBusy(false) }
  }
  const cancel = async (job: Job) => {
    if (!window.confirm('Cancel this active job? You can restore an unexecuted lesson plan afterward.')) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/jobs/${job.id}/cancel`, { confirmation: 'CANCEL JOB' })
      await load()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  if (!jobs && !error) return <Loading />
  return <>
    <PageHeader eyebrow="CODEX CONTROL" title="Jobs" />
    {error && <ErrorState message={error} retry={load} />}
    <section className="command-pane">
      <div className="mode-switch" role="group" aria-label="Command mode"><button className={mode === 'plan' ? 'selected' : ''} onClick={() => setMode('plan')}>Plan · read only</button><button className={mode === 'execute' ? 'selected' : ''} onClick={() => setMode('execute')}>Execute</button></div>
      <label htmlFor="instruction">Commander instruction</label>
      <textarea id="instruction" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe one bounded job…" rows={5} />
      <button className="primary large" onClick={submit} disabled={!prompt.trim() || busy}><TerminalSquare />{busy ? 'Working…' : mode === 'plan' ? 'Build plan' : 'Execute'}</button>
      {events.length > 0 && <pre className="event-log" aria-live="polite">{events.join('\n')}</pre>}
    </section>
    <section className="jobs-list">{jobs?.map((job) => <article key={job.id}>
      <div className={`job-state ${job.status}`}>{statusIcon(job.status)}</div>
      <div className="job-summary"><small>{job.id} · {job.mode}{job.destructive ? ' · DESTRUCTIVE' : ''} · {statusLabel(job.status)}</small><h2>{job.title}</h2><p>{job.plan_digest ? `Plan ready · ${job.plan_digest.slice(0, 12)}…` : job.error ? 'Needs attention' : 'Preparing plan…'}</p></div>
      <div className="job-actions">
        {job.status === 'awaiting_approval' && <button className="primary" disabled={busy} onClick={() => void approve(job)}><Play />{isLesson(job) ? 'Run lesson' : 'Run approved plan'}</button>}
        {['failed', 'cancelled'].includes(job.status) && (job.execution_count || 0) === 0 && <button disabled={busy} onClick={() => void restore(job)}><RotateCcw />Restore plan</button>}
        {activeStatuses.has(job.status) && <button className="cancel-job" disabled={busy} onClick={() => void cancel(job)}><StopCircle />Cancel</button>}
      </div>
      <details className="job-details" open={job.status === 'awaiting_approval' ? true : undefined}>
        <summary>Open details</summary>
        <dl><dt>Status</dt><dd>{statusLabel(job.status)}</dd><dt>Instruction</dt><dd><pre>{job.instruction || job.title}</pre></dd>{job.error && <><dt>Error</dt><dd role="alert">{job.error}</dd></>}{job.plan && <><dt>Approved plan</dt><dd><pre>{job.plan}</pre></dd></>}{job.created_at && <><dt>Created</dt><dd>{job.created_at}</dd></>}{job.updated_at && <><dt>Updated</dt><dd>{job.updated_at}</dd></>}</dl>
      </details>
      {job.deployment_revision && <p className="job-revision">Deployment {job.deployment_revision}</p>}
    </article>)}</section>
  </>
}

function isLesson(job: Job) { return (job.instruction || job.title).includes('/owner-lessons.md') }

function statusIcon(status: string) {
  if (status === 'completed') return <Check />
  if (status === 'failed') return <AlertTriangle />
  if (status === 'cancelled') return <Ban />
  if (status === 'awaiting_approval') return <Clock3 />
  return <LoaderCircle />
}

export function statusLabel(status: string) {
  return ({ queued: 'queued', planning: 'planning', awaiting_approval: 'ready to run', running: 'running', completed: 'completed', failed: 'failed', cancelled: 'cancelled', cancel_requested: 'cancellation requested' } as Record<string, string>)[status] || status
}
