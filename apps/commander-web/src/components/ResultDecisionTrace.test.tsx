import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { ContentCandidate, ContentDebug, CriticPassDebug } from '../types'
import { ResultDecisionTrace } from './ResultDecisionTrace'

const ids = Array.from({ length: 5 }, (_value, index) =>
  `01900000-0000-7000-8000-${String(index + 1).padStart(12, '0')}`,
)

function candidate(candidateId: string, index: number): ContentCandidate {
  return {
    candidate_id: candidateId,
    alias: `C${index + 1}`,
    round: 0,
    generation_kind: 'initial',
    template_id: ['moment_tension', 'contrast_reframe', 'mechanism_proof', 'human_story', 'direct_offer'][index],
    template_version: 1,
    parameters: {
      hook_pressure: 50 + index,
      emotional_intensity: 40 + index,
      conceptual_novelty: 60 + index,
      information_density: 30 + index,
      visual_complexity: 20 + index,
    },
    document: {
      hook: `Hook ${index + 1}`,
      headline: `Headline ${index + 1}`,
      primary_text: 'Primary', supporting_text: 'Supporting', offer: 'Offer', cta: 'CTA',
      caption: 'Caption', alt_text: `Candidate image ${index + 1}`,
      desired_emotion: 'Confidence', visual_concept: 'One clear composition',
    },
    preview: {
      asset_url: `/api/v1/content-runs/run/candidates/${candidateId}/asset`,
      sha256: String(index + 1).repeat(64), mime_type: 'image/jpeg', width: 1080, height: 1080,
    },
  }
}

function criticPass(passNumber: 1 | 2 | 3, ranking: string[]): CriticPassDebug {
  return {
    pass_id: `pass-${passNumber}`,
    pass_number: passNumber,
    active_candidate_ids: ranking,
    hard_gates: Object.fromEntries(ranking.map((id) => [id, { exact_offer_cta: true, safe_crop_layout: true }])),
    candidate_scores: Object.fromEntries(ranking.map((id, index) => [id, {
      scores: { message_clarity: 10 - index }, complexity: 'none',
      weighted_total: 92 - index, eligible: true, reason_codes: ['clear_message'],
    }])),
    ranking,
    pairwise_results: ranking.length > 1 ? [{
      left: ranking[0], right: ranking[1], winner: ranking[0], reason_codes: ['clearer'],
    }] : [],
    observations: [`Pass ${passNumber} observation.`],
    actions: passNumber < 3 ? [{
      action_type: 'regenerate_elements', base_candidate_id: ranking[0], status: 'completed',
    }] : [],
    final_selection: passNumber === 3 ? {
      candidate_id: ranking[0],
      decision_summary: ['Strongest hook.', 'Clearest next step.'],
    } : null,
  }
}

describe('Result decision trace', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:candidate'),
      revokeObjectURL: vi.fn(),
    })
  })

  it('shows five authenticated previews, exact parameters, and the three-pass decision path', async () => {
    const debug: ContentDebug = {
      candidates: ids.map(candidate),
      critic_passes: [criticPass(1, ids), criticPass(2, ids.slice(0, 3)), criticPass(3, ids.slice(0, 2))],
    }
    const image = vi.fn().mockResolvedValue(new Blob(['jpeg'], { type: 'image/jpeg' }))
    const api = { image } as unknown as ApiClient

    render(<ResultDecisionTrace value={debug} api={api} selectedCandidateId={ids[0]} language="en" />)

    expect(screen.getByText('Every image and its exact generation parameters')).toBeInTheDocument()
    expect(screen.getAllByText('Hook pressure')).toHaveLength(5)
    expect(screen.getByText('Screen all five')).toBeInTheDocument()
    expect(screen.getByText('Compare improvements')).toBeInTheDocument()
    expect(screen.getByText('Choose the finalist')).toBeInTheDocument()
    expect(screen.getByText('Selected C1')).toBeInTheDocument()
    expect(await screen.findAllByRole('img')).toHaveLength(5)
    await waitFor(() => expect(image).toHaveBeenCalledTimes(5))
    expect(image).toHaveBeenCalledWith(
      debug.candidates[0].preview.asset_url,
      'image/jpeg',
      debug.candidates[0].preview.sha256,
    )
  })

  it('shows grouped screening evidence and an explicit no-selection decision', async () => {
    const first = criticPass(1, ids.slice(0, 3))
    const second = criticPass(2, ids.slice(3))
    const final = criticPass(3, [ids[0], ids[3]])
    first.critic_scope = 'screening_group_1_of_2'
    second.critic_scope = 'screening_group_2_of_2'
    final.critic_scope = 'group_winner_comparison'
    first.actions = []
    second.actions = []
    final.final_selection = null
    for (const pass of [first, second, final]) {
      for (const score of Object.values(pass.candidate_scores)) score.eligible = false
    }
    const debug: ContentDebug = {
      candidates: ids.map(candidate),
      critic_passes: [first, second, final],
    }
    const api = {
      image: vi.fn().mockResolvedValue(new Blob(['jpeg'], { type: 'image/jpeg' })),
    } as unknown as ApiClient

    render(<ResultDecisionTrace value={debug} api={api} language="en" />)

    expect(screen.getByText('Screen the first three')).toBeVisible()
    expect(screen.getByText('Screen the remaining two')).toBeVisible()
    expect(screen.getByText('Compare both group winners')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'No eligible finalist' })).toBeVisible()
    expect(screen.getAllByText('Not eligible')).toHaveLength(5)
  })
})
