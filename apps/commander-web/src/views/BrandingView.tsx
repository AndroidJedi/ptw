import { Check, Download, Pause, Play, Plus, RefreshCw, RotateCcw, Send, ShieldAlert, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { AnnotationCanvas } from '../components/AnnotationCanvas'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type {
  BrandCandidate, BrandDirection, BrandKit, BrandReview, BrandRun, BrandStatus,
  I18n, Region,
} from '../types'
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
    pending: 'Очікує', running: 'Виконується', paused: 'Призупинено', awaiting_review: 'Потрібен відгук',
    completed: 'Завершено', failed: 'Помилка', stale: 'Застаріло',
  } as Record<string, string>)[status] || status
}

function Logo({ api, direction }: { api: ApiClient; direction: BrandDirection }) {
  const [src, setSrc] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (!direction.logo_asset?.url) return
    let active = true
    let objectUrl = ''
    void api.blob(direction.logo_asset.url).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (active) setSrc(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    }).catch((cause: Error) => active && setError(cause.message))
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, direction.logo_asset?.url])
  if (error) return <div className="brand-logo-error">Лого недоступне</div>
  return src ? <img src={src} alt={`Символ напряму ${direction.name}`} /> : <div className="brand-logo-loading">PTW</div>
}

function ReviewLogo({ api, direction, regions, onChange }: {
  api: ApiClient; direction: BrandDirection; regions: Region[]; onChange: (regions: Region[]) => void
}) {
  const [src, setSrc] = useState('')
  useEffect(() => {
    if (!direction.logo_asset?.url) return
    let active = true
    let objectUrl = ''
    void api.blob(direction.logo_asset.url).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (active) setSrc(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, direction.logo_asset?.url])
  return src
    ? <AnnotationCanvas src={src} alt={`Лого ${direction.name}`} regions={regions} onChange={onChange} />
    : <Loading />
}

function CandidateCard({ item, language, selected, onSelect }: {
  item: BrandCandidate; language: Language; selected: boolean; onSelect: () => void
}) {
  const quality = item.quality.attempted ? Math.round(item.quality.successful / item.quality.attempted * 100) : 0
  return <button className={`brand-candidate ${selected ? 'selected' : ''}`} onClick={onSelect} type="button">
    <div><span>{item.active_brand_kit ? `KIT · ${item.active_brand_kit.name} · ${item.active_brand_kit.status}` : 'ГОТОВА ІДЕЯ'}</span><time>{new Date(item.created_at).toLocaleDateString('uk-UA')}</time></div>
    <h3>{item.owner_idea}</h3>
    <div className="brand-candidate-theses">{item.theses.map((thesis) => <section key={thesis.id}>
      <strong>{thesis.recommended ? '★ РЕКОМЕНДОВАНО · ' : ''}{text(thesis.title, language)}</strong>
      <p><b>Для кого:</b> {text(thesis.target_user, language)}</p>
      <ol>{thesis.loop_steps.map((step, index) => <li key={index}>{text(step, language)}</li>)}</ol>
    </section>)}</div>
    <footer><span>{item.theses.length} тез</span><span>Якість доказів {quality}%</span></footer>
  </button>
}

function DirectionPreview({ direction, theme }: { direction: BrandDirection; theme: 'light' | 'dark' }) {
  const palette = direction.manifest.palette[theme]
  const style = {
    color: palette.text,
    background: palette.background,
    fontFamily: `'${direction.manifest.typography.body}', system-ui, sans-serif`,
  }
  return <div className="brand-ui-preview" style={style} data-theme={theme}>
    <small style={{ color: palette.muted }}>НАСТУПНИЙ ДОКАЗ</small>
    <h4 style={{ fontFamily: `'${direction.manifest.typography.display}', system-ui, sans-serif` }}>Ваш прогрес видно</h4>
    <p>Збережіть результат і відкрийте наступний крок.</p>
    <div><button style={{ color: palette.background, background: palette.primary }}>Додати доказ</button><span style={{ color: palette.text, background: palette.surface }}>Серія · 4 дні</span></div>
  </div>
}

export function BrandingView({ api, language, initialRunId }: {
  api: ApiClient; language: Language; initialRunId?: string
}) {
  const [candidates, setCandidates] = useState<BrandCandidate[] | null>(null)
  const [runs, setRuns] = useState<BrandRun[] | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState('')
  const [selectedRun, setSelectedRun] = useState(initialRunId || '')
  const [status, setStatus] = useState<BrandStatus | null>(null)
  const [selectedDirection, setSelectedDirection] = useState('')
  const [selectedStage, setSelectedStage] = useState('')
  const [stageOutput, setStageOutput] = useState<unknown>(null)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [constraints, setConstraints] = useState('')
  const [referenceUrls, setReferenceUrls] = useState('')
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [regions, setRegions] = useState<Region[]>([])
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [history, setHistory] = useState<BrandReview[]>([])
  const [kit, setKit] = useState<BrandKit | null>(null)
  const [readiness, setReadiness] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadLists = () => {
    setError('')
    return Promise.all([
      api.get<{ items: BrandCandidate[] }>('/api/v1/branding/cases?limit=50'),
      api.get<{ items: BrandRun[] }>('/api/v1/branding/runs?limit=50'),
      api.get<Record<string, unknown>>('/api/v1/branding/providers'),
    ]).then(([caseData, runData, providerData]) => {
      setCandidates(caseData.items); setRuns(runData.items); setReadiness(providerData)
      if (!selectedRun && runData.items[0]) setSelectedRun(runData.items[0].id)
      if (!selectedCandidate && caseData.items[0]) setSelectedCandidate(caseData.items[0].idea_run_id)
    }).catch((cause: Error) => setError(cause.message))
  }

  const loadRun = (runId = selectedRun) => {
    if (!runId) { setStatus(null); return Promise.resolve() }
    return api.get<BrandStatus>(`/api/v1/branding/runs/${runId}`).then((data) => {
      setStatus(data)
      setKit(null)
      setSelectedDirection((current) => current && data.directions.some((item) => item.id === current) ? current : data.directions[0]?.id || '')
      if (data.run.commander_brand_kit_id) {
        void api.get<BrandKit>(`/api/v1/branding/kits/${data.run.commander_brand_kit_id}`).then(setKit).catch(() => undefined)
      }
    }).catch((cause: Error) => setError(cause.message))
  }

  useEffect(() => { void loadLists() }, [api])
  useEffect(() => { void loadRun() }, [api, selectedRun])
  useEffect(() => {
    if (!status || !['pending', 'running'].includes(status.run.status)) return
    const timer = window.setInterval(() => { void loadRun() }, 2500)
    return () => window.clearInterval(timer)
  }, [api, selectedRun, status?.run.status])

  const direction = useMemo(
    () => status?.directions.find((item) => item.id === selectedDirection) || null,
    [status, selectedDirection],
  )

  useEffect(() => {
    setRegions(direction?.annotations || [])
    setRating(direction?.rating || 0)
    setComment(direction?.overall_comment || '')
    setHistory([])
    if (!direction || !selectedRun) return
    void api.get<{ items: BrandReview[] }>(`/api/v1/branding/runs/${selectedRun}/directions/${direction.id}/reviews`)
      .then((data) => setHistory(data.items)).catch(() => undefined)
  }, [api, direction?.id, selectedRun])

  const create = async () => {
    if (!selectedCandidate) return
    setBusy(true); setError('')
    try {
      const created = await api.post<{ run_id: string }>('/api/v1/branding/runs', {
        idea_run_id: selectedCandidate,
        constraints,
        reference_urls: referenceUrls.split(/\n/).map((value) => value.trim()).filter(Boolean),
        manual_transcripts: transcripts.filter((item) => item.video_url && item.transcript),
      })
      setCreateOpen(false); setSelectedRun(created.run_id); await loadLists()
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
    if (!direction || !rating) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/branding/runs/${selectedRun}/directions/${direction.id}/review`, { rating, comment, annotations: regions })
      setRegions([]); setComment(''); await loadRun()
      const reviews = await api.get<{ items: BrandReview[] }>(`/api/v1/branding/runs/${selectedRun}/directions/${direction.id}/reviews`)
      setHistory(reviews.items)
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

  if (!candidates || !runs) return error ? <ErrorState message={error} retry={loadLists} /> : <Loading />
  const reviewed = status?.directions.filter((item) => item.latest_feedback_id).length || 0
  return <>
    <PageHeader eyebrow="BRANDING V1" title="Брендинг" />
    {error && <div className="laval-error" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Закрити"><X /></button></div>}
    <div className="brand-toolbar">
      <div><small>ПРОВАЙДЕР</small><strong>{String(readiness?.provider || '—')} · SEO вимкнено</strong></div>
      <button className="primary" onClick={() => setCreateOpen(true)} disabled={!candidates.length}><Plus />Новий бренд</button>
    </div>
    {createOpen && <section className="brand-create" role="dialog" aria-modal="true" aria-label="Новий Branding запуск">
      <header><div><small>КРОК 1</small><h2>Оберіть завершену ідею</h2></div><button onClick={() => setCreateOpen(false)} aria-label="Закрити"><X /></button></header>
      <div className="brand-candidates">{candidates.map((item) => <CandidateCard key={item.idea_run_id} item={item} language={language} selected={selectedCandidate === item.idea_run_id} onSelect={() => setSelectedCandidate(item.idea_run_id)} />)}</div>
      {candidates.length === 0 && <Empty><h2>Немає готових live-ідей</h2><p>Завершіть Idea Laval із хоча б однією тезою, що вижила.</p></Empty>}
      <label>Вільні обмеження бренду<textarea rows={3} maxLength={4000} value={constraints} onChange={(event) => setConstraints(event.target.value)} placeholder="Тон, заборонені асоціації, аудиторні нюанси…" /></label>
      <label>Референсні HTTPS URL — один на рядок<textarea rows={3} value={referenceUrls} onChange={(event) => setReferenceUrls(event.target.value)} placeholder="https://…" /></label>
      <div className="brand-transcripts"><div><strong>Ручні YouTube-транскрипти</strong><button type="button" className="secondary" disabled={transcripts.length >= 5} onClick={() => setTranscripts([...transcripts, { title: '', video_url: '', transcript: '' }])}><Plus />Додати</button></div>
        {transcripts.map((item, index) => <article key={index}><input value={item.title} onChange={(event) => setTranscripts(transcripts.map((value, itemIndex) => itemIndex === index ? { ...value, title: event.target.value } : value))} placeholder="Назва відео" /><input value={item.video_url} onChange={(event) => setTranscripts(transcripts.map((value, itemIndex) => itemIndex === index ? { ...value, video_url: event.target.value } : value))} placeholder="https://youtube.com/watch?v=…" /><textarea rows={3} maxLength={10_000} value={item.transcript} onChange={(event) => setTranscripts(transcripts.map((value, itemIndex) => itemIndex === index ? { ...value, transcript: event.target.value } : value))} placeholder="Неперевірений текст власника" /><button type="button" onClick={() => setTranscripts(transcripts.filter((_value, itemIndex) => itemIndex !== index))}>Видалити</button></article>)}
      </div>
      <button className="primary large" disabled={!selectedCandidate || busy} onClick={() => void create()}>{busy ? 'Запуск…' : 'Створити й запустити'}</button>
    </section>}
    {runs.length === 0 ? <Empty><h2>Ще немає Branding-запусків</h2><p>Оберіть завершену Idea справу — перевірка оцінок не потрібна.</p></Empty> : <div className="brand-layout">
      <nav className="brand-runs" aria-label="Branding запуски">{runs.map((run) => <button key={run.id} className={selectedRun === run.id ? 'selected' : ''} onClick={() => setSelectedRun(run.id)}><span><i className={`status-dot ${run.status}`} />{statusLabel(run.status)}</span><strong>{run.owner_preview || 'Branding run'}</strong><small>{run.completed_stages || 0}/10 етапів</small></button>)}</nav>
      <section className="brand-workspace">
        {!status ? <Loading /> : <>
          <header className="brand-run-head"><div><small>{statusLabel(status.run.status)}</small><h2>{status.run.source_snapshot.owner_idea}</h2><p>{reviewed}/3 лого мають актуальний відгук · ${status.cost.total_usd.toFixed(4)}</p></div><div className="brand-actions">
            {status.run.status === 'running' && <button className="secondary" disabled={busy} onClick={() => void control('pause')}><Pause />Пауза</button>}
            {['paused', 'failed'].includes(status.run.status) && <button className="primary" disabled={busy} onClick={() => void control('resume')}><Play />Продовжити</button>}
            {status.run.status === 'failed' && <button className="secondary" disabled={busy} onClick={() => void control('rerun')}><RotateCcw />Перезапустити етап</button>}
            <button className="secondary" disabled={busy} onClick={() => { void loadRun(); void loadLists() }}><RefreshCw />Оновити</button>
          </div></header>
          {status.run.source_stale && <p className="brand-warning"><ShieldAlert />Idea справа змінилась. Kit лишається доступним в історії, але не може створювати нові пости.</p>}
          <div className="brand-stages">{status.stages.map((stage) => <button key={stage.stage} className={`${stage.status} ${selectedStage === stage.stage ? 'selected' : ''}`} onClick={() => void inspect(stage.stage)}><span>{String(stage.ordinal + 1).padStart(2, '0')}</span><strong>{stage.stage.replaceAll('_', ' ')}</strong><small>{statusLabel(stage.status)} · спроба {stage.attempt}</small></button>)}</div>
          {selectedStage && <details className="brand-inspector" open><summary>{selectedStage} · вхід та артефакт</summary><pre>{stageOutput ? JSON.stringify(stageOutput, null, 2) : 'Завантаження…'}</pre></details>}
          {status.directions.length > 0 && <>
            <div className="brand-section-head"><div><small>ТРИ НЕЗАЛЕЖНІ НАПРЯМИ</small><h2>Оберіть і перевірте кожне лого</h2></div><div className="brand-theme"><button className={theme === 'light' ? 'selected' : ''} onClick={() => setTheme('light')}>Світла</button><button className={theme === 'dark' ? 'selected' : ''} onClick={() => setTheme('dark')}>Темна</button></div></div>
            <div className="brand-directions">{status.directions.map((item) => <button key={item.id} className={selectedDirection === item.id ? 'selected' : ''} onClick={() => setSelectedDirection(item.id)}><Logo api={api} direction={item} /><span>{item.ordinal}/3 · {item.latest_feedback_id ? `✓ ${item.rating}/5` : 'потрібен відгук'}</span><h3>{item.name}</h3><p>{text(item.manifest.tagline, language)}</p></button>)}</div>
          </>}
          {direction && <div className="brand-direction-detail">
            <div className="brand-review-visual"><div className="brand-logo-large"><Logo api={api} direction={direction} /></div><div className="brand-palette">{Object.entries(direction.manifest.palette[theme]).map(([name, color]) => <div key={name}><i style={{ background: color }} /><span>{name}<b>{color}</b></span></div>)}</div><DirectionPreview direction={direction} theme={theme} /></div>
            <aside className="brand-review-panel"><small>НАПРЯМ {direction.ordinal}</small><h2>{direction.name}</h2><p>{text(direction.manifest.positioning, language)}</p><dl><div><dt>Display</dt><dd>{direction.manifest.typography.display}</dd></div><div><dt>Body</dt><dd>{direction.manifest.typography.body}</dd></div></dl><ul>{direction.manifest.design_principles.map((item) => <li key={item}>{item}</li>)}</ul>
              {direction.logo_asset && <ReviewLogo api={api} direction={direction} regions={regions} onChange={setRegions} />}
              {direction.latest_feedback_id && <p className="correction-note">Нове збереження додасть незмінне виправлення через <code>supersedes</code>.</p>}
              <fieldset><legend>Оцінка лого</legend><div className="rating">{[1, 2, 3, 4, 5].map((value) => <button type="button" key={value} className={rating === value ? 'selected' : ''} onClick={() => setRating(value)}>{value}</button>)}</div></fieldset>
              <label>Загальний коментар<textarea rows={3} value={comment} onChange={(event) => setComment(event.target.value)} /></label>
              <button className="primary large" disabled={!rating || busy} onClick={() => void review()}><Send />{direction.latest_feedback_id ? 'Зберегти виправлення' : 'Надіслати відгук'}</button>
              {history.length > 0 && <details className="review-history"><summary>Історія відгуків · {history.length}</summary>{history.map((item) => <article key={item.feedback_id}><strong>{item.rating}/5</strong><p>{item.overall_comment || 'Без коментаря'}</p><small>{new Date(item.created_at).toLocaleString('uk-UA')}</small></article>)}</details>}
            </aside>
          </div>}
          {direction && status.run.status === 'awaiting_review' && <section className="brand-approval"><ShieldAlert /><div><strong>Перевірка назви обмежена</strong><p>Виконано лише collision screen проти конкурентів і брендів PTW. Domain and trademark clearance are not performed.</p></div><button className="primary" disabled={reviewed !== 3 || busy || status.run.source_stale} onClick={() => void approve()}><Check />Затвердити {direction.name}</button></section>}
          {kit && <section className="brand-kit-ready"><Check /><div><small>IMMUTABLE BRAND KIT</small><h2>{kit.name}</h2><p>{kit.status === 'stale' ? 'Історичний, застарілий Kit' : 'React/TypeScript UI kit готовий'}</p></div><button className="primary" disabled={busy || !kit.download} onClick={() => void download()}><Download />Завантажити ZIP</button></section>}
        </>}
      </section>
    </div>}
  </>
}
