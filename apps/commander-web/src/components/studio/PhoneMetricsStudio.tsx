import { Bold, Check, Highlighter, ImagePlus, RefreshCcw, Save, Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../../api'
import { ErrorState } from '../../components/State'
import { PhoneHeroDirectionPicker, creativeDirectionFromDraft, type PhoneHeroDirectionDraft } from './PhoneHeroDirectionPicker'
import { translate, type Language } from '../../i18n'
import type {
  StudioPhoneActionButtonConfiguration, StudioPhoneMetricCardConfiguration,
  StudioPhoneMetricsConfiguration, StudioPhoneMetricsContent,
  StudioCheckpointResponse, StudioPhoneMetricsDetail, StudioPhoneScreenHistoryItem,
  StudioFontFamily, StudioPhoneTypographyRole,
} from '../../types'

function PhoneScreenHistoryOption({
  api, basePath, item, index, busy, label, currentLabel, onSelect,
}: {
  api: ApiClient
  basePath: string
  item: StudioPhoneScreenHistoryItem
  index: number
  busy: boolean
  label: string
  currentLabel: string
  onSelect: () => void
}) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let disposed = false
    let objectUrl = ''
    void api.media(
      `${basePath}/phone-screen/history/${item.sha256}`,
      item.mime_type, item.sha256,
    ).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (disposed) URL.revokeObjectURL(objectUrl)
      else setUrl(objectUrl)
    }).catch(() => {
      if (!disposed) setUrl('')
    })
    return () => {
      disposed = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [api, basePath, item.mime_type, item.sha256])

  return <button
    className={`phone-screen-history-option ${item.selected ? 'is-selected' : ''}`}
    type="button" role="radio" aria-checked={item.selected} aria-label={label}
    disabled={busy} onClick={onSelect}
  >
    <span className="phone-screen-history-image">{url
      ? <img src={url} alt="" />
      : <ImagePlus aria-hidden="true" />}</span>
    <small>{item.selected ? currentLabel : `0${index + 1}`}</small>
  </button>
}

export function PhoneMetricsStudio({ api, language, basePath, detail: initialDetail, onDetail, onCheckpoint = () => {} }: {
  api: ApiClient
  language: Language
  basePath: string
  detail: StudioPhoneMetricsDetail
  onDetail: (detail: StudioPhoneMetricsDetail | unknown) => void
  onCheckpoint?: (result: StudioCheckpointResponse<StudioPhoneMetricsDetail>) => void
}) {
  const [detail, setDetail] = useState(initialDetail)
  const [configuration, setConfiguration] = useState<StudioPhoneMetricsConfiguration>(structuredClone(initialDetail.configuration))
  const [content, setContent] = useState<StudioPhoneMetricsContent>(structuredClone(initialDetail.content))
  const [previewUrl, setPreviewUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const initialScreenAsset = initialDetail.assets.find((asset) => asset.slot === 'phone_screen')
  const [screenDirection, setScreenDirection] = useState(() => {
    const source = initialScreenAsset?.source
    return typeof source?.visual_direction === 'string' ? source.visual_direction : ''
  })
  const [enhanceCurrent, setEnhanceCurrent] = useState(Boolean(initialScreenAsset?.available))
  const [legacyDirection, setLegacyDirection] = useState<PhoneHeroDirectionDraft>({ style: '', background: '' })
  const [editingCreativeDirection, setEditingCreativeDirection] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const previewGeneration = useRef(0)
  const supportingTextRef = useRef<HTMLTextAreaElement>(null)
  const hasCurrentPhoneScreen = detail.assets.some((asset) => (
    asset.slot === 'phone_screen' && asset.available && Boolean(asset.sha256)
  ))
  const savedCreativeDirection = detail.generation?.creative_direction
  const hasCreativeDirection = Boolean(savedCreativeDirection)
  const canGenerateWithDirection = hasCreativeDirection && !editingCreativeDirection
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const textureLabel = (texture: string) => ({
    none: tr('Off', 'Без текстури'),
    grain: tr('Fine grain', 'Дрібне зерно'),
    concrete: tr('Concrete', 'Бетон'),
    travertine: tr('Travertine', 'Травертин'),
    paper: tr('Soft paper', 'М’який папір'),
    frosted: tr('Frosted glass', 'Матове скло'),
  }[texture] || texture)
  const fontLabels: Record<StudioFontFamily, string> = {
    Inter: tr('Inter — neutral & clear', 'Inter — нейтральний і чіткий'),
    'Roboto Condensed': tr('Roboto Condensed — compact & direct', 'Roboto Condensed — компактний і прямий'),
    Manrope: tr('Manrope — friendly & modern', 'Manrope — дружній і сучасний'),
    Montserrat: tr('Montserrat — geometric & bold', 'Montserrat — геометричний і сміливий'),
    'Source Sans 3': tr('Source Sans 3 — clean & readable', 'Source Sans 3 — чистий і читабельний'),
    Oswald: tr('Oswald — bold & urgent', 'Oswald — сміливий і динамічний'),
    'Cormorant Garamond': tr('Cormorant Garamond — editorial & premium', 'Cormorant Garamond — редакційний і преміальний'),
    'Cormorant Garamond Italic': tr('Cormorant Garamond Italic — expressive editorial', 'Cormorant Garamond Italic — виразний редакційний'),
    Lora: tr('Lora — warm editorial', 'Lora — теплий редакційний'),
    'Lora Italic': tr('Lora Italic — elegant & human', 'Lora Italic — елегантний і людяний'),
  }
  const typographyRoles: Array<{
    role: StudioPhoneTypographyRole; en: string; uk: string
  }> = [
    { role: 'offer', en: 'Eyebrow', uk: 'Надзаголовок' },
    { role: 'hero_title', en: 'Headline', uk: 'Заголовок' },
    { role: 'supporting_text', en: 'Supporting text', uk: 'Пояснювальний текст' },
    { role: 'cta', en: 'CTA', uk: 'CTA' },
    { role: 'metric_value', en: 'Metric values', uk: 'Значення метрик' },
    { role: 'metric_label', en: 'Metric labels', uk: 'Підписи метрик' },
    { role: 'phone_title', en: 'In-phone title', uk: 'Заголовок у телефоні' },
    { role: 'phone_buttons', en: 'In-phone buttons', uk: 'Кнопки у телефоні' },
  ]

  useEffect(() => {
    setDetail(initialDetail)
    setConfiguration(structuredClone(initialDetail.configuration))
    setContent(structuredClone(initialDetail.content))
  }, [initialDetail.state_sha256])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const replacePreview = (blob: Blob) => setPreviewUrl((current) => {
    if (current) URL.revokeObjectURL(current)
    return URL.createObjectURL(blob)
  })
  const render = async (
    saved: StudioPhoneMetricsDetail, draft = false,
    nextConfiguration = configuration, nextContent = content,
  ) => {
    const generation = ++previewGeneration.current
    setPreviewBusy(true)
    try {
      const blob = await api.postMedia(`${basePath}/preview`, draft ? {
        state_sha256: saved.state_sha256, configuration: nextConfiguration, content: nextContent,
      } : { state_sha256: saved.state_sha256 }, 'image/png', { deadlineMs: 90_000 })
      if (generation === previewGeneration.current) replacePreview(blob)
    } catch (cause) {
      if (generation === previewGeneration.current) setError((cause as Error).message)
    } finally {
      if (generation === previewGeneration.current) setPreviewBusy(false)
    }
  }
  useEffect(() => { void render(detail) }, [detail.state_sha256])
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (
        JSON.stringify(configuration) !== JSON.stringify(detail.configuration)
        || JSON.stringify(content) !== JSON.stringify(detail.content)
      ) void render(detail, true, configuration, content)
    }, 220)
    return () => window.clearTimeout(timer)
  }, [configuration, content, detail.state_sha256])

  const applyDetail = (next: StudioPhoneMetricsDetail) => {
    setDetail(next)
    setConfiguration(structuredClone(next.configuration))
    setContent(structuredClone(next.content))
    onDetail(next)
  }
  const save = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<StudioCheckpointResponse<StudioPhoneMetricsDetail>>(`${basePath}/save`, {
        base_sha256: detail.state_sha256, configuration, content,
      }, { deadlineMs: 60_000 })
      const next = result.creative
      applyDetail(next); await render(next)
      onCheckpoint(result)
      setNotice(!result.checkpoint_created
        ? tr('Creative is already saved; no new learning was created.', 'Креатив уже збережено; нового навчання не створено.')
        : result.checkpoint?.status === 'queued'
          ? tr('Creative saved. Learning is queued for retry.', 'Креатив збережено. Навчання поставлено в чергу на повтор.')
          : tr('Creative saved and Project learning updated.', 'Креатив збережено, навчання проєкту оновлено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const generatePhoneScreen = async () => {
    if (!canGenerateWithDirection) return
    setBusy(true); setError(''); setNotice('')
    try {
      const useCurrentAsReference = enhanceCurrent && hasCurrentPhoneScreen
      let saved = detail
      if (
        JSON.stringify(configuration) !== JSON.stringify(detail.configuration)
        || JSON.stringify(content) !== JSON.stringify(detail.content)
      ) {
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/configuration`, {
          base_sha256: detail.state_sha256, configuration, content,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      const next = await api.post<StudioPhoneMetricsDetail>(`${basePath}/phone-screen/generate`, {
        base_sha256: saved.state_sha256, visual_direction: screenDirection.trim(),
        enhance_current: useCurrentAsReference,
      }, { deadlineMs: 360_000 })
      applyDetail(next); setEnhanceCurrent(true); await render(next)
      setNotice(useCurrentAsReference
        ? tr('Current iPhone hero visual enhanced and applied.', 'Поточний герой-візуал iPhone покращено й застосовано.')
        : tr('New iPhone hero visual generated and applied.', 'Новий герой-візуал для iPhone згенеровано й застосовано.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const saveCreativeDirection = async () => {
    const direction = creativeDirectionFromDraft(legacyDirection)
    if (!direction) return
    setBusy(true); setError(''); setNotice('')
    try {
      const next = await api.post<StudioPhoneMetricsDetail>(`${basePath}/creative-direction`, {
        base_sha256: detail.state_sha256, creative_direction: direction,
      }, { deadlineMs: 60_000 })
      applyDetail(next)
      setEditingCreativeDirection(false)
      setNotice(tr('Image direction saved for this creative.', 'Напрям зображення збережено для цього креативу.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const selectPhoneScreen = async (sha256: string) => {
    if (detail.phone_screen_history.some((item) => item.sha256 === sha256 && item.selected)) return
    setBusy(true); setError(''); setNotice('')
    try {
      let saved = detail
      if (
        JSON.stringify(configuration) !== JSON.stringify(detail.configuration)
        || JSON.stringify(content) !== JSON.stringify(detail.content)
      ) {
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/configuration`, {
          base_sha256: detail.state_sha256, configuration, content,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      const next = await api.post<StudioPhoneMetricsDetail>(`${basePath}/phone-screen/select`, {
        base_sha256: saved.state_sha256, sha256,
      }, { deadlineMs: 60_000 })
      applyDetail(next); setEnhanceCurrent(true); await render(next)
      const selected = next.phone_screen_history.find((item) => item.selected)
      const selectedDirection = selected?.source.visual_direction
      if (typeof selectedDirection === 'string') setScreenDirection(selectedDirection)
      setNotice(tr('Selected iPhone image applied.', 'Вибране зображення iPhone застосовано.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const selectTemplate = async (templateId: string) => {
    if (templateId === detail.template_id) return
    setBusy(true); setError(''); setNotice('')
    try {
      const next = await api.post<StudioPhoneMetricsDetail>(`${basePath}/templates/apply`, {
        base_sha256: detail.state_sha256, template_id: templateId,
      }, { deadlineMs: 60_000 })
      onDetail(next)
      setNotice(tr('Template replaced the complete editable draft.', 'Шаблон повністю замінив редаговану чернетку.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.post<StudioCheckpointResponse<StudioPhoneMetricsDetail>>(`${basePath}/approve`, {
        base_sha256: detail.state_sha256, configuration, content,
        change_note: 'Phone & metrics creative',
      }, { deadlineMs: 90_000 })
      const next = result.creative
      onCheckpoint(result)
      applyDetail(next); setNotice(result.checkpoint?.status === 'queued'
        ? tr(
          'Immutable phone creative saved. Learning is queued for retry.',
          'Незмінний креатив з телефоном збережено. Навчання поставлено в чергу на повтор.',
        )
        : tr('Immutable phone creative saved.', 'Незмінний креатив з телефоном збережено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const setStat = (index: number, key: 'value' | 'label', value: string) => setContent((current) => ({
    ...current, stats: current.stats.map((stat, statIndex) => statIndex === index ? { ...stat, [key]: value } : stat),
  }))
  const setMetricCard = <Key extends keyof StudioPhoneMetricCardConfiguration>(
    index: number, key: Key, value: StudioPhoneMetricCardConfiguration[Key],
  ) => setConfiguration((current) => ({
    ...current,
    metric_cards: current.metric_cards.map((card, cardIndex) => (
      cardIndex === index ? { ...card, [key]: value } : card
    )),
  }))
  const setPhoneButtonText = (index: number, value: string) => setContent((current) => ({
    ...current,
    phone_buttons: current.phone_buttons.map((text, buttonIndex) => (
      buttonIndex === index ? value : text
    )),
  }))
  const setPhoneButton = <Key extends keyof StudioPhoneActionButtonConfiguration>(
    index: number, key: Key, value: StudioPhoneActionButtonConfiguration[Key],
  ) => setConfiguration((current) => ({
    ...current,
    phone_buttons: current.phone_buttons.map((button, buttonIndex) => (
      buttonIndex === index ? { ...button, [key]: value } : button
    )),
  }))
  const setTypography = <Key extends 'font_family' | 'font_size'>(
    role: StudioPhoneTypographyRole, key: Key,
    value: StudioPhoneMetricsConfiguration['typography'][StudioPhoneTypographyRole][Key],
  ) => setConfiguration((current) => ({
    ...current,
    typography: {
      ...current.typography,
      [role]: { ...current.typography[role], [key]: value },
    },
  }))
  const markSupportingSelection = (marker: '**' | '==') => {
    const field = supportingTextRef.current
    if (!field) return
    const start = field.selectionStart
    const end = field.selectionEnd
    if (field.value.length + marker.length * 2 > 220) return
    setContent((current) => ({
      ...current,
      supporting_text: `${current.supporting_text.slice(0, start)}${marker}${current.supporting_text.slice(start, end)}${marker}${current.supporting_text.slice(end)}`,
    }))
    window.requestAnimationFrame(() => {
      field.focus()
      field.setSelectionRange(start + marker.length, end + marker.length)
    })
  }

  return <div className="studio-page phone-metrics-studio-page">
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
    <section className="panel studio-template-selector" aria-label={tr('Post template selector', 'Вибір шаблону допису')}>
      <small>{tr('TEMPLATE', 'ШАБЛОН')}</small><h2>{tr('Start from a fixed composition', 'Почніть із фіксованої композиції')}</h2>
      <p>{tr('Changing template replaces all editable copy and assets. Saved immutable versions are preserved.', 'Зміна шаблону замінює весь редагований текст і ресурси. Збережені незмінні версії не змінюються.')}</p>
      <div className="studio-template-grid">{detail.templates.map((template) => <button key={template.template_id} type="button" className={`studio-template-card ${template.template_id === detail.template_id ? 'is-active' : ''}`} disabled={busy} onClick={() => void selectTemplate(template.template_id)}>
        <strong>{template.name}</strong><small>{template.canvas.width}×{template.canvas.height}</small><span>{template.description}</span>
      </button>)}</div>
    </section>
    <section className="studio-commandbar phone-metrics-commandbar">
      <div><small>{tr('FIXED NATAL TEMPLATE', 'ФІКСОВАНИЙ ШАБЛОН NATAL')}</small><strong>phone_metrics · v{detail.catalog.template_version}</strong></div>
      <button className="secondary" disabled={busy} onClick={() => void approve()}><Check />{tr('Approve creative', 'Схвалити креатив')}</button>
      <button className="primary" disabled={busy} onClick={() => void save()}><Save />{tr('Save creative', 'Зберегти креатив')}</button>
    </section>
    <section className="phone-metrics-workspace">
      <main className="studio-canvas-panel phone-metrics-canvas-panel">
        <header><div><small>{tr('LIVE 4:5 RENDER', 'ЖИВИЙ РЕНДЕР 4:5')}</small><h2>{tr('Natal phone & metrics', 'Natal: телефон і метрики')}</h2></div>{(busy || previewBusy) && <RefreshCcw className="spin" />}</header>
        <figure aria-busy={previewBusy}>{previewUrl ? <img src={previewUrl} alt={tr('Natal phone and metrics creative', 'Креатив Natal із телефоном і метриками')} /> : <div className="studio-preview-empty"><ImagePlus /><span>{tr('Render unavailable', 'Рендер недоступний')}</span></div>}</figure>
      </main>
      <aside className="universal-controls phone-metrics-controls">
        <section className="panel universal-section"><small>{tr('OWNER COPY', 'ТЕКСТ ВЛАСНИКА')}</small><h2>{tr('Visible content', 'Видимий вміст')}</h2>
          <label className="universal-toggle"><input
            aria-label={tr('Show eyebrow', 'Показувати надзаголовок')}
            type="checkbox" checked={configuration.offer.enabled}
            onChange={(event) => setConfiguration({
              ...configuration, offer: { enabled: event.target.checked },
            })}
          /><span>{configuration.offer.enabled
            ? tr('Eyebrow visible', 'Надзаголовок видимий')
            : tr('Eyebrow removed', 'Надзаголовок прибрано')}
          </span></label>
          {configuration.offer.enabled && <label><span>{tr('Eyebrow', 'Надзаголовок')}</span><input value={content.offer} maxLength={32} onChange={(event) => setContent({ ...content, offer: event.target.value })} /></label>}
          <label><span>{tr('Headline', 'Заголовок')}</span><textarea rows={4} value={content.hero_title} maxLength={140} onChange={(event) => setContent({ ...content, hero_title: event.target.value })} /></label>
          <div className="phone-rich-copy">
            <label><span>{tr('Supporting text', 'Пояснювальний текст')}</span><textarea ref={supportingTextRef} rows={4} value={content.supporting_text} maxLength={220} onChange={(event) => setContent({ ...content, supporting_text: event.target.value })} /></label>
            <div className="phone-markup-toolbar" role="toolbar" aria-label={tr('Supporting text formatting', 'Форматування пояснювального тексту')}>
              <button type="button" className="secondary" onClick={() => markSupportingSelection('**')} aria-label={tr('Bold selected words', 'Виділити вибрані слова жирним')}><Bold /></button>
              <button type="button" className="secondary" onClick={() => markSupportingSelection('==')} aria-label={tr('Highlight selected words', 'Підсвітити вибрані слова кольором')}><Highlighter /></button>
              <small>{tr('Select words, then use bold or colour.', 'Виберіть слова, потім застосуйте жирний шрифт або колір.')}</small>
            </div>
            <div className="phone-rich-settings">
              <label className="universal-color-field"><span>{tr('Word colour', 'Колір слів')}<code>{configuration.supporting_text.highlight_color}</code></span><input aria-label={tr('Highlight color', 'Колір підсвічування')} type="color" value={configuration.supporting_text.highlight_color} onChange={(event) => setConfiguration({ ...configuration, supporting_text: { ...configuration.supporting_text, highlight_color: event.target.value.toUpperCase() } })} /></label>
            </div>
          </div>
          <label><span>CTA</span><input value={content.cta} maxLength={60} onChange={(event) => setContent({ ...content, cta: event.target.value })} /></label>
          <label><span>{tr('Optional in-phone title', 'Необов’язковий заголовок у телефоні')}</span><input value={content.phone_hero_title} maxLength={72} onChange={(event) => setContent({ ...content, phone_hero_title: event.target.value })} /></label>
        </section>
        <section className="panel universal-section"><small>{tr('TYPOGRAPHY', 'ТИПОГРАФІКА')}</small><h2>{tr('Font and size for every text role', 'Шрифт і розмір для кожної ролі')}</h2>
          <div className="phone-typography-list">
            {typographyRoles.map(({ role, en, uk }) => {
              const appearance = configuration.typography[role]
              const bounds = detail.catalog.variation.typography[role]
              const label = tr(en, uk)
              return <div className="phone-metrics-stat-input phone-typography-role" key={role}>
                <strong>{label}</strong>
                <div className="phone-metric-fields"><div className="universal-field-grid">
                  <label><span>{tr('Font family', 'Сімейство шрифту')}</span><select
                    aria-label={`${label} ${tr('font family', 'сімейство шрифту')}`}
                    value={appearance.font_family}
                    onChange={(event) => setTypography(role, 'font_family', event.target.value as StudioFontFamily)}
                  >{detail.catalog.variation.font_families.map((font) => <option key={font} value={font}>{fontLabels[font]}</option>)}</select></label>
                  <label className="universal-range-field"><span>{tr('Font size', 'Розмір шрифту')}<code>{appearance.font_size}px</code></span><input
                    aria-label={`${label} ${tr('font size', 'розмір шрифту')}`}
                    type="range" min={bounds.minimum} max={bounds.maximum} step="1"
                    value={appearance.font_size}
                    onChange={(event) => setTypography(role, 'font_size', Number(event.target.value))}
                  /></label>
                </div></div>
              </div>
            })}
          </div>
          <p className="universal-section-note">{tr('Typography changes only editable creative copy. Natal identity and iPhone system chrome remain fixed.', 'Типографіка змінює лише редагований текст креативу. Айдентика Natal і системні елементи iPhone залишаються фіксованими.')}</p>
        </section>
        <section className="panel universal-section"><small>{tr('OPTIONAL TEXTURES', 'НЕОБОВ’ЯЗКОВІ ТЕКСТУРИ')}</small><h2>{tr('Material finish', 'Фактура поверхні')}</h2>
          <label><span>{tr('Full post background', 'Повний фон допису')}</span><select aria-label={tr('Full post background texture', 'Текстура повного фону допису')} value={configuration.background.texture} onChange={(event) => setConfiguration({ ...configuration, background: { ...configuration.background, texture: event.target.value as StudioPhoneMetricsConfiguration['background']['texture'] } })}>
            {detail.catalog.variation.background_textures.map((texture) => <option key={texture} value={texture}>{textureLabel(texture)}</option>)}
          </select></label>
          <label><span>{tr('Left copy area', 'Ліва текстова зона')}</span><select aria-label={tr('Left copy area texture', 'Текстура лівої текстової зони')} value={configuration.copy_background.texture} onChange={(event) => setConfiguration({ ...configuration, copy_background: { texture: event.target.value as StudioPhoneMetricsConfiguration['copy_background']['texture'] } })}>
            {detail.catalog.variation.copy_background_textures.map((texture) => <option key={texture} value={texture}>{textureLabel(texture)}</option>)}
          </select></label>
          <label><span>{tr('Inside iPhone screen', 'Усередині екрана iPhone')}</span><select aria-label={tr('iPhone screen texture', 'Текстура екрана iPhone')} value={configuration.phone_screen.texture} onChange={(event) => setConfiguration({ ...configuration, phone_screen: { texture: event.target.value as StudioPhoneMetricsConfiguration['phone_screen']['texture'] } })}>
            {detail.catalog.variation.phone_screen_textures.map((texture) => <option key={texture} value={texture}>{textureLabel(texture)}</option>)}
          </select></label>
          <p className="universal-section-note">{tr('Each menu has Off plus three deterministic finishes. The left-area finish is bounded behind Natal and the copy only; every texture stays beneath text and interface details.', 'Кожне меню має вимкнений стан і три детерміновані фактури. Фактура лівої зони обмежена лише тлом під Natal і текстом; усі текстури залишаються під текстом та елементами інтерфейсу.')}</p>
        </section>
        <section className="panel universal-section"><small>{tr('IN-PHONE ACTIONS', 'ДІЇ В ТЕЛЕФОНІ')}</small><h2>{tr('Three bottom buttons', 'Три нижні кнопки')}</h2>
          {content.phone_buttons.map((text, index) => {
            const button = configuration.phone_buttons[index]
            return <div className="phone-metrics-stat-input phone-action-button-input" key={index}>
              <strong>{index + 1}</strong>
              <div className="phone-metric-fields">
                <div className="universal-field-grid">
                  <label><span>{tr('Text', 'Текст')}</span><input aria-label={tr(`Phone button ${index + 1} text`, `Текст кнопки в телефоні ${index + 1}`)} value={text} maxLength={48} onChange={(event) => setPhoneButtonText(index, event.target.value)} /></label>
                  <label><span>{tr('Style', 'Стиль')}</span><select aria-label={tr(`Phone button ${index + 1} style`, `Стиль кнопки в телефоні ${index + 1}`)} value={button.style} onChange={(event) => setPhoneButton(index, 'style', event.target.value as StudioPhoneActionButtonConfiguration['style'])}>
                    {detail.catalog.variation.phone_button_styles.map((style) => <option key={style} value={style}>{({
                      filled: tr('Filled', 'Заливка'), elevated: tr('Elevated', 'З тінню'),
                      outlined: tr('Outlined', 'Контур'), text: tr('Text only', 'Лише текст'),
                    })[style]}</option>)}
                  </select></label>
                  <label><span>{tr('Shape', 'Форма')}</span><select aria-label={tr(`Phone button ${index + 1} shape`, `Форма кнопки в телефоні ${index + 1}`)} value={button.shape} onChange={(event) => setPhoneButton(index, 'shape', event.target.value as StudioPhoneActionButtonConfiguration['shape'])}>
                    {detail.catalog.variation.phone_button_shapes.map((shape) => <option key={shape} value={shape}>{({
                      square: tr('Square', 'Прямокутна'), rounded: tr('Rounded', 'Заокруглена'), pill: tr('Pill', 'Капсула'),
                    })[shape]}</option>)}
                  </select></label>
                  <label className="universal-color-field"><span>{tr('Text colour', 'Колір тексту')}<code>{button.text_color}</code></span><input aria-label={tr(`Phone button ${index + 1} text color`, `Колір тексту кнопки в телефоні ${index + 1}`)} type="color" value={button.text_color} onChange={(event) => setPhoneButton(index, 'text_color', event.target.value.toUpperCase())} /></label>
                  <label className="universal-color-field"><span>{tr('Background / border', 'Фон / контур')}<code>{button.background_color}</code></span><input aria-label={tr(`Phone button ${index + 1} background color`, `Колір фону кнопки в телефоні ${index + 1}`)} type="color" value={button.background_color} onChange={(event) => setPhoneButton(index, 'background_color', event.target.value.toUpperCase())} /></label>
                </div>
              </div>
            </div>
          })}
          <p className="universal-section-note">{tr('Each action is independent and stays inside the iPhone. The screenshot defaults are blue filled, elevated white, and blue text-only.', 'Кожна дія налаштовується окремо й залишається всередині iPhone. Типові стилі зі скриншота: синя заливка, біла кнопка з тінню та лише синій текст.')}</p>
        </section>
        <section className="panel universal-section"><small>{tr('THREE METRIC CARDS', 'ТРИ КАРТКИ-МЕТРИКИ')}</small><h2>{tr('Text and appearance', 'Текст і вигляд')}</h2>
          {content.stats.map((stat, index) => {
            const card = configuration.metric_cards[index]
            return <div className="phone-metrics-stat-input" key={index}>
              <strong>{index + 1}</strong>
              <div className="phone-metric-fields">
                <div className="universal-field-grid">
                  <label><span>{tr('Value', 'Значення')}</span><input aria-label={tr(`Metric ${index + 1} value`, `Значення метрики ${index + 1}`)} value={stat.value} maxLength={24} onChange={(event) => setStat(index, 'value', event.target.value)} /></label>
                  <label><span>{tr('Label', 'Підпис')}</span><input aria-label={tr(`Metric ${index + 1} label`, `Підпис метрики ${index + 1}`)} value={stat.label} maxLength={38} onChange={(event) => setStat(index, 'label', event.target.value)} /></label>
                  <label><span>{tr('Style', 'Стиль')}</span><select aria-label={tr(`Metric ${index + 1} style`, `Стиль метрики ${index + 1}`)} value={card.style} onChange={(event) => setMetricCard(index, 'style', event.target.value as StudioPhoneMetricCardConfiguration['style'])}>
                    {detail.catalog.variation.metric_card_styles.map((style) => <option key={style} value={style}>{style === 'filled' ? tr('Filled', 'Заливка') : tr('Outlined', 'Контур')}</option>)}
                  </select></label>
                  <label><span>{tr('Shape', 'Форма')}</span><select aria-label={tr(`Metric ${index + 1} shape`, `Форма метрики ${index + 1}`)} value={card.shape} onChange={(event) => setMetricCard(index, 'shape', event.target.value as StudioPhoneMetricCardConfiguration['shape'])}>
                    {detail.catalog.variation.metric_card_shapes.map((shape) => <option key={shape} value={shape}>{({
                      square: tr('Square', 'Прямокутна'), rounded: tr('Rounded', 'Заокруглена'), pill: tr('Pill', 'Капсула'),
                    })[shape]}</option>)}
                  </select></label>
                  <label className="universal-color-field"><span>{tr('Text colour', 'Колір тексту')}<code>{card.text_color}</code></span><input aria-label={tr(`Metric ${index + 1} text color`, `Колір тексту метрики ${index + 1}`)} type="color" value={card.text_color} onChange={(event) => setMetricCard(index, 'text_color', event.target.value.toUpperCase())} /></label>
                  <label className="universal-color-field"><span>{tr('Background', 'Фон')}<code>{card.background_color}</code></span><input aria-label={tr(`Metric ${index + 1} background color`, `Колір фону метрики ${index + 1}`)} type="color" value={card.background_color} onChange={(event) => setMetricCard(index, 'background_color', event.target.value.toUpperCase())} /></label>
                </div>
              </div>
            </div>
          })}
          <p className="universal-section-note">{tr('Each button is independent. The default is the reference cobalt fill, white text, and rounded shape.', 'Кожна кнопка налаштовується окремо. Типово використано еталонну синю заливку, білий текст і заокруглену форму.')}</p>
        </section>
        <section className="panel universal-section phone-screen-rule"><small>{tr('IPHONE HERO VISUAL', 'ГЕРОЙ-ВІЗУАЛ IPHONE')}</small><h2>{tr('Generate or enhance hero artwork', 'Згенерувати або покращити герой-візуал')}</h2>
          {savedCreativeDirection && !editingCreativeDirection
            ? <PhoneHeroDirectionPicker
              language={language} value={savedCreativeDirection} locked disabled={busy}
              onReset={() => {
                setLegacyDirection({ style: '', background: '' })
                setEditingCreativeDirection(true)
                setError(''); setNotice('')
              }} idPrefix="phone-saved-direction"
            />
            : <><PhoneHeroDirectionPicker language={language} value={legacyDirection} onChange={setLegacyDirection} disabled={busy} idPrefix="phone-legacy-direction" /><div className="phone-hero-direction-actions"><button className="secondary phone-hero-direction-save" type="button" disabled={busy || !creativeDirectionFromDraft(legacyDirection)} onClick={() => void saveCreativeDirection()}><Check />{savedCreativeDirection
              ? tr('Save new direction', 'Зберегти новий напрям')
              : tr('Save direction & enable generation', 'Зберегти напрям і ввімкнути генерацію')}</button>{savedCreativeDirection && <button className="ghost" type="button" disabled={busy} onClick={() => {
                setEditingCreativeDirection(false)
                setLegacyDirection({ style: '', background: '' })
              }}><X />{tr('Cancel', 'Скасувати')}</button>}</div><p className="phone-hero-direction-note">{savedCreativeDirection
              ? tr('Choose and save a replacement direction. Existing images and history stay unchanged until you generate again.', 'Оберіть і збережіть новий напрям. Наявні зображення та історія не зміняться, доки ви не запустите нову генерацію.')
              : tr('Choose and save one style plus one background treatment before generating a new image for this existing creative.', 'Виберіть і збережіть один стиль та один варіант фону перед генерацією нового зображення для цього наявного креативу.')}</p></>}
          <label><span>{tr('What should be shown', 'Що має бути зображено')}</span><textarea
            aria-label={tr('iPhone visual direction', 'Опис візуалу iPhone')}
            rows={4} maxLength={600} value={screenDirection}
            placeholder={tr('Example: translucent glass steps rising through soft blue light with one lime accent', 'Наприклад: прозорі скляні сходи в м’якому блакитному світлі з одним лаймовим акцентом')}
            onChange={(event) => setScreenDirection(event.target.value)}
          /></label>
          {detail.phone_screen_history.length > 0 && <div className="phone-screen-history">
            <div><strong>{tr('Last 3 images', 'Останні 3 зображення')}</strong><small>{tr('Choose one to apply or enhance', 'Виберіть для застосування або покращення')}</small></div>
            <div className="phone-screen-history-options" role="radiogroup" aria-label={tr('Recent iPhone images', 'Останні зображення iPhone')}>
              {detail.phone_screen_history.map((item, index) => <PhoneScreenHistoryOption
                key={item.sha256} api={api} basePath={basePath} item={item} index={index} busy={busy}
                currentLabel={tr('CURRENT', 'ПОТОЧНЕ')}
                label={item.selected
                  ? tr(`iPhone image ${index + 1}, current`, `Зображення iPhone ${index + 1}, поточне`)
                  : tr(`Select iPhone image ${index + 1}`, `Вибрати зображення iPhone ${index + 1}`)}
                onSelect={() => void selectPhoneScreen(item.sha256)}
              />)}
            </div>
          </div>}
          <label className={`universal-toggle phone-screen-enhance ${hasCurrentPhoneScreen ? '' : 'is-disabled'}`}>
            <input
              aria-label={tr('Enhance current image', 'Покращити поточне зображення')}
              type="checkbox" checked={enhanceCurrent && hasCurrentPhoneScreen}
              disabled={busy || !canGenerateWithDirection || !detail.phone_screen_generation_available || !hasCurrentPhoneScreen}
              onChange={(event) => setEnhanceCurrent(event.target.checked)}
            />
            <span><strong>{tr('Enhance current image', 'Покращити поточне зображення')}</strong><small>{hasCurrentPhoneScreen
              ? tr('Use the current raw hero as the image reference and apply your direction as an edit.', 'Використати поточний вихідний герой-візуал як референс і застосувати опис як редагування.')
              : tr('Available after the first hero image is generated.', 'Стане доступним після першої генерації герой-візуалу.')}</small></span>
          </label>
          <button className="primary phone-screen-generate" type="button"
            disabled={busy || !canGenerateWithDirection || !detail.phone_screen_generation_available || screenDirection.trim().length < 8}
            onClick={() => void generatePhoneScreen()}><Sparkles />{tr('Generate & apply', 'Згенерувати й застосувати')}</button>
          <p>{detail.phone_screen_generation_available
            ? tr('Enhance sends the current raw hero image with your direction; turning it off generates from scratch. The Natal logo, UI, title, action buttons, and device stay crisp, and the current visual is preserved if generation fails.', 'Режим покращення надсилає поточний вихідний герой-візуал разом з описом; якщо вимкнути його, зображення генерується з нуля. Логотип Natal, інтерфейс, заголовок, кнопки дій і пристрій залишаються чіткими, а в разі помилки поточний візуал зберігається.')
            : tr('Codex image generation is unavailable in this local Post editor. Sign in to Codex and restart the Post editor; the circles remain as the deterministic fallback.', 'Генерація зображень Codex недоступна в цьому локальному редакторі допису. Увійдіть у Codex і перезапустіть редактор; кола залишаються детермінованим резервним варіантом.')}
          </p>
        </section>
      </aside>
    </section>
  </div>
}
