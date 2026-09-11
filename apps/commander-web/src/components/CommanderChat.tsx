import { useEffect, useRef, useState } from 'react'
import { Bot, History, ImagePlus, LoaderCircle, Plus, Reply, Rocket, Send, Square, X } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import { imageReferencePayload } from './ImageReferenceInput'
import './CommanderChat.css'

type Options = { mode: 'plan' | 'build'; model: string; effort: string }
type Model = { id: string; name: string; default_effort: string; efforts: string[]; default: boolean }
type Turn = { id: string; message: string; reply: string; status: string; mode?: string; model?: string; effort?: string; reply_to_message_id?: string; error_code?: string; attachments?: { id: string; name: string }[] }
type Question = { id: string; status: string; answers?: Record<string, string[]>; payload: { questions: { id: string; question: string; options?: { label: string; description: string }[] }[] } }
type Chat = { id: string; turns: Turn[]; preferences?: Options; questions?: Question[]; event_cursor?: number; before?: number; has_more?: boolean; releases?: { request_id: string; status: string }[] }
type Runtime = { target: string; available: boolean; chats: { id: string; title: string }[]; active_turn?: { id: string; chat_id: string } }
type Deployment = { id: string; revision?: string; status: string; phase?: string; workflow_url?: string; chat_id?: string }
type Release = { candidate: { available: boolean; deployable?: boolean; changed_files: string[]; unavailable_reason?: string }; deployment?: Deployment; history?: Deployment[] }
const base = '/api/v1/settings/commander'
const active = (turn: Turn) => ['queued', 'running', 'stopping'].includes(turn.status)
const storage = {
  get(key: string) { try { return localStorage.getItem('ptw-commander-' + key) || '' } catch { return '' } },
  set(key: string, value: string) { try { localStorage.setItem('ptw-commander-' + key, value) } catch { /* private browser */ } },
}

function Questions({ question, api, chatId, language, reload }: { question: Question; api: ApiClient; chatId: string; language: Language; reload: () => Promise<void> }) {
  const [answers, setAnswers] = useState<Record<string, string>>(() => { try { return JSON.parse(storage.get('answer-' + question.id) || '{}') } catch { return {} } })
  useEffect(() => storage.set('answer-' + question.id, JSON.stringify(answers)), [answers, question.id])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef<{ key: string; id: string } | null>((() => { try { return JSON.parse(storage.get('answer-request-' + question.id) || 'null') } catch { return null } })())
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <form className="commander-question" onSubmit={event => {
    event.preventDefault(); setBusy(true); setError('')
    const key = JSON.stringify(answers)
    const id = pending.current?.key === key ? pending.current.id : crypto.randomUUID()
    pending.current = { key, id }
    storage.set('answer-request-' + question.id, JSON.stringify(pending.current))
    void api.post(`${base}/chats/${chatId}/questions/${question.id}/answers`, {
      request_id: id, answers: Object.fromEntries(Object.entries(answers).map(([name, value]) => [name, [value]])),
    }).then(reload).catch(cause => setError(cause.message)).finally(() => setBusy(false))
  }}>
    {question.payload.questions.map(item => <fieldset key={item.id} disabled={busy}>
      <legend>{item.question}</legend>
      {item.options?.map(option => <label className="commander-answer-option" key={option.label}>
        <input type="radio" name={`${question.id}-${item.id}`} checked={answers[item.id] === option.label} onChange={() => setAnswers({ ...answers, [item.id]: option.label })} />
        <span>{option.label}<small>{option.description}</small></span>
      </label>)}
      <input aria-label={`${tr('Your answer', 'Ваша відповідь')}: ${item.question}`} placeholder={tr('Or write your answer…', 'Або напишіть відповідь…')} value={answers[item.id] || ''} onChange={event => setAnswers({ ...answers, [item.id]: event.target.value })} />
    </fieldset>)}
    {error && <p role="alert">{error}</p>}
    <button className="primary" disabled={busy || question.payload.questions.some(q => !answers[q.id]?.trim())}>{tr('Send answer', 'Надіслати відповідь')}</button>
  </form>
}

function DraftImage({ file, remove }: { file: File; remove: () => void }) {
  const [url, setUrl] = useState('')
  useEffect(() => { const next = URL.createObjectURL(file); setUrl(next); return () => URL.revokeObjectURL(next) }, [file])
  return <div className="commander-image"><img src={url} alt={file.name} /><span>{file.name}</span><button type="button" aria-label={`Remove ${file.name}`} onClick={remove}><X /></button></div>
}

export function CommanderChat({ api, language }: { api: ApiClient; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [runtime, setRuntime] = useState<Runtime | null>(null)
  const [chat, setChat] = useState<Chat | null>(null)
  const [models, setModels] = useState<Model[]>([])
  const [modes, setModes] = useState<string[]>(['build'])
  const [options, setOptions] = useState<Options>({ mode: 'build', model: '', effort: '' })
  const [drawer, setDrawer] = useState(false)
  const [draft, setDraft] = useState('')
  const [images, setImages] = useState<File[]>([])
  const [replyTo, setReplyTo] = useState<Turn | null>(null)
  const [release, setRelease] = useState<Release | null>(null)
  const [error, setError] = useState('')
  const [activity, setActivity] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const selected = useRef(storage.get('selected'))
  const initialized = useRef('')
  const pending = useRef<{ key: string; id: string } | null>(null)
  const deploymentRequest = useRef(storage.get('deployment-request'))
  const eventCursor = useRef(0)
  const composer = useRef<HTMLTextAreaElement>(null)
  const timeline = useRef<HTMLDivElement>(null)
  const imageInput = useRef<HTMLInputElement>(null)
  const follow = useRef(true)
  const running = chat?.turns.find(active)
  const selectedModel = models.find(model => model.id === options.model)

  const installChat = (value: Chat) => {
    if (initialized.current !== value.id) {
      initialized.current = value.id
      setDraft(storage.get('draft-' + value.id)); setReplyTo(null); setImages([])
      if (value.preferences?.model) setOptions(value.preferences)
      eventCursor.current = value.event_cursor || 0
      follow.current = true
    }
    setChat(old => old?.id === value.id && old.turns.length > value.turns.length
      ? { ...value, turns: [...old.turns.filter(t => !value.turns.some(n => n.id === t.id)), ...value.turns], before: old.before, has_more: old.has_more }
      : value)
  }

  const load = async () => {
    const detail = await api.get<Runtime>(base)
    setRuntime(detail)
    if (selected.current && !detail.chats.some(c => c.id === selected.current)) selected.current = ''
    const id = selected.current || detail.active_turn?.chat_id || detail.chats[0]?.id
    if (id) {
      selected.current = id; storage.set('selected', id)
      const value = await api.get<Chat>(`${base}/chats/${id}`)
      if (selected.current === id) installChat(value)
    }
    if (detail.target === 'hosted') setRelease(await api.get<Release>(`${base}/deployments${id ? '?chat_id=' + id : ''}`))
  }

  useEffect(() => {
    let disposed = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        await load()
        if (selected.current) {
          const id = selected.current
          const value = await api.get<{ cursor: number; events: { kind: string; payload: { type?: string } }[] }>(`${base}/chats/${id}/events?after=${eventCursor.current}`)
          if (selected.current === id) {
            eventCursor.current = value.cursor
            const last = value.events.filter(e => e.kind === 'activity').at(-1)
            if (last) setActivity(last.payload.type || '')
          }
        }
      } catch (cause) { if (!disposed) setError((cause as Error).message) }
      finally { if (!disposed) { setLoading(false); timer = setTimeout(() => void poll(), 1500) } }
    }
    void poll()
    void api.get<{ models: Model[]; modes: string[] }>(`${base}/capabilities`, { deadlineMs: 60_000 }).then(value => {
      if (disposed) return
      setModels(value.models); setModes(value.modes)
      const model = value.models.find(m => m.default) || value.models[0]
      if (model) setOptions(old => old.model ? old : { mode: 'build', model: model.id, effort: model.default_effort })
    }).catch(cause => { if (!disposed) setError(cause.message) })
    return () => { disposed = true; clearTimeout(timer) }
  }, [api]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (follow.current && timeline.current) timeline.current.scrollTop = timeline.current.scrollHeight }, [chat?.turns.map(t => t.reply + t.status).join('|'), chat?.questions?.length])
  useEffect(() => {
    const viewport = window.visualViewport
    const resize = () => document.documentElement.style.setProperty('--commander-viewport', `${viewport?.height || window.innerHeight}px`)
    resize(); viewport?.addEventListener('resize', resize)
    return () => { viewport?.removeEventListener('resize', resize); document.documentElement.style.removeProperty('--commander-viewport') }
  }, [])
  const changeDraft = (text: string) => { setDraft(text); if (chat) storage.set('draft-' + chat.id, text) }
  const choose = async (id: string) => {
    selected.current = id; storage.set('selected', id); setDrawer(false); setError('')
    const value = await api.get<Chat>(`${base}/chats/${id}`)
    if (selected.current === id) installChat(value)
  }
  const create = async () => {
    const value = await api.post<Chat>(`${base}/chats`, {})
    selected.current = value.id; storage.set('selected', value.id); installChat(value); setDrawer(false)
    return value
  }
  const setPreference = (next: Options) => {
    setOptions(next)
    if (chat) void api.post(`${base}/chats/${chat.id}/preferences`, next).catch(cause => setError(cause.message))
  }
  const send = async (override?: { message: string; reply: Turn }) => {
    const message = override?.message || draft.trim()
    if ((!message && !images.length) || busy || !options.model) return
    setBusy(true); setError(''); follow.current = true
    try {
      const current = chat || await create()
      const selection: Options = { ...options, ...(override ? { mode: 'build' as const } : {}) }
      const reply = override?.reply || replyTo
      const key = JSON.stringify({ chat: current.id, message, selection, reply: reply?.id, images: images.map(f => [f.name, f.size, f.lastModified]) })
      if (!pending.current) { try { pending.current = JSON.parse(storage.get('request-' + current.id) || 'null') } catch { /* invalid stored request */ } }
      const requestId = pending.current?.key === key ? pending.current.id : crypto.randomUUID()
      pending.current = { key, id: requestId }
      storage.set('request-' + current.id, JSON.stringify(pending.current))
      const attachments = await Promise.all(images.map(async file => ({ name: file.name, ...await imageReferencePayload(file) })))
      setChat(await api.post<Chat>(`${base}/chats/${current.id}/messages`, {
        message, request_id: requestId, ...selection, ...(reply ? { reply_to_message_id: reply.id } : {}), ...(attachments.length ? { attachments } : {}),
      }, { deadlineMs: 60_000 }))
      setDraft(''); storage.set('draft-' + current.id, ''); setImages([]); setReplyTo(null); pending.current = null
      storage.set('request-' + current.id, '')
      if (override) setOptions(selection)
      if (imageInput.current) imageInput.current.value = ''
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const deploy = async () => {
    setBusy(true); setError('')
    try {
      const current = chat || await create()
      const id = deploymentRequest.current || crypto.randomUUID()
      deploymentRequest.current = id; storage.set('deployment-request', id)
      setChat(await api.post<Chat>(`${base}/chats/${current.id}/deploy`, { request_id: id }, { deadlineMs: 30_000 }))
      deploymentRequest.current = ''; storage.set('deployment-request', '')
      await load()
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const deployment = release?.deployment
  const releaseActive = !!deployment && ['preparing', 'queued', 'running'].includes(deployment.status)
  const releaseLabel = deployment?.status === 'succeeded' ? tr('Deployment completed', 'Розгортання завершено')
    : deployment?.status === 'failed' ? tr('Deployment failed — open details', 'Помилка розгортання — відкрити деталі')
      : deployment?.status === 'bookkeeping_required' ? tr('Live — source synchronization needs attention', 'Опубліковано — потрібна синхронізація коду')
        : tr('Building, checking and deploying…', 'Збірка, перевірка та розгортання…')
  const releasePhase = deployment?.phase && ({ application: tr('Updating services', 'Оновлення сервісів'), hosting: tr('Publishing website', 'Публікація сайту'), infrastructure: tr('Applying configuration', 'Застосування конфігурації'), rolled_back: tr('Previous release restored', 'Попередній реліз відновлено'), recovery_failed: tr('Recovery needs operator attention', 'Відновлення потребує уваги оператора') } as Record<string, string>)[deployment.phase]

  return <section className="commander-workspace" aria-label="Commander">
    <header className="commander-header"><div><Bot /><h1>Commander <small>GOD mode</small></h1></div><div>
      <button className="secondary" aria-label={tr('Conversation history', 'Історія розмов')} aria-expanded={drawer} onClick={() => setDrawer(!drawer)}><History /></button>
      <button className="secondary" aria-label={tr('New chat', 'Новий чат')} disabled={busy} onClick={() => void create().catch(cause => setError(cause.message))}><Plus /></button>
    </div></header>
    {drawer && <aside className="commander-history" aria-label={tr('Conversations', 'Розмови')}>{runtime?.chats.map(item => <button key={item.id} aria-current={item.id === chat?.id ? 'page' : undefined} onClick={() => void choose(item.id).catch(cause => setError(cause.message))}>{item.title || tr('New conversation', 'Нова розмова')}</button>)}</aside>}
    <div className="commander-timeline" ref={timeline} role="log" aria-label={tr('Commander conversation', 'Розмова з Commander')} onScroll={() => { const node = timeline.current; if (node) follow.current = node.scrollHeight - node.scrollTop - node.clientHeight < 90 }}>
      {loading && <p role="status">{tr('Loading Commander…', 'Завантаження Commander…')}</p>}
      {!loading && !chat?.turns.length && <div className="commander-welcome"><Bot /><h2>{tr('What should we build?', 'Що будемо створювати?')}</h2><p>{tr('Discuss an idea, make a plan, or ask for a change. When ready, tell Commander to deploy it.', 'Обговоріть ідею, складіть план або попросіть внести зміни. Коли буде готово — попросіть Commander розгорнути їх.')}</p></div>}
      {chat?.has_more && <button className="secondary" onClick={() => { void api.get<Chat>(`${base}/chats/${chat.id}?before=${chat.before}`).then(value => setChat({ ...chat, turns: [...value.turns, ...chat.turns], before: value.before, has_more: value.has_more })) }}>{tr('Earlier messages', 'Попередні повідомлення')}</button>}
      {chat?.turns.map(turn => <div className="commander-turn" key={turn.id}>
        <article className="commander-message is-owner"><small>{tr('You', 'Ви')}{turn.reply_to_message_id && ` · ${tr('reply', 'відповідь')}`}</small><p>{turn.message}</p>{turn.attachments?.map(a => <span className="commander-attachment-record" key={a.id}><ImagePlus />{a.name}</span>)}</article>
        {(turn.reply || active(turn) || !['steered', 'completed'].includes(turn.status)) && <article className="commander-message is-agent"><small>Commander · {turn.mode === 'plan' ? 'Plan' : 'Build'}</small>
          {turn.reply && <Markdown remarkPlugins={[remarkGfm]}>{turn.reply.replace(/<\/?proposed_plan>/g, '')}</Markdown>}
          {active(turn) && <p className="commander-working" role="status"><LoaderCircle className="spin" />{tr('Working… You can reply below.', 'Працюю… Можете відповісти нижче.')} {activity === 'fileChange' ? tr('Editing files', 'Редагування файлів') : activity === 'commandExecution' ? tr('Running a check', 'Виконання перевірки') : ''}</p>}
          {!active(turn) && !['completed', 'steered'].includes(turn.status) && <p role="alert">{tr('This task stopped before completion. Reply to continue; existing changes are retained.', 'Завдання зупинилося до завершення. Відповідайте, щоб продовжити; внесені зміни збережено.')}</p>}
          {turn.reply && <div className="commander-message-actions"><button aria-label={tr('Reply to message', 'Відповісти на повідомлення')} onClick={() => { setReplyTo(turn); composer.current?.focus() }}><Reply />{tr('Reply', 'Відповісти')}</button>
            {turn.mode === 'plan' && turn.status === 'completed' && <button disabled={!!running || busy} onClick={() => void send({ message: tr('Implement this plan.', 'Реалізуй цей план.'), reply: turn })}>{tr('Implement plan', 'Реалізувати план')}</button>}
            <details><summary>{tr('Details', 'Деталі')}</summary><small>{turn.model} · {turn.effort} · {turn.status}<br />{turn.id}{turn.error_code && ` · ${turn.error_code}`}</small></details>
          </div>}
        </article>}
      </div>)}
      {chat?.questions?.filter(q => q.status === 'pending').map(question => <Questions key={question.id} question={question} api={api} chatId={chat.id} language={language} reload={load} />)}
      {chat?.questions?.filter(q => q.status !== 'pending').map(question => <details key={question.id} className="commander-question"><summary>{tr('Clarification', 'Уточнення')} · {question.status}</summary>{question.payload.questions.map(item => <p key={item.id}>{item.question}<br />{question.answers?.[item.id]?.join(', ') || tr('Reply below to continue this interrupted question.', 'Відповідайте нижче, щоб продовжити це перерване уточнення.')}</p>)}</details>)}
      {deployment && (!deployment.chat_id || deployment.chat_id === chat?.id) && <article className="commander-release-message" role="status"><Rocket /><div><strong>{releaseLabel}</strong><small>{deployment.revision?.slice(0, 12)}</small>{deployment.workflow_url && <a href={deployment.workflow_url} target="_blank" rel="noreferrer">{tr('Release details', 'Деталі релізу')}</a>}</div></article>}
      {releasePhase && <p className="commander-changes" role="status">{releasePhase}</p>}
      {chat?.releases?.filter(item => item.status !== 'submitted').map(item => <p key={item.request_id} className="commander-changes" role={item.status === 'failed' ? 'alert' : 'status'}>{item.status === 'failed' ? tr('Deployment could not start. Review the current changes, then retry Deploy.', 'Не вдалося почати розгортання. Перегляньте зміни й повторіть спробу.') : tr('Sending completed changes to deployment…', 'Передаю завершені зміни на розгортання…')}</p>)}
      {release?.history?.filter(item => item.id !== deployment?.id).map(item => <details className="commander-release-message" key={item.id}><summary>{tr('Previous release', 'Попередній реліз')} · {item.status}</summary><small>{item.revision?.slice(0, 12)}</small>{item.workflow_url && <a href={item.workflow_url} target="_blank" rel="noreferrer">{tr('Release details', 'Деталі релізу')}</a>}</details>)}
      {release?.candidate.changed_files.length ? <div className="commander-changes"><span>{tr('New changes ready', 'Нові зміни готові')} · {release.candidate.changed_files.length} {tr('files', 'файлів')}</span><details><summary>{tr('View changes', 'Переглянути зміни')}</summary>{release.candidate.changed_files.map(path => <code key={path}>{path}</code>)}</details></div> : null}
    </div>
    <form className="commander-composer" onSubmit={event => { event.preventDefault(); void send() }}>
      {error && <div className="commander-error" role="alert"><span>{error}</span><button type="button" aria-label={tr('Dismiss error', 'Закрити помилку')} onClick={() => setError('')}><X /></button></div>}
      {replyTo && <div className="commander-reply-preview"><span>{tr('Replying to Commander', 'Відповідь Commander')}<small>{replyTo.reply.slice(0, 160)}</small></span><button type="button" aria-label={tr('Cancel reply', 'Скасувати відповідь')} onClick={() => setReplyTo(null)}><X /></button></div>}
      {!!images.length && <div className="commander-images">{images.map((file, index) => <DraftImage file={file} key={`${file.name}-${index}`} remove={() => setImages(images.filter((_, i) => i !== index))} />)}</div>}
      <textarea ref={composer} aria-label={tr('Message Commander', 'Повідомлення Commander')} value={draft} rows={2} maxLength={8000} placeholder={tr('Message Commander…', 'Напишіть Commander…')} onChange={event => changeDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); void send() } }} />
      <div className="commander-composer-controls"><div className="commander-options">
        <label><span>{tr('Mode', 'Режим')}</span><select aria-label={tr('Mode', 'Режим')} value={options.mode} onChange={event => setPreference({ ...options, mode: event.target.value as Options['mode'] })}>{modes.map(mode => <option key={mode} value={mode}>{mode === 'plan' ? 'Plan' : 'Build'}</option>)}</select></label>
        <label className="commander-model"><span>{tr('Model', 'Модель')}</span><select aria-label={tr('Model', 'Модель')} value={options.model} onChange={event => { const model = models.find(m => m.id === event.target.value)!; setPreference({ ...options, model: model.id, effort: model.efforts.includes(options.effort) ? options.effort : model.default_effort }) }}>{!models.length && <option value="">{tr('Loading…', 'Завантаження…')}</option>}{models.map(model => <option key={model.id} value={model.id}>{model.name}</option>)}</select></label>
        <label><span>{tr('Effort', 'Зусилля')}</span><select aria-label={tr('Effort', 'Зусилля')} value={options.effort} onChange={event => setPreference({ ...options, effort: event.target.value })}>{selectedModel?.efforts.map(effort => <option key={effort} value={effort}>{effort}</option>)}</select></label>
      </div><div className="commander-send-actions">
        <label className="commander-attach" title={tr('Attach images', 'Додати зображення')}><ImagePlus /><input ref={imageInput} type="file" accept="image/png,image/jpeg,image/webp" multiple aria-label={tr('Attach images', 'Додати зображення')} onChange={event => {
          const next = [...images, ...Array.from(event.target.files || [])]
          if (next.length > 4 || next.some(f => !['image/png', 'image/jpeg', 'image/webp'].includes(f.type) || f.size > 8 * 1024 * 1024) || next.reduce((total, f) => total + f.size, 0) > 20 * 1024 * 1024) setError(tr('Use up to four PNG, JPEG or WebP images, 8 MB each and 20 MB total.', 'До чотирьох PNG, JPEG або WebP, по 8 МБ і 20 МБ загалом.'))
          else setImages(next)
        }} /></label>
        {runtime?.target === 'hosted' && <button type="button" className="secondary" disabled={busy || !!runtime.active_turn || releaseActive || !release?.candidate.deployable || options.mode === 'plan'} onClick={() => void deploy()}><Rocket />{tr('Deploy', 'Розгорнути')}</button>}
        {running && <button type="button" className="secondary" aria-label={tr('Stop', 'Зупинити')} onClick={() => void api.post(`${base}/chats/${chat!.id}/turns/${running.id}/stop`, {}).then(load).catch(cause => setError(cause.message))}><Square /></button>}
        <button className="primary" disabled={busy || !runtime?.available || !options.model || (!draft.trim() && !images.length)} aria-label={tr('Send', 'Надіслати')}><Send /></button>
      </div></div>
      {running && <small className="commander-next-turn">{tr('Replies steer current work. Mode, model and effort changes apply to the next task.', 'Відповіді уточнюють поточну роботу. Зміни режиму, моделі та зусиль діють із наступного завдання.')}</small>}
    </form>
  </section>
}
