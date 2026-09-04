import { act, render, screen } from '@testing-library/react'
import type { User } from 'firebase/auth'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const firebase = vi.hoisted(() => ({
  auth: { currentUser: null as User | null },
  getRedirectResult: vi.fn(),
  onAuthStateChanged: vi.fn(),
  signInWithPopup: vi.fn(),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock('firebase/auth', () => ({
  getRedirectResult: firebase.getRedirectResult,
  onAuthStateChanged: firebase.onAuthStateChanged,
  signInWithPopup: firebase.signInWithPopup,
  signInWithRedirect: firebase.signInWithRedirect,
  signOut: firebase.signOut,
}))
vi.mock('./firebase', () => ({
  AUTH_PERSISTENCE_MARKER: 'ptw-auth-local-storage-v1',
  auth: firebase.auth,
  googleProvider: {},
}))
vi.mock('./api', () => ({ ApiClient: class {} }))
vi.mock('./components/Shell', () => ({ Shell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }))
vi.mock('./views/ProductBriefView', () => ({ ProductBriefView: () => <p>OWNER CONSOLE READY</p> }))
vi.mock('./views/StudioView', () => ({ StudioView: () => <p>POST EDITOR READY</p> }))

import App, { AUTH_BOOT_TIMEOUT_MS } from './App'

const owner = {
  email: 'sgolovaschuk@gmail.com',
  emailVerified: true,
  getIdToken: vi.fn(),
} as unknown as User

describe('Firebase redirect startup', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    firebase.auth.currentUser = null
    firebase.getRedirectResult.mockReset()
    firebase.onAuthStateChanged.mockReset()
    firebase.signOut.mockReset()
    firebase.onAuthStateChanged.mockReturnValue(() => undefined)
  })

  afterEach(() => vi.useRealTimers())

  it('opens the console from a redirect result even when the auth observer never fires', async () => {
    firebase.getRedirectResult.mockResolvedValue({ user: owner })
    render(<App />)
    expect(await screen.findByText('OWNER CONSOLE READY')).toBeInTheDocument()
    expect(screen.getByText('sgolovaschuk@gmail.com')).toBeInTheDocument()
  })

  it('shows sign-in when there is no redirect result and the auth observer never fires', async () => {
    firebase.getRedirectResult.mockResolvedValue(null)
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Увійти через Google' })).toBeInTheDocument()
  })

  it('releases a stalled Safari boot into a recoverable sign-in screen', async () => {
    vi.useFakeTimers()
    firebase.getRedirectResult.mockReturnValue(new Promise(() => undefined))
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('PTW')
    await act(async () => { await vi.advanceTimersByTimeAsync(AUTH_BOOT_TIMEOUT_MS) })
    expect(screen.getByRole('alert')).toHaveTextContent('Safari не завершив відновлення входу')
    expect(screen.getByRole('button', { name: 'Увійти через Google' })).toBeInTheDocument()
  })
})
