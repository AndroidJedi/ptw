import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { LandingContent, LandingConfiguration } from '../types'
import { MarketingSections } from './MarketingSections'
import { marketingDefaults, marketingContentDefaults } from './marketing'

const content = {
  hero: { title: 'Choose water' },
  features: [
    { title: 'Compare water', description: 'Compare water composition in one place.' },
    { title: 'Understand minerals', description: 'Plain explanations of mineralization.' },
    { title: 'Choose your taste', description: 'Choose according to your taste preferences.' },
  ],
  social_proof: { heading: 'Reviews', items: [] },
  marketing: marketingContentDefaults,
} as unknown as LandingContent
const configuration = { marketing: marketingDefaults, presentation: { language: 'en' } } as LandingConfiguration
const props = { configuration, content, imageUrls: {}, contactId: 'contacts', part: 'reviews' as const }

it('keeps three domain-specific cards in the review layout without inventing customer proof', () => {
  const { container, rerender } = render(<MarketingSections {...props} />)
  expect(screen.getByRole('heading', { name: 'About the app' })).toBeVisible()
  expect(container.querySelectorAll('.mk-reviews article')).toHaveLength(3)
  expect(container.querySelectorAll('.mk-feedback-icon')).toHaveLength(3)
  expect(container.querySelectorAll('.mk-feedback-icon-water svg')).toHaveLength(3)
  expect(screen.getByText('Compare water composition in one place.')).toBeVisible()
  expect(container.querySelectorAll('blockquote, .mk-stars, .mk-reviews footer')).toHaveLength(0)
  rerender(<MarketingSections {...props} content={{ ...content, hero: { ...content.hero, title: 'Track medicine' }, social_proof: { ...content.social_proof, heading: 'Reviews' }, features: content.features.map((_, i) => ({ title: `Medicine ${i}`, description: `Track medicine packages ${i}.` })) }} />)
  expect(screen.getByText('Track medicine packages 0.')).toBeVisible()
  expect(screen.queryByText('Compare water composition in one place.')).toBeNull()
  expect(container.querySelectorAll('.mk-feedback-icon-water')).toHaveLength(0)
})

it('renders supplied product copy, selects the editor section and respects an explicit hide', () => {
  const onSelect = vi.fn()
  const custom = { ...content, marketing: { ...marketingContentDefaults, feedback_examples: content.features.map((f, i) => ({ topic: f.title, statement: `Compare water composition ${i}.` })) } }
  const { rerender } = render(<MarketingSections {...props} content={custom} editing onSelect={onSelect} />)
  fireEvent.click(screen.getByText('Compare water composition 0.'))
  expect(onSelect).toHaveBeenCalledWith('social_proof')
  rerender(<MarketingSections {...props} configuration={{ ...configuration, marketing: { ...marketingDefaults, reference_reviews_enabled: false } }} />)
  expect(screen.queryByRole('heading', { name: 'About the app' })).toBeNull()
})

it('renders verified customer feedback in the same three-card section', () => {
  const { container } = render(<MarketingSections {...props} content={{ ...content, social_proof: { heading: 'Verified feedback', items: [{ statement: 'An owner-supplied quote.', attribution: 'Verified source' }] } }} />)
  expect(screen.getByRole('heading', { name: 'Verified feedback' })).toBeVisible()
  expect(container.querySelectorAll('.mk-reviews blockquote')).toHaveLength(1)
  expect(container.querySelectorAll('.mk-feedback-icon-water svg')).toHaveLength(1)
  expect(screen.getByText('An owner-supplied quote.')).toBeVisible()
  expect(screen.queryByText('Compare water composition in one place.')).toBeNull()
})

it('renders five editable feedback cards with their selected source portraits', () => {
  const items = Array.from({ length: 5 }, (_, index) => ({
    statement: `Water comparison ${index + 1}`,
    attribution: `Visitor ${index + 1}`,
    avatar_asset_id: `bokko_review_portrait_${index + 1}`,
  }))
  const { container } = render(<MarketingSections {...props} content={{ ...content, social_proof: { heading: 'Water feedback', items } }} />)
  expect(container.querySelectorAll('.mk-reviews blockquote')).toHaveLength(5)
  expect(container.querySelectorAll('.mk-feedback-avatar')).toHaveLength(5)
  expect(container.querySelectorAll('.mk-feedback-icon')).toHaveLength(0)
})
