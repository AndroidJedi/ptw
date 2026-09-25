import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { revokeMetaConsent } from './metaPixel'

export const CONSENT_KEY = 'natal_privacy_preferences_v2'
export const CONSENT_MAX_AGE = 180 * 24 * 60 * 60 * 1000
export type Preferences = { version: 2; analytics: boolean; marketing: boolean; savedAt: number }

export function readPreferences(): Preferences | null {
  try {
    const value = JSON.parse(window.localStorage.getItem(CONSENT_KEY) || 'null')
    return value?.version === 2 && typeof value.analytics === 'boolean' && typeof value.marketing === 'boolean'
      && Number.isFinite(value.savedAt) && value.savedAt <= Date.now() && Date.now() - value.savedAt < CONSENT_MAX_AGE ? value : null
  } catch { return null }
}

type PrivacyContext = {
  preferences: Preferences | null; open: boolean
  show: () => void; close: () => void; decide: (analytics: boolean, marketing: boolean) => void
}
const Context = createContext<PrivacyContext | null>(null)

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(readPreferences)
  const [open, setOpen] = useState(() => !readPreferences())
  // Keep a denied in-memory choice when storage is unavailable. Expiry is also
  // checked in long-lived tabs, not just on the next page load.
  useEffect(() => {
    if (!preferences) return
    let timer: number
    const check = () => {
      if (Date.now() - preferences.savedAt >= CONSENT_MAX_AGE) {
        revokeMetaConsent(); setPreferences(null); setOpen(true)
      } else timer = window.setTimeout(check, Math.min(CONSENT_MAX_AGE - (Date.now() - preferences.savedAt) + 1, 2_147_483_647))
    }
    check()
    return () => window.clearTimeout(timer)
  }, [preferences])
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== CONSENT_KEY && event.key !== null) return
      const next = readPreferences()
      if (!next?.marketing) revokeMetaConsent()
      setPreferences(next); setOpen(!next)
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  function decide(analytics: boolean, marketing: boolean) {
    const value: Preferences = { version: 2, analytics, marketing, savedAt: Date.now() }
    if (!marketing) revokeMetaConsent()
    try {
      window.localStorage.setItem(CONSENT_KEY, JSON.stringify(value))
      window.localStorage.removeItem('natal_meta_pixel_consent_v1')
    } catch { /* The current tab still respects the visitor's choice. */ }
    setPreferences(value); setOpen(false)
  }
  return <Context.Provider value={{ preferences, open, show: () => setOpen(true), close: () => setOpen(false), decide }}>{children}</Context.Provider>
}

export function usePrivacy() {
  const context = useContext(Context)
  if (!context) throw new Error('PrivacyProvider is required')
  return context
}
