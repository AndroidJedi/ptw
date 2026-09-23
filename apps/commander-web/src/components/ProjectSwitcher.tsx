import { AlertTriangle, FolderKanban, Pencil, Plus, Save, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { translate, type Language } from '../i18n'
import type { ValidationProject } from '../types'

export function ProjectSwitcher({ projects, projectId, onSelect, onNew, onRename, onDelete, language }: {
  projects: ValidationProject[] | null
  projectId: string | null
  onSelect: (projectId: string) => void
  onNew: () => void
  onRename: (projectId: string, name: string) => Promise<void>
  onDelete: (projectId: string, requestId: string, confirmationName: string) => Promise<void>
  language: Language
}) {
  const selected = projects?.find((item) => item.project_id === projectId) || null
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deleteRequestId, setDeleteRequestId] = useState('')
  const tr = (en: string, uk: string) => translate(language, en, uk)

  useEffect(() => {
    setEditing(false)
    setName(selected?.name || '')
    setDeleteOpen(false)
    setDeleteConfirmation('')
    setDeleteRequestId('')
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

  const openDelete = () => {
    if (!selected) return
    setEditing(false)
    setDeleteConfirmation('')
    setDeleteRequestId(crypto.randomUUID())
    setError('')
    setDeleteOpen(true)
  }

  const remove = async () => {
    if (!selected || deleteConfirmation !== selected.name || !deleteRequestId) return
    setBusy(true); setError('')
    try {
      await onDelete(selected.project_id, deleteRequestId, deleteConfirmation)
      setDeleteOpen(false)
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
      {selected && !editing && <button className="ghost danger" onClick={openDelete}><Trash2 />{tr('Delete', 'Видалити')}</button>}
    </div>
    {selected && editing && <div className="project-rename"><label>{tr('Project name', 'Назва проєкту')}<input maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label><button className="primary" disabled={busy || !name.trim()} onClick={() => void save()}><Save />{tr('Save name', 'Зберегти назву')}</button><button className="ghost" disabled={busy} onClick={() => setEditing(false)}><X />{tr('Cancel', 'Скасувати')}</button></div>}
    {selected && <p className="uuid-line">{language === 'uk' ? `${selected.brief_count} брифів` : `${selected.brief_count} Brief${selected.brief_count === 1 ? '' : 's'}`}</p>}
    {error && !deleteOpen && <p className="project-switcher-error" role="alert">{error}</p>}
    {selected && deleteOpen && <div className="modal-backdrop" role="presentation"><section className="panel project-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="project-delete-title">
      <header><div><small>{tr('DESTRUCTIVE PROJECT ACTION', 'НЕБЕЗПЕЧНА ДІЯ З ПРОЄКТОМ')}</small><h2 id="project-delete-title">{tr(`Delete “${selected.name}”?`, `Видалити «${selected.name}»?`)}</h2></div><button className="icon-button" disabled={busy} aria-label={tr('Close delete confirmation', 'Закрити підтвердження видалення')} onClick={() => setDeleteOpen(false)}><X /></button></header>
      <div className="project-delete-warning"><AlertTriangle aria-hidden="true" /><p>{tr('The Project will disappear from every PTW workspace and its published Landing will stop opening. PTW retains its internal audit lineage. Posts already published on external services are not removed there.', 'Проєкт зникне з усіх робочих просторів PTW, а його опублікований лендінг перестане відкриватися. PTW збереже внутрішню історію аудиту. Дописи, уже опубліковані у зовнішніх сервісах, там не видаляються.')}</p></div>
      <label>{tr(`Type ${selected.name} to confirm`, `Введіть ${selected.name} для підтвердження`)}<input autoFocus value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} autoComplete="off" /></label>
      {error && <p className="project-switcher-error" role="alert">{error}</p>}
      <footer><button className="ghost" disabled={busy} onClick={() => setDeleteOpen(false)}>{tr('Cancel', 'Скасувати')}</button><button className="primary danger" disabled={busy || deleteConfirmation !== selected.name} onClick={() => void remove()}><Trash2 />{busy ? tr('Deleting…', 'Видалення…') : tr('Delete Project', 'Видалити проєкт')}</button></footer>
    </section></div>}
  </section>
}
