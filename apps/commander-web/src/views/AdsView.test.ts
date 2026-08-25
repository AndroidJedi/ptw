import { describe, expect, it } from 'vitest'
import type { CreativeBatch } from '../types'
import { batchFailureReason, batchLessonRerunState } from './AdsView'

describe('Ads failure reason', () => {
  it('turns the legacy offer validator error into an actionable explanation', () => {
    const failure = batchFailureReason({
      batch_id: '01a03327-a038-72a6-85ae-e50983b0e6f4',
      brief_id: '01a03327-3006-7449-848e-7153ec4d572e',
      status: 'failed',
      failure_count: 1,
      error_code: 'ValueError',
      error_message: 'every creative must retain the Product Brief offer exactly',
      approved_offer: 'Free 15-minute mentor call.',
      creatives: [],
      created_at: '2026-08-24T09:43:50Z',
    } satisfies CreativeBatch)

    expect(failure.title).toBe('Approved offer continuity check failed')
    expect(failure.explanation).toContain('Free 15-minute mentor call.')
    expect(failure.detail).toContain('retain the Product Brief offer')
  })

  it('keeps the same reason available after a successful retry', () => {
    const failure = batchFailureReason({
      batch_id: '01a03327-a038-72a6-85ae-e50983b0e6f4',
      brief_id: '01a03327-3006-7449-848e-7153ec4d572e',
      status: 'completed',
      failure_count: 1,
      approved_offer: 'Free 15-minute mentor call.',
      last_failed_attempt: {
        attempt_id: '01a03327-a0c8-7fe7-96a3-b86e09099abb',
        attempt_number: 1,
        error_code: 'ValueError',
        error_message: 'every creative must retain the Product Brief offer exactly',
        started_at: '2026-08-24T09:43:50Z',
        completed_at: '2026-08-24T09:44:17Z',
      },
      creatives: [],
      created_at: '2026-08-24T09:43:50Z',
    } satisfies CreativeBatch, true)

    expect(failure.title).toBe('Approved offer continuity check failed')
    expect(failure.explanation).toContain('Free 15-minute mentor call.')
  })
})

describe('Ads learned rerun state', () => {
  const batch = {
    batch_id: '01a03327-a038-72a6-85ae-e50983b0e6f4',
    brief_id: '01a03327-3006-7449-848e-7153ec4d572e',
    status: 'completed', failure_count: 0, creatives: [], created_at: '2026-08-24T09:43:50Z',
  } satisfies CreativeBatch

  it('becomes ready only after feedback lessons are promoted', () => {
    expect(batchLessonRerunState({
      ...batch, lesson_status_counts: { promoted: 4 },
    })).toEqual({ kind: 'ready', promoted: 4 })
    expect(batchLessonRerunState({
      ...batch, lesson_status_counts: { promoted: 3, planning: 1 },
    })).toEqual({ kind: 'unfinished', promoted: 3, unfinished: 1 })
  })

  it('opens the already-created immutable child instead of offering another duplicate run', () => {
    expect(batchLessonRerunState({
      ...batch, rerun_batch_id: '01a03327-a038-72a6-85ae-e50983b0ffff',
      lesson_status_counts: { promoted: 4 },
    })).toEqual({ kind: 'created', batchId: '01a03327-a038-72a6-85ae-e50983b0ffff' })
  })
})
