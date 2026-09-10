import { useEffect, useRef } from 'react'
import type { Language } from '../../i18n'
import { ErrorState } from '../State'

export function StudioActionFeedback({ error, notice, language }: {
  error: string; notice: string; language: Language
}) {
  const feedback = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!error) return
    feedback.current?.focus({ preventScroll: true })
    feedback.current?.scrollIntoView({ block: 'start', behavior: 'auto' })
  }, [error])

  if (!error && !notice) return null
  return <div ref={feedback} tabIndex={-1} className="studio-action-feedback">
    {error && <ErrorState message={error} language={language} />}
    {notice && <p className="notice" role="status">{notice}</p>}
  </div>
}
