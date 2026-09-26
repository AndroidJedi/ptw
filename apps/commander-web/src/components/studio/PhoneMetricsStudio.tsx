import { Bold, Check, Highlighter, ImagePlus, RefreshCcw, Save, Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { EditableColorField } from '../EditableColorField'
import { ImageReferenceInput, imageReferencePayload } from '../ImageReferenceInput'
import { VisualModeSelect } from '../VisualModeSelect'
import type { ApiClient } from '../../api'
import { STUDIO_CHECKPOINT_DEADLINE_MS } from '../../studio-checkpoints'
import { ErrorState } from '../../components/State'
import { StudioActionFeedback } from './StudioActionFeedback'
import { StudioManualAgent } from './StudioManualAgent'
import { PhoneHeroDirectionPicker, creativeDirectionFromDraft, type PhoneHeroDirectionDraft } from './PhoneHeroDirectionPicker'
import { StudioSection } from './StudioSection'
import { PostTemplatePicker } from './PostTemplatePicker'
import { translate, type Language } from '../../i18n'
import type {
  ImageInstructionContext, MetricProvenance,
  StudioPhoneActionButtonConfiguration, StudioPhoneMetricCardConfiguration,
  StudioPhoneMetricsConfiguration, StudioPhoneMetricsContent,
  StudioCheckpointResponse, StudioPhoneMetricsDetail, StudioPhoneScreenHistoryItem,
  StudioFontFamily, StudioManualAgentResult, StudioPhoneTypographyRole,
} from '../../types'

function imageInstruction(source?: Record<string, unknown> | null): ImageInstructionContext {
  const context = source?.image_context as { instruction?: ImageInstructionContext } | undefined
  return context?.instruction ? { origin: context.instruction.origin, owner_instruction: context.instruction.owner_instruction } : { origin: 'legacy_unknown' }
}

function PhoneScreenHistoryOption({
  api, basePath, item, index, busy, label, retryLabel, currentLabel, onSelect,
}: {
  api: ApiClient
  basePath: string
  item: StudioPhoneScreenHistoryItem
  index: number
  busy: boolean
  label: string
  retryLabel: string
  currentLabel: string
  onSelect: () => void
}) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)
  useEffect(() => {
    let disposed = false
    let objectUrl = ''
    let retryTimer: number | undefined
    let retry = 0
    setUrl('')
    setLoading(true)
    setLoadFailed(false)
    const load = () => void api.media(
        `${basePath}/phone-screen/history/${item.sha256}`,
        item.mime_type, item.sha256,
      ).then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        if (disposed) URL.revokeObjectURL(objectUrl)
        else {
          setUrl(objectUrl)
          setLoading(false)
        }
      }).catch(() => {
        if (disposed) return
        if (retry < 2) {
          retry += 1
          retryTimer = window.setTimeout(load, retry * 750)
          return
        }
        setLoading(false)
        setLoadFailed(true)
      })
    load()
    return () => {
      disposed = true
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [api, basePath, item.mime_type, item.sha256, loadAttempt])

  return <button
    className={`phone-screen-history-option ${item.selected ? 'is-selected' : ''}`}
    type="button" role="radio" aria-checked={item.selected}
    aria-label={loadFailed ? retryLabel : label}
    aria-busy={loading}
    disabled={busy} onClick={() => {
      if (loadFailed) setLoadAttempt((current) => current + 1)
      else onSelect()
    }}
  >
    <span className="phone-screen-history-image">{url
      ? <img src={url} alt="" />
      : loading ? <RefreshCcw className="spin" aria-hidden="true" /> : <ImagePlus aria-hidden="true" />}</span>
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
  const [previewState, setPreviewState] = useState('')
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const initialScreenAsset = initialDetail.assets.find((asset) => asset.slot === 'phone_screen')
  const [screenDirection, setScreenDirection] = useState(() => {
    const source = initialScreenAsset?.source
    return typeof source?.visual_direction === 'string' ? source.visual_direction : ''
  })
  const [instruction, setInstruction] = useState<ImageInstructionContext>(() => imageInstruction(initialScreenAsset?.source))
  const [metricSources, setMetricSources] = useState<MetricProvenance[] | undefined>(initialDetail.generation?.metric_provenance)
  const currentMetricSources = metricSources?.map((source, index) => {
    const stat = content.stats[index]
    return source.value === stat.value && source.label === stat.label ? source : { ...stat, origin: 'owner_supplied' as const, validation_status: 'unvalidated' as const, evidence: '' }
  })
  const metricPayload = currentMetricSources ? { metric_provenance: currentMetricSources } : {}
  const [referenceImage, setReferenceImage] = useState<File | null>(null)
  useEffect(() => { setReferenceImage(null) }, [basePath])
  const [enhanceCurrent, setEnhanceCurrent] = useState(Boolean(initialScreenAsset?.available))
  const [legacyDirection, setLegacyDirection] = useState<PhoneHeroDirectionDraft>({ style: '', background: '' })
  const [editingCreativeDirection, setEditingCreativeDirection] = useState(false)
  const [error, setError] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [notice, setNotice] = useState('')
  const previewGeneration = useRef(0)
  const heroTitleRef = useRef<HTMLTextAreaElement>(null)
  const supportingTextRef = useRef<HTMLTextAreaElement>(null)
  const hasCurrentPhoneScreen = detail.assets.some((asset) => (
    asset.slot === 'phone_screen' && asset.available && Boolean(asset.sha256)
  ))
  const savedCreativeDirection = detail.generation?.creative_direction
  const hasCreativeDirection = Boolean(savedCreativeDirection)
  const pendingCreativeDirection = !hasCreativeDirection || editingCreativeDirection
    ? creativeDirectionFromDraft(legacyDirection)
    : null
  const canGenerateWithDirection = (hasCreativeDirection && !editingCreativeDirection)
    || Boolean(pendingCreativeDirection)
  const authored = detail.editor_key === 'post.declarative.react'
  const mutationBusy = busy || generating
  const enhanceDisabled = Boolean(referenceImage) || !canGenerateWithDirection
    || !detail.phone_screen_generation_available || !hasCurrentPhoneScreen
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
  const setTemplateTypography = (fieldId: string, update: Partial<{ font_family: StudioFontFamily; font_size: number }>) => {
    const field = detail.template_fields?.find((item) => item.id === fieldId)
    if (!field) return
    setConfiguration(current => ({
      ...current,
      template_typography: {
        ...current.template_typography,
        [fieldId]: { font_family: field.font_family, font_size: field.font_size, ...current.template_typography?.[fieldId], ...update },
      },
    }))
  }

  useEffect(() => {
    setDetail(initialDetail)
    setConfiguration(structuredClone(initialDetail.configuration))
    setContent(structuredClone(initialDetail.content))
  }, [initialDetail.state_sha256])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const previewStateFor = (
    saved: StudioPhoneMetricsDetail,
    nextConfiguration: StudioPhoneMetricsConfiguration,
    nextContent: StudioPhoneMetricsContent,
  ) => JSON.stringify([saved.state_sha256, nextConfiguration, nextContent])
  const currentPreviewState = previewStateFor(detail, configuration, content)
  const replacePreview = (blob: Blob, state: string) => {
    setPreviewUrl(URL.createObjectURL(blob))
    setPreviewState(state)
  }
  const render = async (
    saved: StudioPhoneMetricsDetail, draft = false,
    nextConfiguration = configuration, nextContent = content,
  ) => {
    const generation = ++previewGeneration.current
    const requestedPreviewState = previewStateFor(
      saved,
      draft ? nextConfiguration : saved.configuration,
      draft ? nextContent : saved.content,
    )
    setPreviewBusy(true)
    setPreviewError('')
    try {
      const blob = await api.postMedia(`${basePath}/preview`, draft ? {
        state_sha256: saved.state_sha256, configuration: nextConfiguration, content: nextContent,
      } : { state_sha256: saved.state_sha256 }, 'image/png', { deadlineMs: 90_000 })
      if (generation === previewGeneration.current) {
        replacePreview(blob, requestedPreviewState)
        setPreviewError('')
      }
    } catch (cause) {
      if (generation === previewGeneration.current) setPreviewError((cause as Error).message)
    } finally {
      if (generation === previewGeneration.current) setPreviewBusy(false)
    }
  }
  useEffect(() => {
    void render(detail)
    return () => { previewGeneration.current += 1 }
  }, [detail.state_sha256, basePath])

  const applyDetail = (next: StudioPhoneMetricsDetail) => {
    setDetail(next)
    setMetricSources(next.generation?.metric_provenance)
    setConfiguration(structuredClone(next.configuration))
    setContent(structuredClone(next.content))
    onDetail(next)
  }
  const save = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.post<StudioCheckpointResponse<StudioPhoneMetricsDetail>>(`${basePath}/save`, {
        base_sha256: detail.state_sha256, configuration, content, ...metricPayload,
      }, { deadlineMs: STUDIO_CHECKPOINT_DEADLINE_MS })
      const next = result.creative
      applyDetail(next)
      onCheckpoint(result)
      const savedNotice = !result.checkpoint_created
        ? tr('Creative is already saved.', 'Креатив уже збережено.')
        : tr('Creative saved with an edit checkpoint.', 'Креатив збережено з контрольною точкою змін.')
      setNotice(result.project_logo_default_updated
        ? `${savedNotice} ${tr('These Natal colors are now the Project default.', 'Ці кольори Natal тепер є типовими для проєкту.')}`
        : savedNotice)
    } catch (cause) {
      setError(`${tr('Save was not confirmed. Your edits are still in the editor.', 'Збереження не підтверджено. Ваші зміни залишаються в редакторі.')}\n${tr('Copy your edits before reloading this page.', 'Скопіюйте зміни перед перезавантаженням сторінки.')}\n${(cause as Error).message}`)
    } finally { setBusy(false) }
  }
  const generatePhoneScreen = async () => {
    if (!canGenerateWithDirection || busy || generating) return
    const hadCurrentPhoneScreen = hasCurrentPhoneScreen
    setGenerating(true); setError(''); setNotice('')
    try {
      const useCurrentAsReference = !referenceImage && enhanceCurrent && hasCurrentPhoneScreen
      const reference = referenceImage ? await imageReferencePayload(referenceImage) : null
      const changedImageSettings = [
        ...(pendingCreativeDirection?.style && pendingCreativeDirection.style !== savedCreativeDirection?.style ? ['style'] : []),
        ...(pendingCreativeDirection?.background && pendingCreativeDirection.background !== savedCreativeDirection?.background ? ['background'] : []),
        ...(JSON.stringify(configuration.background) !== JSON.stringify(detail.configuration.background) ? ['palette'] : []),
      ]
      let saved = detail
      if (
        JSON.stringify(configuration) !== JSON.stringify(saved.configuration)
        || JSON.stringify(content) !== JSON.stringify(saved.content)
      ) {
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/configuration`, {
          base_sha256: saved.state_sha256, configuration, content, ...metricPayload,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      if (pendingCreativeDirection) {
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/creative-direction`, {
          base_sha256: saved.state_sha256, creative_direction: pendingCreativeDirection,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
        setEditingCreativeDirection(false)
        setLegacyDirection({ style: '', background: '' })
      }
      const next = await api.post<StudioPhoneMetricsDetail>(`${basePath}/phone-screen/generate`, {
        base_sha256: saved.state_sha256, visual_direction: screenDirection.trim(), instruction_context: instruction,
        ...(changedImageSettings.length ? { changed_image_settings: changedImageSettings } : {}),
        enhance_current: useCurrentAsReference,
        ...(reference ? { reference_image: reference } : {}),
      }, { deadlineMs: 360_000 })
      applyDetail(next)
      if (!hadCurrentPhoneScreen) setEnhanceCurrent(true)
      setNotice(useCurrentAsReference
        ? tr('Current iPhone hero visual enhanced and applied.', 'Поточний герой-візуал iPhone покращено й застосовано.')
        : tr('New iPhone hero visual generated and applied.', 'Новий герой-візуал для iPhone згенеровано й застосовано.'))
    } catch (cause) { setError((cause as Error).message) } finally { setReferenceImage(null); setGenerating(false) }
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
          base_sha256: detail.state_sha256, configuration, content, ...metricPayload,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      const next = await api.post<StudioPhoneMetricsDetail>(`${basePath}/phone-screen/select`, {
        base_sha256: saved.state_sha256, sha256,
      }, { deadlineMs: 60_000 })
      applyDetail(next); setEnhanceCurrent(true)
      const selected = next.phone_screen_history.find((item) => item.selected)
      setInstruction(imageInstruction(selected?.source))
      const selectedDirection = selected?.source.visual_direction
      if (typeof selectedDirection === 'string') setScreenDirection(selectedDirection)
      setNotice(tr('Selected iPhone image applied.', 'Вибране зображення iPhone застосовано.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.post<StudioCheckpointResponse<StudioPhoneMetricsDetail>>(`${basePath}/approve`, {
        base_sha256: detail.state_sha256, configuration, content, ...metricPayload,
        change_note: authored ? detail.template_name || 'Post creative' : 'Phone & metrics creative',
      }, { deadlineMs: STUDIO_CHECKPOINT_DEADLINE_MS })
      const next = result.creative
      onCheckpoint(result)
      applyDetail(next); setNotice(result.project_logo_default_updated
        ? tr('Immutable phone creative saved. These Natal colors are now the Project default.', 'Незмінний креатив із телефоном збережено. Ці кольори Natal тепер є типовими для проєкту.')
        : authored ? tr('Post approved. This version is saved in history.', 'Допис схвалено. Цю версію збережено в історії.') : tr('Immutable phone creative saved.', 'Незмінний креатив з телефоном збережено.'))
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
  const markSelection = (
    key: 'hero_title' | 'supporting_text', field: HTMLTextAreaElement | null,
    marker: '**' | '==', maximum: number,
  ) => {
    if (!field) return
    const start = field.selectionStart
    const end = field.selectionEnd
    if (field.value.length + marker.length * 2 > maximum) return
    setContent((current) => ({
      ...current,
      [key]: `${current[key].slice(0, start)}${marker}${current[key].slice(start, end)}${marker}${current[key].slice(end)}`,
    }))
    window.requestAnimationFrame(() => {
      field.focus()
      field.setSelectionRange(start + marker.length, end + marker.length)
    })
  }

  const applyAgentResult = async (
    result: StudioManualAgentResult<StudioPhoneMetricsConfiguration, StudioPhoneMetricsContent>,
    screenshots: File[],
  ) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const nextConfiguration = structuredClone(result.configuration)
      const nextContent = structuredClone(result.content)
      setConfiguration(nextConfiguration); setContent(nextContent)
      setMetricSources(result.metric_provenance)
      const nextDirection = result.creative_direction
      const directionChanged = Boolean(nextDirection) && JSON.stringify(nextDirection) !== JSON.stringify(detail.generation?.creative_direction || null)
      let saved = detail
      if (result.image_actions.length || directionChanged) {
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/configuration`, {
          base_sha256: saved.state_sha256,
          configuration: nextConfiguration, content: nextContent,
          ...(result.metric_provenance ? { metric_provenance: result.metric_provenance } : {}),
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      if (directionChanged && nextDirection) {
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/creative-direction`, {
          base_sha256: saved.state_sha256, creative_direction: nextDirection,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      const changed = [
        ...(['style', 'background'] as const).filter(key => nextDirection && nextDirection[key] !== detail.generation?.creative_direction?.[key]),
        ...(JSON.stringify(nextConfiguration.background) !== JSON.stringify(detail.configuration.background) ? ['palette'] : []),
      ]
      const action = result.image_actions[0]
      if (action) {
        const reference = action.reference_index > 0
          ? await imageReferencePayload(screenshots[action.reference_index - 1]) : null
        saved = await api.post<StudioPhoneMetricsDetail>(`${basePath}/phone-screen/generate`, {
          base_sha256: saved.state_sha256,
          visual_direction: action.visual_direction,
          ...(result.owner_instruction ? { instruction_context: { origin: 'agent', owner_instruction: result.owner_instruction } } : {}),
          ...(changed.length ? { changed_image_settings: changed } : {}),
          enhance_current: action.enhance_current,
          ...(reference ? { reference_image: reference } : {}),
        }, { deadlineMs: 360_000 })
        setScreenDirection(action.visual_direction)
        setInstruction(result.owner_instruction ? { origin: 'agent', owner_instruction: result.owner_instruction } : { origin: 'legacy_unknown' })
        setEnhanceCurrent(true)
        applyDetail(saved)
      } else {
        await render(saved, true, nextConfiguration, nextContent)
      }
      setNotice(tr(
        `Agent adjusted ${result.changed_paths.length} editor field${result.changed_paths.length === 1 ? '' : 's'}${action ? ' and applied a generated image' : ''}. Review before saving.`,
        `Агент налаштував ${result.changed_paths.length} полів редактора${action ? ' і застосував згенероване зображення' : ''}. Перевірте перед збереженням.`,
      ))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      throw cause
    } finally { setBusy(false) }
  }

  return <div className="studio-page phone-metrics-studio-page">
    <section className="studio-commandbar phone-metrics-commandbar">
      <div><small>{tr('TEMPLATE', 'ШАБЛОН')}</small><strong>{detail.template_name || 'Phone & metrics'} · v{detail.catalog.template_version}</strong></div>
      <PostTemplatePicker api={api} language={language} basePath={basePath} detail={detail} configuration={configuration} content={content} disabled={mutationBusy || previewBusy} onApply={value => { applyDetail(value); void render(value); setNotice(tr('Template applied. Review your Post before approving.', 'Шаблон застосовано. Перевірте допис перед схваленням.')) }} />
      {!authored && <StudioManualAgent compact api={api} language={language} endpoint={`${basePath}/agent`} stateSha256={detail.state_sha256} configuration={configuration} content={content} disabled={mutationBusy || previewBusy} onApply={applyAgentResult} />}
      <button className="secondary" disabled={mutationBusy} onClick={() => void approve()}><Check />{tr('Approve creative', 'Схвалити креатив')}</button>
      <button className="primary" disabled={mutationBusy} onClick={() => void save()}><Save />{tr('Save creative', 'Зберегти креатив')}</button>
    </section>
    <StudioActionFeedback error={error} notice={notice} language={language} />
    <section className={`phone-metrics-workspace ${authored ? 'authored-post-workspace' : ''}`}>
      <main className="studio-canvas-panel phone-metrics-canvas-panel">
        <header><div><small>{tr('POST PREVIEW', 'ПРЕВ’Ю ДОПИСУ')}</small><h2>{authored ? detail.template_name : tr('Natal phone & metrics', 'Natal: телефон і метрики')}</h2></div>{(busy || generating || previewBusy) && <RefreshCcw className="spin" />}</header>
        <button type="button" className="secondary" disabled={busy || generating || previewBusy} onClick={() => void render(detail, true)}><RefreshCcw />{tr('Update preview', 'Оновити прев’ю')}</button>
        {authored && <a className="secondary authored-post-edit-link" href="#post-edit-controls">{tr('Edit text and fonts', 'Редагувати текст і шрифти')}</a>}
        <div className="studio-preview-feedback" aria-live="polite">
          {previewBusy ? tr('Rendering your changes…', 'Рендеримо ваші зміни…')
            : previewState !== currentPreviewState ? tr('Changes not previewed. Press Update preview when ready.', 'Зміни ще не показано. Натисніть «Оновити прев’ю», коли завершите редагування.')
              : tr('Preview up to date', 'Прев’ю оновлено')}
        </div>
        {previewError && <ErrorState message={previewError} language={language} />}
        <figure aria-busy={previewBusy}>{previewUrl ? <img src={previewUrl} alt={authored ? tr('Post preview', 'Прев’ю допису') : tr('Natal phone and metrics creative', 'Креатив Natal із телефоном і метриками')} /> : <div className="studio-preview-empty">{previewBusy ? <RefreshCcw className="spin" /> : <ImagePlus />}<span>{previewBusy ? tr('Updating preview…', 'Оновлення прев’ю…') : tr('Render unavailable', 'Рендер недоступний')}</span></div>}</figure>
      </main>
      <aside id={authored ? 'post-edit-controls' : undefined} className="studio-controls phone-metrics-controls">
        {authored && <>
          <StudioSection eyebrow={tr('POST COPY', 'ТЕКСТ ДОПИСУ')} title={tr('Text and bullets', 'Текст і маркери')}
            expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}>
            {detail.template_fields?.map((field) => {
              const role = ({ headline: tr('Headline', 'Заголовок'), description: tr('Supporting text', 'Пояснювальний текст'), cta: tr('Button', 'Кнопка'), meta: tr('Caption', 'Підпис'), footer: tr('Footer', 'Нижній текст') } as Record<string, string>)[field.role] || tr('Text', 'Текст')
              const name = field.id.replace(/[_-]+/g, ' ')
              return <label key={field.id}><span>{name} · {role}</span><textarea rows={3} maxLength={500} disabled={mutationBusy} value={content.template_text?.[field.id] || ''} onChange={event => setContent(current => ({ ...current, template_text: { ...current.template_text, [field.id]: event.target.value.replace(/\s+/g, ' ') } }))} /></label>
            })}
            <p className="studio-section-note">{tr('This template sets the number of separate text and bullet positions. To add another, edit the design in Templates, accept its new version, then select it with Change template.', 'Цей шаблон задає кількість окремих текстових полів і маркерів. Щоб додати ще один, відредагуйте дизайн у «Шаблони», схваліть нову версію та виберіть її через «Змінити шаблон».')}</p>
          </StudioSection>
          <StudioSection eyebrow={tr('TYPOGRAPHY', 'ТИПОГРАФІКА')} title={tr('Font and size for each text field', 'Шрифт і розмір кожного поля')}
            expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}>
            {detail.template_fields?.map((field) => {
              const appearance = configuration.template_typography?.[field.id] || field
              return <div key={field.id} className="phone-metrics-stat-input authored-post-type-field"><strong>{field.id.replace(/[_-]+/g, ' ')}</strong><div className="studio-field-grid">
                <label><span>{tr('Font family', 'Сімейство шрифту')}</span><select aria-label={`${field.id} ${tr('font family', 'сімейство шрифту')}`} disabled={mutationBusy} value={appearance.font_family} onChange={event => setTemplateTypography(field.id, { font_family: event.target.value as StudioFontFamily })}>{Object.entries(fontLabels).map(([family, label]) => <option key={family} value={family}>{label}</option>)}</select></label>
                <label className="studio-range-field"><span>{tr('Font size', 'Розмір шрифту')}<code>{appearance.font_size}px</code></span><input aria-label={`${field.id} ${tr('font size', 'розмір шрифту')}`} type="range" min="12" max="180" step="1" disabled={mutationBusy} value={appearance.font_size} onChange={event => setTemplateTypography(field.id, { font_size: Number(event.target.value) })} /></label>
              </div></div>
            })}
            <button type="button" className="secondary" disabled={mutationBusy || !configuration.template_typography} onClick={() => setConfiguration(current => {
              const { template_typography: _typography, ...rest } = current
              return rest
            })}>{tr('Use template fonts', 'Шрифти шаблону')}</button>
            <p className="studio-section-note">{tr('A changed font size renders exactly. If it does not fit, reduce the size or enlarge this text area in a new template version.', 'Змінений розмір шрифту відображається точно. Якщо текст не вміщується, зменште розмір або збільште текстову область у новій версії шаблону.')}</p>
          </StudioSection>
          {detail.template_palette_defaults && <StudioSection eyebrow={tr('BACKGROUND', 'ФОН')} title={tr('Background palette', 'Кольори фону')}
            expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}><fieldset aria-label={tr('Background palette', 'Кольори фону')} disabled={mutationBusy}>
            <p>{tr('Choose tones that complement the hero image and keep the text readable.', 'Оберіть відтінки, що пасують до головного зображення та зберігають читабельність тексту.')}</p>
            {(['gradient_start', 'gradient_end'] as const).map(key => <EditableColorField key={key}
              label={{ gradient_start: tr('Gradient start', 'Початок градієнта'), gradient_end: tr('Gradient end', 'Кінець градієнта') }[key]}
              value={(configuration.template_palette || detail.template_palette_defaults!)[key]}
              onChange={color => setConfiguration(current => ({ ...current, template_palette: { ...(current.template_palette || detail.template_palette_defaults!), [key]: color } }))}
            />)}
            <button type="button" className="secondary" disabled={!configuration.template_palette} onClick={() => setConfiguration(current => {
              const { template_palette: _palette, ...rest } = current
              return rest
            })}>{tr('Use template colors', 'Кольори шаблону')}</button>
          </fieldset></StudioSection>}
        </>}
        {!authored && <><StudioSection
          eyebrow={tr('VISUAL MODE', 'ВІЗУАЛЬНИЙ РЕЖИМ')} title={tr('Phone frame or image only', 'Рамка телефона або лише зображення')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          <VisualModeSelect language={language} value={configuration.visual_mode} disabled={mutationBusy}
            onChange={visual_mode => setConfiguration(current => ({ ...current, visual_mode }))} />
          <label className="studio-toggle"><input aria-label={tr('Show device', 'Показувати телефон')} type="checkbox" checked={configuration.device.enabled !== false} onChange={(event) => setConfiguration(current => ({ ...current, device: { ...current.device, enabled: event.target.checked } }))} /><span>{configuration.device.enabled !== false ? tr('Device visible', 'Телефон видимий') : tr('Device removed', 'Телефон прибрано')}</span></label>
          <p className="studio-section-note">{tr('Image only shows the selected artwork without the phone or its interface. Phone settings are kept when you switch back.', 'Лише зображення показує обрану ілюстрацію без телефону та його інтерфейсу. Налаштування телефону збережуться для повернення.')}</p>
        </StudioSection>
        <StudioSection
          eyebrow={tr('OWNER COPY', 'ТЕКСТ ВЛАСНИКА')} title={tr('Visible content', 'Видимий вміст')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          <label className="studio-toggle"><input
            aria-label={tr('Show eyebrow', 'Показувати надзаголовок')}
            type="checkbox" checked={configuration.offer.enabled}
            onChange={(event) => setConfiguration({
              ...configuration, offer: { enabled: event.target.checked },
            })}
          /><span>{configuration.offer.enabled
            ? tr('Eyebrow visible', 'Надзаголовок видимий')
            : tr('Eyebrow removed', 'Надзаголовок прибрано')}
          </span></label>
          {configuration.offer.enabled && <label><span>{tr('Eyebrow', 'Надзаголовок')}</span><input value={content.offer} maxLength={32} onChange={(event) => setContent(current => ({ ...current, offer: event.target.value }))} /></label>}
          <label className="studio-toggle"><input aria-label={tr('Show headline', 'Показувати заголовок')} type="checkbox" checked={configuration.hero_title.enabled !== false} onChange={(event) => setConfiguration(current => ({ ...current, hero_title: { ...current.hero_title, enabled: event.target.checked } }))} /><span>{configuration.hero_title.enabled !== false ? tr('Headline visible', 'Заголовок видимий') : tr('Headline removed', 'Заголовок прибрано')}</span></label>
          {configuration.hero_title.enabled !== false && <div className="phone-rich-copy">
            <label><span>{tr('Headline', 'Заголовок')}</span><textarea ref={heroTitleRef} aria-label={tr('Headline', 'Заголовок')} rows={4} value={content.hero_title} maxLength={140} onChange={(event) => setContent(current => ({ ...current, hero_title: event.target.value }))} /></label>
            <div className="phone-markup-toolbar" role="toolbar" aria-label={tr('Headline formatting', 'Форматування заголовка')}>
              <button type="button" className="secondary" onClick={() => markSelection('hero_title', heroTitleRef.current, '**', 140)} aria-label={tr('Bold selected headline words', 'Виділити вибрані слова заголовка жирним')}><Bold /></button>
              <button type="button" className="secondary" onClick={() => markSelection('hero_title', heroTitleRef.current, '==', 140)} aria-label={tr('Colour selected headline words', 'Підсвітити вибрані слова заголовка кольором')}><Highlighter /></button>
              <small>{tr('Select words, then use bold or colour.', 'Виберіть слова, потім застосуйте жирний шрифт або колір.')}</small>
            </div>
            <div className="phone-rich-settings">
              <EditableColorField className="studio-color-field" label={tr('Headline highlight color', 'Колір виділення заголовка')} hexLabel={tr('Headline highlight color hex', 'HEX кольору виділення заголовка')} value={configuration.hero_title.highlight_color} onChange={(value) => setConfiguration({ ...configuration, hero_title: { ...configuration.hero_title, highlight_color: value } })} />
            </div>
          </div>}
          <label className="studio-toggle"><input aria-label={tr('Show supporting text', 'Показувати пояснювальний текст')} type="checkbox" checked={configuration.supporting_text.enabled !== false} onChange={(event) => setConfiguration(current => ({ ...current, supporting_text: { ...current.supporting_text, enabled: event.target.checked } }))} /><span>{configuration.supporting_text.enabled !== false ? tr('Supporting text visible', 'Пояснювальний текст видимий') : tr('Supporting text removed', 'Пояснювальний текст прибрано')}</span></label>
          {configuration.supporting_text.enabled !== false && <div className="phone-rich-copy">
            <label><span>{tr('Supporting text', 'Пояснювальний текст')}</span><textarea ref={supportingTextRef} rows={4} value={content.supporting_text} maxLength={220} onChange={(event) => setContent(current => ({ ...current, supporting_text: event.target.value }))} /></label>
            <div className="phone-markup-toolbar" role="toolbar" aria-label={tr('Supporting text formatting', 'Форматування пояснювального тексту')}>
              <button type="button" className="secondary" onClick={() => markSelection('supporting_text', supportingTextRef.current, '**', 220)} aria-label={tr('Bold selected words', 'Виділити вибрані слова жирним')}><Bold /></button>
              <button type="button" className="secondary" onClick={() => markSelection('supporting_text', supportingTextRef.current, '==', 220)} aria-label={tr('Highlight selected words', 'Підсвітити вибрані слова кольором')}><Highlighter /></button>
              <small>{tr('Select words, then use bold or colour.', 'Виберіть слова, потім застосуйте жирний шрифт або колір.')}</small>
            </div>
            <div className="phone-rich-settings">
              <EditableColorField className="studio-color-field" label={tr('Highlight color', 'Колір підсвічування')} hexLabel={tr('Highlight color hex', 'HEX кольору підсвічування')} value={configuration.supporting_text.highlight_color} onChange={(value) => setConfiguration({ ...configuration, supporting_text: { ...configuration.supporting_text, highlight_color: value } })} />
            </div>
          </div>}
          <label className="studio-toggle"><input
            aria-label={tr('Show bottom CTA', 'Показувати нижній CTA')}
            type="checkbox" checked={configuration.cta.enabled}
            onChange={(event) => setConfiguration({
              ...configuration, cta: { ...configuration.cta, enabled: event.target.checked },
            })}
          /><span>{configuration.cta.enabled
            ? tr('Bottom CTA visible', 'Нижній CTA видимий')
            : tr('Bottom CTA removed', 'Нижній CTA прибрано')}
          </span></label>
          {configuration.cta.enabled && <>
            <label><span>{tr('CTA label', 'Текст CTA')}</span><input aria-label={tr('CTA label', 'Текст CTA')} aria-describedby="phone-cta-hint" value={content.cta} maxLength={60} onChange={(event) => setContent(current => ({ ...current, cta: event.target.value }))} /></label>
            <p id="phone-cta-hint" className="studio-section-note">{tr('Leave empty to hide the CTA band.', 'Залиште порожнім, щоб приховати смугу CTA.')}</p>
            <div className="phone-rich-settings">
              <EditableColorField className="studio-color-field" label={tr('CTA background color', 'Колір фону CTA')} hexLabel={tr('CTA background color hex', 'HEX кольору фону CTA')} value={configuration.cta.background_color} onChange={(value) => setConfiguration({ ...configuration, cta: { ...configuration.cta, background_color: value } })} />
              <EditableColorField className="studio-color-field" label={tr('CTA text color', 'Колір тексту CTA')} hexLabel={tr('CTA text color hex', 'HEX кольору тексту CTA')} value={configuration.cta.text_color} onChange={(value) => setConfiguration({ ...configuration, cta: { ...configuration.cta, text_color: value } })} />
            </div>
          </>}
          <label className="studio-toggle"><input aria-label={tr('Show in-phone title', 'Показувати заголовок у телефоні')} type="checkbox" checked={configuration.phone_screen.title_enabled !== false} onChange={(event) => setConfiguration(current => ({ ...current, phone_screen: { ...current.phone_screen, title_enabled: event.target.checked } }))} /><span>{configuration.phone_screen.title_enabled !== false ? tr('In-phone title visible', 'Заголовок у телефоні видимий') : tr('In-phone title removed', 'Заголовок у телефоні прибрано')}</span></label>
          {configuration.phone_screen.title_enabled !== false && <label><span>{tr('Optional in-phone title', 'Необов’язковий заголовок у телефоні')}</span><input value={content.phone_hero_title} maxLength={72} onChange={(event) => setContent(current => ({ ...current, phone_hero_title: event.target.value }))} /></label>}
        </StudioSection>
        <StudioSection
          eyebrow={tr('BRAND VISIBILITY', 'ВИДИМІСТЬ БРЕНДУ')} title={tr('Natal logos', 'Логотипи Natal')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          <label className="studio-toggle"><input
            aria-label={tr('Show post logo', 'Показувати логотип допису')}
            type="checkbox" checked={configuration.logo.enabled}
            onChange={(event) => setConfiguration({
              ...configuration, logo: { ...configuration.logo, enabled: event.target.checked },
            })}
          /><span><strong>{tr('Upper-left post logo', 'Логотип угорі ліворуч')}</strong><small>{configuration.logo.enabled
            ? tr('Visible on the post canvas', 'Видимий на полотні допису')
            : tr('Hidden from the post canvas', 'Прихований із полотна допису')}</small></span></label>
          <label className="studio-toggle"><input
            aria-label={tr('Show in-phone logo', 'Показувати логотип у телефоні')}
            type="checkbox" checked={configuration.phone_screen.logo_enabled}
            onChange={(event) => setConfiguration({
              ...configuration,
              phone_screen: { ...configuration.phone_screen, logo_enabled: event.target.checked },
            })}
          /><span><strong>{tr('Logo inside iPhone', 'Логотип усередині iPhone')}</strong><small>{configuration.phone_screen.logo_enabled
            ? tr('Visible in the app screen', 'Видимий на екрані застосунку')
            : tr('Hidden from the app screen', 'Прихований з екрана застосунку')}</small></span></label>
          <div className="studio-field-grid">
            <EditableColorField className="studio-color-field" label={tr('Logo symbol color', 'Колір знака логотипа')} hexLabel={tr('Logo symbol color hex', 'HEX кольору знака логотипа')} value={configuration.logo.symbol_color} onChange={(value) => setConfiguration({ ...configuration, logo: { ...configuration.logo, symbol_color: value } })} />
            <EditableColorField className="studio-color-field" label={tr('Natal name color', 'Колір назви Natal')} hexLabel={tr('Natal name color hex', 'HEX кольору назви Natal')} value={configuration.logo.name_color} onChange={(value) => setConfiguration({ ...configuration, logo: { ...configuration.logo, name_color: value } })} />
          </div>
          <p className="studio-section-note">{tr('Both visible lock-ups share these colors. The full symbol, including its inner stroke, uses the symbol color. Save or Approve makes the pair the Project default; the canonical artwork cannot be replaced.', 'Обидва видимі логотипи використовують ці кольори. Увесь знак, включно з внутрішнім штрихом, має колір знака. Після «Зберегти» або «Схвалити» пара стане типовою для проєкту; канонічне зображення не можна замінити.')}</p>
        </StudioSection>
        <StudioSection
          eyebrow={tr('TYPOGRAPHY', 'ТИПОГРАФІКА')} title={tr('Font and size for every text role', 'Шрифт і розмір для кожної ролі')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          <div className="phone-typography-list">
            {typographyRoles.map(({ role, en, uk }) => {
              const appearance = configuration.typography[role]
              const bounds = detail.catalog.variation.typography[role]
              const label = tr(en, uk)
              return <div className="phone-metrics-stat-input phone-typography-role" key={role}>
                <strong>{label}</strong>
                <div className="phone-metric-fields"><div className="studio-field-grid">
                  <label><span>{tr('Font family', 'Сімейство шрифту')}</span><select
                    aria-label={`${label} ${tr('font family', 'сімейство шрифту')}`}
                    value={appearance.font_family}
                    onChange={(event) => setTypography(role, 'font_family', event.target.value as StudioFontFamily)}
                  >{detail.catalog.variation.font_families.map((font) => <option key={font} value={font}>{fontLabels[font]}</option>)}</select></label>
                  <label className="studio-range-field"><span>{tr('Font size', 'Розмір шрифту')}<code>{appearance.font_size}px</code></span><input
                    aria-label={`${label} ${tr('font size', 'розмір шрифту')}`}
                    type="range" min={bounds.minimum} max={bounds.maximum} step="1"
                    value={appearance.font_size}
                    onChange={(event) => setTypography(role, 'font_size', Number(event.target.value))}
                  /></label>
                </div></div>
              </div>
            })}
          </div>
          <p className="studio-section-note">{tr('Typography changes only editable creative copy. Logo artwork and iPhone system chrome keep their renderer-owned typography.', 'Типографіка змінює лише редагований текст креативу. Типографіка логотипів і системних елементів iPhone залишається під контролем рендерера.')}</p>
        </StudioSection>
        <StudioSection
          eyebrow={tr('OPTIONAL TEXTURES', 'НЕОБОВ’ЯЗКОВІ ТЕКСТУРИ')} title={tr('Material finish', 'Фактура поверхні')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          <label><span>{tr('Full post background', 'Повний фон допису')}</span><select aria-label={tr('Full post background texture', 'Текстура повного фону допису')} value={configuration.background.texture} onChange={(event) => setConfiguration({ ...configuration, background: { ...configuration.background, texture: event.target.value as StudioPhoneMetricsConfiguration['background']['texture'] } })}>
            {detail.catalog.variation.background_textures.map((texture) => <option key={texture} value={texture}>{textureLabel(texture)}</option>)}
          </select></label>
          <label><span>{tr('Left copy area', 'Ліва текстова зона')}</span><select aria-label={tr('Left copy area texture', 'Текстура лівої текстової зони')} value={configuration.copy_background.texture} onChange={(event) => setConfiguration({ ...configuration, copy_background: { texture: event.target.value as StudioPhoneMetricsConfiguration['copy_background']['texture'] } })}>
            {detail.catalog.variation.copy_background_textures.map((texture) => <option key={texture} value={texture}>{textureLabel(texture)}</option>)}
          </select></label>
          <label><span>{tr('Inside iPhone screen', 'Усередині екрана iPhone')}</span><select aria-label={tr('iPhone screen texture', 'Текстура екрана iPhone')} value={configuration.phone_screen.texture} onChange={(event) => setConfiguration({ ...configuration, phone_screen: { ...configuration.phone_screen, texture: event.target.value as StudioPhoneMetricsConfiguration['phone_screen']['texture'] } })}>
            {detail.catalog.variation.phone_screen_textures.map((texture) => <option key={texture} value={texture}>{textureLabel(texture)}</option>)}
          </select></label>
          <p className="studio-section-note">{tr('Each menu has Off plus three deterministic finishes. The left-area finish is bounded behind Natal and the copy only; every texture stays beneath text and interface details.', 'Кожне меню має вимкнений стан і три детерміновані фактури. Фактура лівої зони обмежена лише тлом під Natal і текстом; усі текстури залишаються під текстом та елементами інтерфейсу.')}</p>
        </StudioSection>
        <StudioSection
          eyebrow={tr('IN-PHONE ACTIONS', 'ДІЇ В ТЕЛЕФОНІ')} title={tr('Three bottom buttons', 'Три нижні кнопки')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          {content.phone_buttons.map((text, index) => {
            const button = configuration.phone_buttons[index]
            return <div className="phone-metrics-stat-input phone-action-button-input" key={index}>
              <label className="studio-toggle"><input aria-label={tr(`Show phone button ${index + 1}`, `Показувати кнопку в телефоні ${index + 1}`)} type="checkbox" checked={button.enabled !== false} onChange={(event) => setPhoneButton(index, 'enabled', event.target.checked)} /><span>{index + 1} · {button.enabled !== false ? tr('Visible', 'Видима') : tr('Hidden', 'Прихована')}</span></label>
              {button.enabled !== false && <div className="phone-metric-fields">
                <div className="studio-field-grid">
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
                  <EditableColorField className="studio-color-field" label={tr(`Phone button ${index + 1} text color`, `Колір тексту кнопки в телефоні ${index + 1}`)} hexLabel={tr(`Phone button ${index + 1} text color hex`, `HEX кольору тексту кнопки в телефоні ${index + 1}`)} value={button.text_color} onChange={(value) => setPhoneButton(index, 'text_color', value)} />
                  <EditableColorField className="studio-color-field" label={tr(`Phone button ${index + 1} background color`, `Колір фону кнопки в телефоні ${index + 1}`)} hexLabel={tr(`Phone button ${index + 1} background color hex`, `HEX кольору фону кнопки в телефоні ${index + 1}`)} value={button.background_color} onChange={(value) => setPhoneButton(index, 'background_color', value)} />
                </div>
              </div>}
            </div>
          })}
          <p className="studio-section-note">{tr('Each action is independent and stays inside the iPhone. The screenshot defaults are blue filled, elevated white, and blue text-only.', 'Кожна дія налаштовується окремо й залишається всередині iPhone. Типові стилі зі скриншота: синя заливка, біла кнопка з тінню та лише синій текст.')}</p>
        </StudioSection>
        <StudioSection
          eyebrow={tr('THREE METRIC CARDS', 'ТРИ КАРТКИ-МЕТРИКИ')} title={tr('Text and appearance', 'Текст і вигляд')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          {content.stats.map((stat, index) => {
            const card = configuration.metric_cards[index]
            return <div className="phone-metrics-stat-input" key={index}>
              <label className="studio-toggle"><input aria-label={tr(`Show metric ${index + 1}`, `Показувати метрику ${index + 1}`)} type="checkbox" checked={card.enabled !== false} onChange={(event) => setMetricCard(index, 'enabled', event.target.checked)} /><span>{index + 1} · {card.enabled !== false ? tr('Visible', 'Видима') : tr('Hidden', 'Прихована')}</span></label>
              {currentMetricSources?.[index] && <p className="studio-section-note" data-testid={`metric-${index + 1}-provenance`}>{currentMetricSources[index].origin === 'ai_hypothesis'
                ? tr('AI hypothesis · unvalidated', 'Гіпотеза ШІ · не перевірено')
                : currentMetricSources[index].origin === 'brief_supported'
                  ? tr('From Product Brief · unvalidated', 'З Product Brief · не перевірено')
                  : currentMetricSources[index].origin === 'legacy_unknown'
                    ? tr('Source unknown · unvalidated', 'Джерело невідоме · не перевірено')
                    : tr('Owner supplied · unvalidated', 'Вказано власником · не перевірено')}</p>}
              {card.enabled !== false && <div className="phone-metric-fields">
                <div className="studio-field-grid">
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
                  <EditableColorField className="studio-color-field" label={tr(`Metric ${index + 1} text color`, `Колір тексту метрики ${index + 1}`)} hexLabel={tr(`Metric ${index + 1} text color hex`, `HEX кольору тексту метрики ${index + 1}`)} value={card.text_color} onChange={(value) => setMetricCard(index, 'text_color', value)} />
                  <EditableColorField className="studio-color-field" label={tr(`Metric ${index + 1} background color`, `Колір фону метрики ${index + 1}`)} hexLabel={tr(`Metric ${index + 1} background color hex`, `HEX кольору фону метрики ${index + 1}`)} value={card.background_color} onChange={(value) => setMetricCard(index, 'background_color', value)} />
                </div>
              </div>}
            </div>
          })}
          <p className="studio-section-note">{tr('Each button is independent. The default is the reference cobalt fill, white text, and rounded shape.', 'Кожна кнопка налаштовується окремо. Типово використано еталонну синю заливку, білий текст і заокруглену форму.')}</p>
        </StudioSection>
        </>}
        <StudioSection
          className="phone-screen-rule" eyebrow={authored ? tr('POST IMAGE', 'ЗОБРАЖЕННЯ ДОПИСУ') : tr('IPHONE HERO VISUAL', 'ГЕРОЙ-ВІЗУАЛ IPHONE')}
          title={tr('Generate or enhance hero artwork', 'Згенерувати або покращити герой-візуал')}
          expandLabel={tr('EXPAND', 'РОЗГОРНУТИ')} collapseLabel={tr('COLLAPSE', 'ЗГОРНУТИ')}
        >
          {savedCreativeDirection && !editingCreativeDirection
            ? <PhoneHeroDirectionPicker
              language={language} value={savedCreativeDirection} locked disabled={mutationBusy}
              onReset={() => {
                setLegacyDirection({ style: '', background: '' })
                setEditingCreativeDirection(true)
                setError(''); setNotice('')
              }} idPrefix="phone-saved-direction"
            />
            : <><PhoneHeroDirectionPicker language={language} value={legacyDirection} onChange={setLegacyDirection} disabled={mutationBusy} idPrefix="phone-legacy-direction" /><div className="phone-hero-direction-actions"><button className="secondary phone-hero-direction-save" type="button" disabled={mutationBusy || !pendingCreativeDirection} onClick={() => void saveCreativeDirection()}><Check />{savedCreativeDirection
              ? tr('Save new direction', 'Зберегти новий напрям')
              : tr('Save direction & enable generation', 'Зберегти напрям і ввімкнути генерацію')}</button>{savedCreativeDirection && <button className="ghost" type="button" disabled={mutationBusy} onClick={() => {
                setEditingCreativeDirection(false)
                setLegacyDirection({ style: '', background: '' })
              }}><X />{tr('Cancel', 'Скасувати')}</button>}</div><p className="phone-hero-direction-note">{savedCreativeDirection
              ? tr('Choose a replacement direction. Save it without changing the current images, or generate to save and use it now.', 'Оберіть новий напрям. Збережіть його без зміни поточних зображень або запустіть генерацію, щоб одразу зберегти й застосувати його.')
              : tr('Choose one style and one background treatment. Save the direction, or generate to save and use it immediately.', 'Виберіть один стиль і один варіант фону. Збережіть напрям або запустіть генерацію, щоб одразу зберегти й застосувати його.')}</p></>}
          <p className="studio-section-note">{tr('Your written image request overrides style and background defaults. Describe the subject, action and setting.', 'Ваш опис зображення має пріоритет над типовим стилем і фоном. Опишіть об’єкт, дію та оточення.')}</p>
          <label><span>{tr('What should be shown', 'Що має бути зображено')}</span><textarea
            aria-label={tr('iPhone visual direction', 'Опис візуалу iPhone')}
            rows={4} maxLength={600} value={screenDirection}
            placeholder={tr('Example: translucent glass steps rising through soft blue light with one lime accent', 'Наприклад: прозорі скляні сходи в м’якому блакитному світлі з одним лаймовим акцентом')}
            onChange={(event) => { setScreenDirection(event.target.value); setInstruction({ origin: 'owner' }) }}
          /></label>
          <ImageReferenceInput value={referenceImage} onChange={setReferenceImage} language={language}
            disabled={mutationBusy || !canGenerateWithDirection || !detail.phone_screen_generation_available} />
          {detail.phone_screen_history.length > 0 && <div className="phone-screen-history">
            <div><strong>{tr('Last 3 images', 'Останні 3 зображення')}</strong><small>{tr('Choose one to apply or enhance', 'Виберіть для застосування або покращення')}</small></div>
            <div className="phone-screen-history-options" data-recent-image-contract="firebase-token-coalescing-v1" role="radiogroup" aria-label={tr('Recent iPhone images', 'Останні зображення iPhone')}>
              {detail.phone_screen_history.map((item, index) => <PhoneScreenHistoryOption
                key={item.sha256} api={api} basePath={basePath} item={item} index={index} busy={mutationBusy}
                currentLabel={tr('CURRENT', 'ПОТОЧНЕ')}
                label={item.selected
                  ? tr(`iPhone image ${index + 1}, current`, `Зображення iPhone ${index + 1}, поточне`)
                  : tr(`Select iPhone image ${index + 1}`, `Вибрати зображення iPhone ${index + 1}`)}
                retryLabel={item.selected
                  ? tr('Retry current iPhone image preview', 'Повторити прев’ю поточного зображення iPhone')
                  : tr(`Retry iPhone image ${index + 1} preview`, `Повторити прев’ю зображення iPhone ${index + 1}`)}
                onSelect={() => void selectPhoneScreen(item.sha256)}
              />)}
            </div>
          </div>}
          <label className={`studio-toggle phone-screen-enhance ${enhanceDisabled ? 'is-disabled' : ''}`}>
            <input
              aria-label={tr('Enhance current image', 'Покращити поточне зображення')}
              type="checkbox" checked={!referenceImage && enhanceCurrent && hasCurrentPhoneScreen}
              disabled={enhanceDisabled}
              onChange={(event) => setEnhanceCurrent(event.target.checked)}
            />
            <span><strong>{tr('Enhance current image', 'Покращити поточне зображення')}</strong><small>{hasCurrentPhoneScreen
              ? tr('Use the current raw hero as the image reference and apply your direction as an edit.', 'Використати поточний вихідний герой-візуал як референс і застосувати опис як редагування.')
              : tr('Available after the first hero image is generated.', 'Стане доступним після першої генерації герой-візуалу.')}</small></span>
          </label>
          <button className="primary phone-screen-generate" type="button"
            aria-busy={generating}
            disabled={mutationBusy || !canGenerateWithDirection || !detail.phone_screen_generation_available || screenDirection.trim().length < 8}
            onClick={() => void generatePhoneScreen()}>{generating ? <RefreshCcw className="spin" /> : <Sparkles />}{generating
              ? tr('Generating & applying…', 'Генеруємо й застосовуємо…')
              : tr('Generate & apply', 'Згенерувати й застосувати')}</button>
          <p>{detail.phone_screen_generation_available
            ? tr('Enhance sends the current raw hero image with your direction; turning it off generates from scratch. The UI, title, action buttons, device, and any shown Natal logo stay crisp, and the current visual is preserved if generation fails.', 'Режим покращення надсилає поточний вихідний герой-візуал разом з описом; якщо вимкнути його, зображення генерується з нуля. Інтерфейс, заголовок, кнопки дій, пристрій і кожен показаний логотип Natal залишаються чіткими, а в разі помилки поточний візуал зберігається.')
            : tr('Codex image generation is unavailable in this local Post editor. Sign in to Codex and restart the Post editor; the circles remain as the deterministic fallback.', 'Генерація зображень Codex недоступна в цьому локальному редакторі допису. Увійдіть у Codex і перезапустіть редактор; кола залишаються детермінованим резервним варіантом.')}
          </p>
        </StudioSection>
      </aside>
    </section>
  </div>
}
