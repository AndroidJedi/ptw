import { getRedirectResult, onAuthStateChanged, signInWithPopup, signInWithRedirect, signOut, type User } from 'firebase/auth'
import { LogIn, LogOut, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { ApiClient } from './api'
import { auth, googleProvider } from './firebase'
import { Shell } from './components/Shell'
import type { Language } from './i18n'
import type { Page } from './types'
import { IdeasView } from './views/IdeasView'
import { JobsView } from './views/JobsView'
import { MoreView } from './views/MoreView'
import { OverviewView } from './views/OverviewView'
import { PostsView } from './views/PostsView'

const OWNER = 'sgolovaschuk@gmail.com'

function prefersRedirectSignIn() {
  return window.matchMedia?.('(pointer: coarse)').matches
    || /Android|iPad|iPhone|iPod/i.test(window.navigator.userAgent)
}

async function enforceOwner(user: User) {
  if (!user.emailVerified || user.email?.toLowerCase() !== OWNER) {
    await signOut(auth)
    throw new Error('Доступ дозволено лише підтвердженому обліковому запису власника.')
  }
}

function Login() {
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void getRedirectResult(auth)
      .then((result) => result ? enforceOwner(result.user) : undefined)
      .catch((cause: { message?: string }) => {
        if (active) setError(cause.message || 'Не вдалося увійти.')
      })
    return () => { active = false }
  }, [])

  const login = async () => {
    setError('')
    try {
      if (prefersRedirectSignIn()) {
        await signInWithRedirect(auth, googleProvider)
        return
      }
      const result = await signInWithPopup(auth, googleProvider)
      await enforceOwner(result.user)
    } catch (cause) {
      const error = cause as { code?: string; message?: string }
      if (error.code === 'auth/popup-blocked' || error.code === 'auth/cancelled-popup-request') {
        await signInWithRedirect(auth, googleProvider)
      } else setError(error.message || 'Не вдалося увійти.')
    }
  }
  return <main className="login-page">
    <div className="login-mark">PTW</div>
    <p>ПРИВАТНА ПАНЕЛЬ ВЛАСНИКА</p><h1>Керуйте всією системою<br />з одного місця.</h1>
    <div className="login-security"><ShieldCheck /><span>Google Identity · App Check · лише власник</span></div>
    <button className="primary login-button" onClick={login}><LogIn />Увійти через Google</button>
    {error && <p role="alert" className="login-error">{error}</p>}
  </main>
}

function Console({ user }: { user: User }) {
  const [page, setPage] = useState<Page>('overview')
  const [language, setLanguage] = useState<Language>('uk')
  const api = useMemo(() => new ApiClient(user), [user])
  return <Shell page={page} onPage={setPage} language={language} onLanguage={() => setLanguage(language === 'uk' ? 'en' : 'uk')}>
    <div className="top-owner"><span>{user.email}</span><button onClick={() => signOut(auth)} aria-label="Вийти"><LogOut /></button></div>
    {page === 'overview' && <OverviewView api={api} language={language} />}
    {page === 'ideas' && <IdeasView api={api} language={language} />}
    {page === 'posts' && <PostsView api={api} language={language} />}
    {page === 'jobs' && <JobsView api={api} />}
    {page === 'more' && <MoreView api={api} />}
  </Shell>
}

function LiveApp() {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  useEffect(() => onAuthStateChanged(auth, (candidate) => {
    if (candidate && (candidate.email?.toLowerCase() !== OWNER || !candidate.emailVerified)) void signOut(auth)
    else setUser(candidate)
  }), [])
  if (user === undefined) return <main className="boot" role="status">PTW</main>
  return user ? <Console user={user} /> : <Login />
}

const e2eOwner = {
  email: OWNER,
  emailVerified: true,
  getIdToken: async () => 'e2e-owner-token',
} as unknown as User

export default function App() {
  const e2eMode = import.meta.env.DEV && (import.meta.env.VITE_E2E === 'true' || new URLSearchParams(window.location.search).has('e2e'))
  return e2eMode ? <Console user={e2eOwner} /> : <LiveApp />
}
