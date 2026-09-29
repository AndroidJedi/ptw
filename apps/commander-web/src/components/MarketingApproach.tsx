import { useId } from 'react'
import type { Language } from '../i18n'
import type { MarketingApproach, ProductBriefDocument } from '../types'

export function approachLabel(value: MarketingApproach, language: Language) {
  return value === 'identity_led' ? (language === 'uk' ? 'Через ідентичність' : 'Identity-led') : (language === 'uk' ? 'Через практичну користь' : 'Benefit-led')
}

export function MarketingApproachSelect({ value, onChange, language, disabled = false, replacement = false }: {
  value: MarketingApproach; onChange: (value: MarketingApproach) => void; language: Language; disabled?: boolean; replacement?: boolean
}) {
  const id = useId()
  const label = replacement ? (language === 'uk' ? 'Маркетинговий підхід для заміни' : 'Marketing approach for replacement') : (language === 'uk' ? 'Маркетинговий підхід' : 'Marketing approach')
  return <div className="marketing-approach-select"><label htmlFor={id}>{label}</label><select id={id} value={value} disabled={disabled} aria-describedby={`${id}-help`} onChange={event => onChange(event.target.value as MarketingApproach)}>
    <option value="benefit_led">{approachLabel('benefit_led', language)}</option><option value="identity_led">{approachLabel('identity_led', language)}</option>
  </select><p id={`${id}-help`}>{value === 'identity_led'
    ? (language === 'uk' ? 'Бажане відчуття себе, конкретна суперечність і реальна користь продукту.' : 'Desired self-image, a specific customer tension, and real functional value.')
    : (language === 'uk' ? 'Проблема клієнта, практичний результат і зрозуміла пропозиція.' : 'The customer’s problem, practical outcome, and a clear offer.')}</p></div>
}

export function MarketingApproachBadge({ value = 'benefit_led', language }: { value?: MarketingApproach; language: Language }) {
  return <p className="marketing-approach-badge">{language === 'uk' ? 'Підхід із брифу' : 'Approach from Brief'}: <strong>{approachLabel(value, language)}</strong></p>
}

export function BriefContent({ value, language }: { value: ProductBriefDocument; language: Language }) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const positioning = value.positioning
  return <div className="brief-document">
    <MarketingApproachBadge value={positioning?.marketing_approach} language={language} />
    <section><small>{tr('POSITIONING HYPOTHESIS', 'ГІПОТЕЗА ПОЗИЦІОНУВАННЯ')}</small><h2>{value.promise}</h2><p>{value.product}</p></section>
    <section><dl><dt>{tr('First customer', 'Перший клієнт')}</dt><dd>{value.target_audience}</dd><dt>{tr('Main pain', 'Головний біль')}</dt><dd>{value.main_pain}</dd><dt>CTA</dt><dd>{value.cta}</dd></dl></section>
    {positioning && <section aria-label={tr('Positioning', 'Позиціонування')}><small>{tr('POSITIONING', 'ПОЗИЦІОНУВАННЯ')}</small><dl>
      {positioning.desired_identity && <><dt>{tr('Desired identity', 'Бажане відчуття себе')}</dt><dd>{positioning.desired_identity}</dd></>}
      <dt>{tr('Customer tension', 'Суперечність клієнта')}</dt><dd>{positioning.customer_tension}</dd>
      <dt>{tr('Category framing', 'Контекст продукту')}</dt><dd>{positioning.category_frame}</dd>
      <dt>{tr('Functional value', 'Практична користь')}</dt><dd>{positioning.functional_value}</dd>
    </dl></section>}
    <section><small>{tr('STRONG VALIDATION OFFER', 'СИЛЬНА ВАЛІДАЦІЙНА ПРОПОЗИЦІЯ')}</small><h2>{value.offer}</h2><p>{value.trust_strategy}</p></section>
    <section><small>{tr('KEY BENEFITS', 'КЛЮЧОВІ ПЕРЕВАГИ')}</small><ul>{value.key_benefits.map(item => <li key={item}>{item}</li>)}</ul></section>
  </div>
}
