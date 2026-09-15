import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { AnalyticsWorkspace } from '../types'
import { AnalyticsView } from './AnalyticsView'

const projectId = '11111111-1111-4111-8111-111111111111'
const runId = '22222222-2222-4222-8222-222222222222'
const candidateId = '33333333-3333-4333-8333-333333333333'

function fixture(review = false): AnalyticsWorkspace {
  return {
    schema: 'ptw.analytics.workspace.v1', scope: 'project', project_id: projectId,
    window_days: 30,
    readiness: {
      instagram: { available: true },
      meta: { available: false, explanation: 'Paid results are imported from Meta Ads Manager CSV.' },
      landing: { available: true },
    },
    organic: [], paid: [],
    landing_funnel: {
      landing_view: 0, primary_cta_click: 0, contact_click: 0,
      primary_cta_rate: null, outbound_contact_rate: null, surfaces: {},
      conversion_label: 'Outbound contact click · conversion proxy',
    },
    skills: { snapshot: null, rules: [] },
    learning_runs: review ? [{
      learning_run_id: runId, scope: 'project', project_id: projectId, surface: 'post',
      status: 'completed', dataset: { sample_size: 2, confidence: 'exploratory' },
      dataset_sha256: 'a'.repeat(64), created_at: '2026-09-13T10:00:00Z',
      candidates: [{
        rule_id: '44444444-4444-4444-8444-444444444444', candidate_id: candidateId,
        scope: 'project', project_id: projectId, surface: 'post', family: 'copy',
        instruction: 'Prefer a direct outcome in the headline.',
        target: { semantic_role: 'hero_title' }, evidence: { comparison: 'age-matched' },
        confidence: { sample_size: 2, project_count: 1, level: 'exploratory' },
        active: false, tombstone: false,
      }],
    }] : [],
    learning_curve: [], freshness: { instagram: null },
    metric_definitions: {},
  }
}

beforeEach(() => {
  Object.defineProperty(globalThis.crypto, 'randomUUID', {
    configurable: true,
    value: vi.fn(() => '55555555-5555-4555-8555-555555555555'),
  })
})

it('labels unavailable analytics and runs learning only from the explicit button', async () => {
  const get = vi.fn(async () => fixture())
  const post = vi.fn(async () => ({ status: 'insufficient_data' }))
  const api = { get, post } as unknown as ApiClient
  render(<AnalyticsView api={api} language="en" projectId={projectId} />)

  expect(await screen.findByText('Paid results are imported from Meta Ads Manager CSV.')).toBeVisible()
  expect(screen.getByText('No provider snapshots in this window.')).toBeVisible()
  expect(post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Run Post learning' }))

  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/analytics/${projectId}/learning-runs`,
    { request_id: '55555555-5555-4555-8555-555555555555', surface: 'post' },
    { deadlineMs: 480_000 },
  ))
})

it('supports per-rule review edits and requires Activate selected', async () => {
  const get = vi.fn(async () => fixture(true))
  const post = vi.fn(async () => ({}))
  const api = { get, post } as unknown as ApiClient
  render(<AnalyticsView api={api} language="en" projectId={projectId} />)

  const instruction = await screen.findByLabelText('Instruction')
  fireEvent.change(instruction, { target: { value: 'Prefer a specific outcome in the headline.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Activate selected' }))

  await waitFor(() => expect(post).toHaveBeenCalledWith(
    `/api/v1/analytics/${projectId}/learning-runs/${runId}/decision`,
    expect.objectContaining({
      decision: 'activate',
      rules: [expect.objectContaining({
        candidate_id: candidateId, family: 'copy',
        instruction: 'Prefer a specific outcome in the headline.',
        target: { semantic_role: 'hero_title' },
      })],
    }),
  ))
})

it('keeps exact-target rule families on one concrete surface', async () => {
  const api = { get: vi.fn(async () => fixture()), post: vi.fn(async () => ({})) } as unknown as ApiClient
  render(<AnalyticsView api={api} language="en" projectId={projectId} />)

  await screen.findByText('No active rules. Add one directly or run learning after enough evidence exists.')
  fireEvent.click(screen.getByRole('button', { name: 'Add rule' }))
  expect(screen.getByLabelText('Surface')).toHaveValue('both')
  fireEvent.change(screen.getByLabelText('Family'), { target: { value: 'ui' } })
  expect(screen.getByLabelText('Surface')).toHaveValue('post')
  expect(screen.queryByRole('option', { name: 'both' })).not.toBeInTheDocument()
})
