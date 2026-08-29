import { ArrowLeft, Check, RefreshCcw, Save, WandSparkles, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ApiClient } from '../../api'
import { translate, type Language } from '../../i18n'
import type { StudioTuneDetail, StudioTuneRuleApproval, StudioTuneRun } from '../../types'

const DRAFT_KEY = 'ptw-studio-tune-draft-v1'
const ACTIVE_STATUSES = new Set<StudioTuneRun['status']>(['queued', 'running'])

interface TuneDraft {
  projectIdea: string
  implementation: string
  feedback: string
}

function loadDraft(): TuneDraft {
  try {
    const value = JSON.parse(window.localStorage.getItem(DRAFT_KEY) || '{}') as Partial<TuneDraft>
    return {
      projectIdea: typeof value.projectIdea === 'string' ? value.projectIdea : '',
      implementation: typeof value.implementation === 'string' ? value.implementation : '',
      feedback: typeof value.feedback === 'string' ? value.feedback : '',
    }
  } catch {
    return { projectIdea: '', implementation: '', feedback: '' }
  }
}

function saveDraft(value: TuneDraft) {
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(value))
  } catch {
    // A blocked storage policy must not block Tune mode.
  }
}

export function StudioTuneWizard({ api, language, open, studioPreviewUrl, onClose }: {
  api: ApiClient
  language: Language
  open: boolean
  studioPreviewUrl: string
  onClose: () => void
}) {
  const initial = useRef(loadDraft())
  const [projectIdea, setProjectIdea] = useState(initial.current.projectIdea)
  const [implementation, setImplementation] = useState(initial.current.implementation)
  const [feedback, setFeedback] = useState(initial.current.feedback)
  const [detail, setDetail] = useState<StudioTuneDetail | null>(null)
  const [run, setRun] = useState<StudioTuneRun | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ruleSaving, setRuleSaving] = useState(false)
  const [ruleNotice, setRuleNotice] = useState('')
  const [ruleError, setRuleError] = useState('')
  const titleId = useId()
  const ideaRef = useRef<HTMLTextAreaElement>(null)
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const active = Boolean(run && ACTIVE_STATUSES.has(run.status))

  useEffect(() => {
    saveDraft({ projectIdea, implementation, feedback })
  }, [projectIdea, implementation, feedback])

  useEffect(() => {
    if (!open) return
    let current = true
    setLoading(true)
    setError('')
    void api.get<StudioTuneDetail>('/api/v1/studio/tune', { deadlineMs: 30_000 })
      .then((value) => {
        if (!current) return
        setDetail(value)
        const latest = value.runs.find((item) => item.run_id === value.active_run_id)
          || value.runs[0]
          || null
        setRun(latest)
        if (latest) {
          setProjectIdea((current) => current.trim() ? current : latest.project_idea)
          setImplementation((current) => current.trim() ? current : latest.implementation)
          if (latest.status === 'completed') {
            setFeedback((current) => current.trim() === latest.feedback.trim() ? '' : current)
          } else if (latest.status === 'failed') {
            setFeedback((current) => current.trim() ? current : latest.feedback)
          }
        }
        if (!latest) window.setTimeout(() => ideaRef.current?.focus(), 0)
      })
      .catch((cause: Error) => { if (current) setError(cause.message) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [api, open])

  useEffect(() => {
    if (!open || !run || !ACTIVE_STATUSES.has(run.status)) return
    let current = true
    const poll = async () => {
      try {
        const value = await api.get<StudioTuneRun>(
          `/api/v1/studio/tune-runs/${run.run_id}`, { deadlineMs: 30_000 },
        )
        if (current) {
          setRun(value)
          if (value.status === 'completed') {
            setFeedback((feedbackValue) => feedbackValue.trim() === value.feedback.trim() ? '' : feedbackValue)
          }
          setError('')
        }
      } catch (cause) {
        if (current) setError((cause as Error).message)
      }
    }
    const timer = window.setInterval(() => void poll(), 1_500)
    return () => {
      current = false
      window.clearInterval(timer)
    }
  }, [api, open, run?.run_id, run?.status])

  useEffect(() => {
    if (!open || run?.status !== 'completed' || !run.preview) {
      setPreviewUrl('')
      setPreviewError('')
      return
    }
    let current = true
    let objectUrl = ''
    setPreviewUrl('')
    setPreviewError('')
    void api.media(
      `/api/v1/studio/tune-runs/${run.run_id}/preview`,
      run.preview.mime_type,
      run.preview.sha256,
    ).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (current) setPreviewUrl(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    }).catch((cause: Error) => {
      if (current) setPreviewError(cause.message)
    })
    return () => {
      current = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [api, open, run?.preview?.mime_type, run?.preview?.sha256, run?.run_id, run?.status])

  useEffect(() => {
    if (!open) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose, open])

  const start = async () => {
    if (active) return
    setLoading(true)
    setError('')
    setRuleNotice('')
    setRuleError('')
    try {
      const value = await api.post<StudioTuneRun>('/api/v1/studio/tune-runs', {
        project_idea: projectIdea.trim(),
        implementation: implementation.trim(),
        feedback: feedback.trim(),
      }, { deadlineMs: 30_000 })
      setRun(value)
      if (value.status === 'completed') setFeedback('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const saveRule = async () => {
    if (!run || !reviewable || !ruleCandidateReady) return
    setRuleSaving(true)
    setRuleNotice('')
    setRuleError('')
    try {
      const value = await api.post<StudioTuneRuleApproval>(
        `/api/v1/studio/tune-runs/${run.run_id}/rules`,
        { rule: ruleCandidate },
        { deadlineMs: 30_000 },
      )
      setRun((current) => {
        if (!current || current.run_id !== value.run_id) return current
        const approved = current.approved_rules || []
        return approved.some((item) => item.rule_sha256 === value.rule_sha256)
          ? current
          : { ...current, approved_rules: [...approved, value] }
      })
      setRuleNotice(value.created
        ? tr('Saved as a reusable rule for future Tune runs.', 'Збережено як повторно використовуване правило для майбутніх запусків Tune.')
        : tr('This reusable rule was already saved.', 'Це повторно використовуване правило вже збережено.'))
    } catch {
      setRuleError(tr(
        'The reusable rule could not be saved. Your feedback is still retained.',
        'Не вдалося зберегти повторно використовуване правило. Ваш відгук усе одно збережено.',
      ))
    } finally {
      setRuleSaving(false)
    }
  }

  const updateFeedback = (value: string) => {
    setFeedback(value)
    setRuleNotice('')
    setRuleError('')
  }

  const anotherIteration = () => {
    setRun(null)
    setFeedback('')
    setError('')
    setRuleNotice('')
    setRuleError('')
    window.setTimeout(() => ideaRef.current?.focus(), 0)
  }

  if (!open) return null

  const stageLabels: Record<StudioTuneRun['stage'], string> = {
    queued: tr('Queued', 'У черзі'),
    preparing: tr('Preparing isolated snapshot', 'Готується ізольована копія'),
    generating: tr('Implementing your direction', 'Реалізується ваш напрям'),
    verifying: tr('Running focused checks', 'Виконуються цільові перевірки'),
    applying: tr('Applying verified Studio changes', 'Застосовуються перевірені зміни Студії'),
    completed: tr('Verified changes applied', 'Перевірені зміни застосовано'),
    failed: tr('Iteration stopped safely', 'Ітерацію безпечно зупинено'),
  }
  const ready = projectIdea.trim().length >= 10 && implementation.trim().length >= 10
  const feedbackReady = ready && feedback.trim().length >= 3
  const reviewable = run?.status === 'completed' || run?.status === 'failed'
  const ruleCandidate = feedback.trim() || run?.feedback.trim() || ''
  const ruleCandidateReady = ruleCandidate.length >= 10
  const currentRuleSaved = Boolean(run?.approved_rules?.some(
    (item) => item.rule.trim().toLocaleLowerCase() === ruleCandidate.toLocaleLowerCase(),
  ))
  const reviewPreviewUrl = run?.status === 'failed' ? studioPreviewUrl : previewUrl
  const runReport = run ? <>
    {run.summary && <div className="studio-tune-summary"><small>{tr('AGENT SUMMARY', 'ПІДСУМОК АГЕНТА')}</small><p>{run.summary}</p></div>}
    {run.changed_files.length > 0 && <details><summary>{tr(`${run.changed_files.length} changed files`, `${run.changed_files.length} змінених файлів`)}</summary><ul>{run.changed_files.map((file) => <li key={file}><code>{file}</code></li>)}</ul></details>}
    {run.verification.length > 0 && <div className="studio-tune-checks">{run.verification.map((item) => <span key={item}><Check />{item}</span>)}</div>}
  </> : null

  return createPortal(<div className="studio-tune-backdrop">
    <section
      className="studio-tune-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-busy={active || loading}
    >
      <header className="studio-tune-header">
        <div className="studio-tune-mark"><WandSparkles /></div>
        <div>
          <small>{tr('LOCAL ONLY · TUNE MODE', 'ЛИШЕ ЛОКАЛЬНО · РЕЖИМ TUNE')}</small>
          <h2 id={titleId}>{tr('Test generation', 'Тестова генерація')}</h2>
          <p>{tr(
            'Turn an idea and your feedback into a verified Studio implementation.',
            'Перетворіть ідею та свій відгук на перевірену реалізацію Студії.',
          )}</p>
        </div>
        <button className="ghost studio-tune-close" aria-label={tr('Close Tune wizard', 'Закрити майстер Tune')} onClick={onClose}><X /></button>
      </header>

      {loading && !detail && <div className="studio-tune-loading" role="status"><RefreshCcw className="spin" /> {tr('Checking local Tune runtime…', 'Перевіряється локальне середовище Tune…')}</div>}
      {detail && !detail.available && <div className="studio-tune-alert" role="alert"><strong>{tr('Tune mode is not ready.', 'Режим Tune не готовий.')}</strong><p>{detail.unavailable_reason}</p></div>}
      {error && <div className="studio-tune-alert" role="alert"><strong>{tr('Tune request could not continue.', 'Запит Tune не вдалося продовжити.')}</strong><p>{tr('Your draft is retained. Please try again.', 'Чернетку збережено. Спробуйте ще раз.')}</p></div>}

      {!reviewable && <div className="studio-tune-body">
        <div className="studio-tune-fields">
          <label>
            <span><b>1</b>{tr('Project idea', 'Ідея проєкту')}</span>
            <textarea
              ref={ideaRef}
              aria-label={tr('Project idea', 'Ідея проєкту')}
              disabled={active}
              rows={5}
              maxLength={4_000}
              value={projectIdea}
              onChange={(event) => setProjectIdea(event.target.value)}
              placeholder={tr('What are we testing, for whom, and why?', 'Що ми тестуємо, для кого і навіщо?')}
            />
          </label>
          <label>
            <span><b>2</b>{tr('How should the implementation look?', 'Якою має бути реалізація?')}</span>
            <textarea
              aria-label={tr('Desired implementation', 'Бажана реалізація')}
              disabled={active}
              rows={7}
              maxLength={6_000}
              value={implementation}
              onChange={(event) => setImplementation(event.target.value)}
              placeholder={tr('Describe the layout, behavior, controls, and feeling you expect.', 'Опишіть макет, поведінку, керування й очікуване враження.')}
            />
          </label>
          <label>
            <span><b>3</b>{tr('Your feedback', 'Ваш відгук')} <em>{tr('optional for the first pass', 'необов’язково для першої спроби')}</em></span>
            <textarea
              aria-label={tr('Your feedback', 'Ваш відгук')}
              disabled={active}
              rows={5}
              maxLength={4_000}
              value={feedback}
              onChange={(event) => updateFeedback(event.target.value)}
              placeholder={tr('After reviewing a pass: what should the generator change next?', 'Після перегляду: що генератор має змінити далі?')}
            />
          </label>
        </div>

        <aside className="studio-tune-safety">
          <small>{tr('SAFE SELF-TUNING', 'БЕЗПЕЧНЕ САМОНАЛАШТУВАННЯ')}</small>
          <h3>{tr('It can improve its Studio code.', 'Він може вдосконалювати код Студії.')}</h3>
          <p>{tr(
            'The agent may update Universal Studio rendering scripts, tests, styles, and Studio UI components—including this wizard UI.',
            'Агент може оновлювати скрипти рендерингу Universal Studio, тести, стилі й UI-компоненти Студії — зокрема інтерфейс цього майстра.',
          )}</p>
          <ul>
            <li>{tr('Works in a disposable copy first', 'Спочатку працює в одноразовій копії')}</li>
            <li>{tr('Cannot change production routes or the Tune safety runner', 'Не може змінювати production-маршрути чи захисний runner Tune')}</li>
            <li>{tr('Copies back only allowlisted files after all checks pass', 'Копіює назад лише дозволені файли після всіх перевірок')}</li>
          </ul>
        </aside>
      </div>}

      {reviewable && <section className="studio-tune-review">
        <figure className="studio-tune-preview studio-tune-review-preview">
          {reviewPreviewUrl
            ? <img
                src={reviewPreviewUrl}
                alt={run.status === 'failed'
                  ? tr('Current Studio creative for feedback', 'Поточний креатив Студії для відгуку')
                  : tr(`Generated creative for iteration ${run.iteration}`, `Згенерований креатив для ітерації ${run.iteration}`)}
              />
            : <div className={run.status === 'completed' && run.preview && !previewError ? 'studio-tune-preview-loading' : 'studio-tune-preview-error'} role="status">{run.status === 'completed' && run.preview && !previewError
              ? tr('Loading generated creative…', 'Завантажується згенерований креатив…')
              : tr('The preview is temporarily unavailable. Return to Studio and reopen feedback.', 'Попередній перегляд тимчасово недоступний. Поверніться до Студії та знову відкрийте відгук.')}</div>}
          <figcaption>{run.status === 'failed'
            ? tr('CURRENT STUDIO CREATIVE · 1080×1080', 'ПОТОЧНИЙ КРЕАТИВ СТУДІЇ · 1080×1080')
            : `${tr('GENERATED CREATIVE', 'ЗГЕНЕРОВАНИЙ КРЕАТИВ')} · ${run.preview?.width || 1080}×${run.preview?.height || 1080}`}</figcaption>
        </figure>

        <div className="studio-tune-review-feedback">
          <small>{tr('REVIEW THE CREATIVE', 'ПЕРЕГЛЯНЬТЕ КРЕАТИВ')}</small>
          <h3>{tr('What should change?', 'Що потрібно змінити?')}</h3>
          <p>{run.status === 'failed' ? tr(
            'The previous automated attempt stopped safely. Review the current Studio creative and adjust or retry your feedback.',
            'Попередню автоматичну спробу безпечно зупинено. Перегляньте поточний креатив Студії та уточніть або повторіть відгук.',
          ) : tr(
            'The original idea and implementation are retained. Describe only what should change in this creative.',
            'Початкову ідею та реалізацію збережено. Опишіть лише те, що потрібно змінити в цьому креативі.',
          )}</p>
          <label>
            <span>{tr('Feedback for next iteration', 'Відгук для наступної ітерації')}</span>
            <textarea
              aria-label={tr('Feedback for next iteration', 'Відгук для наступної ітерації')}
              rows={7}
              maxLength={4_000}
              value={feedback}
              onChange={(event) => updateFeedback(event.target.value)}
              placeholder={tr(
                'Describe exactly what should change in the creative shown here.',
                'Опишіть точно, що потрібно змінити у показаному тут креативі.',
              )}
            />
          </label>
          <details className="studio-tune-context">
            <summary>{tr('Original direction', 'Початковий напрям')}</summary>
            <dl>
              <div><dt>{tr('Project idea', 'Ідея проєкту')}</dt><dd>{projectIdea}</dd></div>
              <div><dt>{tr('Implementation', 'Реалізація')}</dt><dd>{implementation}</dd></div>
            </dl>
          </details>
          <div className="studio-tune-rule-approval">
            <div>
              <strong>{tr('Use this in future Tune runs', 'Використовувати в майбутніх запусках Tune')}</strong>
              <span>{tr(
                'This saves the text shown below as a reusable Studio rule, not as a one-off preference.',
                'Текст нижче буде збережено як повторно використовуване правило Студії, а не як разове побажання.',
              )}</span>
              {ruleCandidate && <code title={ruleCandidate}>{ruleCandidate}</code>}
            </div>
            <button className="secondary" disabled={ruleSaving || !ruleCandidateReady || currentRuleSaved} onClick={() => void saveRule()}><Save />{currentRuleSaved
              ? tr('Reusable rule saved', 'Повторно використовуване правило збережено')
              : tr('Save as reusable rule', 'Зберегти як повторно використовуване правило')}</button>
          </div>
          {ruleNotice && <p className="studio-tune-rule-notice" role="status">{ruleNotice}</p>}
          {ruleError && <p className="studio-tune-rule-error" role="alert">{ruleError}</p>}
        </div>
      </section>}

      {run && <section className={`studio-tune-run studio-tune-run-${run.status}`} aria-live="polite">
        <header>
          {run.status === 'completed' ? <Check /> : <RefreshCcw className={active ? 'spin' : ''} />}
          <div><small>{tr(`ITERATION ${run.iteration}`, `ІТЕРАЦІЯ ${run.iteration}`)}</small><strong>{stageLabels[run.stage]}</strong></div>
        </header>
        {active && <><p>{tr(
          'Keep this local app running. Verified changes will appear through the development server when the run finishes.',
          'Не закривайте локальний застосунок. Перевірені зміни з’являться через dev-сервер після завершення.',
        )}</p><div className="studio-tune-progress" role="progressbar" aria-label={tr('Tune generation progress', 'Прогрес генерації Tune')} /></>}
        {reviewable ? <details className="studio-tune-report"><summary>{tr('Iteration report', 'Звіт ітерації')}</summary>{runReport}</details> : runReport}
      </section>}

      <footer className="studio-tune-actions">
        {reviewable && <button className="secondary" onClick={onClose}><ArrowLeft />{tr('Back to Studio', 'Назад до Студії')}</button>}
        {reviewable && <button className="secondary" onClick={anotherIteration}><WandSparkles />{tr('Start a new direction', 'Почати новий напрям')}</button>}
        {reviewable && <button className="primary" disabled={loading || !detail?.available || !feedbackReady} onClick={() => void start()}><WandSparkles />{run?.status === 'failed' ? tr('Retry feedback', 'Повторити відгук') : tr('Apply feedback', 'Застосувати відгук')}</button>}
        {!active && !run && <button className="primary" disabled={loading || !detail?.available || !ready} onClick={() => void start()}><WandSparkles />{feedback.trim() ? tr('Apply feedback', 'Застосувати відгук') : tr('Generate test', 'Згенерувати тест')}</button>}
      </footer>
    </section>
  </div>, document.body)
}
