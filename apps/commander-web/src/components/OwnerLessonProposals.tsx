import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import type { ValidationSkillProposal } from '../types'

type LessonDomain = 'product_brief' | 'ad_creative'

const labels: Record<LessonDomain, { heading: string; scope: string }> = {
  product_brief: { heading: 'Owner lesson proposals', scope: 'Product Brief' },
  ad_creative: { heading: 'Owner lesson proposals', scope: 'Ad Creative' },
}

export function OwnerLessonProposals({ api, domain, refreshKey = 0 }: {
  api: ApiClient
  domain: LessonDomain
  refreshKey?: string | number
}) {
  const [proposals, setProposals] = useState<ValidationSkillProposal[]>([])
  const [lesson, setLesson] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async () => {
    const result = await api.get<{ items: ValidationSkillProposal[] }>(`/api/v1/skill-proposals/${domain}`)
    setProposals(result.items)
    setLesson(result.items.filter((item) => item.status === 'pending').map((item) => item.lesson.trim()).filter(Boolean).join('\n'))
  }
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [api, domain, refreshKey])

  const pending = proposals.filter((item) => item.status === 'pending')
  const plan = async () => {
    const normalized = lesson.trim()
    if (!pending.length || !normalized || normalized.length > 4000) return
    setBusy(true); setError(''); setNotice('')
    try {
      await api.post(`/api/v1/skill-proposals/${domain}/plan`, {
        proposal_ids: pending.map((item) => item.proposal_id), lesson: normalized,
      })
      setNotice('One combined lesson plan was created. Review and approve it in Admin → Jobs.')
      await load()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!proposals.length) return null
  const label = labels[domain]
  return <section className="lesson-proposals">
    <h3>{label.heading}</h3>
    <p>Pending feedback is appended into one editable {label.scope} lesson and sent through one owner-gated plan.</p>
    {pending.length ? <article>
      <textarea rows={Math.min(8, Math.max(3, pending.length * 2))} maxLength={4000} disabled={busy} value={lesson} onChange={(event) => setLesson(event.target.value)} />
      <small>{pending.length} pending feedback {pending.length === 1 ? 'item' : 'items'} · {pending.map((item) => item.proposal_id).join(' · ')}</small>
      <div><button className="secondary" disabled={busy || !lesson.trim() || lesson.trim().length > 4000} onClick={() => void plan()}>{busy ? 'Planning…' : 'Plan combined lesson'}</button></div>
    </article> : <p>No pending feedback lessons.</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    <details><summary>Proposal history ({proposals.length})</summary><ul>{proposals.map((proposal) => <li key={proposal.proposal_id}><code>{proposal.proposal_id}</code> · {proposal.status}</li>)}</ul></details>
  </section>
}
