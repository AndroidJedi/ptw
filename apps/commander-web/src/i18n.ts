import type { I18n } from './types'

export type Language = 'uk' | 'en'

export function translate(language: Language, en: string, uk: string) {
  return language === 'uk' ? uk : en
}

export function local<T>(value: I18n<T> | T | null | undefined, language: Language): T | string {
  if (value && typeof value === 'object' && 'en' in value && 'uk' in value) return value[language]
  return value ?? ''
}
