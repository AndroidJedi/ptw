import { Check, ImagePlus, Maximize2, Plus, RefreshCcw, Save, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type { LandingConfiguration, LandingContent, LandingDetail, LandingSummary } from '../types'

type SourcePost = { creative_id: string; version: number; version_sha256: string; template_id: string; source_brief_id: string }

function clone<T>(value: T): T { return structuredClone(value) }

function TextField({ label, value, onChange, multiline = false }: { label: string; value: string; onChange: (value: string) => void; multiline?: boolean }) {
  return <label className="landing-field"><span>{label}</span>{multiline
    ? <textarea aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} />
    : <input aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} />
  }</label>
}

function LandingPreview({ configuration, content, imageUrls }: { configuration: LandingConfiguration; content: LandingContent; imageUrls: Record<string, string> }) {
  const theme = configuration.theme
  const styles = {
    '--landing-background': theme.background_color, '--landing-surface': theme.surface_color,
    '--landing-text': theme.text_color, '--landing-accent': theme.accent_color,
    '--landing-radius': `${theme.corner_radius}px`, '--landing-font': theme.font_family,
    '--landing-heading-font': theme.heading_font_family,
  } as CSSProperties
  return <article className={`landing-preview landing-hero-${configuration.hero.alignment}`} style={styles} aria-label="Landing live preview">
    <section className={`landing-preview-hero image-${configuration.hero.image_position}`}>
      <div><small>PTW · PRIVATE LANDING</small><h1>{content.hero.title || 'Hero title'}</h1><p>{content.hero.supporting_text || 'Supporting copy'}</p><button>{content.hero.cta_label || 'Call to action'}</button></div>
      {imageUrls.hero_visual ? <img src={imageUrls.hero_visual} alt="Generated landing hero visual" /> : <div className="landing-visual-placeholder">Hero visual</div>}
    </section>
    <section className={`landing-preview-features ${configuration.features.layout}`}><h2>Key features</h2><div>{content.features.map((feature, index) => <article key={index}><strong>{feature.title || `Feature ${index + 1}`}</strong><p>{feature.description || 'Feature description'}</p></article>)}</div></section>
    <section className={`landing-preview-proof ${configuration.social_proof.layout}`}><h2>{content.social_proof.heading || 'Social proof'}</h2>{content.social_proof.items.length ? <div>{content.social_proof.items.map((item, index) => <blockquote key={index}>“{item.statement}”<footer>{item.attribution}</footer></blockquote>)}</div> : <p>Owner-provided evidence appears here.</p>}</section>
    <section className={`landing-preview-break ${configuration.visual_break.height}`}>{imageUrls.visual_break_visual ? <img src={imageUrls.visual_break_visual} alt="Generated landing visual break" /> : <div className="landing-visual-placeholder">Visual break</div>}</section>
    <section className={`landing-preview-contacts ${configuration.contacts.alignment}`}><h2>{content.contacts.heading || 'Contact us'}</h2><p>{content.contacts.supporting_text || 'Contact details'}</p><div>{content.contacts.email && <span>{content.contacts.email}</span>}{content.contacts.phone && <span>{content.contacts.phone}</span>}{content.contacts.url && <span>{content.contacts.url}</span>}</div></section>
    <section className={`landing-preview-faq ${configuration.faq.style}`}><h2>FAQ</h2>{content.faq.map((item, index) => <details key={index} open><summary>{item.question || `Question ${index + 1}`}</summary><p>{item.answer || 'Answer'}</p></details>)}</section>
  </article>
}

export function LandingView({ api, language, projectId = null, landingId = null, onLanding = () => {} }: { api: ApiClient; language: Language; projectId?: string | null; landingId?: string | null; onLanding?: (landingId: string) => void }) {
  const [pages, setPages] = useState<LandingSummary[] | null>(null)
  const [sources, setSources] = useState<SourcePost[] | null>(null)
  const [detail, setDetail] = useState<LandingDetail | null>(null)
  const [configuration, setConfiguration] = useState<LandingConfiguration | null>(null)
  const [content, setContent] = useState<LandingContent | null>(null)
  const [images, setImages] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [landingViewOpen, setLandingViewOpen] = useState(false)
  const [note, setNote] = useState('Initial approved Landing')
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const base = projectId ? `/api/v1/landings/projects/${projectId}` : ''

  const applyDetail = (value: LandingDetail) => {
    setDetail(value); setConfiguration(clone(value.configuration)); setContent(clone(value.content)); setError('')
  }
  const reload = async () => {
    if (!projectId) return
    setError(''); setPages(null); setSources(null); setDetail(null)
    try {
      const [pageList, sourceList] = await Promise.all([
        api.get<{ items: LandingSummary[] }>(`${base}/pages`), api.get<{ items: SourcePost[] }>(`${base}/source-posts`),
      ])
      setPages(pageList.items); setSources(sourceList.items)
      const selected = pageList.items.find((item) => item.landing_id === landingId) || pageList.items[0]
      if (selected) {
        const value = await api.get<LandingDetail>(`${base}/pages/${selected.landing_id}`)
        applyDetail(value)
        if (selected.landing_id !== landingId) onLanding(selected.landing_id)
      }
    } catch (cause) { setPages([]); setSources([]); setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  useEffect(() => { void reload() }, [projectId, landingId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!detail || !projectId || !['queued', 'composing', 'generating_images'].includes(detail.status)) return
    let active = true
    let timer: number | undefined
    const refreshProgress = async () => {
      try {
        const value = await api.get<LandingDetail>(`${base}/pages/${detail.landing_id}`)
        if (active) applyDetail(value)
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        if (active) timer = window.setTimeout(refreshProgress, 2_500)
      }
    }
    timer = window.setTimeout(refreshProgress, 2_500)
    return () => { active = false; if (timer !== undefined) window.clearTimeout(timer) }
  }, [api, base, detail?.landing_id, detail?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!landingViewOpen) return
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setLandingViewOpen(false) }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [landingViewOpen])

  useEffect(() => {
    let active = true
    const urls: string[] = []
    const load = async () => {
      if (!detail || !projectId) { setImages({}); return }
      const next: Record<string, string> = {}
      await Promise.all(detail.assets.filter((item) => item.available && item.sha256).map(async (item) => {
        const blob = await api.image(`${base}/pages/${detail.landing_id}/visuals/${item.slot}/history/${item.sha256}`, 'image/png', item.sha256!)
        const url = URL.createObjectURL(blob); urls.push(url); next[item.slot] = url
      }))
      if (active) setImages(next)
    }
    void load().catch((cause) => active && setError(cause instanceof Error ? cause.message : String(cause)))
    return () => { active = false; urls.forEach((url) => URL.revokeObjectURL(url)) }
  }, [detail?.landing_id, detail?.state_sha256, projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const persist = async () => {
    if (!detail || !configuration || !content) throw new Error('Landing draft is not ready')
    const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/configuration`, { base_sha256: detail.state_sha256, configuration, content })
    applyDetail(value)
    return value
  }
  const create = async (source: SourcePost) => {
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingSummary }>(`${base}/pages`, { source_creative_id: source.creative_id, source_version: source.version })
      onLanding(value.landing.landing_id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const createVariant = async () => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingSummary }>(`${base}/pages/variants`, {
        source_creative_id: detail.source_creative_id, source_version: detail.source_version,
      })
      onLanding(value.landing.landing_id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const save = async (approve = false) => {
    if (!detail || !configuration || !content) return
    setBusy(true); setError('')
    try {
      const value = await api.post<{ landing: LandingDetail }>(`${base}/pages/${detail.landing_id}/${approve ? 'approve' : 'save'}`, approve
        ? { base_sha256: detail.state_sha256, configuration, content, change_note: note }
        : { base_sha256: detail.state_sha256, configuration, content })
      applyDetail(value.landing)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const generate = async (slot: 'hero_visual' | 'visual_break_visual', enhance = false) => {
    if (!detail || !content) return
    setBusy(true); setError('')
    try {
      const saved = await persist()
      const direction = slot === 'hero_visual' ? content.hero.visual_direction : content.visual_break.visual_direction
      const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/visuals/${slot}/generate`, { base_sha256: saved.state_sha256, visual_direction: direction, ...(enhance ? { enhance_current: true } : {}) }, { deadlineMs: 480_000 })
      applyDetail(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const selectVisual = async (slot: 'hero_visual' | 'visual_break_visual', sha256: string) => {
    if (!detail) return
    setBusy(true); setError('')
    try {
      const value = await api.post<LandingDetail>(`${base}/pages/${detail.landing_id}/visuals/${slot}/select`, {
        base_sha256: detail.state_sha256, sha256,
      })
      applyDetail(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const retry = async () => {
    if (!detail) return
    setBusy(true)
    try { await api.post(`${base}/pages/${detail.landing_id}/retry`, {}); await reload() } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setBusy(false) }
  }
  const setFeature = (index: number, field: 'title' | 'description', value: string) => setContent((current) => current && ({ ...current, features: current.features.map((item, i) => i === index ? { ...item, [field]: value } : item) }))
  const setFaq = (index: number, field: 'question' | 'answer', value: string) => setContent((current) => current && ({ ...current, faq: current.faq.map((item, i) => i === index ? { ...item, [field]: value } : item) }))
  const updateProof = (index: number, field: 'statement' | 'attribution', value: string) => setContent((current) => current && ({ ...current, social_proof: { ...current.social_proof, items: current.social_proof.items.map((item, i) => i === index ? { ...item, [field]: value } : item) } }))
  const status = useMemo(() => detail?.status, [detail?.status])

  if (!projectId) return <Empty><h2>{tr('Choose a Project', 'Оберіть проєкт')}</h2><p>{tr('A Landing is always scoped to one Project.', 'Лендінг завжди належить одному проєкту.')}</p></Empty>
  if (pages === null || sources === null) return <Loading language={language} />
  if (error) return <ErrorState message={error} retry={() => void reload()} language={language} />
  if (!detail) return <section className="panel landing-source-picker"><small>{tr('PRIVATE LANDING', 'ПРИВАТНИЙ ЛЕНДІНГ')}</small><h1>{tr('Create a Landing from an approved Post', 'Створіть лендінг із затвердженого допису')}</h1><p>{tr('Landing captures the selected Post version’s design, then remains independently editable.', 'Лендінг зафіксує дизайн обраної версії допису та далі редагуватиметься окремо.')}</p>{sources.length ? <div className="landing-source-list">{sources.map((source) => <button key={`${source.creative_id}:${source.version}`} className="panel" disabled={busy} onClick={() => void create(source)}><Sparkles /><span>{source.template_id} · v{source.version}</span><small>{source.creative_id.slice(0, 8)}</small></button>)}</div> : <Empty><h2>{tr('Approve a Post first', 'Спершу затвердьте допис')}</h2><p>{tr('Landing starts only from an immutable approved Post version.', 'Лендінг створюється лише з незмінної затвердженої версії допису.')}</p></Empty>}</section>
  if (status !== 'draft' || !configuration || !content) return <section className="panel landing-progress"><small>LANDING · {detail.template_id}</small><h1>{status === 'failed' ? tr('Landing generation needs attention', 'Створення лендінгу потребує уваги') : tr('Building the Landing', 'Створюємо лендінг')}</h1><p>{status === 'composing' ? tr('Writing the fixed page sections…', 'Заповнюємо фіксовані секції сторінки…') : status === 'generating_images' ? tr('Generating matching page visuals…', 'Створюємо візуали в стилі допису…') : tr('Queued for generation…', 'У черзі на створення…')}</p>{status === 'failed' && <button className="primary" disabled={busy} onClick={() => void retry()}><RefreshCcw />{tr('Retry', 'Повторити')}</button>}</section>

  const selected = (slot: string) => detail.assets.find((item) => item.slot === slot)
  const history = (slot: 'hero_visual' | 'visual_break_visual') => selected(slot)?.history || []
  const historyPicker = (slot: 'hero_visual' | 'visual_break_visual') => history(slot).length > 1 && <div className="landing-visual-history" aria-label={tr(`${slot} history`, `${slot} історія`)}>{history(slot).map((item, index) => <button key={item.sha256} className={item.selected ? 'active' : ''} disabled={busy || item.selected} onClick={() => void selectVisual(slot, item.sha256)}>{tr(`Visual ${index + 1}`, `Візуал ${index + 1}`)}</button>)}</div>
  const siblings = pages.filter((item) => item.source_creative_id === detail.source_creative_id && item.source_version === detail.source_version)
  const isLatestSibling = siblings[0]?.landing_id === detail.landing_id
  return <section className="landing-studio"><header className="landing-studio-header"><div><small>PRIVATE LANDING · POST v{detail.source_version}</small><h1>{tr('Landing Studio', 'Landing Studio')}</h1><p>{tr('Every section is bounded and editable. Changes remain private.', 'Кожна секція обмежена та редагована. Зміни залишаються приватними.')}</p></div><div><div className="landing-variant-actions">{pages.length > 1 && <select aria-label={tr('Landing variant', 'Варіант лендінгу')} value={detail.landing_id} onChange={(event) => onLanding(event.target.value)}>{pages.map((item) => <option key={item.landing_id} value={item.landing_id}>{tr('Landing', 'Лендінг')} {item.ordinal} · {item.approved_version_count ? tr('approved', 'затверджено') : tr('draft', 'чернетка')}</option>)}</select>}{isLatestSibling && detail.approved_version_count > 0 && <button disabled={busy} onClick={() => void createVariant()}><Plus />{tr('New variant', 'Новий варіант')}</button>}</div><button className="secondary" onClick={() => setLandingViewOpen(true)}><Maximize2 />{tr('View Landing', 'Переглянути лендінг')}</button><button className="secondary" disabled={busy} onClick={() => void save(false)}><Save />{tr('Save Landing', 'Зберегти лендінг')}</button><button className="primary" disabled={busy} onClick={() => void save(true)}><Check />{tr('Approve Landing', 'Затвердити лендінг')}</button></div></header>
    <div className="landing-studio-grid"><aside className="landing-controls panel">
      <h2>{tr('Page settings', 'Налаштування сторінки')}</h2>
      <label className="landing-field"><span>{tr('Accent color', 'Акцентний колір')}</span><input aria-label={tr('Accent color', 'Акцентний колір')} type="color" value={configuration.theme.accent_color} onChange={(event) => setConfiguration({ ...configuration, theme: { ...configuration.theme, accent_color: event.target.value } })} /></label>
      <label className="landing-field"><span>{tr('Heading font', 'Шрифт заголовків')}</span><select aria-label={tr('Heading font', 'Шрифт заголовків')} value={configuration.theme.heading_font_family} onChange={(event) => setConfiguration({ ...configuration, theme: { ...configuration.theme, heading_font_family: event.target.value as LandingConfiguration['theme']['heading_font_family'] } })}>{detail.catalog.font_families.map((font) => <option key={font}>{font}</option>)}</select></label>
      <h2>{tr('Hero', 'Hero')}</h2>
      <TextField label={tr('Hero title', 'Hero заголовок')} value={content.hero.title} onChange={(value) => setContent({ ...content, hero: { ...content.hero, title: value } })} />
      <TextField label={tr('Hero supporting text', 'Hero текст')} value={content.hero.supporting_text} multiline onChange={(value) => setContent({ ...content, hero: { ...content.hero, supporting_text: value } })} />
      <TextField label={tr('CTA label', 'Текст CTA')} value={content.hero.cta_label} onChange={(value) => setContent({ ...content, hero: { ...content.hero, cta_label: value } })} />
      <TextField label={tr('Hero visual direction', 'Напрям Hero-візуалу')} value={content.hero.visual_direction} multiline onChange={(value) => setContent({ ...content, hero: { ...content.hero, visual_direction: value } })} />
      <div className="landing-visual-actions"><button className="secondary" disabled={busy || !content.hero.visual_direction} onClick={() => void generate('hero_visual')}><ImagePlus />{tr('Generate hero', 'Згенерувати Hero')}</button><button disabled={busy || !selected('hero_visual')?.available} onClick={() => void generate('hero_visual', true)}>{tr('Enhance', 'Покращити')}</button></div>{historyPicker('hero_visual')}
      <h2>{tr('Three killer features', 'Три ключові переваги')}</h2>{content.features.map((feature, index) => <div className="landing-repeater" key={index}><TextField label={`${tr('Feature', 'Перевага')} ${index + 1} ${tr('title', 'назва')}`} value={feature.title} onChange={(value) => setFeature(index, 'title', value)} /><TextField label={`${tr('Feature', 'Перевага')} ${index + 1} ${tr('description', 'опис')}`} value={feature.description} multiline onChange={(value) => setFeature(index, 'description', value)} /></div>)}
      <h2>{tr('Social proof', 'Соціальний доказ')}</h2><TextField label={tr('Proof heading', 'Заголовок доказу')} value={content.social_proof.heading} onChange={(value) => setContent({ ...content, social_proof: { ...content.social_proof, heading: value } })} />
      {content.social_proof.items.map((item, index) => <div className="landing-repeater" key={index}><TextField label={tr('Evidence statement', 'Текст доказу')} value={item.statement} multiline onChange={(value) => updateProof(index, 'statement', value)} /><TextField label={tr('Evidence attribution', 'Джерело доказу')} value={item.attribution} onChange={(value) => updateProof(index, 'attribution', value)} /><button aria-label={tr('Remove evidence', 'Видалити доказ')} onClick={() => setContent({ ...content, social_proof: { ...content.social_proof, items: content.social_proof.items.filter((_, i) => i !== index) } })}><Trash2 /></button></div>)}
      {content.social_proof.items.length < 3 && <button onClick={() => setContent({ ...content, social_proof: { ...content.social_proof, items: [...content.social_proof.items, { statement: '', attribution: '' }] } })}><Plus />{tr('Add owner evidence', 'Додати доказ власника')}</button>}
      <h2>{tr('Visual break', 'Візуальна пауза')}</h2><TextField label={tr('Visual-break direction', 'Напрям візуальної паузи')} value={content.visual_break.visual_direction} multiline onChange={(value) => setContent({ ...content, visual_break: { visual_direction: value } })} /><div className="landing-visual-actions"><button className="secondary" disabled={busy || !content.visual_break.visual_direction} onClick={() => void generate('visual_break_visual')}><ImagePlus />{tr('Generate visual', 'Згенерувати візуал')}</button><button disabled={busy || !selected('visual_break_visual')?.available} onClick={() => void generate('visual_break_visual', true)}>{tr('Enhance', 'Покращити')}</button></div>{historyPicker('visual_break_visual')}
      <h2>{tr('Contacts', 'Контакти')}</h2><TextField label={tr('Contacts heading', 'Заголовок контактів')} value={content.contacts.heading} onChange={(value) => setContent({ ...content, contacts: { ...content.contacts, heading: value } })} /><TextField label={tr('Contacts supporting text', 'Текст контактів')} value={content.contacts.supporting_text} multiline onChange={(value) => setContent({ ...content, contacts: { ...content.contacts, supporting_text: value } })} /><TextField label={tr('Email', 'Email')} value={content.contacts.email} onChange={(value) => setContent({ ...content, contacts: { ...content.contacts, email: value } })} /><TextField label={tr('Phone', 'Телефон')} value={content.contacts.phone} onChange={(value) => setContent({ ...content, contacts: { ...content.contacts, phone: value } })} /><TextField label={tr('HTTPS contact URL', 'HTTPS URL контакту')} value={content.contacts.url} onChange={(value) => setContent({ ...content, contacts: { ...content.contacts, url: value } })} />
      <h2>FAQ</h2>{content.faq.map((item, index) => <div className="landing-repeater" key={index}><TextField label={`FAQ ${index + 1}`} value={item.question} onChange={(value) => setFaq(index, 'question', value)} /><TextField label={tr('Answer', 'Відповідь')} value={item.answer} multiline onChange={(value) => setFaq(index, 'answer', value)} /></div>)}
      <TextField label={tr('Approval note', 'Нотатка затвердження')} value={note} onChange={setNote} />
    </aside><div className="landing-preview-panel"><small>{tr('LIVE RESPONSIVE PREVIEW', 'ЖИВЕ АДАПТИВНЕ ПРЕВ’Ю')}</small><LandingPreview configuration={configuration} content={content} imageUrls={images} /></div></div>
    {landingViewOpen && <div className="landing-view-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setLandingViewOpen(false) }}><section className="landing-view-dialog" role="dialog" aria-modal="true" aria-label={tr('Full-screen Landing preview', 'Повноекранне прев’ю лендінгу')}><header><div><small>{tr('PRIVATE LANDING', 'ПРИВАТНИЙ ЛЕНДІНГ')}</small><strong>{tr('Full-screen preview', 'Повноекранне прев’ю')}</strong></div><button className="ghost" aria-label={tr('Close full-screen preview', 'Закрити повноекранне прев’ю')} onClick={() => setLandingViewOpen(false)}><X /></button></header><div className="landing-view-canvas"><LandingPreview configuration={configuration} content={content} imageUrls={images} /></div></section></div>}
  </section>
}
