import type { LandingImageVariants } from '../../commander-web/src/landing/LandingImage'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { LandingPage } from '../../commander-web/src/landing/LandingPage'
import type { LandingConfiguration, LandingContent } from '../../commander-web/src/types'
import natalLogo from '../../../natal/assets/logo-natal.png'
import { MetaPixelConsent } from './MetaPixelConsent'
import { LegalLinks } from '../../commander-web/src/landing/LegalLinks'
import { LegalPage, legalRoute } from './legal/LegalPage'
import { PrivacyProvider, usePrivacy } from './privacyPreferences'

export type PublicLanding = {
  canonical_url: string
  project_name: string
  configuration: LandingConfiguration
  content: LandingContent
  asset_variants?: LandingImageVariants
  assets: Record<string, string>
  version_sha256: string
  published_at: string
}

const routePattern = /^\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/
export const PUBLIC_API_ORIGIN = (import.meta.env.VITE_PUBLIC_API_ORIGIN || 'https://commander.proove-them-wrong.com').replace(/\/$/, '')

function setMetadata(snapshot?: PublicLanding) {
  document.title = snapshot ? `${snapshot.project_name} — Natal` : 'Natal'
  document.documentElement.lang = snapshot?.configuration.presentation?.language || 'en'
  document.querySelector('link[rel="canonical"]')?.remove()
  if (snapshot) {
    const link = document.createElement('link')
    link.rel = 'canonical'; link.href = snapshot.canonical_url
    document.head.append(link)
  }
}

function NatalMark() {
  return <img className="natal-public-logo" src={natalLogo} alt="Natal" />
}

function NotFound() {
  useEffect(() => { setMetadata() }, [])
  return <main className="natal-public-state"><NatalMark /><h1>Page not found</h1><p>This Natal page is unavailable.</p><a href="/">Go to Natal</a></main>
}

function PublicShell({ children, path, language = 'en', track = true }: { children: ReactNode; path: string; language?: string; track?: boolean }) {
  return <>{children}<MetaPixelConsent path={path} language={language} track={track} /></>
}

export function PublicApp({ path = window.location.pathname, apiOrigin = PUBLIC_API_ORIGIN }: { path?: string; apiOrigin?: string }) {
  return <PrivacyProvider><PublicPage path={path} apiOrigin={apiOrigin} /></PrivacyProvider>
}

function PublicPage({ path, apiOrigin }: { path: string; apiOrigin: string }) {
  const { preferences } = usePrivacy()
  const [snapshot, setSnapshot] = useState<PublicLanding | null>(null)
  const [failed, setFailed] = useState(false)
  const match = routePattern.exec(path)
  const root = path === '/' || path === ''
  const legal = legalRoute(path)
  const legalLanguage = new URLSearchParams(window.location.search).get('lang') === 'uk' ? 'uk' : 'en'
  const visitId = useRef(crypto.randomUUID())
  const viewedDigest = useRef<string | undefined>(undefined)
  const analyticsRoute = match ? `/${match[1]}` : ''
  const attributionToken = new URLSearchParams(window.location.search).get('ptw_attribution')
  const emit = useCallback((eventType: 'landing_view' | 'primary_cta_click' | 'contact_click', surface: 'page' | 'hero' | 'phone' | 'telegram' | 'instagram' | 'email', target: 'page' | 'contacts' | 'telegram' | 'instagram' | 'email' | 'phone') => {
    if (!preferences?.analytics || !snapshot || !analyticsRoute) return
    const width = window.innerWidth
    const body = {
      event_id: crypto.randomUUID(), visit_id: visitId.current,
      route: analyticsRoute, landing_version_sha256: snapshot.version_sha256,
      event_type: eventType, surface, target,
      attribution_token: attributionToken && /^[A-Za-z0-9_-]{43}$/.test(attributionToken) ? attributionToken : null,
      viewport_class: width < 600 ? 'mobile' : width < 1024 ? 'tablet' : 'desktop',
    }
    void fetch(`${apiOrigin}/api/v1/public/landing-analytics/events`, {
      method: 'POST', mode: 'cors', credentials: 'omit', keepalive: true,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }).catch(() => undefined)
  }, [analyticsRoute, apiOrigin, attributionToken, snapshot, preferences?.analytics])

  useEffect(() => {
    if (legal) return
    setSnapshot(null); setFailed(false)
    if (root) { setMetadata(); return }
    if (!match) { setFailed(true); return }
    const controller = new AbortController()
    const slug = match[1]
    fetch(`${apiOrigin}/api/v1/public/landings/${slug}`, {
      method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store',
      headers: { Accept: 'application/json' }, signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error('unavailable')
      const value = await response.json() as PublicLanding
      if (value.canonical_url !== `https://natal-service.com/${slug}`) throw new Error('invalid public snapshot')
      const assets = Object.fromEntries(Object.entries(value.assets).map(([slot, url]) => [slot, `${apiOrigin}${url}`])) as PublicLanding['assets']
      const asset_variants = value.asset_variants && Object.fromEntries(Object.entries(value.asset_variants).map(([slot, variants]) => [slot, variants.map(variant => ({ ...variant, url: `${apiOrigin}${variant.url}` }))]))
      const next = { ...value, assets, asset_variants }
      setSnapshot(next); setMetadata(value)
    }).catch(error => { if (error.name !== 'AbortError') setFailed(true) })
    return () => controller.abort()
  }, [apiOrigin, path]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!preferences?.analytics || !snapshot || viewedDigest.current === snapshot.version_sha256) return
    viewedDigest.current = snapshot.version_sha256
    emit('landing_view', 'page', 'page')
  }, [emit, snapshot, preferences?.analytics])

  if (legal) return <PublicShell path={path} language={legalLanguage} track={false}><LegalPage document={legal} language={legalLanguage} /></PublicShell>
  if (root) return <PublicShell path={path}><main className="natal-public-state natal-public-home"><NatalMark /><h1>Natal</h1><p>Digital products and services by Natal.</p><LegalLinks language="en" origin="" /></main></PublicShell>
  if (!match || failed) return <PublicShell path={path} track={false}><NotFound /></PublicShell>
  if (!snapshot) return <PublicShell path={path} track={false}><main className="natal-public-state" role="status"><NatalMark /><p>Loading Natal page…</p></main></PublicShell>
  return <PublicShell path={path} language={snapshot.configuration.presentation?.language || 'uk'}><main className="natal-public-landing"><LandingPage legalOrigin="" configuration={snapshot.configuration} content={snapshot.content} imageUrls={snapshot.assets} imageVariants={snapshot.asset_variants} onAnalyticsEvent={emit} /></main></PublicShell>
}
