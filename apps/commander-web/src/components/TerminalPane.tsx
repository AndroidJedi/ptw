import { useEffect, useRef, useState } from 'react'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import type { ApiClient } from '../api'

export function TerminalPane({ api }: { api: ApiClient }) {
  const host = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'closed' | 'connecting' | 'open'>('closed')
  const socket = useRef<WebSocket | null>(null)
  const terminal = useRef<Terminal | null>(null)

  useEffect(() => () => { socket.current?.close(); terminal.current?.dispose() }, [])

  const connect = async () => {
    if (!host.current || status !== 'closed') return
    setStatus('connecting')
    const term = new Terminal({ cursorBlink: true, fontSize: 13, theme: { background: '#000000', foreground: '#ffffff', cursor: '#ffffff' } })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(host.current)
    fit.fit()
    term.writeln('\x1b[1;35mАВАРІЙНИЙ ROOT-ДОСТУП\x1b[0m  журнал сеансу не зберігається\r\n')
    const ws = new WebSocket(await api.websocketUrl('/api/v1/root-sessions'))
    socket.current = ws
    terminal.current = term
    term.onData((data) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: 'input', data })))
    term.onResize(({ cols, rows }) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: 'resize', cols, rows })))
    ws.onopen = () => { setStatus('open'); ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows })) }
    ws.onmessage = (event) => {
      try { const message = JSON.parse(event.data) as { type: string; data?: string }; if (message.type === 'output' && message.data) term.write(message.data) }
      catch { term.write(String(event.data)) }
    }
    ws.onclose = () => { term.writeln('\r\n\x1b[31mСеанс закрито\x1b[0m'); setStatus('closed') }
  }

  return <section className="terminal-card">
    <div><strong>Аварійний доступ · root</strong><span>15 хв простою · максимум 60 хв · журнал не зберігається</span></div>
    <button className="danger" onClick={connect} disabled={status !== 'closed'}>{status === 'closed' ? 'Відкрити root PTY' : status === 'connecting' ? 'Підключення…' : 'Сесія активна'}</button>
    <div ref={host} className="terminal-host" aria-label="Root-термінал" />
  </section>
}
