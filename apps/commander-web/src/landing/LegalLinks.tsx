export type LegalDocument = 'terms' | 'privacy' | 'cookies'
export type LegalLanguage = 'en' | 'uk'

export const legalLabels: Record<LegalLanguage, Record<LegalDocument, string>> = {
  en: { terms: 'Terms & conditions', privacy: 'Privacy policy', cookies: 'Cookie policy' },
  uk: { terms: 'Умови користування', privacy: 'Політика конфіденційності', cookies: 'Політика cookie' },
}

export function legalUrl(document: LegalDocument, language: LegalLanguage, origin = 'https://natal-service.com') {
  return `${origin}/legal/${document}?lang=${language}`
}

/** Shared shell documents do not alter stored template or approved Landing content. */
export function LegalLinks({ language = 'uk', privacyUrl, termsUrl, origin, editing, onSelect, className = '' }: {
  language?: LegalLanguage; privacyUrl?: string; termsUrl?: string; origin?: string
  editing?: boolean; onSelect?: () => void; className?: string
}) {
  return <nav className={`natal-legal-links ${className}`} aria-label={language === 'uk' ? 'Правові документи' : 'Policies'}>
    {(['privacy', 'terms', 'cookies'] as const).map(document => <a key={document}
      href={(document === 'privacy' ? privacyUrl : document === 'terms' ? termsUrl : '') || legalUrl(document, language, origin)}
      onClick={event => { if (editing) { event.preventDefault(); onSelect?.() } }}
    >{legalLabels[language][document]}</a>)}
  </nav>
}
