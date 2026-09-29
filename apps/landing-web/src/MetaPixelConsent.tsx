import { useEffect, useRef, useState } from 'react'
import { legalUrl } from '../../commander-web/src/landing/LegalLinks'
import { trackMetaPageView } from './metaPixel'
import { usePrivacy } from './privacyPreferences'

export function MetaPixelConsent({ path, language = 'en', track = true }: { path: string; language?: string; track?: boolean }) {
  const { preferences, open, close, decide } = usePrivacy()
  const [analytics, setAnalytics] = useState(false), [marketing, setMarketing] = useState(false)
  const panel = useRef<HTMLElement>(null)
  const uk = language === 'uk'
  useEffect(() => {
    if (preferences?.marketing && track) trackMetaPageView(path)
  }, [preferences?.marketing, path, track])
  useEffect(() => {
    if (open) { setAnalytics(preferences?.analytics || false); setMarketing(preferences?.marketing || false) }
  }, [open, preferences])
  function save(a: boolean, m: boolean) { decide(a, m) }
  return <>
    {open && <aside ref={panel} tabIndex={-1} className="natal-pixel-consent" aria-label={uk ? 'Налаштування вимірювання' : 'Measurement preferences'}>
      <div><strong>{uk ? 'Налаштування вимірювання' : 'Measurement settings'}</strong>
        <p>{uk ? 'Власна аналітика Natal і Meta Pixel працюють автоматично. Тут можна вимкнути кожне вимірювання для цього браузера.' : 'Natal analytics and Meta Pixel run automatically. You can turn either measurement off for this browser here.'}</p>
        <p><a href={legalUrl('privacy', uk ? 'uk' : 'en', '')}>{uk ? 'Політика конфіденційності' : 'Privacy policy'}</a> · <a href={legalUrl('cookies', uk ? 'uk' : 'en', '')}>{uk ? 'Політика cookie' : 'Cookie policy'}</a></p>
        <label><input type="checkbox" checked={analytics} onChange={event => setAnalytics(event.target.checked)} />{uk ? 'Аналітика Natal — перегляди та переходи до контактів' : 'Natal analytics — page views and contact clicks'}</label>
        <label><input type="checkbox" checked={marketing} onChange={event => setMarketing(event.target.checked)} />{uk ? 'Реклама Meta — Pixel, cookie та вимірювання реклами' : 'Meta advertising — Pixel, cookies and ad measurement'}</label>
      </div>
      <div className="natal-pixel-consent__actions">
        <button type="button" onClick={() => save(false, false)}>{uk ? 'Вимкнути вимірювання' : 'Turn measurement off'}</button>
        <button type="button" onClick={() => save(true, true)}>{uk ? 'Увімкнути вимірювання' : 'Turn measurement on'}</button>
        <button type="button" onClick={() => save(analytics, marketing)}>{uk ? 'Зберегти вибір' : 'Save preferences'}</button>
        {preferences && <button type="button" onClick={() => { close() }}>{uk ? 'Закрити' : 'Close'}</button>}
      </div>
    </aside>}
  </>
}
