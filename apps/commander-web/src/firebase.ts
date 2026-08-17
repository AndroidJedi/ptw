import { initializeApp } from 'firebase/app'
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from 'firebase/app-check'
import { browserLocalPersistence, getAuth, GoogleAuthProvider, setPersistence } from 'firebase/auth'

const firebaseConfig = {
  apiKey: 'AIzaSyAQT3Qju_9XOn0FMnW2_oU5QrN40Zx1Srw',
  authDomain: 'provethemwrong-86123.firebaseapp.com',
  projectId: 'provethemwrong-86123',
  storageBucket: 'provethemwrong-86123.firebasestorage.app',
  messagingSenderId: '463396258702',
  appId: '1:463396258702:web:e52325c94f477ede1c9adf',
  measurementId: 'G-HD88RV65GL',
}

export const firebaseApp = initializeApp(firebaseConfig)
export const auth = getAuth(firebaseApp)
void setPersistence(auth, browserLocalPersistence)
export const googleProvider = new GoogleAuthProvider()
googleProvider.setCustomParameters({ prompt: 'select_account', login_hint: 'sgolovaschuk@gmail.com' })

const appCheckKey = import.meta.env.VITE_RECAPTCHA_ENTERPRISE_SITE_KEY
export const appCheck = appCheckKey
  ? initializeAppCheck(firebaseApp, {
      provider: new ReCaptchaEnterpriseProvider(appCheckKey),
      isTokenAutoRefreshEnabled: true,
    })
  : null
