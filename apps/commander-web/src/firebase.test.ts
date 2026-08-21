import { beforeEach, describe, expect, it, vi } from 'vitest'

const sdk = vi.hoisted(() => ({
  app: {},
  auth: { currentUser: null },
  appCheck: {},
  localPersistence: {},
  popupRedirectResolver: {},
  initializeApp: vi.fn(),
  initializeAuth: vi.fn(),
  initializeAppCheck: vi.fn(),
  setCustomParameters: vi.fn(),
}))

vi.mock('firebase/app', () => ({ initializeApp: sdk.initializeApp }))
vi.mock('firebase/auth', () => ({
  browserLocalPersistence: sdk.localPersistence,
  browserPopupRedirectResolver: sdk.popupRedirectResolver,
  GoogleAuthProvider: class { setCustomParameters = sdk.setCustomParameters },
  initializeAuth: sdk.initializeAuth,
}))
vi.mock('firebase/app-check', () => ({
  initializeAppCheck: sdk.initializeAppCheck,
  ReCaptchaEnterpriseProvider: class {},
}))

describe('Firebase browser initialization', () => {
  beforeEach(() => {
    sdk.initializeApp.mockReturnValue(sdk.app)
    sdk.initializeAuth.mockReturnValue(sdk.auth)
    sdk.initializeAppCheck.mockReturnValue(sdk.appCheck)
  })

  it('selects localStorage persistence before Auth starts', async () => {
    const { auth, AUTH_PERSISTENCE_MARKER } = await import('./firebase')
    expect(auth).toBe(sdk.auth)
    expect(AUTH_PERSISTENCE_MARKER).toBe('ptw-auth-local-storage-v1')
    expect(sdk.initializeAuth).toHaveBeenCalledWith(sdk.app, {
      persistence: sdk.localPersistence,
      popupRedirectResolver: sdk.popupRedirectResolver,
    })
  })
})
