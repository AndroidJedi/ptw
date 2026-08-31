import { ArrowRight, Check, Trophy, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ApiClient } from '../api'
import { translate, type Language } from '../i18n'
import type {
  CandidateParameterName, ContentCandidate, ContentDebug, CriticPassDebug,
} from '../types'

const parameterNames: CandidateParameterName[] = [
  'hook_pressure',
  'emotional_intensity',
  'conceptual_novelty',
  'information_density',
  'visual_complexity',
]

const parameterLabels: Record<CandidateParameterName, { en: string; uk: string }> = {
  hook_pressure: { en: 'Hook pressure', uk: 'Сила гачка' },
  emotional_intensity: { en: 'Emotional intensity', uk: 'Емоційна інтенсивність' },
  conceptual_novelty: { en: 'Concept novelty', uk: 'Новизна концепції' },
  information_density: { en: 'Information density', uk: 'Щільність інформації' },
  visual_complexity: { en: 'Visual complexity', uk: 'Візуальна складність' },
}

const scoreLabels: Record<string, { en: string; uk: string }> = {
  task_brief_suitability: { en: 'Brief fit', uk: 'Відповідність брифу' },
  hook_strength: { en: 'Hook', uk: 'Гачок' },
  message_clarity: { en: 'Clarity', uk: 'Ясність' },
  persuasion_action: { en: 'Persuasion', uk: 'Переконливість' },
  coherence: { en: 'Coherence', uk: 'Цілісність' },
  specificity_credibility: { en: 'Credibility', uk: 'Достовірність' },
  composition_legibility: { en: 'Composition', uk: 'Композиція' },
  originality_tone: { en: 'Originality', uk: 'Оригінальність' },
}

function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
}

function CandidatePreviewImage({
  api, candidate, language,
}: {
  api: ApiClient
  candidate: ContentCandidate
  language: Language
}) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)
  const tr = (en: string, uk: string) => translate(language, en, uk)

  useEffect(() => {
    let local = ''
    let active = true
    setUrl('')
    setFailed(false)
    void api.image(
      candidate.preview.asset_url,
      candidate.preview.mime_type,
      candidate.preview.sha256,
    ).then((blob) => {
      if (!active || !(blob instanceof Blob)) return
      local = URL.createObjectURL(blob)
      setUrl(local)
    }).catch(() => { if (active) setFailed(true) })
    return () => {
      active = false
      if (local) URL.revokeObjectURL(local)
    }
  }, [api, candidate.candidate_id, candidate.preview.sha256])

  if (failed) return <div className="candidate-image-state">{tr('Preview unavailable', 'Попередній перегляд недоступний')}</div>
  if (!url) return <div className="candidate-image-state">{tr('Loading preview…', 'Завантаження перегляду…')}</div>
  return <img src={url} alt={candidate.document.alt_text} />
}

function scoreFor(candidateId: string, pass: CriticPassDebug | undefined) {
  return pass?.candidate_scores[candidateId]
}

function CandidateCard({
  api, candidate, pass, selectedCandidateId, language,
}: {
  api: ApiClient
  candidate: ContentCandidate
  pass: CriticPassDebug | undefined
  selectedCandidateId?: string
  language: Language
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const evaluation = scoreFor(candidate.candidate_id, pass)
  const gates = pass?.hard_gates[candidate.candidate_id] || {}
  const failedGates = Object.entries(gates).filter(([, value]) => !value)
  const selected = candidate.candidate_id === selectedCandidateId

  return <article className={`candidate-card${selected ? ' final-candidate' : ''}`}>
    <div className="candidate-image-wrap">
      <CandidatePreviewImage api={api} candidate={candidate} language={language} />
      <span className="candidate-number">{candidate.alias}</span>
      {selected && <span className="winner-badge"><Trophy />{tr('Final', 'Фінал')}</span>}
    </div>
    <div className="candidate-card-body">
      <div className="candidate-heading">
        <div><small>{tr('DIRECTION', 'НАПРЯМ')}</small><h4>{humanize(candidate.template_id)}</h4></div>
        <span className="version-tag">v{candidate.template_version}</span>
      </div>
      <p className="candidate-hook">{candidate.document.hook}</p>
      <div className="candidate-verdict">
        {evaluation ? <span className={failedGates.length ? 'failed' : 'passed'}>
          {failedGates.length ? <X /> : <Check />}
          {failedGates.length
            ? tr(`${failedGates.length} gate${failedGates.length === 1 ? '' : 's'} failed`, `${failedGates.length} перевірок не пройдено`)
            : tr('All hard gates passed', 'Усі обов’язкові перевірки пройдено')}
        </span> : <span>{tr('Not evaluated', 'Не оцінено')}</span>}
        {evaluation && <strong>{Math.round(evaluation.weighted_total)}/100</strong>}
      </div>
      {evaluation && <div className={`eligibility-state ${evaluation.eligible ? 'passed' : 'failed'}`}>
        {evaluation.eligible ? <Check /> : <X />}
        <strong>{evaluation.eligible ? tr('Eligible', 'Придатний') : tr('Not eligible', 'Непридатний')}</strong>
        <span>{tr(`Complexity: ${evaluation.complexity}`, `Складність: ${evaluation.complexity}`)}</span>
      </div>}
      {!!failedGates.length && <div className="failed-gate-list">
        <small>{tr('FAILED GATES', 'НЕПРОЙДЕНІ ПЕРЕВІРКИ')}</small>
        {failedGates.map(([name]) => <span key={name}>{humanize(name)}</span>)}
      </div>}
      {evaluation && <div className="candidate-score-grid">
        {Object.entries(evaluation.scores).map(([name, score]) => <div key={name}>
          <span>{translate(language, scoreLabels[name]?.en || humanize(name), scoreLabels[name]?.uk || humanize(name))}</span>
          <strong>{score}/10</strong>
        </div>)}
      </div>}
      <div className="parameter-list">
        {parameterNames.map((name) => <div className="parameter-row" key={name}>
          <span>{translate(language, parameterLabels[name].en, parameterLabels[name].uk)}</span>
          <div className="parameter-track" aria-hidden="true"><i style={{ width: `${candidate.parameters[name]}%` }} /></div>
          <strong>{candidate.parameters[name]}</strong>
        </div>)}
      </div>
      {evaluation?.reason_codes.length ? <p className="reason-codes">
        {evaluation.reason_codes.map(humanize).join(' · ')}
      </p> : null}
    </div>
  </article>
}

function DecisionStage({
  pass, candidates, selectedCandidateId, language, groupedLocal,
}: {
  pass: CriticPassDebug
  candidates: Map<string, ContentCandidate>
  selectedCandidateId?: string
  language: Language
  groupedLocal: boolean
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const stageTitles = groupedLocal ? {
    1: tr('Screen the first three', 'Перевірка перших трьох'),
    2: tr('Screen the remaining two', 'Перевірка решти двох'),
    3: tr('Compare both group winners', 'Порівняння переможців груп'),
  } : {
    1: tr('Screen all five', 'Перевірка всіх п’яти'),
    2: tr('Compare improvements', 'Порівняння покращень'),
    3: tr('Choose the finalist', 'Вибір фіналіста'),
  }
  const passing = pass.ranking.filter((id) => {
    const gates = pass.hard_gates[id] || {}
    return Object.values(gates).every(Boolean)
  }).length

  return <article className={`decision-stage pass-${pass.pass_number}`}>
    <header><span>{pass.pass_number}</span><div><small>{tr(`PASS ${pass.pass_number}`, `ЕТАП ${pass.pass_number}`)}</small><h4>{stageTitles[pass.pass_number]}</h4></div></header>
    <p className="stage-rule">
      {tr(`${passing} of ${pass.ranking.length} passed every hard gate.`, `${passing} з ${pass.ranking.length} пройшли всі обов’язкові перевірки.`)}
    </p>
    <ol className="stage-ranking">
      {pass.ranking.map((id, index) => {
        const candidate = candidates.get(id)
        const score = scoreFor(id, pass)
        const selected = id === selectedCandidateId
        return <li key={id} className={selected ? 'selected' : ''}>
          <span>{index + 1}</span>
          <strong>{candidate?.alias || id.slice(0, 8)}</strong>
          {score && <em>{Math.round(score.weighted_total)}</em>}
          {selected && <Trophy aria-label={tr('Final selection', 'Фінальний вибір')} />}
        </li>
      })}
    </ol>
    {!!pass.pairwise_results.length && <div className="pairwise-list">
      <small>{tr('HEAD-TO-HEAD', 'ПОПАРНЕ ПОРІВНЯННЯ')}</small>
      {pass.pairwise_results.map((pair) => <p key={`${pair.left}-${pair.right}`}>
        <span>{candidates.get(pair.left)?.alias || pair.left.slice(0, 8)}</span>
        <ArrowRight />
        <strong>{candidates.get(pair.winner)?.alias || pair.winner.slice(0, 8)}</strong>
        <small>{pair.reason_codes.map(humanize).join(', ')}</small>
      </p>)}
    </div>}
    {!!pass.actions.length && <p className="stage-actions">
      <strong>{tr('Next:', 'Далі:')}</strong>{' '}
      {pass.actions.map((action) => humanize(action.action_type)).join(' · ')}
    </p>}
    <ul className="stage-observations">{pass.observations.map((item) => <li key={item}>{item}</li>)}</ul>
  </article>
}

export function ResultDecisionTrace({
  value, api, selectedCandidateId, language,
}: {
  value: ContentDebug
  api: ApiClient
  selectedCandidateId?: string
  language: Language
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const initialCandidates = value.candidates.filter((candidate) => candidate.generation_kind === 'initial').slice(0, 5)
  const byId = useMemo(
    () => new Map(value.candidates.map((candidate) => [candidate.candidate_id, candidate])),
    [value.candidates],
  )
  const firstPass = value.critic_passes.find((pass) => pass.pass_number === 1)
  const secondPass = value.critic_passes.find((pass) => pass.pass_number === 2)
  const finalPass = value.critic_passes.find((pass) => pass.pass_number === 3)
  const groupedLocal = firstPass?.critic_scope === 'screening_group_1_of_2'
    || (firstPass?.active_candidate_ids.length === 3 && secondPass?.active_candidate_ids.length === 2)
  const finalId = finalPass?.final_selection?.candidate_id || selectedCandidateId

  return <div className="decision-trace">
    <section className="trace-intro">
      <small>{tr('FIVE INITIAL DIRECTIONS', 'П’ЯТЬ ПОЧАТКОВИХ НАПРЯМІВ')}</small>
      <h3>{tr('Every image and its exact generation parameters', 'Кожне зображення та точні параметри його створення')}</h3>
      <p>{tr(
        groupedLocal
          ? 'Each direction shows its own screening score, failed gates, and critic reason codes.'
          : 'Pass 1 scores shown below. Hard gates are checked before the weighted score can count.',
        groupedLocal
          ? 'Для кожного напряму показано його оцінку, непройдені перевірки та коди причин критика.'
          : 'Нижче показані оцінки етапу 1. Обов’язкові перевірки виконуються до врахування зваженої оцінки.',
      )}</p>
    </section>
    <section className="candidate-grid">
      {initialCandidates.map((candidate) => <CandidateCard
        key={candidate.candidate_id}
        api={api}
        candidate={candidate}
        pass={value.critic_passes.find((pass) => (
          pass.pass_number < 3 && pass.active_candidate_ids.includes(candidate.candidate_id)
        )) || firstPass}
        selectedCandidateId={finalId}
        language={language}
      />)}
    </section>

    <section className="trace-intro decision-intro">
      <small>{tr('DECISION PATH', 'ШЛЯХ РІШЕННЯ')}</small>
      <h3>{finalPass && !finalPass.final_selection
        ? tr('How the five directions were screened', 'Як було перевірено п’ять напрямів')
        : tr('How five directions became one final post', 'Як п’ять напрямів стали одним фінальним дописом')}</h3>
      <p>{tr(
        groupedLocal
          ? 'The critic independently screened groups of three and two, then re-evaluated both group winners side by side.'
          : 'The system first rejects hard-gate failures, then ranks eligible work by weighted score, compares the strongest directions head-to-head, improves bounded elements, and rechecks the final two.',
        groupedLocal
          ? 'Критик незалежно перевірив групи з трьох і двох варіантів, а потім повторно порівняв переможців обох груп.'
          : 'Система спочатку відхиляє роботи, що не пройшли обов’язкові перевірки, потім ранжує придатні варіанти за зваженою оцінкою, попарно порівнює найсильніші напрями, точково покращує елементи й повторно перевіряє фінальні два.',
      )}</p>
    </section>
    <section className="decision-flow">
      {value.critic_passes.map((pass, index) => <div className="decision-flow-step" key={pass.pass_id}>
        <DecisionStage pass={pass} candidates={byId} selectedCandidateId={finalId} language={language} groupedLocal={groupedLocal} />
        {index < value.critic_passes.length - 1 && <ArrowRight className="flow-arrow" />}
      </div>)}
    </section>
    {finalPass?.final_selection && <section className="final-decision">
      <Trophy />
      <div>
        <small>{tr('FINAL DECISION', 'ФІНАЛЬНЕ РІШЕННЯ')}</small>
        <h3>{tr('Selected', 'Обрано')} {byId.get(finalPass.final_selection.candidate_id)?.alias || tr('final candidate', 'фінальний варіант')}</h3>
        <ul>{finalPass.final_selection.decision_summary.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
    </section>}
    {finalPass && !finalPass.final_selection && <section className="final-decision no-selection">
      <X />
      <div>
        <small>{tr('FINAL DECISION', 'ФІНАЛЬНЕ РІШЕННЯ')}</small>
        <h3>{tr('No eligible finalist', 'Немає придатного фіналіста')}</h3>
        <p>{tr(
          'The comparison completed, but neither group winner passed every eligibility rule. Nothing was silently discarded: both finalists and all prior evidence remain visible above.',
          'Порівняння завершено, але жоден переможець групи не пройшов усі правила придатності. Нічого не приховано: обидва фіналісти та всі попередні дані показані вище.',
        )}</p>
        <ul>{finalPass.ranking.map((id) => {
          const score = finalPass.candidate_scores[id]
          return <li key={id}>
            <strong>{byId.get(id)?.alias || id.slice(0, 8)}</strong>{' · '}
            {Math.round(score.weighted_total)}/100 · {score.reason_codes.map(humanize).join(', ')}
          </li>
        })}</ul>
      </div>
    </section>}
  </div>
}
