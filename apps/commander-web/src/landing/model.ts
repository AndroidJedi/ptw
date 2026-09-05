import type { LandingConfiguration, LandingContent, LandingPresentation, LandingVisualSummary } from '../types'

export type Section = 'theme' | 'hero' | 'features' | 'social_proof' | 'visual_break' | 'contacts' | 'faq'
export const sections: Section[] = ['theme', 'hero', 'features', 'social_proof', 'visual_break', 'contacts', 'faq']
export const defaults: LandingPresentation = {
  language: 'uk', cta_target: 'contacts', heading_scale: 1, spacing: 'comfortable',
  hero_focus: { x: 50, y: 50 }, visual_break_focus: { x: 50, y: 50 },
}
export const labels = {
  en: { theme: 'Page design', hero: 'Hero', features: 'Features', social_proof: 'Evidence', visual_break: 'Visual story', contacts: 'Get in touch', faq: 'Questions', explore: 'Discover the details', contact: 'Get in touch', visit: 'Open website', email: 'Email us', phone: 'Call us', top: 'Back to top', private: 'Private preview' },
  uk: { theme: 'Дизайн сторінки', hero: 'Перший екран', features: 'Можливості', social_proof: 'Досвід користувачів', visual_break: 'Візуальна історія', contacts: 'Зв’язатися', faq: 'Запитання', explore: 'Дізнатися більше', contact: 'Зв’язатися', visit: 'Відкрити сайт', email: 'Написати нам', phone: 'Зателефонувати', top: 'На початок', private: 'Приватне прев’ю' },
}
export function validContact(field: 'email' | 'phone' | 'url', value: string) {
  if (field === 'email') return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
  if (field === 'phone') return /^\+?[0-9 ()-]+$/.test(value) && value.replace(/\D/g, '').length >= 3 && value.replace(/\D/g, '').length <= 15
  try { const url = new URL(value); return value.startsWith('https://') && Boolean(url.hostname) && !url.username && !url.password && !/[\s\\]/.test(value) } catch { return false }
}
export function contactHref(field: 'email' | 'phone' | 'url', value: string) {
  if (!validContact(field, value)) return undefined
  return field === 'email' ? `mailto:${value}` : field === 'phone' ? `tel:${value.replace(/[ ()-]/g, '')}` : value
}
export type Issue = { section: Section; path: string; en: string; uk: string }
export function landingIssues(configuration: LandingConfiguration, content: LandingContent, assets: LandingVisualSummary[]): Issue[] {
  const issues: Issue[] = []
  const required = (section: Section, path: string, value: string, en: string, uk: string) => {
    if (!value.trim()) issues.push({ section, path, en, uk })
  }
  required('hero', 'hero.title', content.hero.title, 'Add a headline', 'Додайте заголовок')
  required('hero', 'hero.supporting_text', content.hero.supporting_text, 'Add supporting copy', 'Додайте опис')
  required('hero', 'hero.cta_label', content.hero.cta_label, 'Add a button label', 'Додайте текст кнопки')
  content.features.forEach((v, i) => { required('features', `features.${i}.title`, v.title, `Feature ${i + 1}: add a title`, `Перевага ${i + 1}: додайте назву`); required('features', `features.${i}.description`, v.description, `Feature ${i + 1}: add a description`, `Перевага ${i + 1}: додайте опис`) })
  if (content.social_proof.items.length) required('social_proof', 'social_proof.heading', content.social_proof.heading, 'Add an evidence heading', 'Додайте заголовок доказів')
  content.social_proof.items.forEach((v, i) => { required('social_proof', `social_proof.${i}.statement`, v.statement, 'Complete or remove this evidence', 'Доповніть або видаліть цей доказ'); required('social_proof', `social_proof.${i}.attribution`, v.attribution, 'Name the evidence source', 'Вкажіть джерело доказу') })
  required('contacts', 'contacts.heading', content.contacts.heading, 'Add a contact heading', 'Додайте заголовок контактів')
  required('contacts', 'contacts.supporting_text', content.contacts.supporting_text, 'Explain the next step', 'Опишіть наступний крок')
  const fields = ['email', 'phone', 'url'] as const
  if (!fields.some(f => validContact(f, content.contacts[f]))) issues.push({ section: 'contacts', path: 'contacts.endpoint', en: 'Add an email, phone, or HTTPS destination', uk: 'Додайте email, телефон або HTTPS-адресу' })
  fields.forEach(f => { if (content.contacts[f] && !validContact(f, content.contacts[f])) issues.push({ section: 'contacts', path: `contacts.${f}`, en: `Check the ${f} destination`, uk: `Перевірте контакт: ${f}` }) })
  const target = configuration.presentation?.cta_target || 'contacts'
  if (target !== 'contacts' && !validContact(target, content.contacts[target])) issues.push({ section: 'hero', path: 'hero.cta_target', en: 'Configure the selected button destination in Contacts', uk: 'Налаштуйте обрану адресу кнопки в Контактах' })
  content.faq.forEach((v, i) => { required('faq', `faq.${i}.question`, v.question, `Question ${i + 1} is missing`, `Додайте запитання ${i + 1}`); required('faq', `faq.${i}.answer`, v.answer, `Answer ${i + 1} is missing`, `Додайте відповідь ${i + 1}`) })
  for (const [slot, section] of [['hero_visual', 'hero'], ['visual_break_visual', 'visual_break']] as const) if (!assets.some(a => a.slot === slot && a.available)) issues.push({ section, path: `${section}.visual`, en: 'Generate this section’s artwork', uk: 'Створіть зображення для цієї секції' })
  const bounded = (section: Section, path: string, value: string, max: number, min = 1) => {
    if (value.trim() && (value.length > max || value.trim().length < min)) issues.push({ section, path, en: `Use ${min}–${max} characters`, uk: `Введіть ${min}–${max} символів` })
  }
  bounded('hero', 'hero.title', content.hero.title, 140)
  bounded('hero', 'hero.supporting_text', content.hero.supporting_text, 360)
  bounded('hero', 'hero.cta_label', content.hero.cta_label, 60)
  bounded('hero', 'hero.visual_direction', content.hero.visual_direction, 600, 8)
  bounded('visual_break', 'visual_break.visual_direction', content.visual_break.visual_direction, 600, 8)
  content.features.forEach((v, i) => { bounded('features', `features.${i}.title`, v.title, 90); bounded('features', `features.${i}.description`, v.description, 300) })
  bounded('social_proof', 'social_proof.heading', content.social_proof.heading, 120)
  content.social_proof.items.forEach((v, i) => { bounded('social_proof', `social_proof.${i}.statement`, v.statement, 360); bounded('social_proof', `social_proof.${i}.attribution`, v.attribution, 120) })
  bounded('contacts', 'contacts.heading', content.contacts.heading, 120)
  bounded('contacts', 'contacts.supporting_text', content.contacts.supporting_text, 300)
  bounded('contacts', 'contacts.email', content.contacts.email, 254, 3)
  bounded('contacts', 'contacts.phone', content.contacts.phone, 60, 3)
  bounded('contacts', 'contacts.url', content.contacts.url, 2048, 8)
  content.faq.forEach((v, i) => { bounded('faq', `faq.${i}.question`, v.question, 180); bounded('faq', `faq.${i}.answer`, v.answer, 500) })
  return issues
}
