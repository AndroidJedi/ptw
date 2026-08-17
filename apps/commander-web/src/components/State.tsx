import type { ReactNode } from 'react'

export function PageHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return <header className="page-header"><div><p>{eyebrow}</p><h1>{title}</h1></div>{action}</header>
}

export function Loading() { return <div className="state" role="status">Завантаження…</div> }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="state error" role="alert"><p>{message}</p>{retry && <button className="secondary" onClick={retry}>Повторити</button>}</div>
}
export function Empty({ children }: { children: ReactNode }) { return <div className="state">{children}</div> }
