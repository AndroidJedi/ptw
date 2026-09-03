import { Check, ImagePlus, RefreshCcw, Save } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../../api'
import { ErrorState } from '../../components/State'
import { translate, type Language } from '../../i18n'
import type { StudioPhoneMetricsContent, StudioPhoneMetricsDetail } from '../../types'

export function PhoneMetricsStudio({ api, language, detail: initialDetail, onDetail }: {
  api: ApiClient
  language: Language
  detail: StudioPhoneMetricsDetail
  onDetail: (detail: StudioPhoneMetricsDetail | unknown) => void
}) {
  const [detail, setDetail] = useState(initialDetail)
  const [content, setContent] = useState<StudioPhoneMetricsContent>(structuredClone(initialDetail.content))
  const [previewUrl, setPreviewUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const previewGeneration = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  useEffect(() => {
    setDetail(initialDetail)
    setContent(structuredClone(initialDetail.content))
  }, [initialDetail.state_sha256])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const replacePreview = (blob: Blob) => setPreviewUrl((current) => {
    if (current) URL.revokeObjectURL(current)
    return URL.createObjectURL(blob)
  })
  const render = async (saved: StudioPhoneMetricsDetail, draft = false, nextContent = content) => {
    const generation = ++previewGeneration.current
    setPreviewBusy(true)
    try {
      const blob = await api.postMedia('/api/v1/studio/preview', draft ? {
        state_sha256: saved.state_sha256, configuration: saved.configuration, content: nextContent,
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
      if (JSON.stringify(content) !== JSON.stringify(detail.content)) void render(detail, true, content)
    }, 220)
    return () => window.clearTimeout(timer)
  }, [content, detail.state_sha256])

  const applyDetail = (next: StudioPhoneMetricsDetail) => {
    setDetail(next); setContent(structuredClone(next.content)); onDetail(next)
  }
  const save = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      const next = await api.post<StudioPhoneMetricsDetail>('/api/v1/studio/configuration', {
        base_sha256: detail.state_sha256, configuration: detail.configuration, content,
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
          <label><span>{tr('Eyebrow', 'Надзаголовок')}</span><input value={content.offer} maxLength={32} onChange={(event) => setContent({ ...content, offer: event.target.value })} /></label>
          <label><span>{tr('Headline', 'Заголовок')}</span><textarea rows={4} value={content.hero_title} maxLength={140} onChange={(event) => setContent({ ...content, hero_title: event.target.value })} /></label>
          <label><span>{tr('Supporting text', 'Пояснювальний текст')}</span><textarea rows={4} value={content.supporting_text} maxLength={220} onChange={(event) => setContent({ ...content, supporting_text: event.target.value })} /></label>
          <label><span>CTA</span><input value={content.cta} maxLength={60} onChange={(event) => setContent({ ...content, cta: event.target.value })} /></label>
          <label><span>{tr('Optional in-phone title', 'Необов’язковий заголовок у телефоні')}</span><input value={content.phone_hero_title} maxLength={72} onChange={(event) => setContent({ ...content, phone_hero_title: event.target.value })} /></label>
        </section>
        <section className="panel universal-section"><small>{tr('THREE METRICS', 'ТРИ МЕТРИКИ')}</small><h2>{tr('Owner-provided values', 'Значення від власника')}</h2>
          {content.stats.map((stat, index) => <div className="phone-metrics-stat-input" key={index}><strong>{index + 1}</strong><label><span>{tr('Value', 'Значення')}</span><input value={stat.value} maxLength={24} onChange={(event) => setStat(index, 'value', event.target.value)} /></label><label><span>{tr('Label', 'Підпис')}</span><input value={stat.label} maxLength={38} onChange={(event) => setStat(index, 'label', event.target.value)} /></label></div>)}
        </section>
        <section className="panel universal-section phone-screen-rule"><small>{tr('PHONE SCREEN', 'ЕКРАН ТЕЛЕФОНУ')}</small><p>{tr('The fixed black iPhone frame and Natal name are not editable. This Studio preview uses a deterministic text-free visual; Post drafts generate final visual-only screen art on the server. No text, logos, UI labels, numbers, or buttons may appear in the screen artwork.', 'Фіксовані чорна рамка iPhone та назва Natal не редагуються. Це прев’ю Студії використовує детермінований арт без тексту; у чернетках допису фінальний візуальний арт екрана генерується на сервері. На екрані не може бути тексту, логотипів, UI-міток, чисел чи кнопок.')}</p></section>
      </aside>
    </section>
  </div>
}
