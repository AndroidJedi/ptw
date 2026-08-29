import {
  Check, Download, ImagePlus, RefreshCcw, Save, Search, Upload, WandSparkles,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { StudioTuneWizard } from '../components/studio/StudioTuneWizard'
import { ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type {
  StudioUniversalConfiguration, StudioUniversalContent, StudioUniversalDetail,
} from '../types'

function fileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error || new Error('File could not be read.'))
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '')
    reader.readAsDataURL(file)
  })
}

function downloadJson(filename: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function normalizedPreviewContent(value: StudioUniversalContent): StudioUniversalContent {
  return {
    ...value,
    bullets: value.bullets.map((item) => item.trim()).filter(Boolean),
  }
}

function NumberField({ label, value, min, max, step = 1, onChange }: {
  label: string
  value: number
  min: number
  max: number
  step?: number
  onChange: (value: number) => void
}) {
  return <label><span>{label}</span><input
    aria-label={label} type="number" value={value} min={min} max={max} step={step}
    onChange={(event) => onChange(Number(event.target.value))}
  /></label>
}

export function StudioView({ api, language, tuneMode = false }: {
  api: ApiClient
  language: Language
  tuneMode?: boolean
}) {
  const [detail, setDetail] = useState<StudioUniversalDetail | null>(null)
  const [configuration, setConfiguration] = useState<StudioUniversalConfiguration | null>(null)
  const [content, setContent] = useState<StudioUniversalContent | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [backgroundQuery, setBackgroundQuery] = useState('')
  const [stickerQuery, setStickerQuery] = useState('')
  const [changeNote, setChangeNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [draftPreviewed, setDraftPreviewed] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [tuneOpen, setTuneOpen] = useState(false)
  const importRef = useRef<HTMLInputElement>(null)
  const draftPreviewGeneration = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  const applyDetail = (value: StudioUniversalDetail) => {
    setDetail(value)
    setConfiguration(structuredClone(value.configuration))
    setContent(structuredClone(value.content))
  }

  const renderPreview = async (value: StudioUniversalDetail) => {
    draftPreviewGeneration.current += 1
    const blob = await api.postMedia(
      '/api/v1/studio/preview', { state_sha256: value.state_sha256 },
      'image/png', { deadlineMs: 90_000 },
    )
    setPreviewUrl(URL.createObjectURL(blob))
    setPreviewError('')
    setPreviewBusy(false)
    setDraftPreviewed(false)
  }

  const load = async () => {
    setBusy(true)
    setError('')
    try {
      const value = await api.get<StudioUniversalDetail>('/api/v1/studio', { deadlineMs: 60_000 })
      applyDetail(value)
      try {
        await renderPreview(value)
      } catch (cause) {
        setError((cause as Error).message)
      }
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { void load() }, [api])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  useEffect(() => {
    const generation = ++draftPreviewGeneration.current
    if (!detail || !configuration || !content || busy) {
      setPreviewBusy(false)
      return
    }
    const normalizedContent = normalizedPreviewContent(content)
    const matchesPersisted = (
      JSON.stringify(configuration) === JSON.stringify(detail.configuration)
      && JSON.stringify(normalizedContent) === JSON.stringify(detail.content)
    )
    if (matchesPersisted) {
      setPreviewBusy(false)
      setPreviewError('')
      setDraftPreviewed(false)
      return
    }
    if (!normalizedContent.hero_title.trim() || !normalizedContent.supporting_text.trim() || !normalizedContent.cta.trim()) {
      setPreviewBusy(false)
      setPreviewError(tr(
        'Complete the title, supporting text, and CTA to refresh the preview.',
        'Заповніть заголовок, пояснення та CTA, щоб оновити прев’ю.',
      ))
      return
    }
    setPreviewBusy(true)
    setPreviewError('')
    setDraftPreviewed(false)
    const timer = window.setTimeout(async () => {
      try {
        const blob = await api.postMedia('/api/v1/studio/preview', {
          state_sha256: detail.state_sha256,
          configuration,
          content: normalizedContent,
        }, 'image/png', { deadlineMs: 90_000 })
        if (draftPreviewGeneration.current !== generation) return
        setPreviewUrl(URL.createObjectURL(blob))
        setDraftPreviewed(true)
      } catch (cause) {
        if (draftPreviewGeneration.current !== generation) return
        setPreviewError((cause as Error).message)
      } finally {
        if (draftPreviewGeneration.current === generation) setPreviewBusy(false)
      }
    }, 180)
    return () => window.clearTimeout(timer)
  }, [api, busy, configuration, content, detail, language])

  const patchConfig = <K extends keyof StudioUniversalConfiguration>(
    group: K, patch: Partial<StudioUniversalConfiguration[K]>,
  ) => setConfiguration((current) => current ? ({
    ...current,
    [group]: { ...(current[group] as object), ...patch },
  }) as StudioUniversalConfiguration : current)

  const saveConfiguration = async (
    nextConfiguration = configuration, nextContent = content,
  ) => {
    if (!detail || !nextConfiguration || !nextContent) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const normalizedContent = normalizedPreviewContent(nextContent)
      const value = await api.post<StudioUniversalDetail>('/api/v1/studio/configuration', {
        base_sha256: detail.state_sha256,
        configuration: nextConfiguration,
        content: normalizedContent,
      }, { deadlineMs: 60_000 })
      applyDetail(value)
      await renderPreview(value)
      setNotice(tr('Studio setup saved.', 'Налаштування Студії збережено.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const uploadAsset = async (slot: string, file: File) => {
    if (!detail) return
    const asset = detail.assets.find((item) => item.slot === slot)
    if (!asset?.allowed_mime_types.includes(file.type)) {
      setError(tr(`Unsupported file type for ${slot}.`, `Непідтримуваний тип файлу для ${slot}.`))
      return
    }
    setBusy(true)
    setError('')
    try {
      const value = await api.post<StudioUniversalDetail>(`/api/v1/studio/assets/${slot}`, {
        base_sha256: detail.state_sha256,
        mime_type: file.type,
        bytes_base64: await fileAsBase64(file),
      }, { deadlineMs: 90_000 })
      applyDetail(value)
      try { await renderPreview(value) } catch { /* Disabled optional slots need no immediate render. */ }
      setNotice(tr(`${slot} saved.`, `${slot} збережено.`))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const sourcePexels = async (slot: 'background_image' | 'sticker_object', query: string) => {
    if (!detail) return
    setBusy(true)
    setError('')
    try {
      const value = await api.post<StudioUniversalDetail>('/api/v1/studio/pexels', {
        base_sha256: detail.state_sha256,
        slot,
        query,
        isolate: slot === 'sticker_object',
      }, { deadlineMs: 90_000 })
      applyDetail(value)
      await renderPreview(value)
      setNotice(tr('Pexels asset sourced with provenance and rendered.', 'Ресурс Pexels отримано з походженням і відрендерено.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const importConfiguration = async (file: File) => {
    if (!detail) return
    setBusy(true)
    setError('')
    try {
      const value = JSON.parse(await file.text()) as {
        configuration?: StudioUniversalConfiguration
        content?: StudioUniversalContent
      }
      if (!value.configuration || !value.content) throw new Error(tr(
        'Import requires configuration and content objects.',
        'Імпорт потребує об’єкти configuration і content.',
      ))
      await saveConfiguration(value.configuration, value.content)
    } catch (cause) {
      setError((cause as Error).message)
      setBusy(false)
    }
  }

  const approve = async () => {
    if (!detail || !changeNote.trim()) return
    setBusy(true)
    setError('')
    try {
      const value = await api.post<StudioUniversalDetail>('/api/v1/studio/approve', {
        state_sha256: detail.state_sha256,
        change_note: changeNote.trim(),
      }, { deadlineMs: 90_000 })
      applyDetail(value)
      setChangeNote('')
      setNotice(tr('Immutable creative and configuration version saved.', 'Незмінну версію креативу й конфігурації збережено.'))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const showVersion = async (version: number, digest: string) => {
    setBusy(true)
    setError('')
    try {
      const blob = await api.media(`/api/v1/studio/versions/${version}/render`, 'image/png', digest)
      setPreviewUrl(URL.createObjectURL(blob))
      setNotice(tr(`Showing immutable version ${version}.`, `Показано незмінну версію ${version}.`))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!detail || !configuration || !content) {
    return error
      ? <ErrorState message={error} retry={() => void load()} language={language} />
      : <Loading language={language} />
  }

  const setBullet = (index: number, value: string) => setContent((current) => {
    if (!current) return current
    const bullets = [...current.bullets]
    while (bullets.length <= index) bullets.push('')
    bullets[index] = value
    return { ...current, bullets }
  })
  const stickerAvailable = detail.assets.some((asset) => asset.slot === 'sticker_object' && asset.available)
  const logoAvailable = detail.assets.some((asset) => asset.slot === 'logo' && asset.available)

  return <div className="studio-page universal-studio-page">
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}

    <section className="studio-commandbar universal-commandbar" aria-label={tr('Universal Studio controls', 'Керування універсальною Студією')}>
      <div><small>{tr('FIXED STRUCTURE', 'ФІКСОВАНА СТРУКТУРА')}</small><strong>universal_ad · v{detail.catalog.template_version}</strong></div>
      {tuneMode && <button className="secondary studio-tune-trigger" disabled={busy} onClick={() => setTuneOpen(true)}><WandSparkles />{tr('Feedback & iterations', 'Відгук та ітерації')}</button>}
      <button className="secondary" disabled={busy} onClick={() => importRef.current?.click()}><Upload />{tr('Import config', 'Імпорт конфігурації')}</button>
      <input ref={importRef} className="visually-hidden" type="file" accept="application/json,.json" onChange={(event) => {
        const file = event.target.files?.[0]
        if (file) void importConfiguration(file)
        event.currentTarget.value = ''
      }} />
      <button className="secondary" onClick={() => downloadJson('universal_ad_configuration.json', {
        schema: 'ptw.studio.universal-ad-export.v1', configuration, content,
      })}><Download />{tr('Export config', 'Експорт конфігурації')}</button>
      <button className="primary" disabled={busy} onClick={() => void saveConfiguration()}><Save />{tr('Save setup', 'Зберегти налаштування')}</button>
    </section>

    <div className="studio-meta">
      <span>{detail.catalog.semantic_roles.length} {tr('stable semantic roles', 'сталих семантичних ролей')}</span>
      <code title={detail.state_sha256}>{detail.state_sha256.slice(0, 12)}</code>
      {busy && <span><RefreshCcw className="spin" /> {tr('Working…', 'Обробка…')}</span>}
      {previewBusy && <span><RefreshCcw className="spin" /> {tr('Updating live preview…', 'Оновлення живого прев’ю…')}</span>}
      {!previewBusy && draftPreviewed && <span className="studio-live-state">{tr('Live preview up to date', 'Живе прев’ю оновлено')}</span>}
      {previewError && <span className="studio-preview-error">{previewError}</span>}
    </div>

    <section className="panel universal-component-dock" aria-labelledby="studio-components-title">
      <header>
        <div><small>{tr('CREATIVE COMPONENTS', 'КОМПОНЕНТИ КРЕАТИВУ')}</small><h2 id="studio-components-title">{tr('Build the composition at a glance', 'Керуйте композицією з одного погляду')}</h2></div>
        <p>{tr('Required roles stay visible. Toggle optional roles here and judge the result immediately in the live preview.', 'Обов’язкові ролі завжди видимі. Перемикайте необов’язкові ролі тут і одразу оцінюйте результат у живому прев’ю.')}</p>
      </header>
      <div className="universal-component-grid">
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Background', 'Фон')}</strong><small>{tr('Mood & contrast', 'Настрій і контраст')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Headline', 'Заголовок')}</strong><small>{tr('Primary hook', 'Головний хук')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>{tr('Supporting copy', 'Пояснення')}</strong><small>{tr('Reason to care', 'Причина зупинитись')}</small></div>
        <div className="universal-component-card is-required"><span>{tr('ALWAYS ON', 'ЗАВЖДИ')}</span><strong>CTA</strong><small>{tr('Next action', 'Наступна дія')}</small></div>
        <label className={`universal-component-card is-toggle ${configuration.bullets.enabled ? 'is-active' : ''}`}>
          <input aria-label="Enable bullets" type="checkbox" checked={configuration.bullets.enabled} onChange={(event) => patchConfig('bullets', { enabled: event.target.checked })} />
          <span>{tr('OPTIONAL', 'ОПЦІЙНО')}</span><strong>{tr('Benefits', 'Переваги')}</strong><small>{configuration.bullets.enabled ? tr('Visible', 'Видимі') : tr('Hidden', 'Приховані')}</small><b className="universal-component-switch" aria-hidden="true"><i /></b>
        </label>
        <label className={`universal-component-card is-toggle ${configuration.sticker.enabled ? 'is-active' : ''} ${!stickerAvailable ? 'is-unavailable' : ''}`}>
          <input aria-label="Enable sticker" type="checkbox" checked={configuration.sticker.enabled} disabled={!stickerAvailable && !configuration.sticker.enabled} onChange={(event) => patchConfig('sticker', { enabled: event.target.checked })} />
          <span>{tr('OPTIONAL', 'ОПЦІЙНО')}</span><strong>{tr('Sticker', 'Стікер')}</strong><small>{!stickerAvailable ? tr('Upload asset first', 'Спочатку додайте ресурс') : configuration.sticker.enabled ? tr('Visible', 'Видимий') : tr('Hidden', 'Прихований')}</small><b className="universal-component-switch" aria-hidden="true"><i /></b>
        </label>
        <label className={`universal-component-card is-toggle ${configuration.logo.enabled ? 'is-active' : ''} ${!logoAvailable ? 'is-unavailable' : ''}`}>
          <input aria-label="Enable logo" type="checkbox" checked={configuration.logo.enabled} disabled={!logoAvailable && !configuration.logo.enabled} onChange={(event) => patchConfig('logo', { enabled: event.target.checked })} />
          <span>{tr('OPTIONAL', 'ОПЦІЙНО')}</span><strong>{tr('Logo', 'Логотип')}</strong><small>{!logoAvailable ? tr('Upload asset first', 'Спочатку додайте ресурс') : configuration.logo.enabled ? tr('Visible', 'Видимий') : tr('Hidden', 'Прихований')}</small><b className="universal-component-switch" aria-hidden="true"><i /></b>
        </label>
      </div>
    </section>

    <section className="universal-studio-workspace">
      <main className="studio-canvas-panel universal-canvas-panel">
        <header><div><small>{tr('LIVE STUDIO RENDER', 'ЖИВИЙ РЕНДЕР СТУДІЇ')}</small><h2>{tr('Every control updates this creative', 'Кожне налаштування оновлює цей креатив')}</h2></div><span className="studio-live-badge">{tr('LIVE PREVIEW', 'ЖИВЕ ПРЕВ’Ю')}</span></header>
        <div className={`studio-preview-feedback ${previewError ? 'is-error' : ''}`} aria-live="polite">
          {previewBusy && <><RefreshCcw className="spin" /> {tr('Rendering your changes…', 'Рендеримо ваші зміни…')}</>}
          {!previewBusy && previewError && <>{tr('Preview could not update:', 'Не вдалося оновити прев’ю:')} {previewError}</>}
          {!previewBusy && !previewError && draftPreviewed && <>{tr('Preview matches your unsaved changes', 'Прев’ю відповідає незбереженим змінам')}</>}
          {!previewBusy && !previewError && !draftPreviewed && <>{tr('Preview matches the saved setup', 'Прев’ю відповідає збереженим налаштуванням')}</>}
        </div>
        <div className="studio-preview-grid">
          <figure aria-busy={previewBusy}>{previewUrl
            ? <img src={previewUrl} alt={tr('Current universal advertising creative', 'Поточний універсальний рекламний креатив')} />
            : <div className="studio-preview-empty"><ImagePlus /><span>{tr('Render unavailable', 'Рендер недоступний')}</span></div>}
          </figure>
        </div>
      </main>

      <aside className="universal-controls">
        <section className="panel universal-section">
          <small>{tr('SEMANTIC CONTENT', 'СЕМАНТИЧНИЙ ВМІСТ')}</small><h2>{tr('Compact ad message', 'Компактне рекламне повідомлення')}</h2>
          <label><span>{tr('Hero Title', 'Головний заголовок')}</span><textarea aria-label="Hero Title" rows={3} value={content.hero_title} onChange={(event) => setContent({ ...content, hero_title: event.target.value })} /></label>
          <label><span>{tr('Supporting Text', 'Пояснювальний текст')}</span><textarea aria-label="Supporting Text" rows={3} value={content.supporting_text} onChange={(event) => setContent({ ...content, supporting_text: event.target.value })} /></label>
          <label><span>CTA</span><input aria-label="CTA" value={content.cta} onChange={(event) => setContent({ ...content, cta: event.target.value })} /></label>
          {configuration.bullets.enabled && <div className="universal-bullets">{[0, 1, 2].map((index) => <input key={index} aria-label={`Bullet ${index + 1}`} placeholder={`${tr('Bullet', 'Пункт')} ${index + 1}`} value={content.bullets[index] || ''} onChange={(event) => setBullet(index, event.target.value)} />)}</div>}
          {!configuration.bullets.enabled && <p className="universal-section-note">{tr('Benefits are hidden. Enable that component above when the message needs scannable proof points.', 'Переваги приховані. Увімкніть цей компонент вище, коли повідомленню потрібні короткі докази.')}</p>}
        </section>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('BACKGROUND', 'ФОН')}</small><strong>{tr('Mood and contrast', 'Настрій і контраст')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body"><div className="universal-field-grid">
            <label><span>{tr('Mode', 'Режим')}</span><select aria-label="Background mode" value={configuration.background.mode} onChange={(event) => patchConfig('background', { mode: event.target.value as StudioUniversalConfiguration['background']['mode'] })}><option value="solid">solid</option><option value="texture">texture</option><option value="image">image</option></select></label>
            <label><span>{tr('Base color', 'Базовий колір')}</span><input aria-label="Background color" type="color" value={configuration.background.color} onChange={(event) => patchConfig('background', { color: event.target.value })} /></label>
            {configuration.background.mode === 'texture' && <label><span>{tr('Texture', 'Текстура')}</span><select value={configuration.background.texture} onChange={(event) => patchConfig('background', { texture: event.target.value as 'paper' | 'grain' })}><option value="paper">paper</option><option value="grain">grain</option></select></label>}
            {configuration.background.mode === 'image' && <>
              <label><span>{tr('Image layout', 'Розміщення зображення')}</span><select value={configuration.background.image_layout} onChange={(event) => patchConfig('background', { image_layout: event.target.value as StudioUniversalConfiguration['background']['image_layout'] })}>{['full', 'left', 'right', 'top', 'bottom'].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label><span>{tr('Fit', 'Вписування')}</span><select value={configuration.background.image_fit} onChange={(event) => patchConfig('background', { image_fit: event.target.value as 'cover' | 'contain' })}><option>cover</option><option>contain</option></select></label>
              <NumberField label="Focal X" value={configuration.background.focal_x} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { focal_x: value })} />
              <NumberField label="Focal Y" value={configuration.background.focal_y} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { focal_y: value })} />
            </>}
            <label><span>{tr('Overlay', 'Накладення')}</span><input type="color" value={configuration.background.overlay_color} onChange={(event) => patchConfig('background', { overlay_color: event.target.value })} /></label>
            <NumberField label="Overlay opacity" value={configuration.background.overlay_opacity} min={0} max={0.85} step={0.05} onChange={(value) => patchConfig('background', { overlay_opacity: value })} />
          </div></div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('HIERARCHY & CTA', 'ІЄРАРХІЯ ТА CTA')}</small><strong>{tr('Type, layout and action', 'Типографіка, макет і дія')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body"><div className="universal-field-grid">
            <label><span>{tr('Font', 'Шрифт')}</span><select aria-label="Font family" value={configuration.typography.font_family} onChange={(event) => patchConfig('typography', { font_family: event.target.value as 'Inter' | 'Roboto Condensed' })}><option>Inter</option><option>Roboto Condensed</option></select></label>
            <label><span>{tr('Alignment', 'Вирівнювання')}</span><select aria-label="Text alignment" value={configuration.typography.alignment} onChange={(event) => patchConfig('typography', { alignment: event.target.value as 'left' | 'center' })}><option>left</option><option>center</option></select></label>
            <NumberField label="Hero size" value={configuration.typography.hero_size} min={64} max={180} onChange={(value) => patchConfig('typography', { hero_size: value })} />
            <NumberField label="Hero weight" value={configuration.typography.hero_weight} min={400} max={900} step={100} onChange={(value) => patchConfig('typography', { hero_weight: value })} />
            <NumberField label="Supporting size" value={configuration.typography.supporting_size} min={22} max={52} onChange={(value) => patchConfig('typography', { supporting_size: value })} />
            <label><span>{tr('Text color', 'Колір тексту')}</span><input type="color" value={configuration.typography.text_color} onChange={(event) => patchConfig('typography', { text_color: event.target.value })} /></label>
            <NumberField label="Content X" value={configuration.layout.content_x} min={48} max={520} onChange={(value) => patchConfig('layout', { content_x: value })} />
            <NumberField label="Content Y" value={configuration.layout.content_y} min={72} max={360} onChange={(value) => patchConfig('layout', { content_y: value })} />
            <NumberField label="Content width" value={configuration.layout.content_width} min={420} max={936} onChange={(value) => patchConfig('layout', { content_width: value })} />
            <NumberField label="Vertical gap" value={configuration.layout.gap} min={8} max={56} onChange={(value) => patchConfig('layout', { gap: value })} />
            <label><span>{tr('CTA background', 'Фон CTA')}</span><input type="color" value={configuration.cta.background_color} onChange={(event) => patchConfig('cta', { background_color: event.target.value })} /></label>
            <label><span>{tr('CTA text', 'Текст CTA')}</span><input type="color" value={configuration.cta.text_color} onChange={(event) => patchConfig('cta', { text_color: event.target.value })} /></label>
            <NumberField label="CTA radius" value={configuration.cta.radius} min={0} max={40} onChange={(value) => patchConfig('cta', { radius: value })} />
          </div></div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('OPTIONAL SETTINGS', 'НАЛАШТУВАННЯ ОПЦІЙ')}</small><strong>{tr('Sticker and logo placement', 'Розміщення стікера й логотипа')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body">
          {configuration.sticker.enabled && <div className="universal-field-grid">
            <label><span>{tr('Position', 'Позиція')}</span><select value={configuration.sticker.position} onChange={(event) => patchConfig('sticker', { position: event.target.value as StudioUniversalConfiguration['sticker']['position'] })}>{['top_left', 'top_right', 'bottom_left', 'bottom_right'].map((item) => <option key={item}>{item}</option>)}</select></label>
            <NumberField label="Sticker rotation" value={configuration.sticker.rotation} min={-18} max={18} onChange={(value) => patchConfig('sticker', { rotation: value })} />
            <NumberField label="Sticker width" value={configuration.sticker.paper_width} min={180} max={480} onChange={(value) => patchConfig('sticker', { paper_width: value })} />
            <NumberField label="Object scale" value={configuration.sticker.object_scale} min={0.45} max={1.25} step={0.05} onChange={(value) => patchConfig('sticker', { object_scale: value })} />
          </div>}
          {configuration.logo.enabled && <div className="universal-field-grid">
            <label><span>{tr('Position', 'Позиція')}</span><select value={configuration.logo.position} onChange={(event) => patchConfig('logo', { position: event.target.value as 'top_left' | 'top_right' })}><option>top_left</option><option>top_right</option></select></label>
            <NumberField label="Logo width" value={configuration.logo.width} min={80} max={280} onChange={(value) => patchConfig('logo', { width: value })} />
          </div>}
          {!configuration.sticker.enabled && !configuration.logo.enabled && <p className="universal-section-note">{tr('Enable Sticker or Logo in the component dock to reveal its placement controls.', 'Увімкніть «Стікер» або «Логотип» у панелі компонентів, щоб побачити налаштування розміщення.')}</p>}
          </div>
        </details>
      </aside>
    </section>

    <section className="panel universal-assets-panel">
      <small>{tr('THREE FIXED ASSET SLOTS', 'ТРИ ФІКСОВАНІ МІСЦЯ ДЛЯ РЕСУРСІВ')}</small><h2>{tr('Background, sticker object, optional logo', 'Фон, об’єкт стікера, необов’язковий логотип')}</h2>
      <div className="studio-asset-list">{detail.assets.map((asset) => <div key={asset.slot}><div><strong>{asset.slot}</strong><span>{asset.available ? `${asset.mime_type} · ${Math.round((asset.byte_count || 0) / 1024)} KB · ${String(asset.source?.origin || 'stored')}` : tr('Optional · not supplied', 'Необов’язково · не надано')}</span></div><label className="secondary"><Upload />{tr('Upload', 'Завантажити')}<input type="file" accept={asset.allowed_mime_types.join(',')} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset(asset.slot, file); event.currentTarget.value = '' }} /></label></div>)}</div>
      <div className="universal-pexels-grid">
        <label><span>{tr('Pexels background query', 'Запит фону Pexels')}</span><input aria-label="Pexels background query" value={backgroundQuery} onChange={(event) => setBackgroundQuery(event.target.value)} /></label>
        <button className="secondary" disabled={busy || !detail.pexels_available || backgroundQuery.trim().length < 2} onClick={() => void sourcePexels('background_image', backgroundQuery)}><Search />{tr('Source background', 'Знайти фон')}</button>
        <label><span>{tr('Pexels sticker object query', 'Запит об’єкта стікера Pexels')}</span><input aria-label="Pexels sticker query" value={stickerQuery} onChange={(event) => setStickerQuery(event.target.value)} /></label>
        <button className="secondary" disabled={busy || !detail.pexels_available || stickerQuery.trim().length < 2} onClick={() => void sourcePexels('sticker_object', stickerQuery)}><Search />{tr('Source & isolate object', 'Знайти й ізолювати об’єкт')}</button>
      </div>
      {!detail.pexels_available && <p className="studio-note">{tr('Pexels is not configured in this local runtime; fixed-slot uploads remain available.', 'Pexels не налаштовано в цьому локальному середовищі; завантаження у фіксовані місця доступні.')}</p>}
    </section>

    <section className="panel studio-approval universal-approval">
      <div><small>{tr('IMMUTABLE EXPERIMENT ASSET', 'НЕЗМІННИЙ РЕСУРС ЕКСПЕРИМЕНТУ')}</small><h2>{tr('Store exact creative + configuration', 'Зберегти точний креатив і конфігурацію')}</h2><p>{tr('Approval stores the rendered PNG, universal configuration, semantic content, asset digests, and internal template digest together.', 'Схвалення разом зберігає PNG, універсальну конфігурацію, семантичний вміст, digest ресурсів і внутрішній digest шаблону.')}</p></div>
      <label><span>{tr('Version note', 'Примітка до версії')}</span><input value={changeNote} onChange={(event) => setChangeNote(event.target.value)} /></label>
      <button className="primary large" disabled={busy || !changeNote.trim()} onClick={() => void approve()}><Check />{tr('Save immutable version', 'Зберегти незмінну версію')}</button>
      {detail.versions.length > 0 && <ol className="universal-version-list">{detail.versions.map((version) => <li key={version.version}><strong>v{version.version}</strong><span>{version.change_note}</span><button className="secondary" onClick={() => void showVersion(version.version, version.render_sha256)}>{tr('View', 'Переглянути')}</button></li>)}</ol>}
    </section>
    {tuneMode && <StudioTuneWizard api={api} language={language} open={tuneOpen} studioPreviewUrl={previewUrl} onClose={() => setTuneOpen(false)} />}
  </div>
}
