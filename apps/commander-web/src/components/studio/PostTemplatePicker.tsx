import { useEffect, useRef, useState } from 'react'
import { LayoutTemplate, X } from 'lucide-react'
import { ApiFailure, type ApiClient } from '../../api'
import type { Language } from '../../i18n'
import type { StudioPhoneMetricsConfiguration, StudioPhoneMetricsContent, StudioPhoneMetricsDetail } from '../../types'
import { TemplateImage } from '../../views/TemplatesView'

type Choice = { surface: 'post'; template_id: string; template_version: number; template_sha256: string; name: string; previews: Record<string, { sha256: string; definition_sha256: string }> }
export function PostTemplatePicker({ api, language, basePath, detail, configuration, content, disabled, onApply }: {
  api: ApiClient; language: Language; basePath: string; detail: StudioPhoneMetricsDetail
  configuration: StudioPhoneMetricsConfiguration; content: StudioPhoneMetricsContent
  disabled: boolean; onApply: (value: StudioPhoneMetricsDetail) => void
}) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Choice[] | null>(null)
  const [selected, setSelected] = useState<Choice | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<Record<string, unknown> | null>(null)
  const [retry, setRetry] = useState(0)
  const panel = useRef<HTMLDivElement>(null)
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  useEffect(() => {
    if (!open) return
    let cancelled = false
    const previous = document.activeElement as HTMLElement | null
    panel.current?.focus()
    setItems(null); setError('')
    void api.get<{ items: Choice[] }>('/api/v1/templates?surface=post', { deadlineMs: 120_000 }).then(value => {
      if (!cancelled) setItems(value.items)
    }).catch(cause => { if (!cancelled) setError(cause.message) })
    return () => { cancelled = true; previous?.focus() }
  }, [api, open, retry])
  const apply = async () => {
    if (!selected) return
    const body = pending || { request_id: crypto.randomUUID(), base_sha256: detail.state_sha256,
      template_reference: { surface: 'post', template_id: selected.template_id, template_version: selected.template_version, template_sha256: selected.template_sha256 },
      configuration, content }
    setPending(body); setBusy(true); setError('')
    try {
      const value = await api.post<StudioPhoneMetricsDetail>(`${basePath}/templates/apply`, body, { deadlineMs: 90_000 })
      setPending(null); setOpen(false); onApply(value)
    } catch (cause) {
      setError((cause as Error).message)
      if (cause instanceof ApiFailure && [400, 404, 409, 422].includes(cause.details.status || 0)) setPending(null)
    } finally { setBusy(false) }
  }
  return <>
    <button className="secondary" disabled={disabled} onClick={() => { setSelected(null); setOpen(true) }}><LayoutTemplate />{tr('Change template', 'Змінити шаблон')}</button>
    {open && <div className="modal-backdrop"><div className="panel post-template-dialog" ref={panel} role="dialog" aria-modal="true" aria-label={tr('Change template', 'Змінити шаблон')} tabIndex={-1} onKeyDown={event => {
      if (event.key === 'Escape' && !busy && !pending) setOpen(false)
      if (event.key === 'Tab') {
        const controls = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]') || [])
        const target = event.shiftKey ? controls.at(-1) : controls[0]
        if (document.activeElement === (event.shiftKey ? controls[0] : controls.at(-1)) || document.activeElement === panel.current) { event.preventDefault(); target?.focus() }
      }
    }}>
      <header><div><h2>{tr('Choose a look for this Post', 'Оберіть вигляд допису')}</h2><p>{tr('Your copy and image carry over. Approved versions stay in history.', 'Текст і зображення збережуться. Схвалені версії залишаться в історії.')}</p></div><button className="icon-button" disabled={busy || !!pending} aria-label={tr('Close', 'Закрити')} onClick={() => setOpen(false)}><X /></button></header>
      {error && <p role="alert">{error}</p>}
      {!items && !error && <p role="status">{tr('Loading templates…', 'Завантаження шаблонів…')}</p>}
      {!items && error && <button onClick={() => setRetry(v => v + 1)}>{tr('Retry', 'Повторити')}</button>}
      <div className="post-template-choices">{items?.map(item => <article key={`${item.template_id}:${item.template_version}`} className={selected === item ? 'is-selected' : ''}>
        <TemplateImage api={api} preview={item.previews.desktop} label={item.name} />
        <button className="secondary" aria-pressed={selected === item} disabled={busy || !!pending} onClick={() => setSelected(item)}>{item.name} · v{item.template_version}</button>
      </article>)}</div>
      {items?.length === 1 && <p>{tr('Accept a new Post design in Templates to add more choices here.', 'Прийміть новий дизайн допису в Шаблонах, щоб він з’явився тут.')}</p>}
      {items?.length === 0 && <p>{tr('No accepted Post templates yet.', 'Ще немає прийнятих шаблонів дописів.')}</p>}
      <footer><button className="primary" disabled={!selected || busy} onClick={() => void apply()}>{busy ? tr('Applying…', 'Застосування…') : pending ? tr('Retry same request', 'Повторити той самий запит') : tr('Apply to this Post', 'Застосувати до допису')}</button></footer>
    </div></div>}
  </>
}
