import {
  Check, Download, ImagePlus, RefreshCcw, Save, Search, Upload, WandSparkles,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { StudioTuneWizard } from '../components/studio/StudioTuneWizard'
import { ErrorState, Loading } from '../components/State'
import { translate, type Language } from '../i18n'
import type {
  StudioUniversalComponentSettings, StudioUniversalConfiguration, StudioUniversalContent,
  StudioUniversalDetail, StudioUniversalFontFamily,
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
  const [draft, setDraft] = useState(String(value))
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (!editing) setDraft(String(value))
  }, [editing, value])

  const parsedDraft = draft.trim() === '' ? Number.NaN : Number(draft)
  const draftIsValid = Number.isFinite(parsedDraft)
    && parsedDraft >= min && parsedDraft <= max
    && (step !== 1 || Number.isInteger(parsedDraft))

  const finishEditing = () => {
    setEditing(false)
    if (!Number.isFinite(parsedDraft)) {
      setDraft(String(value))
      return
    }
    const bounded = Math.min(max, Math.max(min, parsedDraft))
    const normalized = step === 1 ? Math.round(bounded) : bounded
    setDraft(String(normalized))
    if (normalized !== value) onChange(normalized)
  }

  return <label><span>{label}</span><input
    aria-label={label} aria-invalid={editing && !draftIsValid}
    type="number" value={draft} min={min} max={max} step={step}
    onFocus={() => setEditing(true)}
    onChange={(event) => {
      const nextDraft = event.target.value
      setDraft(nextDraft)
      const nextValue = nextDraft.trim() === '' ? Number.NaN : Number(nextDraft)
      if (
        Number.isFinite(nextValue) && nextValue >= min && nextValue <= max
        && (step !== 1 || Number.isInteger(nextValue))
      ) onChange(nextValue)
    }}
    onBlur={finishEditing}
    onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }}
  /></label>
}

function ColorField({ label, value, onChange }: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return <label className="universal-color-field">
    <span>{label}<code>{value.toUpperCase()}</code></span>
    <input aria-label={label} type="color" value={value} onChange={(event) => onChange(event.target.value)} />
  </label>
}

function RangeField({ label, value, min, max, step, onChange }: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
}) {
  return <label className="universal-range-field">
    <span>{label}<code>{Math.round(value * 100)}%</code></span>
    <input
      aria-label={label} type="range" value={value} min={min} max={max} step={step}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  </label>
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
  const previewMode = useRef<'saved' | 'draft'>('saved')
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
    previewMode.current = 'saved'
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
      if (previewMode.current === 'draft') {
        setPreviewBusy(true)
        setPreviewError('')
        const timer = window.setTimeout(async () => {
          try {
            const blob = await api.postMedia(
              '/api/v1/studio/preview', { state_sha256: detail.state_sha256 },
              'image/png', { deadlineMs: 90_000 },
            )
            if (draftPreviewGeneration.current !== generation) return
            setPreviewUrl(URL.createObjectURL(blob))
            previewMode.current = 'saved'
            setDraftPreviewed(false)
          } catch (cause) {
            if (draftPreviewGeneration.current !== generation) return
            setPreviewError((cause as Error).message)
          } finally {
            if (draftPreviewGeneration.current === generation) setPreviewBusy(false)
          }
        }, 180)
        return () => window.clearTimeout(timer)
      }
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
        previewMode.current = 'draft'
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
    const draftConfiguration = configuration ? structuredClone(configuration) : null
    const draftContent = content ? structuredClone(content) : null
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
      if (draftConfiguration && draftContent) {
        const nextConfiguration = slot === 'background_image' ? {
          ...draftConfiguration,
          background: { ...draftConfiguration.background, mode: 'image' as const },
        } : slot === 'logo' ? {
          ...draftConfiguration,
          logo: { ...draftConfiguration.logo, enabled: true },
        } : draftConfiguration
        setDetail(value)
        setConfiguration(nextConfiguration)
        setContent(draftContent)
      } else {
        applyDetail(value)
      }
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

  const exportConfiguration = async () => {
    if (!detail || !configuration || !content) return
    setBusy(true)
    setError('')
    try {
      const normalizedContent = normalizedPreviewContent(content)
      const componentSettings = await api.post<StudioUniversalComponentSettings>(
        '/api/v1/studio/component-settings', {
          state_sha256: detail.state_sha256,
          configuration,
          content: normalizedContent,
        },
      )
      downloadJson('universal_ad_configuration.json', {
        schema: 'ptw.studio.universal-ad-export.v4',
        template_id: detail.catalog.template_id,
        template_version: detail.catalog.template_version,
        base_state_sha256: detail.state_sha256,
        catalog_sha256: detail.catalog.sha256,
        component_settings: componentSettings,
        configuration,
        content: normalizedContent,
      })
      setNotice(tr(
        'Configuration and component ID metadata exported.',
        'Конфігурацію та метадані ID компонентів експортовано.',
      ))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
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
  const backgroundAsset = detail.assets.find((asset) => asset.slot === 'background_image')
  const logoAsset = detail.assets.find((asset) => asset.slot === 'logo')
  const fontOptions: Array<{ value: StudioUniversalFontFamily; label: string }> = [
    { value: 'Inter', label: tr('Inter — neutral & clear', 'Inter — нейтральний і чіткий') },
    { value: 'Manrope', label: tr('Manrope — friendly & modern', 'Manrope — дружній і сучасний') },
    { value: 'Oswald', label: tr('Oswald — bold & urgent', 'Oswald — сміливий і динамічний') },
    { value: 'Cormorant Garamond', label: tr('Cormorant Garamond — editorial & premium', 'Cormorant Garamond — редакційний і преміальний') },
  ]

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
      <button className="secondary" disabled={busy} onClick={() => void exportConfiguration()}><Download />{tr('Export config + IDs', 'Експорт конфігурації + ID')}</button>
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
          {configuration.bullets.enabled && <div className="universal-bullets">
            <label><span>{tr('Bullet style', 'Стиль маркера')}</span><select
              aria-label="Bullet style" value={configuration.bullets.style}
              onChange={(event) => patchConfig('bullets', { style: event.target.value as StudioUniversalConfiguration['bullets']['style'] })}
            >
              <option value="check">{tr('Check mark', 'Позначка')}</option>
              <option value="circle">{tr('Filled circle', 'Заповнене коло')}</option>
              <option value="circle_outline">{tr('Outlined circle', 'Контурне коло')}</option>
            </select></label>
            {[0, 1, 2].map((index) => <input key={index} aria-label={`Bullet ${index + 1}`} placeholder={`${tr('Bullet', 'Пункт')} ${index + 1}`} value={content.bullets[index] || ''} onChange={(event) => setBullet(index, event.target.value)} />)}
          </div>}
          {!configuration.bullets.enabled && <p className="universal-section-note">{tr('Benefits are hidden. Enable that component above when the message needs scannable proof points.', 'Переваги приховані. Увімкніть цей компонент вище, коли повідомленню потрібні короткі докази.')}</p>}
        </section>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('BACKGROUND', 'ФОН')}</small><strong>{tr('Mood and contrast', 'Настрій і контраст')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body"><div className="universal-field-grid">
            <label><span>{tr('Mode', 'Режим')}</span><select aria-label="Background mode" value={configuration.background.mode} onChange={(event) => patchConfig('background', { mode: event.target.value as StudioUniversalConfiguration['background']['mode'] })}><option value="solid">solid</option><option value="texture">texture</option><option value="image">image</option></select></label>
            <ColorField label={tr('Background color', 'Базовий колір')} value={configuration.background.color} onChange={(value) => patchConfig('background', { color: value })} />
            {configuration.background.mode === 'texture' && <>
              <label><span>{tr('Texture', 'Текстура')}</span><select aria-label="Texture" value={configuration.background.texture} onChange={(event) => patchConfig('background', { texture: event.target.value as StudioUniversalConfiguration['background']['texture'] })}>
                {detail.catalog.variation.texture_presets.map((texture) => <option key={texture} value={texture}>{texture}</option>)}
              </select></label>
              <RangeField label={tr('Texture intensity', 'Інтенсивність текстури')} value={configuration.background.texture_intensity} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { texture_intensity: value })} />
            </>}
            {configuration.background.mode === 'image' && <>
              <label><span>{tr('Image layout', 'Розміщення зображення')}</span><select value={configuration.background.image_layout} onChange={(event) => patchConfig('background', { image_layout: event.target.value as StudioUniversalConfiguration['background']['image_layout'] })}>{['full', 'left', 'right', 'top', 'bottom'].map((item) => <option key={item}>{item}</option>)}</select></label>
              {configuration.background.image_layout !== 'full' && <label><span>{tr('Image / background mix', 'Співвідношення зображення / фону')}</span><select
                aria-label="Image background mix" value={configuration.background.image_percent}
                onChange={(event) => patchConfig('background', { image_percent: Number(event.target.value) as 25 | 75 })}
              ><option value={75}>75% image · 25% background</option><option value={25}>25% image · 75% background</option></select></label>}
              <label><span>{tr('Fit', 'Вписування')}</span><select value={configuration.background.image_fit} onChange={(event) => patchConfig('background', { image_fit: event.target.value as 'cover' | 'contain' })}><option>cover</option><option>contain</option></select></label>
              <NumberField label="Focal X" value={configuration.background.focal_x} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { focal_x: value })} />
              <NumberField label="Focal Y" value={configuration.background.focal_y} min={0} max={1} step={0.05} onChange={(value) => patchConfig('background', { focal_y: value })} />
              <div className="universal-inline-upload universal-field-span">
                <div><strong>{tr('Sample image', 'Тестове зображення')}</strong><span>{backgroundAsset?.available ? `${backgroundAsset.mime_type} · ${String(backgroundAsset.source?.origin || 'stored')}` : tr('No image supplied', 'Зображення не додано')}</span></div>
                <label className="secondary"><Upload />{tr('Upload sample', 'Завантажити приклад')}<input
                  aria-label="Upload sample background image" type="file"
                  accept={backgroundAsset?.allowed_mime_types.join(',') || 'image/jpeg,image/png,image/webp'}
                  onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset('background_image', file); event.currentTarget.value = '' }}
                /></label>
              </div>
            </>}
            <ColorField label={tr('Overlay color', 'Колір накладення')} value={configuration.background.overlay_color} onChange={(value) => patchConfig('background', { overlay_color: value })} />
            <RangeField label={tr('Overlay opacity', 'Прозорість накладення')} value={configuration.background.overlay_opacity} min={0} max={0.85} step={0.05} onChange={(value) => patchConfig('background', { overlay_opacity: value })} />
          </div></div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('LOGO', 'ЛОГОТИП')}</small><strong>{tr('Brand mark and background', 'Знак бренду та фон')}</strong></span><em>{configuration.logo.enabled ? tr('VISIBLE', 'ВИДИМИЙ') : tr('HIDDEN', 'ПРИХОВАНИЙ')}</em></summary>
          <div className="universal-section-body">
            <div className="universal-inline-upload">
              <div><strong>{tr('Logo asset', 'Файл логотипа')}</strong><span>{logoAsset?.available ? `${logoAsset.mime_type} · ${String(logoAsset.source?.origin || 'stored')}` : tr('No logo supplied', 'Логотип не додано')}</span></div>
              <label className="secondary"><Upload />{tr('Replace logo', 'Замінити логотип')}<input
                aria-label="Upload logo" type="file"
                accept={logoAsset?.allowed_mime_types.join(',') || 'image/png,image/webp'}
                onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset('logo', file); event.currentTarget.value = '' }}
              /></label>
            </div>
            <div className="universal-field-grid">
              <label className="universal-toggle universal-field-span"><input
                aria-label="Show logo" type="checkbox" checked={configuration.logo.enabled}
                disabled={!logoAvailable && !configuration.logo.enabled}
                onChange={(event) => patchConfig('logo', { enabled: event.target.checked })}
              />{tr('Show logo in the creative', 'Показувати логотип у креативі')}</label>
              {configuration.logo.enabled && <>
                <label className="universal-toggle universal-field-span"><input
                  aria-label="Show logo background" type="checkbox"
                  checked={configuration.logo.background_enabled}
                  onChange={(event) => patchConfig('logo', { background_enabled: event.target.checked })}
                />{tr('Show background behind logo', 'Показувати фон під логотипом')}</label>
                {configuration.logo.background_enabled && <ColorField
                  label={tr('Logo background color', 'Колір фону логотипа')}
                  value={configuration.logo.background_color}
                  onChange={(value) => patchConfig('logo', { background_color: value })}
                />}
                <label><span>{tr('Logo position', 'Позиція логотипа')}</span><select
                  aria-label="Logo position" value={configuration.logo.position}
                  onChange={(event) => patchConfig('logo', { position: event.target.value as StudioUniversalConfiguration['logo']['position'] })}
                ><option value="top_left">{tr('Top left', 'Зверху ліворуч')}</option><option value="top_right">{tr('Top right', 'Зверху праворуч')}</option></select></label>
                <NumberField label="Logo width" value={configuration.logo.width} min={80} max={280} onChange={(value) => patchConfig('logo', { width: value })} />
              </>}
            </div>
            {!logoAvailable && <p className="universal-section-note">{tr('Upload a PNG or WebP logo to make this component available.', 'Завантажте логотип PNG або WebP, щоб зробити цей компонент доступним.')}</p>}
          </div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('HIERARCHY & CTA', 'ІЄРАРХІЯ ТА CTA')}</small><strong>{tr('Type, layout and action', 'Типографіка, макет і дія')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body"><div className="universal-field-grid">
            <label><span>{tr('Main font mood', 'Настрій основного шрифту')}</span><select aria-label="Font family" value={configuration.typography.font_family} onChange={(event) => patchConfig('typography', { font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <label><span>{tr('Benefits font mood', 'Настрій шрифту переваг')}</span><select aria-label="Benefits font family" value={configuration.typography.benefits_font_family} onChange={(event) => patchConfig('typography', { benefits_font_family: event.target.value as StudioUniversalFontFamily })}>
              {fontOptions.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
            </select></label>
            <label><span>{tr('Alignment', 'Вирівнювання')}</span><select aria-label="Text alignment" value={configuration.typography.alignment} onChange={(event) => patchConfig('typography', { alignment: event.target.value as 'left' | 'center' })}><option>left</option><option>center</option></select></label>
            <NumberField label="Hero size" value={configuration.typography.hero_size} min={64} max={180} onChange={(value) => patchConfig('typography', { hero_size: value })} />
            <NumberField label="Hero weight" value={configuration.typography.hero_weight} min={400} max={900} step={100} onChange={(value) => patchConfig('typography', { hero_weight: value })} />
            <NumberField label="Supporting size" value={configuration.typography.supporting_size} min={22} max={52} onChange={(value) => patchConfig('typography', { supporting_size: value })} />
            <ColorField label={tr('Text color', 'Колір тексту')} value={configuration.typography.text_color} onChange={(value) => patchConfig('typography', { text_color: value })} />
            <NumberField label="Content X" value={configuration.layout.content_x} min={48} max={520} onChange={(value) => patchConfig('layout', { content_x: value })} />
            <NumberField label="Content Y" value={configuration.layout.content_y} min={72} max={360} onChange={(value) => patchConfig('layout', { content_y: value })} />
            <NumberField label="Content width" value={configuration.layout.content_width} min={420} max={936} onChange={(value) => patchConfig('layout', { content_width: value })} />
            <NumberField label="Vertical gap" value={configuration.layout.gap} min={8} max={56} onChange={(value) => patchConfig('layout', { gap: value })} />
            <label><span>{tr('CTA style', 'Стиль CTA')}</span><select aria-label="CTA style" value={configuration.cta.style} onChange={(event) => patchConfig('cta', { style: event.target.value as StudioUniversalConfiguration['cta']['style'] })}>
              <option value="filled">filled</option><option value="gradient">gradient</option><option value="reverse">reverse</option><option value="link">link</option><option value="outlined">outlined</option>
            </select></label>
            <label><span>{tr('CTA placement', 'Розміщення CTA')}</span><select aria-label="CTA placement" value={configuration.cta.position} onChange={(event) => patchConfig('cta', { position: event.target.value as StudioUniversalConfiguration['cta']['position'] })}>
              <option value="below_text">{tr('Below text', 'Під текстом')}</option>
              <option value="bottom_left">{tr('Bottom left', 'Знизу ліворуч')}</option>
              <option value="bottom_right">{tr('Bottom right', 'Знизу праворуч')}</option>
            </select></label>
            <ColorField label={tr('CTA background color', 'Колір фону CTA')} value={configuration.cta.background_color} onChange={(value) => patchConfig('cta', { background_color: value })} />
            <ColorField label={tr('CTA text color', 'Колір тексту CTA')} value={configuration.cta.text_color} onChange={(value) => patchConfig('cta', { text_color: value })} />
            <NumberField label="CTA radius" value={configuration.cta.radius} min={0} max={40} onChange={(value) => patchConfig('cta', { radius: value })} />
          </div></div>
        </details>

        <details className="panel universal-section universal-disclosure">
          <summary><span><small>{tr('OPTIONAL SETTINGS', 'НАЛАШТУВАННЯ ОПЦІЙ')}</small><strong>{tr('Sticker placement', 'Розміщення стікера')}</strong></span><em>{tr('EDIT', 'ЗМІНИТИ')}</em></summary>
          <div className="universal-section-body">
          {configuration.sticker.enabled && <div className="universal-field-grid">
            <label><span>{tr('Position', 'Позиція')}</span><select aria-label="Sticker position" value={configuration.sticker.position} onChange={(event) => patchConfig('sticker', { position: event.target.value as StudioUniversalConfiguration['sticker']['position'] })}>
              <option value="top_left">{tr('Top left', 'Зверху ліворуч')}</option><option value="top_right">{tr('Top right', 'Зверху праворуч')}</option>
              <option value="bottom_left">{tr('Bottom left', 'Знизу ліворуч')}</option><option value="bottom_right">{tr('Bottom right', 'Знизу праворуч')}</option>
              <option value="right_edge">{tr('Sticks from right', 'Виступає справа')}</option><option value="bottom_edge">{tr('Sticks from bottom', 'Виступає знизу')}</option>
              <option value="bullet_list">{tr('Sticks to benefits', 'Кріпиться до переваг')}</option><option value="hero_title">{tr('Sticks to hero title', 'Кріпиться до заголовка')}</option>
              <option value="cta">{tr('Sticks to CTA', 'Кріпиться до CTA')}</option>
            </select></label>
            <NumberField label="Sticker rotation" value={configuration.sticker.rotation} min={-18} max={18} onChange={(value) => patchConfig('sticker', { rotation: value })} />
            <NumberField label="Sticker width" value={configuration.sticker.width} min={120} max={720} onChange={(value) => patchConfig('sticker', { width: value })} />
            <NumberField label="Object scale" value={configuration.sticker.object_scale} min={0.35} max={1.5} step={0.05} onChange={(value) => patchConfig('sticker', { object_scale: value })} />
            <NumberField label="Adjust from right" value={configuration.sticker.offset_right} min={-720} max={720} onChange={(value) => patchConfig('sticker', { offset_right: value })} />
            <NumberField label="Adjust from bottom" value={configuration.sticker.offset_bottom} min={-720} max={720} onChange={(value) => patchConfig('sticker', { offset_bottom: value })} />
          </div>}
          {!configuration.sticker.enabled && <p className="universal-section-note">{tr('Enable Sticker in the component dock to reveal its placement controls.', 'Увімкніть «Стікер» у панелі компонентів, щоб побачити налаштування розміщення.')}</p>}
          </div>
        </details>
      </aside>
    </section>

    <section className="panel universal-assets-panel">
      <small>{tr('THREE FIXED ASSET SLOTS', 'ТРИ ФІКСОВАНІ МІСЦЯ ДЛЯ РЕСУРСІВ')}</small><h2>{tr('Background, sticker object, logo (Natal by default)', 'Фон, об’єкт стікера, логотип (Natal за замовчуванням)')}</h2>
      <div className="studio-asset-list">{detail.assets.map((asset) => <div key={asset.slot}><div><strong>{asset.slot}</strong><span>{asset.available ? `${asset.mime_type} · ${Math.round((asset.byte_count || 0) / 1024)} KB · ${String(asset.source?.origin || 'stored')}` : tr('Optional · not supplied', 'Необов’язково · не надано')}</span></div><label className="secondary"><Upload />{tr('Upload', 'Завантажити')}<input aria-label={`Upload ${asset.slot} asset`} type="file" accept={asset.allowed_mime_types.join(',')} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset(asset.slot, file); event.currentTarget.value = '' }} /></label></div>)}</div>
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
