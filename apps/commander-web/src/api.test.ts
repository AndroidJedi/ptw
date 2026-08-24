import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./firebase', () => ({ appCheck: {} }))

import { fetchWithDeadline, resolveApiBaseUrl, resolveFirebaseTokens, validateImageResponse } from './api'

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
  it('turns a stalled request into an explicit safe-refresh error', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })))
    const request = fetchWithDeadline('/api/v1/overview', {}, 25)
    const rejected = expect(request).rejects.toThrow(/Стан на сервері міг уже змінитися.*Повторити/)
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

describe('authenticated image integrity', () => {
  it('accepts the declared media type, digest, and ETag', async () => {
    const sha256 = 'fe7984712ccab67b150e3e8337f9cb104bbf44d7b404fb8286e1ca8eb335eddb'
    const response = new Response('jpeg-fixture', {
      headers: { 'Content-Type': 'image/jpeg', ETag: `"${sha256}"` },
    })

    const blob = await validateImageResponse(response, 'image/jpeg', sha256)

    expect(blob.type).toBe('image/jpeg')
    expect(blob.size).toBe(12)
  })

  it('rejects a mislabeled inline PNG before rendering it', async () => {
    const response = new Response(new Uint8Array([0x89, 0x50, 0x4e, 0x47]), {
      headers: { 'Content-Type': 'image/png' },
    })

    await expect(validateImageResponse(response, 'image/jpeg', 'a'.repeat(64)))
      .rejects.toThrow('returned image/png; expected image/jpeg')
  })

  it('rejects corrupted bytes even when the media type is correct', async () => {
    const response = new Response('corrupted', { headers: { 'Content-Type': 'image/jpeg' } })

    await expect(validateImageResponse(response, 'image/jpeg', 'a'.repeat(64)))
      .rejects.toThrow('SHA-256 integrity check')
  })
})
