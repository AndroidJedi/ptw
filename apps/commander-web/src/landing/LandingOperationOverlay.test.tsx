import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { LandingOperationOverlay, type LandingOperation } from './LandingOperationOverlay'

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
})

function failed(category: string, jobs: LandingOperation['jobs'] = []): LandingOperation {
  return { operation_id: 'operation', request_id: 'request', landing_id: 'landing', project_id: 'project',
    kind: 'agent', status: 'failed', phase: 'failed', started_at: '', updated_at: '', revision: 3,
    jobs, error: { phase: 'interpreting', category, code: 'StudioManualAgentProviderError', retryable: category === 'provider' } }
}

it.each(['en', 'uk'] as const)('explains service contract failure without copy or image blame (%s)', language => {
  render(<LandingOperationOverlay language={language} operation={failed('contract')} retry={vi.fn()} close={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent(language === 'en' ? 'Your draft is unchanged' : 'Чернетку не змінено')
  expect(screen.queryByText(/Previously completed images|Раніше завершені зображення/)).not.toBeInTheDocument()
  expect(screen.queryByText(/correct the request|виправте запит/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Retry unfinished work|Повторити незавершене/)).not.toBeInTheDocument()
})

it('explains the preserved historical interpretation failure as an agent response problem', () => {
  render(<LandingOperationOverlay language="uk" operation={failed('validation')} close={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('Агент не зміг повернути коректні зміни')
  expect(screen.queryByText(/виправте запит/)).not.toBeInTheDocument()
})

it('offers retry for provider failure and reports only actual completed images', () => {
  const retry = vi.fn()
  const operation = failed('provider', [{ slot: 'app_screen_1', status: 'completed' }, { slot: 'app_screen_2', status: 'failed' }])
  render(<LandingOperationOverlay language="en" operation={operation} retry={retry} />)
  expect(screen.getByText('1 of 2 images completed.')).toBeInTheDocument()
  expect(screen.getByText(/Previously completed images/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry unfinished work' }))
  expect(retry).toHaveBeenCalledOnce()
})
