import { FolderKanban, Pencil, Plus, Save, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ValidationProject } from '../types'

export function ProjectSwitcher({ projects, projectId, onSelect, onNew, onRename }: {
  projects: ValidationProject[] | null
  projectId: string | null
  onSelect: (projectId: string) => void
  onNew: () => void
  onRename: (projectId: string, name: string) => Promise<void>
}) {
  const selected = projects?.find((item) => item.project_id === projectId) || null
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setEditing(false)
    setName(selected?.name || '')
    setError('')
  }, [selected?.project_id, selected?.name])

  const save = async () => {
    if (!selected || !name.trim()) return
    setBusy(true); setError('')
    try {
      await onRename(selected.project_id, name.trim())
      setEditing(false)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="project-switcher" aria-label="Project workspace">
    <div className="project-switcher-heading"><FolderKanban aria-hidden="true" /><div><small>PROJECT WORKSPACE</small><strong>{selected?.name || (projects === null ? 'Loading projects…' : 'No project yet')}</strong></div></div>
    {!!projects?.length && <label>Project<select aria-label="Project" value={selected?.project_id || ''} onChange={(event) => onSelect(event.target.value)}>{projects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name} · {project.latest_brief_status || 'new'}</option>)}</select></label>}
    <div className="project-switcher-actions">
      {selected && !editing && <button className="secondary" onClick={() => setEditing(true)}><Pencil />Rename</button>}
      <button className="secondary" onClick={onNew}><Plus />New Project</button>
    </div>
    {selected && editing && <div className="project-rename"><label>Project name<input maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label><button className="primary" disabled={busy || !name.trim()} onClick={() => void save()}><Save />Save name</button><button className="ghost" disabled={busy} onClick={() => setEditing(false)}><X />Cancel</button></div>}
    {selected && <p className="uuid-line">Project {selected.project_id} · {selected.brief_count} Brief{selected.brief_count === 1 ? '' : 's'} · {selected.ad_batch_count} Ad batch{selected.ad_batch_count === 1 ? '' : 'es'}</p>}
    {error && <p className="project-switcher-error" role="alert">{error}</p>}
  </section>
}
