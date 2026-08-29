import { Check, Download, RefreshCcw, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { ResultDecisionTrace } from '../components/ResultDecisionTrace'
import { translate, type Language } from '../i18n'
import type { ContentDebug, ContentResult, ContentRun, ProductBrief } from '../types'

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

function ResultContent({ value, language }: { value: ContentResult; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <article className="result-card">
    <small>{tr('FINAL INSTAGRAM POST', 'ФІНАЛЬНИЙ ДОПИС В INSTAGRAM')}</small>
    <h2>{value.content.hook}</h2>
    <h3>{value.content.headline}</h3>
    <p>{value.content.primary_text}</p>
    <p className="muted-copy">{value.content.supporting_text}</p>
    <div className="result-offer"><strong>{value.content.offer}</strong><span>{value.content.cta}</span></div>
    {value.content.caption && <section><small>{tr('CAPTION', 'ПІДПИС')}</small><p>{value.content.caption}</p></section>}
  </article>
}

export function ResultView({ api, projectId, language, localDemo = false }: { api: ApiClient; projectId: string | null; language: Language; localDemo?: boolean }) {
  const [briefs, setBriefs] = useState<ProductBrief[] | null>(null)
  const [runs, setRuns] = useState<ContentRun[]>([])
  const [selectedRun, setSelectedRun] = useState<ContentRun | null>(null)
  const [result, setResult] = useState<ContentResult | null>(null)
  const [assetUrl, setAssetUrl] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [debug, setDebug] = useState<ContentDebug | null>(null)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  const approved = useMemo(
    () => briefs?.find((item) => item.approved && item.status === 'completed') || null,
    [briefs],
  )

  const load = async (preferredRunId?: string) => {
    if (!projectId) {
      setBriefs([]); setRuns([]); setSelectedRun(null); setResult(null)
      return
    }
    const [briefValue, runValue] = await Promise.all([
      api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: ContentRun[] }>(`/api/v1/content-runs?limit=50&project_id=${encodeURIComponent(projectId)}`),
    ])
    setBriefs(briefValue.items); setRuns(runValue.items)
    const runId = preferredRunId || selectedRun?.run_id || runValue.items[0]?.run_id
    if (!runId) { setSelectedRun(null); setResult(null); return }
    if (selectedRun?.run_id !== runId) setDebug(null)
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
    if (!result.asset_sha256) { setError(tr('Rendered Instagram post is missing its asset digest.', 'У відрендереного допису в Instagram відсутній цифровий відбиток файлу.')); return }
    void api.image(result.asset_url, 'image/jpeg', result.asset_sha256)
      .then((blob) => {
        if (!(blob instanceof Blob)) return
        local = URL.createObjectURL(blob); setAssetUrl(local)
      })
      .catch((cause: Error) => setError(cause.message))
    return () => { if (local) URL.revokeObjectURL(local) }
  }, [api, result?.creative_id])

  const create = async () => {
    if (!approved) return
    setBusy(true); setError(''); setNotice('')
    try {
      const run = await api.post<ContentRun>('/api/v1/content-runs', {
        request_id: crypto.randomUUID(), brief_id: approved.brief_id,
      }, { deadlineMs: 60_000 })
      setSelectedRun(run); setResult(null); setNotice(tr('Instagram post creation started.', 'Створення допису в Instagram розпочато.'))
      await load(run.run_id)
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
      setNotice(decision === 'accepted' ? tr('Instagram post accepted.', 'Допис в Instagram прийнято.') : tr('Instagram post rejected. Feedback recorded.', 'Допис в Instagram відхилено. Відгук збережено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const download = async () => {
    if (!selectedRun || !result || !assetUrl) {
      setError(tr('The rendered Instagram image is not available yet.', 'Відрендерене зображення для Instagram ще недоступне.'))
      return
    }
    if (!localDemo) await api.post(`/api/v1/content-runs/${selectedRun.run_id}/outcomes`, { event_type: 'downloaded' })
    const link = document.createElement('a'); link.href = assetUrl
    link.download = 'natal-instagram-post.jpg'; link.click()
    setNotice(tr('Instagram post downloaded and recorded.', 'Допис в Instagram завантажено та зафіксовано.'))
  }

  const useResult = async () => {
    if (!selectedRun) return
    await api.post(`/api/v1/content-runs/${selectedRun.run_id}/outcomes`, { event_type: 'used' })
    setNotice(tr('Instagram post use recorded.', 'Використання допису в Instagram зафіксовано.'))
  }

  if (!briefs) return error ? <ErrorState message={error} retry={() => void load()} language={language} /> : <Loading language={language} />
  return <>
    <PageHeader eyebrow={tr('NATAL · ONE FINAL POST', 'NATAL · ОДИН ФІНАЛЬНИЙ ДОПИС')} title={tr('Instagram post', 'Допис в Instagram')} />
    {localDemo && <p className="notice" role="status">{tr('Representative local Result · provider generation, feedback, and persisted outcomes are disabled.', 'Репрезентативний локальний результат · генерацію через провайдера, відгуки та збереження результатів вимкнено.')}</p>}
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
    {!projectId ? <Empty><Sparkles className="empty-mark" /><h2>{tr('Select or create a Project', 'Виберіть або створіть проєкт')}</h2></Empty> : <>
      <section className="panel result-create">
        <div><small>{tr('SOURCE', 'ДЖЕРЕЛО')}</small><h2>{approved?.product || tr('Approved Product Brief required', 'Потрібен схвалений продуктовий бриф')}</h2><p>{approved?.promise || tr('Approve a completed Brief before creating an Instagram post.', 'Схваліть завершений бриф перед створенням допису в Instagram.')}</p></div>
        <p>{tr('Natal branding is applied automatically. Nothing else is required.', 'Брендинг Natal застосовується автоматично. Більше нічого не потрібно.')}</p>
        <button className="primary large" disabled={localDemo || busy || !approved} onClick={create}><Sparkles />{tr('Create Instagram post', 'Створити допис в Instagram')}</button>
      </section>

      {selectedRun && <section className="panel result-progress">
        <small>{tr('INSTAGRAM POST CREATION', 'СТВОРЕННЯ ДОПИСУ В INSTAGRAM')}</small>
        {ACTIVE.has(selectedRun.status) && <><h2><RefreshCcw className="spin" /> {translate(language, stageCopy[selectedRun.current_stage].en, stageCopy[selectedRun.current_stage].uk)}</h2><progress max={100} value={selectedRun.progress_percent} /><p>{selectedRun.progress_percent}% · {tr('bounded maximum 45 minutes', 'максимум 45 хвилин')}</p></>}
        {selectedRun.status === 'failed' && <><h2>{tr('Instagram post could not be completed', 'Не вдалося завершити допис в Instagram')}</h2><p>{selectedRun.error_message || selectedRun.error_code}</p><button className="secondary" disabled={localDemo || busy} onClick={retry}>{tr('Create immutable retry', 'Створити незмінну повторну спробу')}</button></>}
        {result && <div className="result-output">
          {assetUrl && <img src={assetUrl} alt={result.content.alt_text} />}
          <ResultContent value={result} language={language} />
          <section className="result-why"><small>{tr('WHY THIS DIRECTION', 'ЧОМУ ЦЕЙ НАПРЯМ')}</small><ul>{result.decision_summary.map((item) => <li key={item}>{item}</li>)}</ul></section>
          <div className="result-actions"><button className="primary" onClick={() => void download()}><Download />{tr('Download post', 'Завантажити допис')}</button><button className="secondary" disabled={localDemo} onClick={() => void useResult()}><Check />{tr('Use post', 'Використати допис')}</button><button disabled={localDemo} onClick={() => void feedback('accepted')}><ThumbsUp />{tr('Accept', 'Прийняти')}</button><button disabled={localDemo} onClick={() => void feedback('rejected')}><ThumbsDown />{tr('Reject', 'Відхилити')}</button><button onClick={() => { setSelectedRun(null); setResult(null); setDebug(null); setNotice(tr('Ready to create another immutable Instagram post.', 'Можна створити ще один незмінний допис в Instagram.')) }}><Sparkles />{tr('Create another', 'Створити ще')}</button></div>
          <details className="result-debug" onToggle={(event) => { if ((event.currentTarget as HTMLDetailsElement).open && !debug) void api.get<ContentDebug>(`/api/v1/content-runs/${selectedRun.run_id}/debug`).then(setDebug).catch((cause: Error) => setError(cause.message)) }}><summary>{tr('See all five directions and the decision', 'Переглянути всі п’ять напрямів і рішення')}</summary>{debug ? <ResultDecisionTrace value={debug} api={api} selectedCandidateId={result.selected_candidate_id} language={language} /> : <p>{tr('Loading bounded trace…', 'Завантаження обмеженого трасування…')}</p>}</details>
        </div>}
      </section>}

      {!!runs.length && <section className="panel result-history"><small>{tr('INSTAGRAM POST HISTORY', 'ІСТОРІЯ ДОПИСІВ В INSTAGRAM')}</small>{runs.map((run) => <button key={run.run_id} className={run.run_id === selectedRun?.run_id ? 'selected' : ''} onClick={() => void load(run.run_id)}><strong>{tr('Instagram post', 'Допис в Instagram')}</strong><span>{run.status} · {new Date(run.created_at).toLocaleString(language === 'uk' ? 'uk-UA' : 'en-US')}</span></button>)}</section>}
    </>}
  </>
}
