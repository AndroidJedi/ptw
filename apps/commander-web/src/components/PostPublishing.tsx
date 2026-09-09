import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import type { InstagramPublication, InstagramWorkspace } from '../types'

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function PostPublishing({ api, language, projectId, creativeId, versions }: {
  api: ApiClient; language: Language; projectId: string; creativeId: string
  versions: Array<{ version: number; render_sha256: string; change_note: string }>
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [open, setOpen] = useState(false)
  const [version, setVersion] = useState(Math.max(0, ...versions.map(item => item.version)))
  const [workspace, setWorkspace] = useState<InstagramWorkspace | null>(null)
  const [caption, setCaption] = useState('')
  const [captionSelection, setCaptionSelection] = useState('')
  const [image, setImage] = useState<{ url: string; blob: Blob; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [submitted, setSubmitted] = useState('')
  const captionTouched = useRef(false)
  const alive = useRef(true)
  const selected = versions.find(item => item.version === version)
  const selectionKey = `${projectId}:${creativeId}:${version}:${selected?.render_sha256}`
  const selection = useRef(selectionKey)
  selection.current = selectionKey
  const base = `/api/v1/instagram/projects/${projectId}`
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    if (!open) return
    let active = true
    void api.get<InstagramWorkspace>(base).then(async value => {
      if (!active) return
      setWorkspace(value)
      if (value.connection.configured && !value.connection.verified) {
        const connection = await api.get<InstagramWorkspace['connection']>('/api/v1/instagram/connection', { deadlineMs: 120_000 })
        if (active) setWorkspace(current => current ? { ...current, connection } : current)
      }
    })
      .catch(cause => { if (active) setError(String(cause)) })
    return () => { active = false }
  }, [api, base, open])
  useEffect(() => {
    const source = workspace?.sources.find(item => item.creative_id === creativeId && item.version === version)
    if (source && !captionTouched.current) {
      setCaption([source.defaults.headline, source.defaults.primary_text].filter(Boolean).join('\n\n').slice(0, 2200))
      setCaptionSelection(selectionKey)
    }
  }, [workspace?.sources, creativeId, version, selectionKey])
  useEffect(() => {
    if (!open || !selected) return
    let active = true
    let url = ''
    setImage(null); setError(''); setNotice('')
    void api.image(`/api/v1/studio/projects/${projectId}/creatives/${creativeId}/versions/${version}/render`, 'image/png', selected.render_sha256)
      .then(blob => {
        if (!active) return
        url = URL.createObjectURL(blob)
        setImage({ url, blob, key: selectionKey })
      }).catch(cause => { if (active) setError(String(cause)) })
    return () => { active = false; if (url) URL.revokeObjectURL(url) }
  }, [api, projectId, creativeId, version, selected?.render_sha256, open, selectionKey])
  const draftKey = JSON.stringify({ creative_id: creativeId, version, caption })
  const readyImage = image?.key === selectionKey ? image : null
  const reloadPublications = async () => {
    const result = await api.get<{ items: InstagramPublication[] }>(`${base}/publications`)
    if (alive.current) setWorkspace(current => current ? { ...current, publications: result.items } : current)
  }
  useEffect(() => {
    if (!open || !workspace?.publications.some(item => ['queued', 'creating_container', 'preparing', 'publishing'].includes(item.status))) return
    const timer = window.setInterval(() => { void reloadPublications().catch(cause => { if (alive.current) setError(String(cause)) }) }, 3000)
    return () => window.clearInterval(timer)
  }, [open, workspace?.publications, base]) // eslint-disable-line react-hooks/exhaustive-deps
  const publish = async () => {
    if (!readyImage || captionSelection !== selectionKey || busy) return
    setBusy(true); setError(''); setNotice('')
    const key = `ptw-instagram-request:${projectId}:${creativeId}`
    const currentSelection = selectionKey
    try {
      const saved = sessionStorage.getItem(key)
      const previous = saved ? JSON.parse(saved) as { draft: string; request_id: string } : null
      const requestId = previous?.draft === draftKey ? previous.request_id : crypto.randomUUID()
      sessionStorage.setItem(key, JSON.stringify({ draft: draftKey, request_id: requestId }))
      await api.post(`${base}/publications`, { request_id: requestId, creative_id: creativeId, version, caption }, { deadlineMs: 120_000 })
      if (alive.current && selection.current === currentSelection) {
        setSubmitted(draftKey)
        setNotice(tr('Publication requested. Its verified status appears below.', 'Публікацію запитано. Перевірений статус з’явиться нижче.'))
        await reloadPublications()
      }
    } catch (cause) { if (alive.current) setError(String(cause)) }
    finally { if (alive.current) setBusy(false) }
  }
  const act = async (publication: InstagramPublication, action: 'retry' | 'sync') => {
    setBusy(true); setError('')
    try { await api.post(`${base}/publications/${publication.publication_id}/${action}`, {}); await reloadPublications() }
    catch (cause) { if (alive.current) setError(String(cause)) }
    finally { if (alive.current) setBusy(false) }
  }
  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); setNotice(tr('Copied', 'Скопійовано')) }
    catch { setError(tr('Clipboard unavailable. Select and copy the text shown above.', 'Буфер обміну недоступний. Виділіть і скопіюйте текст вище.')) }
  }
  if (!versions.length) return null
  const adUrl = `?page=ads&project=${encodeURIComponent(projectId)}&ad_creative=${encodeURIComponent(creativeId)}&ad_version=${version}&destination=WEBSITE`
  return <section className="panel post-publishing" aria-label={tr('Publish approved Post', 'Опублікувати затверджений допис')}>
    <h2>{tr('Publish approved Post', 'Опублікувати затверджений допис')}</h2>
    <p>{tr('Publishing uses the selected approved image. Approve pending edits to use them.', 'Публікація використовує вибране затверджене зображення. Щоб використати зміни, спочатку затвердьте їх.')}</p>
    <label>{tr('Approved version', 'Затверджена версія')}<select value={version} disabled={busy} onChange={event => { captionTouched.current = false; setVersion(Number(event.target.value)) }}>
      {[...versions].sort((a, b) => b.version - a.version).map(item => <option key={item.version} value={item.version}>v{item.version} · {item.change_note}</option>)}
    </select></label>
    <div className="post-publishing-actions"><button className="secondary" aria-expanded={open} onClick={() => setOpen(value => !value)}>{tr('Publish to Instagram', 'Опублікувати в Instagram')}</button>
      <a className="primary" href={adUrl}>{tr('Create Instagram ad', 'Створити рекламу Instagram')}</a></div>
    {open && <>
      {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
      <figure className="ads-preview">{readyImage ? <img src={readyImage.url} alt={tr('Approved Instagram image', 'Затверджене зображення Instagram')} /> : <p>{tr('Verifying approved image…', 'Перевіряємо затверджене зображення…')}</p>}</figure>
      <p>{workspace?.connection.instagram?.username ? `@${workspace.connection.instagram.username}` : tr('Instagram account unavailable', 'Акаунт Instagram недоступний')}</p>
      {!workspace?.connection.verified && <p>{workspace?.connection.explanation || tr('Checking publishing access…', 'Перевіряємо доступ до публікації…')}</p>}
      <label>{tr('Instagram caption', 'Підпис Instagram')}<textarea rows={6} maxLength={2200} value={caption} disabled={busy} onChange={event => { captionTouched.current = true; setCaptionSelection(selectionKey); setCaption(event.target.value) }} /></label>
      {workspace?.landing && <><a href={workspace.landing.canonical_url} target="_blank" rel="noreferrer">{workspace.landing.canonical_url}</a>
        <div className="post-publishing-actions"><button className="secondary" onClick={() => void copy(workspace.landing!.canonical_url)}>{tr('Copy landing URL', 'Копіювати URL лендінгу')}</button>
          <button className="secondary" disabled={busy} onClick={() => { captionTouched.current = true; setCaptionSelection(selectionKey); setCaption(current => `${current}\n\n${tr('Learn more via the link in bio.', 'Дізнайтеся більше за посиланням у профілі.')}`.slice(0, 2200)) }}>{tr('Add link-in-bio guidance', 'Додати заклик до посилання у профілі')}</button></div>
        <p>{tr('Set the landing link in your Instagram profile manually. The button inside this image is not clickable.', 'Додайте посилання на лендінг у профіль Instagram вручну. Кнопка всередині зображення не є клікабельною.')}</p></>}
      <div className="post-publishing-actions"><button className="primary" disabled={busy || !readyImage || captionSelection !== selectionKey || !workspace?.connection.verified || submitted === draftKey} onClick={() => void publish()}>{tr('Publish now', 'Опублікувати зараз')}</button>
        <button className="secondary" disabled={!readyImage} onClick={() => { if (readyImage) { downloadBlob(readyImage.blob, `post-v${version}.png`); setNotice(tr('Exported. Upload the image and caption in Instagram to publish.', 'Експортовано. Завантажте зображення та підпис в Instagram для публікації.')) } }}>{tr('Download image', 'Завантажити зображення')}</button>
        <button className="secondary" onClick={() => void copy(caption)}>{tr('Copy caption', 'Копіювати підпис')}</button>
        <a className="secondary" href="https://www.instagram.com/" target="_blank" rel="noreferrer">{tr('Open Instagram', 'Відкрити Instagram')}</a></div>
      <div className="post-publications">{workspace?.publications.filter(item => item.specification.creative_id === creativeId).map(item => <article key={item.publication_id}>
        <strong>v{item.specification.version} · {({ published: tr('Published', 'Опубліковано'), published_unresolved: tr('Published · link pending', 'Опубліковано · посилання очікується'), uncertain: tr('Outcome uncertain', 'Результат невідомий'), failed: tr('Failed', 'Помилка'), queued: tr('Queued', 'У черзі'), preparing: tr('Preparing', 'Підготовка'), creating_container: tr('Preparing', 'Підготовка'), publishing: tr('Publishing', 'Публікація') } as Record<string, string>)[item.status]}</strong>
        <code>{item.publication_id}</code>{item.container_id && <code>Container: {item.container_id}</code>}{item.media_id && <code>Instagram: {item.media_id}</code>}{item.error && <p role="alert">{item.error}</p>}
        <div className="post-publishing-actions">{item.permalink && <a href={item.permalink} target="_blank" rel="noreferrer">{tr('View published post', 'Переглянути опублікований допис')}</a>}
          {item.status === 'failed' && !item.publish_started && <button className="secondary" disabled={busy} onClick={() => void act(item, 'retry')}>{tr('Retry preparation', 'Повторити підготовку')}</button>}
          {(item.status === 'published' || (item.status === 'failed' && !item.publish_started)) && <button className="secondary" disabled={busy} onClick={() => { sessionStorage.removeItem(`ptw-instagram-request:${projectId}:${creativeId}`); setSubmitted(''); setNotice(tr('Review the image and caption, then Publish now to create a new post.', 'Перевірте зображення й підпис, потім натисніть «Опублікувати зараз», щоб створити новий допис.')) }}>{tr('Prepare another post', 'Підготувати інший допис')}</button>}
          <button className="secondary" disabled={busy} onClick={() => void act(item, 'sync')}>{tr('Sync status', 'Синхронізувати статус')}</button></div>
      </article>)}</div>
    </>}
  </section>
}
