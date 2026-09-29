import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { EarlyAccess, useEarlyAccess } from './EarlyAccess'

function Open() {
  const open = useEarlyAccess()
  return <button onClick={event => open('apple', event.currentTarget)}>App Store</button>
}

it('keeps an uncertain receipt UUID after closing and reopening and clears sent inputs before a new inquiry', async () => {
  const submit = vi.fn().mockRejectedValueOnce(new Error('unconfirmed')).mockResolvedValue(undefined)
  render(<EarlyAccess language="en" submit={submit}><Open /></EarlyAccess>)
  fireEvent.click(screen.getByRole('button', { name: 'App Store' }))
  fireEvent.change(screen.getByLabelText('Your question (optional)'), { target: { value: 'Could I suggest a source?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('wasn’t confirmed')
  const receipt = submit.mock.calls[0][0].request_id
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'App Store' }))
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByRole('status')).toHaveTextContent('saved your question')
  expect(submit.mock.calls[1][0].request_id).toBe(receipt)
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'App Store' }))
  expect(screen.getByLabelText('Your question (optional)')).toHaveValue('')
})

it('requires a question or contact, accepts contact alone and shows useful invalid-contact feedback', async () => {
  const submit = vi.fn().mockRejectedValueOnce(new Error('invalid_contact')).mockResolvedValue(undefined)
  render(<EarlyAccess language="uk" submit={submit}><Open /></EarlyAccess>)
  fireEvent.click(screen.getByRole('button', { name: 'App Store' }))
  fireEvent.click(screen.getByRole('button', { name: 'Надіслати' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Напишіть запитання або залиште контакт')
  expect(submit).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Контакт (необов’язково)'), { target: { value: 'visitor@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Надіслати' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Перевірте контакт')
  fireEvent.change(screen.getByLabelText('Контакт (необов’язково)'), { target: { value: 'corrected@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Надіслати' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('сповіщення про запуск'))
  expect(submit.mock.calls[0][0].request_id).not.toBe(submit.mock.calls[1][0].request_id)
  expect(submit.mock.calls[1][0].question).toBe('')
})

it('a private template preview cannot claim a submission was saved', async () => {
  render(<EarlyAccess language="en"><Open /></EarlyAccess>)
  fireEvent.click(screen.getByRole('button', { name: 'App Store' }))
  fireEvent.change(screen.getByLabelText('Your question (optional)'), { target: { value: 'A preview question' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Open the published page')
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
