import { BriefcaseBusiness, LayoutDashboard, Lightbulb, MoreHorizontal } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Page } from '../types'

const items: Array<{ id: Page; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'overview', label: 'Огляд', icon: LayoutDashboard },
  { id: 'ideas', label: 'Ідеї', icon: Lightbulb },
  { id: 'jobs', label: 'Завдання', icon: BriefcaseBusiness },
  { id: 'more', label: 'Ще', icon: MoreHorizontal },
]

export function Shell({ page, onPage, children, language, onLanguage }: {
  page: Page
  onPage: (page: Page) => void
  children: ReactNode
  language: 'uk' | 'en'
  onLanguage: () => void
}) {
  return <div className="app-shell">
    <aside className="rail" aria-label="Головна навігація">
      <div className="brand" aria-label="PTW Commander"><span>PTW</span><small>Командир</small></div>
      <nav>
        {items.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
          <Icon aria-hidden="true" /><span>{label}</span>
        </button>)}
      </nav>
      <button className="language" onClick={onLanguage} aria-label="Змінити мову">{language === 'uk' ? 'EN' : 'УКР'}</button>
    </aside>
    <main id="main-content">{children}</main>
    <nav className="bottom-nav" aria-label="Головна навігація">
      {items.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
        <Icon aria-hidden="true" /><span>{label}</span>
      </button>)}
    </nav>
  </div>
}
