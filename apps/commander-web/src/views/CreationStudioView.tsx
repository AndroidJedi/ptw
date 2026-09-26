import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Download, Plus, Sparkles } from 'lucide-react'
import type { ApiClient } from '../api'
import type { Language } from '../i18n'
import { ImageReferenceInput, imageReferencePayload } from '../components/ImageReferenceInput'
import natalLogo from '../../../../natal/assets/logo-natal.png'
import './CreationStudioView.css'

type Mode = 'pack' | 'brief' | 'post' | 'landing' | 'templates'
type Preview = { sha256: string; failures: unknown[] }
type Creation = {
  run_id: string; operation_id: string; state_sha256: string; mode: Mode; scope: string; status: string; instruction: string; language: Language
  error: string | null; failed_stage: string | null; template_run_id: string | null; template_versions: unknown[]
  recovery?: { code: string; stage: string; can_retry: boolean; can_edit: boolean; has_brief: boolean; issues: string[] } | null
  design_retries?: number
  brief: { brief_id: string; project_id: string; document: Record<string, string | string[] | number>; document_sha256: string } | null
  documents: Record<string, unknown>; previews: Record<string, Preview>
  messages: { role: string; text: string; target: string }[]
}
const activeStates = new Set(['queued', 'reference', 'brief', 'design', 'content', 'image', 'render', 'review'])
const root = '/api/v1/create'

function PreviewImage({ api, preview, label }: { api: ApiClient; preview: Preview; label: string }) {
  const [url, setUrl] = useState(''), [error, setError] = useState('')
  useEffect(() => {
    let alive = true, next = ''
    setUrl(''); setError('')
    void api.image(`${root}/media/${preview.sha256}`, 'image/png', preview.sha256).then(blob => {
      if (alive) { next = URL.createObjectURL(blob); setUrl(next) }
    }).catch(cause => { if (alive) setError((cause as Error).message) })
    return () => { alive = false; if (next) URL.revokeObjectURL(next) }
  }, [api, preview.sha256])
  return error ? <p role="alert">{error}</p> : url ? <img src={url} alt={label} /> : <p role="status">…</p>
}

export function CreationStudioView({ api, language }: { api: ApiClient; language: Language }) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const [mode, setMode] = useState<Mode>('pack'), [scope, setScope] = useState('combined')
  const [instruction, setInstruction] = useState(''), [website, setWebsite] = useState(''), [reuse, setReuse] = useState(false)
  const [file, setFile] = useState<File | null>(null), [outputLanguage, setOutputLanguage] = useState(language)
  const [designs, setDesigns] = useState<{ run_id: string; name: string; surfaces: string[] }[]>([]), [design, setDesign] = useState('')
  const [run, setRun] = useState<Creation | null>(null), [history, setHistory] = useState<Creation[]>([])
  const [selected, setSelected] = useState(() => new URLSearchParams(location.search).get('creation'))
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [inputOpen, setInputOpen] = useState(!selected)
  const [message, setMessage] = useState(''), [target, setTarget] = useState('all'), [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 600px)').matches)
  const inFlight = useRef(false), selectedRef = useRef(selected), agentInput = useRef<HTMLTextAreaElement>(null), agentSection = useRef<HTMLDetailsElement>(null)
  const pendingRequest = useRef<{ fingerprint: string; value: Record<string, unknown> } | null>(null)
  selectedRef.current = selected
  const active = busy || Boolean(run && activeStates.has(run.status))
  const choices: [Mode, string, string][] = [
    ['pack', 'Brief + Post + Landing', 'Бриф + Допис + Лендінг'], ['brief', 'Brief', 'Бриф'], ['post', 'Post', 'Допис'], ['landing', 'Landing', 'Лендінг'], ['templates', 'Reusable templates', 'Шаблони'],
  ]
  const label = (value: string) => ({ queued: tr('Starting', 'Починаємо'), reference: tr('Reading your reference', 'Вивчаємо референс'), brief: tr('Writing the Brief', 'Створюємо бриф'), design: tr('Composing the design', 'Створюємо дизайн'), content: tr('Writing your copy', 'Готуємо текст'), image: tr('Creating artwork', 'Створюємо зображення'), render: tr('Rendering your drafts', 'Рендеримо чернетки'), review: tr('Checking the result', 'Перевіряємо результат'), ready: tr('Draft ready', 'Чернетка готова'), needs_review: tr('Needs another pass', 'Потрібне доопрацювання'), failed: tr('Creation paused', 'Створення призупинено'), interrupted: tr('Creation interrupted', 'Створення перервано') }[value] || value)
  const select = (id: string | null) => {
    setSelected(id); setRun(null); setError(''); setInputOpen(!id); setTarget('all')
    const params = new URLSearchParams(location.search)
    if (id) params.set('creation', id); else params.delete('creation')
    window.history.replaceState({}, '', `${location.pathname}?${params}`)
  }
  const refreshHistory = () => api.get<{ items: Creation[] }>(`${root}/runs`).then(value => setHistory(value.items))
  useEffect(() => { void refreshHistory().catch(cause => setError((cause as Error).message)) }, [api])
  useEffect(() => { void api.get<{ items: typeof designs }>(`${root}/designs`).then(value => setDesigns(value.items)).catch(cause => setError((cause as Error).message)) }, [api, run?.template_versions.length])
  useEffect(() => {
    if (!selected) return
    let alive = true, timer: ReturnType<typeof setTimeout>
    const refresh = async () => {
      try {
        const value = await api.get<Creation>(`${root}/runs/${selected}`)
        if (alive) { setRun(value); setError(''); if (activeStates.has(value.status)) timer = setTimeout(refresh, 2000); else void refreshHistory().catch(() => undefined) }
      } catch (cause) { if (alive) { setError((cause as Error).message); timer = setTimeout(refresh, 5000) } }
    }
    void refresh()
    return () => { alive = false; clearTimeout(timer) }
  }, [api, selected, run?.operation_id, busy])

  const create = async () => {
    if (inFlight.current) return
    inFlight.current = true; setBusy(true); setError('')
    try {
      const sourceDesign = ['brief', 'templates'].includes(mode) ? '' : design
      const fingerprint = JSON.stringify([mode, scope, instruction, website, reuse, outputLanguage, sourceDesign, file?.name, file?.lastModified, file?.size])
      let value = pendingRequest.current?.fingerprint === fingerprint ? pendingRequest.current.value : null
      if (!value) {
        const refs: string[] = []
        if (file) {
          const uploaded = await api.post<{ reference_id: string }>(`${root}/references`, { request_id: crypto.randomUUID(), image: await imageReferencePayload(file) })
          refs.push(uploaded.reference_id)
        }
        value = { request_id: crypto.randomUUID(), mode, scope, instruction, url: website.trim(), language: outputLanguage, reuse_images: reuse, reference_ids: refs, ...(sourceDesign ? { template_source_id: sourceDesign } : {}) }
        pendingRequest.current = { fingerprint, value }
      }
      const result = await api.post<Creation>(`${root}/runs`, value)
      select(result.run_id); setRun(result); setFile(null); pendingRequest.current = null
      void refreshHistory().catch(() => undefined)
    } catch (cause) { setError((cause as Error).message) }
    finally { inFlight.current = false; setBusy(false) }
  }
  const change = async (action: 'edit' | 'retry' | 'accept') => {
    if (!run || inFlight.current) return
    const id = run.run_id
    inFlight.current = true; setBusy(true); setError('')
    try {
      const result = await api.post<Creation>(`${root}/runs/${id}/${action}`, { request_id: crypto.randomUUID(), base_sha256: run.state_sha256, ...(action === 'edit' ? { target, instruction: message } : {}) })
      if (selectedRef.current === id) { setRun(result); if (action === 'edit') setMessage('') }
    } catch (cause) { setError((cause as Error).message) }
    finally { inFlight.current = false; setBusy(false) }
  }
  const download = async () => {
    if (!run) return
    setBusy(true); setError('')
    try {
      const blob = await api.download(`${root}/runs/${run.run_id}/export`, 'application/zip', { deadlineMs: 60000 })
      const url = URL.createObjectURL(blob), anchor = document.createElement('a')
      anchor.href = url; anchor.download = 'natal-studio.zip'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const ask = (next: string) => {
    setTarget(next)
    if (agentSection.current) agentSection.current.open = true
    requestAnimationFrame(() => { agentInput.current?.focus(); agentInput.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }) })
  }
  const recovery = run?.recovery
  const canEdit = run && recovery?.can_edit !== false && (['ready', 'needs_review'].includes(run.status) || (run.status === 'failed' && Boolean(run.brief || Object.keys(run.documents).length))) && !active
  const recoveryCopy: Record<string, [string, string]> = {
    design_timeout: [tr('Design generation timed out', 'Час очікування дизайну минув'), tr('The design service did not respond in time. Continue creating to resume the saved design. You do not need to rewrite your idea.', 'Сервіс дизайну не відповів вчасно. Натисніть «Продовжити створення», щоб відновити роботу. Переписувати ідею не потрібно.')],
    design_failed: [tr('Design generation stopped', 'Створення дизайну зупинилося'), tr('The design could not finish. Continue creating to try the unfinished step again.', 'Дизайн не вдалося завершити. Продовжіть створення, щоб повторити незавершений крок.')],
    design_invalid: [tr('The generated layout needs a fix', 'Створений макет потребує виправлення'), tr('The agent returned an invalid layout setting. Continue creating to let it correct the design. You do not need to rewrite your idea.', 'Агент повернув некоректне налаштування макета. Продовжіть створення, щоб він виправив дизайн. Переписувати ідею не потрібно.')],
    design_checkpoint: [tr('Your design is partly complete', 'Дизайн частково готовий'), tr('Continue creating to apply the remaining saved adjustments.', 'Продовжіть створення, щоб застосувати решту збережених правок.')],
    design_adjustment: [tr('The layout needs adjustment', 'Макет потребує правок'), tr('Let the agent fix the issues below. You can also describe a specific change.', 'Агент може виправити наведені нижче недоліки. Також можна описати конкретну правку.')],
    design_capability: [tr('This design needs a simpler approach', 'Цей дизайн потребує простішого рішення'), tr('Ask the agent to adapt the design using the available elements. Repeating the same step will not add the missing capability.', 'Попросіть агента адаптувати дизайн за допомогою доступних елементів. Повторення цього кроку не додасть відсутню можливість.')],
    design_limit: [tr('This design could not be completed', 'Цей дизайн не вдалося завершити'), tr('The design reached its adjustment limit. Your work is saved; start a new creation with a simpler design direction.', 'Дизайн досяг ліміту правок. Роботу збережено; почніть нове створення з простішим напрямом дизайну.')],
    service_error: [tr('The design service needs a fix', 'Сервіс дизайну потребує виправлення'), tr('An internal error prevented completion. Changing your idea or retrying the same step will not fix it. Your work is saved.', 'Внутрішня помилка завадила завершенню. Зміна ідеї чи повторення цього кроку не допоможуть. Вашу роботу збережено.')],
    visual_review: [tr('Your drafts need a change', 'Чернетки потребують правки'), tr('Review the issues below, then tell the agent what to change. Your current previews remain available.', 'Перегляньте недоліки нижче та опишіть агенту потрібну правку. Поточні прев’ю залишаються доступними.')],
    copy_fit: [tr('Some text does not fit yet', 'Деякі тексти ще не вміщуються'), tr('Let the agent shorten the text to fit, or ask for a layout change.', 'Агент може скоротити текст, щоб він умістився. Або попросіть змінити макет.')],
    interrupted: [tr('Creation was interrupted', 'Створення було перервано'), tr('Continue from the saved progress. You do not need to start over.', 'Продовжіть зі збереженого місця. Починати заново не потрібно.')],
    stage_failed: [tr('Creation could not finish', 'Створення не вдалося завершити'), tr('Continue creating to retry the unfinished step. Completed work is saved.', 'Продовжіть створення, щоб повторити незавершений крок. Готову роботу збережено.')],
  }
  const recoveryText = recoveryCopy[recovery?.code || 'stage_failed'] || recoveryCopy.stage_failed

  return <div className="creation-studio">
    <a className="creation-console-link" href="?page=briefs">← {tr('PTW console', 'Панель PTW')}</a>
    <header className="creation-heading"><div><img src={natalLogo} alt="Natal" /><span>STUDIO</span></div><button className="secondary" disabled={active} onClick={() => { select(null); setInstruction(''); setWebsite(''); setFile(null); setMessage(''); setDesign(''); setMode('pack') }}><Plus size={16} />{tr('New creation', 'Нове створення')}</button></header>
    <div className="creation-intro"><p>{tr('FROM A SPARK TO SOMETHING REAL', 'ВІД ІДЕЇ ДО ГОТОВОЇ КОНЦЕПЦІЇ')}</p><h1>{tr('Your next idea starts here.', 'Ваша наступна ідея починається тут.')}</h1><p>{tr('Describe it. Add a reference. Create your Brief, Post and Landing in one place.', 'Опишіть ідею. Додайте референс. Створіть бриф, допис і лендінг в одному місці.')}</p></div>
    {history.length > 0 && <label className="creation-history">{tr('Your creations', 'Ваші роботи')}<select aria-label={tr('Your creations', 'Ваші роботи')} value={selected || ''} disabled={busy} onChange={event => select(event.target.value || null)}><option value="">{tr('New creation', 'Нове створення')}</option>{history.map(item => <option key={item.run_id} value={item.run_id}>{item.instruction.slice(0, 65) || tr('From reference', 'За референсом')} · {label(item.status)}</option>)}</select></label>}
    {error && <p className="creation-error" role="alert">{error}</p>}
    <details className="creation-section creation-input" open={inputOpen} onToggle={event => setInputOpen(event.currentTarget.open)}>
      <summary><span className="creation-number">01</span><span>{tr('The starting point', 'Початкова ідея')}</span><small>{tr('Idea · Brief · Link · Image', 'Ідея · Бриф · Посилання · Зображення')}</small></summary>
      <div className="creation-section-body">
        <label>{tr('What would you like to create?', 'Що ви хочете створити?')}<textarea value={instruction} onChange={event => setInstruction(event.target.value)} maxLength={6000} rows={4} placeholder={tr('An idea, an existing brief, or a direction for your new template…', 'Ідея, готовий бриф або побажання до нового шаблону…')} disabled={active} /></label>
        <div className="creation-modes" role="group" aria-label={tr('Create', 'Створити')}>{choices.map(([value, en, uk]) => <button key={value} type="button" disabled={active} aria-pressed={mode === value} onClick={() => setMode(value)}>{tr(en, uk)}</button>)}</div>
        {mode === 'templates' && <label>{tr('Template surfaces', 'Формати шаблонів')}<select value={scope} onChange={event => setScope(event.target.value)} disabled={active}><option value="combined">Post + Landing</option><option value="post">Post</option><option value="landing">Landing</option></select></label>}
        {!['brief', 'templates'].includes(mode) && designs.length > 0 && <label>{tr('Design', 'Дизайн')}<select aria-label={tr('Design', 'Дизайн')} value={design} onChange={event => setDesign(event.target.value)} disabled={active}><option value="">{tr('Let the agent create a new design', 'Агент створить новий дизайн')}</option>{designs.filter(item => (mode === 'pack' ? ['post', 'landing'] : [mode]).every(surface => item.surfaces.includes(surface))).map(item => <option key={item.run_id} value={item.run_id}>{item.name}</option>)}</select></label>}
        <details className="creation-reference"><summary>{tr('Add a reference', 'Додати референс')} <small>{tr('optional', 'необов’язково')}</small></summary><div className="creation-reference-body">
          <label>{tr('Website link', 'Посилання на сайт')}<input type="url" value={website} placeholder="https://example.com" onChange={event => setWebsite(event.target.value)} disabled={active} maxLength={2048} /></label>
          <ImageReferenceInput value={file} onChange={setFile} disabled={active} language={language} />
          {website && <label className="creation-check"><input type="checkbox" checked={reuse} onChange={event => setReuse(event.target.checked)} disabled={active} />{tr('Reuse photos from this website', 'Використати фотографії з цього сайту')}</label>}
          <small>{tr('Layout and visual style inspire the result. Your templates use Natal branding.', 'Референс задає структуру та стиль. Ваші шаблони використовують бренд Natal.')}</small>
        </div></details>
        <div className="creation-submit"><label>{tr('Content language', 'Мова матеріалів')}<select value={outputLanguage} onChange={event => setOutputLanguage(event.target.value as Language)} disabled={active}><option value="uk">Українська</option><option value="en">English</option></select></label><button className="primary" disabled={active || !(instruction.trim() || website || file)} onClick={() => void create()}><Sparkles size={17} />{tr('Create with agent', 'Створити з агентом')}</button></div>
      </div>
    </details>
    {run && <>
      <div className="creation-status" role="status"><span className={active ? 'creation-pulse' : ''} /><strong>{label(run.status)}</strong>{active && <span>{tr('You can leave this page; your progress is saved.', 'Можна закрити сторінку — прогрес зберігається.')}</span>}</div>
      {active && run.status === 'design' && Boolean(run.design_retries) && <p className="creation-retry-status" role="status">{tr('The design service timed out. Retrying automatically; your saved work is safe.', 'Сервіс дизайну не відповів вчасно. Повторюємо автоматично; збережена робота не втрачена.')}</p>}
      {recovery && <div className="creation-recovery" role="alert">
        <h2>{recoveryText[0]}</h2><p>{recoveryText[1]}</p>
        {recovery.has_brief && <p className="creation-preserved">{tr('Your Brief is saved. Continuing will keep it.', 'Ваш бриф збережено. Продовження не змінить його.')}</p>}
        {recovery.issues.length > 0 && <details><summary>{tr('What needs adjustment', 'Що потребує правок')}</summary><ul>{recovery.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul></details>}
        <div className="creation-recovery-actions">
          {recovery.can_retry && <button className="primary" disabled={active} onClick={() => void change('retry')}>{['design_adjustment', 'copy_fit'].includes(recovery.code) ? tr('Fix automatically', 'Виправити автоматично') : tr('Continue creating', 'Продовжити створення')}</button>}
          {canEdit && <button className="secondary" onClick={() => ask('all')}>{tr('Describe a change', 'Описати правку')}</button>}
        </div>
      </div>}
      {!recovery && run.error && <p className="creation-error" role="alert">{run.error}</p>}
      {run.brief && <details className="creation-section" open><summary><span className="creation-number">02</span><span>{tr('Brief', 'Бриф')}</span><small>{tr('The idea, clarified', 'Чітко сформульована ідея')}</small></summary><div className="creation-section-body"><dl className="creation-brief">{Object.entries(run.brief.document).filter(([key]) => !['schema_version', 'language'].includes(key)).map(([key, value]) => <div key={key}><dt>{({ product: tr('Product', 'Продукт'), target_audience: tr('Audience', 'Аудиторія'), main_pain: tr('Problem', 'Проблема'), promise: tr('Promise', 'Обіцянка'), key_benefits: tr('Benefits', 'Переваги'), cta: tr('Action', 'Дія'), trust_strategy: tr('Trust', 'Довіра'), offer: tr('Offer', 'Пропозиція') }[key] || key)}</dt><dd>{Array.isArray(value) ? value.map(item => <p key={item}>{item}</p>) : value}</dd></div>)}</dl><button className="secondary" disabled={!canEdit} onClick={() => ask('brief')}>{tr('Ask agent to edit Brief', 'Редагувати бриф через агента')}</button></div></details>}
      {(['post', 'landing'] as const).filter(surface => run.previews[`${surface}:desktop`]).map(surface => <details key={`${run.run_id}:${surface}`} className="creation-section" open><summary><span className="creation-number">{surface === 'post' ? '03' : '04'}</span><span>{surface === 'post' ? tr('Post', 'Допис') : tr('Landing', 'Лендінг')}</span><small>{tr('Draft', 'Чернетка')}</small></summary><div className="creation-section-body"><div className="creation-preview-tools"><button className="secondary" disabled={!canEdit} onClick={() => ask(surface)}>{tr('Edit with agent', 'Редагувати через агента')}</button>{surface === 'landing' && <div role="group" aria-label={tr('Landing viewport', 'Розмір лендінгу')}><button aria-pressed={!mobile} onClick={() => setMobile(false)}>Desktop</button><button aria-pressed={mobile} onClick={() => setMobile(true)}>Mobile</button></div>}</div><div className={`creation-preview ${surface} ${surface === 'landing' && mobile ? 'mobile' : ''}`}><PreviewImage api={api} preview={run.previews[`${surface}:${surface === 'landing' && mobile ? 'mobile' : 'desktop'}`] || run.previews[`${surface}:desktop`]} label={`${surface} ${tr('draft', 'чернетка')}`} /></div></div></details>)}
      <details ref={agentSection} className="creation-section creation-agent" open><summary><span className="creation-number">↗</span><span>{tr('Make it yours', 'Доведіть до свого бачення')}</span><small>Astra · xhigh</small></summary><div className="creation-section-body">
        {run.messages.length > 0 && <div className="creation-messages">{run.messages.map((item, index) => <p key={index}>{item.text}</p>)}</div>}
        <label>{tr('Edit', 'Редагувати')}<select value={target} onChange={event => setTarget(event.target.value)} disabled={!canEdit}><option value="all">{tr('Whole package / idea', 'Увесь набір / ідею')}</option>{run.brief && <option value="brief">{tr('Brief', 'Бриф')}</option>}{Object.keys(run.documents).map(surface => <option value={surface} key={surface}>{surface === 'post' ? 'Post' : 'Landing'}</option>)}</select></label>
        <div className="creation-composer"><textarea ref={agentInput} aria-label={tr('Message to agent', 'Повідомлення агенту')} rows={3} value={message} maxLength={2000} onChange={event => setMessage(event.target.value)} disabled={!canEdit} placeholder={tr('“Make the headline shorter and the background warmer…”', '«Скороти заголовок і зроби фон теплішим…»')} /><button className="primary" aria-label={tr('Send edit', 'Надіслати правку')} disabled={!canEdit || !message.trim()} onClick={() => void change('edit')}><ArrowUp /></button></div>
      </div></details>
      <details className="creation-section" open={run.status === 'ready'}><summary><span className="creation-number">✓</span><span>{tr('Take it with you', 'Збережіть результат')}</span><small>PNG · HTML · JSON</small></summary><div className="creation-section-body creation-export"><p>{tr('Download your draft package to share or continue working on it. Landing exports include a responsive HTML preview.', 'Завантажте чернетки, щоб поділитися ними або продовжити роботу. Експорт лендінгу містить адаптивне HTML-прев’ю.')}</p><button className="primary" disabled={active || run.status !== 'ready'} onClick={() => void download()}><Download size={17} />{tr('Download package', 'Завантажити набір')}</button>{run.mode === 'templates' && <button className="secondary" disabled={active || run.status !== 'ready' || Boolean(run.template_versions.length)} onClick={() => void change('accept')}>{run.template_versions.length ? tr('Saved in Templates', 'Збережено у шаблонах') : tr('Save to Templates', 'Зберегти у шаблони')}</button>}<small>{tr('These are private drafts. Public links and campaign publishing are separate steps.', 'Це приватні чернетки. Публічні посилання та запуск реклами — окремі кроки.')}</small></div></details>
    </>}
  </div>
}
