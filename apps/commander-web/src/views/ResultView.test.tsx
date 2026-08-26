import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { ProductBrief, ProjectBrandKit } from '../types'
import { ResultView } from './ResultView'

const projectId = '018f07ea-7f20-7000-8000-000000000001'
const brief: ProductBrief = {
  brief_id: '018f07ea-7f20-7000-8000-000000000002',
  project_id: projectId,
  project_name: 'Horoscope',
  request_id: '018f07ea-7f20-7000-8000-000000000003',
  owner_idea_source_id: '018f07ea-7f20-7000-8000-000000000004',
  raw_idea: 'Personalized horoscope for job seekers',
  status: 'completed', failure_count: 0, approved: true,
  product: 'Event-based personalized horoscope for job seekers',
  promise: 'Receive personalized guidance for the next move.',
  created_at: '2026-08-26T10:00:00Z',
}

function apiWith(kits: ProjectBrandKit[], post = vi.fn()) {
  return {
    get: vi.fn(async (path: string) => {
      if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
      if (path.startsWith('/api/v1/content-runs?')) return { items: [] }
      if (path.startsWith('/api/v1/project-assets?')) return { items: [] }
      if (path.startsWith('/api/v1/project-brand-kits?')) return { items: kits }
      throw new Error(`Unexpected GET ${path}`)
    }),
    post, image: vi.fn(), media: vi.fn(), websocketUrl: vi.fn(), request: vi.fn(),
  } as unknown as ApiClient
}

function expectBrandSetupBeforeResult() {
  const setup = screen.getByText('PROJECT BRAND KIT').closest('section')
  const result = screen.getByText('SOURCE').closest('section')
  expect(setup).not.toBeNull()
  expect(result).not.toBeNull()
  expect(setup!.compareDocumentPosition(result!) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0)
}

describe('ResultView prerequisites', () => {
  it('places missing brand-kit setup before the disabled Result action', async () => {
    const savedKit: ProjectBrandKit = {
      brand_kit_id: '018f07ea-7f20-7000-8000-000000000005', project_id: projectId,
      document: {
        name: 'Horoscope', colors: ['#111111', '#FFFFFF', '#43BDD3', '#F4F2EC'],
        fonts: ['Inter'], tone_notes: 'Direct', logo_source_asset_id: null,
      },
      document_sha256: 'a'.repeat(64), created_at: '2026-08-26T10:05:00Z',
    }
    const post = vi.fn().mockResolvedValue(savedKit)
    render(<ResultView api={apiWith([], post)} projectId={projectId} />)

    await screen.findByText(brief.product!)
    expectBrandSetupBeforeResult()
    expect(screen.getByRole('button', { name: 'Create result' })).toBeDisabled()
    expect(screen.getByText('Save the Project brand kit above before creating a Result.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Brand name'), { target: { value: 'Horoscope' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save brand kit' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/project-brand-kits', {
      project_id: projectId, parent_brand_kit_id: null,
      document: {
        name: 'Horoscope', colors: ['#111111', '#FFFFFF', '#43BDD3', '#F4F2EC'],
        fonts: ['Inter'], tone_notes: 'Direct, conversational, specific, and honest.',
        logo_source_asset_id: null,
      },
    }))
  })

  it('places missing Instagram logo setup before the disabled Result action', async () => {
    const kit: ProjectBrandKit = {
      brand_kit_id: '018f07ea-7f20-7000-8000-000000000005', project_id: projectId,
      document: { name: 'Horoscope', colors: ['#111111'], fonts: ['Inter'], tone_notes: 'Direct' },
      document_sha256: 'a'.repeat(64), created_at: '2026-08-26T10:05:00Z',
    }
    render(<ResultView api={apiWith([kit])} projectId={projectId} />)

    await screen.findByText(brief.product!)
    fireEvent.click(screen.getByRole('radio', { name: 'Instagram post' }))
    await waitFor(expectBrandSetupBeforeResult)
    expect(screen.getByRole('button', { name: 'Create result' })).toBeDisabled()
    expect(screen.getByText('Add an approved logo to the latest brand kit above before creating an Instagram post.')).toBeInTheDocument()
  })
})
