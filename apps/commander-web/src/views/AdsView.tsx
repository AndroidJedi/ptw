import { AlertTriangle, CheckCircle2, ExternalLink, MapPin, Megaphone, RefreshCcw, RotateCcw, Search, ShieldCheck, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { downloadBlob } from '../components/PostPublishing'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type { MetaAdsDeployment, MetaAdsLocation, MetaAdsPresetVersion, MetaAdsProjectWorkspace, MetaAdsSourceVersion } from '../types'

const runningStates = new Set(['queued', 'creating_campaign', 'creating_ad_set', 'uploading_image', 'creating_creative', 'creating_ad'])
const categories = ['NONE', 'CREDIT', 'EMPLOYMENT', 'HOUSING', 'ISSUES_ELECTIONS_POLITICS', 'FINANCIAL_PRODUCTS_SERVICES', 'ONLINE_GAMBLING_AND_GAMING']
const metaConsoles = [
  { href: 'https://business.facebook.com/settings', en: 'Business settings', uk: 'Налаштування бізнесу', detailEn: 'Portfolio and assigned business assets', detailUk: 'Портфоліо та призначені бізнес-активи' },
  { href: 'https://business.facebook.com/settings/system-users', en: 'System users', uk: 'Системні користувачі', detailEn: 'App role, assets and token generation', detailUk: 'Роль застосунку, активи та створення токена' },
  { href: 'https://developers.facebook.com/apps/', en: 'App dashboard', uk: 'Панель застосунків', detailEn: 'Marketing API app and access level', detailUk: 'Застосунок Marketing API та рівень доступу' },
  { href: 'https://business.facebook.com/settings/ad-accounts', en: 'Ad accounts', uk: 'Рекламні акаунти', detailEn: 'Account status, access and payment setup', detailUk: 'Статус акаунта, доступ і налаштування оплати' },
  { href: 'https://business.facebook.com/settings/pages', en: 'Facebook Pages', uk: 'Сторінки Facebook', detailEn: 'Page ownership and system-user access', detailUk: 'Власність Page і доступ системного користувача' },
  { href: 'https://business.facebook.com/settings/instagram-accounts', en: 'Instagram accounts', uk: 'Акаунти Instagram', detailEn: 'Professional account and connected assets', detailUk: 'Професійний акаунт і пов’язані активи' },
  { href: 'https://developers.facebook.com/tools/debug/accesstoken/', en: 'Token debugger', uk: 'Перевірка токена', detailEn: 'Expiry, app and granted permissions', detailUk: 'Строк дії, застосунок і надані дозволи' },
]

function short(value?: string | null) { return value ? value.length > 22 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value : '—' }
function presetGeography(preset: MetaAdsPresetVersion['specification']) {
  return preset.cities?.length
    ? preset.cities.map(city => `${city.name} · ${city.radius_km} km`).join(', ')
    : preset.countries.join(', ')
}

interface PresetCity extends MetaAdsLocation { radius_km: number }
interface PresetDraft {
  name: string
  geo_mode: 'countries' | 'cities'
  countries: string
  city_country_code: string
  cities: PresetCity[]
  age_min: number
  age_max: number
  gender: string
  daily_budget_minor: number
}
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
  const [destination, setDestination] = useState<'WEBSITE' | 'INSTAGRAM_DIRECT'>(() => new URLSearchParams(window.location.search).get('destination') === 'WEBSITE' ? 'WEBSITE' : 'INSTAGRAM_DIRECT')
  const initialSource = useRef({ creative: new URLSearchParams(window.location.search).get('ad_creative'), version: Number(new URLSearchParams(window.location.search).get('ad_version')) })
  const [category, setCategory] = useState('NONE')
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [presetOpen, setPresetOpen] = useState(false)
  const [preset, setPreset] = useState<PresetDraft>({
    name: '', geo_mode: 'countries', countries: 'UA', city_country_code: 'UA', cities: [],
    age_min: 25, age_max: 55, gender: 'all', daily_budget_minor: 500,
  })
  const [locationQuery, setLocationQuery] = useState('Kyiv')
  const [locationResults, setLocationResults] = useState<MetaAdsLocation[]>([])
  const [locationBusy, setLocationBusy] = useState(false)
  const [locationError, setLocationError] = useState('')
  const epoch = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const base = projectId ? `/api/v1/ads/projects/${projectId}` : ''

  const applyWorkspace = (value: MetaAdsProjectWorkspace) => {
    setWorkspace(value)
    setSelectedPresetId(current => value.presets.some(item => item.preset_id === current) ? current : value.presets[0]?.preset_id || '')
    setSelectedSource(current => value.sources.find(item => item.creative_id === current?.creative_id && item.version === current.version) || value.sources.find(item => item.creative_id === initialSource.current.creative && item.version === initialSource.current.version) || (initialSource.current.creative ? null : value.sources[0]) || null)
    setError('')
  }

  const reload = async (quiet = false) => {
    if (!projectId) return
    const current = ++epoch.current
    if (!quiet) { setWorkspace(null); setError(''); setNotice('') }
    try {
      const value = await api.get<MetaAdsProjectWorkspace>(base)
      if (current === epoch.current) applyWorkspace(value)
      if (value.connection.configured && !value.connection.verified) {
        const connection = await api.get<MetaAdsProjectWorkspace['connection']>('/api/v1/ads/connection', { deadlineMs: 120_000 })
        if (current === epoch.current) setWorkspace(existing => existing ? { ...existing, connection } : existing)
      }
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
        countries: preset.geo_mode === 'countries'
          ? preset.countries.split(',').map(item => item.trim().toUpperCase()).filter(Boolean)
          : [],
        ...(preset.geo_mode === 'cities' ? { cities: preset.cities.map(city => ({
          key: city.key, name: city.name, country_code: city.country_code,
          radius_km: Number(city.radius_km),
        })) } : {}),
        age_min: Number(preset.age_min), age_max: Number(preset.age_max), gender: preset.gender,
        daily_budget_minor: Number(preset.daily_budget_minor),
      })
      await reload(true)
      setSelectedPresetId(result.preset.preset_id)
      setPresetOpen(false)
      setNotice(tr('Audience preset version saved.', 'Версію пресета аудиторії збережено.'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  const searchLocations = async () => {
    setLocationBusy(true); setLocationError(''); setLocationResults([])
    try {
      const query = encodeURIComponent(locationQuery.trim())
      const country = encodeURIComponent(preset.city_country_code.trim().toUpperCase())
      const result = await api.get<{ items: MetaAdsLocation[] }>(`/api/v1/ads/locations?query=${query}&country_code=${country}`)
      setLocationResults(result.items)
      if (!result.items.length) setLocationError(tr('No Meta city matches found.', 'Meta не знайшла відповідного міста.'))
    } catch (cause) {
      setLocationError(cause instanceof Error ? cause.message : String(cause))
    } finally { setLocationBusy(false) }
  }

  const addCity = (city: MetaAdsLocation) => {
    setPreset(current => current.cities.some(item => item.key === city.key) || current.cities.length >= 5
      ? current
      : { ...current, cities: [...current.cities, { ...city, radius_km: 20 }] })
  }

  const removeCity = (key: string) => {
    setPreset(current => ({ ...current, cities: current.cities.filter(city => city.key !== key) }))
  }

  const stage = async () => {
    if (!selectedSource || !selectedPreset) return
    setBusy(true); setError(''); setNotice('')
    try {
      const payload = {
        creative_id: selectedSource.creative_id,
        version: selectedSource.version, preset_id: selectedPreset.preset_id,
        headline, primary_text: primaryText,
        ...(destination === 'WEBSITE' ? { destination_type: destination, landing_event_id: workspace?.landing?.event_id } : { welcome_message: welcomeMessage }),
        special_ad_categories: [category],
      }
      const storageKey = `ptw-ad-request:${projectId}`
      const fingerprint = JSON.stringify(payload)
      const saved = sessionStorage.getItem(storageKey)
      const previous = saved ? JSON.parse(saved) as { fingerprint: string; request_id: string } : null
      const requestId = previous?.fingerprint === fingerprint ? previous.request_id : crypto.randomUUID()
      sessionStorage.setItem(storageKey, JSON.stringify({ fingerprint, request_id: requestId }))
      await api.post(`${base}/deployments`, { ...payload, request_id: requestId }, { deadlineMs: 120_000 })
      setNotice(tr('Staging reserved. PTW is creating PAUSED Meta objects.', 'Staging зарезервовано. PTW створює об’єкти Meta зі статусом PAUSED.'))
      await reload(true)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  const exportImage = async () => {
    if (!selectedSource || !projectId) return
    setBusy(true); setError('')
    try {
      const blob = await api.image(`/api/v1/studio/projects/${projectId}/creatives/${selectedSource.creative_id}/versions/${selectedSource.version}/render`, 'image/png', selectedSource.render_sha256)
      downloadBlob(blob, `instagram-ad-v${selectedSource.version}.png`)
      setNotice(tr('Exported. Upload this image in Ads Manager, paste the text and website URL, then review and publish there.', 'Експортовано. Завантажте зображення в Ads Manager, вставте текст і URL сайту, перевірте та опублікуйте там.'))
    } catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const copy = async (value: string) => {
    try { await navigator.clipboard.writeText(value); setNotice(tr('Copied', 'Скопійовано')) }
    catch { setError(tr('Clipboard unavailable. Select and copy the displayed text.', 'Буфер обміну недоступний. Виділіть і скопіюйте показаний текст.')) }
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
  const adsManagerUrl = workspace.ads_manager_url || 'https://adsmanager.facebook.com/adsmanager/manage/campaigns'
  const setupChecks = [
    {
      ok: workspace.connection.configured,
      en: 'Secure system-user token', uk: 'Захищений токен системного користувача',
      detail: workspace.connection.configured
        ? tr('Server secret is configured; the token is never sent to this browser.', 'Серверний секрет налаштовано; токен ніколи не передається в цей браузер.')
        : tr('Run the hidden-prompt PTW configurator with a fresh token.', 'Запустіть PTW-конфігуратор із прихованим введенням нового токена.'),
    },
    {
      ok: connected,
      en: 'Permissions verified', uk: 'Дозволи перевірено',
      detail: (workspace.connection.required_permissions || ['ads_management', 'ads_read']).join(' · '),
    },
    {
      ok: Boolean(workspace.connection.account),
      en: 'Ad Account available', uk: 'Рекламний акаунт доступний',
      detail: workspace.connection.account?.name || tr('Assign the Ad Account to the system user.', 'Призначте рекламний акаунт системному користувачу.'),
    },
    {
      ok: Boolean(workspace.connection.page),
      en: 'Facebook Page available', uk: 'Сторінка Facebook доступна',
      detail: workspace.connection.page?.name || tr('Assign the connected Page to the system user.', 'Призначте пов’язану Page системному користувачу.'),
    },
    {
      ok: Boolean(workspace.connection.instagram),
      en: 'Instagram actor available', uk: 'Instagram actor доступний',
      detail: workspace.connection.instagram?.username ? `@${workspace.connection.instagram.username}` : tr('Connect the professional Instagram account to the Page.', 'Під’єднайте професійний Instagram-акаунт до Page.'),
    },
    {
      ok: workspace.sources.length > 0,
      en: 'Approved Post available', uk: 'Затверджений Post доступний',
      detail: workspace.sources.length
        ? tr(`${workspace.sources.length} immutable version(s) ready for Ads.`, `${workspace.sources.length} незмінних версій готово для Ads.`)
        : tr('Approve a Post version in this Project.', 'Затвердьте версію Post у цьому Project.'),
    },
  ]

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

    <section className="panel ads-setup">
      <div className="ads-section-title"><div><small>{tr('READINESS & CONSOLES', 'ГОТОВНІСТЬ І КОНСОЛІ')}</small><h2>{tr('What is still needed', 'Що ще потрібно')}</h2></div><span>{setupChecks.filter(item => item.ok).length}/{setupChecks.length}</span></div>
      <div className="ads-setup-grid">
        <div className="ads-checklist">
          {setupChecks.map(item => <div key={item.en} className={`ads-check ${item.ok ? 'is-ok' : 'is-pending'}`}>
            {item.ok ? <CheckCircle2 /> : <AlertTriangle />}
            <span><strong>{language === 'uk' ? item.uk : item.en}</strong><small>{item.detail}</small></span>
          </div>)}
        </div>
        <div className="ads-console-grid">
          {metaConsoles.map(item => <a key={item.href} className="ads-console-link" href={item.href} target="_blank" rel="noreferrer">
            <span><strong>{language === 'uk' ? item.uk : item.en}</strong><small>{language === 'uk' ? item.detailUk : item.detailEn}</small></span><ExternalLink />
          </a>)}
          <a className="ads-console-link" href={adsManagerUrl} target="_blank" rel="noreferrer"><span><strong>Ads Manager</strong><small>{tr('Campaign, Ad Set, Creative and Ad status', 'Статуси Campaign, Ad Set, Creative та Ad')}</small></span><ExternalLink /></a>
        </div>
      </div>
    </section>

    <section className="ads-compose-grid">
      <div className="panel ads-sources">
        <div className="ads-section-title"><div><small>{tr('APPROVED SOURCES', 'ЗАТВЕРДЖЕНІ ДЖЕРЕЛА')}</small><h2>{tr('Post versions', 'Версії дописів')}</h2></div><span>{workspace.sources.length}</span></div>
        {workspace.sources.length === 0 ? <div className="ads-source-empty"><p>{tr('Approve a version in Post Studio first. It will appear here automatically.', 'Спочатку затвердьте версію у Post Studio. Вона автоматично з’явиться тут.')}</p><a className="secondary" href={`?page=posts&project=${encodeURIComponent(projectId)}`}>{tr('Open Post Studio', 'Відкрити Post Studio')}</a></div> : <div className="ads-source-list">{workspace.sources.map(source => <article key={`${source.creative_id}-${source.version}`} className={selectedSource?.creative_id === source.creative_id && selectedSource.version === source.version ? 'selected' : ''}><button type="button" onClick={() => setSelectedSource(source)}><span className="ads-approved-source"><CheckCircle2 />{tr('Approved for Ads', 'Затверджено для Ads')}</span><strong>Post {source.creative_ordinal} · v{source.version}</strong><span>{source.template_id}{source.change_note ? ` · ${source.change_note}` : ''}</span><code>{short(source.render_sha256)}</code></button><a href={`?page=posts&project=${encodeURIComponent(projectId)}&creative=${encodeURIComponent(source.creative_id)}`}>{tr('Open in Post Studio', 'Відкрити в Post Studio')} <ExternalLink /></a></article>)}</div>}
      </div>

      <div className="panel ads-editor">
        <div className="ads-section-title"><div><small>{tr('FINAL IMMUTABLE SPEC', 'ФІНАЛЬНА НЕЗМІННА СПЕЦИФІКАЦІЯ')}</small><h2>{tr('Creative and delivery', 'Креатив і доставка')}</h2></div><Megaphone /></div>
        {selectedSource ? <>
          <figure className="ads-preview">{previewUrl ? <img src={previewUrl} alt={tr('Approved Post selected for Meta Ads', 'Затверджений допис, вибраний для Meta Ads')} /> : <span>{tr('Verifying PNG…', 'Перевірка PNG…')}</span>}<figcaption>SHA-256 {short(selectedSource.render_sha256)}</figcaption></figure>
          <div className="ads-fields">
            <label>{tr('Destination', 'Призначення')}<select value={destination} onChange={event => setDestination(event.target.value as 'WEBSITE' | 'INSTAGRAM_DIRECT')}><option value="WEBSITE">{tr('Website · deployed landing', 'Сайт · опублікований лендінг')}</option><option value="INSTAGRAM_DIRECT">Instagram Direct</option></select></label>
            {destination === 'WEBSITE' && <div className="ads-website-destination"><strong>{tr('Learn more → Website', 'Дізнатися більше → Сайт')}</strong>{workspace.landing ? <a href={workspace.landing.canonical_url} target="_blank" rel="noreferrer">{workspace.landing.canonical_url}</a> : <p>{tr('Publish a Landing in this Project first.', 'Спочатку опублікуйте лендінг цього проєкту.')} <a href={`?page=landing&project=${projectId}`}>{tr('Open Landing', 'Відкрити лендінг')}</a></p>}</div>}

            <label>{tr('Headline', 'Заголовок')}<input value={headline} maxLength={255} onChange={event => setHeadline(event.target.value)} /></label>
            <label>{tr('Primary text', 'Основний текст')}<textarea rows={5} value={primaryText} maxLength={2200} onChange={event => setPrimaryText(event.target.value)} /></label>
            {destination === 'INSTAGRAM_DIRECT' && <label>{tr('Initial Direct message', 'Початкове повідомлення Direct')}<textarea rows={2} value={welcomeMessage} maxLength={1000} onChange={event => setWelcomeMessage(event.target.value)} /></label>}
            <label>{tr('Audience preset version', 'Версія пресета аудиторії')}<select value={selectedPresetId} onChange={event => setSelectedPresetId(event.target.value)}><option value="">{tr('Create a preset first', 'Спочатку створіть пресет')}</option>{workspace.presets.map(item => <option key={item.preset_id} value={item.preset_id}>v{item.version} · {item.specification.name} · {item.specification.daily_budget_minor} {workspace.connection.account?.currency || tr('minor units', 'мін. од.')}</option>)}</select></label>
            <label>{tr('Special ad category', 'Спеціальна категорія реклами')}<select value={category} onChange={event => setCategory(event.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label>
          </div>
          <div className="ads-fixed"><span>Instagram Feed</span><span>{destination === 'WEBSITE' ? 'OUTCOME_TRAFFIC' : 'OUTCOME_ENGAGEMENT'}</span><span>{destination === 'WEBSITE' ? 'Website · Learn more' : 'Instagram Direct'}</span><span>{destination === 'WEBSITE' ? 'LINK_CLICKS' : 'CONVERSATIONS'}</span><span>IMPRESSIONS</span><span>Lowest cost</span><span>Enhancements: OFF</span></div>
          <button className="primary large" disabled={!connected || !selectedPreset || busy || !headline.trim() || !primaryText.trim() || !previewUrl || (destination === 'WEBSITE' ? !workspace.landing : !welcomeMessage.trim())} onClick={() => void stage()}><Megaphone />{busy ? tr('Working…', 'Виконується…') : tr('Create PAUSED campaign structure', 'Створити PAUSED-структуру кампанії')}</button>
          <div className="post-publishing-actions"><button className="secondary" disabled={busy} onClick={() => void exportImage()}>{tr('Download image', 'Завантажити зображення')}</button><button className="secondary" onClick={() => void copy([headline, primaryText].filter(Boolean).join('\n\n'))}>{tr('Copy ad text', 'Копіювати текст реклами')}</button>{workspace.landing && <button className="secondary" onClick={() => void copy(workspace.landing!.canonical_url)}>{tr('Copy landing URL', 'Копіювати URL лендінгу')}</button>}<a className="secondary" href={adsManagerUrl} target="_blank" rel="noreferrer">{tr('Open in Ads Manager', 'Відкрити в Ads Manager')}</a></div>
          <p>{tr('Export is available without Meta access. Create or review the ad and start paid delivery in Ads Manager. These links open Meta; they do not fill its forms.', 'Експорт доступний без підключення Meta. Створіть або перевірте рекламу та запустіть покази в Ads Manager. Посилання відкривають Meta, але не заповнюють форми.')}</p>
        </> : <p>{tr('Select an approved Post version.' , 'Виберіть затверджену версію допису.')}</p>}
      </div>
    </section>

    <section className="panel ads-presets">
      <div className="ads-section-title"><div><small>{tr('VERSIONED TARGETING', 'ВЕРСІЙНИЙ TARGETING')}</small><h2>{tr('Audience presets', 'Пресети аудиторії')}</h2></div><button className="secondary" onClick={() => setPresetOpen(value => !value)}>{presetOpen ? tr('Close', 'Закрити') : tr('New preset', 'Новий пресет')}</button></div>
      {presetOpen && <div className="ads-preset-form">
        <label>{tr('Name', 'Назва')}<input value={preset.name} maxLength={80} onChange={event => setPreset(current => ({ ...current, name: event.target.value }))} /></label>
        <label>{tr('Geography', 'Географія')}<select value={preset.geo_mode} onChange={event => setPreset(current => ({ ...current, geo_mode: event.target.value as PresetDraft['geo_mode'] }))}><option value="countries">{tr('Entire countries', 'Цілі країни')}</option><option value="cities">{tr('City + radius', 'Місто + радіус')}</option></select></label>
        {preset.geo_mode === 'countries' ? <label>{tr('Countries (ISO, comma-separated)', 'Країни (ISO, через кому)')}<input value={preset.countries} onChange={event => setPreset(current => ({ ...current, countries: event.target.value }))} /></label> : <div className="ads-city-targeting">
          <div className="ads-city-search">
            <label>{tr('Country code', 'Код країни')}<input value={preset.city_country_code} maxLength={2} onChange={event => setPreset(current => ({ ...current, city_country_code: event.target.value.toUpperCase() }))} /></label>
            <label>{tr('Search city in Meta', 'Знайти місто в Meta')}<input value={locationQuery} maxLength={80} onChange={event => setLocationQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void searchLocations() } }} /></label>
            <button className="secondary" type="button" disabled={!connected || locationBusy || locationQuery.trim().length < 2 || preset.city_country_code.trim().length !== 2} onClick={() => void searchLocations()}><Search />{locationBusy ? tr('Searching…', 'Пошук…') : tr('Search Meta', 'Знайти в Meta')}</button>
          </div>
          {!connected && <p className="ads-location-help">{tr('Connect and verify Meta first; city keys come directly from its targeting search.', 'Спочатку під’єднайте та перевірте Meta; ключі міст беруться безпосередньо з її targeting search.')}</p>}
          {locationError && <p className="ads-location-error" role="alert">{locationError}</p>}
          {locationResults.length > 0 && <div className="ads-location-results">{locationResults.map(city => <button type="button" key={city.key} disabled={preset.cities.some(item => item.key === city.key)} onClick={() => addCity(city)}><MapPin /><span><strong>{city.name}</strong><small>{[city.region, city.country_name].filter(Boolean).join(', ')}</small></span>{preset.cities.some(item => item.key === city.key) ? <CheckCircle2 /> : tr('Add', 'Додати')}</button>)}</div>}
          {preset.cities.length > 0 && <div className="ads-selected-cities">{preset.cities.map(city => <article key={city.key}><span><MapPin /><strong>{city.name}</strong><small>{city.country_code} · Meta key {city.key}</small></span><label>{tr('Radius, km', 'Радіус, км')}<input type="number" min="17" max="80" value={city.radius_km} onChange={event => setPreset(current => ({ ...current, cities: current.cities.map(item => item.key === city.key ? { ...item, radius_km: Number(event.target.value) } : item) }))} /></label><button type="button" className="icon-button" aria-label={tr(`Remove ${city.name}`, `Видалити ${city.name}`)} onClick={() => removeCity(city.key)}><X /></button></article>)}</div>}
        </div>}
        <label>{tr('Minimum age', 'Мінімальний вік')}<input type="number" min="18" max="65" value={preset.age_min} onChange={event => setPreset(current => ({ ...current, age_min: Number(event.target.value) }))} /></label>
        <label>{tr('Maximum age', 'Максимальний вік')}<input type="number" min="18" max="65" value={preset.age_max} onChange={event => setPreset(current => ({ ...current, age_max: Number(event.target.value) }))} /></label>
        <label>{tr('Gender', 'Стать')}<select value={preset.gender} onChange={event => setPreset(current => ({ ...current, gender: event.target.value }))}><option value="all">{tr('All', 'Усі')}</option><option value="women">{tr('Women', 'Жінки')}</option><option value="men">{tr('Men', 'Чоловіки')}</option></select></label>
        <label>{tr('Daily budget (minor currency units)', 'Денний бюджет (мінімальні одиниці валюти)')}<input type="number" min="1" value={preset.daily_budget_minor} onChange={event => setPreset(current => ({ ...current, daily_budget_minor: Number(event.target.value) }))} /></label>
        <button className="primary" disabled={busy || !preset.name.trim() || (preset.geo_mode === 'cities' ? !preset.cities.length : !preset.countries.trim())} onClick={() => void createPreset()}>{tr('Save immutable version', 'Зберегти незмінну версію')}</button>
      </div>}
      {!presetOpen && <div className="ads-preset-list">{workspace.presets.map(item => <button key={item.preset_id} className={selectedPresetId === item.preset_id ? 'selected' : ''} onClick={() => setSelectedPresetId(item.preset_id)}><strong>v{item.version} · {item.specification.name}</strong><span>{presetGeography(item.specification)} · {item.specification.age_min}–{item.specification.age_max} · {item.specification.gender}</span><code>{short(item.specification_sha256)}</code></button>)}</div>}
    </section>

    <section className="panel ads-history">
      <div className="ads-section-title"><div><small>{tr('APPEND-ONLY HISTORY', 'APPEND-ONLY ІСТОРІЯ')}</small><h2>{tr('Staging deployments', 'Staging deployments')}</h2></div>{workspace.ads_manager_url && <a className="secondary" href={workspace.ads_manager_url} target="_blank" rel="noreferrer">Ads Manager <ExternalLink /></a>}</div>
      {workspace.deployments.length === 0 ? <p>{tr('No deployment has been staged for this Project.', 'Для цього Project ще немає staging deployment.')}</p> : <div className="ads-deployment-list">{workspace.deployments.map(item => <article key={item.deployment_id} className={`ads-deployment is-${item.status}`}><header><div><strong>Post v{item.source_version}</strong><code>{short(item.deployment_id)}</code></div><span>{runningStates.has(item.status) && <RefreshCcw className="spin" />}{item.status === 'staged' ? tr('Created in Meta', 'Створено в Meta') : item.status}</span></header><dl><div><dt>Campaign</dt><dd>{short(item.meta_campaign_id)} · {objectStatus(item.status_snapshot?.campaign)}</dd></div><div><dt>Ad Set</dt><dd>{short(item.meta_ad_set_id)} · {objectStatus(item.status_snapshot?.ad_set)}</dd></div><div><dt>Creative</dt><dd>{short(item.meta_creative_id)}</dd></div><div><dt>Ad</dt><dd>{short(item.meta_ad_id)} · {objectStatus(item.status_snapshot?.ad)}</dd></div></dl>{item.error?.error_message && <p role="alert">{item.error.error_message}</p>}<footer>{item.ads_manager_url && <a className="secondary" href={item.ads_manager_url} target="_blank" rel="noreferrer">{tr('Open in Ads Manager', 'Відкрити в Ads Manager')}</a>}{item.status === 'failed' && <button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'retry')}><RotateCcw />{tr('Retry safely', 'Безпечно повторити')}</button>}{item.status === 'staged' && <button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'sync')}><RefreshCcw />{tr('Sync status', 'Синхронізувати статус')}</button>}</footer></article>)}</div>}
    </section>
  </div>
}
