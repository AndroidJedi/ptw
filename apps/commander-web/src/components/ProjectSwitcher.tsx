import { FolderKanban, Pencil, Plus, Save, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { translate, type Language } from '../i18n'
import type { ValidationProject } from '../types'

export function ProjectSwitcher({ projects, projectId, onSelect, onNew, onRename, language }: {
  projects: ValidationProject[] | null
  projectId: string | null
  onSelect: (projectId: string) => void
  onNew: () => void
  onRename: (projectId: string, name: string) => Promise<void>
  language: Language
}) {
  const selected = projects?.find((item) => item.project_id === projectId) || null
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const tr = (en: string, uk: string) => translate(language, en, uk)

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

  return <section className="project-switcher" aria-label={tr('Project workspace', 'Робочий простір проєкту')}>
    <div className="project-switcher-heading"><FolderKanban aria-hidden="true" /><div><small>{tr('PROJECT WORKSPACE', 'РОБОЧИЙ ПРОСТІР ПРОЄКТУ')}</small><strong>{selected?.name || (projects === null ? tr('Loading projects…', 'Завантаження проєктів…') : projects.length ? tr('New Project', 'Новий проєкт') : tr('No project yet', 'Проєкту ще немає'))}</strong></div></div>
    {!!projects?.length && <label>{tr('Existing Project', 'Існуючий проєкт')}<select aria-label={tr('Existing Project', 'Існуючий проєкт')} value={selected?.project_id || ''} onChange={(event) => onSelect(event.target.value)}><option value="" disabled>{tr('Choose an existing project', 'Виберіть існуючий проєкт')}</option>{projects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name} · {project.latest_brief_status || tr('new', 'новий')}</option>)}</select></label>}
    <div className="project-switcher-actions">
      {selected && !editing && <button className="secondary" onClick={() => setEditing(true)}><Pencil />{tr('Rename', 'Перейменувати')}</button>}
      <button className="secondary" onClick={onNew}><Plus />{tr('New Project', 'Новий проєкт')}</button>
    </div>
    {selected && editing && <div className="project-rename"><label>{tr('Project name', 'Назва проєкту')}<input maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label><button className="primary" disabled={busy || !name.trim()} onClick={() => void save()}><Save />{tr('Save name', 'Зберегти назву')}</button><button className="ghost" disabled={busy} onClick={() => setEditing(false)}><X />{tr('Cancel', 'Скасувати')}</button></div>}
    {selected && <p className="uuid-line">{language === 'uk' ? `${selected.brief_count} брифів · ${selected.result_run_count} соціальних артефактів` : `${selected.brief_count} Brief${selected.brief_count === 1 ? '' : 's'} · ${selected.result_run_count} social artifact${selected.result_run_count === 1 ? '' : 's'}`}</p>}
    {error && <p className="project-switcher-error" role="alert">{error}</p>}
  </section>
}
