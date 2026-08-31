import { render, screen } from '@testing-library/react'
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
})
