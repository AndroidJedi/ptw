import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ValidationProject } from '../types'
import { ProjectSwitcher } from './ProjectSwitcher'

const projects: ValidationProject[] = [{
  project_id: '018f07ea-7f20-7000-8000-000000000001',
  request_id: '018f07ea-7f20-7000-8000-000000000002',
  owner_idea_source_id: '018f07ea-7f20-7000-8000-000000000003',
  name: 'Psychologist consultations', name_source: 'product_brief',
  requested_by: 'firebase:owner', latest_brief_id: '018f07ea-7f20-7000-8000-000000000004',
  latest_brief_status: 'completed', brief_count: 2, result_run_count: 1,
  result_creation_enabled: true,
  created_at: '2026-08-25T08:00:00Z', updated_at: '2026-08-25T08:05:00Z',
}, {
  project_id: '018f07ea-7f20-7000-8000-000000000011',
  request_id: '018f07ea-7f20-7000-8000-000000000012',
  owner_idea_source_id: '018f07ea-7f20-7000-8000-000000000013',
  name: 'Mentor marketplace', name_source: 'raw_idea', requested_by: 'firebase:owner',
  latest_brief_id: '018f07ea-7f20-7000-8000-000000000014', latest_brief_status: 'generating',
  brief_count: 1, result_run_count: 0, result_creation_enabled: false,
  created_at: '2026-08-25T09:00:00Z', updated_at: '2026-08-25T09:00:00Z',
}]

describe('ProjectSwitcher', () => {
  it('selects, renames, and starts projects without using UUIDs as labels', async () => {
    const onSelect = vi.fn()
    const onNew = vi.fn()
    const onRename = vi.fn().mockResolvedValue(undefined)
    render(<ProjectSwitcher projects={projects} projectId={projects[0].project_id} onSelect={onSelect} onNew={onNew} onRename={onRename} />)

    const selector = screen.getByLabelText('Project')
    expect(selector).toHaveTextContent('Psychologist consultations · completed')
    expect(selector).not.toHaveTextContent(projects[0].project_id)
    expect(screen.queryByText(projects[0].project_id, { exact: false })).not.toBeInTheDocument()
    fireEvent.change(selector, { target: { value: projects[1].project_id } })
    expect(onSelect).toHaveBeenCalledWith(projects[1].project_id)

    fireEvent.click(screen.getByRole('button', { name: 'Rename' }))
    fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'Focused validation' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save name' }))
    await waitFor(() => expect(onRename).toHaveBeenCalledWith(projects[0].project_id, 'Focused validation'))

    fireEvent.click(screen.getByRole('button', { name: 'New Project' }))
    expect(onNew).toHaveBeenCalledOnce()
  })
})
