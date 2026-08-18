import type { ApiClient } from '../api'
import type { Language } from '../i18n'
import { PageHeader } from '../components/State'
import { LavalEngine } from '../components/LavalEngine'

export function IdeasView({ api, language }: { api: ApiClient; language: Language }) {
  return <>
    <PageHeader eyebrow="IDEA LAVAL ENGINE" title="Ідеї" />
    <LavalEngine api={api} language={language} />
  </>
}
