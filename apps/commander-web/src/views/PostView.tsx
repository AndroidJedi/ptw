import { Check, Image, RefreshCcw, Send, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'
import type {
  ProductBrief, SimplePost, StudioPhoneBackgroundTexture,
  StudioPhoneMetricsContent, StudioPhoneScreenTexture,
} from '../types'

const activeStatuses = new Set<SimplePost['status']>(['queued', 'generating', 'tuning'])

const defaultPhoneContent: StudioPhoneMetricsContent = {
  schema: 'ptw.studio.phone-metrics-content.v2',
  offer: 'NATAL',
  hero_title: 'Ваш головний меседж тут',
  supporting_text: 'Додайте коротке пояснення, яке допоможе зробити наступний крок.',
  cta: 'ДІЗНАТИСЯ БІЛЬШЕ',
  stats: [
    { value: 'ВАШЕ', label: 'значення' },
    { value: 'ВАШЕ', label: 'значення' },
    { value: 'ВАШЕ', label: 'значення' },
  ],
  phone_hero_title: '',
  phone_buttons: ['Створити новий акаунт', 'Увійти', 'Можливо пізніше'],
}

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
  const [templateId, setTemplateId] = useState<'universal_ad' | 'phone_metrics'>('universal_ad')
  const [phoneContent, setPhoneContent] = useState<StudioPhoneMetricsContent>(structuredClone(defaultPhoneContent))
  const [phoneTextures, setPhoneTextures] = useState<{
    background: StudioPhoneBackgroundTexture
    copy_background: StudioPhoneBackgroundTexture
    phone_screen: StudioPhoneScreenTexture
  }>({ background: 'concrete', copy_background: 'none', phone_screen: 'grain' })
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
        template_id: templateId,
        template_input: templateId === 'phone_metrics'
          ? { content: phoneContent, textures: phoneTextures }
          : null,
      }, { deadlineMs: 60_000 })
      setPost(value.post)
      setNotice(templateId === 'phone_metrics' ? tr(
        'Generating one phone-screen visual and applying the fixed Natal template.',
        'Генерується один візуал екрана телефону та застосовується фіксований шаблон Natal.',
      ) : tr(
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
      <fieldset className="post-template-selector" disabled={busy}>
        <legend>{tr('Template', 'Шаблон')}</legend>
        <div className="studio-template-grid">
          <label className={`studio-template-card ${templateId === 'universal_ad' ? 'is-active' : ''}`}>
            <input aria-label={tr('Universal ad', 'Універсальна реклама')} type="radio" name="post-template" value="universal_ad" checked={templateId === 'universal_ad'} onChange={() => setTemplateId('universal_ad')} />
            <strong>{tr('Universal ad', 'Універсальна реклама')}</strong><small>1080×1080</small>
            <span>{tr('One Pexels photograph and editable Universal Studio composition.', 'Одна фотографія Pexels та редагована композиція Universal Studio.')}</span>
          </label>
          <label className={`studio-template-card ${templateId === 'phone_metrics' ? 'is-active' : ''}`}>
            <input aria-label={tr('Phone & metrics', 'Телефон і метрики')} type="radio" name="post-template" value="phone_metrics" checked={templateId === 'phone_metrics'} onChange={() => setTemplateId('phone_metrics')} />
            <strong>{tr('Phone & metrics', 'Телефон і метрики')}</strong><small>1080×1350</small>
            <span>{tr('Fixed crisp Natal app screen and front-facing iPhone, three metrics, and Brief-generated text-free hero art.', 'Фіксований чіткий екран застосунку Natal і фронтальний iPhone, три метрики й згенерований із Брифу герой-арт без тексту.')}</span>
          </label>
        </div>
      </fieldset>
      {templateId === 'phone_metrics' && <section className="post-phone-inputs" aria-label={tr('Phone and metrics post content', 'Вміст допису телефону й метрик')}>
        <p>{tr('These owner-entered values lock when the Post draft begins. Natal stays visible and fixed.', 'Ці введені власником значення фіксуються з початком чернетки допису. Natal завжди видимий і фіксований.')}</p>
        <label><span>{tr('Full post background texture', 'Текстура повного фону допису')}</span><select aria-label={tr('Full post background texture', 'Текстура повного фону допису')} value={phoneTextures.background} onChange={(event) => setPhoneTextures({ ...phoneTextures, background: event.target.value as StudioPhoneBackgroundTexture })}>
          <option value="none">{tr('Off', 'Без текстури')}</option><option value="grain">{tr('Fine grain', 'Дрібне зерно')}</option><option value="concrete">{tr('Concrete', 'Бетон')}</option><option value="travertine">{tr('Travertine', 'Травертин')}</option>
        </select></label>
        <label><span>{tr('Left copy area texture', 'Текстура лівої текстової зони')}</span><select aria-label={tr('Left copy area texture', 'Текстура лівої текстової зони')} value={phoneTextures.copy_background} onChange={(event) => setPhoneTextures({ ...phoneTextures, copy_background: event.target.value as StudioPhoneBackgroundTexture })}>
          <option value="none">{tr('Off', 'Без текстури')}</option><option value="grain">{tr('Fine grain', 'Дрібне зерно')}</option><option value="concrete">{tr('Concrete', 'Бетон')}</option><option value="travertine">{tr('Travertine', 'Травертин')}</option>
        </select></label>
        <label><span>{tr('iPhone screen texture', 'Текстура екрана iPhone')}</span><select aria-label={tr('iPhone screen texture', 'Текстура екрана iPhone')} value={phoneTextures.phone_screen} onChange={(event) => setPhoneTextures({ ...phoneTextures, phone_screen: event.target.value as StudioPhoneScreenTexture })}>
          <option value="none">{tr('Off', 'Без текстури')}</option><option value="grain">{tr('Fine grain', 'Дрібне зерно')}</option><option value="paper">{tr('Soft paper', 'М’який папір')}</option><option value="frosted">{tr('Frosted glass', 'Матове скло')}</option>
        </select></label>
        <label><span>{tr('Eyebrow', 'Надзаголовок')}</span><input maxLength={32} value={phoneContent.offer} onChange={(event) => setPhoneContent({ ...phoneContent, offer: event.target.value })} /></label>
        <label><span>{tr('Headline', 'Заголовок')}</span><textarea rows={3} maxLength={140} value={phoneContent.hero_title} onChange={(event) => setPhoneContent({ ...phoneContent, hero_title: event.target.value })} /></label>
        <label><span>{tr('Supporting text', 'Пояснювальний текст')}</span><textarea rows={3} maxLength={220} value={phoneContent.supporting_text} onChange={(event) => setPhoneContent({ ...phoneContent, supporting_text: event.target.value })} /></label>
        <label><span>CTA</span><input maxLength={60} value={phoneContent.cta} onChange={(event) => setPhoneContent({ ...phoneContent, cta: event.target.value })} /></label>
        <label><span>{tr('Optional phone title', 'Необов’язковий заголовок у телефоні')}</span><input maxLength={72} value={phoneContent.phone_hero_title} onChange={(event) => setPhoneContent({ ...phoneContent, phone_hero_title: event.target.value })} /></label>
        <div className="post-phone-metrics"><strong>{tr('Three owner metrics', 'Три метрики власника')}</strong>{phoneContent.stats.map((stat, index) => <div key={index}><label><span>{tr('Value', 'Значення')} {index + 1}</span><input maxLength={24} value={stat.value} onChange={(event) => setPhoneContent((current) => ({ ...current, stats: current.stats.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item) }))} /></label><label><span>{tr('Label', 'Підпис')} {index + 1}</span><input maxLength={38} value={stat.label} onChange={(event) => setPhoneContent((current) => ({ ...current, stats: current.stats.map((item, itemIndex) => itemIndex === index ? { ...item, label: event.target.value } : item) }))} /></label></div>)}</div>
      </section>}
      <button className="primary large" disabled={busy} onClick={generate}>
        <Sparkles />{templateId === 'phone_metrics' ? tr('Generate phone post', 'Згенерувати допис з телефоном') : tr('Generate one post', 'Згенерувати один допис')}
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
      {post.status === 'draft' && (post.template_id || 'universal_ad') === 'universal_ad' && <form className="panel post-comment" onSubmit={(event) => { event.preventDefault(); void tune() }}>
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
      {post.status === 'draft' && (post.template_id || 'universal_ad') === 'phone_metrics' && <section className="panel post-comment"><p>{tr('This fixed phone template has no after-start tuning: its owner copy, screen art, and template selection are locked for review.', 'Цей фіксований шаблон телефону не має налаштувань після старту: текст власника, арт екрана та вибір шаблону заблоковані для перевірки.')}</p><div className="post-actions"><button className="primary" type="button" disabled={busy} onClick={approve}><Check />{tr('Approve as asset', 'Схвалити як ресурс')}</button></div></section>}
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
