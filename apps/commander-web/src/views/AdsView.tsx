import { Download, ExternalLink, RefreshCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { downloadBlob } from '../components/PostPublishing'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type { MetaAdsSourceVersion, PublishedLandingReference } from '../types'

type Arm = {
  arm_id: string; ordinal: number; source_creative_id: string; source_version: number
  ad_name: string; headline: string; primary_text: string; tracked_url: string
  paid: { spend_minor?: number; impressions?: number; link_clicks?: number; landing_page_views?: number }
  funnel: { landing_view: number; primary_cta_click: number; contact_click: number }
  cost_per_primary_cta_minor: number | null
}
type ValidationTest = {
  test_id: string; name: string; state: 'prepared' | 'active' | 'completed' | 'abandoned'
  total_budget_minor: number; daily_budget_minor: number; currency: string; duration_days: number
  campaign_name: string; ad_set_name: string; arms: Arm[]; current_leader_arm_id: string | null
  imports: Array<{ import_id: string; created_at: string; ignored_rows: number }>
}
type Workspace = {
  schema: 'ptw.instagram-validation.workspace.v1'; project_id: string; project_name: string
  sources: MetaAdsSourceVersion[]; landing: PublishedLandingReference | null
  tests: ValidationTest[]; ads_manager_url: string
}
type CsvPreview = {
  csv_sha256: string; headers: string[]; mapping: Record<string, string | null>
  matched_rows: Array<{ row: number; ad_name: string; matched_arm_id: string }>
  ignored_rows: Array<{ row: number; ad_name: string }>; can_import: boolean
}

function money(minor: number, currency: string, language: Language) {
  try { return new Intl.NumberFormat(language === 'uk' ? 'uk-UA' : 'en-US', { style: 'currency', currency }).format(minor / 100) }
  catch { return `${(minor / 100).toFixed(2)} ${currency}` }
}

export function AdsView({ api, language, projectId = null }: {
  api: ApiClient; language: Language; projectId?: string | null
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [name, setName] = useState('Instagram idea test')
  const [budget, setBudget] = useState('50')
  const [currency, setCurrency] = useState('USD')
  const [duration, setDuration] = useState(5)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [csvText, setCsvText] = useState<Record<string, string>>({})
  const [previews, setPreviews] = useState<Record<string, CsvPreview>>({})

  const load = async () => {
    if (!projectId) { setWorkspace(null); return }
    setError('')
    try {
      const value = await api.get<Workspace>(`/api/v1/instagram-tests/projects/${projectId}`)
      setWorkspace(value)
      const query = new URLSearchParams(window.location.search)
      const initialCreative = query.get('ad_creative'); const initialVersion = Number(query.get('ad_version'))
      if (initialCreative && initialVersion && !selected.length) setSelected([`${initialCreative}:${initialVersion}`])
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  useEffect(() => { void load() }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const sourceByKey = useMemo(() => new Map((workspace?.sources || []).map(item => [`${item.creative_id}:${item.version}`, item])), [workspace?.sources])
  const toggle = (key: string) => setSelected(current => current.includes(key) ? current.filter(item => item !== key) : current.length < 6 ? [...current, key] : current)
  const create = async () => {
    if (!projectId) return
    setBusy(true); setError(''); setNotice('')
    try {
      await api.post(`/api/v1/instagram-tests/projects/${projectId}/tests`, {
        request_id: crypto.randomUUID(), name: name.trim(),
        total_budget_minor: Math.round(Number(budget) * 100), currency: currency.toUpperCase(), duration_days: duration,
        arms: selected.map(key => sourceByKey.get(key)).filter(Boolean).map(item => ({ creative_id: item!.creative_id, version: item!.version })),
      }, { deadlineMs: 120_000 })
      setSelected([]); setNotice(tr('Launch kit prepared. Download it and reproduce the fixed setup in Meta Ads Manager.', 'Launch kit підготовлено. Завантажте його та відтворіть фіксовані налаштування в Meta Ads Manager.')); await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const transition = async (test: ValidationTest, action: 'activated' | 'completed' | 'abandoned') => {
    if (!projectId) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/instagram-tests/projects/${projectId}/tests/${test.test_id}/${action}`, { request_id: crypto.randomUUID(), ...(action === 'completed' ? { campaign_stopped: true } : {}) })
      await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const download = async (test: ValidationTest) => {
    if (!projectId) return
    setBusy(true); setError('')
    try {
      const blob = await api.download(`/api/v1/instagram-tests/projects/${projectId}/tests/${test.test_id}/launch-kit`, 'application/zip', { deadlineMs: 120_000 })
      downloadBlob(blob, `${test.campaign_name}.zip`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }
  const readCsv = async (test: ValidationTest, file?: File) => {
    if (!file || !projectId) return
    const text = await file.text(); setCsvText(current => ({ ...current, [test.test_id]: text })); setError('')
    try {
      const preview = await api.post<CsvPreview>(`/api/v1/instagram-tests/projects/${projectId}/tests/${test.test_id}/imports/preview`, { csv_text: text })
      setPreviews(current => ({ ...current, [test.test_id]: preview }))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  const importCsv = async (test: ValidationTest) => {
    if (!projectId || !csvText[test.test_id]) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/instagram-tests/projects/${projectId}/tests/${test.test_id}/imports`, { request_id: crypto.randomUUID(), csv_text: csvText[test.test_id], accept_ignored_rows: true })
      setPreviews(current => { const next = { ...current }; delete next[test.test_id]; return next }); await load()
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { setBusy(false) }
  }

  if (!projectId) return <Empty><p>{tr('Select a Project to prepare an Instagram test.', 'Оберіть проєкт, щоб підготувати Instagram-тест.')}</p></Empty>
  if (!workspace && !error) return <Loading language={language} />
  if (!workspace) return <ErrorState message={error} retry={() => void load()} language={language} />
  const daily = Number.isFinite(Number(budget)) && duration > 0 ? Math.ceil(Number(budget) * 100 / duration) : 0

  return <div className="ads-page">
    <header className="page-header ads-header"><div><small>{tr('FAST IDEA VALIDATION', 'ШВИДКА ПЕРЕВІРКА ІДЕЙ')}</small><h1>{tr('Instagram tests', 'Instagram-тести')}</h1><p>{tr('PTW prepares exact assets, copy and tracking. You launch one Campaign with one Ad Set manually in Meta Ads Manager; PTW never stores the audience.', 'PTW готує точні креативи, тексти й трекінг. Ви вручну запускаєте одну Campaign з одним Ad Set у Meta Ads Manager; PTW ніколи не зберігає аудиторію.')}</p></div><button className="secondary" onClick={() => void load()}><RefreshCcw />{tr('Refresh', 'Оновити')}</button></header>
    {error && <p role="alert" className="notice">{error}</p>}{notice && <p role="status" className="notice">{notice}</p>}

    <section className="panel"><div className="ads-section-title"><div><small>{tr('FIXED LAUNCH CONTRACT', 'ФІКСОВАНИЙ КОНТРАКТ ЗАПУСКУ')}</small><h2>{tr('What to create in Meta', 'Що створити в Meta')}</h2></div></div>
      <div className="ads-fixed"><span>Traffic</span><span>Website</span><span>Landing Page Views</span><span>Instagram Feed only</span><span>Learn More</span><span>Campaign budget</span><span>Dynamic creative OFF</span><span>Enhancements OFF</span></div>
      <p>{tr('Do not use “Boost post”: it creates a simplified promotion around an existing organic post and exposes fewer controls. Ads Manager creates separate ads, preserves exact per-ad URLs and lets 2–6 creatives compete for one campaign budget.', 'Не використовуйте «Просувати допис»: це спрощене просування вже наявного органічного допису з меншою кількістю налаштувань. Ads Manager створює окремі оголошення, зберігає точний URL кожного ad і дає 2–6 креативам конкурувати за спільний бюджет campaign.')}</p>
    </section>

    <section className="panel"><div className="ads-section-title"><div><small>{tr('NEW TEST', 'НОВИЙ ТЕСТ')}</small><h2>{tr('Choose 2–6 approved Posts', 'Оберіть 2–6 затверджених дописів')}</h2></div><span>{selected.length}/6</span></div>
      {!workspace.landing && <p role="alert">{tr('Publish one approved Landing version first.', 'Спочатку опублікуйте одну затверджену версію Landing.')}</p>}
      <div className="ads-source-list">{workspace.sources.map(source => { const key = `${source.creative_id}:${source.version}`; return <article key={key} className={selected.includes(key) ? 'selected' : ''}><button type="button" onClick={() => toggle(key)}><strong>Post {source.creative_ordinal} · v{source.version}</strong><span>{source.defaults.headline || tr('No headline', 'Без заголовка')}</span><small>{source.change_note}</small></button></article> })}</div>
      {!workspace.sources.length && <p>{tr('Approve at least two Post versions in Studio.', 'Затвердьте щонайменше дві версії дописів у Studio.')}</p>}
      <div className="ads-fields"><label>{tr('Test name', 'Назва тесту')}<input value={name} maxLength={80} onChange={event => setName(event.target.value)} /></label><label>{tr('Total budget', 'Загальний бюджет')}<input type="number" min="0.01" step="0.01" value={budget} onChange={event => setBudget(event.target.value)} /></label><label>{tr('Currency', 'Валюта')}<input value={currency} maxLength={3} onChange={event => setCurrency(event.target.value.toUpperCase())} /></label><label>{tr('Duration, days', 'Тривалість, днів')}<input type="number" min="1" max="30" value={duration} onChange={event => setDuration(Number(event.target.value))} /></label></div>
      <p>{tr('Derived daily budget:', 'Розрахований денний бюджет:')} <strong>{money(daily, currency, language)}</strong></p>
      <button className="primary" disabled={busy || !workspace.landing || selected.length < 2 || selected.length > 6 || !name.trim() || !daily} onClick={() => void create()}>{tr('Prepare launch kit', 'Підготувати launch kit')}</button>
    </section>

    <section className="panel"><div className="ads-section-title"><div><small>{tr('LIFECYCLE & RESULTS', 'ЖИТТЄВИЙ ЦИКЛ І РЕЗУЛЬТАТИ')}</small><h2>{tr('Prepared tests', 'Підготовлені тести')}</h2></div></div>
      {!workspace.tests.length && <p>{tr('No tests yet.', 'Тестів ще немає.')}</p>}
      <div className="ads-deployments">{workspace.tests.map(test => { const preview = previews[test.test_id]; return <article className="ads-deployment" key={test.test_id}>
        <div className="ads-section-title"><div><strong>{test.name}</strong><small>{test.state.toUpperCase()} · {test.campaign_name}</small></div>{test.current_leader_arm_id && <span>{tr('Current leader', 'Поточний лідер')}: AD-{test.arms.find(item => item.arm_id === test.current_leader_arm_id)?.ordinal.toString().padStart(2, '0')}</span>}</div>
        <p>{money(test.total_budget_minor, test.currency, language)} · {test.duration_days} {tr('days', 'днів')} · {money(test.daily_budget_minor, test.currency, language)}/{tr('day', 'день')}</p>
        <div className="post-publishing-actions"><button className="secondary" disabled={busy} onClick={() => void download(test)}><Download />{tr('Download launch kit', 'Завантажити launch kit')}</button><a className="primary" href={workspace.ads_manager_url} target="_blank" rel="noreferrer">{tr('Open Meta Ads Manager', 'Відкрити Meta Ads Manager')}<ExternalLink /></a>{test.state === 'prepared' && <><button className="secondary" disabled={busy} onClick={() => void transition(test, 'activated')}>{tr('I launched it', 'Я запустив кампанію')}</button><button className="secondary" disabled={busy} onClick={() => void transition(test, 'abandoned')}>{tr('Abandon', 'Відмовитися')}</button></>}{test.state === 'active' && <button className="secondary" disabled={busy} onClick={() => window.confirm(tr('Confirm that both Campaign and Ad Set are stopped in Meta.', 'Підтвердьте, що Campaign і Ad Set зупинені в Meta.')) && void transition(test, 'completed')}>{tr('Stopped in Meta · complete', 'Зупинено в Meta · завершити')}</button>}</div>
        <div className="ads-insights"><table><thead><tr><th>Ad</th><th>{tr('Spend', 'Витрати')}</th><th>LPV Meta</th><th>{tr('Landing', 'Landing')}</th><th>{tr('Primary CTA', 'Primary CTA')}</th><th>{tr('Contact', 'Контакт')}</th><th>{tr('Cost / primary CTA', 'Ціна / primary CTA')}</th></tr></thead><tbody>{test.arms.map(arm => <tr key={arm.arm_id} className={arm.arm_id === test.current_leader_arm_id ? 'selected' : ''}><td><strong>AD-{arm.ordinal.toString().padStart(2, '0')}</strong><small>{arm.ad_name}</small></td><td>{money(arm.paid.spend_minor || 0, test.currency, language)}</td><td>{arm.paid.landing_page_views || 0}</td><td>{arm.funnel.landing_view}</td><td>{arm.funnel.primary_cta_click}</td><td>{arm.funnel.contact_click}</td><td>{arm.cost_per_primary_cta_minor == null ? '—' : money(arm.cost_per_primary_cta_minor, test.currency, language)}</td></tr>)}</tbody></table></div>
        <p><small>{tr('Leader is informational only. PTW never declares a statistical winner automatically.', 'Лідер лише інформаційний. PTW ніколи автоматично не оголошує статистичного переможця.')}</small></p>
        <label>{tr('Meta Ads Manager CSV', 'CSV з Meta Ads Manager')}<input type="file" accept=".csv,text/csv" onChange={event => void readCsv(test, event.target.files?.[0])} /></label>
        {preview && <div className="ads-request-review"><strong>{tr('Import preview', 'Попередній перегляд імпорту')}</strong><p>{tr('Matched', 'Зіставлено')}: {preview.matched_rows.length} · {tr('Ignored', 'Проігноровано')}: {preview.ignored_rows.length}</p><p>{Object.entries(preview.mapping).map(([key, value]) => `${key}: ${value || '—'}`).join(' · ')}</p><button className="primary" disabled={busy || !preview.can_import} onClick={() => void importCsv(test)}>{preview.ignored_rows.length ? tr('Confirm ignored rows and import', 'Підтвердити пропущені рядки й імпортувати') : tr('Import results', 'Імпортувати результати')}</button></div>}
      </article> })}</div>
    </section>
  </div>
}
