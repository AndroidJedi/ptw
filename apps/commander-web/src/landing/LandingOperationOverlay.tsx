import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { LoaderCircle, AlertCircle, RefreshCcw } from 'lucide-react'
import type { Language } from '../i18n'
import { imageReferencePayload, type ImageReference } from '../components/ImageReferenceInput'
import './operation.css'

export type LandingOperation = {
  operation_id: string; request_id: string; landing_id: string; project_id: string
  kind: 'agent' | 'image'; status: 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'
  phase: string; started_at: string; updated_at: string; revision: number
  jobs: Array<{ slot: string; status: string; sha256?: string; error?: { category: string; code: string } }>
  error?: { phase: string; category: string; code: string; retryable: boolean } | null
  result?: Record<string, unknown> | null
}

export function LandingOperationOverlay({ language, operation, phase, error, retry, close, jobs: initialJobs, startedAt }: {
  language: Language; operation?: LandingOperation | null; phase?: string; error?: string
  jobs?: LandingOperation['jobs']; startedAt?: string
  retry?: (references?: ImageReference[]) => void; close?: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const [tick, setTick] = useState(Date.now())
  const began = useRef(Date.now())
  const [references, setReferences] = useState<ImageReference[]>()
  const [referenceError, setReferenceError] = useState('')
  const uk = language === 'uk'
  const tr = (en: string, ua: string) => uk ? ua : en
  const failed = phase !== 'checking' && Boolean(error || operation?.error || ['failed', 'interrupted'].includes(operation?.status || ''))
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const dialog = ref.current!
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '')
    dialog.focus()
    const timer = window.setInterval(() => setTick(Date.now()), 1000)
    return () => { window.clearInterval(timer); dialog.close?.(); document.body.style.overflow = overflow; previous?.focus() }
  }, [])
  const stage = phase || operation?.phase || 'preparing'
  const descriptions: Record<string, string> = {
    preparing: tr('Preparing your request and checking the current Landing.', 'Готуємо запит і перевіряємо поточний лендінг.'),
    queued: tr('Waiting for an available generation worker.', 'Очікуємо вільного виконавця генерації.'),
    interpreting: tr('The agent is reading your instruction and preparing the requested changes.', 'Агент аналізує вашу інструкцію та готує потрібні зміни.'),
    applying: tr('Applying the requested draft settings before generating images.', 'Застосовуємо налаштування чернетки перед генерацією зображень.'),
    images: tr('Generating the requested images. Each completed image is retained independently.', 'Генеруємо потрібні зображення. Кожен завершений результат зберігається окремо.'),
    composing: tr('Writing the Landing sections from the approved source.', 'Готуємо розділи лендінгу із затвердженого джерела.'),
    generating_images: tr('Generating the template’s app screens and artwork.', 'Генеруємо екрани застосунку та зображення шаблону.'),
    preview: tr('Loading the updated preview.', 'Завантажуємо оновлений попередній перегляд.'),
    checking: tr('Checking whether the server has already completed this request.', 'Перевіряємо, чи сервер уже завершив цей запит.'),
  }
  const categories: Record<string, string> = {
    timeout: tr('The provider did not finish within its time limit. Retry checks the existing job before requesting more work.', 'Провайдер не завершив роботу вчасно. Перед повторенням перевіримо наявне завдання.'),
    provider: tr('The image or agent service could not complete this step. Completed changes remain available.', 'Сервіс зображень або агента не завершив цей крок. Виконані зміни збережено.'),
    interrupted: tr('The worker restarted before completion. Check and resume unfinished work; completed images will be reused.', 'Виконавець перезапустився до завершення. Перевірте й відновіть незавершену роботу; готові зображення використаємо повторно.'),
    validation: tr('The requested changes did not pass validation. Return to the editor, correct the request, and send it again.', 'Запитані зміни не пройшли перевірку. Поверніться в редактор, виправте запит і надішліть його знову.'),
    stale: tr('The Landing changed while this request was running. Return to the editor and review its latest state before sending a new request.', 'Лендінг змінився під час виконання. Поверніться в редактор і перевірте останній стан перед новим запитом.'),
  }
  const slotLabel = (slot: string) => slot.startsWith('app_screen_') ? tr(`App screen ${slot.slice(-1)}`, `Екран застосунку ${slot.slice(-1)}`) : ({ hero_visual: tr('Hero image', 'Головне зображення'), visual_break_visual: tr('Supporting image', 'Додаткове зображення'), walkthrough_visual: tr('Walkthrough image', 'Зображення кроків') }[slot] || slot)
  const statusLabel = (status: string) => ({ queued: tr('Queued', 'У черзі'), generating: tr('Generating', 'Генерується'), preparing: tr('Preparing display images', 'Готуємо зображення для показу'), completed: tr('Completed', 'Завершено'), failed: tr('Failed', 'Помилка') }[status] || tr('Processing', 'Обробляється'))
  const jobs = operation?.jobs || initialJobs || []
  const done = jobs.filter(job => job.status === 'completed').length
  const elapsed = Math.max(0, Math.floor((tick - (Date.parse(operation?.started_at || startedAt || '') || began.current)) / 1000))
  return createPortal(<dialog ref={ref} className="landing-operation-overlay" aria-modal="true" aria-labelledby="landing-operation-title" tabIndex={-1} onCancel={event => event.preventDefault()}>
    <section className="landing-operation-card">
      {failed ? <AlertCircle size={32} /> : <LoaderCircle size={32} className="landing-operation-spin" />}
      <h2 id="landing-operation-title">{failed ? tr('This request needs attention', 'Цей запит потребує уваги') : tr('Updating your Landing', 'Оновлюємо ваш лендінг')}</h2>
      <div role={failed ? 'alert' : 'status'} aria-live="polite"><p>{failed ? error || categories[operation?.error?.category || 'provider'] : descriptions[stage] || descriptions.preparing}</p>
        {!!jobs.length && <p>{tr(`${done} of ${jobs.length} images completed.`, `Завершено ${done} із ${jobs.length} зображень.`)}</p>}</div>
      {!!jobs.length && <ul>{jobs.map(job => <li key={job.slot}><span>{slotLabel(job.slot)}</span><strong>{statusLabel(job.status)}</strong></li>)}</ul>}
      {!failed && <small>{tr('Elapsed', 'Минуло')}: {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}</small>}
      {failed && <><p>{tr('Previously completed images are retained. Retry continues only unfinished work.', 'Раніше завершені зображення збережено. Повторення продовжить лише незавершену роботу.')}</p>
      {error?.includes('Reattach') && <label>{tr('Reattach the original screenshots in the same order', 'Додайте початкові знімки екрана в тому самому порядку')}<input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={event => {
        const files = Array.from(event.target.files || [])
        setReferenceError('')
        if (files.length > 4) { setReferenceError(tr('Attach at most four screenshots.', 'Додайте щонайбільше чотири знімки екрана.')); return }
        void Promise.all(files.map(imageReferencePayload)).then(setReferences).catch(cause => setReferenceError(String(cause.message)))
      }} /></label>}
      {referenceError && <p role="alert">{referenceError}</p>}<div className="landing-operation-actions">
        {retry && operation?.error?.retryable !== false && <button className="primary" onClick={() => retry(references)}><RefreshCcw size={16} />{tr('Retry unfinished work', 'Повторити незавершене')}</button>}
        {close && <button className="secondary" onClick={close}>{tr('Return to editor', 'Повернутися в редактор')}</button>}
      </div><details><summary>{tr('Technical details', 'Технічні дані')}</summary><p>{operation?.error?.code || 'RequestError'} · {operation?.error?.phase || stage}</p>{operation && <p>{operation.operation_id}</p>}</details></>}
    </section>
  </dialog>, document.body)
}
