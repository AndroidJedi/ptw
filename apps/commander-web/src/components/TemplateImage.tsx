import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import type { Language } from '../i18n'
import '../views/TemplatesView.css'

type Preview = { sha256: string }

export function TemplateImage({ api, preview, label, language = 'en' }: { api: ApiClient; preview?: Preview; label: string; language?: Language }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let cancelled = false, objectUrl = ''
    setUrl(''); setError('')
    if (preview) void api.image(`/api/v1/templates/media/${preview.sha256}`, 'image/png', preview.sha256).then(blob => {
      if (cancelled) return
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl)
    }).catch((cause: Error) => { if (!cancelled) setError(cause.message) })
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, preview?.sha256, retry])
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  return <div className="template-image">{url ? <a href={url} target="_blank" rel="noreferrer" aria-label={`${tr('Open full resolution', 'Відкрити повний розмір')}: ${label}`}><img src={url} alt={label} /></a> : error ? <div role="alert"><p>{error}</p><button onClick={() => setRetry(value => value + 1)}>{tr('Retry preview', 'Повторити прев’ю')}</button></div> : <p role="status">{preview ? tr('Loading preview…', 'Завантаження прев’ю…') : tr('Preview is being prepared.', 'Прев’ю готується.')}</p>}</div>
}
