import { AlertTriangle, Bell, Image as ImageIcon, Megaphone, RefreshCcw, Send, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { OwnerLessonProposals } from '../components/OwnerLessonProposals'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { AdCreative, CreativeBatch } from '../types'

const angleNames: Record<AdCreative['angle'], string> = {
  emotional: 'Emotional', practical: 'Practical', curiosity: 'Curiosity',
  authority: 'Authority', problem_first: 'Problem-first',
}

export function batchFailureReason(batch: CreativeBatch, previous = false) {
  const attempt = previous ? batch.last_failed_attempt : batch
  const detail = attempt?.error_message || attempt?.error_code || 'The generator stopped without a detailed error.'
  if (detail.includes('retain the Product Brief offer') || detail.includes('offer field') || detail.includes('offer wording')) {
    return {
      title: 'Approved offer continuity check failed',
      detail,
      explanation: batch.approved_offer
        ? `At least one generated draft did not preserve the approved offer as required: “${batch.approved_offer}”.`
        : 'At least one generated draft did not preserve the approved Product Brief offer as required.',
    }
  }
  return { title: 'Creative batch generation failed', detail, explanation: detail }
}

function notificationText(batch: CreativeBatch) {
  const status = batch.failure_notification?.status
  if (status === 'sent') return 'Telegram failure notification sent to the allowlisted owner chat.'
  if (status === 'ambiguous') return 'Telegram delivery timed out; delivery is unknown and was not retried.'
  if (status === 'suppressed') return 'Telegram notification was suppressed by emergency stop.'
  if (status === 'failed') return 'Telegram notification could not be delivered; the failure remains recorded here.'
  if (status === 'pending') return 'Telegram notification is being delivered through the existing PTW bot.'
  return 'This attempt predates audited Telegram failure notifications.'
}

function AuthenticatedImage({ api, creative }: { api: ApiClient; creative: AdCreative }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    let objectUrl = ''
    setUrl(''); setError('')
    void api.image(creative.image.url, creative.image.mime_type, creative.image.sha256).then((blob) => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl)
    }).catch((cause: Error) => { if (active) setError(cause.message) })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, creative.creative_id, creative.image.url, creative.image.mime_type, creative.image.sha256, retry])
  const decodeFailure = () => {
    setUrl('')
    setError('Authenticated image bytes passed transport checks, but this browser could not decode them.')
  }
  if (error) return <div className="creative-image-fallback" role="alert"><ImageIcon /><strong>Creative image unavailable</strong><span>{error}</span><small>Creative {creative.creative_id}</small><button className="secondary" onClick={() => setRetry((value) => value + 1)}>Retry image</button></div>
  if (!url) return <div className="creative-image-fallback"><RefreshCcw className="spin" /><span>Loading authenticated image…</span></div>
  return <img src={url} alt={creative.image.alt || creative.image_description} onError={decodeFailure} />
}

function CreativeCard({ api, creative, onNotice }: {
  api: ApiClient; creative: AdCreative; onNotice: (message: string) => void
}) {
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async () => {
    if (!feedback.trim()) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ feedback_id: string; weight_update_id: string; proposal_id: string }>(`/api/v1/ad-creatives/${creative.creative_id}/feedback`, { comment: feedback.trim() })
      setFeedback(''); onNotice(`Feedback ${result.feedback_id} saved; lesson proposal ${result.proposal_id} was appended to the pending combined lesson.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  return <article className="panel creative-card">
    <div className="creative-art"><AuthenticatedImage api={api} creative={creative} /></div>
    <div className="creative-copy"><small>{String(creative.ordinal + 1).padStart(2, '0')} · {angleNames[creative.angle]}</small><h2>{creative.hook}</h2><p>{creative.primary_text}</p><p className="creative-offer">Offer · {creative.offer}</p><p className="creative-cta">CTA · {creative.cta}</p>
      <p className="pexels-credit"><a href={creative.image.source_url} target="_blank" rel="noreferrer">Photo</a> by <a href={creative.image.photographer_url} target="_blank" rel="noreferrer">{creative.image.photographer}</a> on <a href="https://www.pexels.com" target="_blank" rel="noreferrer">Pexels</a></p>
      <details><summary>Creative metadata</summary><dl><dt>Creative UUID</dt><dd>{creative.creative_id}</dd><dt>Brief UUID</dt><dd>{creative.brief_id}</dd><dt>Asset UUID</dt><dd>{creative.image.asset_id}</dd><dt>Emotion</dt><dd>{creative.desired_emotion}</dd><dt>Image category</dt><dd>{creative.image_category}</dd><dt>Crop</dt><dd>{creative.crop_focus}</dd><dt>SHA-256</dt><dd>{creative.image.sha256}</dd><dt>License</dt><dd><a href={creative.image.license_url} target="_blank" rel="noreferrer">{creative.image.license}</a></dd></dl></details>
      <div className="creative-feedback"><label>Feedback for this complete creative<textarea rows={3} maxLength={2000} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="What should future creatives learn?" /></label><button className="secondary" disabled={busy || !feedback.trim()} onClick={submit}>Save feedback <Send /></button>{error && <p role="alert">{error}</p>}</div>
    </div>
  </article>
}

export function AdsView({ api }: { api: ApiClient }) {
  const [items, setItems] = useState<CreativeBatch[] | null>(null)
  const [selected, setSelected] = useState<CreativeBatch | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [proposalRevision, setProposalRevision] = useState(0)
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
  const failure = selected?.status === 'failed' ? batchFailureReason(selected) : null
  const recoveredFailure = selected?.status === 'completed' && selected.last_failed_attempt
    ? batchFailureReason(selected, true)
    : null
  if (!items) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="STAGE 2 · COMPLETE AD POSTS" title="Ads" />
    {error && <ErrorState message={error} />}{notice && <p className="landing-notice" role="status">{notice}</p>}
    {!items.length ? <Empty><Megaphone className="empty-mark" /><h2>No creative batch yet</h2><p>Approve a completed Product Brief to generate exactly five complete Ad Creatives.</p></Empty> : <div className="ads-workspace">
      <section className="panel"><label>Creative batch<select value={selected?.batch_id || ''} onChange={(event) => void load(event.target.value)}>{items.map((item) => <option key={item.batch_id} value={item.batch_id}>{item.batch_id} · {item.status}</option>)}</select></label>{selected && <p className="uuid-line">Brief {selected.brief_id} · batch {selected.batch_id}</p>}</section>
      {selected && ['queued', 'generating'].includes(selected.status) && <section className="panel generation-state"><RefreshCcw className="spin" /><div><h2>Building five creatives</h2><p>One structured call, fixed angles, real Pexels photos, deterministic 1080×1080 renders.</p></div></section>}
      {selected?.status === 'failed' && failure && <section className="panel batch-failure" role="alert">
        <header><AlertTriangle /><div><small>FAILED AT VALIDATION · {selected.error_code || 'GenerationError'}</small><h2>{failure.title}</h2></div></header>
        <dl>
          <dt>Reason</dt><dd>{failure.explanation}</dd>
          <dt>Recorded detail</dt><dd><code>{failure.detail}</code></dd>
          <dt>Safety outcome</dt><dd><ShieldCheck /> The batch is atomic: no partial creatives or images were saved.</dd>
          <dt>Telegram</dt><dd><Bell /> {notificationText(selected)}</dd>
        </dl>
        <button className="secondary" disabled={busy} onClick={retry}>{busy ? 'Retrying…' : 'Retry entire batch'}</button>
      </section>}
      {selected?.status === 'completed' && recoveredFailure && <section className="panel batch-recovery" role="status">
        <header><ShieldCheck /><div><small>RECOVERED AFTER RETRY</small><h2>Batch completed after an earlier failure</h2></div></header>
        <p>{recoveredFailure.explanation}</p>
        <details><summary>Previous attempt details</summary><p><code>{recoveredFailure.detail}</code></p><p>{notificationText(selected)}</p></details>
      </section>}
      {selected?.status === 'completed' && <><section className="creative-grid">{selected.creatives.map((creative) => <CreativeCard key={creative.creative_id} api={api} creative={creative} onNotice={(message) => { setNotice(message); setProposalRevision((value) => value + 1) }} />)}</section><OwnerLessonProposals api={api} domain="ad_creative" refreshKey={proposalRevision} /></>}
    </div>}
  </>
}
