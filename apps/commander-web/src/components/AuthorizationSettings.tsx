import { ExternalLink, LoaderCircle, RefreshCcw, ShieldCheck, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'

type AuthorizationStatus = {
  status: 'authorized' | 'authorization_required' | 'authorizing' | 'verifying' | 'failed'
  test_status: 'passed' | 'failed' | null
  authorization_url?: string
  device_code?: string
}

const active = new Set(['authorizing', 'verifying'])

export function AuthorizationSettings({ api, language, onClose }: {
  api: ApiClient
  language: Language
  onClose: () => void
}) {
  const [value, setValue] = useState<AuthorizationStatus | null>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const load = async () => {
    try {
      setValue(await api.get<AuthorizationStatus>('/api/v1/settings/chatgpt-authorization'))
      setError('')
    } catch (cause) { setError((cause as Error).message) }
  }
  useEffect(() => { void load() }, [api])
  useEffect(() => {
    if (!value || !active.has(value.status)) return
    const timer = window.setInterval(() => void load(), 2000)
    return () => window.clearInterval(timer)
  }, [value?.status])
  const refresh = async () => {
    setRefreshing(true); setError('')
    try { setValue(await api.post<AuthorizationStatus>('/api/v1/settings/chatgpt-authorization/refresh', {})) }
    catch (cause) { setError((cause as Error).message) } finally { setRefreshing(false) }
  }
  const status = value?.status || 'loading'
  const label = status === 'authorized'
    ? value?.test_status === 'passed'
      ? tr('Authorized and verified', 'Авторизовано й перевірено')
      : tr('Authorized', 'Авторизовано')
    : status === 'authorizing'
      ? tr('Waiting for authorization', 'Очікується авторизація')
      : status === 'verifying'
        ? tr('Verifying ChatGPT/Codex CLI', 'Перевіряється ChatGPT/Codex CLI')
        : status === 'failed'
          ? tr('Authorization check failed', 'Перевірка авторизації не вдалася')
          : status === 'loading' ? tr('Checking status…', 'Перевіряється статус…')
            : tr('Authorization required', 'Потрібна авторизація')
  return <div className="modal-backdrop" role="presentation">
    <section className="panel settings-dialog" role="dialog" aria-modal="true" aria-labelledby="chatgpt-authorization-title">
      <header><div><small>{tr('SETTINGS', 'НАЛАШТУВАННЯ')}</small><h2 id="chatgpt-authorization-title">ChatGPT Authorization</h2></div><button className="icon-button" onClick={onClose} aria-label={tr('Close settings', 'Закрити налаштування')}><X /></button></header>
      <div className={`authorization-status is-${status}`} role="status"><ShieldCheck /><div><small>{tr('CURRENT STATUS', 'ПОТОЧНИЙ СТАН')}</small><strong>{label}</strong>{value?.test_status === 'passed' && <span>{tr('Working test request passed.', 'Робочий тестовий запит пройдено.')}</span>}</div></div>
      {value?.status === 'authorizing' && <div className="authorization-device">
        <p>{tr('Open the secure device page and enter the code. This window will update automatically after completion.', 'Відкрийте захищену сторінку пристрою та введіть код. Це вікно оновиться автоматично після завершення.')}</p>
        {value.authorization_url && <a className="secondary" href={value.authorization_url} target="_blank" rel="noreferrer"><ExternalLink />{tr('Open authorization page', 'Відкрити сторінку авторизації')}</a>}
        {value.device_code && <code aria-label={tr('Device code', 'Код пристрою')}>{value.device_code}</code>}
        {(!value.authorization_url || !value.device_code) && <p className="authorization-wait"><LoaderCircle className="spin" />{tr('Preparing secure device prompt…', 'Готується захищене запрошення…')}</p>}
      </div>}
      {value?.status === 'failed' && <p>{tr('The credentials were saved, but the required working test did not pass. Start authorization again.', 'Дані авторизації збережено, але обов’язковий робочий тест не пройшов. Запустіть авторизацію ще раз.')}</p>}
      {error && <p className="settings-error" role="alert">{error}</p>}
      <footer><button className="primary" disabled={refreshing || status === 'authorizing' || status === 'verifying'} onClick={() => void refresh()}>{refreshing ? <LoaderCircle className="spin" /> : <RefreshCcw />}{tr('Refresh authorization', 'Оновити авторизацію')}</button><button className="secondary" onClick={() => void load()}>{tr('Check status', 'Перевірити статус')}</button></footer>
    </section>
  </div>
}
