import { type ReactNode, useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import type { InstagramPublication, InstagramWorkspace, MetaAdsSourceVersion, TikTokPublication, TikTokWorkspace } from '../types'

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = filename; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

type CommonWorkspace<P> = {
  connection: { configured: boolean; verified: boolean; explanation?: string }
  sources: MetaAdsSourceVersion[]; publications: P[]
  landing?: { canonical_url: string } | null
}
type CorePublication = {
  publication_id: string; error?: string | null; retryable?: boolean; syncable?: boolean
  source?: { creative_id: string; version: number }; phase?: string; status?: string
  external?: { transfer_id?: string | null; post_ids?: string[]; permalink?: string | null }
  specification?: { creative_id?: string; version?: number; is_aigc?: boolean }
  analytics?: { tracked_url?: string | null } | null
  permalink?: string | null; container_id?: string | null; media_id?: string | null
}
type ShellProps<P extends CorePublication, W extends CommonWorkspace<P>> = {
  api: ApiClient; language: Language; projectId: string; creativeId: string; version: number
  renderSha256: string; provider: 'instagram' | 'tiktok'; label: string
  draftKey: string; request: (requestId: string) => Record<string, unknown>; valid: boolean
  fields: (workspace: W | null, source: MetaAdsSourceVersion | undefined) => ReactNode
  account: (workspace: W | null) => string; openUrl: string; onWorkspace?: (workspace: W) => void
}

function PublishingShell<P extends CorePublication, W extends CommonWorkspace<P>>(props: ShellProps<P, W>) {
  const { api, language, projectId, creativeId, version, renderSha256, provider, label } = props
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [open, setOpen] = useState(false)
  const [workspace, setWorkspace] = useState<W | null>(null)
  const [image, setImage] = useState<{ url: string; blob: Blob; key: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [submitted, setSubmitted] = useState('')
  const alive = useRef(true)
  const selectionKey = `${projectId}:${creativeId}:${version}:${renderSha256}`
  const base = `/api/v1/${provider}/projects/${projectId}`
  const refresh = async () => {
    const result = await api.get<{ items: P[] }>(`${base}/publications`)
    if (alive.current) setWorkspace(current => current ? { ...current, publications: result.items } : current)
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    if (!open) return
    let active = true
    void api.get<W>(base).then(async value => {
      if (!active) return
      setWorkspace(value); props.onWorkspace?.(value)
      if (provider === 'tiktok' || (value.connection.configured && !value.connection.verified)) {
        const connection = await api.get<W['connection']>(`/api/v1/${provider}/connection`, { deadlineMs: 120_000 })
        if (active) {
          const next = { ...value, connection }
          setWorkspace(next); props.onWorkspace?.(next)
        }
      }
    }).catch(cause => { if (active) setError(String(cause)) })
    return () => { active = false }
  }, [api, base, open, provider, version]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!open || !renderSha256) return
    let active = true; let url = ''
    setImage(null); setError(''); setNotice('')
    void api.image(`/api/v1/studio/projects/${projectId}/creatives/${creativeId}/versions/${version}/render`, 'image/png', renderSha256)
      .then(blob => { if (active) { url = URL.createObjectURL(blob); setImage({ url, blob, key: selectionKey }) } })
      .catch(cause => { if (active) setError(String(cause)) })
    return () => { active = false; if (url) URL.revokeObjectURL(url) }
  }, [api, creativeId, open, projectId, renderSha256, selectionKey, version])
  useEffect(() => {
    if (!open || !workspace?.publications.some(item => ['queued', 'preparing', 'publishing'].includes(item.phase || item.status || ''))) return
    const timer = window.setInterval(() => { void refresh().catch(cause => setError(String(cause))) }, 3000)
    return () => window.clearInterval(timer)
  }, [open, workspace?.publications, base]) // eslint-disable-line react-hooks/exhaustive-deps
  const readyImage = image?.key === selectionKey ? image : null
  const publish = async () => {
    if (!readyImage || !props.valid || busy) return
    setBusy(true); setError(''); setNotice('')
    const storageKey = `ptw-${provider}-request:${projectId}:${creativeId}`
    try {
      const saved = sessionStorage.getItem(storageKey)
      const previous = saved ? JSON.parse(saved) as { draft: string; request_id: string } : null
      const requestId = previous?.draft === props.draftKey ? previous.request_id : crypto.randomUUID()
      sessionStorage.setItem(storageKey, JSON.stringify({ draft: props.draftKey, request_id: requestId }))
      await api.post(`${base}/publications`, props.request(requestId), { deadlineMs: 120_000 })
      if (alive.current) { setSubmitted(props.draftKey); setNotice(tr('Publication requested. Its verified status appears below.', 'Публікацію запитано. Перевірений статус з’явиться нижче.')); await refresh() }
    } catch (cause) { if (alive.current) setError(String(cause)) }
    finally { if (alive.current) setBusy(false) }
  }
  const act = async (item: P, action: 'retry' | 'sync') => {
    setBusy(true); setError('')
    try { await api.post(`${base}/publications/${item.publication_id}/${action}`, {}); await refresh() }
    catch (cause) { setError(String(cause)) } finally { setBusy(false) }
  }
  const selectedSource = workspace?.sources.find(item => item.creative_id === creativeId && item.version === version)
  const items = (workspace?.publications || []).filter(item => (item.source?.creative_id || item.specification?.creative_id) === creativeId)
  return <div className="social-provider">
    <button className="secondary" aria-expanded={open} onClick={() => setOpen(value => !value)}>{tr(`Publish to ${label}`, `Опублікувати в ${label}`)}</button>
    {open && <div className="social-provider-panel">
      {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
      <figure className="ads-preview">{readyImage ? <img src={readyImage.url} alt={tr(`Approved ${label} image`, `Затверджене зображення ${label}`)} /> : <p>{tr('Verifying approved image…', 'Перевіряємо затверджене зображення…')}</p>}</figure>
      <p>{props.account(workspace)}</p>
      {!workspace?.connection.verified && <p>{workspace?.connection.explanation || tr('Checking publishing access…', 'Перевіряємо доступ до публікації…')}</p>}
      {props.fields(workspace, selectedSource)}
      <div className="post-publishing-actions">
        <button className="primary" disabled={busy || !readyImage || !workspace?.connection.verified || !props.valid || submitted === props.draftKey} onClick={() => void publish()}>{tr('Publish now', 'Опублікувати зараз')}</button>
        <button className="secondary" disabled={!readyImage} onClick={() => { if (readyImage) { downloadBlob(readyImage.blob, `post-v${version}.png`); setNotice(tr(`Exported. Upload the image in ${label} if direct publishing is unavailable.`, `Експортовано. Завантажте зображення в ${label}, якщо пряма публікація недоступна.`)) } }}>{tr('Download image', 'Завантажити зображення')}</button>
        <a className="secondary" href={props.openUrl} target="_blank" rel="noreferrer">{tr(`Open ${label}`, `Відкрити ${label}`)}</a>
      </div>
      <div className="post-publications">{items.map(item => {
        const phase = item.phase || item.status || 'failed'; const sourceVersion = item.source?.version || item.specification?.version
        const permalink = item.external?.permalink || item.permalink; const transfer = item.external?.transfer_id || item.container_id
        const trackedUrl = item.analytics?.tracked_url
        const phaseLabel = ({ published: tr('Published', 'Опубліковано'), published_unresolved: tr('Published · link pending', 'Опубліковано · посилання очікується'), uncertain: tr('Outcome uncertain', 'Результат невідомий'), failed: tr('Failed', 'Помилка'), queued: tr('Queued', 'У черзі'), preparing: tr('Preparing', 'Підготовка'), creating_container: tr('Preparing', 'Підготовка'), publishing: tr('Publishing', 'Публікація') } as Record<string, string>)[phase] || phase.replaceAll('_', ' ')
        return <article key={item.publication_id}><strong>v{sourceVersion} · {phaseLabel}</strong><code>{item.publication_id}</code>{transfer && <code>Transfer: {transfer}</code>}{item.error && <p role="alert">{item.error}</p>}{trackedUrl && <div className="tracked-publication-url"><p>{tr('Tracked Landing URL · caption unchanged', 'Відстежуваний URL лендінгу · підпис не змінено')}</p><a href={trackedUrl} target="_blank" rel="noreferrer">{trackedUrl}</a><button className="secondary" type="button" onClick={() => void navigator.clipboard.writeText(trackedUrl)}>{tr('Copy tracked URL', 'Копіювати відстежуваний URL')}</button></div>}<div className="post-publishing-actions">
          {permalink && <a href={permalink} target="_blank" rel="noreferrer">{tr('View published post', 'Переглянути опублікований допис')}</a>}
          {item.retryable && <button className="secondary" disabled={busy} onClick={() => void act(item, 'retry')}>{tr('Retry preparation', 'Повторити підготовку')}</button>}
          {item.syncable && <button className="secondary" disabled={busy} onClick={() => void act(item, 'sync')}>{tr('Sync status', 'Синхронізувати статус')}</button>}
          {(phase === 'published' || item.retryable) && <button className="secondary" disabled={busy} onClick={() => { sessionStorage.removeItem(`ptw-${provider}-request:${projectId}:${creativeId}`); setSubmitted('') }}>{tr('Prepare another post', 'Підготувати інший допис')}</button>}
        </div></article>
      })}</div>
    </div>}
  </div>
}

function InstagramPanel(props: Omit<ShellProps<InstagramPublication, InstagramWorkspace>, 'provider' | 'label' | 'draftKey' | 'request' | 'valid' | 'fields' | 'account' | 'openUrl'>) {
  const { language, creativeId, version } = props
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [caption, setCaption] = useState('')
  const [sourceKey, setSourceKey] = useState('')
  const key = `${creativeId}:${version}`
  const copy = (text: string) => { void navigator.clipboard.writeText(text) }
  return <PublishingShell<InstagramPublication, InstagramWorkspace> {...props} provider="instagram" label="Instagram" draftKey={JSON.stringify({ creativeId, version, caption })}
    valid={sourceKey === key} request={requestId => ({ request_id: requestId, source: { creative_id: creativeId, version }, content: { title: '', description: caption }, settings: {}, creator_snapshot_sha256: null, consent: {} })}
    onWorkspace={workspace => { const source = workspace.sources.find(item => item.creative_id === creativeId && item.version === version); setCaption([source?.defaults.headline, source?.defaults.primary_text].filter(Boolean).join('\n\n').slice(0, 2200)); setSourceKey(key) }}
    openUrl="https://www.instagram.com/" account={workspace => workspace?.connection.instagram?.username ? `@${workspace.connection.instagram.username}` : tr('Instagram account unavailable', 'Акаунт Instagram недоступний')}
    fields={(workspace, source) => <>
      <label>{tr('Instagram caption', 'Підпис Instagram')}<textarea rows={6} maxLength={2200} value={sourceKey === key ? caption : [source?.defaults.headline, source?.defaults.primary_text].filter(Boolean).join('\n\n').slice(0, 2200)} onChange={event => { setSourceKey(key); setCaption(event.target.value) }} /></label>
      {workspace?.landing && <><p><a href={workspace.landing.canonical_url} target="_blank" rel="noreferrer">{workspace.landing.canonical_url}</a></p><button className="secondary" type="button" onClick={() => copy(workspace.landing!.canonical_url)}>{tr('Copy landing URL', 'Копіювати URL лендінгу')}</button></>}
    </>} />
}

function TikTokPanel(props: Omit<ShellProps<TikTokPublication, TikTokWorkspace>, 'provider' | 'label' | 'draftKey' | 'request' | 'valid' | 'fields' | 'account' | 'openUrl'>) {
  const { api, language, creativeId, version } = props
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [connection, setConnection] = useState<TikTokWorkspace['connection'] | null>(null)
  const [connectError, setConnectError] = useState('')
  const [title, setTitle] = useState(''); const [description, setDescription] = useState('')
  const [draftSource, setDraftSource] = useState('')
  const [privacy, setPrivacy] = useState(''); const [comments, setComments] = useState(false); const [music, setMusic] = useState(false)
  const [commercialChoice, setCommercialChoice] = useState<'none' | 'own' | 'branded' | 'both' | ''>(''); const [consent, setConsent] = useState(false)
  const ownBrand = commercialChoice === 'own' || commercialChoice === 'both'; const branded = commercialChoice === 'branded' || commercialChoice === 'both'; const commercial = Boolean(ownBrand || branded)
  const valid = Boolean(privacy && consent && commercialChoice && connection?.creator_snapshot_sha256 && !(branded && privacy === 'SELF_ONLY'))
  const draft = JSON.stringify({ creativeId, version, title, description, privacy, comments, music, commercialChoice, consent, snapshot: connection?.creator_snapshot_sha256 })
  const connect = async () => {
    setConnectError('')
    try {
      const value = await api.post<{ authorization_url: string }>('/api/v1/tiktok/oauth/start', { return_to: window.location.pathname + window.location.search })
      window.location.assign(value.authorization_url)
    } catch (cause) { setConnectError(String(cause)) }
  }
  return <PublishingShell<TikTokPublication, TikTokWorkspace> {...props} provider="tiktok" label="TikTok" draftKey={draft} valid={valid} onWorkspace={workspace => {
    setConnection(workspace.connection)
    const source = workspace.sources.find(item => item.creative_id === creativeId && item.version === version)
    if (draftSource !== `${creativeId}:${version}`) { setTitle(String(source?.defaults.headline || '').slice(0, 90)); setDescription(String(source?.defaults.primary_text || '').slice(0, 4000)); setDraftSource(`${creativeId}:${version}`); setPrivacy(''); setConsent(false); setCommercialChoice('') }
  }} request={requestId => ({ request_id: requestId, source: { creative_id: creativeId, version }, content: { title, description }, settings: { privacy_level: privacy, allow_comment: comments, auto_add_music: music, commercial_content: { enabled: commercial, own_brand: ownBrand, branded_content: branded } }, creator_snapshot_sha256: connection?.creator_snapshot_sha256, consent: { music_usage_confirmed: consent } })}
    openUrl="https://www.tiktok.com/@natal_cast" account={workspace => workspace?.connection.account?.username ? `@${workspace.connection.account.username}` : tr('TikTok account unavailable', 'Акаунт TikTok недоступний')}
    fields={workspace => <>
      {connectError && <p role="alert">{connectError}</p>}
      {!workspace?.connection.verified ? <button className="secondary" type="button" onClick={() => void connect()} disabled={!workspace?.connection.configured}>{workspace?.connection.account ? tr('Reconnect @natal_cast', 'Повторно під’єднати @natal_cast') : tr('Connect @natal_cast', 'Під’єднати @natal_cast')}</button> : null}
      <label>{tr('TikTok photo title', 'Заголовок фото TikTok')}<input maxLength={90} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>{tr('TikTok description', 'Опис TikTok')}<textarea rows={6} maxLength={4000} value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label>{tr('Privacy (choose manually)', 'Приватність (оберіть вручну)')}<select value={privacy} onChange={event => setPrivacy(event.target.value)}><option value="">{tr('Choose privacy…', 'Оберіть приватність…')}</option>{workspace?.connection.creator?.privacy_level_options.map(option => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}</select></label>
      <label><input type="checkbox" checked={comments} disabled={workspace?.connection.creator?.comment_disabled} onChange={event => setComments(event.target.checked)} /> {tr('Allow comments', 'Дозволити коментарі')}</label>
      <label><input type="checkbox" checked={music} onChange={event => setMusic(event.target.checked)} /> {tr('Automatically add recommended music', 'Автоматично додати рекомендовану музику')}</label>
      <label>{tr('Commercial-content disclosure (choose manually)', 'Розкриття комерційного вмісту (оберіть вручну)')}<select value={commercialChoice} onChange={event => setCommercialChoice(event.target.value as typeof commercialChoice)}><option value="">{tr('Choose disclosure…', 'Оберіть розкриття…')}</option><option value="none">{tr('No brand promotion', 'Без просування бренду')}</option><option value="own">{tr("Creator's own brand", 'Власний бренд автора')}</option><option value="branded">{tr('Paid partnership / third-party brand', 'Платне партнерство / сторонній бренд')}</option><option value="both">{tr('Own brand and paid partnership', 'Власний бренд і платне партнерство')}</option></select></label>
      <p>{tr('AI-generated labeling is determined by the immutable approved asset provenance.', 'Позначка ШІ визначається походженням незмінного затвердженого ресурсу.')}</p>
      <label><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /> {tr("By posting, you agree to TikTok's Music Usage Confirmation.", 'Публікуючи, ви погоджуєтеся з TikTok Music Usage Confirmation.')}</label>
    </>} />
}

export function PostPublishing({ api, language, projectId, creativeId, versions }: {
  api: ApiClient; language: Language; projectId: string; creativeId: string
  versions: Array<{ version: number; render_sha256: string; change_note: string }>
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [version, setVersion] = useState(Math.max(0, ...versions.map(item => item.version)))
  const selected = versions.find(item => item.version === version)
  if (!versions.length || !selected) return null
  const common = { api, language, projectId, creativeId, version, renderSha256: selected.render_sha256 }
  const adUrl = `?page=ads&project=${encodeURIComponent(projectId)}&ad_creative=${encodeURIComponent(creativeId)}&ad_version=${version}&destination=WEBSITE`
  return <section className="panel post-publishing" aria-label={tr('Publish approved Post', 'Опублікувати затверджений допис')}>
    <h2>{tr('Publish approved Post', 'Опублікувати затверджений допис')}</h2>
    <p>{tr('Both publishers use this exact approved image. Provider controls and consent are reviewed separately.', 'Обидва канали використовують саме це затверджене зображення. Налаштування й згода перевіряються окремо.')}</p>
    <label>{tr('Approved version', 'Затверджена версія')}<select value={version} onChange={event => setVersion(Number(event.target.value))}>{[...versions].sort((a, b) => b.version - a.version).map(item => <option key={item.version} value={item.version}>v{item.version} · {item.change_note}</option>)}</select></label>
    <div className="post-publishing-actions"><InstagramPanel {...common} /><TikTokPanel {...common} /><a className="primary" href={adUrl}>{tr('Create Instagram ad', 'Створити рекламу Instagram')}</a></div>
  </section>
}
