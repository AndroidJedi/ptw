import { ArrowRight, Check, ExternalLink, LayoutTemplate, LoaderCircle, RotateCcw, Sparkles, TriangleAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import { local, type Language } from '../i18n'
import type { LandingBrief, LandingBuild, LandingCandidate, LandingFeature, LandingTemplate } from '../types'

const activeStatuses = new Set(['queued', 'building', 'publishing'])

function featureLines(items: LandingFeature[]) {
  return items.map((item) => `${item.title} — ${item.description}`).join('\n')
}

function parseFeatureLines(value: string): LandingFeature[] {
  return value.split('\n').map((line) => line.trim()).filter(Boolean).slice(0, 6).map((line, index) => {
    const pieces = line.split(/\s+[—–-]\s+/, 2)
    return pieces.length === 2
      ? { title: pieces[0], description: pieces[1] }
      : { title: `Перевага ${index + 1}`, description: line }
  })
}

function buildLabel(status: LandingBuild['status']) {
  return ({
    queued: 'Збірку поставлено в чергу',
    building: 'Natal збирає сторінку',
    publishing: 'Публікуємо у Firebase',
    published: 'Лендинг опубліковано',
    failed: 'Збірка не завершилась',
  } as Record<LandingBuild['status'], string>)[status]
}

function upsertBuild(items: LandingBuild[], incoming: LandingBuild) {
  return [incoming, ...items.filter((item) => item.id !== incoming.id)]
}

export function LandingView({ api, language }: {
  api: ApiClient
  language: Language
}) {
  const [templates, setTemplates] = useState<LandingTemplate[] | null>(null)
  const [candidates, setCandidates] = useState<LandingCandidate[] | null>(null)
  const [builds, setBuilds] = useState<LandingBuild[] | null>(null)
  const [selectedRun, setSelectedRun] = useState('')
  const [templateId, setTemplateId] = useState<LandingTemplate['id'] | ''>('')
  const [brief, setBrief] = useState<LandingBrief | null>(null)
  const [features, setFeatures] = useState('')
  const [visibleBuildId, setVisibleBuildId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    setError('')
    Promise.all([
      api.get<{ items: LandingTemplate[] }>('/api/v1/landings/templates'),
      api.get<{ items: LandingCandidate[] }>('/api/v1/landings/candidates?limit=30'),
      api.get<{ items: LandingBuild[] }>('/api/v1/landings/builds?limit=30'),
    ]).then(([templateData, candidateData, buildData]) => {
      setTemplates(templateData.items)
      setCandidates(candidateData.items)
      setBuilds(buildData.items)
      setSelectedRun((current) => current || candidateData.items[0]?.idea_run_id || '')
    }).catch((cause: Error) => setError(cause.message))
  }

  useEffect(() => { load() }, [api])
  const selected = useMemo(
    () => candidates?.find((item) => item.idea_run_id === selectedRun) || null,
    [candidates, selectedRun],
  )
  const visibleBuild = useMemo(
    () => builds?.find((item) => item.id === visibleBuildId)
      || builds?.find((item) => item.idea_run_id === selectedRun)
      || null,
    [builds, selectedRun, visibleBuildId],
  )
  const activeBuild = builds?.find((item) => activeStatuses.has(item.status)) || null

  useEffect(() => {
    if (!selected) return
    setBrief(structuredClone(selected.brief))
    setFeatures(featureLines(selected.brief.key_features))
    setTemplateId(selected.recommended_template_id)
    setVisibleBuildId('')
  }, [selected])

  useEffect(() => {
    if (!visibleBuild || !activeStatuses.has(visibleBuild.status)) return
    let active = true
    const refresh = async () => {
      try {
        const updated = await api.get<LandingBuild>(`/api/v1/landings/builds/${visibleBuild.id}`)
        if (active) setBuilds((current) => upsertBuild(current || [], updated))
      } catch (cause) {
        if (active) setError((cause as Error).message)
      }
    }
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [api, visibleBuild?.id, visibleBuild?.status])

  const update = (key: 'business_idea' | 'target_audience' | 'pain' | 'promise', value: string) => {
    setBrief((current) => current ? { ...current, [key]: value } : current)
  }
  const updateCta = (key: 'label' | 'url', value: string) => {
    setBrief((current) => current ? { ...current, cta: { ...current.cta, [key]: value } } : current)
  }
  const submit = async () => {
    if (!brief || !selected || !templateId) return
    const keyFeatures = parseFeatureLines(features)
    if (!keyFeatures.length) {
      setError('Додайте хоча б одну ключову перевагу.')
      return
    }
    setBusy(true); setError('')
    try {
      const created = await api.post<LandingBuild>('/api/v1/landings/builds', {
        request_id: window.crypto.randomUUID(),
        idea_run_id: selected.idea_run_id,
        template_id: templateId,
        brief: { ...brief, key_features: keyFeatures },
      })
      setBuilds((current) => upsertBuild(current || [], created))
      setVisibleBuildId(created.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const retry = async (build: LandingBuild) => {
    setBusy(true); setError('')
    try {
      const updated = await api.post<LandingBuild>(`/api/v1/landings/builds/${build.id}/retry`, {})
      setBuilds((current) => upsertBuild(current || [], updated))
      setVisibleBuildId(updated.id)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  if (!templates || !candidates || !builds) return error ? <ErrorState message={error} retry={load} /> : <Loading />
  return <>
    <PageHeader eyebrow="NATAL LANDING BUILDER" title="Лендинги" />
    {error && <ErrorState message={error} retry={load} />}
    {!candidates.length ? <Empty><LayoutTemplate className="empty-mark" /><h2>Немає завершених оцінок</h2><p>Завершіть Idea Laval evaluation, щоб зібрати з неї landing brief.</p></Empty> : <div className="landing-workbench">
      <section className="landing-source panel">
        <div className="landing-section-head"><div><small>01 · ДЖЕРЕЛО</small><h2>Завершена оцінка ідеї</h2></div><Check aria-hidden="true" /></div>
        <label htmlFor="landing-candidate">Ідея</label>
        <select id="landing-candidate" value={selectedRun} onChange={(event) => setSelectedRun(event.target.value)}>
          {candidates.map((item) => <option key={item.idea_run_id} value={item.idea_run_id}>{item.brief.business_idea}</option>)}
        </select>
        {selected && <details><summary>Джерело й якість</summary><p>RUN {selected.idea_run_id} · THESIS {selected.brief.source.thesis_id || 'немає'} · verdict {selected.verdict || 'not available'} · model {selected.quality.successful || 0}/{selected.quality.attempted || 0}</p></details>}
      </section>

      <section className="landing-templates panel">
        <div className="landing-section-head"><div><small>02 · СТРУКТУРА</small><h2>Шаблон</h2></div><Sparkles aria-hidden="true" /></div>
        <div className="landing-template-grid" role="radiogroup" aria-label="Шаблон лендингу">
          {templates.map((template) => <label key={template.id} className={templateId === template.id ? 'selected' : ''}>
            <input type="radio" name="landing-template" value={template.id} checked={templateId === template.id} onChange={() => setTemplateId(template.id)} />
            <span>{selected?.recommended_template_id === template.id ? 'РЕКОМЕНДОВАНО' : template.id.toUpperCase()}</span>
            <strong>{String(local(template.name, language))}</strong>
            <p>{String(local(template.description, language))}</p>
          </label>)}
        </div>
      </section>

      {brief && <section className="landing-brief panel">
        <div className="landing-section-head"><div><small>03 · ЗМІСТ ЛЕНДИНГУ</small><h2>Перевірте зміст</h2></div><LayoutTemplate aria-hidden="true" /></div>
        <p className="landing-brand-lock"><img src="/natal-logo-icon.svg" alt="" onError={(event) => { event.currentTarget.hidden = true }} />Назва й логотип зафіксовані: <strong>Natal</strong></p>
        <div className="landing-form-grid">
          <label>Бізнес-ідея<textarea rows={3} value={brief.business_idea} onChange={(event) => update('business_idea', event.target.value)} /></label>
          <label>Цільова аудиторія<textarea rows={3} value={brief.target_audience} onChange={(event) => update('target_audience', event.target.value)} /></label>
          <label>Біль<textarea rows={4} value={brief.pain} onChange={(event) => update('pain', event.target.value)} /></label>
          <label>Обіцянка цінності<textarea rows={4} value={brief.promise} onChange={(event) => update('promise', event.target.value)} /></label>
        </div>
        <label>Ключові переваги <small>Одна на рядок: назва — опис</small><textarea rows={7} value={features} onChange={(event) => setFeatures(event.target.value)} /></label>
        <div className="landing-form-grid">
          <label>Текст CTA<input value={brief.cta.label} onChange={(event) => updateCta('label', event.target.value)} /></label>
          <label>Посилання CTA<input value={brief.cta.url} onChange={(event) => updateCta('url', event.target.value)} /></label>
        </div>
        <button className="primary large" disabled={busy || !templateId || Boolean(activeBuild)} onClick={submit}>{busy ? 'Запускаємо…' : activeBuild ? 'Інша збірка вже виконується' : 'Зібрати й опублікувати у Firebase'}<ArrowRight aria-hidden="true" /></button>
        <p className="landing-publish-note">Збірка стартує одразу. Після перевірки сторінка автоматично публікується на окремому Firebase Hosting site.</p>
      </section>}

      {visibleBuild && <section className={`landing-build-state ${visibleBuild.status}`} role="status">
        {activeStatuses.has(visibleBuild.status) ? <LoaderCircle className="spin" aria-hidden="true" /> : visibleBuild.status === 'failed' ? <TriangleAlert aria-hidden="true" /> : <Check aria-hidden="true" />}
        <div><small>BUILD {visibleBuild.id}</small><h2>{buildLabel(visibleBuild.status)}</h2><p>{visibleBuild.template_id} · Firebase {visibleBuild.firebase_site_id}{visibleBuild.firebase_version ? ` · ${visibleBuild.firebase_version}` : ''}</p>{visibleBuild.error_message && <p className="landing-build-error">{visibleBuild.error_message}</p>}</div>
        {visibleBuild.status === 'published' && visibleBuild.public_url && <a className="secondary" href={visibleBuild.public_url} target="_blank" rel="noreferrer">Відкрити лендинг <ExternalLink aria-hidden="true" /></a>}
        {visibleBuild.status === 'failed' && <button className="secondary" disabled={busy || Boolean(activeBuild)} onClick={() => retry(visibleBuild)}>Повторити <RotateCcw aria-hidden="true" /></button>}
      </section>}

      {builds.length > 0 && <section className="landing-history panel"><div className="landing-section-head"><div><small>ІСТОРІЯ</small><h2>Лише Natal лендинги</h2></div></div>{builds.slice(0, 10).map((build) => <button key={build.id} className={visibleBuild?.id === build.id ? 'selected' : ''} onClick={() => setVisibleBuildId(build.id)}><span>{buildLabel(build.status)}</span><strong>{build.brief.business_idea}</strong><small>{build.template_id} · {build.id.slice(0, 8)}</small></button>)}</section>}
    </div>}
  </>
}
