import type { LandingComponents, LandingImageDirections, LandingConfiguration, LandingContent, LandingPresentation, LandingVisualSummary } from '../types'

export type Section = 'comparison' | 'walkthrough' | 'values' | 'cta' | 'downloads' | 'app_screens' | 'app_screen_1' | 'app_screen_2' | 'app_screen_3' | 'theme' | 'hero' | 'app_feature' | 'features' | 'social_proof' | 'visual_break' | 'contacts' | 'faq'
export const sections: Section[] = ['theme', 'hero', 'app_feature', 'features', 'social_proof', 'visual_break', 'contacts', 'faq']
export const defaults: LandingPresentation = {
  language: 'uk', cta_target: 'contacts', heading_scale: 1, spacing: 'comfortable',
  hero_focus: { x: 50, y: 50 }, visual_break_focus: { x: 50, y: 50 },
}
export const labels = {
  en: { comparison: 'Comparison', walkthrough: 'How it works', values: 'Service benefits', cta: 'CTA panel', downloads: 'Store buttons & footer', app_screens: 'App walkthrough', app_screen_1: 'Screen 1', app_screen_2: 'Screen 2', app_screen_3: 'Screen 3', app_feature: 'App feature', theme: 'Page design', hero: 'Hero', features: 'Features', social_proof: 'Evidence', visual_break: 'Visual story', contacts: 'Get in touch', faq: 'Questions', explore: 'Discover the details', contact: 'Get in touch', visit: 'Open Telegram bot', instagram: 'Instagram', email: 'Email us', phone: 'Call us', top: 'Back to top', private: 'Private preview' },
  uk: { comparison: 'Порівняння', walkthrough: 'Як це працює', values: 'Переваги сервісу', cta: 'Панель CTA', downloads: 'Кнопки магазинів і футер', app_screens: 'Огляд застосунку', app_screen_1: 'Екран 1', app_screen_2: 'Екран 2', app_screen_3: 'Екран 3', app_feature: 'Функція застосунку', theme: 'Дизайн сторінки', hero: 'Перший екран', features: 'Можливості', social_proof: 'Досвід користувачів', visual_break: 'Візуальна історія', contacts: 'Зв’язатися', faq: 'Запитання', explore: 'Дізнатися більше', contact: 'Зв’язатися', visit: 'Відкрити Telegram-бота', instagram: 'Instagram', email: 'Написати нам', phone: 'Зателефонувати', top: 'На початок', private: 'Приватне прев’ю' },
}
export function telegramBotUsername(value: string) {
  try {
    const url = new URL(value)
    const username = url.pathname.startsWith('/') ? url.pathname.slice(1) : ''
    return url.protocol === 'https:' && url.hostname.toLowerCase() === 't.me' && !url.username && !url.password && !url.port
      && url.pathname === `/${username}` && !url.search && !url.hash
      && /^[A-Za-z0-9_]{2,29}bot$/i.test(username) ? username : null
  } catch { return null }
}
export function instagramUsername(value: string) {
  try {
    const url = new URL(value)
    const parts = url.pathname.split('/').filter(Boolean)
    const username = parts.length === 1 ? parts[0] : ''
    return url.protocol === 'https:' && ['instagram.com', 'www.instagram.com'].includes(url.hostname.toLowerCase())
      && !url.username && !url.password && !url.port && !url.search && !url.hash
      && [`/${username}`, `/${username}/`].includes(url.pathname)
      && /^[A-Za-z0-9._]{1,30}$/.test(username) ? username : null
  } catch { return null }
}
export function validContact(field: 'email' | 'phone' | 'url' | 'instagram', value: string) {
  if (field === 'email') return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
  if (field === 'phone') return /^\+?[0-9 ()-]+$/.test(value) && value.replace(/\D/g, '').length >= 3 && value.replace(/\D/g, '').length <= 15
  if (field === 'instagram') return instagramUsername(value) !== null
  return telegramBotUsername(value) !== null
}
export function contactHref(field: 'email' | 'phone' | 'url' | 'instagram', value: string) {
  if (!validContact(field, value)) return undefined
  return field === 'email' ? `mailto:${value}` : field === 'phone' ? `tel:${value.replace(/[ ()-]/g, '')}` : field === 'instagram' ? `https://www.instagram.com/${instagramUsername(value)}/` : `https://t.me/${telegramBotUsername(value)}`
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
  const contacts = { ...content.contacts, instagram: content.contacts.instagram || '' }
  const fields = ['email', 'phone', 'url', 'instagram'] as const
  if (!fields.some(f => validContact(f, contacts[f]))) issues.push({ section: 'contacts', path: 'contacts.endpoint', en: 'Add an email, phone, Telegram bot, or Instagram link', uk: 'Додайте email, телефон, посилання на Telegram-бота або Instagram' })
  fields.forEach(f => { if (contacts[f] && !validContact(f, contacts[f])) issues.push({ section: 'contacts', path: `contacts.${f}`, en: `Check the ${f} destination`, uk: `Перевірте контакт: ${f}` }) })
  const target = configuration.presentation?.cta_target || 'contacts'
  if (target !== 'contacts' && !validContact(target, content.contacts[target])) issues.push({ section: 'hero', path: 'hero.cta_target', en: 'Configure the selected button destination in Contacts', uk: 'Налаштуйте обрану адресу кнопки в Контактах' })
  content.faq.forEach((v, i) => { required('faq', `faq.${i}.question`, v.question, `Question ${i + 1} is missing`, `Додайте запитання ${i + 1}`); required('faq', `faq.${i}.answer`, v.answer, `Answer ${i + 1} is missing`, `Додайте відповідь ${i + 1}`) })
  for (const [slot, section] of (content.app_screens ? [['app_screen_1', 'app_screen_1'], ['app_screen_2', 'app_screen_2'], ['app_screen_3', 'app_screen_3'], ['visual_break_visual', 'visual_break']] : [['hero_visual', 'hero'], ['visual_break_visual', 'visual_break']]) as Array<[string, Section]>) if (!assets.some(a => a.slot === slot && a.available)) issues.push({ section, path: `${section}.visual`, en: 'Generate this section’s artwork', uk: 'Створіть зображення для цієї секції' })
  const marketing = configuration.marketing, extra = content.marketing
  if (marketing && extra) {
    for (const [flag, key, section, fields] of [
      ['comparison_enabled', 'comparison_rows', 'comparison', ['text']],
      ['walkthrough_enabled', 'walkthrough_steps', 'walkthrough', ['title', 'description']],
      ['benefits_enabled', 'values', 'values', ['title', 'description']],
    ] as const) if (marketing[flag]) extra[key].forEach((item, i) => {
      if (item.enabled && fields.some(field => !(item as unknown as Record<string, unknown>)[field])) issues.push({ section, path: `marketing.${key}.${i}`, en: `Complete or hide item ${i + 1}`, uk: `Заповніть або приховайте пункт ${i + 1}` })
    })
    if (marketing.walkthrough_enabled && !assets.some(a => a.slot === 'walkthrough_visual' && a.available)) issues.push({ section: 'walkthrough', path: 'marketing.walkthrough_visual', en: 'Generate the walkthrough mockup', uk: 'Створіть мокап огляду' })
  }
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
  if (content.app_feature) {
    const feature = content.app_feature
    for (const key of ['title', 'description', 'action_label'] as const) {
      required('app_feature', `app_feature.${key}`, feature[key], 'Complete the app feature', 'Заповніть функцію застосунку')
      bounded('app_feature', `app_feature.${key}`, feature[key], appFeatureLimits[key])
    }
    feature.items.forEach((item, index) => {
      required('app_feature', `app_feature.items.${index}.label`, item.label, 'Add a screen row label', 'Додайте назву рядка екрана')
      for (const key of ['label', 'value'] as const) bounded('app_feature', `app_feature.items.${index}.${key}`, item[key], appFeatureLimits[key])
    })
  }
  content.app_screens?.forEach((screen, index) => {
    const section = `app_screen_${index + 1}` as Section
    for (const [key, maximum] of [['title', 90], ['description', 300], ['visual_direction', 600]] as const) {
      required(section, `app_screens.${index}.${key}`, screen[key], 'Complete this app screen', 'Заповніть цей екран')
      bounded(section, `app_screens.${index}.${key}`, screen[key], maximum, key === 'visual_direction' ? 8 : 1)
    }
  })
  return issues
}

export const componentDefaults: LandingComponents = { button_style: 'filled', button_shape: 'rounded', button_color: '#1f55d9', button_text_color: '#ffffff', card_style: 'filled', icon_style: 'soft', contact_style: 'contrast' }
export const imageDirectionDefaults: LandingImageDirections = {
  hero_visual: { style: 'premium_editorial', background: 'scene' },
  visual_break_visual: { style: 'premium_editorial', background: 'scene' },
}

export const phoneDefaults = { theme: 'light', layout: 'overview' } as const
export const appFeatureLimits = { title: 72, description: 160, action_label: 36, label: 60, value: 80 }
export function resolvedAppFeature(content: LandingContent, language: 'uk' | 'en') {
  return content.app_feature || {
    title: content.features[0].title.slice(0, 72), description: content.features[0].description.slice(0, 160),
    action_label: language === 'uk' ? 'Дізнатися більше' : 'Explore the app',
    items: content.features.map(item => ({ label: item.title.slice(0, 60), value: '' })),
  }
}
