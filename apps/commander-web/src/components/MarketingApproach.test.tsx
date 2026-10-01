import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ProductBriefDocument } from '../types'
import { BriefContent } from './MarketingApproach'

const legacy: ProductBriefDocument = {
  schema_version: 1, language: 'en', product: 'Car sharing', target_audience: 'Friends planning a weekend',
  main_pain: 'Plans stay in the group chat', promise: 'Friends. Weekend. Let’s go.',
  key_benefits: ['Temporary use of a car', 'Travel together', 'No car purchase'], cta: 'Ask about a car',
  offer: 'Ask about a car for your weekend', trust_strategy: 'Explain terms and price',
}
const current: ProductBriefDocument = {
  ...legacy, schema_version: 3,
  positioning: { marketing_approach: 'identity_led', desired_identity: 'The friend who makes plans happen',
    customer_tension: 'Good plans keep getting postponed', category_frame: 'A car for time together', functional_value: 'Temporary access to a car' },
  brand_identity: {
    belief: 'Good weekends begin with someone saying let’s go.', identity_signal: 'I turn the chat into memories.',
    values: 'Initiative, shared time, thoughtful choices.', cultural_tension: 'Plans that never leave the chat.',
    category_reframe: 'From car rental to the start of a shared weekend.', emotional_reward: 'Pride in getting everyone together.',
    competence_cue: 'People, bags and route first; car second.', proof_anchor: 'Temporary car use.',
    voice: 'Warm and decisive. Let’s go.', visual_world: 'Friends loading weekend bags into a recognizable car.', ritual: '',
  },
}

describe('Versioned Brief rendering', () => {
  it.each(['en', 'uk'] as const)('shows the brand handoff with %s labels and no empty ritual', language => {
    render(<BriefContent value={current} language={language} />)
    const section = screen.getByRole('region', { name: language === 'uk' ? 'Ідентичність бренду' : 'Brand identity' })
    expect(within(section).getByRole('heading', { name: current.brand_identity!.belief })).toBeInTheDocument()
    for (const text of Object.values(current.brand_identity!).filter(Boolean)) expect(within(section).getByText(text)).toBeInTheDocument()
    expect(within(section).queryByText(language === 'uk' ? 'Спільний ритуал' : 'A shared ritual')).not.toBeInTheDocument()
  })

  it('does not fabricate a brand section for historical V1 or V2', () => {
    const { rerender } = render(<BriefContent value={legacy} language="en" />)
    expect(screen.queryByRole('region', { name: 'Brand identity' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Positioning' })).not.toBeInTheDocument()
    rerender(<BriefContent value={{ ...legacy, schema_version: 2, positioning: current.positioning }} language="en" />)
    expect(screen.getByRole('region', { name: 'Positioning' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Brand identity' })).not.toBeInTheDocument()
  })
})
