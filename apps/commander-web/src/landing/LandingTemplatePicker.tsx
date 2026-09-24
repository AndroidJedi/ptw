import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { ApiFailure, type ApiClient } from '../api'
import type { LandingTemplateReference } from '../types'
import { TemplateImage } from '../views/TemplatesView'
import { LandingDialog } from './LandingCanvas'

export type LandingTemplateChoice = LandingTemplateReference & { name: string; description?: string }
export type LandingTemplateRequest = { request_id: string; template_reference: LandingTemplateReference; source_creative_id: string; source_version: number }
type Preview = { sha256: string; definition_sha256: string }

export function LandingTemplatePicker({ api, language, items, currentId, requestKey, source, onApply, onClose }: {
  api: ApiClient; language: 'en' | 'uk'; items: LandingTemplateChoice[]; currentId: string
  requestKey: string; source: { source_creative_id: string; source_version: number }
  onApply: (request: LandingTemplateRequest) => Promise<void>; onClose: () => void
}) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const [selected, setSelected] = useState<LandingTemplateChoice | null>(null)
  const [pending, setPending] = useState<LandingTemplateRequest | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [previews, setPreviews] = useState<Record<string, Preview>>({})
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(requestKey) || 'null') as LandingTemplateRequest | null
      if (saved?.request_id && saved.source_creative_id === source.source_creative_id && saved.source_version === source.source_version) {
        setPending(saved); setSelected(items.find(item => item.template_sha256 === saved.template_reference.template_sha256) || null)
      }
    } catch { /* Session storage is optional; the same mounted attempt still retries safely. */ }
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const loadPreviews = () => {
      void api.get<{ items: Array<LandingTemplateChoice & { preview_status?: string; previews: Record<string, Preview> }> }>('/api/v1/templates?surface=landing').then(value => {
        if (!active) return
        setPreviews(Object.fromEntries(value.items.filter(item => item.previews?.desktop).map(item => [item.template_sha256, item.previews.desktop])))
        if (value.items.some(item => item.preview_status === 'pending')) timer = setTimeout(loadPreviews, 1500)
      }).catch(() => { /* Catalog choices remain usable when a preview is unavailable. */ })
    }
    loadPreviews()
    return () => { active = false; clearTimeout(timer) }
  }, [api, requestKey]) // eslint-disable-line react-hooks/exhaustive-deps
  const apply = async () => {
    if (!selected && !pending) return
    const request = pending || { ...source, request_id: crypto.randomUUID(), template_reference: {
      template_id: selected!.template_id, template_version: selected!.template_version, template_sha256: selected!.template_sha256,
    } }
    setPending(request); setBusy(true); setError('')
    try { sessionStorage.setItem(requestKey, JSON.stringify(request)) } catch { /* Keep the in-memory request. */ }
    try {
      await onApply(request)
      try { sessionStorage.removeItem(requestKey) } catch { /* Browser storage may be blocked. */ }
      setPending(null); onClose()
    } catch (cause) {
      setError((cause as Error).message)
      if (cause instanceof ApiFailure && [400, 404, 409, 422].includes(cause.details.status || 0)) {
        setPending(null)
        try { sessionStorage.removeItem(requestKey) } catch { /* Browser storage may be blocked. */ }
      }
    } finally { setBusy(false) }
  }
  return <LandingDialog title={tr('Change template', 'Змінити шаблон')} onClose={() => { if (!busy) onClose() }} className="landing-template-dialog">
    <div className="landing-template-content">
      <p>{tr('Choose a design to try. Your previous Landing stays in History.', 'Оберіть дизайн. Попередній лендінг залишиться в історії.')}</p>
      <div className="landing-template-choices">{items.map(item => <article key={item.template_sha256} className={selected?.template_sha256 === item.template_sha256 ? 'is-selected' : ''}>
        {previews[item.template_sha256] ? <TemplateImage api={api} preview={previews[item.template_sha256]} label={item.name} language={language} /> : <div className={`landing-template-skeleton is-${item.template_id}`} aria-hidden="true"><i /><i /><i /></div>}
        <button className="secondary" disabled={busy || !!pending} aria-pressed={selected?.template_sha256 === item.template_sha256} onClick={() => setSelected(item)}>{selected?.template_sha256 === item.template_sha256 && <Check />}{item.name}</button>
        <small>{item.template_id === currentId ? tr('Current design', 'Поточний дизайн') : item.template_id === 'app_showcase' ? tr('Gradient, app screens, walkthrough', 'Градієнт, екрани застосунку, огляд') : tr('Clean layout with a single phone', 'Лаконічний дизайн з одним телефоном')}</small>
      </article>)}</div>
      {error && <p role="alert">{error}</p>}
      {pending && error && <p>{tr('Retry checks the same request and will not create another copy.', 'Повтор перевірить той самий запит без створення ще однієї копії.')}</p>}
      <button className="primary landing-template-apply" disabled={busy || (!selected && !pending)} onClick={() => void apply()}>{busy ? tr('Applying…', 'Застосування…') : pending ? tr('Retry', 'Повторити') : tr('Apply template', 'Застосувати шаблон')}</button>
    </div>
  </LandingDialog>
}
