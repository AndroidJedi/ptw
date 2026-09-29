import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'

type Inquiry = { request_id: string; created_at: string; source: string; question: string; contact: string; contact_channel: string; slug: string; landing_version_id: string }
export function LandingInbox({ api, projectId, language }: { api: ApiClient; projectId: string; language: 'uk' | 'en' }) {
  const [items, setItems] = useState<Inquiry[] | null>(null), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const uk = language === 'uk'
  useEffect(() => {
    let active = true
    setItems(null); setError('')
    api.get<{ items: Inquiry[] }>(`/api/v1/landings/projects/${projectId}/inquiries`).then(value => { if (active) setItems(value.items) }).catch(() => { if (active) setError(uk ? 'Не вдалося завантажити звернення.' : 'Could not load inquiries.') })
    return () => { active = false }
  }, [api, projectId, uk, retry])
  return <div className="landing-inbox">
    <p>{uk ? 'Останні 50 звернень із публічного лендінгу. Контакти залишено для відповіді або сповіщення про запуск альфа-версії.' : 'Latest 50 inquiries from the public Landing. Contacts were provided for a reply or an alpha-launch notification.'}</p>
    {error ? <p role="alert">{error} <button onClick={() => setRetry(value => value + 1)}>{uk ? 'Спробувати ще раз' : 'Try again'}</button></p> : items === null ? <p role="status">{uk ? 'Завантажуємо…' : 'Loading…'}</p> : items.length === 0 ? <p>{uk ? 'Звернень поки немає.' : 'No inquiries yet.'}</p> : items.map(item => <article key={item.request_id} style={{ borderTop: '1px solid #ddd', padding: '16px 0', overflowWrap: 'anywhere' }}>
      <small>{new Date(item.created_at).toLocaleString(uk ? 'uk-UA' : 'en-GB')} · /{item.slug} · {item.source}</small>
      {item.question && <p style={{ whiteSpace: 'pre-wrap' }}>{item.question}</p>}
      {item.contact && <p><strong>{item.contact_channel}: </strong>{item.contact}</p>}
      <details><summary>{uk ? 'Технічні дані' : 'Technical details'}</summary><p>ID: {item.request_id}<br />{uk ? 'Версія лендінгу' : 'Landing version'}: {item.landing_version_id}</p></details>
    </article>)}
  </div>
}
