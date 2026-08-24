import { Image as ImageIcon, Megaphone, RefreshCcw, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { AdCreative, CreativeBatch, ValidationSkillProposal } from '../types'

const angleNames: Record<AdCreative['angle'], string> = {
  emotional: 'Emotional', practical: 'Practical', curiosity: 'Curiosity',
  authority: 'Authority', problem_first: 'Problem-first',
}

function AuthenticatedImage({ api, creative }: { api: ApiClient; creative: AdCreative }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    let objectUrl = ''
    void api.blob(creative.image.url).then((blob) => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl)
    }).catch((cause: Error) => setError(cause.message))
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, creative.creative_id, creative.image.url])
  if (error) return <div className="creative-image-fallback"><ImageIcon /><span>{error}</span></div>
  if (!url) return <div className="creative-image-fallback"><RefreshCcw className="spin" /><span>Loading authenticated image…</span></div>
  return <img src={url} alt={creative.image.alt || creative.image_description} />
}

function CreativeCard({ api, creative, onNotice }: {
  api: ApiClient; creative: AdCreative; onNotice: (message: string) => void
}) {
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [proposals, setProposals] = useState<ValidationSkillProposal[]>([])
  const [proposalLessons, setProposalLessons] = useState<Record<string, string>>({})
  const loadProposals = async () => {
    const result = await api.get<{ items: ValidationSkillProposal[] }>(`/api/v1/skill-proposals/ad_creative?target_id=${creative.creative_id}`)
    setProposals(result.items)
    setProposalLessons(Object.fromEntries(result.items.map((item) => [item.proposal_id, item.lesson])))
  }
  useEffect(() => { void loadProposals().catch((cause: Error) => setError(cause.message)) }, [api, creative.creative_id])
  const submit = async () => {
    if (!feedback.trim()) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ feedback_id: string; weight_update_id: string; proposal_id: string }>(`/api/v1/ad-creatives/${creative.creative_id}/feedback`, { comment: feedback.trim() })
      setFeedback(''); await loadProposals(); onNotice(`Feedback ${result.feedback_id} saved; lesson proposal ${result.proposal_id} is pending owner promotion.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const proposalAction = async (proposal: ValidationSkillProposal, action: 'update' | 'dismiss' | 'plan') => {
    setBusy(true); setError('')
    try {
      const lesson = (proposalLessons[proposal.proposal_id] || '').trim()
      await api.post(`/api/v1/skill-proposals/ad_creative/${proposal.proposal_id}/${action}`, action === 'dismiss' ? {} : { lesson })
      await loadProposals()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  return <article className="panel creative-card">
    <div className="creative-art"><AuthenticatedImage api={api} creative={creative} /></div>
    <div className="creative-copy"><small>{String(creative.ordinal + 1).padStart(2, '0')} · {angleNames[creative.angle]}</small><h2>{creative.hook}</h2><p>{creative.primary_text}</p><p className="creative-cta">CTA · {creative.cta}</p>
      <p className="pexels-credit"><a href={creative.image.source_url} target="_blank" rel="noreferrer">Photo</a> by <a href={creative.image.photographer_url} target="_blank" rel="noreferrer">{creative.image.photographer}</a> on <a href="https://www.pexels.com" target="_blank" rel="noreferrer">Pexels</a></p>
      <details><summary>Creative metadata</summary><dl><dt>Creative UUID</dt><dd>{creative.creative_id}</dd><dt>Brief UUID</dt><dd>{creative.brief_id}</dd><dt>Asset UUID</dt><dd>{creative.image.asset_id}</dd><dt>Emotion</dt><dd>{creative.desired_emotion}</dd><dt>Image category</dt><dd>{creative.image_category}</dd><dt>Crop</dt><dd>{creative.crop_focus}</dd><dt>SHA-256</dt><dd>{creative.image.sha256}</dd><dt>License</dt><dd><a href={creative.image.license_url} target="_blank" rel="noreferrer">{creative.image.license}</a></dd></dl></details>
      <div className="creative-feedback"><label>Feedback for this complete creative<textarea rows={3} maxLength={2000} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="What should future creatives learn?" /></label><button className="secondary" disabled={busy || !feedback.trim()} onClick={submit}>Save feedback <Send /></button>{error && <p role="alert">{error}</p>}</div>
      {!!proposals.length && <section className="lesson-proposals"><h3>Owner lesson proposals</h3>{proposals.map((proposal) => <article key={proposal.proposal_id}><textarea rows={3} maxLength={500} disabled={proposal.status !== 'pending'} value={proposalLessons[proposal.proposal_id] || ''} onChange={(event) => setProposalLessons((items) => ({ ...items, [proposal.proposal_id]: event.target.value }))} /><small>{proposal.proposal_id} · {proposal.status}</small>{proposal.status === 'pending' && <div><button className="secondary" disabled={busy || !(proposalLessons[proposal.proposal_id] || '').trim()} onClick={() => void proposalAction(proposal, 'update')}>Save edit</button><button className="secondary" disabled={busy || !(proposalLessons[proposal.proposal_id] || '').trim()} onClick={() => void proposalAction(proposal, 'plan')}>Plan promotion</button><button className="ghost" disabled={busy} onClick={() => void proposalAction(proposal, 'dismiss')}>Dismiss</button></div>}</article>)}</section>}
    </div>
  </article>
}

export function AdsView({ api }: { api: ApiClient }) {
  const [items, setItems] = useState<CreativeBatch[] | null>(null)
  const [selected, setSelected] = useState<CreativeBatch | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const load = async (preferredId?: string) => {
    const value = await api.get<{ items: CreativeBatch[] }>('/api/v1/ad-batches?limit=100')
    setItems(value.items)
    const id = preferredId || selected?.batch_id || value.items[0]?.batch_id
    if (!id) { setSelected(null); return }
    setSelected(await api.get<CreativeBatch>(`/api/v1/ad-batches/${id}`))
  }
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [api])
  useEffect(() => {
    if (!selected || !['queued', 'generating'].includes(selected.status)) return
    const timer = window.setInterval(() => void load(selected.batch_id).catch((cause: Error) => setError(cause.message)), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.batch_id, selected?.status])
  const retry = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try { await api.post(`/api/v1/ad-batches/${selected.batch_id}/retry`, {}); await load(selected.batch_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  if (!items) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="STAGE 2 · COMPLETE AD POSTS" title="Ads" />
    {error && <ErrorState message={error} />}{notice && <p className="landing-notice" role="status">{notice}</p>}
    {!items.length ? <Empty><Megaphone className="empty-mark" /><h2>No creative batch yet</h2><p>Approve a completed Product Brief to generate exactly five complete Ad Creatives.</p></Empty> : <div className="ads-workspace">
      <section className="panel"><label>Creative batch<select value={selected?.batch_id || ''} onChange={(event) => void load(event.target.value)}>{items.map((item) => <option key={item.batch_id} value={item.batch_id}>{item.batch_id} · {item.status}</option>)}</select></label>{selected && <p className="uuid-line">Brief {selected.brief_id} · batch {selected.batch_id}</p>}</section>
      {selected && ['queued', 'generating'].includes(selected.status) && <section className="panel generation-state"><RefreshCcw className="spin" /><div><h2>Building five creatives</h2><p>One structured call, fixed angles, real Pexels photos, deterministic 1080×1080 renders.</p></div></section>}
      {selected?.status === 'failed' && <section className="panel state error"><p>{selected.error_message || selected.error_code || 'Creative batch failed atomically.'}</p><button className="secondary" disabled={busy} onClick={retry}>Retry entire batch</button></section>}
      {selected?.status === 'completed' && <section className="creative-grid">{selected.creatives.map((creative) => <CreativeCard key={creative.creative_id} api={api} creative={creative} onNotice={setNotice} />)}</section>}
    </div>}
  </>
}
