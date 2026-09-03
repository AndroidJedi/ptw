import { Bold, Check, Highlighter, ImagePlus, RefreshCcw, Save, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../../api'
import { ErrorState } from '../../components/State'
import { translate, type Language } from '../../i18n'
import type {
  StudioPhoneActionButtonConfiguration, StudioPhoneMetricCardConfiguration,
  StudioPhoneMetricsConfiguration, StudioPhoneMetricsContent,
  StudioPhoneMetricsDetail,
} from '../../types'

export function PhoneMetricsStudio({ api, language, detail: initialDetail, onDetail }: {
  api: ApiClient
  language: Language
  detail: StudioPhoneMetricsDetail
  onDetail: (detail: StudioPhoneMetricsDetail | unknown) => void
}) {
  const [detail, setDetail] = useState(initialDetail)
  const [configuration, setConfiguration] = useState<StudioPhoneMetricsConfiguration>(structuredClone(initialDetail.configuration))
  const [content, setContent] = useState<StudioPhoneMetricsContent>(structuredClone(initialDetail.content))
  const [previewUrl, setPreviewUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [screenDirection, setScreenDirection] = useState(() => {
    const source = initialDetail.assets.find((asset) => asset.slot === 'phone_screen')?.source
    return typeof source?.visual_direction === 'string' ? source.visual_direction : ''
  })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const previewGeneration = useRef(0)
  const supportingTextRef = useRef<HTMLTextAreaElement>(null)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const textureLabel = (texture: string) => ({
    none: tr('Off', 'Без текстури'),
    grain: tr('Fine grain', 'Дрібне зерно'),
    concrete: tr('Concrete', 'Бетон'),
    travertine: tr('Travertine', 'Травертин'),
    paper: tr('Soft paper', 'М’який папір'),
    frosted: tr('Frosted glass', 'Матове скло'),
  }[texture] || texture)

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
      const blob = await api.postMedia('/api/v1/studio/preview', draft ? {
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
      const next = await api.post<StudioPhoneMetricsDetail>('/api/v1/studio/configuration', {
        base_sha256: detail.state_sha256, configuration, content,
      }, { deadlineMs: 60_000 })
      applyDetail(next); await render(next)
      setNotice(tr('Phone & metrics setup saved.', 'Налаштування «Телефон і метрики» збережено.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const generatePhoneScreen = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      let saved = detail
      if (
        JSON.stringify(configuration) !== JSON.stringify(detail.configuration)
        || JSON.stringify(content) !== JSON.stringify(detail.content)
      ) {
        saved = await api.post<StudioPhoneMetricsDetail>('/api/v1/studio/configuration', {
          base_sha256: detail.state_sha256, configuration, content,
        }, { deadlineMs: 60_000 })
        applyDetail(saved)
      }
      const next = await api.post<StudioPhoneMetricsDetail>('/api/v1/studio/phone-screen/generate', {
        base_sha256: saved.state_sha256, visual_direction: screenDirection.trim(),
      }, { deadlineMs: 360_000 })
      applyDetail(next); await render(next)
      setNotice(tr('New iPhone hero visual generated and applied.', 'Новий герой-візуал для iPhone згенеровано й застосовано.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const selectTemplate = async (templateId: string) => {
    if (templateId === detail.template_id) return
    setBusy(true); setError(''); setNotice('')
    try {
      const next = await api.post<StudioPhoneMetricsDetail>('/api/v1/studio/templates/apply', {
        base_sha256: detail.state_sha256, template_id: templateId,
      }, { deadlineMs: 60_000 })
      onDetail(next)
      setNotice(tr('Template replaced the complete editable draft.', 'Шаблон повністю замінив редаговану чернетку.'))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const approve = async () => {
    setBusy(true); setError('')
    try {
      const next = await api.post<StudioPhoneMetricsDetail>('/api/v1/studio/approve', {
        state_sha256: detail.state_sha256, change_note: 'Phone & metrics creative',
      }, { deadlineMs: 90_000 })
      applyDetail(next); setNotice(tr('Immutable phone creative saved.', 'Незмінний креатив з телефоном збережено.'))
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
    <section className="panel studio-template-selector" aria-label={tr('Studio template selector', 'Вибір шаблону Студії')}>
      <small>{tr('TEMPLATE', 'ШАБЛОН')}</small><h2>{tr('Start from a fixed composition', 'Почніть із фіксованої композиції')}</h2>
      <p>{tr('Changing template replaces all editable copy and assets. Saved immutable versions are preserved.', 'Зміна шаблону замінює весь редагований текст і ресурси. Збережені незмінні версії не змінюються.')}</p>
      <div className="studio-template-grid">{detail.templates.map((template) => <button key={template.template_id} type="button" className={`studio-template-card ${template.template_id === detail.template_id ? 'is-active' : ''}`} disabled={busy} onClick={() => void selectTemplate(template.template_id)}>
        <strong>{template.name}</strong><small>{template.canvas.width}×{template.canvas.height}</small><span>{template.description}</span>
      </button>)}</div>
    </section>
    <section className="studio-commandbar phone-metrics-commandbar">
      <div><small>{tr('FIXED NATAL TEMPLATE', 'ФІКСОВАНИЙ ШАБЛОН NATAL')}</small><strong>phone_metrics · v{detail.catalog.template_version}</strong></div>
      <button className="secondary" disabled={busy} onClick={() => void approve()}><Check />{tr('Save immutable', 'Зберегти незмінно')}</button>
      <button className="primary" disabled={busy} onClick={() => void save()}><Save />{tr('Save setup', 'Зберегти налаштування')}</button>
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
              <label className="universal-range-field"><span>{tr('Font size', 'Розмір шрифту')}<code>{configuration.supporting_text.font_size}px</code></span><input aria-label={tr('Supporting text font size', 'Розмір пояснювального тексту')} type="range" min="20" max="38" step="1" value={configuration.supporting_text.font_size} onChange={(event) => setConfiguration({ ...configuration, supporting_text: { ...configuration.supporting_text, font_size: Number(event.target.value) } })} /></label>
              <label className="universal-color-field"><span>{tr('Word colour', 'Колір слів')}<code>{configuration.supporting_text.highlight_color}</code></span><input aria-label={tr('Highlight color', 'Колір підсвічування')} type="color" value={configuration.supporting_text.highlight_color} onChange={(event) => setConfiguration({ ...configuration, supporting_text: { ...configuration.supporting_text, highlight_color: event.target.value.toUpperCase() } })} /></label>
            </div>
          </div>
          <label><span>CTA</span><input value={content.cta} maxLength={60} onChange={(event) => setContent({ ...content, cta: event.target.value })} /></label>
          <label><span>{tr('Optional in-phone title', 'Необов’язковий заголовок у телефоні')}</span><input value={content.phone_hero_title} maxLength={72} onChange={(event) => setContent({ ...content, phone_hero_title: event.target.value })} /></label>
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
        <section className="panel universal-section phone-screen-rule"><small>{tr('IPHONE HERO VISUAL', 'ГЕРОЙ-ВІЗУАЛ IPHONE')}</small><h2>{tr('Generate a new background', 'Згенерувати новий фон')}</h2>
          <label><span>{tr('Visual direction', 'Опис візуалу')}</span><textarea
            aria-label={tr('iPhone visual direction', 'Опис візуалу iPhone')}
            rows={4} maxLength={600} value={screenDirection}
            placeholder={tr('Example: translucent glass steps rising through soft blue light with one lime accent', 'Наприклад: прозорі скляні сходи в м’якому блакитному світлі з одним лаймовим акцентом')}
            onChange={(event) => setScreenDirection(event.target.value)}
          /></label>
          <button className="primary phone-screen-generate" type="button"
            disabled={busy || !detail.phone_screen_generation_available || screenDirection.trim().length < 8}
            onClick={() => void generatePhoneScreen()}><Sparkles />{tr('Generate & apply', 'Згенерувати й застосувати')}</button>
          <p>{detail.phone_screen_generation_available
            ? tr('This replaces only the mutable artwork inside the iPhone. The Natal logo, UI, title, action buttons, and device stay crisp; the current visual is preserved if generation fails.', 'Це замінює лише змінний арт усередині iPhone. Логотип Natal, інтерфейс, заголовок, кнопки дій і пристрій залишаються чіткими; у разі помилки поточний візуал зберігається.')
            : tr('Codex image generation is unavailable in this local Studio runtime. Sign in to Codex and restart Studio; the circles remain as the deterministic fallback.', 'Генерація зображень Codex недоступна в цьому локальному середовищі Студії. Увійдіть у Codex і перезапустіть Студію; кола залишаються детермінованим резервним варіантом.')}
          </p>
        </section>
      </aside>
    </section>
  </div>
}
