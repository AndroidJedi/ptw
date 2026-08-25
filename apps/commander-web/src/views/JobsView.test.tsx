import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { Job } from '../types'
import { JobsView } from './JobsView'

const lessonInstruction = 'Update only skills/ad-creative-generator/references/owner-lessons.md.'

function client(job: Job) {
  return {
    get: vi.fn().mockResolvedValue({ items: [job] }),
    post: vi.fn().mockResolvedValue({ ...job, status: 'cancelled' }),
    websocketUrl: vi.fn(),
  } as unknown as ApiClient
}

describe('Admin job controls', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('shows openable future-rule steps and one explicit apply action', async () => {
    const api = client({
      id: 'f520e7f2-9652-46bd-94eb-f7b58d87b32c', mode: 'plan',
      title: lessonInstruction, instruction: lessonInstruction,
      status: 'awaiting_approval', execution_count: 0,
      plan: '1. Consolidate four lessons.', plan_digest: 'f'.repeat(64),
    })
    render(<JobsView api={api} />)
    expect(await screen.findByRole('button', { name: 'Apply future rule' })).toBeInTheDocument()
    expect(screen.getByText('Open details')).toBeInTheDocument()
    expect(screen.getByText('1. Consolidate four lessons.')).toBeVisible()
    expect(screen.getByText('Steps Codex will run')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
  })

  it('uses one review-first workflow instead of plan and execute modes', async () => {
    const api = client({
      id: 'f520e7f2-9652-46bd-94eb-f7b58d87b32c', mode: 'plan',
      title: 'Inspect production', status: 'completed', execution_count: 0,
    })
    api.websocketUrl = vi.fn().mockResolvedValue('ws://localhost/jobs/1')
    vi.stubGlobal('WebSocket', vi.fn(() => ({})))
    render(<JobsView api={api} />)

    expect(await screen.findByText('You will review the steps before anything changes. One job runs at a time.', { exact: false })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Plan · read only' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Execute' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('What should Codex do?'), { target: { value: 'Inspect production' } })
    fireEvent.click(screen.getByRole('button', { name: 'Review steps' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/v1/jobs', {
      mode: 'plan', instruction: 'Inspect production',
    }))
  })

  it('requires confirmation before the labelled cancel action mutates state', async () => {
    const job: Job = {
      id: 'f520e7f2-9652-46bd-94eb-f7b58d87b32c', mode: 'plan',
      title: lessonInstruction, instruction: lessonInstruction,
      status: 'planning', execution_count: 0,
    }
    const api = client(job)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<JobsView api={api} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(confirm).toHaveBeenCalledOnce()
    expect(api.post).not.toHaveBeenCalled()

    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      `/api/v1/jobs/${job.id}/cancel`, { confirmation: 'CANCEL JOB' },
    ))
  })
})
