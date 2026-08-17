import { describe, expect, it } from 'vitest'
import { local } from './i18n'

describe('local', () => {
  it('defaults to the requested localized value', () => {
    expect(local({ en: 'Mission', uk: 'Місія' }, 'uk')).toBe('Місія')
    expect(local({ en: 'Mission', uk: 'Місія' }, 'en')).toBe('Mission')
  })
})
