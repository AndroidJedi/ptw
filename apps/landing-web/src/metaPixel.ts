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
    fbq('init', META_PIXEL_ID)
    initialized[META_PIXEL_ID] = true
  }

  if (window.__natalMetaPixelLastPage === path) return
  window.__natalMetaPixelLastPage = path
  fbq('track', 'PageView')
}
