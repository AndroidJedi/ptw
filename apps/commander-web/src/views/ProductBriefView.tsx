import { Check, RefreshCcw, Send, Sparkles, Target } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { ProductBrief, ProductBriefDocument, ValidationSkillProposal } from '../types'

const activeStatuses = new Set(['queued', 'generating'])

function BriefDocument({ value }: { value: ProductBriefDocument }) {
  return <div className="brief-document">
    <section><small>POSITIONING HYPOTHESIS</small><h2>{value.promise}</h2><p>{value.product}</p></section>
    <section><dl><dt>First customer</dt><dd>{value.target_audience}</dd><dt>Main pain</dt><dd>{value.main_pain}</dd><dt>CTA</dt><dd>{value.cta}</dd></dl></section>
    <section><small>STRONG VALIDATION OFFER</small><h2>{value.offer}</h2><p>{value.trust_strategy}</p></section>
    <section><small>KEY BENEFITS</small><ul>{value.key_benefits.map((item) => <li key={item}>{item}</li>)}</ul></section>
  </div>
}

export function ProductBriefView({ api }: { api: ApiClient }) {
  const [items, setItems] = useState<ProductBrief[] | null>(null)
  const [selected, setSelected] = useState<ProductBrief | null>(null)
  const [rawIdea, setRawIdea] = useState('')
  const [correction, setCorrection] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [proposals, setProposals] = useState<ValidationSkillProposal[]>([])
  const [proposalLessons, setProposalLessons] = useState<Record<string, string>>({})

  const loadProposals = async (briefId: string) => {
    const value = await api.get<{ items: ValidationSkillProposal[] }>(`/api/v1/skill-proposals/product_brief?target_id=${briefId}`)
    setProposals(value.items)
    setProposalLessons(Object.fromEntries(value.items.map((item) => [item.proposal_id, item.lesson])))
  }
  const load = async (preferredId?: string) => {
    const value = await api.get<{ items: ProductBrief[] }>('/api/v1/briefs?limit=100')
    setItems(value.items)
    const id = preferredId || selected?.brief_id || value.items[0]?.brief_id
    if (!id) { setSelected(null); setProposals([]); return }
    const detail = await api.get<ProductBrief>(`/api/v1/briefs/${id}`)
    setSelected(detail)
    await loadProposals(id)
  }
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [api])
  useEffect(() => {
    if (!selected || !activeStatuses.has(selected.status)) return
    const timer = window.setInterval(() => void load(selected.brief_id).catch((cause: Error) => setError(cause.message)), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.brief_id, selected?.status])

  const create = async () => {
    if (!rawIdea.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ brief: ProductBrief }>('/api/v1/briefs', {
        request_id: crypto.randomUUID(), raw_idea: rawIdea.trim(),
      })
      setRawIdea(''); setNotice('One Product Brief is being generated from the idea.'); await load(result.brief.brief_id)
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
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/briefs/${selected.brief_id}/approve`, { honor_confirmed: true })
      setNotice('Approved. Exactly five Ad Creatives are now being generated.'); await load(selected.brief_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try { await api.post(`/api/v1/briefs/${selected.brief_id}/retry`, {}); await load(selected.brief_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const proposalAction = async (proposal: ValidationSkillProposal, action: 'update' | 'dismiss' | 'plan') => {
    setBusy(true); setError('')
    try {
      const lesson = (proposalLessons[proposal.proposal_id] || '').trim()
      await api.post(`/api/v1/skill-proposals/product_brief/${proposal.proposal_id}/${action}`, action === 'dismiss' ? {} : { lesson })
      await loadProposals(proposal.target_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!items) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="STAGE 1 · ONE HYPOTHESIS" title="Product Briefs" />
    {error && <ErrorState message={error} />}{notice && <p className="landing-notice" role="status">{notice}</p>}
    <section className="panel brief-create"><div><small>RAW IDEA ONLY</small><h2>What do you want to validate?</h2><p>No market research, SEO, YouTube, evidence reports, or alternative hypotheses.</p></div>
      <textarea rows={5} maxLength={10000} value={rawIdea} onChange={(event) => setRawIdea(event.target.value)} placeholder="Describe one product idea…" />
      <button className="primary large" disabled={busy || !rawIdea.trim()} onClick={create}><Sparkles />Generate Product Brief</button>
    </section>
    {!items.length ? <Empty><Target className="empty-mark" /><h2>No Product Brief yet</h2><p>Enter one raw idea above to start the smallest validation loop.</p></Empty> : <div className="brief-workspace">
      <aside className="panel brief-list"><small>BRIEFS</small>{items.map((item) => <button key={item.brief_id} className={selected?.brief_id === item.brief_id ? 'selected' : ''} onClick={() => void load(item.brief_id)}><strong>{item.raw_idea.slice(0, 100)}</strong><span>{item.status} · {item.language?.toUpperCase() || '—'} · {item.approved ? 'approved' : 'not approved'}</span></button>)}</aside>
      {selected && <div className="panel brief-detail"><small>BRIEF {selected.brief_id}</small><p className="uuid-line">Source {selected.owner_idea_source_id}{selected.base_brief_id ? ` · supersedes ${selected.base_brief_id}` : ''}</p>
        {activeStatuses.has(selected.status) && <p className="generation-state"><RefreshCcw className="spin" /> Generating one testable positioning…</p>}
        {selected.status === 'failed' && <div className="state error"><p>{selected.error_message || selected.error_code || 'Generation failed'}</p><button className="secondary" disabled={busy} onClick={retry}>Retry</button></div>}
        {selected.document && <><BriefDocument value={selected.document} />
          <div className="approval-row">{selected.approved ? <p><Check /> Approved · creative batch {selected.creative_batch_id}</p> : <button className="primary" disabled={busy} onClick={approve}><Check />I can honor this promise and offer — approve</button>}</div>
          <section className="brief-correction"><h2>Correct this hypothesis</h2><p>Creates a new immutable Brief that must be approved again.</p><textarea rows={4} maxLength={2000} value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder="One correction for the complete Brief…" /><button className="secondary" disabled={busy || !correction.trim()} onClick={correct}>Create replacement <Send /></button></section>
        </>}
        {!!proposals.length && <section className="lesson-proposals"><h2>Owner lesson proposals</h2><p>Edit the generalized lesson before an owner-gated plan may update only the Product Brief owner lessons.</p>{proposals.map((proposal) => <article key={proposal.proposal_id}><textarea rows={3} maxLength={500} disabled={proposal.status !== 'pending'} value={proposalLessons[proposal.proposal_id] || ''} onChange={(event) => setProposalLessons((items) => ({ ...items, [proposal.proposal_id]: event.target.value }))} /><small>{proposal.proposal_id} · {proposal.status}</small>{proposal.status === 'pending' && <div><button className="secondary" disabled={busy || !(proposalLessons[proposal.proposal_id] || '').trim()} onClick={() => void proposalAction(proposal, 'update')}>Save edit</button><button className="secondary" disabled={busy || !(proposalLessons[proposal.proposal_id] || '').trim()} onClick={() => void proposalAction(proposal, 'plan')}>Plan promotion</button><button className="ghost" disabled={busy} onClick={() => void proposalAction(proposal, 'dismiss')}>Dismiss</button></div>}</article>)}</section>}
      </div>}
    </div>}
  </>
}
