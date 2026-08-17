import { History, Images, Plus, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { Creative, Region } from '../types'
import { AnnotationCanvas } from '../components/AnnotationCanvas'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'

interface Review {
  feedback_id: string
  rating: number
  predicted_ctr?: number
  overall_comment: string
  supersedes_feedback_id?: string
  created_at: string
}

export function PostsView({ api, language }: { api: ApiClient; language: Language }) {
  const [filter, setFilter] = useState<'pending' | 'reviewed'>('pending')
  const [items, setItems] = useState<Creative[] | null>(null)
  const [selected, setSelected] = useState<Creative | null>(null)
  const [image, setImage] = useState('')
  const [history, setHistory] = useState<Review[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [ctr, setCtr] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [requestText, setRequestText] = useState('')
  const [ideaId, setIdeaId] = useState('')

  const load = () => api.get<{ items: Creative[] }>(`/api/v1/posts?review_status=${filter}&limit=20`)
    .then((data) => { setItems(data.items); setSelected(data.items[0] || null) })
    .catch((cause: Error) => setError(cause.message))

  useEffect(() => { void load() }, [api, filter])
  useEffect(() => {
    setRegions([]); setComment(''); setRating(selected?.rating || 0)
    setCtr(selected?.predicted_ctr === undefined ? '' : String(selected.predicted_ctr))
    setHistory([]); setImage('')
    if (!selected) return
    let active = true
    let objectUrl = ''
    void api.blob(selected.image_url).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (active) setImage(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    }).catch((cause: Error) => setError(cause.message))
    void api.get<{ items: Review[] }>(`/api/v1/creatives/${selected.uuid}/reviews`)
      .then((data) => active && setHistory(data.items)).catch(() => undefined)
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, selected])

  const create = async (count: 1 | 10) => {
    setBusy(true); setError('')
    try {
      await api.post(
        count === 1 ? '/api/v1/posts' : '/api/v1/post-batches',
        count === 1 ? { request_text: requestText } : { idea_id: ideaId ? Number(ideaId) : null },
      )
      setFilter('pending'); await load()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const submit = async () => {
    if (!selected || !rating) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/creatives/${selected.uuid}/reviews`, {
        artifact_digest: selected.artifact_digest,
        rating, comment,
        predicted_ctr: selected.batch_id && ctr ? Number(ctr) : null,
        regions,
        supersedes_feedback_id: selected.latest_feedback_id || null,
      })
      setRegions([]); setRating(0); setComment(''); setCtr(''); await load()
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!items && !error) return <Loading />
  return <>
    <PageHeader eyebrow="ЦИКЛ КРЕАТИВІВ" title="Пости" />
    {error && <ErrorState message={error} retry={load} />}
    <section className="post-controls">
      <label>Один пост: гачок | підпис | заклик до дії<input value={requestText} onChange={(event) => setRequestText(event.target.value)} placeholder="Вони сумнівались… | Покажи прогрес | ПОЧАТИ" /></label>
      <button onClick={() => create(1)} disabled={busy || !requestText.trim()}><Plus />Створити один</button>
      <label>10 варіантів: ID ідеї (порожнє = найкраща)<input inputMode="numeric" value={ideaId} onChange={(event) => setIdeaId(event.target.value.replace(/\D/g, ''))} placeholder="Наприклад, 42" /></label>
      <button onClick={() => create(10)} disabled={busy}><Images />Створити 10 варіантів</button>
    </section>
    <div className="tabs review-tabs" role="tablist">
      <button className={filter === 'pending' ? 'selected' : ''} onClick={() => setFilter('pending')}>Черга перевірки</button>
      <button className={filter === 'reviewed' ? 'selected' : ''} onClick={() => setFilter('reviewed')}><History />Галерея / історія</button>
    </div>
    {items?.length === 0 && <Empty><h2>{filter === 'pending' ? 'Черга порожня' : 'Ще немає перевірок'}</h2><p>Створіть один пост або набір із 10 варіантів.</p></Empty>}
    {items && items.length > 1 && <div className="creative-picker" aria-label="Креативи">{items.map((item) => <button key={item.uuid} className={selected?.uuid === item.uuid ? 'selected' : ''} onClick={() => setSelected(item)}><strong>{item.batch_id ? `${item.position}/10` : 'ОДИН'}</strong><span>{String(local(item.title, language))}</span><small>{item.rating ? `${item.rating}/5` : 'перевірка'}</small></button>)}</div>}
    {selected && <div className="review-layout">
      <div>
        <div className="review-heading"><div><small>{selected.batch_id ? `НАБІР · ${selected.position}/10` : 'ОДИН ПОСТ'}</small><h2>{String(local(selected.title, language))}</h2></div><span>{selected.uuid.slice(0, 8)} · {selected.artifact_digest.slice(0, 10)}</span></div>
        {image ? <AnnotationCanvas src={image} alt={String(local(selected.title, language))} regions={regions} onChange={setRegions} /> : <Loading />}
        {history.length > 0 && <details className="review-history"><summary>Незмінна історія відгуків · {history.length}</summary>{history.map((review) => <article key={review.feedback_id}><strong>{review.rating}/5{review.predicted_ctr === undefined || review.predicted_ctr === null ? '' : ` · CTR ${review.predicted_ctr}%`}</strong><p>{review.overall_comment || 'Без загального коментаря'}</p><small>{review.feedback_id}<br />{new Date(review.created_at).toLocaleString('uk-UA')}</small></article>)}</details>}
      </div>
      <form className="review-form" onSubmit={(event) => { event.preventDefault(); void submit() }}>
        {selected.latest_feedback_id && <p className="correction-note">Виправлення створить нову незмінну редакцію з посиланням <code>supersedes</code>.</p>}
        <fieldset><legend>Загальна оцінка</legend><div className="rating">{[1, 2, 3, 4, 5].map((value) => <button type="button" key={value} className={rating === value ? 'selected' : ''} onClick={() => setRating(value)} aria-label={`${value} з 5`}>{value}</button>)}</div></fieldset>
        {selected.batch_id && <label>Прогноз CTR, %<input inputMode="decimal" value={ctr} onChange={(event) => setCtr(event.target.value)} placeholder="1.25" required /></label>}
        <label>Загальний коментар<textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={4} /></label>
        <button className="primary large" disabled={!rating || busy || (Boolean(selected.batch_id) && !ctr)}><Send />{busy ? 'Збереження…' : selected.latest_feedback_id ? 'Зберегти виправлення' : 'Надіслати відгук'}</button>
      </form>
    </div>}
  </>
}
