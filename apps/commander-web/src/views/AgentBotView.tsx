import { ArrowRight, Bot, BrainCircuit, CheckCircle2, CircleAlert, Clock3, Plus, RefreshCw, Send, ShieldCheck, Square, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import './AgentBotView.css'

type Agent = { id: string; name: string; role: string; description: string; status?: string; active_runs?: number }
type Permission = { agent_id: string; capability: string; mode: 'allowed' | 'approval_required' | 'denied'; reason: string }
type BotMessage = { id: string; sender: 'user' | 'commander' | 'business_researcher'; recipient: string; kind: string; text: string; data: Record<string, any>; created_at?: string }
type Action = { id: string; action_type: string; mode: string; status: string; reason: string; payload: Record<string, any>; created_at?: string }
type Task = { id: string; status: string; context: Record<string, any>; result: Record<string, any>; error?: string }
type Conversation = { id: string; title: string; status: string }
type Detail = { conversation: Conversation; messages: BotMessage[]; tasks: Task[]; actions: Action[]; agents: Agent[]; permissions: Permission[] }
type Status = { available: boolean; agents: Agent[]; permissions: Permission[]; conversations: Conversation[] }

const base = '/api/v1/agent-bot'
const selectedKey = 'ptw-agent-bot-conversation'

function statusLabel(status: string, language: Language) {
  const labels: Record<string, [string, string]> = {
    idle: ['Idle', 'Очікує'], working: ['Working', 'Працює'], waiting_user: ['Needs your input', 'Потрібна ваша відповідь'],
    waiting_approval: ['Needs approval', 'Потрібне підтвердження'], completed: ['Completed', 'Завершено'], failed: ['Failed', 'Помилка'],
    queued: ['Queued', 'У черзі'], running: ['Running', 'Виконується'], cancelled: ['Stopped', 'Зупинено'],
  }
  const pair = labels[status] || [status, status]
  return language === 'uk' ? pair[1] : pair[0]
}

function AgentBadge({ agent, language }: { agent: Agent; language: Language }) {
  const isResearcher = agent.id === 'business_researcher'
  return <article className="agent-bot-agent-card">
    <div className="agent-bot-agent-icon">{isResearcher ? <BrainCircuit /> : <Bot />}</div>
    <div className="agent-bot-agent-copy"><strong>{agent.name}</strong><small>{agent.role}</small><p>{agent.description}</p></div>
    <span className={`agent-bot-status-dot ${agent.status === 'working' ? 'is-working' : ''}`} title={statusLabel(agent.status || 'idle', language)} />
  </article>
}

export function AgentBotView({ api, language }: { api: ApiClient; language: Language }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [status, setStatus] = useState<Status | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const currentTask = detail?.tasks.at(-1)
  const pendingAction = detail?.actions.find(action => action.status === 'pending')
  const isWorking = ['working', 'waiting_user', 'waiting_approval'].includes(detail?.conversation.status || '')
  const report = detail?.messages.find(message => message.kind === 'final_result')?.data.report
  const activeAgent = status?.agents.find(agent => agent.status === 'working')
  const permissions = useMemo(() => status?.permissions || detail?.permissions || [], [detail?.permissions, status?.permissions])

  const loadConversation = async (id: string) => setDetail(await api.get<Detail>(`${base}/conversations/${id}`))

  useEffect(() => {
    let mounted = true
    void (async () => {
      try {
        const current = await api.get<Status>(base)
        if (!mounted) return
        setStatus(current)
        let id = ''
        try { id = localStorage.getItem(selectedKey) || '' } catch { /* private storage */ }
        if (!id || !current.conversations.some(item => item.id === id)) id = current.conversations[0]?.id || ''
        if (!id) {
          const created = await api.post<{ conversation: Conversation }>(`${base}/conversations`, { title: tr('Business idea research', 'Дослідження бізнес-ідеї') })
          id = created.conversation.id
        }
        try { localStorage.setItem(selectedKey, id) } catch { /* private storage */ }
        await loadConversation(id)
      } catch (cause) { if (mounted) setError((cause as Error).message) }
      finally { if (mounted) setLoading(false) }
    })()
    return () => { mounted = false }
  }, [api, language])

  useEffect(() => {
    if (!detail || !isWorking) return
    const timer = window.setInterval(() => {
      void loadConversation(detail.conversation.id).catch(cause => setError((cause as Error).message))
      void api.get<Status>(base).then(setStatus).catch(() => undefined)
    }, 1400)
    return () => window.clearInterval(timer)
  }, [api, detail?.conversation.id, detail?.conversation.status, isWorking])

  const createConversation = async () => {
    setBusy(true); setError('')
    try {
      const created = await api.post<{ conversation: Conversation }>(`${base}/conversations`, { title: tr('Business idea research', 'Дослідження бізнес-ідеї') })
      try { localStorage.setItem(selectedKey, created.conversation.id) } catch { /* private storage */ }
      await loadConversation(created.conversation.id)
      const next = await api.get<Status>(base); setStatus(next)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const send = async () => {
    if (!detail || !draft.trim() || busy) return
    setBusy(true); setError('')
    try {
      const requestId = crypto.randomUUID()
      await api.post(`${base}/conversations/${detail.conversation.id}/messages`, { request_id: requestId, message: draft.trim() })
      setDraft('')
      await loadConversation(detail.conversation.id)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const decide = async (action: Action, decision: 'approved' | 'rejected') => {
    if (!detail || busy) return
    setBusy(true); setError('')
    try {
      await api.post(`${base}/conversations/${detail.conversation.id}/actions/${action.id}`, { decision })
      await loadConversation(detail.conversation.id)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  const stop = async () => {
    if (!detail || !currentTask || busy) return
    setBusy(true)
    try { await api.post(`${base}/conversations/${detail.conversation.id}/tasks/${currentTask.id}/stop`, {}); await loadConversation(detail.conversation.id) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  return <section className="agent-bot-workspace" aria-label="Commander Bot">
    <header className="agent-bot-header">
      <div className="agent-bot-title"><div className="agent-bot-mark"><Sparkles /></div><div><p className="eyebrow">PTW · MULTI-AGENT MVP</p><h1>Commander Bot</h1><p>{tr('A supervised workspace for autonomous agent collaboration.', 'Контрольований простір для автономної взаємодії агентів.')}</p></div></div>
      <button className="agent-bot-new" type="button" disabled={busy} onClick={() => void createConversation()}><Plus />{tr('New research', 'Нове дослідження')}</button>
    </header>
    {error && <div className="agent-bot-error" role="alert"><CircleAlert /><span>{error}</span><button type="button" onClick={() => setError('')} aria-label={tr('Dismiss error', 'Закрити помилку')}>×</button></div>}
    <div className="agent-bot-layout">
      <aside className="agent-bot-pane agent-bot-agents-pane" aria-label={tr('Agents pane', 'Панель агентів')}>
        <div className="agent-bot-pane-head"><div><span className="agent-bot-kicker">{tr('Pane 01', 'Панель 01')}</span><h2>{tr('Agents', 'Агенти')}</h2></div><span className="agent-bot-count">{(status?.agents || detail?.agents || []).length}</span></div>
        <p className="agent-bot-pane-intro">{tr('The registered workers in this session.', 'Зареєстровані учасники цієї сесії.')}</p>
        <div className="agent-bot-agent-list">{(status?.agents || detail?.agents || []).map(agent => <AgentBadge key={agent.id} agent={agent} language={language} />)}</div>
        <div className="agent-bot-pane-note"><CheckCircle2 /><div><strong>{tr('Mediated by Commander', 'Через Commander')}</strong><p>{tr('No specialist can call you or a tool directly.', 'Спеціаліст не може напряму звернутися до вас або інструмента.')}</p></div></div>
      </aside>
      <main className="agent-bot-pane agent-bot-conversation">
        <div className="agent-bot-conversation-head"><div><span className="agent-bot-kicker">{tr('Pane 02 · Hub-and-spoke', 'Панель 02 · hub-and-spoke')}</span><h2>{detail?.conversation.title || tr('Loading conversation…', 'Завантаження розмови…')}</h2></div><div className={`agent-bot-session-status is-${detail?.conversation.status || 'idle'}`}>{detail && statusLabel(detail.conversation.status, language)}</div></div>
        <div className="agent-bot-thread" role="log" aria-label={tr('Agent conversation', 'Розмова агентів')}>
          {loading && <p className="agent-bot-empty">{tr('Connecting to the agent workspace…', 'Підключення до простору агентів…')}</p>}
          {!loading && detail?.messages.length === 0 && <div className="agent-bot-empty agent-bot-empty-start"><Sparkles /><h3>{tr('Start with a business idea', 'Почніть із бізнес-ідеї')}</h3><p>{tr('Describe the problem, product or service. Business Researcher will decide what it needs to know and ask Commander for the next action.', 'Опишіть проблему, продукт або сервіс. Business Researcher сам визначить, чого бракує, і попросить Commander про наступну дію.')}</p></div>}
          {detail?.messages.map(message => <article className={`agent-bot-message is-${message.sender}`} key={message.id}>
            <div className="agent-bot-message-meta">{message.sender === 'user' ? tr('You', 'Ви') : message.sender === 'commander' ? 'Commander' : 'Business Researcher'}<span>{message.kind === 'agent_request' ? tr('request to Commander', 'запит до Commander') : message.kind === 'action_result' ? tr('action result', 'результат дії') : message.kind === 'final_result' ? tr('final assessment', 'підсумкова оцінка') : ''}</span></div>
            <p>{message.text}</p>
            {message.kind === 'agent_request' && <div className="agent-bot-request-note"><ArrowRight />{message.data.reason}</div>}
            {message.kind === 'final_result' && message.data.report && <div className="agent-bot-report"><div><strong>{tr('Audience & problem', 'Аудиторія та проблема')}</strong><p>{message.data.report.audience}</p><p>{message.data.report.problem}</p></div><div><strong>{tr('Demand & monetization', 'Попит і монетизація')}</strong><p>{message.data.report.demand}</p><p>{message.data.report.monetization}</p></div><div><strong>{tr('Risks', 'Ризики')}</strong><ul>{message.data.report.risks?.map((item: string) => <li key={item}>{item}</li>)}</ul></div><div><strong>{tr('Recommended next steps', 'Наступні кроки')}</strong><ol>{message.data.report.next_steps?.map((item: string) => <li key={item}>{item}</li>)}</ol></div><small>{message.data.report.research_note}</small></div>}
          </article>)}
          {isWorking && detail && <div className="agent-bot-live" role="status"><span className="agent-bot-live-pulse" />{activeAgent ? `${activeAgent.name} · ${statusLabel('working', language)}` : tr('Coordinating the next step…', 'Координація наступного кроку…')}<RefreshCw className="agent-bot-spin" /></div>}
        </div>
        <form className="agent-bot-composer" onSubmit={event => { event.preventDefault(); void send() }}><textarea aria-label={tr('Message Commander Bot', 'Повідомлення Commander Bot')} value={draft} onChange={event => setDraft(event.target.value)} placeholder={detail?.conversation.status === 'waiting_user' ? tr('Answer Commander’s question…', 'Відповідайте на запит Commander…') : tr('Describe a business idea…', 'Опишіть бізнес-ідею…')} maxLength={8000} rows={3} /><div><small>{tr('All agent messages are mediated by Commander.', 'Усі повідомлення агентів проходять через Commander.')}</small><div><button type="button" className="secondary" disabled={!isWorking || busy} onClick={() => void stop()}><Square />{tr('Stop', 'Зупинити')}</button><button className="primary" disabled={busy || !draft.trim() || !detail}><Send />{tr('Send', 'Надіслати')}</button></div></div></form>
      </main>
      <aside className="agent-bot-pane agent-bot-controls-pane" aria-label={tr('Task and permissions pane', 'Панель задач і дозволів')}>
        <div className="agent-bot-pane-head"><div><span className="agent-bot-kicker">{tr('Pane 03 · Control', 'Панель 03 · контроль')}</span><h2>{tr('Task & permissions', 'Задача та дозволи')}</h2></div><ShieldCheck className="agent-bot-pane-icon" /></div>
        <section className="agent-bot-control-section"><div className="agent-bot-panel-title"><h3>{tr('Task state', 'Стан задачі')}</h3><Clock3 /></div><div className="agent-bot-task-line"><span>{tr('Business research', 'Дослідження бізнес-ідеї')}</span><strong>{currentTask ? statusLabel(currentTask.status, language) : statusLabel('idle', language)}</strong></div>{currentTask && <div className="agent-bot-task-steps"><span className={['running', 'waiting_user', 'waiting_approval', 'completed'].includes(currentTask.status) ? 'is-done' : ''}>1 · {tr('Brief received', 'Бриф отримано')}</span><span className={currentTask.context?.target_market ? 'is-done' : ''}>2 · {tr('Market clarified', 'Ринок уточнено')}</span><span className={currentTask.context?.market_research ? 'is-done' : ''}>3 · {tr('Research action', 'Дослідницька дія')}</span><span className={currentTask.status === 'completed' ? 'is-done' : ''}>4 · {tr('Assessment delivered', 'Оцінку сформовано')}</span></div>}</section>
        <section className="agent-bot-control-section"><div className="agent-bot-panel-title"><h3>{tr('Permission model', 'Модель дозволів')}</h3><ShieldCheck /></div><p className="agent-bot-panel-intro">{tr('Every requested action is evaluated before execution.', 'Кожна дія проходить перевірку до виконання.')}</p><div className="agent-bot-permissions">{permissions.filter(item => item.agent_id === 'business_researcher').map(item => <div key={item.capability}><span>{item.capability}</span><em className={`mode-${item.mode}`}>{item.mode === 'approval_required' ? tr('approval', 'підтвердження') : item.mode === 'allowed' ? tr('allowed', 'дозволено') : tr('denied', 'заборонено')}</em></div>)}</div></section>
        {pendingAction && <section className="agent-bot-control-section agent-bot-control-approval"><div className="agent-bot-panel-title"><h3>{tr('Owner approval required', 'Потрібне підтвердження власника')}</h3><ShieldCheck /></div><p>{pendingAction.reason}</p><small>{tr('Requested action', 'Запитана дія')}: {pendingAction.action_type}</small><div className="agent-bot-approval-actions"><button type="button" className="primary" disabled={busy} onClick={() => void decide(pendingAction, 'approved')}>{tr('Approve', 'Підтвердити')}</button><button type="button" className="secondary" disabled={busy} onClick={() => void decide(pendingAction, 'rejected')}>{tr('Reject', 'Відхилити')}</button></div></section>}
        <section className="agent-bot-control-section agent-bot-architecture"><div className="agent-bot-panel-title"><h3>{tr('Communication rule', 'Правило комунікації')}</h3><CheckCircle2 /></div><div className="agent-bot-flow"><span>Business Researcher</span><ArrowRight /><span>Commander</span><ArrowRight /><span>{tr('You / tools', 'Ви / інструменти')}</span></div><p>{tr('The specialist never calls the user or tools directly. Commander remains the single coordination point.', 'Спеціаліст не звертається до користувача або інструментів напряму. Commander залишається єдиною точкою координації.')}</p></section>
      </aside>
    </div>
  </section>
}
