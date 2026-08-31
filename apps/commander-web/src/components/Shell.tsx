import { Layers3, Sparkles, Target } from 'lucide-react'
import type { ReactNode } from 'react'
import { translate, type Language } from '../i18n'
import type { Page } from '../types'

const items: Array<{ id: Page; en: string; uk: string; icon: typeof Target }> = [
  { id: 'briefs', en: 'Product Briefs', uk: 'Продуктові брифи', icon: Target },
  { id: 'result', en: 'Social posts', uk: 'Дописи для соцмереж', icon: Sparkles },
  { id: 'studio', en: 'Studio', uk: 'Студія', icon: Layers3 },
]

export function Shell({ page, onPage, children, language, onLanguage }: {
  page: Page
  onPage: (page: Page) => void
  children: ReactNode
  language: Language
  onLanguage: () => void
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  return <div className="app-shell">
    <aside className="rail" aria-label={tr('Main navigation', 'Головна навігація')}>
      <div className="brand" aria-label="PTW"><span>PTW</span><small>{tr('Validation', 'Валідація')}</small></div>
      <nav aria-label={tr('Desktop navigation', 'Головна навігація на комп’ютері')}>
        {items.map(({ id, en, uk, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
          <Icon aria-hidden="true" /><span>{tr(en, uk)}</span>
        </button>)}
      </nav>
      <button className="language" onClick={onLanguage} aria-label={tr('Change language', 'Змінити мову')}>{language === 'uk' ? 'EN' : 'УКР'}</button>
    </aside>
    <main id="main-content">{children}</main>
    <nav className="bottom-nav" aria-label={tr('Mobile navigation', 'Головна навігація на телефоні')}>
      {items.map(({ id, en, uk, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => onPage(id)} aria-current={page === id ? 'page' : undefined}>
        <Icon aria-hidden="true" /><span>{tr(en, uk)}</span>
      </button>)}
      <button className="mobile-language" onClick={onLanguage} aria-label={tr('Change language', 'Змінити мову')}><span>{language === 'uk' ? 'EN' : 'УКР'}</span></button>
    </nav>
  </div>
}
