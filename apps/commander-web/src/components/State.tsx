import type { ReactNode } from 'react'
import { translate, type Language } from '../i18n'

export function PageHeader({ title, action }: { title: string; action?: ReactNode }) {
  return <header className="page-header"><div><h1>{title}</h1></div>{action}</header>
}

export function Loading({ language = 'uk' }: { language?: Language }) { return <div className="state" role="status">{translate(language, 'Loading…', 'Завантаження…')}</div> }
export function ErrorState({ message, retry, language = 'uk' }: { message: string; retry?: () => void; language?: Language }) {
  const lines = message.split('\n').map((line) => line.trim()).filter(Boolean)
  return <div className="state error" role="alert"><div className="error-copy">{lines.map((line, index) => index === 0 ? <strong key={line}>{line}</strong> : <p key={`${index}-${line}`}>{line}</p>)}</div>{retry && <button className="secondary" onClick={retry}>{translate(language, 'Retry', 'Повторити')}</button>}</div>
}
export function Empty({ children }: { children: ReactNode }) { return <div className="state">{children}</div> }
