import { getToken } from 'firebase/app-check'
import type { User } from 'firebase/auth'
import { appCheck } from './firebase'

const baseUrl = (import.meta.env.VITE_COMMANDER_API_URL || '').replace(/\/$/, '')

export class ApiClient {
  constructor(private readonly user: User) {}

  private async headers(json = false): Promise<HeadersInit> {
    const token = await this.user.getIdToken()
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
    if (json) headers['Content-Type'] = 'application/json'
    if (appCheck) headers['X-Firebase-AppCheck'] = (await getToken(appCheck, false)).token
    return headers
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      cache: 'no-store',
      credentials: 'omit',
      headers: { ...(await this.headers(Boolean(init.body))), ...init.headers },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }

  get<T>(path: string): Promise<T> { return this.request<T>(path) }
  post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  }

  async blob(path: string): Promise<Blob> {
    const response = await fetch(`${baseUrl}${path}`, {
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
