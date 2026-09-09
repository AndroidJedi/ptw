import type { ApiClient } from '../api'
import { AuthorizationSettings } from '../components/AuthorizationSettings'
import { PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'

export function SettingsView({ api, language }: { api: ApiClient; language: Language }) {
  return <div className="settings-page">
    <PageHeader title={translate(language, 'Settings', 'Налаштування')} />
    <AuthorizationSettings api={api} language={language} />
  </div>
}
