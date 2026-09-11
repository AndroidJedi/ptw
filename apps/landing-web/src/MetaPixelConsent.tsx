import { useEffect, useState } from 'react'
import { trackMetaPageView } from './metaPixel'

const STORAGE_KEY = 'natal_meta_pixel_consent_v1'
type Consent = 'accepted' | 'rejected' | 'pending'

function browserStorage(): Storage | undefined {
  try { return window.localStorage || undefined }
  catch { return undefined }
}

function storedConsent(): Consent {
  const value = browserStorage()?.getItem(STORAGE_KEY)
  return value === 'accepted' || value === 'rejected' ? value : 'pending'
}

export function MetaPixelConsent({ path, language = 'en' }: { path: string; language?: string }) {
  const [consent, setConsent] = useState<Consent>(storedConsent)
  const ukrainian = language.toLowerCase().startsWith('uk')

  useEffect(() => {
    if (consent === 'accepted') trackMetaPageView(path)
  }, [consent, path])

  function decide(value: Exclude<Consent, 'pending'>) {
    browserStorage()?.setItem(STORAGE_KEY, value)
    setConsent(value)
  }

  if (consent !== 'pending') return null
  return <aside className="natal-pixel-consent" aria-label={ukrainian ? 'Налаштування аналітики' : 'Analytics preferences'}>
    <div>
      <strong>{ukrainian ? 'Аналітика сайту' : 'Site analytics'}</strong>
      <p>{ukrainian
        ? 'Дозволити Meta Pixel вимірювати перегляди сторінок? Meta може використовувати файли cookie.'
        : 'Allow Meta Pixel to measure page views? Meta may use cookies.'}</p>
    </div>
    <div className="natal-pixel-consent__actions">
      <button type="button" onClick={() => decide('rejected')}>{ukrainian ? 'Відхилити' : 'Reject'}</button>
      <button type="button" className="natal-pixel-consent__accept" onClick={() => decide('accepted')}>{ukrainian ? 'Дозволити' : 'Allow'}</button>
    </div>
  </aside>
}
