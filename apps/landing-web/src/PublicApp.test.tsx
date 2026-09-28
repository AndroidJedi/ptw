import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { PublicLanding } from './PublicApp'
import { PublicApp } from './PublicApp'
import { CONSENT_KEY, CONSENT_MAX_AGE } from './privacyPreferences'
import { legalProfileReady } from './legal/LegalPage'
import profile from './legal/profile.json'

const snapshot: PublicLanding = {
  canonical_url: 'https://natal-service.com/sample-project',
  project_name: 'Sample Project', version_sha256: 'a'.repeat(64),
  published_at: '2026-09-08T00:00:00Z',
  configuration: {
    schema: 'ptw.landing.configuration.v1',
    theme: { background_color: '#fff', surface_color: '#eee', text_color: '#111', accent_color: '#222', font_family: 'Inter', heading_font_family: 'Inter', corner_radius: 8 },
    hero: { alignment: 'left', image_position: 'right' }, features: { layout: 'three_columns' },
    social_proof: { layout: 'cards' }, visual_break: { height: 'medium' }, contacts: { alignment: 'left' }, faq: { style: 'divided' },
  },
  content: {
    schema: 'ptw.landing.content.v1', hero: { title: 'A public promise', supporting_text: 'Public supporting copy', cta_label: 'Contact us', visual_direction: '' },
    features: [{ title: 'One', description: 'First' }, { title: 'Two', description: 'Second' }, { title: 'Three', description: 'Third' }],
    social_proof: { heading: '', items: [] }, visual_break: { visual_direction: '' },
    contacts: { heading: 'Contact', supporting_text: 'Talk to us', email: 'hello@example.com', phone: '', url: '', instagram: 'https://www.instagram.com/natal_service/' },
    faq: [{ question: 'Question?', answer: 'Answer.' }],
  },
  assets: {
    hero_visual: '/api/v1/public/landings/sample-project/versions/' + 'a'.repeat(64) + '/assets/hero_visual/' + 'b'.repeat(64) + '.png',
    visual_break_visual: '/api/v1/public/landings/sample-project/versions/' + 'a'.repeat(64) + '/assets/visual_break_visual/' + 'c'.repeat(64) + '.png',
  },
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); window.history.replaceState({}, '', '/') })

it('renders the umbrella with shared policies and no product directory', () => {
  render(<PublicApp path="/" apiOrigin="" />)
  expect(screen.getByRole('heading', { name: 'Natal' })).toBeVisible()
  expect(screen.getByText('Digital products and services by Natal.')).toBeVisible()
  expect(within(screen.getByRole('navigation', { name: 'Policies' })).getAllByRole('link')).toHaveLength(3)
})

it('loads Meta Pixel only after explicit consent and tracks the current route once', () => {
  render(<PublicApp path="/" apiOrigin="" />)
  expect(document.querySelector('script[data-meta-pixel]')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Allow all' }))
  const script = document.querySelector('script[data-meta-pixel]')
  expect(script).toHaveAttribute('src', 'https://connect.facebook.net/en_US/fbevents.js')
  expect(script).toHaveAttribute('data-meta-pixel', '1056720310312959')
  expect(window.fbq?.queue).toEqual([
    ['consent', 'grant'],
    ['set', 'autoConfig', false, '1056720310312959'],
    ['init', '1056720310312959'],
    ['track', 'PageView'],
  ])
})

it('persists rejection without contacting Meta', () => {
  render(<PublicApp path="/" apiOrigin="" />)
  fireEvent.click(screen.getByRole('button', { name: 'Reject optional' }))
  expect(JSON.parse(window.localStorage.getItem(CONSENT_KEY)!)).toMatchObject({ version: 2, analytics: false, marketing: false })
  expect(document.querySelector('script[data-meta-pixel]')).toBeNull()
  expect(window.fbq).toBeUndefined()
})

it('fetches and renders a published direct slug with the shared renderer', async () => {
  const value = snapshot
  const fetch = vi.fn(async () => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  render(<PublicApp path="/sample-project" apiOrigin="https://api.example" />)

  expect(await screen.findByRole('heading', { name: 'A public promise' })).toBeVisible()
  expect(screen.getByLabelText('Landing live preview')).toBeVisible()
  expect(screen.getByRole('link', { name: /Instagram @natal_service/ })).toHaveAttribute('href', 'https://www.instagram.com/natal_service/')
  expect(fetch).toHaveBeenCalledWith('https://api.example/api/v1/public/landings/sample-project', expect.objectContaining({ credentials: 'omit', cache: 'no-store' }))
  expect(document.title).toBe('Sample Project — Natal')
})

it('shows the branded visual 404 for nested and invalid routes without calling the API', () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(<PublicApp path="/invalid/path" apiOrigin="https://api.example" />)
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  expect(screen.getByText('This Natal page is unavailable.')).toBeVisible()
  expect(screen.getByRole('link', { name: 'Go to Natal' })).toHaveAttribute('href', '/')
  expect(fetch).not.toHaveBeenCalled()
  render(<PublicApp path="/legacy/old-project" apiOrigin="https://api.example" />)
  expect(fetch).not.toHaveBeenCalled()
})

it('shows the same visual 404 when the bounded public API returns 404', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 404 })))
  render(<PublicApp path="/unpublished-project" apiOrigin="https://api.example" />)
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Page not found' })).toBeVisible())
})

it.each(['terms', 'privacy', 'cookies'])('serves the %s legal deep link without public API or Pixel calls even with prior consent', kind => {
  window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ version: 2, analytics: true, marketing: true, savedAt: Date.now() }))
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  render(<PublicApp path={`/legal/${kind}`} />)
  expect(screen.getByRole('heading', { level: 1 })).toBeVisible()
  expect(screen.getByLabelText('Document status')).toHaveTextContent('This document is not final')
  expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute('href', `https://natal-service.com/legal/${kind}?lang=en`)
  expect(fetch).not.toHaveBeenCalled()
  expect(window.fbq).toBeUndefined()
})

it('does not mark an incomplete legal profile ready merely because reviewed is true', () => {
  expect(legalProfileReady()).toBe(false)
  expect(legalProfileReady({ ...profile, reviewed: true, effectiveDate: '2026-09-25' })).toBe(false)
})

it('uses Ukrainian legal copy and language links without changing document identity', () => {
  window.history.replaceState({}, '', '/legal/terms?lang=uk')
  render(<PublicApp />)
  expect(document.documentElement.lang).toBe('uk')
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Умови користування')
  expect(screen.getByRole('link', { name: 'English' })).toHaveAttribute('href', '/legal/terms?lang=en')
})

it('gates first-party events separately from Meta and stops them after withdrawal', async () => {
  const fetch = vi.fn(async () => new Response(JSON.stringify(snapshot), { status: 200 }))
  vi.stubGlobal('fetch', fetch)
  render(<PublicApp path="/sample-project" />)
  await screen.findByRole('heading', { name: 'A public promise' })
  const events = () => fetch.mock.calls.filter(call => String((call as unknown[])[0]).includes('landing-analytics'))
  expect(events()).toHaveLength(0)
  fireEvent.click(screen.getByRole('checkbox', { name: /Аналітика Natal/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Зберегти вибір' }))
  await waitFor(() => expect(events()).toHaveLength(1))
  expect(window.fbq).toBeUndefined()
  fireEvent.click(screen.getByRole('button', { name: 'Налаштування cookie' }))
  fireEvent.click(screen.getByRole('button', { name: 'Відхилити необов’язкові' }))
  fireEvent.click(screen.getByRole('link', { name: /Instagram @natal_service/ }))
  expect(events()).toHaveLength(1)
})

it('withdraws Meta permission, clears queued PageViews and first-party Pixel cookies', () => {
  render(<PublicApp path="/" />)
  fireEvent.click(screen.getByRole('button', { name: 'Allow all' }))
  document.cookie = '_fbp=old; Path=/'
  document.cookie = '_fbc=old; Path=/'
  fireEvent.click(screen.getByRole('button', { name: 'Cookie settings' }))
  fireEvent.click(screen.getByRole('button', { name: 'Reject optional' }))
  expect(window.fbq?.queue).toContainEqual(['consent', 'revoke'])
  expect(window.fbq?.queue.some(command => command[0] === 'track')).toBe(false)
  expect(document.cookie).not.toMatch(/_fb[pc]=/)
  expect(JSON.parse(window.localStorage.getItem(CONSENT_KEY)!)).toMatchObject({ analytics: false, marketing: false })
})

it.each(['legacy', 'expired', 'malformed', 'future'])('does not silently reuse %s consent', state => {
  if (state === 'legacy') window.localStorage.setItem('natal_meta_pixel_consent_v1', 'accepted')
  else window.localStorage.setItem(CONSENT_KEY, state === 'malformed' ? '{oops' : JSON.stringify({ version: 2, analytics: true, marketing: true, savedAt: Date.now() + (state === 'future' ? 60000 : -CONSENT_MAX_AGE - 1) }))
  render(<PublicApp path="/" />)
  expect(screen.getByLabelText('Privacy preferences')).toBeVisible()
  expect(window.fbq).toBeUndefined()
})

it('honours rejection even when browser storage throws', () => {
  const get = vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  const set = vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  render(<PublicApp path="/" />)
  fireEvent.click(screen.getByRole('button', { name: 'Reject optional' }))
  expect(screen.queryByLabelText('Privacy preferences')).not.toBeInTheDocument()
  expect(window.fbq).toBeUndefined()
  get.mockRestore(); set.mockRestore()
})

it('honours withdrawal from another tab and expires consent in a long-lived tab', () => {
  vi.useFakeTimers()
  window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ version: 2, analytics: true, marketing: true, savedAt: Date.now() - CONSENT_MAX_AGE + 1000 }))
  render(<PublicApp path="/" />)
  expect(window.fbq).toBeDefined()
  act(() => { vi.advanceTimersByTime(1002) })
  expect(screen.getByLabelText('Privacy preferences')).toBeVisible()
  expect(window.fbq?.queue).toContainEqual(['consent', 'revoke'])
  fireEvent.click(screen.getByRole('button', { name: 'Allow all' }))
  window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ version: 2, analytics: false, marketing: false, savedAt: Date.now() }))
  act(() => { window.dispatchEvent(new StorageEvent('storage', { key: CONSENT_KEY })) })
  expect(window.fbq?.queue.at(-1)).toEqual(['consent', 'revoke'])
})
