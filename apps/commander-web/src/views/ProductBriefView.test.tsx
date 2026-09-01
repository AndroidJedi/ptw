import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import { ProductBriefView } from './ProductBriefView'

describe('Product Brief workspace', () => {
  it('keeps the new-project screen focused on the idea input', () => {
    const api = {} as ApiClient

    render(<ProductBriefView
      api={api}
      projectId={null}
      onProjectCreated={vi.fn()}
      onProjectBriefChanged={vi.fn()}
      onProjectsRefresh={vi.fn(async () => undefined)}
      onOpenResult={vi.fn()}
      language="en"
    />)

    expect(screen.getByRole('heading', { name: 'New Project' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What do you want to validate?' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Describe one product idea…')).toBeInTheDocument()
    expect(screen.queryByText('NEW PROJECT · RAW IDEA ONLY')).not.toBeInTheDocument()
    expect(screen.queryByText(/Local learning workspace/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Generating an initial Brief creates/)).not.toBeInTheDocument()
  })

  it('sends the active console language with new Project creation', async () => {
    const post = vi.fn(async (_path: string, _body: Record<string, unknown>) => ({
      project: {
        project_id: 'project-1', request_id: 'request-1', owner_idea_source_id: 'source-1',
        name: 'Проєкт', name_source: 'raw_idea', requested_by: 'owner',
        result_creation_enabled: false, brief_count: 1, result_run_count: 0,
        created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
      },
      brief: {
        brief_id: 'brief-1', project_id: 'project-1', project_name: 'Проєкт',
        request_id: 'request-1', owner_idea_source_id: 'source-1', raw_idea: 'An English idea',
        status: 'queued', failure_count: 0, approved: false,
        created_at: '2026-09-01T00:00:00Z',
      },
    }))
    const get = vi.fn(async (path: string) => path.includes('?') ? { items: [] } : {})
    const api = { post, get } as unknown as ApiClient

    render(<ProductBriefView
      api={api}
      projectId={null}
      onProjectCreated={vi.fn()}
      onProjectBriefChanged={vi.fn()}
      onProjectsRefresh={vi.fn(async () => undefined)}
      onOpenResult={vi.fn()}
      language="uk"
    />)

    fireEvent.change(screen.getByPlaceholderText('Опишіть одну продуктову ідею…'), {
      target: { value: 'An English idea' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Згенерувати продуктовий бриф і створити проєкт' }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0][1]).toMatchObject({ raw_idea: 'An English idea', language: 'uk' })
  })
})
