import { render, screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import { describe, expect, it } from 'vitest'
import { Shell } from './components/Shell'

describe('operator shell', () => {
  it('has no basic accessibility violations', async () => {
    const { container } = render(<Shell page="overview" onPage={() => undefined} language="uk" onLanguage={() => undefined}><h1>Огляд</h1></Shell>)
    expect(screen.getAllByText('Огляд').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Брендинг')).toHaveLength(2)
    expect(screen.getByRole('navigation', { name: 'Головна навігація на телефоні' }).querySelectorAll('button')).toHaveLength(5)
    expect(screen.queryByText('Пости')).not.toBeInTheDocument()
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
  })
})
