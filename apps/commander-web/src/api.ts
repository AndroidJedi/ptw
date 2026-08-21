import { getToken } from 'firebase/app-check'
import type { User } from 'firebase/auth'
import { appCheck } from './firebase'

const PRODUCTION_API_URL = 'https://commander.proove-them-wrong.com'
export const API_DEADLINE_MS = 15_000
export const FIREBASE_TOKEN_DEADLINE_MS = 10_000

export function resolveApiBaseUrl(configured: string | undefined, production: boolean) {
  return (configured || (production ? PRODUCTION_API_URL : '')).replace(/\/$/, '')
}

const baseUrl = resolveApiBaseUrl(import.meta.env.VITE_COMMANDER_API_URL, import.meta.env.PROD)

export async function fetchWithDeadline(
  input: RequestInfo | URL,
  init: RequestInit = {},
  deadlineMs = API_DEADLINE_MS,
): Promise<Response> {
  const controller = new AbortController()
  const callerSignal = init.signal
  const abortFromCaller = () => controller.abort(callerSignal?.reason)
  if (callerSignal?.aborted) abortFromCaller()
  else callerSignal?.addEventListener('abort', abortFromCaller, { once: true })
  const timeout = window.setTimeout(() => controller.abort('api-deadline'), deadlineMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (cause) {
    if (controller.signal.aborted && !callerSignal?.aborted) {
      throw new Error('API не відповідає протягом 15 секунд. Стан на сервері міг уже змінитися — натисніть «Повторити», щоб безпечно оновити екран.')
    }
    throw cause
  } finally {
    window.clearTimeout(timeout)
    callerSignal?.removeEventListener('abort', abortFromCaller)
  }
}

export async function resolveFirebaseTokens(
  idTokenRequest: Promise<string>,
  appCheckTokenRequest: Promise<{ token: string }>,
  deadlineMs = FIREBASE_TOKEN_DEADLINE_MS,
): Promise<[string, string]> {
  let timeout = 0
  const seconds = Math.ceil(deadlineMs / 1000)
  try {
    return await Promise.race([
      Promise.all([idTokenRequest, appCheckTokenRequest]).then(([idToken, appCheckToken]) => [idToken, appCheckToken.token] as [string, string]),
      new Promise<never>((_resolve, reject) => {
        timeout = window.setTimeout(() => reject(new Error(`Firebase ID token / App Check не готові протягом ${seconds} секунд. Оновіть сторінку й натисніть «Повторити».`)), deadlineMs)
      }),
    ])
  } finally {
    window.clearTimeout(timeout)
  }
}

async function jsonBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new Error(`API повернув неочікувану відповідь (HTTP ${response.status}). Оновіть сторінку й повторіть.`)
  }
  return response.json()
}

export class ApiClient {
  constructor(private readonly user: User) {}

  private async headers(json = false): Promise<HeadersInit> {
    const e2eMode = import.meta.env.DEV && (import.meta.env.VITE_E2E === 'true' || new URLSearchParams(window.location.search).has('e2e'))
    const [token, appCheckToken] = e2eMode
      ? [await this.user.getIdToken(), 'e2e-app-check']
      : await resolveFirebaseTokens(this.user.getIdToken(), getToken(appCheck, false))
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
    if (json) headers['Content-Type'] = 'application/json'
    headers['X-Firebase-AppCheck'] = appCheckToken
    return headers
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetchWithDeadline(`${baseUrl}${path}`, {
      ...init,
      cache: 'no-store',
      credentials: 'omit',
      headers: { ...(await this.headers(Boolean(init.body))), ...init.headers },
    })
    const body = await jsonBody(response).catch((cause) => {
      if (!response.ok) return {}
      throw cause
    }) as { detail?: unknown } | T
    const rawDetail = body && typeof body === 'object' && 'detail' in body ? body.detail : ''
    const detail = typeof rawDetail === 'string'
      ? rawDetail
      : rawDetail ? JSON.stringify(rawDetail) : ''
    if (!response.ok) throw new Error(detail || `HTTP ${response.status}`)
    return body as T
  }

  get<T>(path: string): Promise<T> { return this.request<T>(path) }
  post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  }

  async blob(path: string): Promise<Blob> {
    const response = await fetchWithDeadline(`${baseUrl}${path}`, {
      cache: 'no-store', credentials: 'omit', headers: await this.headers(),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.blob()
  }

  async websocketUrl(path: string): Promise<string> {
    const { ticket } = await this.post<{ ticket: string }>('/api/v1/ws-tickets', { path })
    const origin = baseUrl || window.location.origin
    const url = new URL(path, origin)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.searchParams.set('ticket', ticket)
    return url.toString()
  }
}
