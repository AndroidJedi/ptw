import { useEffect, useRef, useState } from 'react'
import { Bot, LoaderCircle, Plus, Send, Square } from 'lucide-react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import './CommanderChat.css'

type Turn = {
  id: string; message: string; reply: string; status: string; error_code: string | null
}
type Chat = { id: string; turns: Turn[] }
type Runtime = {
  target: 'local'; available: boolean; unavailable_reason: string | null
  chats: { id: string; title: string }[]
  active_turn: { id: string; chat_id: string } | null
}
const base = '/api/v1/settings/commander'
const active = (turn: Turn) => ['queued', 'running', 'stopping'].includes(turn.status)

export function CommanderChat({ api, language }: { api: ApiClient; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [open, setOpen] = useState(false)
  const [runtime, setRuntime] = useState<Runtime | null>(null)
  const [chat, setChat] = useState<Chat | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [pollError, setPollError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const selected = useRef<string | null>(null)
  const pending = useRef<{ chatId: string; message: string; requestId: string } | null>(null)
  const alive = useRef(true)
  const running = chat?.turns.find(active)

  const load = async () => {
    const detail = await api.get<Runtime>(base)
    const id = selected.current || detail.active_turn?.chat_id || detail.chats[0]?.id
    const value = id ? await api.get<Chat>(`${base}/chats/${id}`) : null
    if (!alive.current) return
    setRuntime(detail)
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
    if (!message || busy || running) return
    setBusy(true); setError('')
    try {
      const current = chat || await create()
      // Reconcile an uncertain HTTP outcome using the same request ID.
      const previous = pending.current
      const requestId = previous?.chatId === current.id && previous.message === message ? previous.requestId : crypto.randomUUID()
      pending.current = { chatId: current.id, message, requestId }
      const value = await api.post<Chat>(`${base}/chats/${current.id}/messages`, { message, request_id: requestId })
      setChat(value); setDraft(''); pending.current = null
      await load()
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const stop = async () => {
    if (!chat || !running) return
    setBusy(true)
    try { setChat(await api.post<Chat>(`${base}/chats/${chat.id}/turns/${running.id}/stop`, {})) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const failure = (turn: Turn) => {
    const outcome = turn.status === 'cancelled' ? tr('Request stopped.', 'Запит зупинено.')
      : turn.status === 'interrupted' ? tr('Request interrupted by a service restart.', 'Запит перервано перезапуском сервісу.')
        : turn.error_code === 'timeout' ? tr('Commander reached the execution time limit.', 'Commander досяг ліміту часу виконання.')
          : tr('Commander could not finish this request. Check the local Codex sign-in and runtime.', 'Commander не зміг завершити запит. Перевірте локальний вхід у Codex та його роботу.')
    return `${outcome}\n${tr('Any edits already made remain in the checkout. Review them before sending a follow-up; this request will not restart automatically.', 'Уже внесені зміни залишаються в коді. Перегляньте їх перед наступним повідомленням; запит не перезапуститься автоматично.')}\n${tr('Turn', 'Запит')}: ${turn.id} · ${turn.error_code}`
  }

  return <section className="panel settings-card commander-card" aria-labelledby="commander-title">
    <header><div><small>{tr('DEVELOPMENT MODE', 'РЕЖИМ РОЗРОБКИ')}</small><h2 id="commander-title"><Bot /> Commander · GOD mode</h2></div><span className="commander-target">{tr('Local checkout', 'Локальний код')}</span></header>
    <p>{tr('Chat with Commander to fix PTW, change any part of the app, or build new functionality. Try adding a carousel creation tab or improving Telegram controls.', 'Спілкуйтеся з Commander, щоб виправляти PTW, змінювати застосунок або додавати функції. Наприклад, створіть вкладку каруселей чи покращте керування Telegram.')}</p>
    <p className="commander-scope">{tr('Changes apply directly to this local checkout using your local Codex sign-in. VPS execution and deployment are not enabled in this version.', 'Зміни вносяться прямо в локальний код через ваш локальний вхід у Codex. Виконання на VPS та розгортання в цій версії ще не ввімкнено.')}</p>
    <p className="commander-scope">{tr('Commander maintains its GOD-mode skills and relevant PTW skills as it learns from verified changes.', 'Commander підтримує навички GOD mode та відповідні навички PTW на основі перевірених змін.')}</p>
    <button className={open ? 'secondary' : 'primary'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? tr('Close chat', 'Закрити чат') : tr('Open Commander chat', 'Відкрити чат Commander')}</button>
    {error && <p className="settings-error" role="alert">{error}</p>}
    {pollError && <p className="settings-error" role="alert">{pollError}</p>}
    {open && <div className="commander-chat">
      {loading && <p role="status">{tr('Loading Commander…', 'Завантаження Commander…')}</p>}
      {runtime && !runtime.available && <p role="alert">{runtime.unavailable_reason === 'skill_missing'
        ? tr('The Commander GOD-mode skill is missing or invalid. Restore the canonical skill and refresh this page.', 'Навичка Commander GOD mode відсутня або некоректна. Відновіть канонічну навичку та оновіть сторінку.')
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
          <article className="commander-message is-owner"><strong>{tr('You', 'Ви')}</strong><p>{turn.message}</p></article>
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
        <footer><span>{draft.length}/8000</span>{running
          ? <button className="secondary" type="button" disabled={busy || running.status === 'stopping'} onClick={() => void stop()}><Square />{tr('Stop', 'Зупинити')}</button>
          : <button className="primary" type="submit" disabled={busy || loading || !runtime?.available || !!runtime.active_turn || !draft.trim()}><Send />{tr('Send', 'Надіслати')}</button>}</footer>
      </form>
    </div>}
  </section>
}
