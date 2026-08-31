import {
  Brain, Check, Copy, Download, FolderKanban, Menu, Pencil, Plus, RefreshCcw,
  Search, Send, Smartphone, Sparkles, Square, Upload, X,
} from 'lucide-react'
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { ResultDecisionTrace } from '../components/ResultDecisionTrace'
import { translate, type Language } from '../i18n'
import type {
  ContentDebug, ContentResult, ContentRun, ProductBrief, ReviewState,
  SocialPlatform, ValidationProject,
} from '../types'

const ACTIVE = new Set(['queued', 'generating'])

interface LocalProjectAsset {
  source_asset_id: string
  title: string
  mime_type: string
  sha256: string
  origin: string
  approval_status: 'pending' | 'approved' | 'rejected'
  approved: boolean
}

interface LocalLessonProposal {
  proposal_id: string
  target: string
  generalized_text: string
  status: 'pending' | 'approved' | 'rejected'
}

interface LocalLearningSummary {
  market_performance: false
  runs: Array<{
    run_id: string
    status: string
    gate_rate: number | null
    initial_best_score: number | null
    final_best_score: number | null
    score_delta: number | null
    applied_setting_changes: Array<{ setting_id: string; before: unknown; after: unknown }>
    owner_outcomes: Array<{ event_type: string }>
    release: { release_id: string; download_count: number } | null
  }>
  lesson_queue: LocalLessonProposal[]
  approved_lessons: Array<{ lesson_id: string; target: string; version: number; text: string }>
}

function fileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error || new Error('File could not be read.'))
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '')
    reader.readAsDataURL(file)
  })
}

const stageCopy: Record<ContentRun['current_stage'], { en: string; uk: string }> = {
  queued: { en: 'Creating five directions', uk: 'Створюємо п’ять напрямів' },
  initial_candidates: { en: 'Creating five directions', uk: 'Створюємо п’ять напрямів' },
  critic_pass_1: { en: 'Improving the strongest direction', uk: 'Покращуємо найсильніший напрям' },
  critic_pass_2: { en: 'Improving the strongest direction', uk: 'Покращуємо найсильніший напрям' },
  critic_pass_3: { en: 'Final review', uk: 'Фінальна перевірка' },
  materializing_result: { en: 'Final review', uk: 'Фінальна перевірка' },
  completed: { en: 'Completed', uk: 'Завершено' },
  failed: { en: 'Failed', uk: 'Не вдалося' },
}

const reviewCopy: Record<ReviewState, { en: string; uk: string }> = {
  unreviewed: { en: 'Needs review', uk: 'Очікує оцінки' },
  ready: { en: 'Ready', uk: 'Готово' },
  needs_changes: { en: 'Needs changes', uk: 'Потребує змін' },
}

function platformFor(run: ContentRun): SocialPlatform {
  return run.platform || (run.output_profile === 'tiktok_photo_post_v1' ? 'tiktok' : 'instagram')
}

function reviewFor(run: ContentRun): ReviewState {
  return run.review_state || 'unreviewed'
}

function orderedRuns(runs: ContentRun[]): ContentRun[] {
  const byParent = new Map<string, ContentRun[]>()
  const ids = new Set(runs.map((run) => run.run_id))
  for (const run of runs) {
    const key = run.parent_run_id && ids.has(run.parent_run_id) ? run.parent_run_id : 'root'
    byParent.set(key, [...(byParent.get(key) || []), run])
  }
  const newest = (left: ContentRun, right: ContentRun) => right.created_at.localeCompare(left.created_at)
  const result: ContentRun[] = []
  const append = (run: ContentRun) => {
    result.push(run)
    for (const child of [...(byParent.get(run.run_id) || [])].sort(newest).reverse()) append(child)
  }
  for (const root of [...(byParent.get('root') || [])].sort(newest)) append(root)
  return result
}

function PlatformMark({ platform }: { platform: SocialPlatform }) {
  return platform === 'tiktok' ? <Smartphone aria-hidden="true" /> : <Square aria-hidden="true" />
}

function NativePostPreview({
  platform, projectName, result, assetUrl, language,
}: {
  platform: SocialPlatform
  projectName: string
  result: ContentResult
  assetUrl: string
  language: Language
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const account = projectName || 'Natal'
  return <article className={`native-post ${platform}`} aria-label={tr(`${platform} post preview`, `Попередній перегляд допису ${platform}`)}>
    <header>
      <span className="native-avatar" aria-hidden="true">{account.slice(0, 1).toUpperCase()}</span>
      <div><strong>{account}</strong><small>{platform === 'tiktok' ? 'TikTok photo' : 'Instagram'}</small></div>
      <PlatformMark platform={platform} />
    </header>
    <div className="native-media">
      {assetUrl
        ? <img src={assetUrl} alt={result.content.alt_text} />
        : <div className="native-media-loading"><RefreshCcw className="spin" />{tr('Loading verified image…', 'Завантаження перевіреного зображення…')}</div>}
    </div>
    <footer><strong>{account}</strong><span>{result.content.caption}</span></footer>
  </article>
}

export interface ResultViewProps {
  api: ApiClient
  projectId: string | null
  projects: ValidationProject[] | null
  runId?: string | null
  onProjectSelect: (projectId: string) => void
  onNewProject: () => void
  onRenameProject: (projectId: string, name: string) => Promise<void>
  onRunSelect: (runId: string | null) => void
  onOpenBriefs: () => void
  language: Language
  localDemo?: boolean
  liveProduction?: boolean
}

export function ResultView({
  api, projectId, projects, runId = null, onProjectSelect, onNewProject,
  onRenameProject, onRunSelect, onOpenBriefs, language,
  localDemo = false, liveProduction = false,
}: ResultViewProps) {
  const [briefs, setBriefs] = useState<ProductBrief[] | null>(null)
  const [runs, setRuns] = useState<ContentRun[]>([])
  const [selectedRun, setSelectedRun] = useState<ContentRun | null>(null)
  const [result, setResult] = useState<ContentResult | null>(null)
  const [assetUrl, setAssetUrl] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [debug, setDebug] = useState<ContentDebug | null>(null)
  const [platform, setPlatform] = useState<SocialPlatform>('instagram')
  const [briefId, setBriefId] = useState('')
  const [creating, setCreating] = useState(false)
  const [projectSearch, setProjectSearch] = useState('')
  const [platformFilter, setPlatformFilter] = useState<'all' | SocialPlatform>('all')
  const [generationFilter, setGenerationFilter] = useState<'all' | 'active' | 'completed' | 'failed'>('all')
  const [reviewFilter, setReviewFilter] = useState<'all' | ReviewState>('all')
  const [navigatorOpen, setNavigatorOpen] = useState(false)
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({})
  const [renaming, setRenaming] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [localAssets, setLocalAssets] = useState<LocalProjectAsset[]>([])
  const [learning, setLearning] = useState<LocalLearningSummary | null>(null)
  const [pexelsQuery, setPexelsQuery] = useState('')
  const [lessonDrafts, setLessonDrafts] = useState<Record<string, string>>({})
  const tr = (en: string, uk: string) => translate(language, en, uk)

  const approved = useMemo(
    () => (briefs || [])
      .filter((item) => item.approved && item.status === 'completed')
      .sort((left, right) => right.created_at.localeCompare(left.created_at)),
    [briefs],
  )
  const selectedProject = projects?.find((item) => item.project_id === projectId) || null
  const comment = selectedRun ? commentDrafts[selectedRun.run_id] || '' : ''
  const selectedReview = selectedRun ? reviewFor(selectedRun) : 'unreviewed'

  const visibleProjects = useMemo(() => {
    const query = projectSearch.trim().toLocaleLowerCase()
    return (projects || []).filter((item) => !query || item.name.toLocaleLowerCase().includes(query))
  }, [projectSearch, projects])

  const visibleRuns = useMemo(() => orderedRuns(runs).filter((run) => (
    (platformFilter === 'all' || platformFor(run) === platformFilter)
    && (generationFilter === 'all'
      || (generationFilter === 'active' ? ACTIVE.has(run.status) : run.status === generationFilter))
    && (reviewFilter === 'all' || reviewFor(run) === reviewFilter)
  )), [generationFilter, platformFilter, reviewFilter, runs])

  useEffect(() => {
    setProjectName(selectedProject?.name || '')
    setRenaming(false)
  }, [selectedProject?.project_id, selectedProject?.name])

  useEffect(() => {
    if (approved.length && !approved.some((item) => item.brief_id === briefId)) {
      setBriefId(approved[0].brief_id)
    }
  }, [approved, briefId])

  const loadRun = async (nextRunId: string) => {
    const run = await api.get<ContentRun>(`/api/v1/content-runs/${nextRunId}`)
    setSelectedRun(run)
    setRuns((items) => items.map((item) => item.run_id === run.run_id ? { ...item, ...run } : item))
    setDebug(null)
    if (run.status === 'completed') {
      setResult(await api.get<ContentResult>(`/api/v1/content-runs/${nextRunId}/result`))
    } else setResult(null)
  }

  const loadWorkspace = async (preferredRunId?: string | null) => {
    if (!projectId) {
      setBriefs([]); setRuns([]); setSelectedRun(null); setResult(null)
      return
    }
    const [briefValue, runValue] = await Promise.all([
      api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: ContentRun[] }>(`/api/v1/content-runs?limit=100&project_id=${encodeURIComponent(projectId)}`),
    ])
    setBriefs(briefValue.items)
    setRuns(runValue.items)
    const chosen = runValue.items.find((item) => item.run_id === preferredRunId)?.run_id
      || runValue.items[0]?.run_id || null
    if (!chosen) {
      setSelectedRun(null); setResult(null); onRunSelect(null)
      return
    }
    if (chosen !== preferredRunId) onRunSelect(chosen)
    await loadRun(chosen)
  }

  useEffect(() => {
    setBriefs(null); setRuns([]); setSelectedRun(null); setResult(null)
    setError(''); setDebug(null); setCreating(false)
    void loadWorkspace(runId).catch((cause: Error) => setError(cause.message))
  }, [api, projectId])

  const loadLocalEvidence = async () => {
    if (!localDemo || !projectId) { setLocalAssets([]); setLearning(null); return }
    const [assets, summary] = await Promise.all([
      api.get<{ items: LocalProjectAsset[] }>(`/api/v1/projects/${projectId}/assets`),
      api.get<LocalLearningSummary>(`/api/v1/learning-summary?project_id=${encodeURIComponent(projectId)}`),
    ])
    setLocalAssets(assets.items)
    setLearning(summary)
    setLessonDrafts((current) => ({
      ...Object.fromEntries(summary.lesson_queue.map((item) => [item.proposal_id, item.generalized_text])),
      ...current,
    }))
  }

  useEffect(() => {
    void loadLocalEvidence().catch((cause: Error) => setError(cause.message))
  }, [api, localDemo, projectId])

  useEffect(() => {
    if (!runId || !projectId || runId === selectedRun?.run_id) return
    void loadRun(runId).catch((cause: Error) => setError(cause.message))
  }, [runId])

  useEffect(() => {
    if (!selectedRun || !ACTIVE.has(selectedRun.status)) return
    const timer = window.setInterval(() => {
      void loadWorkspace(selectedRun.run_id).catch((cause: Error) => setError(cause.message))
    }, 2000)
    return () => window.clearInterval(timer)
  }, [selectedRun?.run_id, selectedRun?.status])

  useEffect(() => {
    if (!result?.asset_url) { setAssetUrl(''); return }
    let local = ''
    if (!result.asset_sha256) {
      setError(tr('Rendered social post is missing its asset digest.', 'У відрендерованого допису відсутній цифровий відбиток файлу.'))
      return
    }
    void api.image(result.asset_url, result.asset_mime_type || 'image/jpeg', result.asset_sha256)
      .then((blob) => {
        if (!(blob instanceof Blob)) return
        local = URL.createObjectURL(blob); setAssetUrl(local)
      })
      .catch((cause: Error) => setError(cause.message))
    return () => { if (local) URL.revokeObjectURL(local) }
  }, [api, result?.creative_id])

  const confirmProduction = (message: string) => !liveProduction || window.confirm(message)

  const create = async () => {
    if (!briefId) return
    if (localDemo && window.sessionStorage.getItem('ptw.studio.unsaved') === '1') {
      setError(tr('Save the Universal Studio draft before starting a run.', 'Збережіть чернетку Universal Studio перед запуском.'))
      return
    }
    if (!confirmProduction(tr(
      `Create a new ${platform === 'tiktok' ? 'TikTok' : 'Instagram'} artifact using production providers?`,
      `Створити новий артефакт ${platform === 'tiktok' ? 'TikTok' : 'Instagram'} через продакшн-провайдери?`,
    ))) return
    setBusy(true); setError(''); setNotice('')
    try {
      const request = localDemo
        ? await api.get<{ state_sha256: string }>('/api/v1/studio').then((studio) => ({
          request_id: crypto.randomUUID(), brief_id: briefId,
          platform: 'instagram' as const, studio_state_sha256: studio.state_sha256,
        }))
        : { request_id: crypto.randomUUID(), brief_id: briefId, platform }
      const run = await api.post<ContentRun>('/api/v1/content-runs', request, { deadlineMs: 60_000 })
      setCreating(false)
      onRunSelect(run.run_id)
      setNotice(tr('Social post creation started.', 'Створення допису для соцмереж розпочато.'))
      await loadWorkspace(run.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retry = async () => {
    if (!selectedRun) return
    setBusy(true); setError('')
    try {
      const child = await api.post<ContentRun>(`/api/v1/content-runs/${selectedRun.run_id}/retry`, {
        request_id: crypto.randomUUID(),
      }, { deadlineMs: 60_000 })
      onRunSelect(child.run_id)
      await loadWorkspace(child.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const ready = async () => {
    if (!selectedRun || selectedReview === 'ready') return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/content-runs/${selectedRun.run_id}/feedback`, { decision: 'accepted' })
      setNotice(tr('Artifact is ready to export.', 'Артефакт готовий до експорту.'))
      await loadWorkspace(selectedRun.run_id)
      await loadLocalEvidence()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const improve = async () => {
    if (!selectedRun || comment.trim().length < 3) return
    if (!confirmProduction(tr(
      'Record this evaluation and create a production revision now?',
      'Зберегти цю оцінку й зараз створити продакшн-ревізію?',
    ))) return
    setBusy(true); setError('')
    try {
      const child = await api.post<ContentRun>(`/api/v1/content-runs/${selectedRun.run_id}/revisions`, {
        request_id: crypto.randomUUID(), comment: comment.trim(),
      }, { deadlineMs: 60_000 })
      setCommentDrafts((items) => ({ ...items, [selectedRun.run_id]: '' }))
      setNotice(tr('Feedback recorded. The improved revision is running.', 'Відгук збережено. Покращена ревізія створюється.'))
      onRunSelect(child.run_id)
      await loadWorkspace(child.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const download = async () => {
    if (!selectedRun || !result || selectedReview !== 'ready') return
    if (localDemo) {
      const packageBlob = await api.download(`/api/v1/content-runs/${selectedRun.run_id}/release`, 'application/zip', { deadlineMs: 60_000 })
      const packageUrl = URL.createObjectURL(packageBlob)
      const packageLink = document.createElement('a'); packageLink.href = packageUrl
      packageLink.download = `ptw-instagram-release-r${(selectedRun.revision_number || 0) + 1}.zip`
      packageLink.click(); URL.revokeObjectURL(packageUrl)
      setNotice(tr('Immutable release package downloaded and recorded.', 'Незмінний пакет релізу завантажено й зафіксовано.'))
      await loadLocalEvidence()
      return
    }
    if (!assetUrl) return
    await api.post(`/api/v1/content-runs/${selectedRun.run_id}/outcomes`, { event_type: 'downloaded' })
    const chosenPlatform = platformFor(selectedRun)
    const link = document.createElement('a'); link.href = assetUrl
    link.download = `natal-${chosenPlatform}-post-r${(selectedRun.revision_number || 0) + 1}.jpg`
    link.click()
    setNotice(tr('Export recorded and image downloaded.', 'Експорт зафіксовано, зображення завантажено.'))
  }

  const uploadLocalAsset = async (file: File) => {
    if (!projectId) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/projects/${projectId}/assets`, {
        title: file.name, mime_type: file.type, bytes_base64: await fileAsBase64(file),
      }, { deadlineMs: 90_000 })
      await loadLocalEvidence()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const decideAsset = async (assetId: string, approved: boolean) => {
    if (!projectId) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/projects/${projectId}/assets/${assetId}/decision`, { approved })
      await loadLocalEvidence()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const sourceLocalPexels = async () => {
    if (!projectId || pexelsQuery.trim().length < 2) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/projects/${projectId}/assets/pexels`, { query: pexelsQuery.trim() }, { deadlineMs: 90_000 })
      setPexelsQuery(''); await loadLocalEvidence()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const decideLesson = async (proposalId: string, decision: 'approved' | 'rejected') => {
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/lessons/${proposalId}/decision`, {
        decision, approval_authority: 'owner', edited_text: lessonDrafts[proposalId] || null,
      })
      await loadLocalEvidence()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const copyText = async (value: string, label: string) => {
    await navigator.clipboard.writeText(value)
    setNotice(tr(`${label} copied.`, `${label} скопійовано.`))
  }

  const saveProjectName = async () => {
    if (!selectedProject || !projectName.trim()) return
    setBusy(true); setError('')
    try { await onRenameProject(selectedProject.project_id, projectName.trim()); setRenaming(false) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  if (!briefs) return error ? <ErrorState message={error} retry={() => void loadWorkspace(runId)} language={language} /> : <Loading language={language} />
  return <div className="social-page">
    <PageHeader eyebrow={tr('CREATE · REVIEW · IMPROVE', 'СТВОРЕННЯ · ОЦІНКА · ПОКРАЩЕННЯ')} title={tr('Social posts', 'Дописи для соцмереж')} />
    {localDemo && <p className="notice" role="status">{tr(
      'Local evaluation and learning only · no publishing, production mutation, or market-performance ingestion.',
      'Лише локальна оцінка й навчання · без публікації, змін продакшну чи ринкових метрик.',
    )}</p>}
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
    <button className="secondary social-navigator-toggle" onClick={() => setNavigatorOpen((value) => !value)} aria-expanded={navigatorOpen}>
      <Menu />{tr('Projects and artifacts', 'Проєкти й артефакти')}
    </button>
    <div className="social-workspace">
      <aside className={`social-navigator ${navigatorOpen ? 'open' : ''}`} aria-label={tr('Projects and artifacts', 'Проєкти й артефакти')}>
        <header><FolderKanban /><div><small>{tr('PROJECTS', 'ПРОЄКТИ')}</small><strong>{selectedProject?.name || tr('Choose a project', 'Виберіть проєкт')}</strong></div></header>
        <label className="social-search"><span className="visually-hidden">{tr('Search projects', 'Пошук проєктів')}</span><Search /><input value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} placeholder={tr('Search projects', 'Пошук проєктів')} /></label>
        <div className="social-project-list">
          {visibleProjects.map((project) => <button key={project.project_id} className={project.project_id === projectId ? 'selected' : ''} onClick={() => { onProjectSelect(project.project_id); setNavigatorOpen(false) }}><strong>{project.name}</strong><span>{project.result_run_count} {tr('artifacts', 'артефактів')}</span></button>)}
        </div>
        <div className="social-project-actions">
          <button className="ghost" onClick={() => setRenaming((value) => !value)} disabled={!selectedProject}><Pencil />{tr('Rename', 'Перейменувати')}</button>
          <button className="ghost" onClick={onNewProject}><Plus />{tr('New', 'Новий')}</button>
        </div>
        {renaming && <div className="social-project-rename"><input maxLength={120} value={projectName} onChange={(event) => setProjectName(event.target.value)} aria-label={tr('Project name', 'Назва проєкту')} /><button className="primary" onClick={() => void saveProjectName()} disabled={busy || !projectName.trim()}><Check /></button><button className="ghost" onClick={() => setRenaming(false)}><X /></button></div>}
        <div className="social-artifact-heading"><small>{tr('ARTIFACTS', 'АРТЕФАКТИ')}</small><button className="primary" onClick={() => { setCreating(true); setNavigatorOpen(false) }} disabled={!projectId}><Plus />{tr('Post', 'Допис')}</button></div>
        <div className="social-filters">
          <select aria-label={tr('Filter by platform', 'Фільтр за платформою')} value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value as typeof platformFilter)}><option value="all">{tr('All platforms', 'Усі платформи')}</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option></select>
          <select aria-label={tr('Filter by generation status', 'Фільтр за статусом створення')} value={generationFilter} onChange={(event) => setGenerationFilter(event.target.value as typeof generationFilter)}><option value="all">{tr('All generation', 'Усі генерації')}</option><option value="active">{tr('In progress', 'У процесі')}</option><option value="completed">{tr('Completed', 'Завершені')}</option><option value="failed">{tr('Failed', 'Невдалі')}</option></select>
          <select aria-label={tr('Filter by review', 'Фільтр за оцінкою')} value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value as typeof reviewFilter)}><option value="all">{tr('All states', 'Усі стани')}</option><option value="unreviewed">{tr('Needs review', 'Очікує оцінки')}</option><option value="ready">{tr('Ready', 'Готово')}</option><option value="needs_changes">{tr('Needs changes', 'Потребує змін')}</option></select>
        </div>
        <div className="social-artifact-list">
          {visibleRuns.map((run) => {
            const runPlatform = platformFor(run)
            const review = reviewFor(run)
            const depth = Math.min(run.revision_number || (run.parent_run_id ? 1 : 0), 3)
            return <button key={run.run_id} className={run.run_id === selectedRun?.run_id ? 'selected' : ''} style={{ '--revision-depth': depth } as CSSProperties & { '--revision-depth': number }} onClick={() => { onRunSelect(run.run_id); setNavigatorOpen(false) }}>
              <span className="artifact-platform"><PlatformMark platform={runPlatform} />{runPlatform === 'tiktok' ? 'TikTok' : 'Instagram'} · R{(run.revision_number || 0) + 1}</span>
              <strong>{ACTIVE.has(run.status) ? translate(language, stageCopy[run.current_stage].en, stageCopy[run.current_stage].uk) : run.status === 'failed' ? tr('Generation failed', 'Генерація не вдалася') : translate(language, reviewCopy[review].en, reviewCopy[review].uk)}</strong>
              <small>{new Date(run.created_at).toLocaleString(language === 'uk' ? 'uk-UA' : 'en-US')}</small>
            </button>
          })}
          {!visibleRuns.length && <p>{tr('No artifacts match these filters.', 'Немає артефактів за цими фільтрами.')}</p>}
        </div>
      </aside>

      <main className="social-detail">
        <div className="social-detail-bar">
          <div>{selectedRun && <><span className={`review-chip ${selectedReview}`}>{translate(language, reviewCopy[selectedReview].en, reviewCopy[selectedReview].uk)}</span><span>{platformFor(selectedRun) === 'tiktok' ? 'TikTok' : 'Instagram'} · R{(selectedRun.revision_number || 0) + 1}</span></>}</div>
          <button className="primary" onClick={() => setCreating(true)} disabled={!projectId}><Plus />{tr('New post', 'Новий допис')}</button>
        </div>

        {creating && <section className="social-create-card">
          <header><div><small>{tr('NEW SOCIAL POST', 'НОВИЙ ДОПИС')}</small><h2>{tr('Choose the destination', 'Оберіть платформу')}</h2></div><button className="ghost" onClick={() => setCreating(false)} aria-label={tr('Close', 'Закрити')}><X /></button></header>
          <div className="platform-choice" role="radiogroup" aria-label={tr('Platform', 'Платформа')}>
            <button role="radio" aria-checked={platform === 'instagram'} className={platform === 'instagram' ? 'selected' : ''} onClick={() => setPlatform('instagram')}><Square />Instagram<span>1080 × 1080</span></button>
            {!localDemo && <button role="radio" aria-checked={platform === 'tiktok'} className={platform === 'tiktok' ? 'selected' : ''} onClick={() => setPlatform('tiktok')}><Smartphone />TikTok<span>1080 × 1920</span></button>}
          </div>
          {approved.length > 1
            ? <label>{tr('Approved Product Brief', 'Схвалений продуктовий бриф')}<select value={briefId} onChange={(event) => setBriefId(event.target.value)}>{approved.map((item) => <option key={item.brief_id} value={item.brief_id}>{item.product}</option>)}</select></label>
            : approved[0] && <p className="social-brief-choice"><Check />{approved[0].product}</p>}
          {!approved.length && <div className="social-no-brief"><p>{tr('Approve a completed Product Brief before creating a post.', 'Схваліть завершений продуктовий бриф перед створенням допису.')}</p><button className="secondary" onClick={onOpenBriefs}>{tr('Open Product Briefs', 'Відкрити продуктові брифи')}</button></div>}
          {localDemo && <p className="social-live-hint">{tr('Uses the current saved Universal Studio export, five strategies, and three critic passes.', 'Використовує поточний збережений експорт Universal Studio, п’ять стратегій і три етапи критика.')}</p>}
          <button className="primary large" disabled={busy || !briefId} onClick={() => void create()}><Sparkles />{tr('Create post', 'Створити допис')}</button>
        </section>}

        {!projectId && <Empty><FolderKanban className="empty-mark" /><h2>{tr('Select or create a Project', 'Виберіть або створіть проєкт')}</h2></Empty>}
        {projectId && !selectedRun && !creating && <Empty><Sparkles className="empty-mark" /><h2>{tr('Create the first social post', 'Створіть перший допис')}</h2><button className="primary" onClick={() => setCreating(true)}><Plus />{tr('New post', 'Новий допис')}</button></Empty>}

        {selectedRun && <section className="social-artifact">
          {ACTIVE.has(selectedRun.status) && <div className="social-progress" role="status"><div><RefreshCcw className="spin" /><div><strong>{translate(language, stageCopy[selectedRun.current_stage].en, stageCopy[selectedRun.current_stage].uk)}</strong><span>{selectedRun.progress_percent}% · {tr('bounded maximum 45 minutes', 'максимум 45 хвилин')}</span></div></div><progress max={100} value={selectedRun.progress_percent} /></div>}
          {selectedRun.status === 'failed' && <div className="social-failure"><h2>{tr('This artifact could not be completed', 'Не вдалося завершити цей артефакт')}</h2><p>{selectedRun.error_message || selectedRun.error_code}</p><button className="secondary" disabled={busy} onClick={() => void retry()}><RefreshCcw />{tr('Retry as a child artifact', 'Повторити як дочірній артефакт')}</button></div>}
          {result && <div className="social-review-layout">
            <div className="social-preview-column">
              <NativePostPreview platform={platformFor(selectedRun)} projectName={selectedProject?.name || 'Natal'} result={result} assetUrl={assetUrl} language={language} />
              <details className="social-advanced" onToggle={(event) => { if ((event.currentTarget as HTMLDetailsElement).open && !debug) void api.get<ContentDebug>(`/api/v1/content-runs/${selectedRun.run_id}/debug`).then(setDebug).catch((cause: Error) => setError(cause.message)) }}>
                <summary>{tr('Export details and decision trace', 'Деталі експорту та рішення')}</summary>
                <dl><dt>{tr('Alt text', 'Альтернативний текст')}</dt><dd>{result.content.alt_text}</dd><dt>{tr('Asset', 'Файл')}</dt><dd>{result.asset_mime_type || 'image/jpeg'} · {result.asset_width || 1080} × {result.asset_height || (platformFor(selectedRun) === 'tiktok' ? 1920 : 1080)}</dd><dt>SHA-256</dt><dd><code>{result.asset_sha256}</code></dd></dl>
                {debug ? <ResultDecisionTrace value={debug} api={api} selectedCandidateId={result.selected_candidate_id} language={language} /> : <p>{tr('Loading bounded trace…', 'Завантаження обмеженого трасування…')}</p>}
              </details>
            </div>
            <aside className="social-review-panel">
              <small>{tr('EVALUATE ARTIFACT', 'ОЦІНІТЬ АРТЕФАКТ')}</small>
              <h2>{translate(language, reviewCopy[selectedReview].en, reviewCopy[selectedReview].uk)}</h2>
              {selectedRun.review_comment && <p className="saved-feedback">{selectedRun.review_comment}</p>}
              <label>{tr('What should change?', 'Що потрібно змінити?')}<textarea minLength={3} maxLength={2000} value={comment} onChange={(event) => setCommentDrafts((items) => ({ ...items, [selectedRun.run_id]: event.target.value }))} placeholder={tr('Make the headline calmer and move the CTA higher…', 'Зробіть заголовок спокійнішим і підніміть CTA вище…')} /></label>
              <div className="social-review-actions">
                <button className="primary" disabled={busy || selectedReview === 'ready' || selectedReview === 'needs_changes'} onClick={() => void ready()}><Check />{tr('Ready', 'Готово')}</button>
                <button className="secondary" disabled={busy || comment.trim().length < 3} onClick={() => void improve()}><Send />{tr('Improve', 'Покращити')}</button>
              </div>
              <p className="review-help">{tr('Improve records your comment as feedback and starts a lineage-linked revision.', '«Покращити» зберігає коментар як відгук і запускає пов’язану ревізію.')}</p>
              <section className={`social-export ${selectedReview === 'ready' ? 'unlocked' : ''}`}>
                <small>{tr('EXPORT PACKAGE', 'ПАКЕТ ЕКСПОРТУ')}</small>
                <button className="secondary" disabled={selectedReview !== 'ready' || (!localDemo && !assetUrl)} onClick={() => void download()}><Download />{localDemo ? tr('Download release package', 'Завантажити пакет релізу') : tr('Download image', 'Завантажити зображення')}</button>
                <button className="ghost" disabled={selectedReview !== 'ready'} onClick={() => void copyText(result.content.caption, platformFor(selectedRun) === 'tiktok' ? tr('Description', 'Опис') : tr('Caption', 'Підпис'))}><Copy />{platformFor(selectedRun) === 'tiktok' ? tr('Copy description', 'Копіювати опис') : tr('Copy caption', 'Копіювати підпис')}</button>
                <button className="ghost" disabled={selectedReview !== 'ready'} onClick={() => void copyText(result.content.alt_text, tr('Alt text', 'Альтернативний текст'))}><Copy />{tr('Copy alt text', 'Копіювати alt text')}</button>
              </section>
            </aside>
          </div>}
        </section>}
      </main>
    </div>
    {localDemo && projectId && <section className="panel local-learning-panel">
      <header><div><small>{tr('LOCAL QUALITY EVIDENCE', 'ЛОКАЛЬНІ ДОКАЗИ ЯКОСТІ')}</small><h2><Brain />{tr('Learning & evidence', 'Навчання й докази')}</h2></div><p>{tr('Internal evaluation only — never a market-performance claim.', 'Лише внутрішня оцінка — не твердження про ринкову ефективність.')}</p></header>
      <div className="local-evidence-grid">
        <section><h3>{tr('Approved asset pool', 'Пул схвалених ресурсів')}</h3>
          <label className="secondary local-upload"><Upload />{tr('Upload photo', 'Завантажити фото')}<input className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadLocalAsset(file); event.currentTarget.value = '' }} /></label>
          <div className="local-pexels"><input value={pexelsQuery} onChange={(event) => setPexelsQuery(event.target.value)} placeholder={tr('Pexels search…', 'Пошук Pexels…')} /><button className="secondary" disabled={busy || pexelsQuery.trim().length < 2} onClick={() => void sourceLocalPexels()}>{tr('Source', 'Знайти')}</button></div>
          <ul>{localAssets.map((asset) => <li key={asset.source_asset_id}><div><strong>{asset.title}</strong><small>{asset.origin} · {asset.sha256.slice(0, 10)} · {asset.approval_status}</small></div>{asset.approval_status === 'pending' && <span><button className="ghost" onClick={() => void decideAsset(asset.source_asset_id, true)}>{tr('Approve', 'Схвалити')}</button><button className="ghost" onClick={() => void decideAsset(asset.source_asset_id, false)}>{tr('Reject', 'Відхилити')}</button></span>}</li>)}</ul>
        </section>
        <section><h3>{tr('Run learning curve', 'Крива навчання запусків')}</h3>
          <ul>{(learning?.runs || []).map((item) => <li key={item.run_id}><div><strong>{item.status} · {item.gate_rate == null ? '—' : `${Math.round(item.gate_rate * 100)}% gates`}</strong><small>{tr('Initial → final', 'Початок → фінал')}: {item.initial_best_score ?? '—'} → {item.final_best_score ?? '—'} ({item.score_delta == null ? '—' : `${item.score_delta >= 0 ? '+' : ''}${item.score_delta}`}) · {item.applied_setting_changes.length} {tr('setting changes', 'змін налаштувань')}</small></div></li>)}</ul>
        </section>
      </div>
      <section className="local-lesson-queue"><h3>{tr('Pending lesson review', 'Черга перевірки уроків')}</h3>{!learning?.lesson_queue.length && <p>{tr('No pending lessons.', 'Немає уроків на розгляді.')}</p>}{learning?.lesson_queue.map((proposal) => <article key={proposal.proposal_id}><small>{proposal.target}</small><textarea rows={3} value={lessonDrafts[proposal.proposal_id] ?? proposal.generalized_text} onChange={(event) => setLessonDrafts((items) => ({ ...items, [proposal.proposal_id]: event.target.value }))} /><div><button className="primary" disabled={busy} onClick={() => void decideLesson(proposal.proposal_id, 'approved')}>{tr('Approve lesson', 'Схвалити урок')}</button><button className="secondary" disabled={busy} onClick={() => void decideLesson(proposal.proposal_id, 'rejected')}>{tr('Reject', 'Відхилити')}</button></div></article>)}</section>
    </section>}
  </div>
}
