import { Check, Download, Pause, Play, Plus, RefreshCw, RotateCcw, ShieldAlert, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { BrandAsset, BrandCandidate, BrandDirection, BrandKit, BrandLogoRevision, BrandProject, BrandRun, BrandStatus, I18n } from '../types'
import type { Language } from '../i18n'

type Transcript = { title: string; video_url: string; transcript: string }

function text(value: unknown, language: Language): string {
  if (value && typeof value === 'object') {
    const localized = value as Partial<I18n>
    return String(localized[language] || localized.uk || localized.en || '')
  }
  return String(value || '')
}

function statusLabel(status: string) {
  return ({
    pending: 'Готується', running: 'Створюється', paused: 'Призупинено', awaiting_review: 'Ваш відгук',
    completed: 'Готово', approved: 'Схвалено', rejected: 'Відхилено', failed: 'Потрібне відновлення', cancelled: 'Скасовано', stale: 'Застаріло',
  } as Record<string, string>)[status] || status
}

function stageStatusLabel(stage: string, status: string) {
  if (stage === 'OWNER_REVIEW' && status === 'paused') return 'Чекає на ваш відгук'
  return statusLabel(status)
}

function AssetLogo({ api, asset, alt }: { api: ApiClient; asset?: BrandAsset; alt: string }) {
  const [src, setSrc] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (!asset?.url) return
    let active = true
    let objectUrl = ''
    setSrc('')
    setError('')
    void api.blob(asset.url).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (active) setSrc(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    }).catch((cause: Error) => active && setError(cause.message))
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, asset?.url])
  if (error) return <div className="brand-logo-error">Лого недоступне</div>
  return src ? <img src={src} alt={alt} /> : <div className="brand-logo-loading">PTW</div>
}

function Logo({ api, direction }: { api: ApiClient; direction: BrandDirection }) {
  return <AssetLogo api={api} asset={direction.logo_asset} alt={`Символ напряму ${direction.name}`} />
}

function requestId(prefix: string) {
  const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}:${id}`
}

function CandidateCard({ item, language, selected, onSelect }: {
  item: BrandCandidate; language: Language; selected: boolean; onSelect: () => void
}) {
  const quality = item.quality.attempted ? Math.round(item.quality.successful / item.quality.attempted * 100) : 0
  const thesis = item.theses.find((value) => value.recommended) || item.theses[0]
  return <button className={`brand-candidate brand-candidate-simple ${selected ? 'selected' : ''}`} onClick={onSelect} type="button">
    <div><span>{item.active_brand_kit ? `KIT · ${item.active_brand_kit.name}` : 'ГОТОВА ІДЕЯ'}</span><time>{new Date(item.created_at).toLocaleDateString('uk-UA')}</time></div>
    <h3>{item.owner_idea}</h3>
    {thesis && <p><b>{thesis.recommended ? '★ ' : ''}{text(thesis.title, language)}</b><br />{text(thesis.target_user, language)}</p>}
    {item.surviving_thesis_count === 0 && <p className="brand-candidate-note">Використаємо оригінальну ідею, механізми та докази.</p>}
    <footer><span>{item.theses.length} тез</span><span>Докази {quality}%</span></footer>
  </button>
}

export function BrandingView({ api, language, initialRunId }: {
  api: ApiClient; language: Language; initialRunId?: string
}) {
  const [candidates, setCandidates] = useState<BrandCandidate[] | null>(null)
  const [runs, setRuns] = useState<BrandRun[] | null>(null)
  const [projects, setProjects] = useState<BrandProject[] | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState('')
  const [selectedRun, setSelectedRun] = useState(initialRunId || '')
  const [status, setStatus] = useState<BrandStatus | null>(null)
  const [selectedDirection, setSelectedDirection] = useState('')
  const [selectedStage, setSelectedStage] = useState('')
  const [stageOutput, setStageOutput] = useState<unknown>(null)
  const [constraints, setConstraints] = useState('')
  const [referenceUrls, setReferenceUrls] = useState('')
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [createRequestId, setCreateRequestId] = useState('')
  const [rebuildRequestId, setRebuildRequestId] = useState('')
  const [comment, setComment] = useState('')
  const [logoCorrection, setLogoCorrection] = useState('')
  const [editLogoOpen, setEditLogoOpen] = useState(false)
  const [kit, setKit] = useState<BrandKit | null>(null)
  const [readiness, setReadiness] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadLists = () => {
    setError('')
    return Promise.all([
      api.get<{ items: BrandCandidate[] }>('/api/v1/branding/cases?limit=50'),
      api.get<{ items: BrandRun[] }>('/api/v1/branding/runs?limit=50'),
      api.get<{ items: BrandProject[] }>('/api/v1/branding/projects?limit=50'),
      api.get<Record<string, unknown>>('/api/v1/branding/providers'),
    ]).then(([caseData, runData, projectData, providerData]) => {
      const nextProjects = projectData.items || []
      setCandidates(caseData.items || []); setRuns(runData.items || []); setProjects(nextProjects); setReadiness(providerData)
      if (!selectedRun) {
        const canonicalRun = nextProjects.find((item) => item.active_kit)?.active_kit?.run_id
        setSelectedRun(canonicalRun || runData.items?.[0]?.id || '')
      }
      if (!selectedCandidate && caseData.items?.[0]) setSelectedCandidate(caseData.items[0].idea_run_id)
    }).catch((cause: Error) => setError(cause.message))
  }

  const loadRun = (runId = selectedRun) => {
    if (!runId) { setStatus(null); return Promise.resolve(undefined) }
    return api.get<BrandStatus>(`/api/v1/branding/runs/${runId}`).then((data) => {
      setStatus(data)
      setKit(null)
      setSelectedDirection((current) => {
        const currentItem = data.directions.find((item) => item.id === current)
        if (currentItem && currentItem.review_state !== 'approved') return currentItem.id
        const activeRevision = data.directions.find((item) => ['pending', 'running'].includes(item.regeneration_status || ''))
        const nextRequired = data.directions.find((item) => item.review_state !== 'approved')
        if (['awaiting_review', 'running'].includes(data.run.status) && (activeRevision || nextRequired)) {
          return (activeRevision || nextRequired)!.id
        }
        return currentItem?.id || data.directions[0]?.id || ''
      })
      if (data.run.commander_brand_kit_id) {
        void api.get<BrandKit>(`/api/v1/branding/kits/${data.run.commander_brand_kit_id}`).then(setKit).catch(() => undefined)
      }
      return data
    }).catch((cause: Error) => { setError(cause.message); return undefined })
  }

  const loadProject = (projectId: string) => {
    if (!projectId) return Promise.resolve(undefined)
    return api.get<BrandProject>(`/api/v1/branding/projects/${projectId}`).then((data) => {
      setProjects((current) => current
        ? [data, ...current.filter((item) => item.id !== data.id)]
        : [data])
      return data
    }).catch((cause: Error) => { setError(cause.message); return undefined })
  }

  const retryRefresh = () => {
    setError('')
    void loadLists()
    void loadRun()
  }

  useEffect(() => { void loadLists() }, [api])
  useEffect(() => { void loadRun() }, [api, selectedRun])
  useEffect(() => {
    if (!status || !['pending', 'running'].includes(status.run.status)) return
    const timer = window.setInterval(() => { void loadRun() }, 2500)
    return () => window.clearInterval(timer)
  }, [api, selectedRun, status?.run.status])

  const project = useMemo(() => {
    if (!projects?.length) return null
    return projects.find((item) => item.runs.some((run) => run.id === selectedRun))
      || projects.find((item) => item.id === status?.run.source_laval_run_id)
      || null
  }, [projects, selectedRun, status?.run.source_laval_run_id])
  const logoRevision = useMemo(() => project?.logo_revisions.find(
    (item) => ['pending', 'running', 'completed', 'failed'].includes(item.status),
  ) || null, [project])

  useEffect(() => {
    if (!project || !logoRevision || !['pending', 'running'].includes(logoRevision.status)) return
    const timer = window.setInterval(() => { void loadProject(project.id) }, 2500)
    return () => window.clearInterval(timer)
  }, [api, project?.id, logoRevision?.id, logoRevision?.status])

  const direction = useMemo(
    () => status?.directions.find((item) => item.id === selectedDirection) || null,
    [status, selectedDirection],
  )

  useEffect(() => {
    setComment(direction?.review_state === 'changes_requested' ? direction.overall_comment || '' : '')
  }, [direction?.id, direction?.review_state, direction?.overall_comment, direction?.revision])

  const create = async () => {
    if (!selectedCandidate) return
    const existingProject = projects?.find((item) => item.id === selectedCandidate)
    if (existingProject) {
      setCreateOpen(false)
      setSelectedRun(
        existingProject.active_kit?.run_id
        || existingProject.runs[existingProject.runs.length - 1]?.id
        || '',
      )
      return
    }
    const retained = createRequestId || requestId('branding-initial')
    setCreateRequestId(retained)
    setBusy(true); setError('')
    try {
      const created = await api.post<{ run_id: string }>('/api/v1/branding/runs', {
        idea_run_id: selectedCandidate,
        intent: 'initial',
        client_request_id: retained,
        constraints,
        reference_urls: referenceUrls.split(/\n/).map((value) => value.trim()).filter(Boolean),
        manual_transcripts: transcripts.filter((item) => item.video_url && item.transcript),
      })
      setCreateRequestId(''); setCreateOpen(false); setSelectedRun(created.run_id); await loadLists()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const rebuild = async () => {
    if (!project || !window.confirm('Повністю перебудувати бренд із дослідження? Чинний Brand Kit залишиться активним до нового схвалення.')) return
    const retained = rebuildRequestId || requestId('branding-rebuild')
    setRebuildRequestId(retained); setBusy(true); setError('')
    try {
      const created = await api.post<{ run_id: string }>(`/api/v1/branding/projects/${project.id}/rebuild`, {
        client_request_id: retained, constraints: '', reference_urls: [], manual_transcripts: [],
      })
      setRebuildRequestId(''); setSelectedRun(created.run_id); await loadLists()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const reviseApprovedLogo = async () => {
    if (!project || !logoCorrection.trim()) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/projects/${project.id}/logo-revisions`, {
        feedback: logoCorrection.trim(), client_request_id: requestId('logo-edit'),
      })
      setLogoCorrection(''); setEditLogoOpen(false); await loadProject(project.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const decideLogoRevision = async (revision: BrandLogoRevision, decision: 'approve' | 'reject') => {
    if (!project) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/projects/${project.id}/logo-revisions/${revision.id}/decision`, { decision })
      await Promise.all([loadProject(project.id), loadLists()])
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryKitRevision = async (revision: BrandLogoRevision) => {
    if (!project) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/projects/${project.id}/logo-revisions/${revision.id}/retry`, {})
      await loadProject(project.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const control = async (action: 'pause' | 'resume' | 'rerun') => {
    if (!selectedRun) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/runs/${selectedRun}/${action}`, action === 'rerun' ? { stage: selectedStage || status?.run.current_stage } : {})
      await loadRun(); await loadLists()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const inspect = async (stage: string) => {
    setSelectedStage(stage); setStageOutput(null)
    try { setStageOutput(await api.get(`/api/v1/branding/runs/${selectedRun}/show?stage=${stage}`)) }
    catch (cause) { setError((cause as Error).message) }
  }

  const review = async () => {
    if (!direction) return
    const correction = comment.trim()
    const decision = correction ? 'changes' : 'approve'
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/runs/${selectedRun}/directions/${direction.id}/review`, {
        decision, comment: correction,
      })
      setComment('')
      await loadRun()
      await loadLists()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryRegeneration = async () => {
    if (!direction) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/runs/${selectedRun}/directions/${direction.id}/regenerate`, {})
      await loadRun(); await loadLists()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const approve = async () => {
    if (!direction) return
    setBusy(true); setError('')
    try {
      const approved = await api.post<BrandKit>(`/api/v1/branding/runs/${selectedRun}/approve`, { direction_id: direction.id })
      setKit(approved); await loadRun(); await loadLists()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const download = async () => {
    if (!kit?.download?.url) return
    setBusy(true)
    try {
      const blob = await api.blob(kit.download.url)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `${kit.name}-brand-kit.zip`; link.click()
      URL.revokeObjectURL(url)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!candidates || !runs || !projects) return error ? <ErrorState message={error} retry={loadLists} /> : <Loading />
  const approved = status?.directions.filter((item) => item.review_state === 'approved').length || 0
  const allApproved = approved === 3
  const reviewMode = status?.run.current_stage === 'OWNER_REVIEW'
    && ['awaiting_review', 'running'].includes(status.run.status)
  const regenerating = direction?.regeneration_feedback_id === direction?.latest_feedback_id
    && ['pending', 'running'].includes(direction?.regeneration_status || '')
  const regenerationFailed = direction?.regeneration_feedback_id === direction?.latest_feedback_id
    && direction?.regeneration_status === 'failed'
  const providerReady = readiness?.ready === true
  const revisionReady = readiness?.revision_ready === true
  const selectedCandidateHasProject = projects.some((item) => item.id === selectedCandidate)
  const providerLabel = providerReady
    ? String(readiness?.provider || 'готовий')
    : readiness?.configured_provider === 'bridge' ? 'Codex ImageGen недоступний' : 'Провайдер недоступний'

  return <>
    <PageHeader eyebrow="BRANDING V1" title="Брендинг" />
    {error && <div className="laval-error brand-error" role="alert"><span>{error}</span><div className="brand-error-actions"><button onClick={retryRefresh} aria-label="Повторити"><RefreshCw />Повторити</button><button onClick={() => setError('')} aria-label="Закрити"><X /></button></div></div>}

    {createOpen && <section className="brand-create" role="dialog" aria-modal="true" aria-label="Новий Branding запуск">
      <header><div><small>НОВИЙ БРЕНД</small><h2>Оберіть ідею</h2></div><button onClick={() => setCreateOpen(false)} aria-label="Закрити"><X /></button></header>
      <div className="brand-candidates">{candidates.map((item) => <CandidateCard key={item.idea_run_id} item={item} language={language} selected={selectedCandidate === item.idea_run_id} onSelect={() => setSelectedCandidate(item.idea_run_id)} />)}</div>
      {candidates.length === 0 && <Empty><h2>Немає завершених live-ідей</h2><p>Завершіть хоча б одну Idea Laval справу.</p></Empty>}
      {!providerReady && <p className="brand-warning"><ShieldAlert />Codex bridge зараз недоступний. Окремий OpenAI API key не потрібен.</p>}
      <details className="brand-create-advanced"><summary>Додати контекст · необов’язково</summary>
        <label>Обмеження бренду<textarea rows={3} maxLength={4000} value={constraints} onChange={(event) => setConstraints(event.target.value)} placeholder="Тон або заборонені асоціації" /></label>
        <label>Референсні HTTPS URL<textarea rows={3} value={referenceUrls} onChange={(event) => setReferenceUrls(event.target.value)} placeholder="Один URL на рядок" /></label>
        <div className="brand-transcripts"><div><strong>Ручні транскрипти</strong><button type="button" className="secondary" disabled={transcripts.length >= 5} onClick={() => setTranscripts([...transcripts, { title: '', video_url: '', transcript: '' }])}><Plus />Додати</button></div>
          {transcripts.map((item, index) => <article key={index}><input value={item.title} onChange={(event) => setTranscripts(transcripts.map((value, itemIndex) => itemIndex === index ? { ...value, title: event.target.value } : value))} placeholder="Назва відео" /><input value={item.video_url} onChange={(event) => setTranscripts(transcripts.map((value, itemIndex) => itemIndex === index ? { ...value, video_url: event.target.value } : value))} placeholder="https://youtube.com/watch?v=…" /><textarea rows={3} maxLength={10_000} value={item.transcript} onChange={(event) => setTranscripts(transcripts.map((value, itemIndex) => itemIndex === index ? { ...value, transcript: event.target.value } : value))} placeholder="Неперевірений текст власника" /><button type="button" onClick={() => setTranscripts(transcripts.filter((_value, itemIndex) => itemIndex !== index))}>Видалити</button></article>)}
        </div>
      </details>
      <button className="primary large brand-single-cta" disabled={!selectedCandidate || busy || (!providerReady && !selectedCandidateHasProject)} onClick={() => void create()}>{busy ? 'Запуск…' : selectedCandidateHasProject ? 'Відкрити Brand Project' : 'Створити бренд'}</button>
    </section>}

    {runs.length === 0 ? <Empty><h2>Ще немає бренду</h2><p>{providerLabel} · SEO вимкнено</p><button className="primary large" disabled={!candidates.length} onClick={() => setCreateOpen(true)}><Plus />Новий бренд</button></Empty> : <section className="brand-flow">
      {project && <section className="brand-project-anchor" aria-label="Brand Project">
        <header><div><small>BRAND PROJECT · ОДНА ІДЕЯ</small><h2>{project.source_idea.owner_idea}</h2></div><span>{project.active_kit ? `KIT V${project.active_kit.project_version || 1} · АКТИВНИЙ` : 'ЩЕ БЕЗ KIT'}</span></header>
        {project.active_kit && <div className="brand-canonical">
          <div className="brand-project-logo"><AssetLogo api={api} asset={project.active_kit.logo_asset} alt={`Чинне лого ${project.active_kit.name}`} /></div>
          <div><small>КАНОНІЧНИЙ BRAND KIT</small><h3>{project.active_kit.name}</h3><p>Це лого лишається активним для постів, доки ви явно не схвалите нову версію.</p><button className="secondary" disabled={Boolean(logoRevision) || !revisionReady} onClick={() => setEditLogoOpen((value) => !value)}>Редагувати схвалене лого</button>{!revisionReady && <small className="brand-inline-warning">Reference-edit bridge недоступний</small>}</div>
        </div>}
        {editLogoOpen && !logoRevision && <div className="brand-approved-edit"><label>Що саме змінити?<textarea aria-label="Зміна схваленого лого" rows={4} maxLength={2000} value={logoCorrection} onChange={(event) => setLogoCorrection(event.target.value)} placeholder="Наприклад: use just letters PTW, play around them" /></label><button className="primary brand-single-cta" disabled={busy || !logoCorrection.trim() || !revisionReady} onClick={() => void reviseApprovedLogo()}>{busy ? 'Створюю ревізію…' : 'Створити кандидат на перевірку'}</button></div>}
        {logoRevision && <section className={`brand-kit-revision ${logoRevision.status}`}>
          <div className="brand-step-progress"><span>РЕВІЗІЯ KIT V{logoRevision.proposed_project_version}</span><b>{statusLabel(logoRevision.status)}</b></div>
          {logoRevision.status === 'completed' && <div className="brand-before-after"><figure><div className="brand-project-logo"><AssetLogo api={api} asset={logoRevision.before_asset} alt="Лого до ревізії" /></div><figcaption>ДО · KIT V{(logoRevision.proposed_project_version || 2) - 1}</figcaption></figure><figure><div className="brand-project-logo"><AssetLogo api={api} asset={logoRevision.after_asset} alt="Лого після ревізії" /></div><figcaption>ПІСЛЯ · КАНДИДАТ V{logoRevision.proposed_project_version}</figcaption></figure></div>}
          {['pending', 'running'].includes(logoRevision.status) && <div className="brand-revision-working"><div className="brand-spinner" /><div><h3>Застосовую правку до чинного лого</h3><p>Оригінал не змінюється й лишається активним.</p></div></div>}
          <blockquote>{logoRevision.feedback || logoRevision.requested_change}</blockquote>
          {logoRevision.strategy && <p className="brand-compliance">Стратегія: {logoRevision.strategy} · reference: {logoRevision.reference_used ? 'verified' : 'not required'} · compliance: {logoRevision.compliance?.passed ? 'passed' : logoRevision.status === 'failed' ? 'failed' : 'pending'}</p>}
          {logoRevision.status === 'completed' && <div className="brand-revision-decisions"><button className="secondary" disabled={busy} onClick={() => void decideLogoRevision(logoRevision, 'reject')}>Відхилити</button><button className="primary" disabled={busy || logoRevision.compliance?.passed !== true} onClick={() => void decideLogoRevision(logoRevision, 'approve')}>Схвалити новий Brand Kit</button></div>}
          {logoRevision.status === 'failed' && <div className="brand-regeneration-state brand-regeneration-failed"><h3>Кандидат не замінив чинне лого</h3><p>{logoRevision.error?.message || logoRevision.compliance?.reason}</p><button className="primary brand-single-cta" disabled={busy} onClick={() => void retryKitRevision(logoRevision)}>Спробувати ще раз</button></div>}
        </section>}
        <div className="brand-project-history"><small>ІСТОРІЯ ПРОЄКТУ</small>{project.runs.map((run) => <button key={run.id} className={run.id === selectedRun ? 'selected' : ''} onClick={() => setSelectedRun(run.id)}><strong>{run.status === 'completed' ? `Brand Kit v${run.project_version || 1}` : `Draft v${run.project_version || 1}`}</strong><span>{statusLabel(run.status)} · {run.current_stage.replaceAll('_', ' ')} · {run.completed_stages || 0}/10</span></button>)}</div>
        <details className="brand-full-rebuild"><summary>Advanced · повна перебудова з дослідження</summary><p>Створює новий Draft, але не змінює чинний Kit без окремого схвалення.</p><button className="secondary" disabled={busy || !providerReady} onClick={() => void rebuild()}>Повністю перебудувати бренд</button></details>
      </section>}
      <details className="brand-switcher"><summary>Інший Brand Project або запуск</summary><label>Запуск<select value={selectedRun} onChange={(event) => setSelectedRun(event.target.value)}>{runs.map((run) => <option key={run.id} value={run.id}>{run.status === 'completed' ? `Kit v${run.project_version || 1}` : `Draft v${run.project_version || 1}`} · {statusLabel(run.status)} · {run.owner_preview || 'Branding'}</option>)}</select></label><button className="secondary" onClick={() => setCreateOpen(true)} disabled={!candidates.length}><Plus />Нова ідея бренду</button></details>

      {!status ? <Loading /> : <>
        <header className="brand-flow-head"><small>{reviewMode ? 'ПЕРЕГЛЯД ЛОГО' : statusLabel(status.run.status)}</small><h2>{status.run.source_snapshot.owner_idea}</h2>{reviewMode && <p>{allApproved ? 'Усі три логотипи схвалено. Оберіть фінальний напрям.' : `${approved} з 3 логотипів схвалено.`}</p>}</header>
        {status.run.source_stale && <p className="brand-warning"><ShieldAlert />Idea справа змінилась. Цей Kit можна завантажити лише як історичний.</p>}

        {reviewMode && !allApproved && direction && <section className="brand-review-step">
          <div className="brand-step-progress"><span>ЛОГО {direction.ordinal} З 3 · ВЕРСІЯ {direction.revision || 1}</span><div>{status.directions.map((item) => <i key={item.id} className={item.review_state === 'approved' ? 'done' : item.id === direction.id ? 'current' : ''} />)}</div></div>
          <div className={`brand-focused-logo ${regenerating ? 'is-regenerating' : ''}`}><Logo api={api} direction={direction} />{regenerating && <div className="brand-logo-regenerating"><div className="brand-spinner" /><strong>Переробляю…</strong></div>}</div>
          <div className="brand-focused-copy"><h2>{direction.name}</h2><p>{text(direction.manifest.tagline, language)}</p></div>
          {regenerating ? <div className="brand-regeneration-state" role="status"><h3>Створюю нову версію за вашим коментарем</h3><p>Ви залишитеся на цьому логотипі. Коли нова версія буде готова, вона з’явиться тут автоматично.</p>{direction.overall_comment && <blockquote>{direction.overall_comment}</blockquote>}</div>
            : regenerationFailed ? <div className="brand-regeneration-state brand-regeneration-failed"><h3>Не вдалося завершити нову версію</h3><p>{direction.regeneration_error?.message || 'Збережений коментар не втрачено.'}</p><button className="primary large brand-single-cta" disabled={busy} onClick={() => void retryRegeneration()}>{busy ? 'Запуск…' : 'Спробувати переробити ще раз'}</button></div>
              : direction.review_state === 'changes_requested' ? <div className="brand-regeneration-state"><h3>Коментар збережено, але ще не застосовано</h3>{direction.overall_comment && <blockquote>{direction.overall_comment}</blockquote>}<button className="primary large brand-single-cta" disabled={busy} onClick={() => void retryRegeneration()}>{busy ? 'Запуск…' : 'Переробити за коментарем'}</button></div>
                : <>
                  {direction.regeneration_status === 'completed' && <p className="brand-regenerated"><Check />Оновлено за вашим коментарем. Перевірте нову версію.{direction.regeneration_verification === 'legacy_unverified' ? ' Історична ревізія · reference/compliance не перевірені.' : ''}</p>}
                  <label className="brand-text-feedback" htmlFor="brand-feedback">Що змінити?<textarea id="brand-feedback" aria-label="Що змінити?" rows={4} maxLength={1000} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Залиште порожнім, якщо лого підходить" /><small>{comment.trim() ? 'Коментар створить нову версію цього самого лого.' : 'Без коментаря — схвалити й перейти далі.'}</small></label>
                  <button className="primary large brand-single-cta" disabled={busy} onClick={() => void review()}>{busy ? (comment.trim() ? 'Запускаю переробку…' : 'Схвалюю…') : comment.trim() ? 'Переробити за коментарем' : approved === 2 ? 'Схвалити й обрати бренд' : 'Схвалити й далі'}</button>
                </>}
        </section>}

        {status.run.status === 'awaiting_review' && allApproved && direction && <section className="brand-choice-step">
          <div className="brand-choice-tabs" role="radiogroup" aria-label="Фінальний напрям">{status.directions.map((item) => <button key={item.id} role="radio" aria-checked={item.id === direction.id} className={item.id === direction.id ? 'selected' : ''} onClick={() => setSelectedDirection(item.id)}><Check />{item.name}</button>)}</div>
          <div className="brand-focused-logo"><Logo api={api} direction={direction} /></div>
          <div className="brand-focused-copy"><small>ФІНАЛЬНИЙ НАПРЯМ</small><h2>{direction.name}</h2><p>{text(direction.manifest.positioning, language)}</p></div>
          <p className="brand-clearance"><ShieldAlert />Domain and trademark clearance are not performed.</p>
          <button className="primary large brand-single-cta" disabled={busy || status.run.source_stale} onClick={() => void approve()}>{busy ? 'Збирання Kit…' : `Затвердити ${direction.name}`}</button>
        </section>}

        {['pending', 'running'].includes(status.run.status) && !reviewMode && <section className="brand-wait-step"><div className="brand-spinner" /><h2>Створюємо три напрями</h2><p>{status.run.current_stage.replaceAll('_', ' ')} · {status.stages.filter((item) => item.status === 'completed').length}/10</p>{status.run.status === 'running' && <button className="secondary brand-single-cta" disabled={busy} onClick={() => void control('pause')}><Pause />Призупинити</button>}</section>}

        {status.run.status === 'paused' && <section className="brand-recovery-step"><h2>Запуск призупинено</h2><p>Уся завершена робота збережена.</p><button className="primary large brand-single-cta" disabled={busy} onClick={() => void control('resume')}><Play />Продовжити</button></section>}
        {status.run.status === 'failed' && <section className="brand-recovery-step"><h2>Потрібне відновлення</h2><p>Продовжимо зі збереженого етапу без повтору завершеної роботи.</p><button className="primary large brand-single-cta" disabled={busy} onClick={() => void control('resume')}><Play />Продовжити зі збереженого</button></section>}

        {status.run.status === 'completed' && kit && <section className="brand-complete-step"><Check /><small>BRAND KIT ГОТОВИЙ</small><h2>{kit.name}</h2><p>{kit.status === 'stale' ? 'Історичний, застарілий Kit' : 'Лого, кольори, шрифти та React/TypeScript UI kit.'}</p><button className="primary large brand-single-cta" disabled={busy || !kit.download} onClick={() => void download()}><Download />Завантажити Brand Kit</button></section>}

        <details className="brand-technical"><summary>Технічний стан · {status.stages.filter((item) => item.status === 'completed').length}/10</summary><p>{providerLabel} · SEO вимкнено · ${status.cost.total_usd.toFixed(4)}</p><div className="brand-stages">{status.stages.map((stage) => <button key={stage.stage} className={`${stage.status} ${selectedStage === stage.stage ? 'selected' : ''}`} onClick={() => void inspect(stage.stage)}><span>{String(stage.ordinal + 1).padStart(2, '0')}</span><strong>{stage.stage.replaceAll('_', ' ')}</strong><small>{stageStatusLabel(stage.stage, stage.status)} · спроба {stage.attempt}</small></button>)}</div>{selectedStage && <div className="brand-inspector"><pre>{stageOutput ? JSON.stringify(stageOutput, null, 2) : 'Завантаження…'}</pre></div>}{status.run.status === 'failed' && <button className="secondary" disabled={busy} onClick={() => void control('rerun')}><RotateCcw />Перезапустити поточний етап</button>}</details>
      </>}
    </section>}
  </>
}
