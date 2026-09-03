import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api'
import type { ProductBrief, SimplePost } from '../types'
import { PostView } from './PostView'

const projectId = '01900000-0000-7000-8000-000000000001'
const briefId = '01900000-0000-7000-8000-000000000002'
const postId = '01900000-0000-7000-8000-000000000003'

const brief: ProductBrief = {
  brief_id: briefId, project_id: projectId, project_name: 'Guided therapy',
  request_id: briefId, owner_idea_source_id: projectId, raw_idea: 'A calmer start',
  status: 'completed', approved: true, failure_count: 0,
  document_sha256: 'b'.repeat(64), created_at: '2026-09-02T08:00:00Z',
  document: {
    schema_version: 1, language: 'en', product: 'Guided therapy',
    target_audience: 'People seeking support', main_pain: 'The first step is difficult',
    promise: 'Start with one calmer conversation', key_benefits: ['Real profiles'],
    cta: 'Book a conversation', trust_strategy: 'Transparent process',
    offer: 'First consultation free',
  },
}

const draft: SimplePost = {
  schema: 'ptw.simple-post.v1', post_id: postId, request_id: postId,
  project_id: projectId, brief_id: briefId, brief_document_sha256: 'b'.repeat(64),
  status: 'draft', failure_count: 0, state_sha256: 'a'.repeat(64),
  template_sha256: 'c'.repeat(64), last_commands: [
    { setting_id: 'configuration.typography.hero_size', value: 92 },
  ],
  last_image_request: { slot: 'background_image', query: 'calm person portrait' },
  preview: { mime_type: 'image/png', sha256: 'd'.repeat(64), width: 1080, height: 1080 },
  studio: null, approved_asset: null, approved_asset_id: null,
  created_at: '2026-09-02T08:00:00Z', updated_at: '2026-09-02T08:01:00Z',
}

function postApi(initial: SimplePost | null) {
  let current = initial ? structuredClone(initial) : null
  const get = vi.fn(async (path: string) => {
    if (path.startsWith('/api/v1/briefs?')) return { items: [brief] }
    if (path.startsWith('/api/v1/posts?')) return { items: current ? [current] : [] }
    if (path === `/api/v1/posts/${postId}`) return structuredClone(current)
    throw new Error(`Unhandled GET ${path}`)
  })
  const post = vi.fn(async (path: string, body: unknown) => {
    if (path === '/api/v1/posts') {
      current = { ...structuredClone(draft), status: 'queued', preview: null, state_sha256: null }
      return { post: current, created: true }
    }
    if (path === `/api/v1/posts/${postId}/tune`) {
      current = { ...structuredClone(draft), status: 'tuning', last_comment: (body as { comment: string }).comment }
      return { post: current, created: true }
    }
    if (path === `/api/v1/posts/${postId}/approve`) {
      current = {
        ...structuredClone(draft), status: 'approved', approved_asset_id: '01900000-0000-7000-8000-000000000004',
        approved_asset: {
          schema: 'ptw.simple-post-asset.v1', asset_id: '01900000-0000-7000-8000-000000000004',
          post_id: postId, project_id: projectId, brief_id: briefId, mime_type: 'image/png',
          sha256: 'e'.repeat(64), width: 1080, height: 1080,
          state_sha256: 'a'.repeat(64), template_sha256: 'c'.repeat(64),
          approved_by: 'owner', created_at: '2026-09-02T08:02:00Z',
        },
      }
      return { post: current, asset_created: true }
    }
    throw new Error(`Unhandled POST ${path}`)
  })
  return {
    get, post,
    postMedia: vi.fn(async () => new Blob(['preview'], { type: 'image/png' })),
    media: vi.fn(async () => new Blob(['asset'], { type: 'image/png' })),
  } as unknown as ApiClient
}

describe('simple post step', () => {
  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:post-preview') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  })

  it('starts exactly one post from the approved Brief', async () => {
    const api = postApi(null)
    render(<PostView api={api} projectId={projectId} language="en" />)

    await screen.findByRole('button', { name: 'Generate one post' })
    fireEvent.click(screen.getByRole('button', { name: 'Generate one post' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/v1/posts', {
      request_id: expect.any(String), brief_id: briefId,
    }, { deadlineMs: 60_000 }))
    expect(screen.getByText('Generating one post and choosing one relevant photograph.')).toBeInTheDocument()
  })

  it('places semantic feedback below the preview and sends it as one agent comment', async () => {
    const api = postApi(draft)
    render(<PostView api={api} projectId={projectId} language="en" />)

    await screen.findByAltText('Single generated post preview')
    const field = screen.getByLabelText('Comment below the preview')
    fireEvent.change(field, { target: { value: 'Pick image with thinking human face.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply comment' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      `/api/v1/posts/${postId}/tune`,
      { request_id: expect.any(String), comment: 'Pick image with thinking human face.' },
      { deadlineMs: 60_000 },
    ))
    expect(screen.getByText('Your comment is being translated into Studio component and image commands.')).toBeInTheDocument()
    expect(screen.getByText('configuration.typography.hero_size')).toBeInTheDocument()
    expect(screen.getByText('calm person portrait')).toBeInTheDocument()
  })

  it('shows a resolved sticker asset command by its exact Studio slot', async () => {
    const stickerDraft = {
      ...structuredClone(draft),
      last_commands: [{ setting_id: 'configuration.sticker.enabled', value: true }],
      last_image_request: {
        slot: 'sticker_object' as const,
        query: 'red push pin physical object close up plain background',
        required_subject_terms: ['push pin'],
      },
    }
    render(<PostView api={postApi(stickerDraft)} projectId={projectId} language="en" />)

    await screen.findByAltText('Single generated post preview')
    expect(screen.getByText('configuration.sticker.enabled')).toBeInTheDocument()
    expect(screen.getByText('asset.sticker_object')).toBeInTheDocument()
  })

  it('creates the asset only after explicit approval', async () => {
    const api = postApi(draft)
    render(<PostView api={api} projectId={projectId} language="en" />)

    await screen.findByRole('button', { name: 'Approve as asset' })
    fireEvent.click(screen.getByRole('button', { name: 'Approve as asset' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      `/api/v1/posts/${postId}/approve`, { state_sha256: 'a'.repeat(64) },
      { deadlineMs: 90_000 },
    ))
    expect(await screen.findByText('Immutable asset created')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Apply comment' })).not.toBeInTheDocument()
  })
})
