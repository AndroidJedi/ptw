export const META_PIXEL_ID = '1056720310312959'
export const META_PIXEL_SCRIPT_URL = 'https://connect.facebook.net/en_US/fbevents.js'

type MetaPixelFunction = ((...args: unknown[]) => void) & {
  callMethod?: (...args: unknown[]) => void
  loaded?: boolean
  queue: unknown[][]
  push?: MetaPixelFunction
  version?: string
}

declare global {
  interface Window {
    _fbq?: MetaPixelFunction
    fbq?: MetaPixelFunction
    __natalMetaPixelInitialized?: Record<string, boolean>
    __natalMetaPixelLastPage?: string
  }
}

function installQueue(): MetaPixelFunction {
  if (window.fbq) return window.fbq
  const queue = function (...args: unknown[]) {
    if (queue.callMethod) queue.callMethod(...args)
    else queue.queue.push(args)
  } as MetaPixelFunction
  queue.queue = []
  queue.loaded = true
  queue.version = '2.0'
  queue.push = queue
  window.fbq = queue
  window._fbq = queue
  return queue
}

export function trackMetaPageView(path: string): void {
  if (!/^\/[A-Za-z0-9/_-]*$/.test(path)) return
  const fbq = installQueue()
  const initialized = window.__natalMetaPixelInitialized ||= {}

  if (!initialized[META_PIXEL_ID]) {
    const script = document.createElement('script')
    script.async = true
    script.src = META_PIXEL_SCRIPT_URL
    script.dataset.metaPixel = META_PIXEL_ID
    document.head.append(script)
    fbq('consent', 'grant')
    fbq('set', 'autoConfig', false, META_PIXEL_ID)
    fbq('init', META_PIXEL_ID)
    initialized[META_PIXEL_ID] = true
  } else fbq('consent', 'grant')

  if (window.__natalMetaPixelLastPage === path) return
  window.__natalMetaPixelLastPage = path
  fbq('track', 'PageView')
}

export function revokeMetaConsent(): void {
  const fbq = window.fbq
  if (fbq) {
    // Withdrawal before script execution must also remove queued PageViews.
    if (!fbq.callMethod) fbq.queue = fbq.queue.filter(command => command[0] !== 'track' && command[0] !== 'consent')
    fbq('consent', 'revoke')
  }
  delete window.__natalMetaPixelLastPage
  const labels = window.location.hostname.split('.')
  const domains = ['', ...labels.map((_, index) => labels.slice(index).join('.'))]
  // Clear root-path host-only and parent-domain Pixel cookies. The browser
  // rejects unrelated domains and public suffixes.
  for (const name of ['_fbp', '_fbc']) for (const domain of domains) {
    document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax${domain ? `; Domain=${domain}` : ''}`
  }
}
