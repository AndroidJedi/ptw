import { Check, Image, RefreshCcw, Send, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'
import type { ProductBrief, SimplePost } from '../types'

const activeStatuses = new Set<SimplePost['status']>(['queued', 'generating', 'tuning'])

function commandValue(value: string | number | boolean | string[]) {
  return Array.isArray(value) ? value.join(' · ') : String(value)
}

export function PostView({ api, projectId, language }: {
  api: ApiClient
  projectId: string | null
  language: Language
}) {
  const [brief, setBrief] = useState<ProductBrief | null>(null)
  const [post, setPost] = useState<SimplePost | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const previewGeneration = useRef(0)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  const replacePreview = (url: string) => setPreviewUrl((current) => {
    if (current) URL.revokeObjectURL(current)
    return url
  })

  const renderPreview = async (value: SimplePost) => {
    if (!value.preview || !value.state_sha256) return
    const generation = ++previewGeneration.current
    const blob = value.approved_asset
      ? await api.media(
        `/api/v1/posts/assets/${value.approved_asset.asset_id}/render`,
        value.approved_asset.mime_type, value.approved_asset.sha256,
      )
      : await api.postMedia(
        `/api/v1/posts/${value.post_id}/preview`,
        { state_sha256: value.state_sha256 }, 'image/png', { deadlineMs: 90_000 },
      )
    if (generation === previewGeneration.current) replacePreview(URL.createObjectURL(blob))
  }

  const loadPost = async (postId: string, withPreview = true) => {
    const previousStatus = post?.status
    const value = await api.get<SimplePost>(`/api/v1/posts/${postId}`, { deadlineMs: 60_000 })
    setPost(value)
    if (withPreview && value.preview && !activeStatuses.has(value.status)) await renderPreview(value)
    if (previousStatus && activeStatuses.has(previousStatus) && !activeStatuses.has(value.status)) {
      setNotice(value.status === 'draft' && !value.last_error
        ? tr('Draft updated. It is still not an asset.', 'Чернетку оновлено. Вона все ще не є ресурсом.')
        : '')
    }
    return value
  }

  const load = async () => {
    if (!projectId) {
      setBrief(null); setPost(null); replacePreview(''); setLoading(false)
      return
    }
    setLoading(true); setError('')
    try {
      const [briefs, posts] = await Promise.all([
        api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
        api.get<{ items: SimplePost[] }>(`/api/v1/posts?limit=100&project_id=${encodeURIComponent(projectId)}`),
      ])
      const latestBrief = briefs.items[0]
      setBrief(latestBrief?.status === 'completed' && latestBrief.approved && latestBrief.document
        ? latestBrief : null)
      if (posts.items[0]) await loadPost(posts.items[0].post_id)
      else { setPost(null); replacePreview('') }
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setBrief(null); setPost(null); replacePreview(''); setNotice('')
    void load()
    return () => { previewGeneration.current += 1 }
  }, [api, projectId])

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  useEffect(() => {
    if (!post || !activeStatuses.has(post.status)) return
    const timer = window.setInterval(() => {
      void loadPost(post.post_id).catch((cause: Error) => setError(cause.message))
    }, 1200)
    return () => window.clearInterval(timer)
  }, [post?.post_id, post?.status])

  const generate = async () => {
    if (!brief) return
    setBusy(true); setError(''); setNotice('')
    try {
      const value = await api.post<{ post: SimplePost }>('/api/v1/posts', {
        request_id: crypto.randomUUID(), brief_id: brief.brief_id,
      }, { deadlineMs: 60_000 })
      setPost(value.post)
      setNotice(tr(
        'Generating one post and choosing one relevant photograph.',
        'Генерується один допис і підбирається одна релевантна фотографія.',
      ))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const retry = async () => {
    if (!post) return
    setBusy(true); setError('')
    try {
      const value = await api.post<SimplePost>(`/api/v1/posts/${post.post_id}/retry`, {})
      setPost(value)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const tune = async () => {
    if (!post || !comment.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const value = await api.post<{ post: SimplePost }>(`/api/v1/posts/${post.post_id}/tune`, {
        request_id: crypto.randomUUID(), comment: comment.trim(),
      }, { deadlineMs: 60_000 })
      setPost(value.post)
      setComment('')
      setNotice(tr(
        'Your comment is being translated into Studio component and image commands.',
        'Ваш коментар перетворюється на команди компонентів Студії та зображення.',
      ))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  const approve = async () => {
    if (!post?.state_sha256) return
    setBusy(true); setError(''); setNotice('')
    try {
      const value = await api.post<{ post: SimplePost }>(`/api/v1/posts/${post.post_id}/approve`, {
        state_sha256: post.state_sha256,
      }, { deadlineMs: 90_000 })
      setPost(value.post)
      await renderPreview(value.post)
      setNotice(tr(
        'Approved. The exact post is now one immutable asset.',
        'Схвалено. Точний допис тепер є одним незмінним ресурсом.',
      ))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (loading) return <Loading language={language} />
  if (!projectId) return <><PageHeader title={tr('Post', 'Допис')} /><Empty>
    <Image className="empty-mark" /><h2>{tr('Select a Project', 'Виберіть проєкт')}</h2>
  </Empty></>

  return <div className="post-page">
    <PageHeader title={tr('Post', 'Допис')} />
    {error && <ErrorState message={error} retry={() => void load()} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
    {!brief && !post && <Empty><Image className="empty-mark" />
      <h2>{tr('Approve a Product Brief first', 'Спочатку схваліть продуктовий бриф')}</h2>
      <p>{tr(
        'The post is generated only from a completed Brief whose promise and offer you approved.',
        'Допис генерується лише із завершеного брифу, обіцянку та пропозицію якого ви схвалили.',
      )}</p>
    </Empty>}
    {brief && !post && <section className="panel post-start">
      <small>{tr('ONE BRIEF → ONE POST', 'ОДИН БРИФ → ОДИН ДОПИС')}</small>
      <h2>{brief.document?.promise}</h2>
      <p>{brief.document?.offer}</p>
      <button className="primary large" disabled={busy} onClick={generate}>
        <Sparkles />{tr('Generate one post', 'Згенерувати один допис')}
      </button>
    </section>}
    {post && <section className="post-workspace" aria-label={tr('Post preview and tuning', 'Прев’ю та налаштування допису')}>
      <div className="post-meta">
        <span>{post.status}</span><code>{post.post_id}</code>
        {post.approved_asset && <strong><Check /> {tr('ASSET', 'РЕСУРС')} · {post.approved_asset.asset_id}</strong>}
      </div>
      {post.last_error && <p className="notice" role="alert">{post.last_error}</p>}
      <div className="post-preview panel">
        {activeStatuses.has(post.status) ? <div className="post-generating" role="status">
          <RefreshCcw className="spin" />
          <strong>{post.status === 'tuning' ? tr('Applying your comment…', 'Застосовується ваш коментар…') : tr('Generating your post…', 'Генерується ваш допис…')}</strong>
          <span>{tr('The draft is not an asset yet.', 'Чернетка ще не є ресурсом.')}</span>
        </div> : previewUrl ? <img src={previewUrl} alt={tr('Single generated post preview', 'Прев’ю одного згенерованого допису')} /> : post.status === 'failed' ? <div className="post-generating">
          <strong>{tr('Generation failed', 'Генерація не вдалася')}</strong>
          <span>{post.last_error}</span>
          <button className="secondary" disabled={busy} onClick={retry}>{tr('Retry', 'Повторити')}</button>
        </div> : <Loading language={language} />}
      </div>
      {post.status === 'draft' && <form className="panel post-comment" onSubmit={(event) => { event.preventDefault(); void tune() }}>
        <label><span>{tr('Comment below the preview', 'Коментар під прев’ю')}</span>
          <textarea rows={3} maxLength={2000} value={comment} onChange={(event) => setComment(event.target.value)} placeholder={tr(
            'For example: Pick an image with a thoughtful human face and make the title smaller.',
            'Наприклад: Підбери зображення із задумливим людським обличчям і зроби заголовок меншим.',
          )} />
        </label>
        <div className="post-actions">
          <button className="secondary" type="submit" disabled={busy || !comment.trim()}><Send />{tr('Apply comment', 'Застосувати коментар')}</button>
          <button className="primary" type="button" disabled={busy} onClick={approve}><Check />{tr('Approve as asset', 'Схвалити як ресурс')}</button>
        </div>
      </form>}
      {!!post.last_commands.length && <details className="panel post-commands">
        <summary>{tr('Applied Studio commands', 'Застосовані команди Студії')}</summary>
        <ul>{post.last_commands.map((command) => <li key={command.setting_id}><code>{command.setting_id}</code><span>{commandValue(command.value)}</span></li>)}</ul>
        {post.last_image_request && <p><code>{`asset.${post.last_image_request.slot}`}</code><span>{post.last_image_request.query}</span></p>}
      </details>}
      {post.status === 'approved' && post.approved_asset && <section className="panel post-approved">
        <Check /><div><strong>{tr('Immutable asset created', 'Незмінний ресурс створено')}</strong>
          <code>{post.approved_asset.sha256}</code></div>
      </section>}
    </section>}
  </div>
}
