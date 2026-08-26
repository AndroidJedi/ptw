import { Check, RefreshCcw, Send, Sparkles, Target } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { ProductBrief, ProductBriefDocument, ValidationProject } from '../types'

const activeStatuses = new Set(['queued', 'generating'])

function BriefDocument({ value }: { value: ProductBriefDocument }) {
  return <div className="brief-document">
    <section><small>POSITIONING HYPOTHESIS</small><h2>{value.promise}</h2><p>{value.product}</p></section>
    <section><dl><dt>First customer</dt><dd>{value.target_audience}</dd><dt>Main pain</dt><dd>{value.main_pain}</dd><dt>CTA</dt><dd>{value.cta}</dd></dl></section>
    <section><small>STRONG VALIDATION OFFER</small><h2>{value.offer}</h2><p>{value.trust_strategy}</p></section>
    <section><small>KEY BENEFITS</small><ul>{value.key_benefits.map((item) => <li key={item}>{item}</li>)}</ul></section>
  </div>
}

export function ProductBriefView({ api, projectId, onProjectCreated, onProjectBriefChanged, onProjectsRefresh, onOpenResult }: {
  api: ApiClient
  projectId: string | null
  onProjectCreated: (project: ValidationProject) => void
  onProjectBriefChanged: (projectId: string, name: string, briefId: string, status: ProductBrief['status']) => void
  onProjectsRefresh: (preferredId?: string) => Promise<void>
  onOpenResult: () => void
}) {
  const [items, setItems] = useState<ProductBrief[] | null>(null)
  const [selected, setSelected] = useState<ProductBrief | null>(null)
  const [rawIdea, setRawIdea] = useState('')
  const [correction, setCorrection] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const load = async (preferredId?: string, targetProjectId = projectId) => {
    if (!targetProjectId) { setItems([]); setSelected(null); return }
    const value = await api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(targetProjectId)}`)
    setItems(value.items)
    const id = preferredId || (value.items.some((item) => item.brief_id === selected?.brief_id) ? selected?.brief_id : undefined) || value.items[0]?.brief_id
    if (!id) { setSelected(null); return }
    const detail = await api.get<ProductBrief>(`/api/v1/briefs/${id}`)
    setSelected(detail)
    onProjectBriefChanged(detail.project_id, detail.project_name, detail.brief_id, detail.status)
  }
  useEffect(() => {
    setItems(null); setSelected(null); setError('')
    void load().catch((cause: Error) => setError(cause.message))
  }, [api, projectId])
  useEffect(() => {
    if (!selected || !activeStatuses.has(selected.status)) return
    const timer = window.setInterval(() => void load(selected.brief_id).catch((cause: Error) => setError(cause.message)), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.brief_id, selected?.status])

  const create = async () => {
    if (!rawIdea.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ project: ValidationProject; brief: ProductBrief }>('/api/v1/briefs', {
        request_id: crypto.randomUUID(), raw_idea: rawIdea.trim(),
      })
      onProjectCreated(result.project)
      setRawIdea(''); setNotice('Project created. One Product Brief is being generated from the idea.'); await load(result.brief.brief_id, result.project.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const correct = async () => {
    if (!selected || !correction.trim()) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ brief: ProductBrief }>(`/api/v1/briefs/${selected.brief_id}/correct`, {
        request_id: crypto.randomUUID(), instruction: correction.trim(),
      })
      setCorrection(''); setNotice('A complete immutable replacement Brief is being generated.'); await load(result.brief.brief_id)
      await onProjectsRefresh(result.brief.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/briefs/${selected.brief_id}/approve`, { honor_confirmed: true })
      setNotice('Approved. Add the task in Result when you are ready.'); await load(selected.brief_id)
      await onProjectsRefresh(selected.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try { await api.post(`/api/v1/briefs/${selected.brief_id}/retry`, {}); await load(selected.brief_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  if (!items) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="STAGE 1 · ONE HYPOTHESIS" title="Product Briefs" />
    {error && <ErrorState message={error} />}{notice && <p className="notice" role="status">{notice}</p>}
    <section className="panel brief-create"><div><small>NEW PROJECT · RAW IDEA ONLY</small><h2>What do you want to validate?</h2><p>Generating an initial Brief creates and selects a new Project. No market research, SEO, YouTube, evidence reports, or alternative hypotheses.</p></div>
      <textarea id="new-project-idea" rows={5} maxLength={10000} value={rawIdea} onChange={(event) => setRawIdea(event.target.value)} placeholder="Describe one product idea…" />
      <button className="primary large" disabled={busy || !rawIdea.trim()} onClick={create}><Sparkles />Generate Product Brief & Create Project</button>
    </section>
    {!items.length ? <Empty><Target className="empty-mark" /><h2>{projectId ? 'No Product Brief in this Project' : 'No Project yet'}</h2><p>Enter one raw idea above to create a Project and start the smallest validation loop.</p></Empty> : <div className="brief-workspace">
      <aside className="panel brief-list"><small>BRIEF HISTORY</small>{items.map((item, index) => <button key={item.brief_id} className={selected?.brief_id === item.brief_id ? 'selected' : ''} onClick={() => void load(item.brief_id)}><strong>{index === 0 ? 'Current Brief' : 'Earlier Brief'} · {item.product || item.raw_idea.slice(0, 70)}</strong><span>{item.status} · {item.language?.toUpperCase() || '—'} · {item.approved ? 'approved' : 'not approved'} · {new Date(item.created_at).toLocaleDateString()}</span></button>)}</aside>
      {selected && <div className="panel brief-detail"><small>{selected.base_brief_id ? 'REPLACEMENT BRIEF' : 'CURRENT IMMUTABLE BRIEF'}</small>
        {activeStatuses.has(selected.status) && <p className="generation-state"><RefreshCcw className="spin" /> Generating one testable hypothesis…</p>}
        {selected.status === 'failed' && <div className="state error"><p>{selected.error_message || selected.error_code || 'Generation failed'}</p><button className="secondary" disabled={busy} onClick={retry}>Retry</button></div>}
        {selected.document && <><BriefDocument value={selected.document} />
          <div className="approval-row">{selected.approved ? <><p><Check /> Approved for Result generation</p><button className="primary" onClick={onOpenResult}><Sparkles />Create result</button></> : <button className="primary" disabled={busy} onClick={approve}><Check />I can honor this promise and offer — approve</button>}</div>
          <section className="brief-correction"><h2>Correct this hypothesis</h2><p>Creates a new immutable Brief that must be approved again.</p><textarea rows={4} maxLength={2000} value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder="One correction for the complete Brief…" /><button className="secondary" disabled={busy || !correction.trim()} onClick={correct}>Create replacement <Send /></button></section>
        </>}
      </div>}
    </div>}
  </>
}
