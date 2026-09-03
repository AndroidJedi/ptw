import { Bold, Check, Highlighter, ImagePlus, RefreshCcw, Save } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../../api'
import { ErrorState } from '../../components/State'
import { translate, type Language } from '../../i18n'
import type {
  StudioPhoneMetricsConfiguration, StudioPhoneMetricsContent, StudioPhoneMetricsDetail,
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
        <section className="panel universal-section"><small>{tr('THREE METRICS', 'ТРИ МЕТРИКИ')}</small><h2>{tr('Owner-provided values', 'Значення від власника')}</h2>
          {content.stats.map((stat, index) => <div className="phone-metrics-stat-input" key={index}><strong>{index + 1}</strong><label><span>{tr('Value', 'Значення')}</span><input value={stat.value} maxLength={24} onChange={(event) => setStat(index, 'value', event.target.value)} /></label><label><span>{tr('Label', 'Підпис')}</span><input value={stat.label} maxLength={38} onChange={(event) => setStat(index, 'label', event.target.value)} /></label></div>)}
        </section>
        <section className="panel universal-section phone-screen-rule"><small>{tr('PHONE SCREEN', 'ЕКРАН ТЕЛЕФОНУ')}</small><p>{tr('The front-facing black iPhone and crisp Natal app shell are fixed. Studio previews use deterministic text-free hero art; Post drafts generate one final hero visual from the approved Brief. Natal, the optional owner title, and the CTA are then added by the renderer, so generated pixels never need to spell words or imitate UI.', 'Фронтальний чорний iPhone і чітка оболонка застосунку Natal зафіксовані. Прев’ю Студії використовує детермінований герой-арт без тексту; для чернетки допису фінальний візуал генерується з затвердженого Брифу. Natal, необов’язковий заголовок власника й CTA потім додає рендерер, тому згенерованим пікселям не потрібно відтворювати слова чи інтерфейс.')}</p></section>
      </aside>
    </section>
  </div>
}
