import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./firebase', () => ({ appCheck: {} }))

import { fetchWithDeadline, resolveApiBaseUrl, resolveFirebaseTokens } from './api'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

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

describe('API deadline', () => {
  it('turns a stalled request into an explicit overload error', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })))
    const request = fetchWithDeadline('/api/v1/overview', {}, 25)
    const rejected = expect(request).rejects.toThrow(/Сервер може бути перевантажений.*Повторити/)
    await vi.advanceTimersByTimeAsync(25)
    await rejected
  })

  it('turns stalled Firebase credentials into a retryable error before fetch', async () => {
    vi.useFakeTimers()
    const tokens = resolveFirebaseTokens(
      new Promise<string>(() => undefined),
      new Promise<{ token: string }>(() => undefined),
      25,
    )
    const rejected = expect(tokens).rejects.toThrow(/Firebase ID token \/ App Check.*Повторити/)
    await vi.advanceTimersByTimeAsync(25)
    await rejected
  })
})
