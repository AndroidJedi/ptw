import { Activity, BarChart3, BookOpenCheck, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import type { AnalyticsWorkspace, CreativeLearningRun, CreativeRuleFamily, CreativeSkillRule } from '../types'

type EditableRule = CreativeSkillRule & { targetText: string; selected: boolean }

const uuid = () => crypto.randomUUID()
const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`
const number = (value: number) => new Intl.NumberFormat().format(Math.round(value))

function editable(rule: CreativeSkillRule): EditableRule {
  return { ...rule, targetText: JSON.stringify(rule.target || {}, null, 2), selected: true }
}

function requestRule(rule: EditableRule): Record<string, unknown> {
  let target: Record<string, unknown>
  try { target = JSON.parse(rule.targetText) as Record<string, unknown> } catch { throw new Error('Rule target must be valid JSON.') }
  return {
    ...(rule.rule_id ? { rule_id: rule.rule_id } : {}),
    ...(rule.candidate_id ? { candidate_id: rule.candidate_id } : {}),
    surface: rule.surface, family: rule.family, instruction: rule.instruction,
    target, evidence: rule.evidence || {}, confidence: rule.confidence,
    active: true, tombstone: false,
  }
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return <article className="analytics-metric"><small>{label}</small><strong>{value}</strong>{note && <span>{note}</span>}</article>
}

function RuleEditor({ rule, selection, onChange, onSave, onDelete, busy, language }: {
  rule: EditableRule; selection?: boolean; onChange: (rule: EditableRule) => void
  onSave?: () => void; onDelete?: () => void; busy: boolean; language: Language
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const families: CreativeRuleFamily[] = rule.scope === 'global'
    ? ['spirit']
    : ['ui', 'copy', 'image', 'domain']
  const exactSurface = rule.family === 'ui' || rule.family === 'copy' || rule.family === 'image'
  return <article className="analytics-rule">
    <header>
      {selection && <input aria-label={tr('Select candidate', 'Вибрати кандидата')} type="checkbox" checked={rule.selected} onChange={event => onChange({ ...rule, selected: event.target.checked })} />}
      <label>{tr('Family', 'Сімейство')}<select value={rule.family} onChange={event => { const family = event.target.value as CreativeRuleFamily; const requiresExactSurface = family === 'ui' || family === 'copy' || family === 'image'; onChange({ ...rule, family, surface: requiresExactSurface && rule.surface === 'both' ? 'post' : rule.surface, targetText: '{}' }) }}>{families.map(family => <option key={family} value={family}>{family}</option>)}</select></label>
      <label>{tr('Surface', 'Поверхня')}<select value={rule.surface} onChange={event => onChange({ ...rule, surface: event.target.value as CreativeSkillRule['surface'] })}><option value="post">post</option><option value="landing">landing</option>{!exactSurface && <option value="both">both</option>}</select></label>
      <span>{rule.confidence.level} · n={rule.confidence.sample_size} · {rule.confidence.project_count ?? (rule.scope === 'global' ? 0 : 1)} {tr('Projects', 'проєктів')}</span>
    </header>
    <label>{tr('Instruction', 'Правило')}<textarea value={rule.instruction} maxLength={1000} onChange={event => onChange({ ...rule, instruction: event.target.value })} /></label>
    {(rule.family === 'ui' || rule.family === 'copy' || rule.family === 'image') && <label>{tr('Typed target (JSON)', 'Типізована ціль (JSON)')}<textarea className="analytics-target" value={rule.targetText} onChange={event => onChange({ ...rule, targetText: event.target.value })} /></label>}
    <footer>
      {onSave && <button className="secondary" disabled={busy} onClick={onSave}><BookOpenCheck />{tr('Save revision', 'Зберегти редакцію')}</button>}
      {onDelete && <button className="ghost danger" disabled={busy} onClick={onDelete}><Trash2 />{tr('Delete', 'Видалити')}</button>}
    </footer>
  </article>
}

export function AnalyticsView({ api, language, projectId }: { api: ApiClient; language: Language; projectId: string | null }) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const [allProjects, setAllProjects] = useState(false)
  const [windowDays, setWindowDays] = useState<0 | 7 | 30 | 90>(30)
  const [workspace, setWorkspace] = useState<AnalyticsWorkspace | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [candidates, setCandidates] = useState<EditableRule[]>([])
  const [rules, setRules] = useState<EditableRule[]>([])
  const scope = allProjects ? 'global' : projectId

  const load = async () => {
    if (!scope) { setWorkspace(null); return }
    setError('')
    const value = await api.get<AnalyticsWorkspace>(`/api/v1/analytics/${scope}/workspace?window=${windowDays}`)
    setWorkspace(value)
    setRules(value.skills.rules.filter(rule => !rule.tombstone).map(editable))
    const review = value.learning_runs.find(run => run.status === 'completed' && !run.decision)
    setCandidates((review?.candidates || []).map(editable))
  }

  useEffect(() => { void load().catch(cause => setError(String(cause.message || cause))) }, [api, scope, windowDays]) // eslint-disable-line react-hooks/exhaustive-deps

  const mutate = async (operation: () => Promise<unknown>, message: string) => {
    setBusy(true); setError(''); setNotice('')
    try { await operation(); setNotice(message); await load() }
    catch (cause) { setError(String((cause as Error).message || cause)) }
    finally { setBusy(false) }
  }

  const latestReview = useMemo<CreativeLearningRun | undefined>(() => workspace?.learning_runs.find(run => run.status === 'completed' && !run.decision), [workspace])
  const tombstones = workspace?.skills.rules.filter(rule => rule.tombstone) || []
  const revise = (index: number, next: EditableRule) => setRules(current => current.map((item, itemIndex) => itemIndex === index ? next : item))
  const reviseCandidate = (index: number, next: EditableRule) => setCandidates(current => current.map((item, itemIndex) => itemIndex === index ? next : item))

  if (!scope) return <section className="empty-state"><BarChart3 /><h2>{tr('Select a Project', 'Оберіть проєкт')}</h2><p>{tr('Analytics can show one Project or All Projects.', 'Аналітика показує один проєкт або всі проєкти.')}</p><button className="primary" onClick={() => setAllProjects(true)}>{tr('View All Projects', 'Усі проєкти')}</button></section>

  return <section className="analytics-view">
    <header className="analytics-header"><div><small>{tr('MEASURE → REVIEW → IMPROVE', 'ВИМІРЮВАТИ → ПЕРЕГЛЯНУТИ → ПОКРАЩИТИ')}</small><h1>{tr('Creative Analytics', 'Аналітика креативів')}</h1><p>{tr('Performance evidence and reviewed Creative Skills. Nothing activates automatically.', 'Докази ефективності та перевірені навички. Нічого не активується автоматично.')}</p></div><div className="analytics-controls"><div className="segmented"><button className={!allProjects ? 'active' : ''} disabled={!projectId} onClick={() => setAllProjects(false)}>{tr('Selected Project', 'Обраний проєкт')}</button><button className={allProjects ? 'active' : ''} onClick={() => setAllProjects(true)}>{tr('All Projects', 'Усі проєкти')}</button></div><select aria-label={tr('Analytics window', 'Період аналітики')} value={windowDays} onChange={event => setWindowDays(Number(event.target.value) as 0 | 7 | 30 | 90)}><option value={7}>7d</option><option value={30}>30d</option><option value={90}>90d</option><option value={0}>{tr('All time', 'За весь час')}</option></select><button className="secondary" disabled={busy} onClick={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/refresh`, { provider: 'all', backfill: false }, { deadlineMs: 180_000 }), tr('Analytics refreshed.', 'Аналітику оновлено.'))}><RefreshCw />{tr('Refresh', 'Оновити')}</button><button className="ghost" disabled={busy} onClick={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/refresh`, { provider: 'all', backfill: true }, { deadlineMs: 180_000 }), tr('One-time backfill recorded.', 'Одноразове дозаповнення записано.'))}>{tr('Backfill older posts', 'Дозаповнити старі дописи')}</button></div></header>
    {error && <p className="notice danger" role="alert">{error}</p>}{notice && <p className="notice">{notice}</p>}
    {!workspace ? <div className="loading-card" role="status">{tr('Loading analytics…', 'Завантаження аналітики…')}</div> : <>
      <div className="analytics-readiness">{Object.entries(workspace.readiness).map(([provider, state]) => { const stamp = provider === 'instagram' ? workspace.freshness.instagram : null; const stale = Boolean(stamp && Date.now() - new Date(stamp).getTime() > 72 * 60 * 60 * 1000); const detail = state.available === true ? stamp ? `${stale ? tr('Stale', 'Застаріло') : tr('Latest', 'Останнє')}: ${new Date(stamp).toLocaleString()}` : tr('Ready · no snapshot yet', 'Готово · знімків ще немає') : state.explanation || tr('Not verified', 'Не перевірено'); return <article key={provider}><span className={state.available === false ? 'status-dot unavailable' : stale || state.available !== true ? 'status-dot stale' : 'status-dot ready'} /> <strong>{provider}</strong><small>{detail}</small></article> })}</div>
      <div className="analytics-metrics"><Metric label={tr('Landing views', 'Перегляди лендінгу')} value={number(workspace.landing_funnel.landing_view)} /><Metric label={tr('Primary CTA rate', 'Частка основного CTA')} value={percent(workspace.landing_funnel.primary_cta_rate)} /><Metric label={tr('Outbound contact rate', 'Частка переходів до контакту')} value={percent(workspace.landing_funnel.outbound_contact_rate)} note={tr('Conversion proxy—not leads or sales', 'Проксі конверсії, не ліди чи продажі')} /><Metric label={tr('Measured posts', 'Виміряні дописи')} value={number(workspace.organic.length)} /></div>

      <section className="panel analytics-section analytics-funnel"><header><div><small>{tr('FIRST-PARTY LANDING', 'ВЛАСНА АНАЛІТИКА ЛЕНДІНГУ')}</small><h2>{tr('Landing funnel', 'Воронка лендінгу')}</h2></div><p>{tr('Cookieless events · outbound contact is a conversion proxy', 'Події без cookies · перехід до контакту є проксі конверсії')}</p></header><div className="analytics-funnel-flow"><Metric label={tr('1 · Landing views', '1 · Перегляди')} value={number(workspace.landing_funnel.landing_view)} /><span aria-hidden="true">→</span><Metric label={tr('2 · Primary CTA clicks', '2 · Кліки основного CTA')} value={number(workspace.landing_funnel.primary_cta_click)} note={percent(workspace.landing_funnel.primary_cta_rate)} /><span aria-hidden="true">→</span><Metric label={tr('3 · Contact clicks', '3 · Переходи до контактів')} value={number(workspace.landing_funnel.contact_click)} note={percent(workspace.landing_funnel.outbound_contact_rate)} /></div><div className="analytics-surface-breakdown">{Object.entries(workspace.landing_funnel.surfaces).map(([surface, count]) => <span key={surface}><strong>{surface}</strong> {number(count)}</span>)}</div></section>

      <section className="panel analytics-section"><header><div><small>{tr('ORGANIC', 'ОРГАНІКА')}</small><h2>{tr('Post leaderboard', 'Рейтинг дописів')}</h2></div></header>{workspace.organic.length === 0 ? <p className="analytics-empty">{tr('No provider snapshots in this window.', 'У цьому періоді немає знімків провайдера.')}</p> : <div className="analytics-table-wrap"><table><thead><tr><th>{tr('Platform', 'Платформа')}</th><th>{tr('Age', 'Вік')}</th><th>{tr('Views', 'Перегляди')}</th><th>{tr('Contact proxy', 'Проксі контакту')}</th><th>CTA</th><th>{tr('High intent', 'Високий намір')}</th><th>{tr('Freshness', 'Свіжість')}</th></tr></thead><tbody>{workspace.organic.map(item => <tr key={item.publication_id}><td>{item.provider}</td><td>{Math.floor(item.age_hours / 24)}d</td><td>{number(item.metrics.views)}</td><td>{percent(item.rates.outbound_contact)}</td><td>{percent(item.rates.primary_cta)}</td><td>{percent(item.rates.high_intent)}</td><td>{item.insight ? new Date(item.insight.created_at).toLocaleString() : tr('Unavailable', 'Недоступно')}</td></tr>)}</tbody></table></div>}</section>

      <section className="analytics-grid"><article className="panel analytics-section"><header><div><small>{tr('PAID META', 'ПЛАТНА META')}</small><h2>{tr('Ad snapshots', 'Знімки реклами')}</h2></div></header>{workspace.paid.length ? workspace.paid.map(item => <p key={item.deployment_id}><strong>{item.status}</strong> · {item.destination_type || 'Instagram Direct'} · {item.latest_insight ? new Date(item.latest_insight.created_at).toLocaleString() : tr('No snapshot', 'Немає знімка')}</p>) : <p className="analytics-empty">{tr('No ads in scope.', 'У цьому охопленні немає реклами.')}</p>}</article><article className="panel analytics-section"><header><div><small>{tr('LEARNING CURVE', 'КРИВА НАВЧАННЯ')}</small><h2>{tr('Skill snapshot cohorts', 'Когорти знімків навичок')}</h2></div></header>{workspace.learning_curve.length ? workspace.learning_curve.map((item, index) => <p key={index}>{tr('Snapshot cohort', 'Когорта')} {index + 1}: {item.items} · {number(item.views)} {tr('views', 'переглядів')} · {number(item.contact_clicks)} {tr('contact clicks', 'переходів')}</p>) : <p className="analytics-empty">{tr('New generations will record exact Project and global snapshot IDs.', 'Нові генерації запишуть точні ID проєктного та глобального знімків.')}</p>}</article></section>

      <section className="panel analytics-section"><header><div><small>{tr('EXPLICIT RUN', 'ЯВНИЙ ЗАПУСК')}</small><h2>{tr('Performance learning', 'Навчання на ефективності')}</h2></div><div className="analytics-actions"><button className="secondary" disabled={busy} onClick={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/learning-runs`, { request_id: uuid(), surface: 'post' }, { deadlineMs: 480_000 }), tr('Post learning run finished.', 'Навчання дописів завершено.'))}><Sparkles />{tr('Run Post learning', 'Навчання дописів')}</button><button className="secondary" disabled={busy} onClick={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/learning-runs`, { request_id: uuid(), surface: 'landing' }, { deadlineMs: 480_000 }), tr('Landing learning run finished.', 'Навчання лендінгів завершено.'))}><Activity />{tr('Run Landing learning', 'Навчання лендінгів')}</button></div></header>{workspace.learning_runs[0]?.status === 'insufficient_data' && <p className="notice">{tr('Insufficient data: at least two comparable items aged 72 hours are required.', 'Недостатньо даних: потрібні щонайменше два порівнювані елементи віком 72 години.')}</p>}{workspace.learning_runs[0]?.status === 'failed' && <p className="notice danger">{workspace.learning_runs[0].error_message}</p>}{latestReview && <div className="analytics-review"><h3>{tr('Review every candidate', 'Перегляньте кожного кандидата')}</h3><p>{tr('Select and edit rules before activation, or reject the complete run.', 'Виберіть і відредагуйте правила перед активацією або відхиліть увесь запуск.')}</p>{candidates.map((rule, index) => <RuleEditor key={rule.candidate_id || rule.rule_id} rule={rule} selection onChange={next => reviseCandidate(index, next)} busy={busy} language={language} />)}<div className="analytics-actions"><button className="primary" disabled={busy || !candidates.some(rule => rule.selected)} onClick={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/learning-runs/${latestReview.learning_run_id}/decision`, { request_id: uuid(), decision: 'activate', rules: candidates.filter(rule => rule.selected).map(requestRule) }), tr('Selected rules activated in a new immutable snapshot.', 'Вибрані правила активовано в новому незмінному знімку.'))}>{tr('Activate selected', 'Активувати вибрані')}</button><button className="ghost danger" disabled={busy} onClick={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/learning-runs/${latestReview.learning_run_id}/decision`, { request_id: uuid(), decision: 'reject', rules: [] }), tr('Learning candidates rejected.', 'Кандидатів навчання відхилено.'))}>{tr('Reject run', 'Відхилити запуск')}</button></div></div>}</section>

      <section className="panel analytics-section"><header><div><small>{workspace.scope === 'global' ? tr('GLOBAL SPIRIT', 'ГЛОБАЛЬНИЙ ДУХ') : tr('PROJECT SKILL', 'НАВИЧКА ПРОЄКТУ')}</small><h2>{tr('Complete Creative Skill', 'Повна творча навичка')}</h2><p>{workspace.skills.snapshot ? `v${workspace.skills.snapshot.version} · ${workspace.skills.snapshot.rules_sha256.slice(0, 12)}` : tr('No active snapshot yet.', 'Активного знімка ще немає.')}</p></div><button className="secondary" disabled={busy} onClick={() => { const family: CreativeRuleFamily = workspace.scope === 'global' ? 'spirit' : 'domain'; setRules(current => [...current, editable({ rule_id: uuid(), scope: workspace.scope, project_id: workspace.project_id, surface: 'both', family, instruction: '', target: {}, evidence: { source: 'owner' }, confidence: { sample_size: 0, level: 'owner' }, active: true, tombstone: false })]) }}>{tr('Add rule', 'Додати правило')}</button></header>{rules.length === 0 ? <p className="analytics-empty">{tr('No active rules. Add one directly or run learning after enough evidence exists.', 'Немає активних правил. Додайте правило або запустіть навчання після накопичення доказів.')}</p> : rules.map((rule, index) => <RuleEditor key={rule.rule_id} rule={rule} onChange={next => revise(index, next)} onSave={() => void mutate(() => api.post(`/api/v1/analytics/${scope}/skills/revisions`, { request_id: uuid(), rule: requestRule(rule) }), tr('Rule saved in a new immutable snapshot.', 'Правило збережено в новому незмінному знімку.'))} onDelete={workspace.skills.rules.some(item => item.rule_id === rule.rule_id) ? () => void mutate(() => api.post(`/api/v1/analytics/${scope}/skills/${rule.rule_id}/delete`, { request_id: uuid() }), tr('Rule tombstone created.', 'Створено позначку видалення правила.')) : undefined} busy={busy} language={language} />)}{tombstones.length > 0 && <details className="analytics-tombstones"><summary>{tr('Deleted rule history', 'Історія видалених правил')} ({tombstones.length})</summary>{tombstones.map(rule => <p key={rule.rule_id}><strong>{rule.family} · {rule.surface}</strong> — {rule.instruction}</p>)}</details>}</section>

      <details className="panel analytics-definitions"><summary>{tr('Metric definitions and limitations', 'Визначення та обмеження метрик')}</summary>{Object.entries(workspace.metric_definitions).map(([key, item]) => <p key={key}><strong>{key}</strong>: {item.numerator} ÷ {item.denominator}. {item.source}. {item.limitation || ''}</p>)}</details>
    </>}
  </section>
}
