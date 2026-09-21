import { Bot, Paperclip, Send, Trash2, WandSparkles, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import type { ApiClient } from '../../api'
import { imageReferencePayload } from '../ImageReferenceInput'
import { translate, type Language } from '../../i18n'
import type { StudioManualAgentResult } from '../../types'

type ChatMessage = { role: 'user' | 'assistant'; content: string }
type SavedRequest = {
  requestId: string
  endpoint: string
  message: string
  savedAt: string
  status: 'pending' | 'failed' | 'completed'
}

const SAVED_REQUEST_LIMIT = 2
const SAVED_REQUEST_PREFIX = 'ptw-studio-agent-requests-v1'

function savedRequestKey(endpoint: string) {
  const projectId = endpoint.match(/\/projects\/([^/]+)\//)?.[1]
  return `${SAVED_REQUEST_PREFIX}:${projectId || endpoint}`
}

function readSavedRequests(endpoint: string): SavedRequest[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(savedRequestKey(endpoint)) || '[]')
    if (!Array.isArray(value)) return []
    return value.filter((item): item is SavedRequest => (
      item && typeof item === 'object'
      && typeof item.requestId === 'string'
      && typeof item.endpoint === 'string'
      && typeof item.message === 'string'
      && typeof item.savedAt === 'string'
      && ['pending', 'failed', 'completed'].includes(item.status)
    )).slice(0, SAVED_REQUEST_LIMIT)
  } catch { return [] }
}

function writeSavedRequests(endpoint: string, requests: SavedRequest[]) {
  try {
    window.localStorage.setItem(
      savedRequestKey(endpoint), JSON.stringify(requests.slice(0, SAVED_REQUEST_LIMIT)),
    )
  } catch { /* Browser-local recovery must never block Agent mode. */ }
}

function ScreenshotTile({ file, remove, disabled, language }: {
  file: File; remove: () => void; disabled: boolean; language: Language
}) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (typeof URL.createObjectURL !== 'function') return
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL?.(next)
  }, [file])
  const label = translate(language, 'Remove screenshot', 'Видалити скриншот')
  return <figure className="studio-agent-screenshot">
    {url && <img src={url} alt="" />}
    <figcaption title={file.name}>{file.name}</figcaption>
    <button type="button" className="icon-button" aria-label={`${label}: ${file.name}`} disabled={disabled} onClick={remove}><X /></button>
  </figure>
}

export function StudioManualAgent<Configuration, Content>({
  api, language, endpoint, stateSha256, configuration, content, disabled = false,
  onApply, compact = false,
}: {
  api: ApiClient
  language: Language
  endpoint: string
  stateSha256: string
  configuration: Configuration
  content: Content
  compact?: boolean
  disabled?: boolean
  onApply: (
    result: StudioManualAgentResult<Configuration, Content>, screenshots: File[],
  ) => Promise<void> | void
}) {
  const [open, setOpen] = useState(false)
  const [task, setTask] = useState('')
  const [screenshots, setScreenshots] = useState<File[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [savedRequests, setSavedRequests] = useState<SavedRequest[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const titleId = useId()
  const tr = (en: string, uk: string) => translate(language, en, uk)

  useEffect(() => {
    const saved = readSavedRequests(endpoint)
    const recoverable = saved.find(item => item.endpoint === endpoint && item.status !== 'completed')
    setSavedRequests(saved); setMessages([]); setScreenshots([])
    setTask(recoverable?.message || ''); setError(''); setOpen(false)
  }, [endpoint])

  const rememberRequest = (request: SavedRequest) => {
    const next = [request, ...readSavedRequests(endpoint).filter(item => item.requestId !== request.requestId)]
      .slice(0, SAVED_REQUEST_LIMIT)
    writeSavedRequests(endpoint, next)
    setSavedRequests(next)
  }

  const updateSavedRequest = (requestId: string, status: SavedRequest['status']) => {
    const next = readSavedRequests(endpoint).map(item => item.requestId === requestId ? { ...item, status } : item)
    writeSavedRequests(endpoint, next)
    setSavedRequests(next)
  }

  const selectScreenshots = (files: FileList | null) => {
    if (!files) return
    const selected = [...files]
    if (selected.some(file => !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || !file.size || file.size > 8 * 1024 * 1024)) {
      setError(tr('Use PNG, JPEG, or WebP screenshots up to 8 MB each.', 'Використовуйте скриншоти PNG, JPEG або WebP до 8 МБ кожен.'))
      return
    }
    const next = [...screenshots, ...selected].slice(0, 4)
    if (next.reduce((total, file) => total + file.size, 0) > 20 * 1024 * 1024) {
      setError(tr('Screenshots must total no more than 20 MB.', 'Загальний розмір скриншотів не може перевищувати 20 МБ.'))
      return
    }
    setError(''); setScreenshots(next)
  }

  const send = async () => {
    const message = task.trim()
    if (!message || pending || disabled) return
    const requestId = crypto.randomUUID()
    rememberRequest({
      requestId, endpoint, message, savedAt: new Date().toISOString(), status: 'pending',
    })
    setPending(true); setError('')
    try {
      const payloads = await Promise.all(screenshots.map(imageReferencePayload))
      const result = await api.post<StudioManualAgentResult<Configuration, Content>>(endpoint, {
        request_id: requestId, base_sha256: stateSha256,
        message, history: messages.slice(-8),
        configuration, content, screenshots: payloads,
      }, { deadlineMs: 480_000 })
      await onApply(result, screenshots)
      updateSavedRequest(requestId, 'completed')
      setMessages(current => [...current, { role: 'user', content: message }, { role: 'assistant', content: result.reply }].slice(-8) as ChatMessage[])
      setTask(''); setScreenshots([])
      if (fileInput.current) fileInput.current.value = ''
    } catch (cause) {
      updateSavedRequest(requestId, 'failed')
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally { setPending(false) }
  }

  return <section className={`studio-manual-agent ${compact ? 'is-compact' : 'panel'} ${open ? 'is-open' : ''}`} aria-labelledby={titleId}>
    <header>
      {(!compact || open) && <div><small>{tr('AGENT MODE · EDITOR ONLY', 'РЕЖИМ АГЕНТА · ЛИШЕ РЕДАКТОР')}</small><h2 id={titleId}><Bot /> {tr('Adjust it for me', 'Налаштуй це за мене')}</h2><p>{tr('Describe the result. The agent can move every bounded editor control and use existing image generation, but cannot change code, Save, Approve, or Publish.', 'Опишіть результат. Агент може змінювати всі дозволені налаштування редактора й використовувати наявну генерацію зображень, але не може змінювати код, зберігати, затверджувати чи публікувати.')}</p></div>}
      <button type="button" className={open ? 'secondary' : 'primary'} onClick={() => setOpen(value => !value)}><WandSparkles />{open ? tr('Close Agent', 'Закрити агента') : tr('Agent mode', 'Режим агента')}</button>
    </header>
    {open && <div className="studio-agent-body">
      {messages.length > 0 && <div className="studio-agent-messages" aria-live="polite">{messages.map((item, index) => <div key={`${index}-${item.role}`} className={`is-${item.role}`}><strong>{item.role === 'user' ? tr('You', 'Ви') : tr('Agent', 'Агент')}</strong><p>{item.content}</p></div>)}</div>}
      {savedRequests.length > 0 && <section className="studio-agent-recent" aria-label={tr('Recent Agent requests on this Project', 'Останні запити до агента в цьому проєкті')}>
        <header><small>{tr('RECENT REQUESTS · THIS PROJECT', 'ОСТАННІ ЗАПИТИ · ЦЕЙ ПРОЄКТ')}</small><button type="button" className="ghost" disabled={pending} onClick={() => { writeSavedRequests(endpoint, []); setSavedRequests([]) }}>{tr('Clear recent', 'Очистити останні')}</button></header>
        <div>{savedRequests.map(item => <button type="button" className="secondary" key={item.requestId} disabled={pending} onClick={() => setTask(item.message)}><small>{item.endpoint.includes('/landings/') ? tr('Landing', 'Лендінг') : tr('Post', 'Допис')} · {item.status === 'completed' ? tr('completed', 'виконано') : item.status === 'failed' ? tr('failed', 'помилка') : tr('pending', 'очікує')}</small><span>{item.message}</span></button>)}</div>
      </section>}
      <label className="studio-agent-task"><span>{tr('Task', 'Завдання')}</span><textarea value={task} maxLength={4000} disabled={pending || disabled} placeholder={tr('Example: Make the hierarchy calmer, use warmer colors, enlarge the main image, and generate a new premium hero.', 'Наприклад: Зроби ієрархію спокійнішою, використай тепліші кольори, збільш головне зображення та згенеруй нового преміального героя.')} onChange={event => setTask(event.target.value)} onKeyDown={event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') void send() }} /></label>
      {screenshots.length > 0 && <div className="studio-agent-screenshots">{screenshots.map((file, index) => <ScreenshotTile key={`${file.name}-${file.lastModified}-${index}`} file={file} language={language} disabled={pending || disabled} remove={() => setScreenshots(current => current.filter((_, itemIndex) => itemIndex !== index))} />)}</div>}
      <footer>
        <label className="secondary studio-agent-attach"><Paperclip />{tr('Add screenshots', 'Додати скриншоти')}<input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={pending || disabled || screenshots.length >= 4} onChange={event => { selectScreenshots(event.target.files); event.currentTarget.value = '' }} /></label>
        {messages.length > 0 && <button type="button" className="ghost" disabled={pending} onClick={() => setMessages([])}><Trash2 />{tr('Clear chat', 'Очистити чат')}</button>}
        <button type="button" className="primary" disabled={pending || disabled || !task.trim()} onClick={() => void send()}>{pending ? <WandSparkles className="spin" /> : <Send />}{pending ? tr('Adjusting…', 'Налаштовую…') : tr('Apply task', 'Застосувати завдання')}</button>
      </footer>
      {error && <p className="studio-agent-error" role="alert">{error}</p>}
      <small className="studio-agent-privacy">{tr('The latest two text requests are kept only in this browser for the Project. Screenshots are normalized for this turn and are not retained. Review the result, then use the normal Save or Approve control yourself.', 'Два останні текстові запити зберігаються лише в цьому браузері для проєкту. Скриншоти нормалізуються тільки для поточного запиту й не зберігаються. Перевірте результат, а потім самостійно скористайтеся звичайною дією «Зберегти» або «Затвердити».')}</small>
    </div>}
  </section>
}
