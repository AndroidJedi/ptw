import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { PublicLanding } from './PublicApp'
import { PublicApp } from './PublicApp'

const snapshot: PublicLanding = {
  canonical_url: 'https://natal-service.com/ai/sample-project',
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
    hero_visual: '/api/v1/public/landings/ai/sample-project/versions/' + 'a'.repeat(64) + '/assets/hero_visual/' + 'b'.repeat(64) + '.png',
    visual_break_visual: '/api/v1/public/landings/ai/sample-project/versions/' + 'a'.repeat(64) + '/assets/visual_break_visual/' + 'c'.repeat(64) + '.png',
  },
}

afterEach(() => vi.unstubAllGlobals())

it('renders the English-only umbrella without a directory or CTA', () => {
  render(<PublicApp path="/" apiOrigin="" />)
  expect(screen.getByRole('heading', { name: 'Natal' })).toBeVisible()
  expect(screen.getByText('Digital products and services by Natal.')).toBeVisible()
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
})

it('loads Meta Pixel only after explicit consent and tracks the current route once', () => {
  render(<PublicApp path="/" apiOrigin="" />)
  expect(document.querySelector('script[data-meta-pixel]')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Allow' }))
  const script = document.querySelector('script[data-meta-pixel]')
  expect(script).toHaveAttribute('src', 'https://connect.facebook.net/en_US/fbevents.js')
  expect(script).toHaveAttribute('data-meta-pixel', '1056720310312959')
  expect(window.fbq?.queue).toEqual([
    ['init', '1056720310312959'],
    ['track', 'PageView'],
  ])
})

it('persists rejection without contacting Meta', () => {
  render(<PublicApp path="/" apiOrigin="" />)
  fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
  expect(window.localStorage.getItem('natal_meta_pixel_consent_v1')).toBe('rejected')
  expect(document.querySelector('script[data-meta-pixel]')).toBeNull()
  expect(window.fbq).toBeUndefined()
})

it.each(['ai', 'la', 'wa'])('fetches and renders a published %s lane with the shared renderer', async lane => {
  const value = { ...snapshot, canonical_url: `https://natal-service.com/${lane}/sample-project` }
  const fetch = vi.fn(async () => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  render(<PublicApp path={`/${lane}/sample-project`} apiOrigin="https://api.example" />)

  expect(await screen.findByRole('heading', { name: 'A public promise' })).toBeVisible()
  expect(screen.getByLabelText('Landing live preview')).toBeVisible()
  expect(screen.getByRole('link', { name: /Instagram @natal_service/ })).toHaveAttribute('href', 'https://www.instagram.com/natal_service/')
  expect(fetch).toHaveBeenCalledWith(`https://api.example/api/v1/public/landings/${lane}/sample-project`, expect.objectContaining({ credentials: 'omit', cache: 'no-store' }))
  expect(document.title).toBe('Sample Project — Natal')
})

it('shows the branded visual 404 for an invalid route without calling the API', () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(<PublicApp path="/invalid/path" apiOrigin="https://api.example" />)
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  expect(screen.getByText('This Natal page is unavailable.')).toBeVisible()
  expect(screen.getByRole('link', { name: 'Go to Natal' })).toHaveAttribute('href', '/')
  expect(fetch).not.toHaveBeenCalled()
})

it('shows the same visual 404 when the bounded public API returns 404', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 404 })))
  render(<PublicApp path="/ai/unpublished-project" apiOrigin="https://api.example" />)
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Page not found' })).toBeVisible())
})
