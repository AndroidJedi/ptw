import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { revokeMetaConsent } from './metaPixel'

export const CONSENT_KEY = 'natal_measurement_preferences_v3'
export type Preferences = { version: 3; analytics: boolean; marketing: boolean; savedAt: number }

export function readPreferences(): Preferences {
  const defaults: Preferences = { version: 3, analytics: true, marketing: true, savedAt: Date.now() }
  try {
    // Preserve previous explicit refusals when replacing the old consent UI.
    const raw = window.localStorage.getItem(CONSENT_KEY) || window.localStorage.getItem('natal_privacy_preferences_v2')
    const value = JSON.parse(raw || 'null')
    if ([2, 3].includes(value?.version) && typeof value.analytics === 'boolean' && typeof value.marketing === 'boolean') return { ...defaults, analytics: value.analytics, marketing: value.marketing }
  } catch { /* Measurement also works when browser storage is unavailable. */ }
  return defaults
}

type PrivacyContext = { preferences: Preferences; open: boolean; show: () => void; close: () => void; decide: (analytics: boolean, marketing: boolean) => void }
const Context = createContext<PrivacyContext | null>(null)
export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(readPreferences)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!preferences.marketing) revokeMetaConsent()
  }, [preferences.marketing])
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== CONSENT_KEY && event.key !== 'natal_privacy_preferences_v2' && event.key !== null) return
      const next = readPreferences()
      if (!next.marketing) revokeMetaConsent()
      setPreferences(next)
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  function decide(analytics: boolean, marketing: boolean) {
    const value: Preferences = { version: 3, analytics, marketing, savedAt: Date.now() }
    if (!marketing) revokeMetaConsent()
    try { window.localStorage.setItem(CONSENT_KEY, JSON.stringify(value)) } catch { /* Retain this tab's choice. */ }
    setPreferences(value); setOpen(false)
  }
  return <Context.Provider value={{ preferences, open, show: () => setOpen(true), close: () => setOpen(false), decide }}>{children}</Context.Provider>
}
export function usePrivacy() {
  const context = useContext(Context)
  if (!context) throw new Error('PrivacyProvider is required')
  return context
}
