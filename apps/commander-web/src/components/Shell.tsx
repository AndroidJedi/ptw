import { Image, Layers3, Settings, Target } from 'lucide-react'
import type { ReactNode } from 'react'
import { translate, type Language } from '../i18n'
import type { Page } from '../types'

const items: Array<{ id: Page; en: string; uk: string; icon: typeof Target }> = [
  { id: 'briefs', en: 'Brief', uk: 'Бриф', icon: Target },
  { id: 'posts', en: 'Post', uk: 'Допис', icon: Image },
  { id: 'studio', en: 'Studio', uk: 'Студія', icon: Layers3 },
]

export function Shell({ page, onPage, children, language, onLanguage, postsAvailable = false }: {
  page: Page
  onPage: (page: Page) => void
  children: ReactNode
  language: Language
  onLanguage: () => void
  postsAvailable?: boolean
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const visibleItems = items.filter((item) => item.id !== 'posts' || postsAvailable)
  return <div className="app-shell">
    <aside className="rail" aria-label={tr('Main navigation', 'Головна навігація')}>
      <div className="brand" aria-label="PTW"><span>PTW</span><small>{tr('Validation', 'Валідація')}</small></div>
      <nav aria-label={tr('Desktop navigation', 'Головна навігація на комп’ютері')}>
        {visibleItems.map(({ id, en, uk, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
          <Icon aria-hidden="true" /><span>{tr(en, uk)}</span>
        </button>)}
      </nav>
      <div className="rail-controls"><button className="language" onClick={onLanguage} aria-label={tr('Change language', 'Змінити мову')}>{language === 'uk' ? 'EN' : 'УКР'}</button><button className={`settings-button ${page === 'settings' ? 'active' : ''}`} onClick={() => onPage('settings')} aria-current={page === 'settings' ? 'page' : undefined} aria-label={tr('Settings', 'Налаштування')}><Settings /></button></div>
    </aside>
    <main id="main-content">{children}</main>
    <nav className="bottom-nav" aria-label={tr('Mobile navigation', 'Головна навігація на телефоні')}>
      {visibleItems.map(({ id, en, uk, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
        <Icon aria-hidden="true" /><span>{tr(en, uk)}</span>
      </button>)}
      <button className="mobile-language" onClick={onLanguage} aria-label={tr('Change language', 'Змінити мову')}><span>{language === 'uk' ? 'EN' : 'УКР'}</span></button>
      <button className={page === 'settings' ? 'mobile-settings active' : 'mobile-settings'} onClick={() => onPage('settings')} aria-current={page === 'settings' ? 'page' : undefined} aria-label={tr('Settings', 'Налаштування')}><Settings /><span>{tr('Settings', 'Налаштування')}</span></button>
    </nav>
  </div>
}
