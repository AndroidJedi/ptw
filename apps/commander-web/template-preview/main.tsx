import { createRoot } from 'react-dom/client'
import { LandingPage } from '../src/landing/LandingPage'
import type { LandingConfiguration, LandingContent } from '../src/types'

declare global { interface Window { templateFixture: { configuration: LandingConfiguration; content: LandingContent; imageUrls: Record<string, string> } } }
const fixture = window.templateFixture
createRoot(document.getElementById('root')!).render(<LandingPage {...fixture} />)
