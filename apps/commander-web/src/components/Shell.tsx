import { Clapperboard, LayoutTemplate, Megaphone, Settings, Target } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Page } from '../types'

const items: Array<{ id: Page; label: string; icon: typeof Target }> = [
  { id: 'briefs', label: 'Product Briefs', icon: Target },
  { id: 'studio', label: 'Ad Studio', icon: Clapperboard },
  { id: 'ads', label: 'Ads', icon: Megaphone },
  { id: 'landing', label: 'Landing', icon: LayoutTemplate },
  { id: 'admin', label: 'Admin', icon: Settings },
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
      <div className="brand" aria-label="PTW"><span>PTW</span><small>Validation</small></div>
      <nav aria-label="Головна навігація на комп’ютері">
        {items.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
          <Icon aria-hidden="true" /><span>{label}</span>
        </button>)}
      </nav>
      <button className="language" onClick={onLanguage} aria-label="Змінити мову">{language === 'uk' ? 'EN' : 'УКР'}</button>
    </aside>
    <main id="main-content">{children}</main>
    <nav className="bottom-nav" aria-label="Головна навігація на телефоні">
      {items.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
        <Icon aria-hidden="true" /><span>{label}</span>
      </button>)}
    </nav>
  </div>
}
