import { AlertTriangle, CheckCircle2, ExternalLink, MapPin, Megaphone, RefreshCcw, RotateCcw, Search, ShieldCheck, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { downloadBlob } from '../components/PostPublishing'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type { MetaAdsConnection, MetaAdsControlAction, MetaAdsDeployment, MetaAdsLocation, MetaAdsPresetVersion, MetaAdsProjectWorkspace, MetaAdsSourceVersion } from '../types'

const runningStates = new Set(['queued', 'creating_campaign', 'creating_ad_set', 'uploading_image', 'creating_creative', 'creating_ad'])
const categories = ['NONE', 'CREDIT', 'EMPLOYMENT', 'HOUSING', 'ISSUES_ELECTIONS_POLITICS', 'FINANCIAL_PRODUCTS_SERVICES', 'ONLINE_GAMBLING_AND_GAMING']
const metaAppDashboardUrl = 'https://developers.facebook.com/apps/'
const metaConsoles = [
  { href: 'https://business.facebook.com/settings', en: 'Business settings', uk: 'Налаштування бізнесу', detailEn: 'Portfolio and assigned business assets', detailUk: 'Портфоліо та призначені бізнес-активи' },
  { href: 'https://business.facebook.com/settings/system-users', en: 'System users', uk: 'Системні користувачі', detailEn: 'App role, assets and token generation', detailUk: 'Роль застосунку, активи та створення токена' },
  { href: metaAppDashboardUrl, en: 'App dashboard', uk: 'Панель застосунків', detailEn: 'Marketing API app and access level', detailUk: 'Застосунок Marketing API та рівень доступу' },
  { href: 'https://business.facebook.com/settings/ad-accounts', en: 'Ad accounts', uk: 'Рекламні акаунти', detailEn: 'Account status, access and payment setup', detailUk: 'Статус акаунта, доступ і налаштування оплати' },
  { href: 'https://business.facebook.com/settings/pages', en: 'Facebook Pages', uk: 'Сторінки Facebook', detailEn: 'Page ownership and system-user access', detailUk: 'Власність Page і доступ системного користувача' },
  { href: 'https://business.facebook.com/settings/instagram-accounts', en: 'Instagram accounts', uk: 'Акаунти Instagram', detailEn: 'Professional account and connected assets', detailUk: 'Професійний акаунт і пов’язані активи' },
  { href: 'https://business.facebook.com/events_manager2/list/pixel/1056720310312959/overview', en: 'Events Manager', uk: 'Менеджер подій', detailEn: 'Pixel PageView activity and diagnostics', detailUk: 'Події PageView і діагностика Pixel' },
  { href: 'https://developers.facebook.com/tools/debug/accesstoken/', en: 'Token debugger', uk: 'Перевірка токена', detailEn: 'Expiry, app and granted permissions', detailUk: 'Строк дії, застосунок і надані дозволи' },
]

function short(value?: string | null) { return value ? value.length > 22 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value : '—' }
function presetGeography(preset: MetaAdsPresetVersion['specification']) {
  return preset.cities?.length
    ? preset.cities.map(city => `${city.name} · ${city.radius_km} km`).join(', ')
    : preset.countries.join(', ')
}

interface PresetCity { key: string; name: string; country_code: string; radius_km: number }
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

function budgetLabel(value: number, currency: string | undefined, language: Language) {
  if (!currency) return `${value} ${language === 'uk' ? 'мін. од.' : 'minor units'}`
  try {
    const formatter = new Intl.NumberFormat(language === 'uk' ? 'uk-UA' : 'en-US', {
      style: 'currency', currency,
    })
    const fractionDigits = formatter.resolvedOptions().maximumFractionDigits ?? 2
    return `${formatter.format(value / (10 ** fractionDigits))} (${value} ${language === 'uk' ? 'мін. од.' : 'minor units'})`
  } catch {
    return `${value} ${currency} ${language === 'uk' ? 'мін. од.' : 'minor units'}`
  }
}

function isBudgetTooLow(deployment: MetaAdsDeployment) {
  return String(deployment.error?.provider_context?.subcode || '') === '1885272'
}

function isMetaAppDevelopmentMode(deployment: MetaAdsDeployment) {
  return String(deployment.error?.provider_context?.subcode || '') === '1885183'
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
  const [presetErrors, setPresetErrors] = useState<Record<string, string>>({})
  const [pendingControl, setPendingControl] = useState<MetaAdsControlAction | null>(null)
  const [kpiTarget, setKpiTarget] = useState('500')
  const [budgetDraft, setBudgetDraft] = useState<Record<string, string>>({})
  const [scheduleDraft, setScheduleDraft] = useState<Record<string, { start: string; end: string }>>({})
  const [preset, setPreset] = useState<PresetDraft>({
    name: '', geo_mode: 'countries', countries: 'UA', city_country_code: 'UA', cities: [],
    age_min: 25, age_max: 55, gender: 'all', daily_budget_minor: 500,
  })
  const [locationQuery, setLocationQuery] = useState('Kyiv')
  const [locationResults, setLocationResults] = useState<MetaAdsLocation[]>([])
  const [locationBusy, setLocationBusy] = useState(false)
  const [locationError, setLocationError] = useState('')
  const [stageError, setStageError] = useState('')
  const epoch = useRef(0)
  const activeProject = useRef<string | null>(null)
  const reloadInFlight = useRef<{ projectId: string; promise: Promise<void> } | null>(null)
  const verifiedConnection = useRef<MetaAdsConnection | null>(null)
  const presetSection = useRef<HTMLElement | null>(null)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const base = projectId ? `/api/v1/ads/projects/${projectId}` : ''

  const applyWorkspace = (value: MetaAdsProjectWorkspace) => {
    const connection = !value.connection.verified && verifiedConnection.current?.verified
      ? verifiedConnection.current
      : value.connection
    setWorkspace({ ...value, connection })
    setSelectedPresetId(current => value.presets.some(item => item.preset_id === current) ? current : value.presets[0]?.preset_id || '')
    setSelectedSource(current => value.sources.find(item => item.creative_id === current?.creative_id && item.version === current.version) || value.sources.find(item => item.creative_id === initialSource.current.creative && item.version === initialSource.current.version) || (initialSource.current.creative ? null : value.sources[0]) || null)
    setError('')
  }

  const reload = async (quiet = false) => {
    if (!projectId) return
    if (activeProject.current !== projectId) {
      activeProject.current = projectId
      epoch.current += 1
      verifiedConnection.current = null
    }
    if (reloadInFlight.current?.projectId === projectId) return reloadInFlight.current.promise
    const current = epoch.current
    const requestProject = projectId
    if (!quiet) { setWorkspace(null); setError(''); setNotice(''); setStageError('') }
    const promise = (async () => {
      try {
        const value = await api.get<MetaAdsProjectWorkspace>(base)
        if (value.connection.verified) verifiedConnection.current = value.connection
        if (current === epoch.current) applyWorkspace(value)
        const cached = verifiedConnection.current
        if (value.connection.configured && !value.connection.verified && (!quiet || !cached?.verified)) {
          const connection = await api.get<MetaAdsProjectWorkspace['connection']>('/api/v1/ads/connection', { deadlineMs: 120_000 })
          if (connection.verified) verifiedConnection.current = connection
          if (current === epoch.current) setWorkspace(existing => existing ? { ...existing, connection } : existing)
        }
      } catch (cause) {
        if (current === epoch.current) setError(cause instanceof Error ? cause.message : String(cause))
      }
    })()
    reloadInFlight.current = { projectId: requestProject, promise }
    try { await promise } finally {
      if (reloadInFlight.current?.promise === promise) reloadInFlight.current = null
    }
  }

  useEffect(() => {
    if (projectId) void reload()
    else {
      activeProject.current = null
      epoch.current += 1
      verifiedConnection.current = null
      setWorkspace(null)
      setSelectedSource(null)
    }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

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
    if (error || !workspace?.deployments.some(item => runningStates.has(item.status))) return
    let cancelled = false
    let timer = window.setTimeout(async function poll() {
      await reload(true)
      if (!cancelled) timer = window.setTimeout(poll, 2_500)
    }, 2_500)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [workspace?.deployments.map(item => item.status).join('|'), error]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedPreset = useMemo(
    () => workspace?.presets.find(item => item.preset_id === selectedPresetId) || null,
    [workspace?.presets, selectedPresetId],
  )
  const minimumDailyBudget = workspace?.connection.account?.minimum_daily_budget_minor
  const accountCurrency = workspace?.connection.account?.currency
  const selectedPresetBudgetLow = Boolean(
    selectedPreset && minimumDailyBudget
    && selectedPreset.specification.daily_budget_minor < minimumDailyBudget,
  )

  useEffect(() => {
    if (!minimumDailyBudget) return
    setPreset(current => current.daily_budget_minor < minimumDailyBudget
      ? { ...current, daily_budget_minor: minimumDailyBudget }
      : current)
  }, [minimumDailyBudget])

  const prepareCompliantPreset = (source = selectedPreset?.specification) => {
    if (!source || !minimumDailyBudget) return
    setPreset({
      name: `${source.name} · ${tr('Meta minimum', 'мінімум Meta')}`.slice(0, 80),
      geo_mode: source.cities?.length ? 'cities' : 'countries',
      countries: source.countries.join(', '),
      city_country_code: source.cities?.[0]?.country_code || source.countries[0] || 'UA',
      cities: (source.cities || []).map(city => ({ ...city })),
      age_min: source.age_min, age_max: source.age_max, gender: source.gender,
      daily_budget_minor: Math.max(source.daily_budget_minor, minimumDailyBudget),
    })
    setPresetErrors({})
    setPresetOpen(true)
    window.requestAnimationFrame(() => presetSection.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }))
  }

  const createPreset = async () => {
    const errors: Record<string, string> = {}
    if (!preset.name.trim()) errors.name = tr('Enter a preset name.', 'Введіть назву пресета.')
    if (preset.geo_mode === 'countries' && !preset.countries.split(',').some(item => /^[A-Za-z]{2}$/.test(item.trim()))) errors.countries = tr('Enter at least one two-letter country code.', 'Введіть щонайменше один дволітерний код країни.')
    if (preset.geo_mode === 'cities' && !preset.cities.length) errors.cities = tr('Add at least one Meta city.', 'Додайте щонайменше одне місто Meta.')
    if (!Number.isInteger(preset.age_min) || preset.age_min < 18 || preset.age_min > 65) errors.age_min = tr('Use an integer age from 18 to 65.', 'Вкажіть цілий вік від 18 до 65.')
    if (!Number.isInteger(preset.age_max) || preset.age_max < preset.age_min || preset.age_max > 65) errors.age_max = tr('Maximum age must be an integer from the minimum age to 65.', 'Максимальний вік має бути цілим числом від мінімального віку до 65.')
    if (!Number.isInteger(preset.daily_budget_minor) || preset.daily_budget_minor < 1) errors.daily_budget_minor = tr('Enter a positive whole-number daily budget.', 'Введіть додатний цілий денний бюджет.')
    else if (minimumDailyBudget && preset.daily_budget_minor < minimumDailyBudget) {
      errors.daily_budget_minor = tr(
        `Meta currently requires at least ${budgetLabel(minimumDailyBudget, accountCurrency, language)}.`,
        `Meta зараз вимагає щонайменше ${budgetLabel(minimumDailyBudget, accountCurrency, language)}.`,
      )
    }
    setPresetErrors(errors)
    if (Object.keys(errors).length) return
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
      setPresetOpen(false); setPresetErrors({})
      setNotice(tr('Audience preset version saved.', 'Версію пресета аудиторії збережено.'))
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause)
      const match = message.match(/"fields":\{"([a-z_]+)":"([^"}]*)/)
      if (match) setPresetErrors(current => ({ ...current, [match[1]]: match[2] }))
      setError(message)
    } finally { setBusy(false) }
  }

  const proposeControl = async (deployment: MetaAdsDeployment, operation: 'activate' | 'pause' | 'set_budget' | 'set_schedule') => {
    if (!projectId) return
    const scope = operation === 'set_budget' || operation === 'set_schedule' ? 'ad_set' : 'ad'
    const baseControl = { request_id: crypto.randomUUID(), deployment_id: deployment.deployment_id, operation, scope }
    const schedule = scheduleDraft[deployment.deployment_id] || { start: '', end: '' }
    const value = operation === 'activate'
      ? { ...baseControl, kpi_target_minor: Number(kpiTarget) }
      : operation === 'set_budget'
        ? { ...baseControl, daily_budget_minor: Number(budgetDraft[deployment.deployment_id] || 0) }
        : operation === 'set_schedule'
          ? { ...baseControl, start_time: schedule.start ? new Date(schedule.start).toISOString() : null, end_time: schedule.end ? new Date(schedule.end).toISOString() : null }
        : baseControl
    setBusy(true); setError('')
    try {
      const response = await api.post<{ action: MetaAdsControlAction }>(`${base}/controls`, value)
      setPendingControl(response.action)
      setNotice(tr('Review the exact Meta change, then confirm it.', 'Перевірте точну зміну Meta, а потім підтвердьте її.'))
      await reload(true)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  const confirmControl = async () => {
    if (!pendingControl || !projectId) return
    setBusy(true); setError('')
    try {
      await api.post(`${base}/controls/${pendingControl.action_id}/confirm`, { confirmed: true }, { deadlineMs: 120_000 })
      setNotice(tr('Confirmed. PTW reconciled the selected Meta objects.', 'Підтверджено. PTW звірив вибрані об’єкти Meta.'))
      setPendingControl(null); await reload(true)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  const refreshInsights = async (deployment: MetaAdsDeployment) => {
    if (!projectId) return
    setBusy(true); setError('')
    try { await api.post(`${base}/deployments/${deployment.deployment_id}/insights`, { window_days: 7 }, { deadlineMs: 120_000 }); await reload(true) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
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
    setBusy(true); setError(''); setNotice(''); setStageError('')
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
      const result = await api.post<{ deployment: MetaAdsDeployment; created: boolean }>(
        `${base}/deployments`, { ...payload, request_id: requestId }, { deadlineMs: 120_000 },
      )
      setWorkspace(existing => existing ? {
        ...existing,
        deployments: [result.deployment, ...existing.deployments.filter(item => item.deployment_id !== result.deployment.deployment_id)],
      } : existing)
      await reload(true)
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause)
      setError(message); setStageError(message)
    } finally { setBusy(false) }
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
    if (action === 'retry' && isBudgetTooLow(deployment)) {
      prepareCompliantPreset(deployment.specification.preset)
      return
    }
    setBusy(true); setError('')
    try { await api.post(`${base}/deployments/${deployment.deployment_id}/${action}`, {}); await reload(true) }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }

  if (!projectId) return <Empty>{tr('Select a Project to stage approved Posts.', 'Виберіть Project, щоб підготувати затверджені дописи.')}</Empty>
  if (!workspace && !error) return <Loading language={language} />
  if (!workspace && error) return <ErrorState message={error} retry={() => void reload()} language={language} />
  if (!workspace) return null
  const connected = workspace.connection.configured && workspace.connection.verified
  const websiteReady = connected && Boolean(workspace.connection.pixel)
  const adsManagerUrl = workspace.ads_manager_url || 'https://adsmanager.facebook.com/adsmanager/manage/campaigns'
  const latestDeployment = workspace.deployments[0] || null
  const latestRunning = Boolean(latestDeployment && runningStates.has(latestDeployment.status))
  const latestBudgetFailure = Boolean(latestDeployment && isBudgetTooLow(latestDeployment))
  const latestAppModeFailure = Boolean(latestDeployment && isMetaAppDevelopmentMode(latestDeployment))
  const latestFailureMessage = latestBudgetFailure && minimumDailyBudget
    ? tr(
      `Meta rejected the Ad Set because ${budgetLabel(latestDeployment!.specification.preset.daily_budget_minor, accountCurrency, language)} is below the current minimum of ${budgetLabel(minimumDailyBudget, accountCurrency, language)}. Create and select a new immutable preset; retrying this unchanged request would fail again.`,
      `Meta відхилила Ad Set, бо ${budgetLabel(latestDeployment!.specification.preset.daily_budget_minor, accountCurrency, language)} нижче поточного мінімуму ${budgetLabel(minimumDailyBudget, accountCurrency, language)}. Створіть і виберіть новий незмінний пресет; повторення цього незміненого запиту знову завершиться помилкою.`,
    )
    : latestAppModeFailure
      ? tr(
        'Meta blocked Creative creation because the PTW Local Ads app is still in Development mode. The Campaign, Ad Set, and approved image are already saved and PAUSED.',
        'Meta заблокувала створення Creative, бо застосунок PTW Local Ads досі в режимі Development. Campaign, Ad Set і затверджене зображення вже збережені та залишаються PAUSED.',
      )
    : latestDeployment?.error?.error_message || ''
  const activeCreationIndex = latestDeployment ? ({
    queued: 0, creating_campaign: 0, creating_ad_set: 1, uploading_image: 2,
    creating_creative: 3, creating_ad: 4, staged: 4, failed: -1,
  } as const)[latestDeployment.status] : -1
  const creationSteps = latestDeployment ? [
    { label: tr('Campaign', 'Кампанія'), complete: Boolean(latestDeployment.meta_campaign_id), id: latestDeployment.meta_campaign_id, waiting: tr('Waiting to create', 'Очікує створення') },
    { label: 'Ad Set', complete: Boolean(latestDeployment.meta_ad_set_id), id: latestDeployment.meta_ad_set_id, waiting: tr('Waiting for Campaign', 'Очікує Campaign') },
    { label: tr('Approved image', 'Затверджене зображення'), complete: Boolean(latestDeployment.meta_image_hash), id: latestDeployment.meta_image_hash, waiting: tr('Waiting for Ad Set', 'Очікує Ad Set') },
    { label: tr('Creative', 'Креатив'), complete: Boolean(latestDeployment.meta_creative_id), id: latestDeployment.meta_creative_id, waiting: tr('Waiting for image upload', 'Очікує завантаження зображення') },
    { label: tr('Ad', 'Реклама'), complete: Boolean(latestDeployment.meta_ad_id), id: latestDeployment.meta_ad_id, waiting: tr('Waiting for Creative', 'Очікує Creative') },
  ].map((step, index, steps) => {
    const firstMissing = steps.findIndex(item => !item.complete)
    const state = step.complete ? 'complete'
      : latestDeployment.status === 'failed' && index === firstMissing ? 'failed'
        : latestRunning && index === activeCreationIndex ? 'active'
          : 'waiting'
    const detail = state === 'complete'
      ? index === 0 ? tr('Created · PAUSED', 'Створено · PAUSED') : index === 2 ? tr('Uploaded from approved Post', 'Завантажено із затвердженого допису') : tr('Created', 'Створено')
      : state === 'active' ? tr('Creating now…', 'Створюється зараз…')
        : state === 'failed' ? tr('Stopped here', 'Зупинено тут') : step.waiting
    return { ...step, index, state, detail }
  }) : []
  const stoppedStep = creationSteps.find(step => step.state === 'failed')
  const activeStep = creationSteps.find(step => step.state === 'active')
  const creationTitle = latestDeployment?.status === 'staged'
    ? tr('Complete — the Meta Ad is created and PAUSED.', 'Готово — рекламу створено в Meta зі статусом PAUSED.')
    : latestDeployment?.status === 'failed'
      ? tr(`Creation stopped at ${stoppedStep?.label || 'Meta'}. Nothing was activated.`, `Створення зупинилось на етапі «${stoppedStep?.label || 'Meta'}». Нічого не активовано.`)
      : tr(`Request accepted — creating ${activeStep?.label || 'the Campaign'}…`, `Запит прийнято — створюється «${activeStep?.label || 'Campaign'}»…`)
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
      ok: Boolean(workspace.connection.pixel),
      en: 'Website Pixel available', uk: 'Pixel сайту доступний',
      detail: workspace.connection.pixel?.name || tr('Assign the Natal Service Website Pixel to this Ad Account.', 'Призначте Pixel Natal Service Website цьому рекламному акаунту.'),
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
    {latestDeployment && <a className={`ads-current-status is-${latestDeployment.status}`} href="#ads-creation-status">
      <span><small>{tr('LATEST META REQUEST', 'ОСТАННІЙ ЗАПИТ META')}</small><strong>{creationTitle}</strong></span>
      <span>{tr('View 5 creation steps', 'Переглянути 5 етапів')} ↓</span>
    </a>}
    {pendingControl && <section className="panel" aria-label={tr('Confirm Meta control', 'Підтвердити керування Meta')}>
      <small>{tr('OWNER CONFIRMATION REQUIRED', 'ПОТРІБНЕ ПІДТВЕРДЖЕННЯ ВЛАСНИКА')}</small>
      <h2>{tr('Review the exact paid-delivery change', 'Перевірте точну зміну платного показу')}</h2>
      <p>{pendingControl.action.operation} · {pendingControl.action.affected_objects.join(' → ')} · <code>{short(pendingControl.deployment_id)}</code></p>
      {pendingControl.action.kpi_target_minor && <p>{tr('7-day KPI target', 'Ціль KPI за 7 днів')}: {pendingControl.action.kpi_target_minor} {workspace.connection.account?.currency || tr('minor units', 'мін. од.')}</p>}
      {pendingControl.action.daily_budget_minor && <p>{tr('Daily budget', 'Денний бюджет')}: {pendingControl.action.daily_budget_minor} {workspace.connection.account?.currency || tr('minor units', 'мін. од.')}</p>}
      <button className="primary" disabled={busy} onClick={() => void confirmControl()}>{tr('Confirm Meta change', 'Підтвердити зміну Meta')}</button>{' '}
      <button className="secondary" disabled={busy} onClick={() => setPendingControl(null)}>{tr('Cancel', 'Скасувати')}</button>
    </section>}

    <section className={`panel ads-connection ${connected ? 'is-ready' : 'is-warning'}`}>
      <small>{tr('CONNECTION', 'ПІДКЛЮЧЕННЯ')}</small>
      <div className="ads-connection-grid">
        <div>{connected ? <CheckCircle2 /> : <AlertTriangle />}<span><strong>{connected ? tr('Meta assets verified', 'Активи Meta перевірено') : tr('Meta staging disabled', 'Staging Meta вимкнено')}</strong><small>{workspace.connection.explanation || tr('System user and assigned assets are available.', 'Системний користувач і призначені активи доступні.')}</small></span></div>
        <dl><div><dt>{tr('Ad Account', 'Рекламний акаунт')}</dt><dd>{workspace.connection.account?.name || '—'} <code>{short(workspace.connection.account?.id)}</code></dd></div><div><dt>{tr('Minimum daily budget', 'Мінімальний денний бюджет')}</dt><dd>{minimumDailyBudget ? budgetLabel(minimumDailyBudget, accountCurrency, language) : '—'}</dd></div><div><dt>Facebook Page</dt><dd>{workspace.connection.page?.name || '—'} <code>{short(workspace.connection.page?.id)}</code></dd></div><div><dt>Instagram</dt><dd>{workspace.connection.instagram?.username ? `@${workspace.connection.instagram.username}` : '—'} <code>{short(workspace.connection.instagram?.id)}</code></dd></div><div><dt>Meta Pixel</dt><dd>{workspace.connection.pixel?.name || '—'} <code>{short(workspace.connection.pixel?.id)}</code></dd></div></dl>
        {workspace.connection.available && <p className="ads-available">{tr('Available to this system user', 'Доступно цьому системному користувачу')}: {workspace.connection.available.ad_accounts.length} Ad Account · {workspace.connection.available.pages.length} Page · {workspace.connection.available.instagram_accounts.length} Instagram · {workspace.connection.available.pixels?.length || 0} Pixel</p>}
      </div>
    </section>

    <details className="panel ads-setup" open={!connected || undefined}>
      <summary className="ads-section-title"><div><small>{tr('READINESS & CONSOLES', 'ГОТОВНІСТЬ І КОНСОЛІ')}</small><h2>{connected ? tr('Meta setup', 'Налаштування Meta') : tr('What is still needed', 'Що ще потрібно')}</h2></div><span>{setupChecks.filter(item => item.ok).length}/{setupChecks.length}</span></summary>
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
    </details>

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
            <label>{tr('Audience preset version', 'Версія пресета аудиторії')}<select value={selectedPresetId} onChange={event => setSelectedPresetId(event.target.value)}><option value="">{tr('Create a preset first', 'Спочатку створіть пресет')}</option>{workspace.presets.map(item => <option key={item.preset_id} value={item.preset_id}>v{item.version} · {item.specification.name} · {budgetLabel(item.specification.daily_budget_minor, accountCurrency, language)}</option>)}</select></label>
            <label>{tr('Special ad category', 'Спеціальна категорія реклами')}<select value={category} onChange={event => setCategory(event.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label>
          </div>
          <div className="ads-fixed"><span>Instagram Feed</span><span>{destination === 'WEBSITE' ? 'OUTCOME_TRAFFIC' : 'OUTCOME_ENGAGEMENT'}</span><span>{destination === 'WEBSITE' ? 'Website · Learn more' : 'Instagram Direct'}</span><span>{destination === 'WEBSITE' ? 'LANDING_PAGE_VIEWS' : 'CONVERSATIONS'}</span><span>IMPRESSIONS</span><span>Lowest cost</span><span>Enhancements: OFF</span></div>
          <div className="ads-request-review" role="group" aria-label={tr('Details PTW will send to Meta', 'Дані, які PTW надішле в Meta')}>
            <small>{tr('THIS CLICK WILL USE', 'ЦЕЙ КЛІК ВИКОРИСТАЄ')}</small>
            <dl>
              <div><dt>{tr('Image', 'Зображення')}</dt><dd><CheckCircle2 /> Post {selectedSource.creative_ordinal} · v{selectedSource.version} · {tr('approved PNG', 'затверджений PNG')}</dd></div>
              <div><dt>{tr('Destination', 'Призначення')}</dt><dd>{destination === 'WEBSITE' && workspace.landing ? <a href={workspace.landing.canonical_url} target="_blank" rel="noreferrer">{workspace.landing.canonical_url}</a> : 'Instagram Direct'}</dd></div>
              <div><dt>{tr('Audience', 'Аудиторія')}</dt><dd>{selectedPreset ? `v${selectedPreset.version} · ${selectedPreset.specification.name} · ${budgetLabel(selectedPreset.specification.daily_budget_minor, accountCurrency, language)}` : tr('Not selected', 'Не вибрано')}</dd></div>
              <div><dt>{tr('Safety', 'Безпека')}</dt><dd>PAUSED · {tr('no activation or spend', 'без активації та витрат')}</dd></div>
            </dl>
          </div>
          {selectedPresetBudgetLow && <div className="ads-stage-feedback is-failed" role="alert"><strong>{tr('This preset cannot be staged.', 'Цей пресет не можна передати в staging.')}</strong><p>{tr(
            `${budgetLabel(selectedPreset!.specification.daily_budget_minor, accountCurrency, language)} is below Meta's current minimum of ${budgetLabel(minimumDailyBudget!, accountCurrency, language)}.`,
            `${budgetLabel(selectedPreset!.specification.daily_budget_minor, accountCurrency, language)} нижче поточного мінімуму Meta ${budgetLabel(minimumDailyBudget!, accountCurrency, language)}.`,
          )}</p><button type="button" className="secondary" onClick={() => prepareCompliantPreset()}>{tr('Prepare a compliant preset version', 'Підготувати допустиму версію пресета')}</button></div>}
          <button className="primary large" disabled={!connected || !selectedPreset || selectedPresetBudgetLow || busy || !headline.trim() || !primaryText.trim() || !previewUrl || (destination === 'WEBSITE' ? (!workspace.landing || !websiteReady) : !welcomeMessage.trim())} onClick={() => void stage()}><Megaphone />{busy ? tr('Working…', 'Виконується…') : tr('Create complete PAUSED ad in Meta', 'Створити повну PAUSED-рекламу в Meta')}</button>
          {stageError && <div className="ads-stage-feedback is-failed" role="alert"><strong>{tr('The request was not reserved.', 'Запит не зарезервовано.')}</strong><p>{stageError}</p></div>}
          {latestDeployment && <div id="ads-creation-status" className={`ads-stage-feedback is-${latestDeployment.status}`} role={latestDeployment.status === 'failed' ? 'alert' : 'status'} aria-live="polite">
            <div className="ads-stage-heading">{latestDeployment.status === 'failed' ? <AlertTriangle /> : latestDeployment.status === 'staged' ? <CheckCircle2 /> : <RefreshCcw className="spin" />}<span><small>{tr('CREATION STATUS', 'СТАТУС СТВОРЕННЯ')}</small><strong>{creationTitle}</strong></span></div>
            <ol className="ads-creation-progress" aria-label={tr('Meta creation progress', 'Хід створення в Meta')}>
              {creationSteps.map(step => <li key={step.label} className={`is-${step.state}`}>
                <span className="ads-step-marker">{step.state === 'complete' ? <CheckCircle2 /> : step.state === 'failed' ? <AlertTriangle /> : step.state === 'active' ? <RefreshCcw className="spin" /> : step.index + 1}</span>
                <span><strong>{step.label}</strong><small>{step.detail}{step.id ? ` · ${short(step.id)}` : ''}</small></span>
              </li>)}
            </ol>
            <p className="ads-next-action"><strong>{tr('Next:', 'Далі:')}</strong> {latestRunning
              ? tr('Wait here; this status updates automatically.', 'Залишайтесь тут; статус оновиться автоматично.')
              : latestDeployment.status === 'staged'
                ? tr('Open the created Ad and review its image, copy, and destination in Meta.', 'Відкрийте створену рекламу та перевірте зображення, текст і призначення в Meta.')
                : latestBudgetFailure && minimumDailyBudget
                  ? tr(`Create a new preset at or above ${budgetLabel(minimumDailyBudget, accountCurrency, language)}, select it, and create again.`, `Створіть новий пресет не нижче ${budgetLabel(minimumDailyBudget, accountCurrency, language)}, виберіть його й запустіть створення ще раз.`)
                  : latestAppModeFailure
                    ? tr('Open the Meta app dashboard, switch PTW Local Ads from Development to Live, then retry this same deployment once.', 'Відкрийте панель застосунку Meta, переведіть PTW Local Ads із Development у Live, а потім один раз повторіть цей самий deployment.')
                  : tr('Read the error below, then use the safe retry in deployment history.', 'Прочитайте помилку нижче, потім скористайтеся безпечним повтором в історії deployment.')}</p>
            {latestFailureMessage && <p>{latestFailureMessage}</p>}
            <details><summary>{tr('Technical details', 'Технічні деталі')}</summary><small>PTW <code>{short(latestDeployment.deployment_id)}</code> · {latestDeployment.status} · SHA-256 <code>{short(latestDeployment.render_sha256)}</code></small>{latestDeployment.specification.landing?.canonical_url && <a href={latestDeployment.specification.landing.canonical_url} target="_blank" rel="noreferrer">{latestDeployment.specification.landing.canonical_url}</a>}</details>
            {latestBudgetFailure && minimumDailyBudget && <button type="button" className="secondary" onClick={() => prepareCompliantPreset(latestDeployment.specification.preset)}>{tr('Prepare a higher-budget preset', 'Підготувати пресет із вищим бюджетом')}</button>}
            {latestAppModeFailure && <div className="post-publishing-actions"><a className="secondary" href={metaAppDashboardUrl} target="_blank" rel="noreferrer">{tr('Open Meta app dashboard', 'Відкрити панель застосунку Meta')} <ExternalLink /></a><button type="button" className="secondary" disabled={busy} onClick={() => void deploymentAction(latestDeployment, 'retry')}><RotateCcw />{tr('App is Live — retry this deployment once', 'Застосунок уже Live — повторити цей deployment один раз')}</button></div>}
            {latestDeployment.status === 'staged' && latestDeployment.ads_manager_url && <a className="secondary" href={latestDeployment.ads_manager_url} target="_blank" rel="noreferrer">{tr('Open the created PTW Ad', 'Відкрити створену PTW-рекламу')} <ExternalLink /></a>}
          </div>}
          <div className="post-publishing-actions"><button className="secondary" disabled={busy} onClick={() => void exportImage()}>{tr('Download image', 'Завантажити зображення')}</button><button className="secondary" onClick={() => void copy([headline, primaryText].filter(Boolean).join('\n\n'))}>{tr('Copy ad text', 'Копіювати текст реклами')}</button>{workspace.landing && <button className="secondary" onClick={() => void copy(workspace.landing!.canonical_url)}>{tr('Copy landing URL', 'Копіювати URL лендінгу')}</button>}<a className="secondary" href={adsManagerUrl} target="_blank" rel="noreferrer">{tr('Open in Ads Manager', 'Відкрити в Ads Manager')}</a></div>
          <p>{tr('Export is available without Meta access. The generic Ads Manager link is manual and does not fill its forms; after PTW completes all five steps, use “Open the created PTW Ad” above.', 'Експорт доступний без підключення Meta. Загальне посилання Ads Manager призначене для ручної роботи й не заповнює форми; після завершення PTW усіх п’яти етапів використайте «Відкрити створену PTW-рекламу» вище.')}</p>
        </> : <p>{tr('Select an approved Post version.' , 'Виберіть затверджену версію допису.')}</p>}
      </div>
    </section>

    <section className="panel ads-presets" ref={presetSection}>
      <div className="ads-section-title"><div><small>{tr('VERSIONED TARGETING', 'ВЕРСІЙНИЙ TARGETING')}</small><h2>{tr('Audience presets', 'Пресети аудиторії')}</h2></div><button className="secondary" onClick={() => setPresetOpen(value => !value)}>{presetOpen ? tr('Close', 'Закрити') : tr('New preset', 'Новий пресет')}</button></div>
      {presetOpen && <div className="ads-preset-form">
        <label>{tr('Name', 'Назва')}<input value={preset.name} maxLength={80} onChange={event => setPreset(current => ({ ...current, name: event.target.value }))} />{presetErrors.name && <small role="alert">{presetErrors.name}</small>}</label>
        <label>{tr('Geography', 'Географія')}<select value={preset.geo_mode} onChange={event => setPreset(current => ({ ...current, geo_mode: event.target.value as PresetDraft['geo_mode'] }))}><option value="countries">{tr('Entire countries', 'Цілі країни')}</option><option value="cities">{tr('City + radius', 'Місто + радіус')}</option></select></label>
        {preset.geo_mode === 'countries' ? <label>{tr('Countries (ISO, comma-separated)', 'Країни (ISO, через кому)')}<input value={preset.countries} onChange={event => setPreset(current => ({ ...current, countries: event.target.value }))} />{presetErrors.countries && <small role="alert">{presetErrors.countries}</small>}</label> : <div className="ads-city-targeting">
          <div className="ads-city-search">
            <label>{tr('Country code', 'Код країни')}<input value={preset.city_country_code} maxLength={2} onChange={event => setPreset(current => ({ ...current, city_country_code: event.target.value.toUpperCase() }))} /></label>
            <label>{tr('Search city in Meta', 'Знайти місто в Meta')}<input value={locationQuery} maxLength={80} onChange={event => setLocationQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void searchLocations() } }} /></label>
            <button className="secondary" type="button" disabled={!connected || locationBusy || locationQuery.trim().length < 2 || preset.city_country_code.trim().length !== 2} onClick={() => void searchLocations()}><Search />{locationBusy ? tr('Searching…', 'Пошук…') : tr('Search Meta', 'Знайти в Meta')}</button>
          </div>
          {!connected && <p className="ads-location-help">{tr('Connect and verify Meta first; city keys come directly from its targeting search.', 'Спочатку під’єднайте та перевірте Meta; ключі міст беруться безпосередньо з її targeting search.')}</p>}
          {locationError && <p className="ads-location-error" role="alert">{locationError}</p>}
          {locationResults.length > 0 && <div className="ads-location-results">{locationResults.map(city => <button type="button" key={city.key} disabled={preset.cities.some(item => item.key === city.key)} onClick={() => addCity(city)}><MapPin /><span><strong>{city.name}</strong><small>{[city.region, city.country_name].filter(Boolean).join(', ')}</small></span>{preset.cities.some(item => item.key === city.key) ? <CheckCircle2 /> : tr('Add', 'Додати')}</button>)}</div>}
          {presetErrors.cities && <small role="alert">{presetErrors.cities}</small>}{preset.cities.length > 0 && <div className="ads-selected-cities">{preset.cities.map(city => <article key={city.key}><span><MapPin /><strong>{city.name}</strong><small>{city.country_code} · Meta key {city.key}</small></span><label>{tr('Radius, km', 'Радіус, км')}<input type="number" min="17" max="80" value={city.radius_km} onChange={event => setPreset(current => ({ ...current, cities: current.cities.map(item => item.key === city.key ? { ...item, radius_km: Number(event.target.value) } : item) }))} /></label><button type="button" className="icon-button" aria-label={tr(`Remove ${city.name}`, `Видалити ${city.name}`)} onClick={() => removeCity(city.key)}><X /></button></article>)}</div>}
        </div>}
        <label>{tr('Minimum age', 'Мінімальний вік')}<input type="number" min="18" max="65" value={preset.age_min} onChange={event => setPreset(current => ({ ...current, age_min: Number(event.target.value) }))} />{presetErrors.age_min && <small role="alert">{presetErrors.age_min}</small>}</label>
        <label>{tr('Maximum age', 'Максимальний вік')}<input type="number" min="18" max="65" value={preset.age_max} onChange={event => setPreset(current => ({ ...current, age_max: Number(event.target.value) }))} />{presetErrors.age_max && <small role="alert">{presetErrors.age_max}</small>}</label>
        <label>{tr('Gender', 'Стать')}<select value={preset.gender} onChange={event => setPreset(current => ({ ...current, gender: event.target.value }))}><option value="all">{tr('All', 'Усі')}</option><option value="women">{tr('Women', 'Жінки')}</option><option value="men">{tr('Men', 'Чоловіки')}</option></select></label>
        <label>{tr('Daily budget (Meta minor units)', 'Денний бюджет (мінімальні одиниці Meta)')}<input type="number" min={minimumDailyBudget || 1} value={preset.daily_budget_minor} onChange={event => setPreset(current => ({ ...current, daily_budget_minor: Number(event.target.value) }))} /><small>{tr('Entered amount', 'Введена сума')}: {budgetLabel(preset.daily_budget_minor || 0, accountCurrency, language)}{minimumDailyBudget ? ` · ${tr('Meta minimum', 'мінімум Meta')}: ${budgetLabel(minimumDailyBudget, accountCurrency, language)}` : ''}</small>{presetErrors.daily_budget_minor && <small role="alert">{presetErrors.daily_budget_minor}</small>}</label>
        <button className="primary" disabled={busy || !preset.name.trim() || (preset.geo_mode === 'cities' ? !preset.cities.length : !preset.countries.trim())} onClick={() => void createPreset()}>{tr('Save immutable version', 'Зберегти незмінну версію')}</button>
      </div>}
      {!presetOpen && <div className="ads-preset-list">{workspace.presets.map(item => <button key={item.preset_id} className={selectedPresetId === item.preset_id ? 'selected' : ''} onClick={() => setSelectedPresetId(item.preset_id)}><strong>v{item.version} · {item.specification.name}</strong><span>{presetGeography(item.specification)} · {item.specification.age_min}–{item.specification.age_max} · {item.specification.gender}</span><span>{tr('Daily', 'На день')}: {budgetLabel(item.specification.daily_budget_minor, accountCurrency, language)}{minimumDailyBudget && item.specification.daily_budget_minor < minimumDailyBudget ? ` · ${tr('below Meta minimum', 'нижче мінімуму Meta')}` : ''}</span><code>{short(item.specification_sha256)}</code></button>)}</div>}
    </section>

    <section className="panel ads-history">
      <div className="ads-section-title"><div><small>{tr('APPEND-ONLY HISTORY', 'APPEND-ONLY ІСТОРІЯ')}</small><h2>{tr('Staging deployments', 'Staging deployments')}</h2></div>{workspace.ads_manager_url && <a className="secondary" href={workspace.ads_manager_url} target="_blank" rel="noreferrer">Ads Manager <ExternalLink /></a>}</div>
      {workspace.deployments.length === 0 ? <p>{tr('No deployment has been staged for this Project.', 'Для цього Project ще немає staging deployment.')}</p> : <div className="ads-deployment-list">{workspace.deployments.map(item => <article key={item.deployment_id} className={`ads-deployment is-${item.status}`}><header><div><strong>Post v{item.source_version}</strong><code>{short(item.deployment_id)}</code></div><span>{runningStates.has(item.status) && <RefreshCcw className="spin" />}{item.status === 'staged' ? tr('Created in Meta', 'Створено в Meta') : item.status}</span></header><dl><div><dt>Campaign</dt><dd>{short(item.meta_campaign_id)} · {objectStatus(item.status_snapshot?.campaign)}</dd></div><div><dt>Ad Set</dt><dd>{short(item.meta_ad_set_id)} · {objectStatus(item.status_snapshot?.ad_set)}</dd></div><div><dt>{tr('Approved image', 'Затверджене зображення')}</dt><dd>{item.meta_image_hash ? tr('Uploaded to Meta', 'Завантажено в Meta') : tr('Not uploaded', 'Не завантажено')} · <code>{short(item.render_sha256)}</code></dd></div><div><dt>Creative</dt><dd>{short(item.meta_creative_id)}</dd></div><div><dt>Ad</dt><dd>{short(item.meta_ad_id)} · {objectStatus(item.status_snapshot?.ad)}</dd></div>{item.specification.landing?.canonical_url && <div><dt>Landing</dt><dd><a href={item.specification.landing.canonical_url} target="_blank" rel="noreferrer">{item.specification.landing.canonical_url}</a></dd></div>}</dl>{workspace.recommendations?.[item.deployment_id]?.[0] && <p>{tr('7-day recommendation', 'Рекомендація за 7 днів')}: <strong>{workspace.recommendations[item.deployment_id][0].record.status}</strong></p>}{item.error?.error_message && <p role="alert">{isBudgetTooLow(item) && minimumDailyBudget ? tr(`The saved budget is below Meta's current minimum of ${budgetLabel(minimumDailyBudget, accountCurrency, language)}. Prepare a new preset; do not retry this unchanged request.`, `Збережений бюджет нижче поточного мінімуму Meta ${budgetLabel(minimumDailyBudget, accountCurrency, language)}. Підготуйте новий пресет; не повторюйте цей незмінений запит.`) : isMetaAppDevelopmentMode(item) ? tr('Meta Creative creation is blocked until PTW Local Ads is switched from Development to Live. Existing objects remain PAUSED.', 'Створення Meta Creative заблоковано, доки PTW Local Ads не буде переведено з Development у Live. Наявні об’єкти залишаються PAUSED.') : item.error.error_message}</p>}<footer>{item.ads_manager_url && <a className="secondary" href={item.ads_manager_url} target="_blank" rel="noreferrer">{item.meta_ad_id ? tr('Open created PTW Ad', 'Відкрити створену PTW-рекламу') : tr('Open created Meta objects', 'Відкрити створені об’єкти Meta')}</a>}{item.status === 'failed' && (isBudgetTooLow(item) && minimumDailyBudget ? <button className="secondary" disabled={busy} onClick={() => prepareCompliantPreset(item.specification.preset)}>{tr('Prepare higher-budget preset', 'Підготувати пресет із вищим бюджетом')}</button> : isMetaAppDevelopmentMode(item) ? <><a className="secondary" href={metaAppDashboardUrl} target="_blank" rel="noreferrer">{tr('Switch app to Live', 'Перевести застосунок у Live')} <ExternalLink /></a><button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'retry')}><RotateCcw />{tr('App is Live — retry once', 'Застосунок уже Live — повторити один раз')}</button></> : <button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'retry')}><RotateCcw />{tr('Retry safely', 'Безпечно повторити')}</button>)}{item.status === 'staged' && <><button className="secondary" disabled={busy} onClick={() => void deploymentAction(item, 'sync')}><RefreshCcw />{tr('Sync status', 'Синхронізувати статус')}</button><button className="secondary" disabled={busy} onClick={() => void proposeControl(item, 'activate')}>{tr('Activate with confirmation', 'Активувати з підтвердженням')}</button><button className="secondary" disabled={busy} onClick={() => void proposeControl(item, 'pause')}>{tr('Pause with confirmation', 'Пауза з підтвердженням')}</button><label>{tr('Daily budget', 'Денний бюджет')}<input type="number" min={minimumDailyBudget || 1} value={budgetDraft[item.deployment_id] || ''} onChange={event => setBudgetDraft(current => ({ ...current, [item.deployment_id]: event.target.value }))} /></label><button className="secondary" disabled={busy || !budgetDraft[item.deployment_id]} onClick={() => void proposeControl(item, 'set_budget')}>{tr('Review budget change', 'Перевірити зміну бюджету')}</button><label>{tr('Start (local time)', 'Початок (місцевий час)')}<input type="datetime-local" value={scheduleDraft[item.deployment_id]?.start || ''} onChange={event => setScheduleDraft(current => ({ ...current, [item.deployment_id]: { start: event.target.value, end: current[item.deployment_id]?.end || '' } }))} /></label><label>{tr('End (local time)', 'Кінець (місцевий час)')}<input type="datetime-local" value={scheduleDraft[item.deployment_id]?.end || ''} onChange={event => setScheduleDraft(current => ({ ...current, [item.deployment_id]: { start: current[item.deployment_id]?.start || '', end: event.target.value } }))} /></label><button className="secondary" disabled={busy || !(scheduleDraft[item.deployment_id]?.start || scheduleDraft[item.deployment_id]?.end)} onClick={() => void proposeControl(item, 'set_schedule')}>{tr('Review schedule change', 'Перевірити зміну розкладу')}</button><button className="secondary" disabled={busy} onClick={() => void refreshInsights(item)}>{tr('Refresh 7-day results', 'Оновити результати за 7 днів')}</button></>}</footer></article>)}</div>}
    </section>
  </div>
}
