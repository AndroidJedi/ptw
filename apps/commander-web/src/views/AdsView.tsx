import { AlertTriangle, CheckCircle2, ExternalLink, Megaphone, RefreshCcw, RotateCcw, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type { MetaAdsDeployment, MetaAdsPresetVersion, MetaAdsProjectWorkspace, MetaAdsSourceVersion } from '../types'

const runningStates = new Set(['queued', 'creating_campaign', 'creating_ad_set', 'uploading_image', 'creating_creative', 'creating_ad'])
const categories = ['NONE', 'CREDIT', 'EMPLOYMENT', 'HOUSING', 'ISSUES_ELECTIONS_POLITICS', 'FINANCIAL_PRODUCTS_SERVICES', 'ONLINE_GAMBLING_AND_GAMING']

function short(value?: string | null) { return value ? value.length > 22 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value : '—' }
function objectStatus(value: unknown) {
  if (!value || typeof value !== 'object') return '—'
  const item = value as { effective_status?: unknown; status?: unknown; issues_info?: unknown }
  const status = String(item.effective_status || item.status || '—')
  const issues = Array.isArray(item.issues_info) && item.issues_info.length ? ` · ${item.issues_info.length} issue(s)` : ''
  return `${status}${issues}`
}

export function AdsView({ api, language, projectId = null }: {
  api: ApiClient
  language: Language
  projectId?: string | null
}) {
  const [workspace, setWorkspace] = useState<MetaAdsProjectWorkspace | null>(null)
  const [selectedSource, setSelectedSource] = useState<MetaAdsSourceVersion | null>(null)
  const [selectedPresetId, setSelectedPresetId] = useState('')
  const [headline, setHeadline] = useState('')
  const [primaryText, setPrimaryText] = useState('')
  const [welcomeMessage, setWelcomeMessage] = useState('')
  const [category, setCategory] = useState('NONE')
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [presetOpen, setPresetOpen] = useState(false)
  const [preset, setPreset] = useState({ name: '', countries: 'UA', age_min: 25, age_max: 55, gender: 'all', daily_budget_minor: 500 })
  const epoch = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const base = projectId ? `/api/v1/ads/projects/${projectId}` : ''

  const applyWorkspace = (value: MetaAdsProjectWorkspace) => {
    setWorkspace(value)
    setSelectedPresetId(current => value.presets.some(item => item.preset_id === current) ? current : value.presets[0]?.preset_id || '')
    setSelectedSource(current => value.sources.find(item => item.creative_id === current?.creative_id && item.version === current.version) || value.sources[0] || null)
    setError('')
  }

  const reload = async (quiet = false) => {
    if (!projectId) return
    const current = ++epoch.current
    if (!quiet) { setWorkspace(null); setError(''); setNotice('') }
    try {
      const value = await api.get<MetaAdsProjectWorkspace>(base)
      if (current === epoch.current) applyWorkspace(value)
    } catch (cause) {
      if (current === epoch.current) setError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  useEffect(() => { if (projectId) void reload(); else { setWorkspace(null); setSelectedSource(null) } }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedSource) return
    setHeadline(selectedSource.defaults.headline)
    setPrimaryText(selectedSource.defaults.primary_text)
    setWelcomeMessage(selectedSource.defaults.welcome_message)
  }, [selectedSource?.creative_id, selectedSource?.version]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let active = true
    let objectUrl = ''
    setPreviewUrl('')
    if (!projectId || !selectedSource) return () => { active = false }
    void api.image(
      `/api/v1/studio/projects/${projectId}/creatives/${selectedSource.creative_id}/versions/${selectedSource.version}/render`,
      'image/png', selectedSource.render_sha256,
    ).then(blob => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob)
      setPreviewUrl(objectUrl)
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : String(cause)) })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, projectId, selectedSource?.creative_id, selectedSource?.version, selectedSource?.render_sha256])

  useEffect(() => {
    if (!workspace?.deployments.some(item => runningStates.has(item.status))) return
    const timer = window.setInterval(() => void reload(true), 2_500)
    return () => window.clearInterval(timer)
  }, [workspace?.deployments.map(item => item.status).join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedPreset = useMemo(
    () => workspace?.presets.find(item => item.preset_id === selectedPresetId) || null,
    [workspace?.presets, selectedPresetId],
  )

  const createPreset = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.post<{ preset: MetaAdsPresetVersion }>('/api/v1/ads/presets', {
        name: preset.name,
        countries: preset.countries.split(',').map(item => item.trim().toUpperCase()).filter(Boolean),
        age_min: Number(preset.age_min), age_max: Number(preset.age_max), gender: preset.gender,
        daily_budget_minor: Number(preset.daily_budget_minor),
      })
      await reload(true)
      setSelectedPresetId(result.preset.preset_id)
      setPresetOpen(false)
      setNotice(tr('Audience preset version saved.', 'Версію пресета аудиторії збережено.'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  const stage = async () => {
    if (!selectedSource || !selectedPreset) return
    setBusy(true); setError(''); setNotice('')
    try {
      await api.post(`${base}/deployments`, {
        request_id: crypto.randomUUID(), creative_id: selectedSource.creative_id,
        version: selectedSource.version, preset_id: selectedPreset.preset_id,
        headline, primary_text: primaryText, welcome_message: welcomeMessage,
        special_ad_categories: [category],
      })
      setNotice(tr('Staging reserved. PTW is creating PAUSED Meta objects.', 'Staging зарезервовано. PTW створює об’єкти Meta зі статусом PAUSED.'))
      await reload(true)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  const deploymentAction = async (deployment: MetaAdsDeployment, action: 'retry' | 'sync') => {
    setBusy(true); setError('')
    try { await api.post(`${base}/deployments/${deployment.deployment_id}/${action}`, {}); await reload(true) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  if (!projectId) return <Empty>{tr('Select a Project to stage approved Posts.', 'Виберіть Project, щоб підготувати затверджені дописи.')}</Empty>
  if (!workspace && !error) return <Loading language={language} />
  if (!workspace && error) return <ErrorState message={error} retry={() => void reload()} language={language} />
  if (!workspace) return null
  const connected = workspace.connection.configured && workspace.connection.verified

  return <div className="ads-page">
    <header className="page-header ads-header">
      <div><small>META MARKETING API · {workspace.connection.graph_version}</small><h1>{tr('Ads', 'Реклама')}</h1><p>{tr('Stage approved Post versions as complete, PAUSED Instagram ad structures.', 'Створюйте з затверджених версій дописів повну структуру реклами Instagram зі статусом PAUSED.')}</p></div>
      <div className="ads-safety"><ShieldCheck /><span><strong>PAUSED ONLY</strong>{tr('No spend or automatic activation', 'Без витрат та автоматичної активації')}</span></div>
    </header>
    {error && <ErrorState message={error} retry={() => void reload(true)} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}

    <section className={`panel ads-connection ${connected ? 'is-ready' : 'is-warning'}`}>
      <small>{tr('CONNECTION', 'ПІДКЛЮЧЕННЯ')}</small>
      <div className="ads-connection-grid">
        <div>{connected ? <CheckCircle2 /> : <AlertTriangle />}<span><strong>{connected ? tr('Meta assets verified', 'Активи Meta перевірено') : tr('Meta staging disabled', 'Staging Meta вимкнено')}</strong><small>{workspace.connection.explanation || tr('System user and assigned assets are available.', 'Системний користувач і призначені активи доступні.')}</small></span></div>
        <dl><div><dt>{tr('Ad Account', 'Рекламний акаунт')}</dt><dd>{workspace.connection.account?.name || '—'} <code>{short(workspace.connection.account?.id)}</code></dd></div><div><dt>Facebook Page</dt><dd>{workspace.connection.page?.name || '—'} <code>{short(workspace.connection.page?.id)}</code></dd></div><div><dt>Instagram</dt><dd>{workspace.connection.instagram?.username ? `@${workspace.connection.instagram.username}` : '—'} <code>{short(workspace.connection.instagram?.id)}</code></dd></div></dl>
        {workspace.connection.available && <p className="ads-available">{tr('Available to this system user', 'Доступно цьому системному користувачу')}: {workspace.connection.available.ad_accounts.length} Ad Account · {workspace.connection.available.pages.length} Page · {workspace.connection.available.instagram_accounts.length} Instagram</p>}
      </div>
    </section>

    <section className="ads-compose-grid">
      <div className="panel ads-sources">
        <div className="ads-section-title"><div><small>{tr('APPROVED SOURCES', 'ЗАТВЕРДЖЕНІ ДЖЕРЕЛА')}</small><h2>{tr('Post versions', 'Версії дописів')}</h2></div><span>{workspace.sources.length}</span></div>
        {workspace.sources.length === 0 ? <p>{tr('Approve a version in Post Studio first.', 'Спочатку затвердьте версію у Post Studio.')}</p> : <div className="ads-source-list">{workspace.sources.map(source => <button key={`${source.creative_id}-${source.version}`} className={selectedSource?.creative_id === source.creative_id && selectedSource.version === source.version ? 'selected' : ''} onClick={() => setSelectedSource(source)}><strong>Post {source.creative_ordinal} · v{source.version}</strong><span>{source.template_id}</span><code>{short(source.render_sha256)}</code></button>)}</div>}
      </div>

      <div className="panel ads-editor">
        <div className="ads-section-title"><div><small>{tr('FINAL IMMUTABLE SPEC', 'ФІНАЛЬНА НЕЗМІННА СПЕЦИФІКАЦІЯ')}</small><h2>{tr('Creative and delivery', 'Креатив і доставка')}</h2></div><Megaphone /></div>
        {selectedSource ? <>
          <figure className="ads-preview">{previewUrl ? <img src={previewUrl} alt={tr('Approved Post selected for Meta Ads', 'Затверджений допис, вибраний для Meta Ads')} /> : <span>{tr('Verifying PNG…', 'Перевірка PNG…')}</span>}<figcaption>SHA-256 {short(selectedSource.render_sha256)}</figcaption></figure>
          <div className="ads-fields">
            <label>{tr('Headline', 'Заголовок')}<input value={headline} maxLength={255} onChange={event => setHeadline(event.target.value)} /></label>
            <label>{tr('Primary text', 'Основний текст')}<textarea rows={5} value={primaryText} maxLength={2200} onChange={event => setPrimaryText(event.target.value)} /></label>
            <label>{tr('Initial Direct message', 'Початкове повідомлення Direct')}<textarea rows={2} value={welcomeMessage} maxLength={1000} onChange={event => setWelcomeMessage(event.target.value)} /></label>
            <label>{tr('Audience preset version', 'Версія пресета аудиторії')}<select value={selectedPresetId} onChange={event => setSelectedPresetId(event.target.value)}><option value="">{tr('Create a preset first', 'Спочатку створіть пресет')}</option>{workspace.presets.map(item => <option key={item.preset_id} value={item.preset_id}>v{item.version} · {item.specification.name} · {item.specification.daily_budget_minor} {workspace.connection.account?.currency || tr('minor units', 'мін. од.')}</option>)}</select></label>
            <label>{tr('Special ad category', 'Спеціальна категорія реклами')}<select value={category} onChange={event => setCategory(event.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label>
          </div>
          <div className="ads-fixed"><span>Instagram Feed</span><span>OUTCOME_ENGAGEMENT</span><span>Instagram Direct</span><span>CONVERSATIONS</span><span>IMPRESSIONS</span><span>Lowest cost</span><span>Enhancements: OFF</span></div>
          <button className="primary large" disabled={!connected || !selectedPreset || busy || !headline.trim() || !primaryText.trim() || !welcomeMessage.trim()} onClick={() => void stage()}><Megaphone />{busy ? tr('Working…', 'Виконується…') : tr('Create PAUSED campaign structure', 'Створити PAUSED-структуру кампанії')}</button>
        </> : <p>{tr('Select an approved Post version.', 'Виберіть затверджену версію допису.')}</p>}
      </div>
    </section>

    <section className="panel ads-presets">
      <div className="ads-section-title"><div><small>{tr('VERSIONED TARGETING', 'ВЕРСІЙНИЙ TARGETING')}</small><h2>{tr('Audience presets', 'Пресети аудиторії')}</h2></div><button className="secondary" onClick={() => setPresetOpen(value => !value)}>{presetOpen ? tr('Close', 'Закрити') : tr('New preset', 'Новий пресет')}</button></div>
      {presetOpen && <div className="ads-preset-form"><label>{tr('Name', 'Назва')}<input value={preset.name} maxLength={80} onChange={event => setPreset(current => ({ ...current, name: event.target.value }))} /></label><label>{tr('Countries (ISO, comma-separated)', 'Країни (ISO, через кому)')}<input value={preset.countries} onChange={event => setPreset(current => ({ ...current, countries: event.target.value }))} /></label><label>{tr('Minimum age', 'Мінімальний вік')}<input type="number" min="18" max="65" value={preset.age_min} onChange={event => setPreset(current => ({ ...current, age_min: Number(event.target.value) }))} /></label><label>{tr('Maximum age', 'Максимальний вік')}<input type="number" min="18" max="65" value={preset.age_max} onChange={event => setPreset(current => ({ ...current, age_max: Number(event.target.value) }))} /></label><label>{tr('Gender', 'Стать')}<select value={preset.gender} onChange={event => setPreset(current => ({ ...current, gender: event.target.value }))}><option value="all">{tr('All', 'Усі')}</option><option value="women">{tr('Women', 'Жінки')}</option><option value="men">{tr('Men', 'Чоловіки')}</option></select></label><label>{tr('Daily budget (minor currency units)', 'Денний бюджет (мінімальні одиниці валюти)')}<input type="number" min="1" value={preset.daily_budget_minor} onChange={event => setPreset(current => ({ ...current, daily_budget_minor: Number(event.target.value) }))} /></label><button className="primary" disabled={busy || !preset.name.trim()} onClick={() => void createPreset()}>{tr('Save immutable version', 'Зберегти незмінну версію')}</button></div>}
      {!presetOpen && <div className="ads-preset-list">{workspace.presets.map(item => <button key={item.preset_id} className={selectedPresetId === item.preset_id ? 'selected' : ''} onClick={() => setSelectedPresetId(item.preset_id)}><strong>v{item.version} · {item.specification.name}</strong><span>{item.specification.countries.join(', ')} · {item.specification.age_min}–{item.specification.age_max} · {item.specification.gender}</span><code>{short(item.specification_sha256)}</code></button>)}</div>}
    </section>

    <section className="panel ads-history">
      <div className="ads-section-title"><div><small>{tr('APPEND-ONLY HISTORY', 'APPEND-ONLY ІСТОРІЯ')}</small><h2>{tr('Staging deployments', 'Staging deployments')}</h2></div>{workspace.ads_manager_url && <a className="secondary" href={workspace.ads_manager_url} target="_blank" rel="noreferrer">Ads Manager <ExternalLink /></a>}</div>
      {workspace.deployments.length === 0 ? <p>{tr('No deployment has been staged for this Project.', 'Для цього Project ще немає staging deployment.')}</p> : <div className="ads-deployment-list">{workspace.deployments.map(item => <article key={item.deployment_id} className={`ads-deployment is-${item.status}`}><header><div><strong>Post v{item.source_version}</strong><code>{short(item.deployment_id)}</code></div><span>{runningStates.has(item.status) && <RefreshCcw className="spin" />}{item.status}</span></header><dl><div><dt>Campaign</dt><dd>{short(workspace.experiment?.meta_campaign_id)} · {objectStatus(item.status_snapshot?.campaign)}</dd></div><div><dt>Ad Set</dt><dd>{short(item.meta_ad_set_id)} · {objectStatus(item.status_snapshot?.ad_set)}</dd></div><div><dt>Creative</dt><dd>{short(item.meta_creative_id)}</dd></div><div><dt>Ad</dt><dd>{short(item.meta_ad_id)} · {objectStatus(item.status_snapshot?.ad)}</dd></div></dl>{item.error?.error_message && <p role="alert">{item.error.error_message}</p>}<footer>{item.status === 'failed' && <button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'retry')}><RotateCcw />{tr('Retry safely', 'Безпечно повторити')}</button>}{item.status === 'staged' && <button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'sync')}><RefreshCcw />{tr('Sync status', 'Синхронізувати статус')}</button>}</footer></article>)}</div>}
    </section>
  </div>
}
