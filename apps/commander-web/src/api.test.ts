import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl } from './api'

describe('API origin', () => {
  it('uses the Commander gateway for production builds without an override', () => {
    expect(resolveApiBaseUrl(undefined, true)).toBe('https://commander.proove-them-wrong.com')
  })

  it('keeps same-origin requests for the local Vite proxy', () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe('')
  })

  it('honors and normalizes an explicit API origin', () => {
    expect(resolveApiBaseUrl('https://example.test/', true)).toBe('https://example.test')
  })
})
