import { Check, RefreshCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import type { ContentCreative } from '../types'

function CreativeImage({ api, creative, language }: {
  api: ApiClient
  creative: ContentCreative
  language: Language
}) {
  const [source, setSource] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let objectUrl = ''
    let active = true
    setSource(''); setError('')
    void api.image(
      creative.preview.asset_url,
      creative.preview.mime_type,
      creative.preview.sha256,
    ).then((blob) => {
      if (!active || !(blob instanceof Blob)) return
      objectUrl = URL.createObjectURL(blob)
      setSource(objectUrl)
    }).catch((cause: Error) => { if (active) setError(cause.message) })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [api, creative.creative_id, creative.preview.sha256])

  if (error) return <div className="creative-image-state" role="alert">{error}</div>
  if (!source) return <div className="creative-image-state"><RefreshCcw className="spin" />{translate(language, 'Loading verified render…', 'Завантаження перевіреного рендера…')}</div>
  return <img src={source} alt={creative.document.alt_text} />
}

export function CreativeReviewGrid({
  api, creatives, selectedCreativeId, approvedCreativeId, actionable, onSelect, language,
}: {
  api: ApiClient
  creatives: ContentCreative[]
  selectedCreativeId: string | null
  approvedCreativeId?: string | null
  actionable: boolean
  onSelect: (creativeId: string) => void
  language: Language
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <section className="creative-review" aria-labelledby="creative-review-heading">
    <header>
      <small>{tr('OWNER REVIEW', 'ПЕРЕГЛЯД ВЛАСНИКОМ')}</small>
      <h2 id="creative-review-heading">{tr('Five verified creative directions', 'П’ять перевірених креативних напрямів')}</h2>
      <p>{tr(
        'Select one post to approve or tune. Regenerate all replaces the complete set.',
        'Оберіть один допис для схвалення або налаштування. «Перегенерувати всі» замінює весь набір.',
      )}</p>
    </header>
    <div className="creative-review-grid" role="radiogroup" aria-label={tr('Creative direction', 'Креативний напрям')}>
      {creatives.map((creative) => {
        const selected = creative.creative_id === selectedCreativeId
        const approved = creative.creative_id === approvedCreativeId
        return <button
          type="button"
          role="radio"
          aria-checked={selected}
          className={`creative-review-card${selected ? ' selected' : ''}${approved ? ' approved' : ''}`}
          key={creative.creative_id}
          onClick={() => onSelect(creative.creative_id)}
          disabled={!actionable && !approved}
        >
          <div className="creative-review-image">
            <CreativeImage api={api} creative={creative} language={language} />
            {(selected || approved) && <span><Check />{approved ? tr('Approved', 'Схвалено') : tr('Selected', 'Обрано')}</span>}
          </div>
          <div className="creative-review-copy">
            <small>{creative.slot} · {creative.template_id}</small>
            <strong>{creative.document.headline}</strong>
            <p>{creative.document.caption}</p>
            <code>{creative.creative_id}</code>
          </div>
        </button>
      })}
    </div>
  </section>
}
