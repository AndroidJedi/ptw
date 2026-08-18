import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const LEGACY_HOST = 'provethemwrong-86123.web.app'
const CANONICAL_HOST = 'provethemwrong-86123.firebaseapp.com'

if (window.location.hostname === LEGACY_HOST) {
  const canonicalUrl = new URL(window.location.href)
  canonicalUrl.hostname = CANONICAL_HOST
  window.location.replace(canonicalUrl)
} else {
  void import('./App').then(({ default: App }) => {
    createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
  })

  if ('serviceWorker' in navigator && import.meta.env.PROD) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'))
  }
}
