import { BookOpen, BriefcaseBusiness } from 'lucide-react'
import { useState } from 'react'
import type { ApiClient } from '../api'
import { JobsView } from './JobsView'
import { MoreView } from './MoreView'

export function AdminView({ api }: { api: ApiClient }) {
  const [area, setArea] = useState<'jobs' | 'system'>('jobs')
  return <>
    <div className="admin-switch" role="tablist">
      <button className={area === 'jobs' ? 'selected' : ''} onClick={() => setArea('jobs')}><BriefcaseBusiness />Jobs</button>
      <button className={area === 'system' ? 'selected' : ''} onClick={() => setArea('system')}><BookOpen />Docs / System / Terminal</button>
    </div>
    {area === 'jobs' ? <JobsView api={api} /> : <MoreView api={api} />}
  </>
}
