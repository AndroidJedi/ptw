import { ArrowRight, Check, LayoutTemplate, MessageSquareText, Monitor, Smartphone, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { LandingBlockId, LandingBuild, LandingDraftSet, LandingEdit, LandingLead, LandingTemplate, LandingTemplateId, PositioningProject, SkillProposal } from '../types'

const blockIds: LandingBlockId[] = ['hero', 'problem', 'features', 'steps', 'proof', 'faq', 'final_cta', 'lead_form']
const blockLabels: Record<LandingBlockId, string> = {
  hero: 'Hero', problem: 'Problem', features: 'Features', steps: 'Steps', proof: 'Proof',
  faq: 'FAQ', final_cta: 'Final CTA', lead_form: 'Lead form',
}
const activeDraft = new Set(['queued', 'populating'])
const activeBuild = new Set(['queued', 'building', 'publishing'])

export function LandingView({ api }: { api: ApiClient }) {
  const [templates, setTemplates] = useState<LandingTemplate[] | null>(null)
  const [projects, setProjects] = useState<PositioningProject[] | null>(null)
  const [project, setProject] = useState<PositioningProject | null>(null)
  const [draft, setDraft] = useState<LandingDraftSet | null>(null)
  const [builds, setBuilds] = useState<LandingBuild[]>([])
  const [leads, setLeads] = useState<LandingLead[]>([])
  const [templateId, setTemplateId] = useState<LandingTemplateId>('product')
  const [preview, setPreview] = useState('')
  const [device, setDevice] = useState<'mobile' | 'desktop'>('desktop')
  const [selectedBlock, setSelectedBlock] = useState<LandingBlockId>('hero')
  const [instruction, setInstruction] = useState('')
  const [editRequest, setEditRequest] = useState<LandingEdit | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [proposals, setProposals] = useState<SkillProposal[]>([])
  const [proposalLessons, setProposalLessons] = useState<Record<string, string>>({})
  const [buildFeedback, setBuildFeedback] = useState<Record<string, string>>({})
  const iframe = useRef<HTMLIFrameElement>(null)

  const load = async () => {
    const [templateData, positioningData, buildData, leadData] = await Promise.all([
      api.get<{ items: LandingTemplate[] }>('/api/v1/landings/templates'),
      api.get<{ items: PositioningProject[] }>('/api/v1/positionings?limit=100'),
      api.get<{ items: LandingBuild[] }>('/api/v1/landings?limit=100'),
      api.get<{ items: LandingLead[] }>('/api/v1/landing-leads?limit=100'),
    ])
    const approved = positioningData.items.filter((item) => item.active_approved_revision_id)
    setTemplates(templateData.items); setProjects(approved); setBuilds(buildData.items); setLeads(leadData.items)
    if (!project && approved[0]) await selectProject(approved[0].id)
  }
  const selectProject = async (projectId: string) => {
    setError(''); setDraft(null); setPreview('')
    const detail = await api.get<PositioningProject>(`/api/v1/positionings/${projectId}`)
    setProject(detail)
    if (!detail.active_approved_revision_id) return
    try {
      const found = await api.get<LandingDraftSet>(`/api/v1/landings/draft-sets/latest?positioning_revision_id=${detail.active_approved_revision_id}`)
      setDraft(found)
    } catch (cause) {
      if (!(cause as Error).message.toLowerCase().includes('not found')) throw cause
    }
  }
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [api])
  const snapshot = draft?.current_snapshots?.[templateId] || null
  const editActive = Boolean(editRequest && ['queued', 'editing'].includes(editRequest.status))
  const projectBuilds = useMemo(() => builds.filter((item) => item.positioning_project_id === project?.id), [builds, project?.id])
  const projectLeads = useMemo(() => leads.filter((item) => projectBuilds.some((build) => build.id === item.build_id)), [leads, projectBuilds])

  useEffect(() => {
    if (!draft || !activeDraft.has(draft.status)) return
    const timer = window.setInterval(() => {
      void api.get<LandingDraftSet>(`/api/v1/landings/draft-sets/${draft.id}`).then(setDraft).catch((cause: Error) => setError(cause.message))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [api, draft?.id, draft?.status])
  useEffect(() => {
    if (!snapshot) { setPreview(''); return }
    void api.get<{ html: string }>(`/api/v1/landings/draft-snapshots/${snapshot.id}/preview`).then((value) => setPreview(value.html)).catch((cause: Error) => setError(cause.message))
  }, [api, snapshot?.id])
  useEffect(() => {
    if (!editRequest || !['queued', 'editing'].includes(editRequest.status)) return
    const timer = window.setInterval(() => {
      void api.get<LandingEdit>(`/api/v1/landings/draft-edits/${editRequest.request_id}`).then(async (value) => {
        setEditRequest(value)
        if (value.status === 'completed' && draft) {
          setDraft(await api.get<LandingDraftSet>(`/api/v1/landings/draft-sets/${draft.id}`))
          setNotice(`Only ${blockLabels[value.block_id]} changed. The superseding snapshot is now current.`)
          setEditRequest(null)
        } else if (value.status === 'failed') {
          setError(value.error_message || 'Landing block edit failed')
        }
      }).catch((cause: Error) => setError(cause.message))
    }, 900)
    return () => window.clearInterval(timer)
  }, [api, draft?.id, editRequest?.request_id, editRequest?.status])
  useEffect(() => {
    if (!draft?.id) { setProposals([]); setProposalLessons({}); return }
    void api.get<{ items: SkillProposal[] }>(`/api/v1/landings/draft-sets/${draft.id}/skill-proposals`).then((value) => {
      setProposals(value.items)
      setProposalLessons(Object.fromEntries(value.items.map((item) => [item.id, item.lesson])))
    }).catch((cause: Error) => setError(cause.message))
  }, [api, draft?.id, editRequest?.status])
  useEffect(() => {
    if (!projectBuilds.some((item) => activeBuild.has(item.status))) return
    const timer = window.setInterval(() => void load().catch((cause: Error) => setError(cause.message)), 1800)
    return () => window.clearInterval(timer)
  }, [projectBuilds.map((item) => `${item.id}:${item.status}`).join('|')])
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== iframe.current?.contentWindow) return
      const value = event.data as { type?: string; templateId?: string; blockId?: LandingBlockId }
      if (value?.type === 'natal.select-block' && value.templateId === templateId && value.blockId && blockIds.includes(value.blockId)) setSelectedBlock(value.blockId)
    }
    window.addEventListener('message', receive)
    return () => window.removeEventListener('message', receive)
  }, [templateId, snapshot?.id])

  const createDraft = async () => {
    if (!project?.active_approved_revision_id) return
    setBusy(true); setError('')
    try {
      const created = await api.post<LandingDraftSet>('/api/v1/landings/draft-sets', {
        request_id: crypto.randomUUID(), positioning_project_id: project.id,
        positioning_revision_id: project.active_approved_revision_id,
      })
      setDraft(created); setNotice('One strict agent turn is populating product, community, and waitlist. All forms remain inert in preview.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const edit = async () => {
    if (!snapshot || !instruction.trim()) return
    setBusy(true); setError('')
    try {
      const editRequest = await api.post<LandingEdit>(`/api/v1/landings/draft-snapshots/${snapshot.id}/edits`, {
        request_id: crypto.randomUUID(), block_id: selectedBlock, instruction,
      })
      setEditRequest(editRequest); setInstruction(''); setNotice(`Only ${blockLabels[selectedBlock]} is being revised.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retryDraft = async () => {
    if (!draft) return
    setBusy(true); setError('')
    try {
      const value = await api.post<LandingDraftSet>(`/api/v1/landings/draft-sets/${draft.id}/retry`, {})
      setDraft(value); setNotice('Landing population retry started.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retryEdit = async () => {
    if (!editRequest) return
    setBusy(true); setError('')
    try {
      const value = await api.post<LandingEdit>(`/api/v1/landings/draft-edits/${editRequest.request_id}/retry`, {})
      setEditRequest(value); setNotice(`Retrying only ${blockLabels[value.block_id]}.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const publish = async () => {
    if (!snapshot) return
    setBusy(true); setError('')
    try {
      const build = await api.post<LandingBuild>(`/api/v1/landings/draft-snapshots/${snapshot.id}/publish`, { request_id: crypto.randomUUID() })
      setBuilds((items) => [build, ...items]); setNotice(`Snapshot ${snapshot.snapshot_number} is publishing without another rewrite.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retryBuild = async (build: LandingBuild) => {
    setBusy(true); setError('')
    try {
      const value = await api.post<LandingBuild>(`/api/v1/landings/${build.id}/retry`, {})
      setBuilds((items) => items.map((item) => item.id === value.id ? value : item))
      setNotice(`Retrying publication of the exact ${build.template_id} snapshot.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retryNotification = async (lead: LandingLead) => {
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/landing-leads/${lead.id}/retry-notification`, {})
      const leadData = await api.get<{ items: LandingLead[] }>('/api/v1/landing-leads?limit=100')
      setLeads(leadData.items); setNotice(`Notification retry recorded for lead ${lead.id}.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const submitBuildFeedback = async (build: LandingBuild) => {
    const comment = (buildFeedback[build.id] || '').trim()
    if (!comment) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/landings/${build.id}/feedback`, { comment })
      setBuildFeedback((items) => ({ ...items, [build.id]: '' }))
      await refreshProposals(); setNotice('Published Landing feedback and its zero-delta lesson proposal were recorded.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const refreshProposals = async () => {
    if (!draft) return
    const value = await api.get<{ items: SkillProposal[] }>(`/api/v1/landings/draft-sets/${draft.id}/skill-proposals`)
    setProposals(value.items); setProposalLessons(Object.fromEntries(value.items.map((item) => [item.id, item.lesson])))
  }
  const planProposal = async (proposal: SkillProposal) => {
    const lesson = (proposalLessons[proposal.id] || '').trim()
    if (!lesson) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/landing-skill-proposals/${proposal.id}/plan`, { lesson })
      await refreshProposals(); setNotice('A bounded read-only plan was opened for the Natal Landing owner lesson.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const dismissProposal = async (proposal: SkillProposal) => {
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/landing-skill-proposals/${proposal.id}/dismiss`, {})
      await refreshProposals()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!templates || !projects) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="NATAL LANDING" title="Лендинг" />
    {error && <ErrorState message={error} />}{notice && <p className="landing-notice" role="status">{notice}</p>}
    {!projects.length ? <Empty><LayoutTemplate className="empty-mark" /><h2>No approved positioning</h2><p>Approve a completed Marketing Positioning revision first.</p></Empty> : <div className="landing-workbench">
      <section className="panel landing-source"><small>01 · APPROVED SOURCE</small><h2>Exact positioning revision</h2><select value={project?.id || ''} onChange={(event) => void selectProject(event.target.value)}>{projects.map((item) => <option key={item.id} value={item.id}>{item.raw_idea.slice(0, 100)}</option>)}</select>{project && <p>Project {project.id}<br />Revision {project.active_approved_revision_id}</p>}
        {!draft && <button className="primary large" disabled={busy} onClick={createDraft}><Sparkles />Populate three templates</button>}
      </section>
      {draft && <section className={`panel landing-draft-state ${draft.status}`}><Check /><div><small>DRAFT SET {draft.id}</small><h2>{draft.status}</h2><p>{draft.population_summary || draft.error_message || 'Durable progress is saved.'}</p>{draft.status === 'failed' && <button className="secondary" disabled={busy} onClick={retryDraft}>Retry population</button>}</div></section>}
      {draft?.status === 'completed' && snapshot && <>
        <section className="panel landing-templates"><small>02 · FIXED TEMPLATES</small><div className="landing-template-grid">{templates.map((item) => <button key={item.id} className={templateId === item.id ? 'selected' : ''} onClick={() => setTemplateId(item.id)}><strong>{item.name.uk}</strong><p>{item.description.uk}</p><small>Snapshot {draft.current_snapshots[item.id]?.snapshot_number || '—'}</small></button>)}</div></section>
        <section className="panel landing-preview-workbench"><small>03 · PRIVATE INERT PREVIEW</small><h2>{templateId} · snapshot {snapshot.snapshot_number}</h2><div className="landing-device-toggle"><button aria-pressed={device === 'mobile'} onClick={() => setDevice('mobile')}><Smartphone />360 px</button><button aria-pressed={device === 'desktop'} onClick={() => setDevice('desktop')}><Monitor />Desktop</button></div><div className={`landing-preview-frame ${device}`}>{preview ? <iframe ref={iframe} title="Private Natal preview" sandbox="allow-scripts" srcDoc={preview} /> : <Loading />}</div>
          <div className="landing-block-picker">{blockIds.map((item) => <button key={item} disabled={editActive} className={selectedBlock === item ? 'selected' : ''} onClick={() => setSelectedBlock(item)}>{blockLabels[item]}</button>)}</div><textarea rows={4} maxLength={2000} disabled={editActive} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder={`One instruction for ${blockLabels[selectedBlock]}…`} />{editRequest?.status === 'failed' && <p role="alert">{editRequest.error_message || 'Landing edit failed.'} <button className="secondary" disabled={busy} onClick={retryEdit}>Retry edit</button></p>}<div className="landing-preview-actions"><button className="secondary" disabled={busy || editActive || !instruction.trim()} onClick={edit}><MessageSquareText />Edit only this block</button><button className="primary" disabled={busy || editActive} onClick={publish}>Publish exact snapshot <ArrowRight /></button></div>
        </section>
      </>}
      <section className="panel"><small>PUBLICATIONS</small>{projectBuilds.length ? projectBuilds.map((build) => <article key={build.id}><strong>{build.template_id} · {build.status}</strong><p>{build.id}</p>{build.public_url && <a href={build.public_url} target="_blank" rel="noreferrer">Open published Landing</a>}{build.error_message && <p>{build.error_message}</p>}{build.status === 'failed' && <button className="secondary" disabled={busy} onClick={() => retryBuild(build)}>Retry exact-snapshot publication</button>}{build.status === 'published' && <div className="publication-feedback"><label>Review this published Landing<textarea rows={3} maxLength={2000} value={buildFeedback[build.id] || ''} onChange={(event) => setBuildFeedback((items) => ({ ...items, [build.id]: event.target.value }))} placeholder="What should future Natal landings learn?" /></label><button className="secondary" disabled={busy || !(buildFeedback[build.id] || '').trim()} onClick={() => submitBuildFeedback(build)}>Record feedback</button></div>}</article>) : <p>No Landing published yet.</p>}</section>
      <section className="panel"><small>LEAD HISTORY</small>{projectLeads.length ? projectLeads.map((lead) => { const notification = lead.notification_attempts.at(-1)?.status || 'pending'; return <article key={lead.id}><strong>{lead.form_id}</strong><p>{lead.id} · {lead.submitted_at}</p><p>{Object.entries(lead.fields).map(([key, value]) => `${key}: ${value}`).join(' · ')}</p><small>Notification: {notification}</small>{notification !== 'sent' && <button className="secondary" disabled={busy} onClick={() => retryNotification(lead)}>Retry notification</button>}</article> }) : <p>No leads yet.</p>}</section>
      {!!proposals.length && <section className="panel skill-proposals"><small>OWNER LESSON PROPOSALS</small><p>Edit the generalized lesson before promotion. Promotion creates a bounded Plan that can update only Natal owner lessons.</p>{proposals.map((proposal) => <article key={proposal.id}><small>{proposal.status} · feedback {proposal.feedback_id}</small><textarea rows={3} maxLength={500} disabled={proposal.status !== 'pending'} value={proposalLessons[proposal.id] || ''} onChange={(event) => setProposalLessons((items) => ({ ...items, [proposal.id]: event.target.value }))} />{proposal.command_session_id && <p>Plan {proposal.command_session_id}</p>}{proposal.status === 'pending' && <div><button className="primary" disabled={busy || !(proposalLessons[proposal.id] || '').trim()} onClick={() => planProposal(proposal)}>Plan promotion</button><button className="secondary" disabled={busy} onClick={() => dismissProposal(proposal)}>Dismiss</button></div>}</article>)}</section>}
    </div>}
  </>
}
