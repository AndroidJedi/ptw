import { getRedirectResult, onAuthStateChanged, signInWithPopup, signInWithRedirect, signOut, type User } from 'firebase/auth'
import { LogIn, LogOut, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { ApiClient } from './api'
import { AUTH_PERSISTENCE_MARKER, auth, googleProvider } from './firebase'
import { Shell } from './components/Shell'
import { ProjectSwitcher } from './components/ProjectSwitcher'
import type { Language } from './i18n'
import type { Page, ValidationProject } from './types'
import { AdsView } from './views/AdsView'
import { AdminView } from './views/AdminView'
import { LandingPlaceholderView } from './views/LandingPlaceholderView'
import { ProductBriefView } from './views/ProductBriefView'
import { StudioView } from './views/StudioView'

const OWNER = 'sgolovaschuk@gmail.com'
export const AUTH_BOOT_TIMEOUT_MS = 10_000

function initialConsoleLocation(): { page: Page; projectId: string | null } {
  const params = new URLSearchParams(window.location.search)
  const requestedPage = params.get('page')
  const known = ['briefs', 'studio', 'ads', 'landing', 'admin'].includes(requestedPage || '')
  const page: Page = known
    ? requestedPage as Page
    : 'briefs'
  if (requestedPage && !known) {
    params.delete('page'); params.delete('run')
    const search = params.toString()
    window.history.replaceState({}, '', `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`)
  }
  return { page, projectId: params.get('project') }
}

function writeConsoleLocation(page: Page, projectId: string | null) {
  const params = new URLSearchParams(window.location.search)
  if (page === 'briefs') params.delete('page')
  else params.set('page', page)
  if (projectId) params.set('project', projectId)
  else params.delete('project')
  params.delete('run')
  const search = params.toString()
  window.history.replaceState({}, '', `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`)
}

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

function errorMessage(cause: unknown, fallback: string) {
  return cause && typeof cause === 'object' && 'message' in cause
    ? String(cause.message || fallback)
    : fallback
}

function Login({ startupError = '' }: { startupError?: string }) {
  const [loginError, setLoginError] = useState('')

  const login = async () => {
    setLoginError('')
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
        try {
          await signInWithRedirect(auth, googleProvider)
        } catch (redirectCause) {
          setLoginError(errorMessage(redirectCause, 'Не вдалося увійти.'))
        }
      } else setLoginError(errorMessage(error, 'Не вдалося увійти.'))
    }
  }
  const visibleError = loginError || startupError
  return <main className="login-page" data-auth-persistence={AUTH_PERSISTENCE_MARKER}>
    <div className="login-mark">PTW</div>
    <p>ПРИВАТНА ПАНЕЛЬ ВЛАСНИКА</p><h1>Керуйте всією системою<br />з одного місця.</h1>
    <div className="login-security"><ShieldCheck /><span>Google Identity · App Check · лише власник</span></div>
    <button className="primary login-button" onClick={login}><LogIn />Увійти через Google</button>
    {visibleError && <p role="alert" className="login-error">{visibleError}</p>}
  </main>
}

function Console({ user }: { user: User }) {
  const initialLocation = useMemo(initialConsoleLocation, [])
  const [page, setPage] = useState<Page>(initialLocation.page)
  const [projects, setProjects] = useState<ValidationProject[] | null>(null)
  const [projectId, setProjectId] = useState<string | null>(initialLocation.projectId)
  const [projectError, setProjectError] = useState('')
  const [language, setLanguage] = useState<Language>('uk')
  const api = useMemo(() => new ApiClient(user), [user])

  const refreshProjects = async (preferredId?: string) => {
    const value = await api.get<{ items: ValidationProject[] }>('/api/v1/projects?limit=100')
    setProjects(value.items)
    const requested = preferredId || new URLSearchParams(window.location.search).get('project')
    const nextId = value.items.some((item) => item.project_id === requested)
      ? requested
      : value.items[0]?.project_id || null
    setProjectId(nextId)
    writeConsoleLocation(page, nextId)
    setProjectError('')
  }

  useEffect(() => {
    void refreshProjects().catch((cause: Error) => {
      setProjects([])
      setProjectError(cause.message)
    })
  }, [api])

  const navigate = (nextPage: Page) => {
    writeConsoleLocation(nextPage, projectId)
    setPage(nextPage)
  }
  const selectProject = (nextProjectId: string) => {
    setProjectId(nextProjectId)
    writeConsoleLocation(page, nextProjectId)
  }
  const projectCreated = (project: ValidationProject) => {
    setProjects((items) => [project, ...(items || []).filter((item) => item.project_id !== project.project_id)])
    selectProject(project.project_id)
  }
  const projectNameChanged = (changedProjectId: string, name: string, briefId: string, status: ValidationProject['latest_brief_status']) => {
    setProjects((items) => (items || []).map((item) => item.project_id === changedProjectId ? {
      ...item, name, latest_brief_id: briefId, latest_brief_status: status,
    } : item))
  }
  const renameProject = async (changedProjectId: string, name: string) => {
    const project = await api.post<ValidationProject>(`/api/v1/projects/${changedProjectId}/rename`, { name })
    setProjects((items) => (items || []).map((item) => item.project_id === project.project_id ? project : item))
  }
  const newProject = () => {
    navigate('briefs')
    window.setTimeout(() => document.getElementById('new-project-idea')?.focus(), 0)
  }
  const selectedProject = projects?.find((project) => project.project_id === projectId) || null
  return <Shell page={page} onPage={navigate} language={language} onLanguage={() => setLanguage(language === 'uk' ? 'en' : 'uk')}>
    <div className="top-owner"><span>{user.email}</span><button onClick={() => signOut(auth)} aria-label="Вийти"><LogOut /></button></div>
    {page !== 'admin' && <ProjectSwitcher projects={projects} projectId={projectId} onSelect={selectProject} onNew={newProject} onRename={renameProject} />}
    {projectError && <p className="landing-notice" role="alert">{projectError} <button className="text-action" onClick={() => void refreshProjects()}>Retry projects</button></p>}
    {page === 'briefs' && <ProductBriefView api={api} projectId={projectId} onProjectCreated={projectCreated} onProjectBriefChanged={projectNameChanged} onProjectsRefresh={refreshProjects} />}
    {page === 'studio' && <StudioView key={projectId || 'no-project'} api={api} projectId={projectId} />}
    {page === 'ads' && <AdsView key={projectId || 'no-project'} api={api} projectId={projectId} />}
    {page === 'landing' && <LandingPlaceholderView project={selectedProject} />}
    {page === 'admin' && <AdminView api={api} />}
  </Shell>
}

export function LiveApp() {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [startupError, setStartupError] = useState('')
  useEffect(() => {
    let active = true
    let settled = false

    const accept = async (candidate: User | null) => {
      if (!active) return
      if (!candidate) {
        settled = true
        setUser(null)
        return
      }
      try {
        await enforceOwner(candidate)
        if (active) {
          settled = true
          setStartupError('')
          setUser(candidate)
        }
      } catch (cause) {
        if (active) {
          settled = true
          setStartupError(errorMessage(cause, 'Не вдалося перевірити обліковий запис.'))
          setUser(null)
        }
      }
    }

    const fail = (cause: unknown) => {
      if (!active) return
      const candidate = auth.currentUser
      if (candidate) {
        void accept(candidate)
        return
      }
      settled = true
      setStartupError(errorMessage(cause, 'Не вдалося відновити вхід. Увійдіть ще раз.'))
      setUser(null)
    }

    const unsubscribe = onAuthStateChanged(auth, (candidate) => void accept(candidate), fail)

    // Resolve the redirect while the boot screen is mounted. Previously this
    // ran only after Auth reported a signed-out user and rendered <Login>, so a
    // stalled Safari observer could prevent its own redirect result from ever
    // being consumed.
    void getRedirectResult(auth)
      .then((result) => void accept(result?.user ?? auth.currentUser))
      .catch(fail)

    const timeout = window.setTimeout(() => {
      if (!active || settled) return
      const candidate = auth.currentUser
      if (candidate) void accept(candidate)
      else {
        settled = true
        setStartupError('Safari не завершив відновлення входу. Оновіть сторінку або увійдіть ще раз.')
        setUser(null)
      }
    }, AUTH_BOOT_TIMEOUT_MS)

    return () => {
      active = false
      window.clearTimeout(timeout)
      unsubscribe()
    }
  }, [])
  if (user === undefined) return <main className="boot" role="status" data-auth-persistence={AUTH_PERSISTENCE_MARKER}>PTW</main>
  return user ? <Console user={user} /> : <Login startupError={startupError} />
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
