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
        brief_count: 1,
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
      language="uk"
    />)

    fireEvent.change(screen.getByPlaceholderText('Опишіть одну продуктову ідею…'), {
      target: { value: 'An English idea' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Згенерувати продуктовий бриф і створити проєкт' }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0][1]).toMatchObject({ raw_idea: 'An English idea', language: 'uk' })
  })

  it('requires a common template and hands the reserved creative to Post', async () => {
    const brief = {
      brief_id: 'brief-1', project_id: 'project-1', project_name: 'Project One',
      request_id: 'request-1', owner_idea_source_id: 'source-1', raw_idea: 'A useful product',
      status: 'completed', failure_count: 0, approved: false,
      created_at: '2026-09-01T00:00:00Z', language: 'en',
      document: {
        schema_version: 1, language: 'en', product: 'Useful product',
        target_audience: 'Operators', main_pain: 'Lost time', promise: 'Move faster',
        key_benefits: ['Clear decisions', 'Less work', 'Visible progress'],
        cta: 'Start now', trust_strategy: 'Show the workflow', offer: 'Guided setup',
      },
    }
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
      if (path === '/api/v1/briefs/brief-1') return brief
      if (path === '/api/v1/studio/templates') return { items: [{
        template_id: 'phone_metrics', name: 'Phone Metrics', description: 'Phone creative',
        canvas: { width: 1080, height: 1080 }, template_version: 1,
        template_sha256: 'a'.repeat(64),
      }] }
      throw new Error(`Unexpected GET ${path}`)
    })
    const post = vi.fn(async () => ({ creative: { creative_id: 'creative-1' } }))
    const onCreative = vi.fn()
    const api = { get, post } as unknown as ApiClient

    render(<ProductBriefView
      api={api}
      projectId="project-1"
      onProjectCreated={vi.fn()}
      onProjectBriefChanged={vi.fn()}
      onProjectsRefresh={vi.fn(async () => undefined)}
      onCreative={onCreative}
      language="en"
    />)

    await screen.findByText('Move faster')
    fireEvent.click(screen.getByRole('button', { name: /I can honor this promise/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Phone Metrics/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Approve Brief & generate creative' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/briefs/brief-1/approve', {
      honor_confirmed: true, template_id: 'phone_metrics',
    }))
    expect(onCreative).toHaveBeenCalledWith('project-1', 'creative-1')
  })

  it('creates a first creative from an already-approved Brief without asking for approval again', async () => {
    const brief = {
      brief_id: 'brief-1', project_id: 'project-1', project_name: 'Project One',
      request_id: 'request-1', owner_idea_source_id: 'source-1', raw_idea: 'A useful product',
      status: 'completed', failure_count: 0, approved: true,
      created_at: '2026-09-01T00:00:00Z', language: 'en',
      document: {
        schema_version: 1, language: 'en', product: 'Useful product',
        target_audience: 'Operators', main_pain: 'Lost time', promise: 'Move faster',
        key_benefits: ['Clear decisions', 'Less work', 'Visible progress'],
        cta: 'Start now', trust_strategy: 'Show the workflow', offer: 'Guided setup',
      },
    }
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
      if (path === '/api/v1/briefs/brief-1') return brief
      if (path === '/api/v1/studio/templates') return { items: [{
        template_id: 'phone_metrics', name: 'Phone Metrics', description: 'Phone creative',
        canvas: { width: 1080, height: 1080 }, template_version: 1,
        template_sha256: 'a'.repeat(64),
      }] }
      throw new Error(`Unexpected GET ${path}`)
    })
    const post = vi.fn(async () => ({ creative: { creative_id: 'creative-1' } }))
    const onCreative = vi.fn()
    const api = { get, post } as unknown as ApiClient

    render(<ProductBriefView
      api={api} projectId="project-1" onProjectCreated={vi.fn()}
      onProjectBriefChanged={vi.fn()} onProjectsRefresh={vi.fn(async () => undefined)}
      onCreative={onCreative} language="en"
    />)

    await screen.findByText('Product Brief approved')
    fireEvent.click(screen.getByRole('button', { name: 'Open or create its creative' }))
    fireEvent.click(await screen.findByRole('button', { name: /Phone Metrics/ }))
    expect(screen.getByRole('button', { name: 'Create creative' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Create creative' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/v1/briefs/brief-1/approve', {
      honor_confirmed: true, template_id: 'phone_metrics',
    }))
    expect(onCreative).toHaveBeenCalledWith('project-1', 'creative-1')
  })
})
