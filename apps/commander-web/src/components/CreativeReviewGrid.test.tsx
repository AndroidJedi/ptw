import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { ContentCreative } from '../types'
import { CreativeReviewGrid } from './CreativeReviewGrid'

const creative = (index: number): ContentCreative => ({
  creative_id: `018f07ea-7f20-7000-8000-00000000001${index}`,
  run_id: '018f07ea-7f20-7000-8000-000000000100',
  slot: `C${index}`,
  round: 0,
  generation_kind: 'initial',
  template_id: `strategy-${index}`,
  template_version: 1,
  parameters: {
    hook_pressure: 20, emotional_intensity: 30, conceptual_novelty: 40,
    information_density: 50, visual_complexity: 60,
  },
  document: {
    hook: `Hook ${index}`, headline: `Headline ${index}`, primary_text: `Primary ${index}`,
    supporting_text: `Support ${index}`, offer: `Offer ${index}`, cta: `CTA ${index}`,
    caption: `Caption ${index}`, alt_text: `Alt ${index}`, desired_emotion: 'calm',
    visual_concept: `Concept ${index}`,
  },
  document_sha256: String(index).repeat(64),
  preview: {
    asset_url: `/creative-${index}.jpg`, sha256: String(index).repeat(64),
    mime_type: 'image/jpeg', width: 1080, height: 1080,
  },
  created_at: '2026-09-01T10:00:00Z',
})

test('shows five Creative UUID cards and reports the owner selection', async () => {
  const onSelect = vi.fn()
  const api = { image: vi.fn().mockResolvedValue(new Blob(['image'], { type: 'image/jpeg' })) } as unknown as ApiClient
  render(<CreativeReviewGrid
    api={api} creatives={[1, 2, 3, 4, 5].map(creative)} selectedCreativeId={null}
    actionable onSelect={onSelect} language="en"
  />)

  expect(await screen.findAllByRole('radio')).toHaveLength(5)
  fireEvent.click(screen.getByRole('radio', { name: /Headline 3/ }))
  expect(onSelect).toHaveBeenCalledWith(creative(3).creative_id)
  expect(screen.queryByText(/score|ranking/i)).not.toBeInTheDocument()
})
