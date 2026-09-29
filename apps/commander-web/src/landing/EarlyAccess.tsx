import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { legalUrl } from './LegalLinks'
import './early-access.css'

export type InquirySource = 'apple' | 'google' | 'telegram' | 'instagram' | 'threads'
export type LandingInquiry = { request_id: string; source: InquirySource; question: string; contact: string; contact_channel: 'email' | 'telegram' | 'instagram'; website: string }
const Context = createContext<(source: InquirySource, trigger?: HTMLElement) => void>(() => {})
export const useEarlyAccess = () => useContext(Context)

export function EarlyAccess({ children, language, legalOrigin, submit }: { children: ReactNode; language: 'uk' | 'en'; legalOrigin?: string; submit?: (inquiry: LandingInquiry) => Promise<void> }) {
  const [source, setSource] = useState<InquirySource | null>(null)
  const [question, setQuestion] = useState(''), [contact, setContact] = useState('')
  const [channel, setChannel] = useState<LandingInquiry['contact_channel']>('email')
  const [busy, setBusy] = useState(false), [sent, setSent] = useState(false), [error, setError] = useState('')
  const request = useRef<LandingInquiry | null>(null), opener = useRef<HTMLElement | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const title = useId(), uk = language === 'uk'
  const tr = (en: string, ua: string) => uk ? ua : en
  useEffect(() => {
    if (source) { if (dialog.current?.showModal) dialog.current.showModal(); else dialog.current?.setAttribute('open', '') }
  }, [source])
  const close = () => { if (busy) return; dialog.current?.close?.(); setSource(null); requestAnimationFrame(() => opener.current?.focus()) }
  const open = (value: InquirySource, trigger?: HTMLElement) => {
    // Touch Safari does not focus a tapped link/button before its click handler.
    opener.current = trigger || document.activeElement as HTMLElement
    if (sent) { setQuestion(''); setContact(''); request.current = null }
    setSource(value); setSent(false); setError('')
  }
  return <Context.Provider value={open}>{children}{source && <dialog ref={dialog} className="natal-early-access" aria-labelledby={title} onCancel={event => { event.preventDefault(); close() }} onClick={event => { if (event.target === event.currentTarget) close() }}>
    <div className="natal-early-access__body">
      <button className="natal-early-access__close" type="button" disabled={busy} onClick={close} aria-label={tr('Close', 'Закрити')}>×</button>
      <h2 id={title}>{tr('We’re building the first version', 'Готуємо першу версію')}</h2>
      {sent ? <p role="status">{contact.trim() ? tr('Thank you! We saved your message and contact for an alpha-launch notification.', 'Дякуємо! Ми зберегли ваше звернення та контакт для сповіщення про запуск альфа-версії.') : tr('Thank you! We saved your question.', 'Дякуємо! Ми зберегли ваше запитання.')}</p> : <>
        <p>{tr('Natal is at an early stage. The alpha version is not available yet. Could you help us by sharing your question or leaving a contact so we can notify you when it launches?', 'Natal зараз на ранній стадії. Альфа-версія ще недоступна. Допоможете нам: напишіть своє запитання або залиште контакт, щоб ми сповістили вас про запуск?')}</p>
        <form onSubmit={async event => {
          event.preventDefault()
          if (busy) return
          if (!question.trim() && !contact.trim()) { setError(tr('Write a question or leave a contact.', 'Напишіть запитання або залиште контакт.')); return }
          if (!submit) { setError(tr('Open the published page to send your message.', 'Щоб надіслати звернення, відкрийте опубліковану сторінку.')); return }
          const input = { source, question: question.trim(), contact: contact.trim(), contact_channel: channel, website: String(new FormData(event.currentTarget).get('website') || '') }
          if (!request.current || JSON.stringify({ ...request.current, request_id: undefined }) !== JSON.stringify(input)) request.current = { ...input, request_id: crypto.randomUUID() }
          setBusy(true); setError('')
          try { await submit(request.current); setSent(true) } catch (cause) {
            const code = cause instanceof Error ? cause.message : ''
            setError(code === 'invalid_contact' ? tr('Check your contact: enter an email or a profile link/nickname for the selected channel.', 'Перевірте контакт: введіть email або посилання/нік для обраного каналу.') : code === 'stale_page' ? tr('This page changed. Reload it before sending your message.', 'Сторінку оновлено. Перезавантажте її перед надсиланням звернення.') : code === 'rate_limit' ? tr('Too many inquiries right now. Please try again shortly.', 'Зараз надходить багато звернень. Спробуйте трохи пізніше.') : tr('Your message wasn’t confirmed. Please try again; your text is still here.', 'Отримання звернення ще не підтверджено. Спробуйте ще раз — ваш текст збережено у формі.'))
          } finally { setBusy(false) }
        }}>
          <label>{tr('Your question (optional)', 'Ваше запитання (необов’язково)')}<textarea autoFocus maxLength={2000} rows={3} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} /></label>
          <label>{tr('How to notify you', 'Куди сповістити')}<select value={channel} disabled={busy} onChange={event => setChannel(event.target.value as LandingInquiry['contact_channel'])}><option value="email">Email</option><option value="telegram">Telegram</option><option value="instagram">Instagram</option></select></label>
          <label>{tr('Contact (optional)', 'Контакт (необов’язково)')}<input type={channel === 'email' ? 'email' : 'text'} maxLength={320} autoComplete={channel === 'email' ? 'email' : 'off'} placeholder={channel === 'email' ? 'you@example.com' : '@nickname / https://…'} value={contact} disabled={busy} onChange={event => setContact(event.target.value)} /></label>
          <label className="natal-early-access__trap" aria-hidden="true">Website<input name="website" tabIndex={-1} autoComplete="off" /></label>
          <p className="natal-early-access__privacy">{tr('A contact is only needed if you want a reply or an alpha-launch notification.', 'Контакт потрібен лише для відповіді або сповіщення про запуск альфа-версії.')} <a href={legalUrl('privacy', language, legalOrigin)} target="_blank" rel="noopener noreferrer">{tr('Privacy policy', 'Політика конфіденційності')}</a></p>
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? tr('Sending…', 'Надсилаємо…') : tr('Send', 'Надіслати')}</button>
        </form>
      </>}
    </div>
  </dialog>}</Context.Provider>
}
