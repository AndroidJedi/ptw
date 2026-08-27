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
  const failedGates = Object.values(gates).filter((value) => !value).length
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
        <span className={failedGates ? 'failed' : 'passed'}>
          {failedGates ? <X /> : <Check />}
          {failedGates
            ? tr(`${failedGates} gate${failedGates === 1 ? '' : 's'} failed`, `${failedGates} перевірок не пройдено`)
            : tr('All hard gates passed', 'Усі обов’язкові перевірки пройдено')}
        </span>
        {evaluation && <strong>{Math.round(evaluation.weighted_total)}/100</strong>}
      </div>
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
  pass, candidates, selectedCandidateId, language,
}: {
  pass: CriticPassDebug
  candidates: Map<string, ContentCandidate>
  selectedCandidateId?: string
  language: Language
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const stageTitles = {
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
  const finalPass = value.critic_passes.find((pass) => pass.pass_number === 3)
  const finalId = finalPass?.final_selection?.candidate_id || selectedCandidateId

  return <div className="decision-trace">
    <section className="trace-intro">
      <small>{tr('FIVE INITIAL DIRECTIONS', 'П’ЯТЬ ПОЧАТКОВИХ НАПРЯМІВ')}</small>
      <h3>{tr('Every image and its exact generation parameters', 'Кожне зображення та точні параметри його створення')}</h3>
      <p>{tr(
        'Pass 1 scores shown below. Hard gates are checked before the weighted score can count.',
        'Нижче показані оцінки етапу 1. Обов’язкові перевірки виконуються до врахування зваженої оцінки.',
      )}</p>
    </section>
    <section className="candidate-grid">
      {initialCandidates.map((candidate) => <CandidateCard
        key={candidate.candidate_id}
        api={api}
        candidate={candidate}
        pass={firstPass}
        selectedCandidateId={finalId}
        language={language}
      />)}
    </section>

    <section className="trace-intro decision-intro">
      <small>{tr('DECISION PATH', 'ШЛЯХ РІШЕННЯ')}</small>
      <h3>{tr('How five directions became one final post', 'Як п’ять напрямів стали одним фінальним дописом')}</h3>
      <p>{tr(
        'The system first rejects hard-gate failures, then ranks eligible work by weighted score, compares the strongest directions head-to-head, improves bounded elements, and rechecks the final two.',
        'Система спочатку відхиляє роботи, що не пройшли обов’язкові перевірки, потім ранжує придатні варіанти за зваженою оцінкою, попарно порівнює найсильніші напрями, точково покращує елементи й повторно перевіряє фінальні два.',
      )}</p>
    </section>
    <section className="decision-flow">
      {value.critic_passes.map((pass, index) => <div className="decision-flow-step" key={pass.pass_id}>
        <DecisionStage pass={pass} candidates={byId} selectedCandidateId={finalId} language={language} />
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
  </div>
}
