import { Check, Download, RefreshCcw, Send, Sparkles, Target } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { EvidenceStatement, PositioningCatalog, PositioningDocument, PositioningProject, PositioningRevision, SkillProposal } from '../types'

const sections = ['positioning_foundation', 'messaging_matrix', 'landing_copy', 'ad_concepts', 'aeo_faqs'] as const
const activeStatuses = new Set(['queued', 'researching', 'synthesizing'])

function Claim({ value }: { value: EvidenceStatement }) {
  return <span className="evidence-claim">{value.text}<small>{value.source_ids.length ? `${value.source_ids.length} source${value.source_ids.length === 1 ? '' : 's'}` : 'ASSUMPTION'}</small></span>
}

function DocumentView({ document }: { document: PositioningDocument }) {
  const foundation = document.positioning_foundation
  return <div className="positioning-document">
    <section><small>01 · POSITIONING FOUNDATION</small><h2><Claim value={foundation.uvp} /></h2>
      <dl><dt>Category</dt><dd><Claim value={foundation.category} /></dd><dt>Audience</dt><dd><Claim value={foundation.definitive_audience} /></dd></dl>
      <div className="positioning-columns"><div><h3>Alternatives</h3>{foundation.competitive_alternatives.map((item, index) => <p key={index}><Claim value={item} /></p>)}</div><div><h3>Jobs / pains / gains</h3>{[...foundation.jobs, ...foundation.pains, ...foundation.gains].map((item, index) => <p key={index}><Claim value={item} /></p>)}</div></div>
    </section>
    <section><small>02 · LAYERED MESSAGING</small><div className="matrix-table">{document.messaging_matrix.map((row, index) => <article key={index}><Claim value={row.feature} /><span>→</span><Claim value={row.functional_benefit} /><span>→</span><Claim value={row.emotional_reward} /></article>)}</div></section>
    <section><small>03 · LANDING COPY</small><h2><Claim value={document.landing_copy.hero.headline} /></h2><p><Claim value={document.landing_copy.hero.subheadline} /></p>{document.landing_copy.value_sections.map((item, index) => <article key={index}><h3><Claim value={item.title} /></h3><p><Claim value={item.body} /></p></article>)}<p className="honest-limit"><Claim value={document.landing_copy.honest_limitation} /></p></section>
    <section><small>04 · AD CONCEPTS</small>{document.ad_concepts.map((item) => <article key={item.kind}><h3>{item.kind === 'contextual_relatable' ? 'Contextual & relatable' : 'Direct problem–solution'}</h3><p><Claim value={item.hook} /></p><p><Claim value={item.body} /></p><small>Visual: <Claim value={item.visual_direction} /></small></article>)}</section>
    <section><small>05 · AEO FAQ</small>{document.aeo_faqs.map((item, index) => <details key={index}><summary>{item.question.text}</summary><p>{item.definition.text} {item.data.text} {item.context.text}</p></details>)}</section>
  </div>
}

export function PositioningView({ api }: { api: ApiClient }) {
  const [catalog, setCatalog] = useState<PositioningCatalog | null>(null)
  const [projects, setProjects] = useState<PositioningProject[] | null>(null)
  const [project, setProject] = useState<PositioningProject | null>(null)
  const [rawIdea, setRawIdea] = useState('')
  const [country, setCountry] = useState('US')
  const [researchLanguage, setResearchLanguage] = useState('en')
  const [outputLanguage, setOutputLanguage] = useState<'uk' | 'en'>('uk')
  const [section, setSection] = useState<typeof sections[number]>('positioning_foundation')
  const [instruction, setInstruction] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [proposals, setProposals] = useState<SkillProposal[]>([])
  const [proposalLessons, setProposalLessons] = useState<Record<string, string>>({})

  const setProposalState = (items: SkillProposal[]) => {
    setProposals(items)
    setProposalLessons(Object.fromEntries(items.map((item) => [item.id, item.lesson])))
  }

  const load = async () => {
    const [catalogData, projectData] = await Promise.all([
      api.get<PositioningCatalog>('/api/v1/positionings/catalog'),
      api.get<{ items: PositioningProject[] }>('/api/v1/positionings?limit=100'),
    ])
    setCatalog(catalogData); setProjects(projectData.items)
    if (!project && projectData.items[0]) await refreshProject(projectData.items[0].id)
  }
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [api])
  const selectedId = project?.id
  const refreshProject = async (id = selectedId) => {
    if (!id) return
    const [detail, proposalData] = await Promise.all([
      api.get<PositioningProject>(`/api/v1/positionings/${id}`),
      api.get<{ items: SkillProposal[] }>(`/api/v1/positionings/${id}/skill-proposals`),
    ])
    setProject(detail)
    setProposalState(proposalData.items)
    setProjects((items) => (items || []).map((item) => item.id === id ? { ...item, active_approved_revision_id: detail.active_approved_revision_id, latest_revision_id: detail.revisions?.[0]?.id, latest_revision_status: detail.revisions?.[0]?.status } : item))
  }
  const latest = project?.revisions?.[0] || null
  const active = Boolean(latest && activeStatuses.has(latest.status))
  useEffect(() => {
    if (!active || !selectedId) return
    const timer = window.setInterval(() => void refreshProject(selectedId).catch((cause: Error) => setError(cause.message)), 1600)
    return () => window.clearInterval(timer)
  }, [active, selectedId])

  const create = async () => {
    if (!rawIdea.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ project: PositioningProject }>('/api/v1/positionings', {
        request_id: crypto.randomUUID(), raw_idea: rawIdea,
        target_country: country, research_language: researchLanguage, output_language: outputLanguage,
      })
      setProject(result.project); setRawIdea(''); setNotice('Positioning synthesis started from your idea. Unsupported market conclusions will be marked as assumptions.'); await load()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const correct = async () => {
    if (!project || !latest?.document || !instruction.trim()) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/positionings/${project.id}/revisions`, {
        request_id: crypto.randomUUID(), base_revision_id: latest.id, section_id: section, instruction,
      })
      setInstruction(''); setNotice('Focused correction saved; a complete coherent replacement revision is being created.'); await refreshProject(project.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async (revision: PositioningRevision) => {
    setBusy(true); setError('')
    try { await api.post(`/api/v1/positioning-revisions/${revision.id}/approve`, {}); await refreshProject(revision.project_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retry = async (revision: PositioningRevision) => {
    setBusy(true); setError('')
    try { await api.post(`/api/v1/positioning-revisions/${revision.id}/retry`, {}); await refreshProject(revision.project_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const download = async (revision: PositioningRevision) => {
    const blob = await api.blob(`/api/v1/positioning-revisions/${revision.id}/export.md`)
    const url = URL.createObjectURL(blob); const link = document.createElement('a')
    link.href = url; link.download = `positioning-${revision.id}.md`; link.click(); URL.revokeObjectURL(url)
  }
  const updateProposal = async (proposal: SkillProposal) => {
    const lesson = (proposalLessons[proposal.id] || '').trim()
    if (!lesson) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/positioning-skill-proposals/${proposal.id}/update`, { lesson })
      await refreshProject(project?.id)
      setNotice('Generalized lesson updated. It is still pending owner promotion.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const planProposal = async (proposal: SkillProposal) => {
    const lesson = (proposalLessons[proposal.id] || '').trim()
    if (!lesson) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/positioning-skill-proposals/${proposal.id}/plan`, { lesson })
      await refreshProject(project?.id)
      setNotice('A bounded read-only plan was opened for the Marketing Positioning owner lesson.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const dismissProposal = async (proposal: SkillProposal) => {
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/positioning-skill-proposals/${proposal.id}/dismiss`, {})
      await refreshProject(project?.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!catalog || !projects) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="MARKETING POSITIONING" title="Позиціонування" />
    {error && <ErrorState message={error} />}{notice && <p className="landing-notice" role="status">{notice}</p>}
    <section className="panel positioning-create"><div><small>NEW PROJECT</small><h2>Start from the raw idea</h2><p>Changing the idea or market creates another project; source history is never rewritten.</p></div>
      <textarea rows={6} maxLength={10000} value={rawIdea} onChange={(event) => setRawIdea(event.target.value)} placeholder="Describe the product idea, intended user, and what is actually known…" />
      <div className="positioning-controls"><label>Market<select value={country} onChange={(event) => setCountry(event.target.value)}>{catalog.countries.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label><label>Market language<select value={researchLanguage} onChange={(event) => setResearchLanguage(event.target.value)}>{catalog.research_languages.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label><label>Output<select value={outputLanguage} onChange={(event) => setOutputLanguage(event.target.value as 'uk' | 'en')}><option value="uk">Українська</option><option value="en">English</option></select></label></div>
      <button className="primary large" disabled={busy || active || !rawIdea.trim()} onClick={create}><Sparkles />Build positioning</button>
    </section>
    {!projects.length ? <Empty><Target className="empty-mark" /><h2>No positioning yet</h2><p>Create the first project above. Production stays empty until you do.</p></Empty> : <div className="positioning-workspace">
      <aside className="panel positioning-list"><small>PROJECTS</small>{projects.map((item) => <button key={item.id} className={project?.id === item.id ? 'selected' : ''} onClick={() => void refreshProject(item.id)}><strong>{item.raw_idea.slice(0, 90)}</strong><span>{item.target_country} · {item.output_language.toUpperCase()} · {item.active_approved_revision_id ? 'approved' : item.latest_revision_status}</span></button>)}</aside>
      <div>{project && <section className="panel positioning-detail"><small>PROJECT {project.id}</small><h2>{project.raw_idea}</h2><p>{project.target_country} · market language {project.research_language} · output {project.output_language}</p>
        {latest && <div className={`revision-state ${latest.status}`}><div><strong>Revision {latest.revision_number} · {latest.status}</strong>{latest.document_sha256 && <code>{latest.document_sha256.slice(0, 16)}…</code>}{latest.error_message && <p>{latest.error_message}</p>}</div><div>{latest.status === 'completed' && !latest.approved && <button className="primary" disabled={busy} onClick={() => approve(latest)}><Check />Approve for Landing & Ads</button>}{latest.status === 'failed' && <button className="secondary" disabled={busy} onClick={() => retry(latest)}><RefreshCcw />Retry</button>}{latest.document && <button className="secondary" onClick={() => void download(latest)}><Download />Markdown</button>}</div></div>}
        {latest?.document && <><DocumentView document={latest.document} /><section className="positioning-correction"><h2>Focused correction</h2><select value={section} onChange={(event) => setSection(event.target.value as typeof section)}>{sections.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select><textarea rows={4} maxLength={2000} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="One correction for this section…" /><button className="secondary" disabled={busy || active || !instruction.trim()} onClick={correct}>Create complete revision <Send /></button></section></>}
        <details className="positioning-sources"><summary>Sources ({project.sources?.length || 0})</summary>{project.sources?.map((source) => <article key={source.id}><small>{source.id} · {source.provider}</small><h3>{source.title}</h3><p>{source.content.slice(0, 700)}</p>{source.source_uri && <a href={source.source_uri} target="_blank" rel="noreferrer">Open source</a>}</article>)}</details>
        {!!proposals.length && <section className="skill-proposals"><h2>Owner lesson proposals</h2><p>Corrections become editable generalized lessons. Promotion first creates a bounded Plan and can update only the Positioning owner-lessons reference.</p>{proposals.map((proposal) => <article key={proposal.id}><small>{proposal.status} · feedback {proposal.feedback_id}</small><textarea rows={3} maxLength={500} disabled={proposal.status !== 'pending'} value={proposalLessons[proposal.id] || ''} onChange={(event) => setProposalLessons((items) => ({ ...items, [proposal.id]: event.target.value }))} />{proposal.command_session_id && <p>Plan {proposal.command_session_id}</p>}{proposal.status === 'pending' && <div><button className="secondary" disabled={busy} onClick={() => updateProposal(proposal)}>Save edit</button><button className="primary" disabled={busy || !(proposalLessons[proposal.id] || '').trim()} onClick={() => planProposal(proposal)}>Plan promotion</button><button className="secondary" disabled={busy} onClick={() => dismissProposal(proposal)}>Dismiss</button></div>}</article>)}</section>}
      </section>}</div>
    </div>}
  </>
}
