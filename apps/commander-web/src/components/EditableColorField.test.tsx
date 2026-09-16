import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { EditableColorField } from './EditableColorField'

function ControlledColor({ changed = vi.fn() }: { changed?: (value: string) => void }) {
  const [value, setValue] = useState('#1675F8')
  return <EditableColorField label="Button color" value={value} onChange={(next) => {
    changed(next)
    setValue(next)
  }} />
}

describe('EditableColorField', () => {
  it('makes the exact picker value selectable and pasteable', () => {
    const changed = vi.fn()
    render(<ControlledColor changed={changed} />)
    const hex = screen.getByRole('textbox', { name: 'Button · HEX · color hex' })
    expect(hex).toHaveValue('#1675F8')
    fireEvent.change(hex, { target: { value: '#dd9588' } })
    expect(changed).toHaveBeenLastCalledWith('#DD9588')
    expect(screen.getByLabelText('Button color')).toHaveValue('#dd9588')
  })

  it('restores the saved value when an incomplete pasted value loses focus', () => {
    render(<ControlledColor />)
    const hex = screen.getByRole('textbox', { name: 'Button · HEX · color hex' })
    fireEvent.change(hex, { target: { value: '#123' } })
    fireEvent.blur(hex)
    expect(hex).toHaveValue('#1675F8')
  })
})
