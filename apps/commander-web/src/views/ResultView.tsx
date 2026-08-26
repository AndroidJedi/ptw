import { Check, Download, Image, RefreshCcw, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'
import type {
  ContentResult, ContentRun, OutputProfile, ProductBrief, ProjectAsset, ProjectBrandKit,
} from '../types'

const ACTIVE = new Set(['queued', 'generating'])

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

async function base64(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000))
  }
  return window.btoa(binary)
}

function ResultContent({ value, language }: { value: ContentResult; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <article className="result-card">
    <small>{tr('FINAL RESULT', 'ФІНАЛЬНИЙ РЕЗУЛЬТАТ')}</small>
    <h2>{value.content.hook}</h2>
    <h3>{value.content.headline}</h3>
    <p>{value.content.primary_text}</p>
    <p className="muted-copy">{value.content.supporting_text}</p>
    <div className="result-offer"><strong>{value.content.offer}</strong><span>{value.content.cta}</span></div>
    {value.content.caption && <section><small>{tr('CAPTION', 'ПІДПИС')}</small><p>{value.content.caption}</p></section>}
  </article>
}

export function ResultView({ api, projectId, language }: { api: ApiClient; projectId: string | null; language: Language }) {
  const [briefs, setBriefs] = useState<ProductBrief[] | null>(null)
  const [runs, setRuns] = useState<ContentRun[]>([])
  const [assets, setAssets] = useState<ProjectAsset[]>([])
  const [kits, setKits] = useState<ProjectBrandKit[]>([])
  const [selectedRun, setSelectedRun] = useState<ContentRun | null>(null)
  const [result, setResult] = useState<ContentResult | null>(null)
  const [assetUrl, setAssetUrl] = useState('')
  const [task, setTask] = useState('')
  const [profile, setProfile] = useState<OutputProfile>('marketing_copy_v1')
  const [brandName, setBrandName] = useState('')
  const [tone, setTone] = useState('Direct, conversational, specific, and honest.')
  const [logoId, setLogoId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [debug, setDebug] = useState<Record<string, unknown> | null>(null)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  const approved = useMemo(
    () => briefs?.find((item) => item.approved && item.status === 'completed') || null,
    [briefs],
  )

  const load = async (preferredRunId?: string) => {
    if (!projectId) {
      setBriefs([]); setRuns([]); setAssets([]); setKits([]); setSelectedRun(null); setResult(null)
      return
    }
    const [briefValue, runValue, assetValue, kitValue] = await Promise.all([
      api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: ContentRun[] }>(`/api/v1/content-runs?limit=50&project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: ProjectAsset[] }>(`/api/v1/project-assets?project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: ProjectBrandKit[] }>(`/api/v1/project-brand-kits?project_id=${encodeURIComponent(projectId)}`),
    ])
    setBriefs(briefValue.items); setRuns(runValue.items); setAssets(assetValue.items); setKits(kitValue.items)
    if (kitValue.items[0]) {
      setBrandName((current) => current || kitValue.items[0].document.name)
      setTone((current) => current || kitValue.items[0].document.tone_notes)
      setLogoId((current) => current || kitValue.items[0].document.logo_source_asset_id || '')
    }
    const runId = preferredRunId || selectedRun?.run_id || runValue.items[0]?.run_id
    if (!runId) { setSelectedRun(null); setResult(null); return }
    const run = await api.get<ContentRun>(`/api/v1/content-runs/${runId}`)
    setSelectedRun(run)
    if (run.status === 'completed') {
      setResult(await api.get<ContentResult>(`/api/v1/content-runs/${runId}/result`))
    } else setResult(null)
  }

  useEffect(() => {
    setBriefs(null); setSelectedRun(null); setResult(null); setError(''); setDebug(null)
    void load().catch((cause: Error) => setError(cause.message))
  }, [api, projectId])

  useEffect(() => {
    if (!selectedRun || !ACTIVE.has(selectedRun.status)) return
    const timer = window.setInterval(() => {
      void load(selectedRun.run_id).catch((cause: Error) => setError(cause.message))
    }, 2000)
    return () => window.clearInterval(timer)
  }, [selectedRun?.run_id, selectedRun?.status])

  useEffect(() => {
    if (!result?.asset_url) { setAssetUrl(''); return }
    let local = ''
    if (!result.asset_sha256) { setError(tr('Rendered Result is missing its asset digest.', 'У відрендереного Result відсутній цифровий відбиток файлу.')); return }
    void api.image(result.asset_url, 'image/jpeg', result.asset_sha256)
      .then((blob) => {
        if (!(blob instanceof Blob)) return
        local = URL.createObjectURL(blob); setAssetUrl(local)
      })
      .catch((cause: Error) => setError(cause.message))
    return () => { if (local) URL.revokeObjectURL(local) }
  }, [api, result?.creative_id])

  const create = async () => {
    if (!approved || !task.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const run = await api.post<ContentRun>('/api/v1/content-runs', {
        request_id: crypto.randomUUID(), brief_id: approved.brief_id,
        task: task.trim(), output_profile: profile,
      }, { deadlineMs: 60_000 })
      setSelectedRun(run); setResult(null); setTask(''); setNotice(tr('Result creation started.', 'Створення результату розпочато.'))
      await load(run.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const upload = async (file: File) => {
    if (!projectId) return
    setBusy(true); setError('')
    try {
      const item = await api.post<ProjectAsset>('/api/v1/project-assets', {
        project_id: projectId, title: file.name, mime_type: file.type,
        bytes_base64: await base64(file),
      }, { deadlineMs: 60_000 })
      setAssets((current) => [item, ...current]); setLogoId(item.source_asset_id)
      setNotice(tr('Approved Project asset added.', 'Схвалений файл проєкту додано.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const saveBrand = async () => {
    if (!projectId || !brandName.trim()) return
    setBusy(true); setError('')
    try {
      const item = await api.post<ProjectBrandKit>('/api/v1/project-brand-kits', {
        project_id: projectId,
        parent_brand_kit_id: kits[0]?.brand_kit_id || null,
        document: {
          name: brandName.trim(), colors: ['#111111', '#FFFFFF', '#43BDD3', '#F4F2EC'],
          fonts: ['Inter'], tone_notes: tone.trim(), logo_source_asset_id: logoId || null,
        },
      })
      setKits((current) => [item, ...current]); setNotice(tr('Project brand kit saved.', 'Бренд-кит проєкту збережено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retry = async () => {
    if (!selectedRun) return
    setBusy(true); setError('')
    try {
      const child = await api.post<ContentRun>(`/api/v1/content-runs/${selectedRun.run_id}/retry`, {
        request_id: crypto.randomUUID(),
      }, { deadlineMs: 60_000 })
      await load(child.run_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const feedback = async (decision: 'accepted' | 'rejected') => {
    if (!selectedRun) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/content-runs/${selectedRun.run_id}/feedback`, { decision })
      setNotice(decision === 'accepted' ? tr('Result accepted.', 'Результат прийнято.') : tr('Result rejected. Feedback recorded.', 'Результат відхилено. Відгук збережено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const download = async () => {
    if (!selectedRun || !result) return
    await api.post(`/api/v1/content-runs/${selectedRun.run_id}/outcomes`, { event_type: 'downloaded' })
    const local = assetUrl || URL.createObjectURL(new Blob([
      [result.content.hook, result.content.headline, result.content.primary_text,
        result.content.supporting_text, result.content.offer, result.content.cta,
        result.content.caption].filter(Boolean).join('\n\n'),
    ], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a'); link.href = local
    link.download = `ptw-result.${assetUrl ? 'jpg' : 'txt'}`; link.click()
    if (!assetUrl) URL.revokeObjectURL(local)
    setNotice(tr('Result downloaded and recorded.', 'Результат завантажено та зафіксовано.'))
  }

  const useResult = async () => {
    if (!selectedRun) return
    await api.post(`/api/v1/content-runs/${selectedRun.run_id}/outcomes`, { event_type: 'used' })
    setNotice(tr('Result use recorded.', 'Використання результату зафіксовано.'))
  }

  if (!briefs) return error ? <ErrorState message={error} retry={() => void load()} language={language} /> : <Loading language={language} />
  return <>
    <PageHeader eyebrow={tr('ONE TASK · ONE FINAL CREATIVE', 'ОДНЕ ЗАВДАННЯ · ОДИН ФІНАЛЬНИЙ КРЕАТИВ')} title={tr('Result', 'Результат')} />
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
    {!projectId ? <Empty><Sparkles className="empty-mark" /><h2>{tr('Select or create a Project', 'Виберіть або створіть проєкт')}</h2></Empty> : <>
      {(!kits.length || (profile === 'instagram_static_ad_v1' && !kits[0]?.document.logo_source_asset_id)) && <section className="panel brand-setup"><small>{tr('PROJECT BRAND KIT', 'БРЕНД-КИТ ПРОЄКТУ')}</small><h2>{tr('Set the approved visual identity', 'Налаштуйте схвалену візуальну айдентику')}</h2>
        <label>{tr('Brand name', 'Назва бренду')}<input value={brandName} maxLength={120} onChange={(event) => setBrandName(event.target.value)} /></label>
        <label>{tr('Tone notes', 'Нотатки про тон')}<textarea rows={3} value={tone} maxLength={500} onChange={(event) => setTone(event.target.value)} /></label>
        <label className="asset-upload"><Image />{tr('Upload approved logo or brand image', 'Завантажте схвалений логотип або зображення бренду')}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file) }} /></label>
        {!!assets.length && <label>{tr('Logo', 'Логотип')}<select value={logoId} onChange={(event) => setLogoId(event.target.value)}><option value="">{tr('Select asset', 'Виберіть файл')}</option>{assets.filter((item) => item.approval_status === 'approved').map((item) => <option key={item.source_asset_id} value={item.source_asset_id}>{item.title}</option>)}</select></label>}
        <button className="secondary" disabled={busy || !brandName.trim()} onClick={saveBrand}><Check />{tr('Save brand kit', 'Зберегти бренд-кит')}</button>
      </section>}

      <section className="panel result-create">
        <div><small>{tr('SOURCE', 'ДЖЕРЕЛО')}</small><h2>{approved?.product || tr('Approved Product Brief required', 'Потрібен схвалений продуктовий бриф')}</h2><p>{approved?.promise || tr('Approve a completed Brief before creating a Result.', 'Схваліть завершений бриф перед створенням Result.')}</p></div>
        <fieldset><legend>{tr('Result type', 'Тип результату')}</legend>
          <label><input type="radio" checked={profile === 'marketing_copy_v1'} onChange={() => setProfile('marketing_copy_v1')} /> {tr('Text', 'Текст')}</label>
          <label><input type="radio" checked={profile === 'instagram_static_ad_v1'} onChange={() => setProfile('instagram_static_ad_v1')} /> {tr('Instagram post', 'Допиc в Instagram')}</label>
        </fieldset>
        <label>{tr('Task', 'Завдання')}<textarea rows={5} maxLength={4000} value={task} onChange={(event) => setTask(event.target.value)} placeholder={tr('Describe the one result you need…', 'Опишіть один потрібний результат…')} /></label>
        <button className="primary large" disabled={busy || !approved || !kits.length || !task.trim() || (profile === 'instagram_static_ad_v1' && !kits[0]?.document.logo_source_asset_id)} onClick={create}><Sparkles />{tr('Create result', 'Створити результат')}</button>
        {!kits.length && <p className="generation-state">{tr('Save the Project brand kit above before creating a Result.', 'Збережіть бренд-кит проєкту вище перед створенням Result.')}</p>}
        {profile === 'instagram_static_ad_v1' && !!kits.length && !kits[0]?.document.logo_source_asset_id && <p className="generation-state">{tr('Add an approved logo to the latest brand kit above before creating an Instagram post.', 'Додайте схвалений логотип до найновішого бренд-киту вище перед створенням допису в Instagram.')}</p>}
      </section>

      {selectedRun && <section className="panel result-progress">
        <small>{tr('RESULT CREATION', 'СТВОРЕННЯ РЕЗУЛЬТАТУ')}</small>
        {ACTIVE.has(selectedRun.status) && <><h2><RefreshCcw className="spin" /> {translate(language, stageCopy[selectedRun.current_stage].en, stageCopy[selectedRun.current_stage].uk)}</h2><progress max={100} value={selectedRun.progress_percent} /><p>{selectedRun.progress_percent}% · {tr('bounded maximum 45 minutes', 'максимум 45 хвилин')}</p></>}
        {selectedRun.status === 'failed' && <><h2>{tr('Result could not be completed', 'Не вдалося завершити Result')}</h2><p>{selectedRun.error_message || selectedRun.error_code}</p><button className="secondary" disabled={busy} onClick={retry}>{tr('Create immutable retry', 'Створити незмінну повторну спробу')}</button></>}
        {result && <div className="result-output">
          {assetUrl && <img src={assetUrl} alt={result.content.alt_text} />}
          <ResultContent value={result} language={language} />
          <section className="result-why"><small>{tr('WHY THIS DIRECTION', 'ЧОМУ ЦЕЙ НАПРЯМ')}</small><ul>{result.decision_summary.map((item) => <li key={item}>{item}</li>)}</ul></section>
          <div className="result-actions"><button className="primary" onClick={() => void download()}><Download />{tr('Download result', 'Завантажити результат')}</button><button className="secondary" onClick={() => void useResult()}><Check />{tr('Use result', 'Використати результат')}</button><button onClick={() => void feedback('accepted')}><ThumbsUp />{tr('Accept', 'Прийняти')}</button><button onClick={() => void feedback('rejected')}><ThumbsDown />{tr('Reject', 'Відхилити')}</button><button onClick={() => { setSelectedRun(null); setResult(null); setDebug(null); setNotice(tr('Ready to create another immutable Result.', 'Можна створити ще один незмінний Result.')) }}><Sparkles />{tr('Create another', 'Створити ще')}</button></div>
          <details onToggle={(event) => { if ((event.currentTarget as HTMLDetailsElement).open && !debug) void api.get<Record<string, unknown>>(`/api/v1/content-runs/${selectedRun.run_id}/debug`).then(setDebug).catch((cause: Error) => setError(cause.message)) }}><summary>{tr('How this was made', 'Як це було створено')}</summary><pre>{debug ? JSON.stringify(debug, null, 2) : tr('Loading bounded trace…', 'Завантаження обмеженого трасування…')}</pre></details>
        </div>}
      </section>}

      {!!runs.length && <section className="panel result-history"><small>{tr('RESULT HISTORY', 'ІСТОРІЯ RESULT')}</small>{runs.map((run) => <button key={run.run_id} className={run.run_id === selectedRun?.run_id ? 'selected' : ''} onClick={() => void load(run.run_id)}><strong>{run.task}</strong><span>{run.status} · {new Date(run.created_at).toLocaleString(language === 'uk' ? 'uk-UA' : 'en-US')}</span></button>)}</section>}
    </>}
  </>
}
