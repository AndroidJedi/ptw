import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle2, ImagePlus, LoaderCircle, Plus, Rocket, Send, Square, X } from 'lucide-react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import { imageReferencePayload } from './ImageReferenceInput'
import './CommanderChat.css'

type Attachment = { id: string; name: string; mime_type: 'image/png'; byte_count: number; sha256: string }
type Turn = {
  id: string; message: string; reply: string; status: string; error_code: string | null; attachments?: Attachment[]
}
type Chat = { id: string; turns: Turn[] }
type Runtime = {
  target: 'local' | 'hosted'; available: boolean; unavailable_reason: string | null
  chats: { id: string; title: string }[]
  active_turn: { id: string; chat_id: string } | null
}
type Deployment = {
  id: string; base_revision: string; revision: string | null; branch: string
  status: 'preparing' | 'queued' | 'running' | 'succeeded' | 'failed'
  error_code: string | null; workflow_url: string | null; updated_at: string
}
type Release = {
  candidate: {
    available: boolean; unavailable_reason: string | null; deployable?: boolean
    changed_files: string[]; protected_files: string[]
  }
  deployment: Deployment | null
}
const base = '/api/v1/settings/commander'
const deploymentPath = `${base}/deployments`
const active = (turn: Turn) => ['queued', 'running', 'stopping'].includes(turn.status)
const maxImages = 4
const maxImageBytes = 8 * 1024 * 1024
const maxImageTotalBytes = 20 * 1024 * 1024

function DraftImage({ file, remove, language }: { file: File; remove: () => void; language: Language }) {
  const [url, setUrl] = useState('')
  const tr = (en: string, uk: string) => translate(language, en, uk)
  useEffect(() => {
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [file])
  return <div className="commander-image">
    {url && <img src={url} alt={file.name} />}
    <span>{file.name}</span>
    <button type="button" className="secondary" aria-label={`${tr('Remove', 'Видалити')} ${file.name}`} onClick={remove}><X /></button>
  </div>
}

function StoredImage({ api, chatId, turnId, attachment }: {
  api: ApiClient; chatId: string; turnId: string; attachment: Attachment
}) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let disposed = false
    let objectUrl = ''
    void api.image(
      `${base}/chats/${chatId}/turns/${turnId}/attachments/${attachment.id}`,
      attachment.mime_type, attachment.sha256,
    ).then(blob => {
      if (disposed) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch(() => undefined)
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, chatId, turnId, attachment.id, attachment.mime_type, attachment.sha256])
  return <div className="commander-image is-stored">
    {url ? <img src={url} alt={attachment.name} /> : <span className="commander-image-placeholder"><ImagePlus /></span>}
    <span>{attachment.name}</span>
  </div>
}

function ImageRecord({ attachment }: { attachment: Attachment }) {
  return <div className="commander-image is-stored">
    <span className="commander-image-placeholder"><ImagePlus /></span>
    <span>{attachment.name}</span>
  </div>
}

export function CommanderChat({ api, language }: { api: ApiClient; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [open, setOpen] = useState(false)
  const [runtime, setRuntime] = useState<Runtime | null>(null)
  const [chat, setChat] = useState<Chat | null>(null)
  const [draft, setDraft] = useState('')
  const [images, setImages] = useState<File[]>([])
  const [imageError, setImageError] = useState('')
  const [error, setError] = useState('')
  const [pollError, setPollError] = useState('')
  const [release, setRelease] = useState<Release | null>(null)
  const [releaseError, setReleaseError] = useState('')
  const [confirmDeploy, setConfirmDeploy] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const selected = useRef<string | null>(null)
  const pending = useRef<{ chatId: string; message: string; images: string; requestId: string } | null>(null)
  const imageInput = useRef<HTMLInputElement>(null)
  const deploymentRequest = useRef<string | null>(null)
  const alive = useRef(true)
  const running = chat?.turns.find(active)
  const hosted = runtime?.target === 'hosted'

  const load = async () => {
    const detail = await api.get<Runtime>(base)
    const id = selected.current || detail.active_turn?.chat_id || detail.chats[0]?.id
    const value = id ? await api.get<Chat>(`${base}/chats/${id}`) : null
    if (!alive.current) return
    setRuntime(detail)
    if (detail.target === 'hosted') {
      try {
        setRelease(await api.get<Release>(deploymentPath))
        setReleaseError('')
      } catch (cause) {
        setReleaseError((cause as Error).message)
      }
    }
    if (!selected.current || selected.current === id) {
      selected.current = id || null
      setChat(value)
    }
    setPollError('')
  }

  useEffect(() => {
    alive.current = true
    let disposed = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try { await load() } catch (cause) { if (!disposed) setPollError((cause as Error).message) }
      finally {
        if (!disposed) { setLoading(false); timer = setTimeout(() => void poll(), 2000) }
      }
    }
    void poll()
    return () => { disposed = true; alive.current = false; clearTimeout(timer) }
  }, [api])

  const select = async (id: string) => {
    selected.current = id
    setChat(null); setLoading(true); setError('')
    try {
      const value = await api.get<Chat>(`${base}/chats/${id}`)
      if (selected.current === id) setChat(value)
    } catch (cause) { setError((cause as Error).message) }
    finally { setLoading(false) }
  }

  const create = async () => {
    const value = await api.post<Chat>(`${base}/chats`, {})
    selected.current = value.id
    setChat(value)
    return value
  }

  const send = async () => {
    const message = draft.trim()
    if ((!message && !images.length) || busy || running) return
    setBusy(true); setError('')
    try {
      const current = chat || await create()
      // Reconcile an uncertain HTTP outcome using the same request ID.
      const previous = pending.current
      const imageKey = images.map(file => `${file.name}:${file.type}:${file.size}:${file.lastModified}`).join('|')
      const requestId = previous?.chatId === current.id && previous.message === message && previous.images === imageKey
        ? previous.requestId : crypto.randomUUID()
      pending.current = { chatId: current.id, message, images: imageKey, requestId }
      const attachments = await Promise.all(images.map(async file => ({ name: file.name, ...await imageReferencePayload(file) })))
      const body = { message, request_id: requestId, ...(attachments.length ? { attachments } : {}) }
      const value = attachments.length
        ? await api.post<Chat>(`${base}/chats/${current.id}/messages`, body, { deadlineMs: 60_000 })
        : await api.post<Chat>(`${base}/chats/${current.id}/messages`, body)
      setChat(value); setDraft(''); setImages([]); setImageError(''); pending.current = null
      if (imageInput.current) imageInput.current.value = ''
      await load()
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const addImages = (files: FileList | null) => {
    if (!files?.length) return
    const next = [...images, ...Array.from(files)]
    const invalid = next.find(file => !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || !file.size || file.size > maxImageBytes)
    if (invalid) {
      setImageError(tr('Use PNG, JPEG, or WebP images up to 8 MB each.', 'Оберіть PNG, JPEG або WebP до 8 МБ кожне.'))
    } else if (next.length > maxImages) {
      setImageError(tr('Attach no more than 4 images to one message.', 'Додайте не більше 4 зображень до одного повідомлення.'))
    } else if (next.reduce((total, file) => total + file.size, 0) > maxImageTotalBytes) {
      setImageError(tr('Attached images must total at most 20 MB.', 'Загальний розмір зображень має бути не більше 20 МБ.'))
    } else {
      setImages(next); setImageError('')
    }
    if (imageInput.current) imageInput.current.value = ''
  }

  const stop = async () => {
    if (!chat || !running) return
    setBusy(true)
    try { setChat(await api.post<Chat>(`${base}/chats/${chat.id}/turns/${running.id}/stop`, {})) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const deploy = async () => {
    if (!release?.candidate.deployable || busy || running) return
    setBusy(true); setReleaseError('')
    try {
      const requestId = deploymentRequest.current || crypto.randomUUID()
      deploymentRequest.current = requestId
      const value = await api.post<Release>(deploymentPath, {
        confirmation: 'DEPLOY NEW CHANGES', request_id: requestId,
      }, { deadlineMs: 30_000 })
      setRelease(value); setConfirmDeploy(false); deploymentRequest.current = null
    } catch (cause) { setReleaseError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const deploymentLabel = (deployment: Deployment) => deployment.status === 'succeeded'
    ? tr('Deployment completed.', 'Розгортання завершено.')
    : deployment.status === 'failed'
      ? tr('Deployment failed safely. Production retained its last accepted release.', 'Розгортання безпечно завершилося помилкою. Production зберіг останній прийнятий реліз.')
      : deployment.status === 'preparing'
        ? tr('Preparing the exact release candidate…', 'Підготовка точної версії для релізу…')
        : deployment.status === 'queued'
          ? tr('Waiting for the off-server build runner…', 'Очікування зовнішнього build runner…')
          : tr('Building, verifying, and deploying…', 'Збірка, перевірка та розгортання…')

  const failure = (turn: Turn) => {
    const outcome = turn.status === 'cancelled' ? tr('Request stopped.', 'Запит зупинено.')
      : turn.status === 'interrupted' ? tr('Request interrupted by a service restart.', 'Запит перервано перезапуском сервісу.')
        : turn.error_code === 'timeout' ? tr('Commander reached the execution time limit.', 'Commander досяг ліміту часу виконання.')
          : tr('Commander could not finish this request. Check the local Codex sign-in and runtime.', 'Commander не зміг завершити запит. Перевірте локальний вхід у Codex та його роботу.')
    return `${outcome}\n${tr('Any edits already made remain in the checkout. Review them before sending a follow-up; this request will not restart automatically.', 'Уже внесені зміни залишаються в коді. Перегляньте їх перед наступним повідомленням; запит не перезапуститься автоматично.')}\n${tr('Turn', 'Запит')}: ${turn.id} · ${turn.error_code}`
  }

  return <section className="panel settings-card commander-card" aria-labelledby="commander-title">
    <header><div><small>{tr('DEVELOPMENT MODE', 'РЕЖИМ РОЗРОБКИ')}</small><h2 id="commander-title"><Bot /> Commander · GOD mode</h2></div><span className="commander-target">{hosted ? tr('Hosted checkout', 'Код на сервері') : tr('Local checkout', 'Локальний код')}</span></header>
    <button className={open ? 'secondary' : 'primary'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? tr('Close chat', 'Закрити чат') : tr('Open Commander chat', 'Відкрити чат Commander')}</button>
    {error && <p className="settings-error" role="alert">{error}</p>}
    {pollError && <p className="settings-error" role="alert">{pollError}</p>}
    {open && <div className="commander-chat">
      {loading && <p role="status">{tr('Loading Commander…', 'Завантаження Commander…')}</p>}
      {runtime && !runtime.available && <p role="alert">{runtime.unavailable_reason === 'skill_missing'
        ? tr('The Commander GOD-mode skill is missing or invalid. Restore the canonical skill and refresh this page.', 'Навичка Commander GOD mode відсутня або некоректна. Відновіть канонічну навичку та оновіть сторінку.')
        : hosted
          ? tr('Commander is unavailable on the PTW server. Refresh ChatGPT Authorization, then retry.', 'Commander недоступний на сервері PTW. Оновіть авторизацію ChatGPT і повторіть спробу.')
          : tr('Commander is unavailable. Install Codex CLI, sign in locally, and restart the local app.', 'Commander недоступний. Встановіть Codex CLI, увійдіть локально та перезапустіть застосунок.')}</p>}
      <div className="commander-toolbar">
        <label>{tr('Conversation', 'Розмова')}<select value={chat?.id || ''} disabled={busy || loading} onChange={event => void select(event.target.value)}>
          <option value="" disabled>{tr('New conversation', 'Нова розмова')}</option>
          {runtime?.chats.map(item => <option value={item.id} key={item.id}>{item.title || tr('New conversation', 'Нова розмова')}</option>)}
        </select></label>
        <button className="secondary" disabled={busy || loading || !!runtime?.active_turn} onClick={() => {
          setBusy(true); setError('')
          void create().then(load).catch(cause => setError(cause.message)).finally(() => setBusy(false))
        }}><Plus />{tr('New chat', 'Новий чат')}</button>
      </div>
      {runtime?.active_turn && runtime.active_turn.chat_id !== chat?.id && <button className="secondary" onClick={() => void select(runtime.active_turn!.chat_id)}>{tr('Open active request', 'Відкрити активний запит')}</button>}
      <div className="commander-messages" role="log" aria-label={tr('Commander conversation', 'Розмова з Commander')} aria-live="polite">
        {!chat?.turns.length && <p className="commander-empty">{tr('Describe what you want to change. Commander can inspect the code, implement it, and run checks.', 'Опишіть бажану зміну. Commander може перевірити код, реалізувати її та виконати тести.')}</p>}
        {chat?.turns.map(turn => <div className="commander-turn" key={turn.id}>
          <article className="commander-message is-owner"><strong>{tr('You', 'Ви')}</strong>{turn.message && <p>{turn.message}</p>}
            {!!turn.attachments?.length && <div className="commander-images is-history">{turn.attachments.map(attachment => active(turn)
              ? <StoredImage api={api} chatId={chat.id} turnId={turn.id} attachment={attachment} key={attachment.id} />
              : <ImageRecord attachment={attachment} key={attachment.id} />)}</div>}
          </article>
          <article className="commander-message"><strong>Commander</strong>
            {active(turn) ? <p role="status"><LoaderCircle className="spin" />{turn.status === 'stopping' ? tr('Stopping…', 'Зупиняється…') : tr('Working on your request…', 'Виконується ваш запит…')}</p>
              : turn.status === 'completed' ? <p>{turn.reply}</p>
                : <p className="settings-error">{failure(turn)}</p>}
          </article>
        </div>)}
      </div>
      <form onSubmit={event => { event.preventDefault(); void send() }}>
        <label htmlFor="commander-message">{tr('Message Commander', 'Повідомлення Commander')}</label>
        <textarea id="commander-message" value={draft} maxLength={8000} rows={4} onChange={event => setDraft(event.target.value)} placeholder={tr('Add a carousel creation tab…', 'Додай вкладку створення каруселей…')} />
        {!!images.length && <div className="commander-images">{images.map((file, index) => <DraftImage file={file} language={language} remove={() => { setImages(current => current.filter((_item, itemIndex) => itemIndex !== index)); setImageError('') }} key={`${file.name}-${file.size}-${file.lastModified}-${index}`} />)}</div>}
        <div className="commander-attachment-controls">
          <label className="secondary commander-attach-button"><ImagePlus />{tr('Add images', 'Додати зображення')}<input ref={imageInput} type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={busy || !!running} aria-label={tr('Add images to Commander conversation', 'Додати зображення до розмови Commander')} onChange={event => addImages(event.target.files)} /></label>
          <small>{tr('PNG, JPEG, or WebP · up to 4 images / 20 MB · deleted after the request.', 'PNG, JPEG або WebP · до 4 зображень / 20 МБ · видаляються після запиту.')}</small>
        </div>
        {imageError && <p className="settings-error" role="alert">{imageError}</p>}
        <footer><span>{draft.length}/8000</span>{running
          ? <button className="secondary" type="button" disabled={busy || running.status === 'stopping'} onClick={() => void stop()}><Square />{tr('Stop', 'Зупинити')}</button>
          : <button className="primary" type="submit" disabled={busy || loading || !runtime?.available || !!runtime.active_turn || (!draft.trim() && !images.length)}><Send />{tr('Send', 'Надіслати')}</button>}</footer>
      </form>
      {hosted && <section className="commander-release" aria-labelledby="commander-release-title">
        <header><div><small>{tr('PRODUCTION RELEASE', 'PRODUCTION РЕЛІЗ')}</small><h3 id="commander-release-title"><Rocket />{tr('Deploy new changes', 'Розгорнути нові зміни')}</h3></div></header>
        {release?.deployment && <div className={`commander-deployment is-${release.deployment.status}`} role="status">
          {release.deployment.status === 'succeeded' ? <CheckCircle2 /> : release.deployment.status === 'failed' ? <AlertTriangle /> : <LoaderCircle className="spin" />}
          <div><strong>{deploymentLabel(release.deployment)}</strong><code>{release.deployment.revision?.slice(0, 12) || release.deployment.id.slice(0, 12)}</code>
            {release.deployment.workflow_url && <a href={release.deployment.workflow_url} target="_blank" rel="noreferrer">{tr('Open release details', 'Відкрити деталі релізу')}</a>}</div>
        </div>}
        {release?.candidate.protected_files.length ? <p className="settings-error" role="alert">{tr('These changes include protected deployment infrastructure and must use the normal operations release:', 'Ці зміни містять захищену інфраструктуру розгортання та потребують звичайного operational release:')} {release.candidate.protected_files.join(', ')}</p> : null}
        {releaseError && <p className="settings-error" role="alert">{releaseError}</p>}
        {!confirmDeploy ? <button className="primary commander-deploy-button" disabled={busy || !!running || !release?.candidate.deployable || !!release?.deployment && ['preparing', 'queued', 'running'].includes(release.deployment.status)} onClick={() => setConfirmDeploy(true)}><Rocket />{tr('DEPLOY NEW CHANGES', 'РОЗГОРНУТИ НОВІ ЗМІНИ')}</button>
          : <div className="commander-deploy-confirm" role="alertdialog" aria-labelledby="commander-deploy-confirm-title">
            <strong id="commander-deploy-confirm-title">{tr('Deploy these changes to production?', 'Розгорнути ці зміни в production?')}</strong>
            <p>{tr('PTW will freeze the exact candidate, build it outside the VPS, run checks, and use the preserving rollout with automatic rollback.', 'PTW зафіксує точну версію, збере її поза VPS, виконає перевірки та застосує preserving rollout з автоматичним rollback.')}</p>
            <div><button className="secondary" disabled={busy} onClick={() => setConfirmDeploy(false)}>{tr('Cancel', 'Скасувати')}</button><button className="primary" disabled={busy} onClick={() => void deploy()}>{busy ? <LoaderCircle className="spin" /> : <Rocket />}{tr('Confirm deployment', 'Підтвердити розгортання')}</button></div>
          </div>}
        {release && !release.candidate.changed_files.length && !['preparing', 'queued', 'running'].includes(release.deployment?.status || '') && <p className="commander-scope">{tr('No undeployed GOD-mode changes are ready.', 'Немає готових нерозгорнутих змін GOD mode.')}</p>}
      </section>}
    </div>}
  </section>
}
