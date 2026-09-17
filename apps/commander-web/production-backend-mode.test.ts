import { describe, expect, it } from 'vitest'
import { validateProductionBackendMode } from './production-backend-mode'

describe('production-backed local mode', () => {
  it('requires a registered UUIDv4 App Check debug token', () => {
    expect(() => validateProductionBackendMode({ VITE_PRODUCTION_BACKEND: 'true' }, 'serve'))
      .toThrow(/requires one registered UUIDv4 VITE_APPCHECK_DEBUG_TOKEN/)
    expect(() => validateProductionBackendMode({
      VITE_PRODUCTION_BACKEND: 'true',
      VITE_APPCHECK_DEBUG_TOKEN: 'not-a-token',
    }, 'serve')).toThrow(/requires one registered UUIDv4 VITE_APPCHECK_DEBUG_TOKEN/)
  })

  it('accepts a local registered token only for the dev server', () => {
    const env = {
      VITE_PRODUCTION_BACKEND: 'true',
      VITE_APPCHECK_DEBUG_TOKEN: '9e55bbf6-3668-4ddd-819e-5064e834fdee',
    }
    expect(() => validateProductionBackendMode(env, 'serve')).not.toThrow()
    expect(() => validateProductionBackendMode(env, 'build')).toThrow(/dev-server-only mode/)
  })

  it('does not constrain ordinary local or production builds', () => {
    expect(() => validateProductionBackendMode({}, 'serve')).not.toThrow()
    expect(() => validateProductionBackendMode({}, 'build')).not.toThrow()
  })
})
