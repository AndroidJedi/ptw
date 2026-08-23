import { BookOpen, ExternalLink, RefreshCcw, Server } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { PageHeader } from '../components/State'
import { TerminalPane } from '../components/TerminalPane'
import { MarkdownDoc } from '../components/MarkdownDoc'

interface SystemState { git_revision: string; services: Record<string, unknown>; emergency_stop: boolean; reset: { permitted: boolean; target?: string } }
interface Doc { path: string; title: string; body: string }

export function MoreView({ api }: { api: ApiClient }) {
  const [tab, setTab] = useState<'system' | 'docs' | 'terminal'>('system')
  const [system, setSystem] = useState<SystemState | null>(null)
  const [docs, setDocs] = useState<Doc[]>([])
  const [selected, setSelected] = useState<Doc | null>(null)
  const [resetConfirmation, setResetConfirmation] = useState('')
  const [resetStatus, setResetStatus] = useState('')
  const loadSystem = () => api.get<SystemState>('/api/v1/system/health').then(setSystem)
  useEffect(() => { loadSystem().catch(() => undefined); api.get<{ items: Doc[] }>('/api/v1/docs?limit=50').then((data) => { setDocs(data.items); setSelected(data.items[0] || null) }).catch(() => undefined) }, [api])
  return <>
    <PageHeader eyebrow="КЕРУВАННЯ ВЛАСНИКА" title="Документація / Система" />
    <div className="tabs" role="tablist"><button className={tab === 'system' ? 'selected' : ''} onClick={() => setTab('system')}><Server />Система</button><button className={tab === 'docs' ? 'selected' : ''} onClick={() => setTab('docs')}><BookOpen />Документація</button><button className={tab === 'terminal' ? 'selected' : ''} onClick={() => setTab('terminal')}># Root</button></div>
    {tab === 'system' && <section className="system-panel">
      <div className="revision"><small>РЕДАКЦІЯ GIT</small><code>{system?.git_revision || 'недоступно'}</code></div>
      <div className="reset-gate"><small>ГЛОБАЛЬНЕ АВАРІЙНЕ КЕРУВАННЯ</small><strong className={system?.emergency_stop ? 'bad' : 'ok'}>{system?.emergency_stop ? 'ЗУПИНЕНО' : 'Система активна'}</strong><button className={system?.emergency_stop ? '' : 'danger-outline'} onClick={async () => { setResetStatus('Оновлення…'); try { await api.post('/api/v1/system/emergency-stop', { active: !system?.emergency_stop }); await loadSystem(); setResetStatus(system?.emergency_stop ? 'Систему відновлено' : 'Аварійну зупинку увімкнено') } catch (cause) { setResetStatus((cause as Error).message) } }}>{system?.emergency_stop ? 'Відновити систему' : 'Аварійно зупинити'}</button></div>
      <div className="service-list">{Object.entries(system?.services || {}).map(([name, status]) => { const label = typeof status === 'string' ? status : JSON.stringify(status); return <div key={name}><span>{name}</span><strong className={label === 'ok' || label.includes('"ready":true') ? 'ok' : 'bad'}>{label}</strong></div> })}</div>
      <div className="reset-gate"><small>НЕЗВОРОТНА РУЙНІВНА ДІЯ · без backup · {system?.reset.target || 'ptw_commander.public only'}</small><input value={resetConfirmation} onChange={(event) => setResetConfirmation(event.target.value)} placeholder="RESET PTW PRODUCTION" /><button className="danger-outline" disabled={!system?.reset.permitted || resetConfirmation !== 'RESET PTW PRODUCTION'} onClick={async () => { setResetStatus('Виконується…'); try { await api.post('/api/v1/system/reset', { confirmation: resetConfirmation }); setResetStatus('Чисте скидання завершено') } catch (cause) { setResetStatus((cause as Error).message) } }}><RefreshCcw />Чисте скидання</button>{resetStatus && <p role="status">{resetStatus}</p>}</div>
    </section>}
    {tab === 'docs' && <div className="docs-layout"><nav aria-label="Документація">{docs.map((doc) => <button key={doc.path} className={selected?.path === doc.path ? 'selected' : ''} onClick={() => setSelected(doc)}>{doc.title}<ExternalLink /></button>)}</nav>{selected && <article className="markdown"><MarkdownDoc body={selected.body} /></article>}</div>}
    {tab === 'terminal' && <TerminalPane api={api} />}
  </>
}
