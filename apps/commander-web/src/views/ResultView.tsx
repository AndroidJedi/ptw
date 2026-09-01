import {
  Brain, Check, CircleStop, Copy, Download, FolderKanban, Plus, RefreshCcw,
  Send, Smartphone, Sparkles, Square, X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { CreativeReviewGrid } from '../components/CreativeReviewGrid'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type {
  ContentCreative, ContentReview, ContentRun, ProductBrief, SocialPlatform,
  StudioUniversalDetail, ValidationProject,
} from '../types'

const ACTIVE = new Set<ContentRun['status']>(['queued', 'generating'])
const REVIEWABLE = new Set<ContentRun['status']>(['awaiting_review', 'approved', 'superseded'])

const stageCopy: Record<ContentRun['current_stage'], { en: string; uk: string }> = {
  queued: { en: 'Queued', uk: 'У черзі' },
  generating_creatives: { en: 'Creating five verified directions', uk: 'Створюємо п’ять перевірених напрямів' },
  awaiting_review: { en: 'Awaiting your review', uk: 'Очікує вашого перегляду' },
  approved: { en: 'Approved', uk: 'Схвалено' },
  superseded: { en: 'Replaced by a newer review set', uk: 'Замінено новішим набором' },
  failed: { en: 'Failed', uk: 'Не вдалося' },
  terminated: { en: 'Terminated', uk: 'Зупинено' },
}

function platformFor(run: ContentRun): SocialPlatform {
  return run.platform || (run.output_profile === 'tiktok_photo_post_v1' ? 'tiktok' : 'instagram')
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

function ApprovedPost({ api, run, creative, projectName, language }: {
  api: ApiClient
  run: ContentRun
  creative: ContentCreative
  projectName: string
  language: Language
}) {
  const [source, setSource] = useState('')
  const [error, setError] = useState('')
  const platform = platformFor(run)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  useEffect(() => {
    let objectUrl = ''
    let active = true
    void api.image(creative.preview.asset_url, creative.preview.mime_type, creative.preview.sha256)
      .then((blob) => {
        if (!active || !(blob instanceof Blob)) return
        objectUrl = URL.createObjectURL(blob); setSource(objectUrl)
      })
      .catch((cause: Error) => { if (active) setError(cause.message) })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, creative.creative_id, creative.preview.sha256])
  return <article className={`native-post ${platform}`} aria-label={tr('Approved native post', 'Схвалений нативний допис')}>
    <header>
      <span className="native-avatar" aria-hidden="true">{projectName.slice(0, 1).toUpperCase()}</span>
      <div><strong>{projectName}</strong><small>{platform === 'tiktok' ? 'TikTok photo' : 'Instagram'}</small></div>
      <PlatformMark platform={platform} />
    </header>
    <div className="native-media">
      {source ? <img src={source} alt={creative.document.alt_text} />
        : <div className="native-media-loading">{error || <><RefreshCcw className="spin" />{tr('Loading verified image…', 'Завантаження перевіреного зображення…')}</>}</div>}
    </div>
    <footer><strong>{projectName}</strong><span>{creative.document.caption}</span></footer>
  </article>
}

export interface ResultViewProps {
  api: ApiClient
  projectId: string | null
  projects: ValidationProject[] | null
  runId?: string | null
  onProjectSelect: (projectId: string) => void
  onRunSelect: (runId: string | null) => void
  onOpenBriefs: () => void
  language: Language
  localDemo?: boolean
  liveProduction?: boolean
}

export function ResultView({
  api, projectId, projects, runId = null, onProjectSelect, onRunSelect,
  onOpenBriefs, language, localDemo = false, liveProduction = false,
}: ResultViewProps) {
  const [briefs, setBriefs] = useState<ProductBrief[] | null>(null)
  const [runs, setRuns] = useState<ContentRun[]>([])
  const [selectedRun, setSelectedRun] = useState<ContentRun | null>(null)
  const [review, setReview] = useState<ContentReview | null>(null)
  const [selectedCreativeId, setSelectedCreativeId] = useState<string | null>(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [platform, setPlatform] = useState<SocialPlatform>('instagram')
  const [briefId, setBriefId] = useState('')
  const [creating, setCreating] = useState(false)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  const approvedBriefs = useMemo(() => (briefs || [])
    .filter((item) => item.approved && item.status === 'completed')
    .sort((left, right) => right.created_at.localeCompare(left.created_at)), [briefs])
  const selectedProject = projects?.find((item) => item.project_id === projectId) || null
  const availableRuns = useMemo(() => orderedRuns(runs), [runs])
  const actionProcessing = Boolean(review?.owner_actions.some((action) => action.status === 'processing'))
  const actionable = selectedRun?.status === 'awaiting_review' && !actionProcessing

  useEffect(() => {
    if (approvedBriefs.length && !approvedBriefs.some((item) => item.brief_id === briefId)) {
      setBriefId(approvedBriefs[0].brief_id)
    }
  }, [approvedBriefs, briefId])

  const loadRun = async (nextRunId: string) => {
    const run = await api.get<ContentRun>(`/api/v1/content-runs/${nextRunId}`)
    setSelectedRun(run)
    setRuns((items) => items.map((item) => item.run_id === run.run_id ? { ...item, ...run } : item))
    if (!REVIEWABLE.has(run.status)) {
      setReview(null); setSelectedCreativeId(null)
      return
    }
    const nextReview = await api.get<ContentReview>(`/api/v1/content-runs/${nextRunId}/review`)
    setReview(nextReview)
    setSelectedCreativeId((current) => {
      const preferred = run.approved_creative_id || current
      return nextReview.creatives.some((item) => item.creative_id === preferred)
        ? preferred as string : nextReview.creatives[0]?.creative_id || null
    })
  }

  const loadWorkspace = async (preferredRunId?: string | null) => {
    if (!projectId) {
      setBriefs([]); setRuns([]); setSelectedRun(null); setReview(null)
      return
    }
    const [briefValue, runValue] = await Promise.all([
      api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: ContentRun[] }>(`/api/v1/content-runs?limit=100&project_id=${encodeURIComponent(projectId)}`),
    ])
    setBriefs(briefValue.items); setRuns(runValue.items)
    const chosen = runValue.items.find((item) => item.run_id === preferredRunId)?.run_id
      || runValue.items[0]?.run_id || null
    if (!chosen) {
      setSelectedRun(null); setReview(null); onRunSelect(null)
      return
    }
    if (chosen !== preferredRunId) onRunSelect(chosen)
    await loadRun(chosen)
  }

  useEffect(() => {
    setBriefs(null); setRuns([]); setSelectedRun(null); setReview(null)
    setError(''); setCreating(false); setSelectedCreativeId(null); setComment('')
    void loadWorkspace(runId).catch((cause: Error) => setError(cause.message))
  }, [api, projectId])

  useEffect(() => {
    if (!runId || !projectId || runId === selectedRun?.run_id) return
    setComment('')
    void loadRun(runId).catch((cause: Error) => setError(cause.message))
  }, [runId])

  useEffect(() => {
    if (!selectedRun || !ACTIVE.has(selectedRun.status)) return
    const timer = window.setInterval(() => {
      void loadWorkspace(selectedRun.run_id).catch((cause: Error) => setError(cause.message))
    }, 2000)
    return () => window.clearInterval(timer)
  }, [selectedRun?.run_id, selectedRun?.status])

  const confirmProduction = (message: string) => !liveProduction || window.confirm(message)

  const create = async () => {
    if (!briefId) return
    if (localDemo && window.sessionStorage.getItem('ptw.studio.unsaved') === '1') {
      setError(tr('Save the Universal Studio draft before starting a run.', 'Збережіть чернетку Universal Studio перед запуском.'))
      return
    }
    if (!confirmProduction(tr('Generate five reviewable posts now?', 'Створити п’ять дописів для перегляду зараз?'))) return
    setBusy(true); setError(''); setNotice('')
    try {
      const request = localDemo
        ? await api.get<StudioUniversalDetail>('/api/v1/studio').then((studio) => {
          if (!studio.pexels_available) throw new Error(tr(
            'Pexels is not configured. Set PEXELS_API_KEY before creating a post.',
            'Pexels не налаштовано. Додайте PEXELS_API_KEY перед створенням допису.',
          ))
          return {
            request_id: crypto.randomUUID(), brief_id: briefId,
            platform: 'instagram' as const, studio_state_sha256: studio.state_sha256,
          }
        })
        : { request_id: crypto.randomUUID(), brief_id: briefId, platform }
      const run = await api.post<ContentRun>('/api/v1/content-runs', request, { deadlineMs: 60_000 })
      setCreating(false); onRunSelect(run.run_id)
      setNotice(tr('Five-post generation started.', 'Створення п’яти дописів розпочато.'))
      await loadWorkspace(run.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retry = async () => {
    if (!selectedRun || !new Set(['failed', 'terminated']).has(selectedRun.status)) return
    setBusy(true); setError('')
    try {
      const child = await api.post<ContentRun>(`/api/v1/content-runs/${selectedRun.run_id}/retry`, {
        request_id: crypto.randomUUID(),
      }, { deadlineMs: 60_000 })
      onRunSelect(child.run_id); await loadWorkspace(child.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const terminate = async () => {
    if (!localDemo || !selectedRun || !ACTIVE.has(selectedRun.status)) return
    if (!window.confirm(tr('Terminate this local run?', 'Зупинити цей локальний запуск?'))) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/content-runs/${selectedRun.run_id}/terminate`, {})
      await loadWorkspace(selectedRun.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const approve = async () => {
    if (!selectedRun || !selectedCreativeId || !actionable) return
    if (!confirmProduction(tr('Approve this Creative and unlock its export?', 'Схвалити цей креатив і відкрити експорт?'))) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/content-runs/${selectedRun.run_id}/review/approve`, {
        request_id: crypto.randomUUID(), creative_id: selectedCreativeId,
      })
      setNotice(tr('Creative approved. Owner learning was applied.', 'Креатив схвалено. Навчання від дії власника застосовано.'))
      await loadWorkspace(selectedRun.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const regenerateAll = async () => {
    if (!selectedRun || !actionable) return
    if (!confirmProduction(tr('Reject this set and generate five new directions?', 'Відхилити цей набір і створити п’ять нових напрямів?'))) return
    setBusy(true); setError('')
    try {
      const child = await api.post<ContentRun>(`/api/v1/content-runs/${selectedRun.run_id}/review/regenerate-all`, {
        request_id: crypto.randomUUID(),
      }, { deadlineMs: 60_000 })
      setNotice(tr('Rejection learning recorded. Five fresh directions are running.', 'Навчання з відхилення збережено. Створюються п’ять нових напрямів.'))
      onRunSelect(child.run_id); await loadWorkspace(child.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const tune = async () => {
    const instruction = comment.trim()
    if (!selectedRun || !selectedCreativeId || !actionable || instruction.length < 3) return
    if (!confirmProduction(tr('Record this instruction and tune only the selected Creative?', 'Зберегти цю інструкцію й налаштувати лише обраний креатив?'))) return
    setBusy(true); setError('')
    try {
      const child = await api.post<ContentRun>(`/api/v1/content-runs/${selectedRun.run_id}/review/tune`, {
        request_id: crypto.randomUUID(), creative_id: selectedCreativeId, comment: instruction,
      }, { deadlineMs: 60_000 })
      setComment(''); setNotice(tr('Tune instruction recorded. One replacement is running.', 'Інструкцію збережено. Створюється одна заміна.'))
      onRunSelect(child.run_id); await loadWorkspace(child.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retryNotification = async () => {
    if (!selectedRun) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/content-runs/${selectedRun.run_id}/review-notification/retry`, {})
      await loadRun(selectedRun.run_id)
      setNotice(tr('Notification retry completed.', 'Повторне сповіщення завершено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const download = async () => {
    if (!selectedRun?.approved_creative_id) return
    try {
      const blob = await api.download(
        `/api/v1/content-runs/${selectedRun.run_id}/creatives/${selectedRun.approved_creative_id}/export`,
        'application/zip', { deadlineMs: 60_000 },
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url
      link.download = `ptw-${platformFor(selectedRun)}-${selectedRun.approved_creative_id}.zip`
      link.click(); URL.revokeObjectURL(url)
    } catch (cause) { setError((cause as Error).message) }
  }

  const copyText = async (value: string, label: string) => {
    await navigator.clipboard.writeText(value)
    setNotice(tr(`${label} copied.`, `${label} скопійовано.`))
  }

  if (!briefs) return error
    ? <ErrorState message={error} retry={() => void loadWorkspace(runId)} language={language} />
    : <Loading language={language} />

  const selectedStageCopy = selectedRun ? stageCopy[selectedRun.current_stage] : null
  const statusLabel = selectedRun && selectedStageCopy
    ? translate(language, selectedStageCopy.en, selectedStageCopy.uk)
    : selectedRun?.current_stage || ''
  const approvedCreative = review?.creatives.find((item) => item.creative_id === selectedRun?.approved_creative_id) || null
  return <div className="social-page">
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
    <label className="social-project-picker">
      <FolderKanban aria-hidden="true" /><span>{tr('Project', 'Проєкт')}</span>
      <select aria-label={tr('Project', 'Проєкт')} value={projectId || ''} onChange={(event) => onProjectSelect(event.target.value)}>
        {!projectId && <option value="">{tr('Select a project', 'Виберіть проєкт')}</option>}
        {(projects || []).map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}
      </select>
    </label>
    <div className="social-workspace"><main className="social-detail">
      {selectedRun && !creating && <div className="social-detail-bar">
        <div>
          <span className={`review-chip ${selectedRun.status}`}>{statusLabel}</span>
          {availableRuns.length > 1
            ? <select aria-label={tr('Review set', 'Набір для перегляду')} value={selectedRun.run_id} onChange={(event) => onRunSelect(event.target.value)}>
              {availableRuns.map((run) => <option key={run.run_id} value={run.run_id}>{platformFor(run)} · R{(run.revision_number || 0) + 1} · {run.generation_kind}</option>)}
            </select>
            : <span>{platformFor(selectedRun)} · R{(selectedRun.revision_number || 0) + 1}</span>}
        </div>
        <button className="primary" onClick={() => setCreating(true)} disabled={!projectId}><Plus />{tr('New set', 'Новий набір')}</button>
      </div>}

      {creating && <section className="social-create-card">
        <header><div><small>{tr('NEW CREATIVE SET', 'НОВИЙ НАБІР КРЕАТИВІВ')}</small><h2>{tr('Generate five posts', 'Створити п’ять дописів')}</h2></div><button className="ghost" onClick={() => setCreating(false)} aria-label={tr('Close', 'Закрити')}><X /></button></header>
        <div className="platform-choice" role="radiogroup" aria-label={tr('Platform', 'Платформа')}>
          <button role="radio" aria-checked={platform === 'instagram'} className={platform === 'instagram' ? 'selected' : ''} onClick={() => setPlatform('instagram')}><Square />Instagram<span>1080 × 1080</span></button>
          {!localDemo && <button role="radio" aria-checked={platform === 'tiktok'} className={platform === 'tiktok' ? 'selected' : ''} onClick={() => setPlatform('tiktok')}><Smartphone />TikTok<span>1080 × 1920</span></button>}
        </div>
        {approvedBriefs.length > 1
          ? <label>{tr('Approved Product Brief', 'Схвалений продуктовий бриф')}<select value={briefId} onChange={(event) => setBriefId(event.target.value)}>{approvedBriefs.map((item) => <option key={item.brief_id} value={item.brief_id}>{item.product}</option>)}</select></label>
          : approvedBriefs[0] && <p className="social-brief-choice"><Check />{approvedBriefs[0].product}</p>}
        {!approvedBriefs.length && <div className="social-no-brief"><p>{tr('Approve a completed Product Brief first.', 'Спочатку схваліть завершений продуктовий бриф.')}</p><button className="secondary" onClick={onOpenBriefs}>{tr('Open Product Briefs', 'Відкрити продуктові брифи')}</button></div>}
        <button className="primary large" disabled={busy || !briefId} onClick={() => void create()}><Sparkles />{tr('Generate five', 'Створити п’ять')}</button>
      </section>}

      {!projectId && <Empty><FolderKanban className="empty-mark" /><h2>{tr('Select or create a Project', 'Виберіть або створіть проєкт')}</h2></Empty>}
      {projectId && !selectedRun && !creating && <Empty><Sparkles className="empty-mark" /><h2>{tr('Create the first five-post set', 'Створіть перший набір із п’яти дописів')}</h2><button className="primary" onClick={() => setCreating(true)}><Plus />{tr('New set', 'Новий набір')}</button></Empty>}

      {selectedRun && <section className="social-artifact">
        {ACTIVE.has(selectedRun.status) && <div className="social-progress">
          <div className="social-progress-header"><div className="social-progress-state" role="status"><RefreshCcw className="spin" /><div><strong>{statusLabel}</strong><span>{selectedRun.progress_percent}% · {tr('bounded maximum 45 minutes', 'максимум 45 хвилин')}</span></div></div>
            {localDemo && <button className="secondary terminate-run" disabled={busy} onClick={() => void terminate()}><CircleStop />{tr('Terminate run', 'Зупинити запуск')}</button>}
          </div><progress max={100} value={selectedRun.progress_percent} />
        </div>}
        {selectedRun.status === 'failed' && <div className="social-failure"><h2>{tr('Generation failed', 'Створення не вдалося')}</h2><p>{selectedRun.error_message || selectedRun.error_code}</p><button className="secondary" disabled={busy} onClick={() => void retry()}><RefreshCcw />{tr('Retry generation', 'Повторити створення')}</button></div>}
        {selectedRun.status === 'terminated' && <div className="social-failure"><h2>{tr('Run terminated', 'Запуск зупинено')}</h2><p>{tr('Generated evidence remains immutable.', 'Створені дані залишаються незмінними.')}</p><button className="secondary" disabled={busy} onClick={() => void retry()}><RefreshCcw />{tr('Retry generation', 'Повторити створення')}</button></div>}
        {selectedRun.status === 'superseded' && <p className="notice">{tr('This set was superseded only after its child set became reviewable.', 'Цей набір замінено лише після того, як дочірній набір став доступним для перегляду.')}</p>}

        {review && <>
          {review.notification && review.notification.status !== 'delivered' && <section className={`notification-state ${review.notification.status}`} role="status">
            <div><strong>{review.notification.status === 'ambiguous' ? tr('Telegram delivery is ambiguous', 'Статус доставки Telegram неоднозначний') : tr('Telegram notification failed', 'Сповіщення Telegram не надіслано')}</strong><p>{review.notification.error_message || tr('The five posts remain reviewable here.', 'П’ять дописів доступні для перегляду тут.')}</p></div>
            <button className="secondary" disabled={busy || review.notification.status === 'pending'} onClick={() => void retryNotification()}><RefreshCcw />{tr('Retry notification', 'Повторити сповіщення')}</button>
          </section>}
          <CreativeReviewGrid api={api} creatives={review.creatives} selectedCreativeId={selectedCreativeId} approvedCreativeId={selectedRun.approved_creative_id} actionable={actionable || selectedRun.status === 'approved'} onSelect={setSelectedCreativeId} language={language} />
          {selectedRun.status === 'awaiting_review' && <aside className="owner-review-actions">
            <div><small>{tr('OWNER ACTION', 'ДІЯ ВЛАСНИКА')}</small><h2>{tr('Teach through your decision', 'Навчайте своїм рішенням')}</h2><p>{tr('The chosen action is persisted immediately and affects future generation.', 'Обрана дія одразу зберігається й впливає на майбутні генерації.')}</p></div>
            <label>{tr('Tune comment for the selected post', 'Коментар для налаштування обраного допису')}<textarea minLength={3} maxLength={2000} value={comment} onChange={(event) => setComment(event.target.value)} placeholder={tr('Keep this direction, but make the headline calmer…', 'Збережіть цей напрям, але зробіть заголовок спокійнішим…')} /></label>
            <div className="owner-review-buttons">
              <button className="primary" disabled={busy || !actionable || !selectedCreativeId} onClick={() => void approve()}><Check />{tr('Approve', 'Схвалити')}</button>
              <button className="secondary" disabled={busy || !actionable || !selectedCreativeId || comment.trim().length < 3} onClick={() => void tune()}><Send />{tr('Tune selected', 'Налаштувати обраний')}</button>
              <button className="secondary danger" disabled={busy || !actionable} onClick={() => void regenerateAll()}><RefreshCcw />{tr('Regenerate all', 'Перегенерувати всі')}</button>
            </div>
            {actionProcessing && <p className="notice">{tr('An owner action is already in progress.', 'Дія власника вже виконується.')}</p>}
          </aside>}
        </>}

        {selectedRun.status === 'approved' && approvedCreative && <section className="approved-result">
          <div><small>{tr('APPROVED POST', 'СХВАЛЕНИЙ ДОПИС')}</small><h2>{tr('Native post and export', 'Нативний допис та експорт')}</h2></div>
          <div className="social-review-layout">
            <div className="social-preview-column"><ApprovedPost api={api} run={selectedRun} creative={approvedCreative} projectName={selectedProject?.name || 'Natal'} language={language} /></div>
            <aside className="social-review-panel"><small>{tr('EXPORT PACKAGE', 'ПАКЕТ ЕКСПОРТУ')}</small><h2>{tr('Unlocked', 'Відкрито')}</h2>
              <button className="secondary" onClick={() => void download()}><Download />{tr('Download export', 'Завантажити експорт')}</button>
              <button className="ghost" onClick={() => void copyText(approvedCreative.document.caption, tr('Caption', 'Підпис'))}><Copy />{tr('Copy caption', 'Копіювати підпис')}</button>
              <button className="ghost" onClick={() => void copyText(approvedCreative.document.alt_text, tr('Alt text', 'Альтернативний текст'))}><Copy />{tr('Copy alt text', 'Копіювати alt text')}</button>
              <code>{approvedCreative.creative_id}</code>
            </aside>
          </div>
        </section>}

        {review && <section className="review-learning-evidence">
          <header><Brain /><div><h2>{tr('Owner learning', 'Навчання від власника')}</h2><p>{tr('Actions and active Project rules; no scores or rankings.', 'Дії та активні правила Проєкту; без оцінок і рейтингів.')}</p></div></header>
          <div className="learning-rule-grid"><section><h3>{tr('Owner actions', 'Дії власника')}</h3>{review.owner_actions.length === 0 ? <p>{tr('No action yet.', 'Дій ще немає.')}</p> : <ul>{review.owner_actions.map((action) => <li key={action.action_id}><strong>{action.action_type} · {action.status}</strong><small>{action.creative_id || action.child_run_id || action.action_id}</small>{action.comment && <p>{action.comment}</p>}</li>)}</ul>}</section>
            <section><h3>{tr('Applied Project rules', 'Застосовані правила Проєкту')}</h3>{review.applied_project_rules.length === 0 ? <p>{tr('No owner rules yet.', 'Правил власника ще немає.')}</p> : <ul>{review.applied_project_rules.map((rule) => <li key={rule.rule_id}><strong>{rule.rule_type}</strong><small>{rule.strategy_id || rule.output_profile || tr('Project scope', 'Рівень Проєкту')}</small>{rule.instruction && <p>{rule.instruction}</p>}</li>)}</ul>}</section>
          </div>
        </section>}
      </section>}
    </main></div>

  </div>
}
