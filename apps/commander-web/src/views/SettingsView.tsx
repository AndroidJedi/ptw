import type { ApiClient } from '../api'
import { AuthorizationSettings } from '../components/AuthorizationSettings'
import { CommanderChat } from '../components/CommanderChat'
import { PageHeader } from '../components/State'
import { translate, type Language } from '../i18n'

export function SettingsView({ api, language, localMode = false }: { api: ApiClient; language: Language; localMode?: boolean }) {
  return <div className="settings-page">
    <PageHeader title={translate(language, 'Settings', 'Налаштування')} />
    {localMode ? <CommanderChat api={api} language={language} /> : <AuthorizationSettings api={api} language={language} />}
  </div>
}
