import { ChevronDown, Play, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { local, type Language } from '../i18n'
import type { Idea } from '../types'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { LavalEngine } from '../components/LavalEngine'

export function IdeasView({ api, language }: { api: ApiClient; language: Language }) {
  const [ideas, setIdeas] = useState<Idea[] | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [showContexts, setShowContexts] = useState(false)
  const [mode, setMode] = useState<'evolution' | 'laval'>('laval')
  const load = () => api.get<{ items: Idea[] }>('/api/v1/ideas?limit=20').then((value) => setIdeas(value.items)).catch((cause: Error) => setError(cause.message))
  useEffect(() => { void load() }, [api])
  const generate = async () => {
    setRunning(true); setError('')
    try { await api.post('/api/v1/generations', { count: 1 }); await load() }
    catch (cause) { setError((cause as Error).message) }
    finally { setRunning(false) }
  }
  if (!ideas && !error && mode === 'evolution') return <Loading />
  return <>
    <PageHeader eyebrow="ЕВОЛЮЦІЯ ІДЕЙ" title="Ідеї" action={mode === 'evolution' ? <div className="header-actions"><button className="secondary" onClick={() => setShowContexts(!showContexts)}><SlidersHorizontal />Контексти</button><button className="primary" onClick={generate} disabled={running}><Play />{running ? 'Запуск…' : 'Нове покоління'}</button></div> : undefined} />
    <div className="mode-switch idea-mode"><button className={mode === 'laval' ? 'selected' : ''} onClick={() => setMode('laval')}>Laval Engine</button><button className={mode === 'evolution' ? 'selected' : ''} onClick={() => setMode('evolution')}>Покоління C01–C10</button></div>
    {mode === 'laval' && <LavalEngine api={api} language={language} />}
    {mode === 'evolution' && <>
    {error && <ErrorState message={error} retry={load} />}
    {showContexts && <ContextManager api={api} />}
    {ideas?.length === 0 && <Empty><LightbulbEmpty /><h2>Чистий старт</h2><p>У базі немає ідей. Покоління 1 запускається тільки вручну.</p><button className="primary large" onClick={generate}><Play />Запустити покоління 1</button></Empty>}
    {ideas && ideas.length > 0 && <section className="ranking-list">
      {ideas.map((idea, index) => <article key={idea.id}>
        <button className="idea-row" onClick={() => setOpen(open === idea.id ? null : idea.id)} aria-expanded={open === idea.id}>
          <span className="rank">{index + 1}</span><div><small>G{idea.generation} · #{idea.id} · {idea.mode}</small><h2>{String(local(idea.title, language))}</h2><p>{String(local(idea.one_liner, language))}</p></div><strong>{idea.score?.toFixed(1) ?? '—'}</strong><ChevronDown />
        </button>
        {open === idea.id && <div className="idea-details">{Object.entries(idea.details).map(([key, value]) => <div key={key}><small>{detailLabel(key, language)}</small><p>{Array.isArray(local(value, language)) ? (local(value, language) as string[]).join(' · ') : String(local(value, language))}</p></div>)}</div>}
      </article>)}
    </section>}</>}
  </>
}

function LightbulbEmpty() { return <div className="empty-mark"><RotateCcw aria-hidden="true" /></div> }

interface ContextRecord { code: string; name: string; prompt_text: string; version: number; active: boolean; revisions: Array<{ version: number }> }

function ContextManager({ api }: { api: ApiClient }) {
  const [kind, setKind] = useState<'idea' | 'post'>('idea')
  const [items, setItems] = useState<ContextRecord[]>([])
  const [selected, setSelected] = useState<ContextRecord | null>(null)
  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const load = () => api.get<{ items: ContextRecord[] }>(`/api/v1/contexts?kind=${kind}`).then((data) => setItems(data.items))
  useEffect(() => { void load() }, [api, kind])
  const choose = (item: ContextRecord) => { setSelected(item); setName(item.name); setPrompt(item.prompt_text) }
  const save = async () => {
    if (!selected) return
    await api.request(`/api/v1/contexts/${kind}/${selected.code}`, { method: 'PUT', body: JSON.stringify({ name, prompt, note: 'web owner revision' }) })
    setSelected(null); await load()
  }
  return <section className="context-manager">
    <div className="mode-switch"><button className={kind === 'idea' ? 'selected' : ''} onClick={() => setKind('idea')}>Ідеї C01–C10</button><button className={kind === 'post' ? 'selected' : ''} onClick={() => setKind('post')}>Пости A01–A10</button></div>
    <div className="context-grid">{items.map((item) => <button key={item.code} onClick={() => choose(item)}><strong>{item.code}</strong><span>v{item.version} · {item.active ? 'УВІМК.' : 'ВИМК.'}</span><p>{item.name}</p></button>)}</div>
    {selected && <div className="context-editor"><div><strong>{selected.code} · нова редакція v{selected.version + 1}</strong><button onClick={() => setSelected(null)} aria-label="Закрити">×</button></div><label>Назва<input value={name} onChange={(event) => setName(event.target.value)} /></label><label>Англійський контракт для LLM<textarea rows={12} value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label><button className="primary large" onClick={save}>Створити редакцію</button></div>}
  </section>
}

const labels: Record<string, string> = {
  customer: 'Клієнт', problem: 'Проблема', product: 'Продукт', business_model: 'Бізнес-модель',
  distribution: 'Дистрибуція', automation: 'Автономність', three_year_exit_logic: 'Шлях до $20 млн за 3 роки',
  key_risks: 'Ключові ризики', first_validation_test: 'Перший тест гіпотези',
}
function detailLabel(key: string, language: Language) { return language === 'uk' ? labels[key] || key.replaceAll('_', ' ') : key.replaceAll('_', ' ') }
