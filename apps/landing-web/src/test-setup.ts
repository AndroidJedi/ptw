import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

if (!window.localStorage) {
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', { configurable: true, value: {
    get length() { return values.size },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => { values.delete(key) },
    setItem: (key: string, value: string) => { values.set(key, value) },
  } satisfies Storage })
}

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  delete window.fbq
  delete window._fbq
  delete window.__natalMetaPixelInitialized
  delete window.__natalMetaPixelLastPage
  document.querySelectorAll('script[data-meta-pixel]').forEach(script => script.remove())
})
