import { useEffect, useRef, useState } from 'react'
import { Check, RefreshCcw, Save } from 'lucide-react'
import { ApiFailure, type ApiClient } from '../../api'
import type { Language } from '../../i18n'
import type { StudioPhoneMetricsDetail, StudioCheckpointResponse, StudioManualAgentResult, StudioPhoneScreenHistoryItem } from '../../types'
import { StudioSection } from './StudioSection'
import { StudioManualAgent } from './StudioManualAgent'
import { PostTemplatePicker } from './PostTemplatePicker'
import { ImageReferenceInput, imageReferencePayload } from '../ImageReferenceInput'
import { EditableColorField } from '../EditableColorField'
import { STUDIO_CHECKPOINT_DEADLINE_MS } from '../../studio-checkpoints'

type Scalar = string | number | boolean
export type DaddyConfiguration = { schema: string; preset: string; style: string; [key: string]: Scalar | Record<string, Scalar> }
type Copy = Record<string, string>
type AssetOperation = { slot: string; body: Record<string, unknown> }
type PendingAsset = AssetOperation & { remaining?: AssetOperation[] }
type Preset = { id: string; name: string; name_uk: string; description: string; slots: string[]; configuration: DaddyConfiguration }
export type DaddyDetail = Omit<StudioPhoneMetricsDetail, 'configuration' | 'content' | 'catalog'> & {
  configuration: DaddyConfiguration; content: Copy; required_asset_slots: string[]; asset_generation_available: boolean
  catalog: { presets: Preset[]; styles: string[]; enums: Record<string, string[]>; bounds: Record<string, [number, number]>; asset_slots: Record<string, { description: string }> }
}
const titles: Record<string, [string, string]> = {
  background: ['Background', 'Фон'], message: ['Message', 'Повідомлення'], device: ['Phone', 'Телефон'], subject: ['Subject', 'Головний об’єкт'],
  collage: ['Collage', 'Колаж'], offer: ['Offer / benefit', 'Пропозиція / користь'], brand: ['Brand placement', 'Розміщення бренду'], action: ['Action', 'Дія'], logo: ['Natal colors', 'Кольори Natal'],
  hero_title: ['Headline', 'Заголовок'], supporting_text: ['Supporting message', 'Підтримувальний текст'], cta: ['Action label', 'Текст дії'], feature_title: ['Feature title', 'Назва функції'],
  feature_text: ['Feature detail', 'Опис функції'], left_label: ['Left panel label', 'Лівий підпис'], right_label: ['Right panel label', 'Правий підпис'],
  screen: ['App screen', 'Екран застосунку'], scene: ['Scene', 'Сцена'], feature: ['Feature image', 'Зображення функції'], prop_one: ['First prop', 'Перший об’єкт'], prop_two: ['Second prop', 'Другий об’єкт'],
  x: ['Horizontal position (%)', 'Позиція по горизонталі (%)'], y: ['Vertical position (%)', 'Позиція по вертикалі (%)'], width: ['Width (%)', 'Ширина (%)'], height: ['Height (%)', 'Висота (%)'],
  enabled: ['Visible', 'Показувати'], title_size: ['Headline size', 'Розмір заголовка'], body_size: ['Body size', 'Розмір тексту'], gap: ['Spacing', 'Відступ'],
  focal_x: ['Horizontal focal point', 'Фокус по горизонталі'], focal_y: ['Vertical focal point', 'Фокус по вертикалі'], cutout: ['Remove background', 'Видалити фон'],
  color: ['Text / base color', 'Колір тексту / основи'], end_color: ['Gradient end', 'Кінець градієнта'], overlay: ['Overlay opacity', 'Прозорість накладання'], overlay_color: ['Overlay color', 'Колір накладання'],
  blur: ['Blur', 'Розмиття'], shape: ['Background shape', 'Форма фону'], rotation: ['Rotation (°)', 'Обертання (°)'], pose: ['Device pose', 'Положення телефона'], shadow: ['Shadow', 'Тінь'],
  font: ['Font', 'Шрифт'], align: ['Text alignment', 'Вирівнювання тексту'], fit: ['Image fit', 'Вписування зображення'], size: ['Text size', 'Розмір тексту'], fill: ['Surface color', 'Колір поверхні'], radius: ['Corner radius', 'Радіус кутів'],
  badges: ['App store badges', 'Значки магазинів'], symbol_color: ['Natal symbol', 'Символ Natal'], name_color: ['Natal name', 'Назва Natal'],
  flow: ['Move blocks with the message', 'Рухати блоки разом із текстом'], shape_color: ['Shape / annotation color', 'Колір форми / позначки'],
  surface: ['Show brand background', 'Показувати фон бренду'], padding: ['Inner spacing', 'Внутрішній відступ'],
  feature_enabled: ['Show feature card', 'Показувати картку функції'], feature_x: ['Feature horizontal position (%)', 'Позиція картки по горизонталі (%)'], feature_y: ['Feature vertical position (%)', 'Позиція картки по вертикалі (%)'],
  feature_width: ['Feature width (%)', 'Ширина картки (%)'], feature_height: ['Feature height (%)', 'Висота картки (%)'], feature_size: ['Feature title size', 'Розмір заголовка картки'], detail_size: ['Feature detail size', 'Розмір опису картки'],
  feature_fill: ['Feature surface', 'Фон картки'], feature_color: ['Feature title color', 'Колір заголовка картки'], detail_color: ['Feature detail color', 'Колір опису картки'],
  previous_price: ['Supplied previous price (optional)', 'Надана попередня ціна (необов’язково)'], second_x: ['Second prop horizontal offset (%)', 'Зсув другого об’єкта по горизонталі (%)'], second_y: ['Second prop vertical offset (%)', 'Зсув другого об’єкта по вертикалі (%)'], second_rotation: ['Second prop rotation (°)', 'Обертання другого об’єкта (°)'],
  annotation_kind: ['Annotation', 'Позначка'], annotation_x: ['Annotation horizontal position (%)', 'Позиція позначки по горизонталі (%)'], annotation_y: ['Annotation vertical position (%)', 'Позиція позначки по вертикалі (%)'], annotation_width: ['Annotation width (%)', 'Ширина позначки (%)'], annotation_height: ['Annotation height (%)', 'Висота позначки (%)'], annotation_rotation: ['Annotation rotation (°)', 'Обертання позначки (°)'],
}

function Media({ api, path, alt }: { api: ApiClient; path: string; alt: string }) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let disposed = false, objectUrl = ''
    setFailed(false)
    void api.download(path, 'image/png').then(blob => {
      objectUrl = URL.createObjectURL(blob)
      if (disposed) URL.revokeObjectURL(objectUrl)
      else setUrl(objectUrl)
    }).catch(() => { if (!disposed) setFailed(true) })
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, path])
  return url ? <img src={url} alt={alt} /> : <span>{failed ? alt : '…'}</span>
}

function AssetPanel({ api, language, basePath, slot, available, busy, generationAvailable, onAction }: {
  api: ApiClient; language: Language; basePath: string; slot: string; available: boolean; busy: boolean; generationAvailable: boolean
  onAction: (slot: string, action: string, options: Record<string, unknown>) => Promise<void>
}) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const [direction, setDirection] = useState(''), [file, setFile] = useState<File | null>(null)
  const [history, setHistory] = useState<StudioPhoneScreenHistoryItem[] | null>(null), [query, setQuery] = useState('')
  const [sources, setSources] = useState<{ stock_available: boolean; registered: { asset_id: string; description: string }[]; photos: { photo_id: string; description: string; image_url: string; source: { attribution: string } }[] } | null>(null)
  const [error, setError] = useState('')
  const act = async (action: string, options: Record<string, unknown>) => {
    setError('')
    try { await onAction(slot, action, options); setHistory(null); setFile(null) } catch (cause) { setError((cause as Error).message) }
  }
  return <div className="daddy-asset-controls">
    <p>{available ? tr('Current artwork is retained until a replacement succeeds.', 'Поточне зображення збережеться до успішної заміни.') : tr('This composition needs an image for this slot.', 'Для цієї композиції потрібне зображення.')}</p>
    <label>{tr('Image direction', 'Напрям зображення')}<textarea maxLength={600} value={direction} onChange={e => setDirection(e.target.value)} disabled={busy} /></label>
    <div className="studio-actions"><button disabled={busy || !generationAvailable || !direction.trim()} onClick={() => void act('generate', { visual_direction: direction.trim(), enhance_current: false })}>{tr('Generate', 'Згенерувати')}</button>
      <button disabled={busy || !generationAvailable || !available || !direction.trim()} onClick={() => void act('generate', { visual_direction: direction.trim(), enhance_current: true })}>{tr('Enhance current', 'Покращити поточне')}</button></div>
    <ImageReferenceInput language={language} value={file} onChange={setFile} disabled={busy} />
    <button disabled={busy || !file} onClick={() => { if (file) void imageReferencePayload(file).then(image => act('upload', { image })).catch(cause => setError(cause.message)) }}>{tr('Use uploaded image', 'Використати завантажене')}</button>
    <button disabled={busy} onClick={() => void api.get<{ items: StudioPhoneScreenHistoryItem[] }>(`${basePath}/assets/${slot}/history`).then(v => setHistory(v.items)).catch(cause => setError(cause.message))}>{tr('Image history', 'Історія зображень')}</button>
    {history && <div className="daddy-history">{history.map(item => <div key={item.sha256}><HistoryImage api={api} path={`${basePath}/assets/${slot}/history/${item.sha256}`} item={item} retryLabel={tr('Retry thumbnail', 'Повторити мініатюру')} /><button disabled={busy || item.selected} onClick={() => void act('select', { sha256: item.sha256 })}>
      <small>{item.selected ? tr('Current', 'Поточне') : tr('Use this image', 'Використати')}</small><small>{String(item.source?.attribution || item.source?.origin || item.source?.provider || '')}</small>
    </button></div>)}</div>}
    <details><summary>{tr('Registered assets and stock photos', 'Зареєстровані зображення та фотосток')}</summary>
      <label>{tr('Search photos', 'Пошук фото')}<input value={query} maxLength={160} onChange={e => setQuery(e.target.value)} /></label>
      <button disabled={busy} onClick={() => void api.get<NonNullable<typeof sources>>(`${basePath}/asset-sources?query=${encodeURIComponent(query)}`).then(setSources).catch(cause => setError(cause.message))}>{tr('Find assets', 'Знайти зображення')}</button>
      {sources && <><select aria-label={tr('Registered image', 'Зареєстроване зображення')} value="" disabled={busy} onChange={e => { if (e.target.value) void act('registered', { asset_id: e.target.value }) }}><option value="">{tr('Choose a registered image', 'Оберіть зображення')}</option>{sources.registered.map(item => <option key={item.asset_id} value={item.asset_id}>{item.description}</option>)}</select>
        {!sources.stock_available && <p>{tr('Stock search is unavailable in this environment.', 'Пошук фотостоку недоступний у цьому середовищі.')}</p>}
        <div className="daddy-history">{sources.photos.map(photo => <button key={photo.photo_id} disabled={busy || slot === 'screen'} onClick={() => void act('stock', { photo_id: photo.photo_id })}><img src={photo.image_url} alt={photo.description} loading="lazy" /><small>{photo.source.attribution}</small></button>)}</div></>}
    </details>
    {error && <p role="alert">{error}</p>}
  </div>
}

function HistoryImage({ api, path, item, retryLabel }: { api: ApiClient; path: string; item: StudioPhoneScreenHistoryItem; retryLabel: string }) {
  const [url, setUrl] = useState('')
  const [attempt, setAttempt] = useState(0), [failed, setFailed] = useState(false)
  useEffect(() => {
    let disposed = false, value = ''
    setFailed(false)
    void api.media(path, item.mime_type, item.sha256).then(blob => {
      value = URL.createObjectURL(blob); if (disposed) URL.revokeObjectURL(value); else setUrl(value)
    }).catch(() => { if (!disposed) setFailed(true) })
    return () => { disposed = true; if (value) URL.revokeObjectURL(value) }
  }, [api, path, item.mime_type, item.sha256, attempt])
  return url ? <img src={url} alt="" /> : failed ? <button onClick={() => setAttempt(v => v + 1)}>{retryLabel}</button> : <span>…</span>
}

export function DaddyStudio({ api, language, basePath, detail: initial, onDetail }: {
  api: ApiClient; language: Language; basePath: string; detail: DaddyDetail; onDetail: (detail: unknown) => void
}) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const label = (key: string) => titles[key] ? titles[key][language === 'uk' ? 1 : 0] : key.replaceAll('_', ' ')
  const [detail, setDetail] = useState(initial), [configuration, setConfiguration] = useState(initial.configuration), [content, setContent] = useState(initial.content)
  const [busy, setBusy] = useState(false), [previewBusy, setPreviewBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [previewUrl, setPreviewUrl] = useState(''), [renderedState, setRenderedState] = useState(''), [presetsOpen, setPresetsOpen] = useState(false)
  const [layoutIssues, setLayoutIssues] = useState<string[]>([])
  const [openAssets, setOpenAssets] = useState<Record<string, boolean>>({})
  const pendingKey = `ptw:daddy:asset:${basePath}`
  const [pendingAsset, setPending] = useState<PendingAsset | null>(() => {
    try { return JSON.parse(sessionStorage.getItem(pendingKey) || 'null') as PendingAsset | null } catch { return null }
  })
  const setPendingAsset = (value: PendingAsset | null) => {
    setPending(value)
    try { if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value)); else sessionStorage.removeItem(pendingKey) } catch { /* Keep the in-memory request when browser storage is full. */ }
  }
  const previewGeneration = useRef(0)
  const proposalRequest = useRef<Record<string, unknown> | null>(null)
  const polishRequest = useRef<Record<string, unknown> | null>(null)
  const draftKey = JSON.stringify([detail.state_sha256, configuration, content])
  const changed = JSON.stringify([configuration, content]) !== JSON.stringify([detail.configuration, detail.content])
  const preset = detail.catalog.presets.find(p => p.id === configuration.preset)!
  const block = (key: string) => configuration[key] as Record<string, Scalar>
  const slots = [...new Set([...preset.slots, ...(block('device').enabled ? ['screen'] : []), ...(block('subject').enabled ? ['subject'] : []), ...(block('collage').enabled ? configuration.preset === 'two_panel' ? ['prop_one'] : ['prop_one', 'prop_two'] : [])])]
    .filter(slot => block(({ scene: 'background', screen: 'device', feature: 'device', subject: 'subject', prop_one: 'collage', prop_two: 'collage' } as Record<string, string>)[slot]).enabled && (slot !== 'feature' || block('device').feature_enabled !== false))
  const apply = (next: DaddyDetail) => { setDetail(next); setConfiguration(next.configuration); setContent(next.content); onDetail(next) }
  const render = async (saved: DaddyDetail, config = configuration, copy = content) => {
    const sequence = ++previewGeneration.current
    setPreviewBusy(true)
    try {
      const blob = await api.postMedia(`${basePath}/preview`, { state_sha256: saved.state_sha256, configuration: config, content: copy }, 'image/png', { deadlineMs: 90_000 }, headers => {
        if (sequence !== previewGeneration.current) return
        try { const issues = JSON.parse(headers.get('x-ptw-layout-issues') || '[]') as { role: string; issue: string }[]; setLayoutIssues(issues.map(v => `${v.role}: ${v.issue}`)) } catch { setLayoutIssues([]) }
      })
      if (sequence === previewGeneration.current) { setPreviewUrl(URL.createObjectURL(blob)); setRenderedState(JSON.stringify([saved.state_sha256, config, copy])) }
    } catch (cause) { if (sequence === previewGeneration.current) setError((cause as Error).message) }
    finally { if (sequence === previewGeneration.current) setPreviewBusy(false) }
  }
  useEffect(() => { void render(detail, detail.configuration, detail.content); return () => { previewGeneration.current++ } }, [basePath, detail.state_sha256])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  const persist = async (config = configuration, copy = content) => {
    const next = await api.post<DaddyDetail>(`${basePath}/configuration`, { base_sha256: detail.state_sha256, configuration: config, content: copy })
    apply(next); return next
  }
  const runAssets = async (operation: PendingAsset) => {
    try {
      let current: PendingAsset | null = operation
      while (current) {
        setPendingAsset(current)
        const next: DaddyDetail = await api.post<DaddyDetail>(`${basePath}/assets/${current.slot}`, current.body, { deadlineMs: 480_000 })
        apply(next)
        const remaining: AssetOperation[] = current.remaining || []
        current = remaining.length ? { ...remaining[0], body: { ...remaining[0].body, base_sha256: next.state_sha256 }, remaining: remaining.slice(1) } : null
        setPendingAsset(current)
      }
    } catch (cause) {
      if (cause instanceof ApiFailure && [400, 404, 409, 422].includes(cause.details.status || 0)) setPendingAsset(null)
      setError((cause as Error).message); throw cause
    }
  }
  const asset = async (slot: string, action: string, options: Record<string, unknown>) => {
    setBusy(true); setError('')
    try {
      const saved = changed && !pendingAsset ? await persist() : detail
      await runAssets(pendingAsset || { slot, body: { base_sha256: saved.state_sha256, request_id: crypto.randomUUID(), action, options } })
    } finally { setBusy(false) }
  }
  const checkpoint = async (kind: 'save' | 'approve') => {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<StudioCheckpointResponse<DaddyDetail>>(`${basePath}/${kind}`, { base_sha256: detail.state_sha256, configuration, content, ...(kind === 'approve' ? { change_note: 'Owner-approved Daddy Post' } : {}) }, { deadlineMs: STUDIO_CHECKPOINT_DEADLINE_MS })
      apply(result.creative); setNotice(kind === 'save' ? tr('Post saved.', 'Допис збережено.') : tr('Post approved.', 'Допис схвалено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const propose = async () => {
    setBusy(true); setError('')
    const request = proposalRequest.current || { request_id: crypto.randomUUID(), scope: 'post',
      instruction: 'Preserve this tuned Daddy composition as a reusable template. Inspect its neutral PNG, correct only genuine layout defects, and retain the owner settings.',
      daddy_configuration: configuration }
    proposalRequest.current = request
    try {
      await api.post('/api/v1/templates/runs', request)
      proposalRequest.current = null
      setNotice(tr('Template proposal created. Review and accept it in Templates. Project copy and images were excluded.', 'Пропозицію шаблону створено. Перегляньте та прийміть її в Шаблонах. Текст і зображення проєкту вилучено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const polish = async () => {
    setBusy(true); setError('')
    const request = polishRequest.current || { request_id: crypto.randomUUID(), base_sha256: detail.state_sha256, configuration, content }
    polishRequest.current = request
    try {
      await api.post(`${basePath}/recompose`, request)
      polishRequest.current = null
      onDetail(await api.get<DaddyDetail>(basePath))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const agentApply = async (result: StudioManualAgentResult<DaddyConfiguration, Copy>, screenshots: File[]) => {
    setConfiguration(result.configuration); setContent(result.content)
    if (!result.image_actions.length) return
    setBusy(true)
    try {
      const operations: AssetOperation[] = []
      for (const action of result.image_actions) {
        const reference = action.reference_index > 0 && screenshots[action.reference_index - 1] ? await imageReferencePayload(screenshots[action.reference_index - 1]) : null
        operations.push({ slot: action.slot, body: { request_id: crypto.randomUUID(), action: 'generate', options: {
          visual_direction: action.visual_direction, enhance_current: action.enhance_current, ...(reference ? { reference_image: reference } : {}),
        } } })
      }
      const saved = await persist(result.configuration, result.content)
      await runAssets({ ...operations[0], body: { ...operations[0].body, base_sha256: saved.state_sha256 }, remaining: operations.slice(1) })
    } finally { setBusy(false) }
  }
  const setField = (group: string, key: string, value: Scalar) => setConfiguration(current => ({ ...current, [group]: { ...(current[group] as Record<string, Scalar>), [key]: value } }))
  const relevantControl = (group: string, key: string) => {
    if (group === 'device' && /^(feature_|detail_)/.test(key)) return configuration.preset === 'phone_feature'
    if (group === 'background' && key.startsWith('annotation_')) return block('background').shape === 'drawing'
    if (group === 'background' && key === 'shape_color') return block('background').shape !== 'plain'
    if (group === 'background' && ['blur', 'focal_x', 'focal_y'].includes(key)) return slots.includes('scene')
    if (group === 'collage' && key.startsWith('second_')) return configuration.preset !== 'two_panel'
    return true
  }
  const relevantCopy = (key: string) => {
    if (key.startsWith('feature_')) return configuration.preset === 'phone_feature' && block('device').enabled && block('device').feature_enabled !== false
    if (['left_label', 'right_label'].includes(key)) return configuration.preset === 'two_panel'
    if (key === 'previous_price') return block('offer').enabled && !!content.offer
    if (key === 'offer') return block('offer').enabled
    if (key === 'cta') return block('action').enabled && !block('action').badges
    return true
  }
  const locked = busy || !!pendingAsset
  const sectionProps = { expandLabel: tr('Expand', 'Розгорнути'), collapseLabel: tr('Collapse', 'Згорнути') }
  const findings = (detail.generation as unknown as { daddy?: { issues?: string[] } })?.daddy?.issues || []
  return <div className="studio-page daddy-studio">
    <header className="panel daddy-toolbar"><div><small>DADDY</small><h2>{tr('Compose a Post', 'Створіть допис')}</h2><p>{language === 'uk' ? preset.name_uk : preset.name}</p></div><div className="studio-actions">
      <PostTemplatePicker api={api} language={language} basePath={basePath} detail={detail} configuration={configuration} content={content} disabled={locked} onApply={apply} />
      <button disabled={locked || previewBusy} onClick={() => void render(detail)}><RefreshCcw />{tr('Update preview', 'Оновити прев’ю')}</button>
      <button disabled={locked} onClick={() => void checkpoint('save')}><Save />{tr('Save', 'Зберегти')}</button>
      <button className="primary" disabled={locked || previewBusy || renderedState !== draftKey || slots.some(slot => !detail.assets.some(a => a.slot === slot && a.available))} onClick={() => void checkpoint('approve')}><Check />{tr('Approve', 'Схвалити')}</button>
    </div></header>
    {error && <p className="panel" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {pendingAsset && <div className="panel"><p>{tr('The image request is awaiting confirmation. Retry uses the same request.', 'Запит зображення очікує підтвердження. Повтор використовує той самий запит.')}</p><button disabled={busy} onClick={() => void asset(pendingAsset.slot, '', {}).catch(() => {})}>{tr('Retry image request', 'Повторити запит зображення')}</button></div>}
    <div className="daddy-workspace"><aside className="daddy-preview panel">
      {previewUrl && <img src={previewUrl} alt={tr('Daddy Post preview', 'Прев’ю допису Daddy')} />}
      <p aria-live="polite">{previewBusy ? tr('Rendering…', 'Рендеринг…') : renderedState !== draftKey ? tr('Changes are ready. Update preview to inspect them.', 'Зміни готові. Оновіть прев’ю для перегляду.') : '1080 × 1350'}</p>
      {(detail.generation as unknown as { daddy?: { review_mode?: string } })?.daddy?.review_mode === 'manual' && <p>{tr('Ready for your review and manual tuning. No automatic visual polish was applied.', 'Готово до вашого перегляду й ручного налаштування. Автоматичне візуальне доопрацювання не застосовувалося.')}</p>}
      {[...findings, ...layoutIssues].length > 0 && <ul>{[...new Set([...findings, ...layoutIssues])].map((item, i) => <li key={i}>{item}</li>)}</ul>}
    </aside><div className="daddy-inspector">
      <StudioManualAgent api={api} language={language} endpoint={`${basePath}/agent`} stateSha256={detail.state_sha256} configuration={configuration} content={content} disabled={locked} onApply={agentApply} />
      <button disabled={locked} onClick={() => void polish()}>{tr('Prepare missing images', 'Підготувати відсутні зображення')}</button>
      <StudioSection {...sectionProps} eyebrow="01" title={tr('Composition', 'Композиція')} onOpenChange={setPresetsOpen}>
        <div className="daddy-presets">{detail.catalog.presets.map(p => <button key={p.id} className={p.id === configuration.preset ? 'is-selected' : ''} aria-pressed={p.id === configuration.preset} disabled={locked} onClick={() => setConfiguration({ ...structuredClone(p.configuration), logo: structuredClone(configuration.logo) })}>
          {presetsOpen && <Media api={api} path={`${basePath}/presets/${p.id}/preview`} alt="" />}<strong>{language === 'uk' ? p.name_uk : p.name}</strong>
        </button>)}</div>
        <label>{tr('Artwork style', 'Стиль зображень')}<select value={configuration.style} disabled={locked} onChange={e => setConfiguration({ ...configuration, style: e.target.value })}>{detail.catalog.styles.map(s => <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>)}</select></label>
        <p>{tr('Changing the composition preserves copy and source images. New image slots appear below.', 'Зміна композиції зберігає текст і вихідні зображення. Нові зображення вказані нижче.')}</p>
        <button disabled={locked} onClick={() => void propose()}>{tr('Propose as reusable template', 'Запропонувати як шаблон')}</button>
      </StudioSection>
      <StudioSection {...sectionProps} eyebrow="02" title={tr('Copy', 'Текст')}>
        {Object.entries(content).filter(([key]) => relevantCopy(key)).map(([key, value]) => <label key={key}>{label(key)}<textarea value={value} disabled={locked} onChange={e => setContent({ ...content, [key]: e.target.value })} /></label>)}
      </StudioSection>
      {Object.entries(configuration).filter(([, value]) => typeof value === 'object').map(([group, value]) => <StudioSection key={group} {...sectionProps} eyebrow={tr('BLOCK', 'БЛОК')} title={label(group)}>
        <button disabled={locked} onClick={() => setConfiguration({ ...configuration, [group]: structuredClone(preset.configuration[group]) })}>{tr('Reset appearance', 'Скинути оформлення')}</button>
        <div className="daddy-fields">{Object.entries(value as Record<string, Scalar>).filter(([key]) => relevantControl(group, key)).map(([key, v]) => {
          const name = label(key), options = detail.catalog.enums[key], bounds = detail.catalog.bounds[key]
          if (typeof v === 'boolean') return <label key={key} className="daddy-check"><input type="checkbox" checked={v} disabled={locked} onChange={e => setField(group, key, e.target.checked)} />{name}</label>
          if (options) return <label key={key}>{name}<select value={String(v)} disabled={locked} onChange={e => setField(group, key, e.target.value)}>{options.map(o => <option key={o} value={o}>{o.replaceAll('_', ' ')}</option>)}</select></label>
          if (typeof v === 'string' && v.startsWith('#')) return <EditableColorField key={key} label={name} value={v} disabled={locked} onChange={color => setField(group, key, color)} />
          return <label key={key}>{name}<input type="number" value={v as number} min={bounds?.[0]} max={bounds?.[1]} step={bounds?.[1] === 1 || key === 'overlay' ? .05 : 1} disabled={locked} onChange={e => { if (e.target.value !== '') setField(group, key, Number(e.target.value)) }} /></label>
        })}</div>
      </StudioSection>)}
      {slots.map(slot => <StudioSection key={slot} {...sectionProps} eyebrow={detail.assets.some(a => a.slot === slot && a.available) ? tr('IMAGE', 'ЗОБРАЖЕННЯ') : tr('IMAGE NEEDED', 'ПОТРІБНЕ ЗОБРАЖЕННЯ')} title={label(slot)} onOpenChange={open => setOpenAssets(previous => ({ ...previous, [slot]: open }))}>
        {openAssets[slot] && <AssetPanel api={api} language={language} basePath={basePath} slot={slot} available={detail.assets.some(a => a.slot === slot && a.available)} busy={locked} generationAvailable={detail.asset_generation_available} onAction={asset} />}
      </StudioSection>)}
    </div></div>
  </div>
}
