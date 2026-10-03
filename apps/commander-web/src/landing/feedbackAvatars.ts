import portrait1 from '../../../../validation_pipeline/studio_assets/template-assets/bokko_review_portrait_1.png'
import portrait2 from '../../../../validation_pipeline/studio_assets/template-assets/bokko_review_portrait_2.png'
import portrait3 from '../../../../validation_pipeline/studio_assets/template-assets/bokko_review_portrait_3.png'
import portrait4 from '../../../../validation_pipeline/studio_assets/template-assets/bokko_review_portrait_4.png'
import portrait5 from '../../../../validation_pipeline/studio_assets/template-assets/bokko_review_portrait_5.png'

export const feedbackAvatars = [
  { id: 'bokko_review_portrait_1', src: portrait1 },
  { id: 'bokko_review_portrait_2', src: portrait2 },
  { id: 'bokko_review_portrait_3', src: portrait3 },
  { id: 'bokko_review_portrait_4', src: portrait4 },
  { id: 'bokko_review_portrait_5', src: portrait5 },
] as const

export function feedbackAvatarUrl(id?: string): string | undefined {
  return feedbackAvatars.find(avatar => avatar.id === id)?.src
}
