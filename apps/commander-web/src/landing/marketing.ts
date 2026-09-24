import type { CSSProperties } from 'react'
import type { LandingConfiguration, LandingContent, LandingMarketingConfiguration, LandingMarketingContent } from '../types'
import data from './marketing-defaults.json'
export const gradients = data.gradients
export const marketingDefaults = data.configuration as LandingMarketingConfiguration
export const marketingContentDefaults = data.content as LandingMarketingContent
export function marketingStyle(c: LandingConfiguration): CSSProperties {
  const m = c.marketing
  const g = gradients.find(g => g.id === m?.gradient_id) || gradients[0]
  return { '--mk-start': g.start, '--mk-end': g.end, '--mk-gradient': `linear-gradient(110deg,${g.start},${g.end})`, '--mk-logo': m?.logo_color || '#ffffff', '--mk-opacity': m?.motif_opacity || .09 } as CSSProperties
}
export function initialMarketingContent(v: LandingContent, uk: boolean): LandingMarketingContent {
  const d = structuredClone(marketingContentDefaults)
  d.introduction = v.hero.supporting_text
  d.comparison_heading = uk ? 'Що змінюється з Natal' : 'What changes with Natal'
  d.comparison_rows = d.comparison_rows.map((r, i) => ({ ...r, text: v.features[i]?.title || '' }))
  d.walkthrough_heading = uk ? 'Як це працює?' : 'How does it work?'
  d.walkthrough_steps = d.walkthrough_steps.map((r, i) => ({ ...r, title: v.app_screens?.[i]?.title || '', description: v.app_screens?.[i]?.description || '' }))
  d.walkthrough_visual_direction = 'A cohesive composition of three staggered complete phone mockups showing the project’s app workflow, readable UI, current palette, clean background, generous safe margins.'
  d.benefits_heading = uk ? 'Більше можливостей щодня' : 'More possibilities every day'
  d.benefits_supporting = v.contacts.supporting_text
  d.benefit_highlight_title = v.features[0]?.title || ''
  d.benefit_highlight_text = v.features[0]?.description || ''
  d.values = d.values.map((r, i) => ({ ...r, title: v.features[i]?.title || '', description: v.features[i]?.description || '' }))
  d.cta_heading = v.contacts.heading; d.cta_text = v.contacts.supporting_text
  return d
}
