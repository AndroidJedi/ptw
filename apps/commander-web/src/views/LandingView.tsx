import {
  ArrowRight, Check, ExternalLink, History, LayoutTemplate, LoaderCircle,
  MessageSquareText, Monitor, RotateCcw, Smartphone, Sparkles, TriangleAlert,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { local, type Language } from '../i18n'
import type {
  LandingBlockEdit, LandingBlockId, LandingBuild, LandingCandidate, LandingDraftPreview,
  LandingDraftSet, LandingSkillProposal, LandingTemplate,
} from '../types'

const blockIds: LandingBlockId[] = ['hero', 'problem', 'features', 'steps', 'proof', 'faq', 'final_cta']
const activeBuildStatuses = new Set(['queued', 'revising', 'building', 'publishing'])
const activeEditStatuses = new Set(['queued', 'editing'])
const blockLabels: Record<LandingBlockId, string> = {
  hero: 'Hero', problem: 'Проблема', features: 'Переваги', steps: 'Кроки',
  proof: 'Докази', faq: 'FAQ', final_cta: 'Фінальний CTA',
}

function buildLabel(status: LandingBuild['status']) {
  return ({
    queued: 'Публікацію поставлено в чергу', revising: 'Natal builder застосовує памʼять',
    building: 'Збираємо точний snapshot', publishing: 'Публікуємо у Firebase',
    published: 'Версію опубліковано', failed: 'Публікація не завершилась',
  } as Record<LandingBuild['status'], string>)[status]
}

function editLabel(status: LandingBlockEdit['status']) {
  return ({ queued: 'У черзі', editing: 'Agent редагує блок', completed: 'Застосовано', failed: 'Не застосовано' })[status]
}

function upsertBuild(items: LandingBuild[], incoming: LandingBuild) {
  return [incoming, ...items.filter((item) => item.id !== incoming.id)]
}

export function LandingView({ api, language }: { api: ApiClient; language: Language }) {
  const [templates, setTemplates] = useState<LandingTemplate[] | null>(null)
  const [candidates, setCandidates] = useState<LandingCandidate[] | null>(null)
  const [builds, setBuilds] = useState<LandingBuild[] | null>(null)
  const [selectedRun, setSelectedRun] = useState('')
  const [templateId, setTemplateId] = useState<LandingTemplate['id']>('product')
  const [draftSet, setDraftSet] = useState<LandingDraftSet | null>(null)
  const [preview, setPreview] = useState<LandingDraftPreview | null>(null)
  const [selectedBlock, setSelectedBlock] = useState<LandingBlockId>('hero')
  const [instruction, setInstruction] = useState('')
  const [device, setDevice] = useState<'mobile' | 'desktop'>('desktop')
  const [proposals, setProposals] = useState<LandingSkillProposal[]>([])
  const [proposalLessons, setProposalLessons] = useState<Record<string, string>>({})
  const [visibleBuildId, setVisibleBuildId] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const load = () => {
    setError('')
    Promise.all([
      api.get<{ items: LandingTemplate[] }>('/api/v1/landings/templates'),
      api.get<{ items: LandingCandidate[] }>('/api/v1/landings/candidates?limit=30'),
      api.get<{ items: LandingBuild[] }>('/api/v1/landings/builds?limit=100'),
    ]).then(([templateData, candidateData, buildData]) => {
      setTemplates(templateData.items)
      setCandidates(candidateData.items)
      setBuilds(buildData.items)
      setSelectedRun((current) => current || candidateData.items[0]?.idea_run_id || '')
    }).catch((cause: Error) => setError(cause.message))
  }

  useEffect(() => { load() }, [api])

  const selected = useMemo(
    () => candidates?.find((item) => item.idea_run_id === selectedRun) || null,
    [candidates, selectedRun],
  )
  const ideaBuilds = useMemo(
    () => (builds || []).filter((item) => item.idea_run_id === selectedRun),
    [builds, selectedRun],
  )
  const visibleBuild = useMemo(
    () => ideaBuilds.find((item) => item.id === visibleBuildId) || ideaBuilds[0] || null,
    [ideaBuilds, visibleBuildId],
  )
  const activeBuild = builds?.find((item) => activeBuildStatuses.has(item.status)) || null
  const snapshot = draftSet?.variants.find((item) => item.template_id === templateId) || null
  const activeEdit = draftSet?.edits.find((item) => activeEditStatuses.has(item.status)) || null
  const proposalRefreshKey = draftSet?.edits
    .map((item) => `${item.request_id}:${item.status}`)
    .join('|') || ''

  useEffect(() => {
    if (!selected) return
    let current = true
    setTemplateId(selected.recommended_template_id)
    setSelectedBlock('hero')
    setInstruction('')
    setDraftSet(null)
    setPreview(null)
    setProposals([])
    setNotice('')
    api.get<LandingDraftSet>(`/api/v1/landings/draft-sets/latest?idea_run_id=${selected.idea_run_id}`)
      .then((result) => { if (current) setDraftSet(result) })
      .catch((cause: Error) => {
        if (current && !cause.message.toLowerCase().includes('not found')) setError(cause.message)
      })
    return () => { current = false }
  }, [api, selected?.idea_run_id])

  const draftActive = draftSet?.status === 'queued' || draftSet?.status === 'populating' || Boolean(activeEdit)
  useEffect(() => {
    if (!draftSet || !draftActive) return
    let current = true
    const refresh = async () => {
      try {
        const updated = await api.get<LandingDraftSet>(`/api/v1/landings/draft-sets/${draftSet.id}`)
        if (current) setDraftSet(updated)
      } catch (cause) {
        if (current) setError((cause as Error).message)
      }
    }
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 1500)
    return () => { current = false; window.clearInterval(timer) }
  }, [api, draftSet?.id, draftActive])

  useEffect(() => {
    if (!snapshot) { setPreview(null); return }
    let current = true
    setPreview(null)
    api.get<LandingDraftPreview>(`/api/v1/landings/draft-snapshots/${snapshot.id}/preview`)
      .then((result) => { if (current) setPreview(result) })
      .catch((cause: Error) => { if (current) setError(cause.message) })
    return () => { current = false }
  }, [api, snapshot?.id])

  useEffect(() => {
    if (!draftSet) return
    let current = true
    api.get<{ items: LandingSkillProposal[] }>(`/api/v1/landings/skill-proposals?draft_set_id=${draftSet.id}`)
      .then((result) => {
        if (!current) return
        setProposals(result.items)
        setProposalLessons((values) => Object.fromEntries(result.items.map((item) => [
          item.id, values[item.id] ?? item.reviewed_lesson ?? item.proposed_lesson ?? '',
        ])))
      })
      .catch((cause: Error) => { if (current) setError(cause.message) })
    return () => { current = false }
  }, [api, draftSet?.id, proposalRefreshKey])

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return
      const payload = event.data as { type?: unknown; templateId?: unknown; blockId?: unknown } | null
      if (!payload || payload.type !== 'natal.select-block' || payload.templateId !== templateId) return
      if (!blockIds.includes(payload.blockId as LandingBlockId)) return
      setSelectedBlock(payload.blockId as LandingBlockId)
    }
    window.addEventListener('message', receive)
    return () => window.removeEventListener('message', receive)
  }, [templateId, preview?.snapshot_id])

  useEffect(() => {
    if (!visibleBuild || !activeBuildStatuses.has(visibleBuild.status)) return
    let current = true
    const refresh = async () => {
      try {
        const updated = await api.get<LandingBuild>(`/api/v1/landings/builds/${visibleBuild.id}`)
        if (current) setBuilds((items) => upsertBuild(items || [], updated))
      } catch (cause) {
        if (current) setError((cause as Error).message)
      }
    }
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 1500)
    return () => { current = false; window.clearInterval(timer) }
  }, [api, visibleBuild?.id, visibleBuild?.status])

  const populate = async () => {
    if (!selected) return
    setBusy(true); setError(''); setNotice('')
    try {
      const created = await api.post<LandingDraftSet>('/api/v1/landings/draft-sets', {
        request_id: window.crypto.randomUUID(), idea_run_id: selected.idea_run_id,
      })
      setDraftSet(created)
      setNotice('Один agent turn запущено для product, community і waitlist. Чернетки залишаються приватними.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryPopulation = async () => {
    if (!draftSet) return
    setBusy(true); setError(''); setNotice('')
    try {
      setDraftSet(await api.post<LandingDraftSet>(`/api/v1/landings/draft-sets/${draftSet.id}/retry`, {}))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const applyEdit = async () => {
    if (!snapshot || !instruction.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const edit = await api.post<LandingBlockEdit>(`/api/v1/landings/draft-snapshots/${snapshot.id}/edits`, {
        request_id: window.crypto.randomUUID(), block_id: selectedBlock, instruction,
      })
      setDraftSet((current) => current ? {
        ...current, edits: [edit, ...current.edits.filter((item) => item.request_id !== edit.request_id)],
      } : current)
      setInstruction('')
      setNotice(`Коментар до ${blockLabels[selectedBlock]} збережено одразу. Agent редагує лише цей блок.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryEdit = async (edit: LandingBlockEdit) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const updated = await api.post<LandingBlockEdit>(`/api/v1/landings/draft-edits/${edit.request_id}/retry`, {})
      setDraftSet((current) => current ? {
        ...current, edits: current.edits.map((item) => item.request_id === updated.request_id ? updated : item),
      } : current)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const publish = async () => {
    if (!snapshot) return
    setBusy(true); setError(''); setNotice('')
    try {
      const parent = ideaBuilds.find((item) => item.status === 'published')
      const created = await api.post<LandingBuild>('/api/v1/landings/builds', {
        request_id: window.crypto.randomUUID(), draft_snapshot_id: snapshot.id,
        parent_build_id: parent?.id,
      })
      setBuilds((items) => upsertBuild(items || [], created))
      setVisibleBuildId(created.id)
      setNotice(`Snapshot ${snapshot.snapshot_number} (${templateId}) передано на явну публікацію без повторного rewrite.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryBuild = async (build: LandingBuild) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const updated = await api.post<LandingBuild>(`/api/v1/landings/builds/${build.id}/retry`, {})
      setBuilds((items) => upsertBuild(items || [], updated))
      setVisibleBuildId(updated.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const dismissProposal = async (proposal: LandingSkillProposal) => {
    setBusy(true); setError('')
    try {
      const updated = await api.post<LandingSkillProposal>(`/api/v1/landings/skill-proposals/${proposal.id}/dismiss`, {})
      setProposals((items) => items.map((item) => item.id === updated.id ? updated : item))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const promoteProposal = async (proposal: LandingSkillProposal) => {
    const lesson = (proposalLessons[proposal.id] || '').trim()
    if (!lesson) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ proposal: LandingSkillProposal }>(`/api/v1/landings/skill-proposals/${proposal.id}/plan`, { lesson })
      setProposals((items) => items.map((item) => item.id === result.proposal.id ? result.proposal : item))
      setNotice('Створено обмежений Plan: лише owner-lessons.md і перевірка skill. Browser не змінює Git напряму.')
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!templates || !candidates || !builds) return error ? <ErrorState message={error} retry={load} /> : <Loading />
  return <>
    <PageHeader eyebrow="NATAL LANDING WORKSPACE" title="Лендинги" />
    {error && <ErrorState message={error} retry={load} />}
    {notice && <p className="landing-notice" role="status">{notice}</p>}
    {!candidates.length ? <Empty><LayoutTemplate className="empty-mark" /><h2>Немає завершених оцінок</h2><p>Завершіть Idea Laval evaluation, щоб створити landing workspace.</p></Empty> : <div className="landing-workbench">
      <section className="landing-source panel">
        <div className="landing-section-head"><div><small>01 · ДЖЕРЕЛО</small><h2>Приватний draft workspace</h2></div><Check aria-hidden="true" /></div>
        <label htmlFor="landing-candidate">Завершена Idea Laval оцінка</label>
        <select id="landing-candidate" value={selectedRun} onChange={(event) => setSelectedRun(event.target.value)}>
          {candidates.map((item) => <option key={item.idea_run_id} value={item.idea_run_id}>{item.brief.business_idea}</option>)}
        </select>
        <p>Одна дія заповнює всі три фіксовані шаблони. Firebase не викликається, доки ви явно не опублікуєте обраний snapshot.</p>
        {selected && <details><summary>Джерело й якість</summary><p>RUN {selected.idea_run_id} · THESIS {selected.brief.source.thesis_id || 'немає'} · verdict {selected.verdict || 'not available'} · model {selected.quality.successful || 0}/{selected.quality.attempted || 0}</p></details>}
        {!draftSet && <button className="primary large" disabled={busy || Boolean(activeBuild)} onClick={populate}>Заповнити три превʼю <Sparkles aria-hidden="true" /></button>}
      </section>

      {draftSet && <section className={`landing-draft-state ${draftSet.status}`} role="status">
        {draftSet.status === 'queued' || draftSet.status === 'populating' ? <LoaderCircle className="spin" aria-hidden="true" /> : draftSet.status === 'failed' ? <TriangleAlert aria-hidden="true" /> : <Check aria-hidden="true" />}
        <div><small>DRAFT SET {draftSet.id}</small><h2>{draftSet.status === 'ready' ? 'Три приватні превʼю готові' : draftSet.status === 'failed' ? 'Заповнення не завершилось' : 'Agent заповнює три шаблони одним turn'}</h2><p>{draftSet.population_summary || draftSet.error_message || 'Прогрес збережено; можна безпечно оновити сторінку.'}</p></div>
        {draftSet.status === 'failed' && <button className="secondary" disabled={busy} onClick={retryPopulation}>Повторити <RotateCcw aria-hidden="true" /></button>}
      </section>}

      {draftSet?.variants.length ? <>
        <section className="landing-templates panel">
          <div className="landing-section-head"><div><small>02 · ВАРІАНТИ</small><h2>Перемикайте без фіксації вибору</h2></div><Sparkles aria-hidden="true" /></div>
          <div className="landing-template-grid" role="tablist" aria-label="Шаблон лендингу">
            {templates.map((template) => <button key={template.id} role="tab" aria-selected={templateId === template.id} className={templateId === template.id ? 'selected' : ''} onClick={() => { setTemplateId(template.id); setSelectedBlock('hero'); setInstruction('') }}>
              <span>{draftSet.recommended_template_id === template.id ? 'РЕКОМЕНДОВАНО · НЕ ЗАФІКСОВАНО' : template.id.toUpperCase()}</span>
              <strong>{String(local(template.name, language))}</strong>
              <p>{String(local(template.description, language))}</p>
              <small>Snapshot {draftSet.variants.find((item) => item.template_id === template.id)?.snapshot_number || 1}</small>
            </button>)}
          </div>
        </section>

        <section className="landing-preview-workbench panel">
          <div className="landing-section-head"><div><small>03 · ПРИВАТНЕ SRCDOC ПРЕВʼЮ</small><h2>{templateId} · snapshot {snapshot?.snapshot_number}</h2></div><LayoutTemplate aria-hidden="true" /></div>
          <p className="landing-brand-lock">Natal assets, UI kit, CTA destination, source IDs і перевірені докази захищені. Інструкція змінює лише вибраний content block.</p>
          <div className="landing-device-toggle" aria-label="Ширина превʼю">
            <button aria-pressed={device === 'mobile'} onClick={() => setDevice('mobile')}><Smartphone aria-hidden="true" />360 px</button>
            <button aria-pressed={device === 'desktop'} onClick={() => setDevice('desktop')}><Monitor aria-hidden="true" />Desktop</button>
          </div>
          <div className={`landing-preview-frame ${device}`}>
            {preview ? <iframe ref={iframeRef} title={`Natal ${templateId} private preview`} sandbox="allow-scripts" srcDoc={preview.html} /> : <Loading />}
          </div>
          <div className="landing-block-picker" role="group" aria-label="Блок для редагування">
            {blockIds.map((blockId) => <button key={blockId} className={selectedBlock === blockId ? 'selected' : ''} aria-pressed={selectedBlock === blockId} onClick={() => setSelectedBlock(blockId)}>{blockLabels[blockId]}</button>)}
          </div>
          <label className="landing-edit-instruction">Інструкція для блоку «{blockLabels[selectedBlock]}»
            <textarea rows={4} maxLength={2000} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Наприклад: зроби заголовок коротшим і почни з конкретного результату…" />
          </label>
          <div className="landing-preview-actions">
            <button className="secondary" disabled={busy || Boolean(activeEdit) || !instruction.trim()} onClick={applyEdit}>{activeEdit ? 'Інше редагування виконується' : 'Застосувати лише до блоку'} <MessageSquareText aria-hidden="true" /></button>
            <button className="primary" disabled={busy || Boolean(activeEdit) || Boolean(activeBuild) || !snapshot} onClick={publish}>Publish this version <ArrowRight aria-hidden="true" /></button>
          </div>
          <p className="landing-publish-note">Preview CTA неактивні. Публікація використовує точний digest цього snapshot і не викликає agent rewrite.</p>
        </section>

        <section className="landing-memory panel">
          <div className="landing-section-head"><div><small>КОМЕНТАРІ Й ПРОГРЕС</small><h2>{draftSet.edits.length ? `${draftSet.edits.length} блокових інструкцій` : 'Ще без інструкцій'}</h2></div><History aria-hidden="true" /></div>
          {draftSet.edits.length ? <ol>{draftSet.edits.map((edit) => <li key={edit.request_id}>
            <small>{edit.template_id} · {blockLabels[edit.block_id]} · {editLabel(edit.status)}</small>
            <p>{edit.instruction}</p>
            {edit.error_message && <p className="landing-build-error">{edit.error_message}</p>}
            {edit.status === 'failed' && <button className="secondary" disabled={busy || Boolean(activeEdit)} onClick={() => retryEdit(edit)}>Повторити <RotateCcw aria-hidden="true" /></button>}
          </li>)}</ol> : <p>Клікніть блок у preview або виберіть його кнопкою, а потім дайте одну сфокусовану інструкцію.</p>}
        </section>

        {proposals.length > 0 && <section className="landing-proposals panel">
          <div className="landing-section-head"><div><small>REUSABLE SKILL LESSONS</small><h2>Пропозиції для owner review</h2></div><Sparkles aria-hidden="true" /></div>
          <p>Кожен коментар уже є scoped runtime memory. Лише Promote створює обмежений Plan для канонічного owner-lessons reference.</p>
          <div className="landing-proposal-list">{proposals.map((proposal) => <article key={proposal.id}>
            <small>{proposal.template_id} · {blockLabels[proposal.block_id]} · {proposal.status}</small>
            <p>{proposal.comment}</p>
            {proposal.status === 'pending_review' && <>
              <label>Узагальнений урок<textarea rows={3} maxLength={500} value={proposalLessons[proposal.id] || ''} onChange={(event) => setProposalLessons((items) => ({ ...items, [proposal.id]: event.target.value }))} /></label>
              <div><button className="secondary" disabled={busy} onClick={() => dismissProposal(proposal)}>Відхилити</button><button className="primary" disabled={busy || !(proposalLessons[proposal.id] || '').trim()} onClick={() => promoteProposal(proposal)}>Promote через Plan</button></div>
            </>}
            {proposal.status === 'pending_generation' && <p>Agent формує редаговану пропозицію…</p>}
            {proposal.status === 'planning' && <p>Plan {proposal.command_session_id} створюється; Git ще не змінено.</p>}
          </article>)}</div>
        </section>}
      </> : null}

      {visibleBuild && <section className={`landing-build-state ${visibleBuild.status}`} role="status">
        {activeBuildStatuses.has(visibleBuild.status) ? <LoaderCircle className="spin" aria-hidden="true" /> : visibleBuild.status === 'failed' ? <TriangleAlert aria-hidden="true" /> : <Check aria-hidden="true" />}
        <div><small>LANDING REVISION {visibleBuild.revision_number} · {visibleBuild.template_id} · BUILD {visibleBuild.id}</small><h2>{buildLabel(visibleBuild.status)}</h2><p>{visibleBuild.source_draft_snapshot_id ? `Exact draft snapshot ${visibleBuild.source_draft_snapshot_id}` : 'Legacy brief build'}{visibleBuild.firebase_version ? ` · ${visibleBuild.firebase_version}` : ''}</p>{visibleBuild.error_message && <p className="landing-build-error">{visibleBuild.error_message}</p>}</div>
        {visibleBuild.status === 'published' && visibleBuild.public_url && <a className="secondary" href={visibleBuild.public_url} target="_blank" rel="noreferrer">Відкрити опубліковану версію <ExternalLink aria-hidden="true" /></a>}
        {visibleBuild.status === 'failed' && <button className="secondary" disabled={busy || Boolean(activeBuild)} onClick={() => retryBuild(visibleBuild)}>Повторити <RotateCcw aria-hidden="true" /></button>}
      </section>}

      {ideaBuilds.length > 0 && <section className="landing-history panel"><div className="landing-section-head"><div><small>ОПУБЛІКОВАНА ІСТОРІЯ</small><h2>Нумеровані immutable revisions</h2></div><History aria-hidden="true" /></div>{ideaBuilds.map((build) => <button key={build.id} className={visibleBuild?.id === build.id ? 'selected' : ''} onClick={() => setVisibleBuildId(build.id)}><span>Версія {build.revision_number} · {buildLabel(build.status)}</span><strong>{build.brief.business_idea}</strong><small>{build.template_id} · {build.id.slice(0, 8)}</small></button>)}</section>}
    </div>}
  </>
}
