import { Check, RefreshCcw, Send, Sparkles, Target } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'
import type { ProductBrief, ProductBriefDocument, ValidationProject } from '../types'

const activeStatuses = new Set(['queued', 'generating'])

function BriefDocument({ value, language }: { value: ProductBriefDocument; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <div className="brief-document">
    <section><small>{tr('POSITIONING HYPOTHESIS', 'ГІПОТЕЗА ПОЗИЦІОНУВАННЯ')}</small><h2>{value.promise}</h2><p>{value.product}</p></section>
    <section><dl><dt>{tr('First customer', 'Перший клієнт')}</dt><dd>{value.target_audience}</dd><dt>{tr('Main pain', 'Головний біль')}</dt><dd>{value.main_pain}</dd><dt>CTA</dt><dd>{value.cta}</dd></dl></section>
    <section><small>{tr('STRONG VALIDATION OFFER', 'СИЛЬНА ВАЛІДАЦІЙНА ПРОПОЗИЦІЯ')}</small><h2>{value.offer}</h2><p>{value.trust_strategy}</p></section>
    <section><small>{tr('KEY BENEFITS', 'КЛЮЧОВІ ПЕРЕВАГИ')}</small><ul>{value.key_benefits.map((item) => <li key={item}>{item}</li>)}</ul></section>
  </div>
}

export function ProductBriefView({ api, projectId, onProjectCreated, onProjectBriefChanged, onProjectsRefresh, onOpenResult, language, localDemo = false }: {
  api: ApiClient
  projectId: string | null
  onProjectCreated: (project: ValidationProject) => void
  onProjectBriefChanged: (projectId: string, name: string, briefId: string, status: ProductBrief['status']) => void
  onProjectsRefresh: (preferredId?: string) => Promise<void>
  onOpenResult: () => void
  language: Language
  localDemo?: boolean
}) {
  const [items, setItems] = useState<ProductBrief[] | null>(null)
  const [selected, setSelected] = useState<ProductBrief | null>(null)
  const [rawIdea, setRawIdea] = useState('')
  const [correction, setCorrection] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const load = async (preferredId?: string, targetProjectId = projectId) => {
    if (!targetProjectId) { setItems([]); setSelected(null); return }
    const value = await api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(targetProjectId)}`)
    setItems(value.items)
    const id = preferredId || (value.items.some((item) => item.brief_id === selected?.brief_id) ? selected?.brief_id : undefined) || value.items[0]?.brief_id
    if (!id) { setSelected(null); return }
    const detail = await api.get<ProductBrief>(`/api/v1/briefs/${id}`)
    setSelected(detail)
    onProjectBriefChanged(detail.project_id, detail.project_name, detail.brief_id, detail.status)
  }
  useEffect(() => {
    setItems(null); setSelected(null); setError('')
    void load().catch((cause: Error) => setError(cause.message))
  }, [api, projectId])
  useEffect(() => {
    if (!selected || !activeStatuses.has(selected.status)) return
    const timer = window.setInterval(() => void load(selected.brief_id).catch((cause: Error) => setError(cause.message)), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.brief_id, selected?.status])

  const create = async () => {
    if (!rawIdea.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<{ project: ValidationProject; brief: ProductBrief }>('/api/v1/briefs', {
        request_id: crypto.randomUUID(), raw_idea: rawIdea.trim(),
      })
      onProjectCreated(result.project)
      setRawIdea(''); setNotice(tr('Project created. One Product Brief is being generated from the idea.', 'Проєкт створено. З ідеї генерується один продуктовий бриф.')); await load(result.brief.brief_id, result.project.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const correct = async () => {
    if (!selected || !correction.trim()) return
    setBusy(true); setError('')
    try {
      const result = await api.post<{ brief: ProductBrief }>(`/api/v1/briefs/${selected.brief_id}/correct`, {
        request_id: crypto.randomUUID(), instruction: correction.trim(),
      })
      setCorrection(''); setNotice(tr('A complete immutable replacement Brief is being generated.', 'Генерується повний незмінний бриф на заміну.')); await load(result.brief.brief_id)
      await onProjectsRefresh(result.brief.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/briefs/${selected.brief_id}/approve`, { honor_confirmed: true })
      setNotice(tr('Approved. You can create a social post now.', 'Схвалено. Тепер можна створити допис для соцмереж.')); await load(selected.brief_id)
      await onProjectsRefresh(selected.project_id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!selected) return
    setBusy(true); setError('')
    try { await api.post(`/api/v1/briefs/${selected.brief_id}/retry`, {}); await load(selected.brief_id) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  if (!projectId) return <>
    <PageHeader eyebrow={tr('NEW PROJECT · RAW IDEA ONLY', 'НОВИЙ ПРОЄКТ · ЛИШЕ СИРА ІДЕЯ')} title={tr('New Project', 'Новий проєкт')} />
    {localDemo && <p className="notice" role="status">{tr('Local learning workspace · Product Brief generation uses the authenticated Codex CLI and never touches production.', 'Локальний простір навчання · генерація продуктового брифу використовує автентифікований Codex CLI і не торкається продакшну.')}</p>}
    {error && <ErrorState message={error} language={language} />}{notice && <p className="notice" role="status">{notice}</p>}
    <section className="panel brief-create"><div><small>{tr('ONE PROJECT · ONE INITIAL HYPOTHESIS', 'ОДИН ПРОЄКТ · ОДНА ПОЧАТКОВА ГІПОТЕЗА')}</small><h2>{tr('What do you want to validate?', 'Що ви хочете перевірити?')}</h2><p>{tr('Generating an initial Brief creates and selects the new Project. Existing Project history stays separate.', 'Генерація початкового брифу створює та вибирає новий проєкт. Історія існуючих проєктів залишається окремо.')}</p></div>
      <textarea id="new-project-idea" rows={5} maxLength={10000} value={rawIdea} onChange={(event) => setRawIdea(event.target.value)} placeholder={tr('Describe one product idea…', 'Опишіть одну продуктову ідею…')} />
      <button className="primary large" disabled={busy || !rawIdea.trim()} onClick={create}><Sparkles />{tr('Generate Product Brief & Create Project', 'Згенерувати продуктовий бриф і створити проєкт')}</button>
    </section>
  </>
  if (!items) return error ? <ErrorState message={error} retry={() => void load()} language={language} /> : <Loading language={language} />
  return <>
    <PageHeader eyebrow={tr('STAGE 1 · ONE HYPOTHESIS', 'ЕТАП 1 · ОДНА ГІПОТЕЗА')} title={tr('Product Briefs', 'Продуктові брифи')} />
    {localDemo && <p className="notice" role="status">{tr('Local immutable Brief history · explicit approval is required before generation.', 'Локальна незмінна історія брифів · перед генерацією потрібне явне схвалення.')}</p>}
    {error && <ErrorState message={error} language={language} />}{notice && <p className="notice" role="status">{notice}</p>}
    {!items.length ? <Empty><Target className="empty-mark" /><h2>{tr('No Product Brief in this Project', 'У цьому проєкті немає продуктового брифу')}</h2><p>{tr('Use New Project to start a separate validation loop.', 'Скористайтеся «Новий проєкт», щоб почати окремий цикл валідації.')}</p></Empty> : <div className="brief-workspace">
      <aside className="panel brief-list"><small>{tr('BRIEF HISTORY', 'ІСТОРІЯ БРИФІВ')}</small>{items.map((item, index) => <button key={item.brief_id} className={selected?.brief_id === item.brief_id ? 'selected' : ''} onClick={() => void load(item.brief_id)}><strong>{index === 0 ? tr('Current Brief', 'Поточний бриф') : tr('Earlier Brief', 'Попередній бриф')} · {item.product || item.raw_idea.slice(0, 70)}</strong><span>{item.status} · {item.language?.toUpperCase() || '—'} · {item.approved ? tr('approved', 'схвалено') : tr('not approved', 'не схвалено')} · {new Date(item.created_at).toLocaleDateString(language === 'uk' ? 'uk-UA' : 'en-US')}</span></button>)}</aside>
      {selected && <div className="panel brief-detail"><small>{selected.base_brief_id ? tr('REPLACEMENT BRIEF', 'БРИФ НА ЗАМІНУ') : tr('CURRENT IMMUTABLE BRIEF', 'ПОТОЧНИЙ НЕЗМІННИЙ БРИФ')}</small>
        {activeStatuses.has(selected.status) && <p className="generation-state"><RefreshCcw className="spin" /> {tr('Generating one testable hypothesis…', 'Генерується одна перевірювана гіпотеза…')}</p>}
        {selected.status === 'failed' && <div className="state error"><p>{selected.error_message || selected.error_code || tr('Generation failed', 'Генерація не вдалася')}</p><button className="secondary" disabled={busy} onClick={retry}>{tr('Retry', 'Повторити')}</button></div>}
        {selected.document && <><BriefDocument value={selected.document} language={language} />
          <div className="approval-row">{selected.approved ? <><p><Check /> {tr('Approved for social post creation', 'Схвалено для створення дописів у соцмережах')}</p><button className="primary" onClick={onOpenResult}><Sparkles />{tr('Create social post', 'Створити допис для соцмереж')}</button></> : <button className="primary" disabled={busy} onClick={approve}><Check />{tr('I can honor this promise and offer — approve', 'Я можу виконати цю обіцянку та пропозицію — схвалити')}</button>}</div>
          <section className="brief-correction"><h2>{tr('Correct this hypothesis', 'Виправити цю гіпотезу')}</h2><p>{tr('Creates a new immutable Brief that must be approved again.', 'Створює новий незмінний бриф, який потрібно схвалити повторно.')}</p><textarea rows={4} maxLength={2000} value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder={tr('One correction for the complete Brief…', 'Одне виправлення для всього брифу…')} /><button className="secondary" disabled={busy || !correction.trim()} onClick={correct}>{tr('Create replacement', 'Створити заміну')} <Send /></button></section>
        </>}
      </div>}
    </div>}
  </>
}
