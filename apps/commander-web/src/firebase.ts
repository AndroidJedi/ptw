import { initializeApp } from 'firebase/app'
import { initializeAppCheck, ReCaptchaEnterpriseProvider, type AppCheck } from 'firebase/app-check'
import {
  browserLocalPersistence,
  browserPopupRedirectResolver,
  GoogleAuthProvider,
  initializeAuth,
} from 'firebase/auth'

const firebaseConfig = {
  apiKey: 'AIzaSyAQT3Qju_9XOn0FMnW2_oU5QrN40Zx1Srw',
  authDomain: 'provethemwrong-86123.firebaseapp.com',
  projectId: 'provethemwrong-86123',
  storageBucket: 'provethemwrong-86123.firebasestorage.app',
  messagingSenderId: '463396258702',
  appId: '1:463396258702:web:e52325c94f477ede1c9adf',
  measurementId: 'G-HD88RV65GL',
}

// App Check site keys are public browser configuration, like Firebase API keys.
// Keep the production key in source so a deploy cannot silently compile App Check
// out of the owner console when a shell environment variable is absent.
const productionAppCheckKey = '6LfFjYstAAAAAJaFuUPZYS9U17vROLcN7Fx6iOQL'

export const firebaseApp = initializeApp(firebaseConfig)
// Safari can leave Firebase's default IndexedDB persistence waiting forever,
// especially after a redirect or when another PTW tab has been open for a long
// time. Select localStorage before Auth initializes instead of migrating the
// session asynchronously after getAuth().
export const AUTH_PERSISTENCE_MARKER = 'ptw-auth-local-storage-v1'
export const auth = initializeAuth(firebaseApp, {
  persistence: browserLocalPersistence,
  popupRedirectResolver: browserPopupRedirectResolver,
})
export const googleProvider = new GoogleAuthProvider()
googleProvider.setCustomParameters({ prompt: 'select_account', login_hint: 'sgolovaschuk@gmail.com' })

const appCheckKey = import.meta.env.VITE_RECAPTCHA_ENTERPRISE_SITE_KEY || productionAppCheckKey
const e2eMode = import.meta.env.DEV && (import.meta.env.VITE_E2E === 'true' || new URLSearchParams(window.location.search).has('e2e'))
const appCheckDebugToken = import.meta.env.DEV ? import.meta.env.VITE_APPCHECK_DEBUG_TOKEN : undefined
if (appCheckDebugToken) {
  ;(self as typeof self & { FIREBASE_APPCHECK_DEBUG_TOKEN?: string }).FIREBASE_APPCHECK_DEBUG_TOKEN = appCheckDebugToken
}

export const appCheck: AppCheck = e2eMode
  ? undefined as unknown as AppCheck
  : initializeAppCheck(firebaseApp, {
    provider: new ReCaptchaEnterpriseProvider(appCheckKey),
    isTokenAutoRefreshEnabled: true,
  })
