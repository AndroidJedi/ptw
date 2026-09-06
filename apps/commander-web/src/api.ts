import { getToken } from 'firebase/app-check'
import type { User } from 'firebase/auth'
import { appCheck } from './firebase'
import type { Language } from './i18n'

const PRODUCTION_API_URL = 'https://commander.proove-them-wrong.com'
export const API_DEADLINE_MS = 15_000
export const FIREBASE_TOKEN_DEADLINE_MS = 10_000

export interface ApiRequestOptions {
  deadlineMs?: number
}

type ApiFailureKind = 'timeout' | 'credentials' | 'network' | 'http' | 'response' | 'integrity'

interface ApiFailureDetails {
  kind: ApiFailureKind
  method?: string
  path?: string
  status?: number
  detail?: string
  deadlineMs?: number
}

function compactDetail(value: unknown): string {
  if (typeof value === 'string') return value.replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300)
  if (!value) return ''
  try { return JSON.stringify(value).replace(/\s+/g, ' ').slice(0, 300) } catch { return '' }
}

function endpointLabel(path = ''): string {
  if (!path) return 'API'
  try { return new URL(path, 'https://ptw.invalid').pathname } catch { return path.split('?', 1)[0] || 'API' }
}

function apiFailureMessage(value: ApiFailureDetails, language: Language): string {
  const uk = language === 'uk'
  const status = value.status
  const detail = compactDetail(value.detail)
  const method = (value.method || 'GET').toUpperCase()
  const endpoint = endpointLabel(value.path)
  let title = uk ? 'Не вдалося виконати запит до API.' : 'The API request could not be completed.'
  let explanation = uk
    ? 'Застосунок не отримав коректної відповіді від сервера.'
    : 'The app did not receive a valid response from the server.'
  let instruction = uk
    ? 'Оновіть дані на екрані та повторіть дію один раз.'
    : 'Refresh the data on this screen and retry the action once.'

  if (value.kind === 'timeout') {
    const seconds = Math.ceil((value.deadlineMs || API_DEADLINE_MS) / 1000)
    const duration = seconds >= 120
      ? (uk ? `${Math.ceil(seconds / 60)} хвилин` : `${Math.ceil(seconds / 60)} minutes`)
      : (uk ? `${seconds} секунд` : `${seconds} seconds`)
    title = uk ? 'API не відповів вчасно.' : 'The API did not respond in time.'
    explanation = uk
      ? `Запит перевищив безпечний ліміт ${duration}. Операція на сервері могла вже завершитися.`
      : `The request exceeded the safe ${duration} limit. The operation may already have completed on the server.`
    instruction = uk
      ? 'Спочатку оновіть екран і перевірте поточний стан. Лише потім натисніть «Повторити».'
      : 'Refresh the screen and check the current state first. Only then select Retry.'
  } else if (value.kind === 'credentials') {
    title = uk ? 'Не вдалося підтвердити сесію власника.' : 'The owner session could not be verified.'
    explanation = uk
      ? 'Firebase ID token або App Check не були готові, тому запит не відправлено.'
      : 'The Firebase ID token or App Check token was not ready, so the request was not sent.'
    instruction = uk
      ? 'Оновіть сторінку. Якщо це повториться — вийдіть, увійдіть через Google знову й повторіть дію.'
      : 'Reload the page. If this repeats, sign out, sign in with Google again, and retry.'
  } else if (value.kind === 'network') {
    title = uk ? 'Немає з’єднання з API.' : 'The API could not be reached.'
    explanation = uk
      ? 'Браузер не зміг встановити захищене з’єднання. Дані на сервері не видалено.'
      : 'The browser could not establish a secure connection. Server data was not deleted.'
    instruction = uk
      ? 'Перевірте інтернет-з’єднання, вимкніть VPN або блокувальник для цього сайту та натисніть «Повторити».'
      : 'Check your connection, disable any VPN or blocker for this site, then select Retry.'
  } else if (value.kind === 'response') {
    title = uk ? 'API повернув неочікувану відповідь.' : 'The API returned an unexpected response.'
    explanation = uk
      ? 'Формат відповіді не відповідає контракту застосунку; отримані дані не застосовано.'
      : 'The response format did not match the app contract, so the returned data was not applied.'
    instruction = uk
      ? 'Оновіть сторінку й повторіть. Якщо помилка лишиться, передайте технічні дані нижче.'
      : 'Reload and retry. If the error remains, report the technical details below.'
  } else if (value.kind === 'integrity') {
    title = uk ? 'Медіафайл не пройшов перевірку цілісності.' : 'The media file failed its integrity check.'
    explanation = uk
      ? 'Тип, розмір або SHA-256 отриманих байтів не збігається зі збереженим записом, тому файл не показано.'
      : 'The received bytes did not match the stored type, size, or SHA-256, so the file was not displayed.'
    instruction = uk
      ? 'Оновіть екран. Якщо помилка повториться, не використовуйте файл і передайте технічні дані нижче.'
      : 'Refresh the screen. If this repeats, do not use the file and report the technical details below.'
  } else if (value.kind === 'http') {
    if (status === 400 || status === 422) {
      title = uk ? 'API відхилив дані запиту.' : 'The API rejected the request data.'
      explanation = detail || (uk ? 'Одне або кілька полів не відповідають дозволеному формату.' : 'One or more fields did not match the accepted format.')
      instruction = uk ? 'Перевірте введені поля, виправте їх і повторіть дію.' : 'Review the entered fields, correct them, and retry.'
    } else if (status === 401) {
      title = uk ? 'Сесія авторизації більше не дійсна.' : 'The authorization session is no longer valid.'
      explanation = uk ? 'API не прийняв поточні Firebase credentials.' : 'The API did not accept the current Firebase credentials.'
      instruction = uk ? 'Оновіть сторінку. Якщо доступ не відновиться — вийдіть і знову увійдіть через Google.' : 'Reload the page. If access is not restored, sign out and sign in with Google again.'
    } else if (status === 403) {
      title = uk ? 'API заборонив цю дію.' : 'The API denied this action.'
      explanation = uk ? 'Поточна сесія не пройшла перевірку власника або App Check.' : 'The current session did not pass the owner or App Check verification.'
      instruction = uk ? 'Увійдіть підтвердженим обліковим записом власника та повторіть дію.' : 'Sign in with the verified owner account and retry.'
    } else if (status === 404) {
      title = uk ? 'Запитаний об’єкт не знайдено.' : 'The requested item was not found.'
      explanation = detail || (uk ? 'Об’єкт міг бути видалений або належати іншому проєкту.' : 'The item may have been removed or may belong to another Project.')
      instruction = uk ? 'Оновіть список, виберіть чинний проєкт або об’єкт і повторіть дію.' : 'Refresh the list, select an existing Project or item, and retry.'
    } else if (status === 409) {
      title = uk ? 'Дані на сервері вже змінилися.' : 'The server data has already changed.'
      explanation = detail || (uk ? 'Запит конфліктує з новішим станом або поточним етапом операції.' : 'The request conflicts with a newer state or the operation’s current stage.')
      instruction = uk ? 'Оновіть екран, перевірте новий стан і повторіть потрібну дію.' : 'Refresh the screen, review the new state, and retry the intended action.'
    } else if (status === 423) {
      title = uk ? 'Генерацію тимчасово зупинено.' : 'Generation is temporarily stopped.'
      explanation = uk ? 'У PTW увімкнено аварійну зупинку; нові операції не запускаються.' : 'PTW emergency stop is active, so new operations are not starting.'
      instruction = uk ? 'Перевірте стан системи, вимкніть аварійну зупинку лише після усунення причини та повторіть.' : 'Check system status, clear the emergency stop only after resolving its cause, then retry.'
    } else if (status === 429) {
      title = uk ? 'Досягнуто ліміт запитів.' : 'The request limit was reached.'
      explanation = uk ? 'Сервіс тимчасово обмежив частоту операцій.' : 'The service temporarily limited request frequency.'
      instruction = uk ? 'Зачекайте хвилину, оновіть стан і повторіть дію один раз.' : 'Wait a minute, refresh the state, and retry once.'
    } else if (status && status >= 500) {
      title = uk ? 'Сервіс PTW тимчасово не виконав запит.' : 'A PTW service could not complete the request.'
      explanation = /chatgpt authorization/i.test(detail)
        ? (uk ? 'Сервіс авторизації ChatGPT/Codex зараз недоступний.' : 'The ChatGPT/Codex authorization service is currently unavailable.')
        : /validation/i.test(detail)
          ? (uk ? 'Сервіс генерації або збереження даних зараз недоступний.' : 'The generation or persistence service is currently unavailable.')
          : (uk ? 'Сталася внутрішня або залежна сервісна помилка. Збережені дані не слід вважати втраченими.' : 'An internal or dependent service failed. Existing saved data should not be considered lost.')
      instruction = uk
        ? 'Оновіть екран і перевірте стан. Якщо помилка повториться, передайте технічні дані нижче.'
        : 'Refresh the screen and check the state. If the error repeats, report the technical details below.'
    } else {
      explanation = detail || explanation
    }
  }

  const technical = [status ? `HTTP ${status}` : '', `${method} ${endpoint}`, value.kind === 'integrity' ? detail : ''].filter(Boolean).join(' · ')
  return [
    title,
    `${uk ? 'Пояснення' : 'Explanation'}: ${explanation}`,
    `${uk ? 'Що робити' : 'What to do'}: ${instruction}`,
    `${uk ? 'Технічні дані' : 'Technical details'}: ${technical}.`,
  ].join('\n')
}

export class ApiFailure extends Error {
  constructor(readonly details: ApiFailureDetails, language: Language = 'uk') {
    super(apiFailureMessage(details, language))
    this.name = 'ApiFailure'
  }
}

function contextualApiFailure(cause: unknown, language: Language, method: string, path: string): ApiFailure {
  if (cause instanceof ApiFailure) return new ApiFailure({ ...cause.details, method, path }, language)
  const code = cause && typeof cause === 'object' && 'code' in cause ? String(cause.code || '') : ''
  if (code.startsWith('auth/') || code.startsWith('appCheck/')) {
    return new ApiFailure({ kind: 'credentials', method, path }, language)
  }
  return new ApiFailure({ kind: 'network', method, path }, language)
}

export function resolveApiBaseUrl(configured: string | undefined, production: boolean) {
  return (configured || (production ? PRODUCTION_API_URL : '')).replace(/\/$/, '')
}

const baseUrl = resolveApiBaseUrl(import.meta.env.VITE_COMMANDER_API_URL, import.meta.env.PROD)
const localStudioMode = import.meta.env.DEV && import.meta.env.VITE_LOCAL_STUDIO === 'true'

function routeBaseUrl(path: string) {
  return localStudioMode && (path.startsWith('/api/v1/studio') || path.startsWith('/api/v1/landings')) ? '' : baseUrl
}

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
      throw new ApiFailure({ kind: 'timeout', deadlineMs })
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
  try {
    return await Promise.race([
      Promise.all([idTokenRequest, appCheckTokenRequest]).then(([idToken, appCheckToken]) => [idToken, appCheckToken.token] as [string, string]),
      new Promise<never>((_resolve, reject) => {
        timeout = window.setTimeout(() => reject(new ApiFailure({ kind: 'credentials', deadlineMs })), deadlineMs)
      }),
    ])
  } finally {
    window.clearTimeout(timeout)
  }
}

async function jsonBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new ApiFailure({ kind: 'response', status: response.status })
  }
  try { return await response.json() } catch { throw new ApiFailure({ kind: 'response', status: response.status }) }
}

function sha256Hex(bytes: ArrayBuffer) {
  return crypto.subtle.digest('SHA-256', bytes).then((digest) =>
    Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join(''),
  )
}

export async function validateImageResponse(
  response: Response,
  expectedMimeType: string,
  expectedSha256: string,
  language: Language = 'en',
  path = '/authenticated-media',
): Promise<Blob> {
  if (!response.ok) throw new ApiFailure({ kind: 'http', method: 'GET', path, status: response.status }, language)
  const contentType = (response.headers.get('content-type') || '').split(';', 1)[0].trim().toLowerCase()
  if (contentType !== expectedMimeType.toLowerCase()) {
    throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: `returned ${contentType || 'no content type'}; expected ${expectedMimeType}` }, language)
  }
  const bytes = await response.arrayBuffer()
  if (!bytes.byteLength) throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: 'empty response' }, language)
  const digest = await sha256Hex(bytes)
  if (digest !== expectedSha256.toLowerCase()) {
    throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: 'SHA-256 mismatch' }, language)
  }
  const etag = response.headers.get('etag')
  if (etag && etag !== `"${expectedSha256}"`) {
    throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: 'ETag mismatch' }, language)
  }
  return new Blob([bytes], { type: contentType })
}

export class ApiClient {
  constructor(private readonly user: User, private readonly language: Language = 'uk') {}

  private async response(path: string, init: RequestInit, options: ApiRequestOptions): Promise<Response> {
    const method = (init.method || 'GET').toUpperCase()
    try {
      return await fetchWithDeadline(`${routeBaseUrl(path)}${path}`, {
        ...init,
        cache: 'no-store',
        credentials: 'omit',
        headers: { ...(await this.headers(path, Boolean(init.body))), ...init.headers },
      }, options.deadlineMs ?? API_DEADLINE_MS)
    } catch (cause) {
      throw contextualApiFailure(cause, this.language, method, path)
    }
  }

  private async headers(path: string, json = false): Promise<HeadersInit> {
    const e2eMode = import.meta.env.DEV && (import.meta.env.VITE_E2E === 'true' || new URLSearchParams(window.location.search).has('e2e'))
    const localStudio = localStudioMode && (path.startsWith('/api/v1/studio') || path.startsWith('/api/v1/landings'))
    const [token, appCheckToken] = e2eMode || localStudio
      ? [await this.user.getIdToken(), 'e2e-app-check']
      : await resolveFirebaseTokens(this.user.getIdToken(), getToken(appCheck, false))
    const ownerToken = localStudio ? 'e2e-owner-token' : token
    const headers: Record<string, string> = { Authorization: `Bearer ${ownerToken}` }
    if (json) headers['Content-Type'] = 'application/json'
    headers['X-Firebase-AppCheck'] = appCheckToken
    return headers
  }

  async request<T>(path: string, init: RequestInit = {}, options: ApiRequestOptions = {}): Promise<T> {
    const method = (init.method || 'GET').toUpperCase()
    const response = await this.response(path, init, options)
    const body = await jsonBody(response).catch((cause) => {
      if (!response.ok) return {}
      throw contextualApiFailure(cause, this.language, method, path)
    }) as { detail?: unknown } | T
    const rawDetail = body && typeof body === 'object' && 'detail' in body ? body.detail : ''
    const detail = compactDetail(rawDetail)
    if (!response.ok) throw new ApiFailure({ kind: 'http', method, path, status: response.status, detail }, this.language)
    return body as T
  }

  get<T>(path: string, options: ApiRequestOptions = {}): Promise<T> { return this.request<T>(path, {}, options) }
  post<T>(path: string, body: unknown, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) }, options)
  }

  async postMedia(
    path: string, body: unknown, expectedMimeType: string,
    options: ApiRequestOptions = {},
  ): Promise<Blob> {
    const response = await this.response(path, { method: 'POST', body: JSON.stringify(body) }, options)
    if (!response.ok) {
      const value = await jsonBody(response).catch(() => ({})) as { detail?: unknown }
      throw new ApiFailure({ kind: 'http', method: 'POST', path, status: response.status, detail: compactDetail(value.detail) }, this.language)
    }
    const contentType = (response.headers.get('content-type') || '').split(';', 1)[0].trim().toLowerCase()
    if (contentType !== expectedMimeType.toLowerCase()) {
      throw new ApiFailure({ kind: 'integrity', method: 'POST', path, detail: `returned ${contentType || 'no content type'}; expected ${expectedMimeType}` }, this.language)
    }
    const bytes = await response.arrayBuffer()
    if (!bytes.byteLength) throw new ApiFailure({ kind: 'integrity', method: 'POST', path, detail: 'empty response' }, this.language)
    const expectedSha256 = response.headers.get('x-ptw-content-sha256') || ''
    if (!/^[0-9a-f]{64}$/i.test(expectedSha256)) {
      throw new ApiFailure({ kind: 'integrity', method: 'POST', path, detail: 'missing SHA-256' }, this.language)
    }
    const digest = await sha256Hex(bytes)
    if (digest !== expectedSha256.toLowerCase()) {
      throw new ApiFailure({ kind: 'integrity', method: 'POST', path, detail: 'SHA-256 mismatch' }, this.language)
    }
    return new Blob([bytes], { type: contentType })
  }

  async image(path: string, expectedMimeType: string, expectedSha256: string): Promise<Blob> {
    const response = await this.response(path, {}, {})
    return validateImageResponse(response, expectedMimeType, expectedSha256, this.language, path)
  }

  async media(path: string, expectedMimeType: string, expectedSha256: string): Promise<Blob> {
    return this.image(path, expectedMimeType, expectedSha256)
  }

  async download(path: string, expectedMimeType: string, options: ApiRequestOptions = {}): Promise<Blob> {
    const response = await this.response(path, {}, options)
    if (!response.ok) {
      const value = await jsonBody(response).catch(() => ({})) as { detail?: unknown }
      throw new ApiFailure({ kind: 'http', method: 'GET', path, status: response.status, detail: compactDetail(value.detail) }, this.language)
    }
    const contentType = (response.headers.get('content-type') || '').split(';', 1)[0].trim().toLowerCase()
    if (contentType !== expectedMimeType.toLowerCase()) throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: `returned ${contentType || 'no content type'}; expected ${expectedMimeType}` }, this.language)
    const bytes = await response.arrayBuffer()
    const expectedSha256 = response.headers.get('x-ptw-content-sha256') || ''
    if (!/^[0-9a-f]{64}$/i.test(expectedSha256)) throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: 'missing SHA-256' }, this.language)
    if (await sha256Hex(bytes) !== expectedSha256.toLowerCase()) throw new ApiFailure({ kind: 'integrity', method: 'GET', path, detail: 'SHA-256 mismatch' }, this.language)
    return new Blob([bytes], { type: contentType })
  }

  async websocketUrl(path: string): Promise<string> {
    const { ticket } = await this.post<{ ticket: string }>('/api/v1/ws-tickets', { path })
    const origin = routeBaseUrl(path) || window.location.origin
    const url = new URL(path, origin)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.searchParams.set('ticket', ticket)
    return url.toString()
  }
}
