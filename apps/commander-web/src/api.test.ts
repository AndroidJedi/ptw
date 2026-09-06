import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./firebase', () => ({ appCheck: {} }))
vi.mock('firebase/app-check', () => ({ getToken: vi.fn(async () => ({ token: 'app-check-test' })) }))

import { ApiClient, fetchWithDeadline, resolveApiBaseUrl, resolveFirebaseTokens, validateImageResponse } from './api'

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
    const rejected = expect(request).rejects.toThrow(/API не відповів вчасно[\s\S]*Пояснення:[\s\S]*Що робити:[\s\S]*Повторити/)
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
    const rejected = expect(tokens).rejects.toThrow(/сесію власника[\s\S]*Firebase ID token або App Check[\s\S]*Що робити:/)
    await vi.advanceTimersByTimeAsync(25)
    await rejected
  })

  it('keeps the short default but accepts an explicit bounded deadline per API call', async () => {
    const timeout = vi.spyOn(window, 'setTimeout')
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })))
    const client = new ApiClient({ getIdToken: vi.fn(async () => 'owner-token') } as any)

    await client.post('/api/v1/slow-operation', { task: 'slow' }, { deadlineMs: 300_000 })

    expect(timeout).toHaveBeenCalledWith(expect.any(Function), 300_000)
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
      .rejects.toThrow(/integrity check[\s\S]*What to do:[\s\S]*returned image\/png; expected image\/jpeg/)
  })

  it('rejects corrupted bytes even when the media type is correct', async () => {
    const response = new Response('corrupted', { headers: { 'Content-Type': 'image/jpeg' } })

    await expect(validateImageResponse(response, 'image/jpeg', 'a'.repeat(64)))
      .rejects.toThrow(/integrity check[\s\S]*SHA-256 mismatch/)
  })
})

describe('actionable API errors', () => {
  it('explains authorization failures and gives an owner action in the selected language', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'invalid Firebase credentials' }), {
      status: 401, headers: { 'Content-Type': 'application/json' },
    })))
    const client = new ApiClient({ getIdToken: vi.fn(async () => 'owner-token') } as any, 'uk')

    await expect(client.get('/api/v1/projects?limit=100')).rejects.toThrow(
      /Сесія авторизації більше не дійсна[\s\S]*Пояснення:[\s\S]*Що робити:[\s\S]*HTTP 401 · GET \/api\/v1\/projects/,
    )
  })

  it('does not expose an internal 5xx detail while preserving useful technical context', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'private internal provider path' }), {
      status: 503, headers: { 'Content-Type': 'application/json' },
    })))
    const client = new ApiClient({ getIdToken: vi.fn(async () => 'owner-token') } as any, 'en')

    let message = ''
    try { await client.post('/api/v1/briefs', { raw_idea: 'test' }) } catch (cause) { message = (cause as Error).message }
    expect(message).toMatch(/PTW service could not complete[\s\S]*What to do:[\s\S]*HTTP 503 · POST \/api\/v1\/briefs/)
    expect(message).not.toContain('private internal provider path')
  })
})
