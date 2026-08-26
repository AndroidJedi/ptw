import type { ReactNode } from 'react'
import { translate, type Language } from '../i18n'

export function PageHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return <header className="page-header"><div><p>{eyebrow}</p><h1>{title}</h1></div>{action}</header>
}

export function Loading({ language = 'uk' }: { language?: Language }) { return <div className="state" role="status">{translate(language, 'Loading…', 'Завантаження…')}</div> }
export function ErrorState({ message, retry, language = 'uk' }: { message: string; retry?: () => void; language?: Language }) {
  return <div className="state error" role="alert"><p>{message}</p>{retry && <button className="secondary" onClick={retry}>{translate(language, 'Retry', 'Повторити')}</button>}</div>
}
export function Empty({ children }: { children: ReactNode }) { return <div className="state">{children}</div> }
