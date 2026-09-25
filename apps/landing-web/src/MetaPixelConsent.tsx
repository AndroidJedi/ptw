import { useEffect, useRef, useState } from 'react'
import { legalUrl } from '../../commander-web/src/landing/LegalLinks'
import { trackMetaPageView } from './metaPixel'
import { usePrivacy } from './privacyPreferences'

export function MetaPixelConsent({ path, language = 'en', track = true }: { path: string; language?: string; track?: boolean }) {
  const { preferences, open, show, close, decide } = usePrivacy()
  const [analytics, setAnalytics] = useState(false), [marketing, setMarketing] = useState(false)
  const panel = useRef<HTMLElement>(null), settings = useRef<HTMLButtonElement>(null)
  const uk = language === 'uk'
  useEffect(() => {
    if (preferences?.marketing && track) trackMetaPageView(path)
  }, [preferences?.marketing, path, track])
  useEffect(() => {
    if (open) { setAnalytics(preferences?.analytics || false); setMarketing(preferences?.marketing || false) }
  }, [open, preferences])
  function save(a: boolean, m: boolean) { decide(a, m); settings.current?.focus() }
  return <>
    <div className="natal-privacy-controls"><button ref={settings} type="button" onClick={() => { show(); requestAnimationFrame(() => panel.current?.focus()) }}>{uk ? 'Налаштування cookie' : 'Cookie settings'}</button></div>
    {open && <aside ref={panel} tabIndex={-1} className="natal-pixel-consent" aria-label={uk ? 'Налаштування приватності' : 'Privacy preferences'}>
      <div><strong>{uk ? 'Ваш вибір приватності' : 'Your privacy choices'}</strong>
        <p>{uk ? 'Сайт працює без необов’язкового вимірювання. Оберіть окремо аналітику Natal та рекламу Meta; змінити вибір можна будь-коли.' : 'The site works without optional measurement. Choose Natal analytics and Meta advertising separately; change your choice at any time.'}</p>
        <p><a href={legalUrl('privacy', uk ? 'uk' : 'en', '')}>{uk ? 'Політика конфіденційності' : 'Privacy policy'}</a> · <a href={legalUrl('cookies', uk ? 'uk' : 'en', '')}>{uk ? 'Політика cookie' : 'Cookie policy'}</a></p>
        <label><input type="checkbox" checked={analytics} onChange={event => setAnalytics(event.target.checked)} />{uk ? 'Аналітика Natal — перегляди та переходи до контактів' : 'Natal analytics — page views and contact clicks'}</label>
        <label><input type="checkbox" checked={marketing} onChange={event => setMarketing(event.target.checked)} />{uk ? 'Реклама Meta — Pixel, cookie та вимірювання реклами' : 'Meta advertising — Pixel, cookies and ad measurement'}</label>
      </div>
      <div className="natal-pixel-consent__actions">
        <button type="button" onClick={() => save(false, false)}>{uk ? 'Відхилити необов’язкові' : 'Reject optional'}</button>
        <button type="button" onClick={() => save(true, true)}>{uk ? 'Дозволити всі' : 'Allow all'}</button>
        <button type="button" onClick={() => save(analytics, marketing)}>{uk ? 'Зберегти вибір' : 'Save preferences'}</button>
        {preferences && <button type="button" onClick={() => { close(); settings.current?.focus() }}>{uk ? 'Закрити' : 'Close'}</button>}
      </div>
    </aside>}
  </>
}
