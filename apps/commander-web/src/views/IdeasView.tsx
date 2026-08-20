import type { ApiClient } from '../api'
import type { Language } from '../i18n'
import { PageHeader } from '../components/State'
import { LavalEngine } from '../components/LavalEngine'
import { ValidationPanel } from '../components/ValidationPanel'
import { useState } from 'react'

export function IdeasView({ api, language, initialRunId }: { api: ApiClient; language: Language; initialRunId?: string }) {
  const [view, setView] = useState<'research' | 'validation'>('research')
  return <>
    <PageHeader eyebrow="IDEA LAVAL ENGINE" title="Ідеї" />
    <nav className="idea-subviews" aria-label="Режим ідей"><button className={view === 'research' ? 'selected' : ''} onClick={() => setView('research')}>Дослідження</button><button className={view === 'validation' ? 'selected' : ''} onClick={() => setView('validation')}>Валідація</button></nav>
    {view === 'research' ? <LavalEngine api={api} language={language} initialRunId={initialRunId} /> : <ValidationPanel api={api} />}
  </>
}
