import type { ApiClient } from '../api'
import { AuthorizationSettings } from '../components/AuthorizationSettings'
import { PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'

export function SettingsView({ api, language, onLanguage }: { api: ApiClient; language: Language; onLanguage?: () => void }) {
  return <div className="settings-page">
    <PageHeader title={translate(language, 'Settings', 'Налаштування')} />
    <section className="panel settings-card settings-language" aria-labelledby="settings-language-title">
      <header><h2 id="settings-language-title">{translate(language, 'Language', 'Мова')}</h2></header>
      <button className="secondary" onClick={onLanguage} aria-label={translate(language, 'Change language', 'Змінити мову')}>{language === 'uk' ? 'English' : 'Українська'}</button>
    </section>
    <AuthorizationSettings api={api} language={language} />
  </div>
}
