import { useEffect } from 'react'
import { LegalLinks, legalLabels, legalUrl, type LegalDocument, type LegalLanguage } from '../../../commander-web/src/landing/LegalLinks'
import natalLogo from '../../../../natal/assets/logo-natal.png'
import contacts from '../../../../validation_pipeline/studio_assets/natal-contacts.json'
import profile from './profile.json'
import { documents } from './documents'
import { usePrivacy } from '../privacyPreferences'
import './legal.css'

export function legalRoute(path: string): LegalDocument | null {
  const match = /^\/legal\/(terms|privacy|cookies)\/?$/.exec(path)
  return match ? match[1] as LegalDocument : null
}

export function legalProfileReady(value = profile): boolean {
  return value.reviewed && /^\d{4}-\d{2}-\d{2}$/.test(value.effectiveDate)
    && [value.operatorName, value.businessAddress, value.registrationDetails, value.country,
      value.retentionDisclosure.en, value.retentionDisclosure.uk, value.transferDisclosure.en,
      value.transferDisclosure.uk, value.representativeDisclosure.en, value.representativeDisclosure.uk].every(item => item.trim())
    && value.markets.length > 0
}

export function LegalPage({ document: kind, language }: { document: LegalDocument; language: LegalLanguage }) {
  const uk = language === 'uk', copy = documents[language][kind]
  const ready = legalProfileReady()
  const { show } = usePrivacy()
  const title = legalLabels[language][kind]
  useEffect(() => {
    document.title = `${title} — Natal`
    document.documentElement.lang = language
    document.querySelector('link[rel="canonical"]')?.remove()
    const canonical = document.createElement('link')
    canonical.rel = 'canonical'; canonical.href = legalUrl(kind, language)
    document.head.append(canonical)
    return () => canonical.remove()
  }, [kind, language, title])
  const unconfirmed = uk ? 'Потребує підтвердження оператора' : 'Awaiting operator confirmation'
  return <div className="natal-legal-page" lang={language}>
    <header className="natal-legal-header"><a href="/" aria-label="Natal"><img src={natalLogo} alt="Natal" /></a>
      <nav aria-label={uk ? 'Мова документа' : 'Document language'}><a href={legalUrl(kind, 'uk', '')} lang="uk" aria-current={uk ? 'page' : undefined}>Українська</a><a href={legalUrl(kind, 'en', '')} lang="en" aria-current={!uk ? 'page' : undefined}>English</a></nav>
    </header>
    <main className="natal-legal-main">
      <p className="natal-legal-eyebrow">Natal · {uk ? 'Правові документи' : 'Legal information'}</p>
      <h1>{title}</h1>
      <p className="natal-legal-version">{uk ? 'Редакція' : 'Revision'} {profile.revision} · {ready ? `${uk ? 'Чинна з' : 'Effective'} ${profile.effectiveDate}` : (uk ? 'Чернетка для перевірки' : 'Draft for review')}</p>
      {!ready && <aside className="natal-legal-draft" aria-label={uk ? 'Статус документа' : 'Document status'}><strong>{uk ? 'Документ ще не завершено' : 'This document is not final'}</strong><p>{uk
        ? 'Реквізити оператора, ринки, строки зберігання та міжнародні передачі ще потребують підтвердження й правової перевірки. Це базова чернетка для інформаційного сайту, а не готовий договір для кожного бізнесу. Вона не обмежує ваших законних прав.'
        : 'Operator details, markets, retention and international transfers still need confirmation and legal review. This is a baseline draft for an information website, not a completed contract for every business. It does not limit your legal rights.'}</p></aside>}
      <p className="natal-legal-intro">{copy.intro}</p>
      <nav className="natal-legal-contents" aria-label={uk ? 'Зміст' : 'Contents'}>{copy.sections.map((section, i) => <a key={section.title} href={`#section-${i + 1}`}>{i + 1}. {section.title}</a>)}<a href="#operator">{uk ? 'Оператор і контакти' : 'Operator and contact'}</a></nav>
      {copy.sections.map((section, i) => <section key={section.title} id={`section-${i + 1}`} tabIndex={-1}><h2>{i + 1}. {section.title}</h2>{section.paragraphs.map(text => <p key={text}>{text}</p>)}</section>)}
      <section id="operator" tabIndex={-1}><h2>{uk ? 'Оператор і контакти' : 'Operator and contact'}</h2>
        <dl>{[
          [uk ? 'Юридичне ім’я' : 'Legal name', profile.operatorName],
          [uk ? 'Ділова адреса' : 'Business address', profile.businessAddress],
          [uk ? 'Реєстраційні відомості' : 'Registration details', profile.registrationDetails],
          [uk ? 'Країна реєстрації' : 'Country of establishment', profile.country],
          [uk ? 'Ринки' : 'Markets', profile.markets.join(', ')],
        ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || unconfirmed}</dd></div>)}</dl>
        <p><a href={`mailto:${contacts.email}`}>{contacts.email}</a><br /><a href={`tel:${contacts.phone.replace(/[^+\d]/g, '')}`}>{contacts.phone}</a></p>
        <p>{uk ? 'Це наявні контакти Natal. Сам бренд і контактна адреса не замінюють повних реквізитів оператора.' : 'These are Natal’s existing contact channels. A brand and contact email do not replace the operator’s full legal identity.'}</p>
      </section>
      {kind === 'privacy' && <>
        <section><h2>{uk ? 'Підтверджені умови обробки' : 'Confirmed processing details'}</h2>{([
          [uk ? 'Зберігання' : 'Retention', profile.retentionDisclosure[language]],
          [uk ? 'Міжнародні передачі' : 'International transfers', profile.transferDisclosure[language]],
          [uk ? 'Представник і відповідальний за захист даних' : 'Representative and data protection contact', profile.representativeDisclosure[language]],
        ]).map(([label, value]) => <p key={label}><strong>{label}: </strong>{value || unconfirmed}</p>)}</section>
        <section><h2>{uk ? 'Органи захисту даних' : 'Data-protection authorities'}</h2><ul>
          <li><a href="https://ombudsman.gov.ua/">{uk ? 'Уповноважений Верховної Ради України з прав людини' : 'Ukrainian Parliament Commissioner for Human Rights'}</a></li>
          <li><a href="https://www.edpb.europa.eu/about-edpb/about-edpb/members_en">{uk ? 'Органи захисту даних ЄЕЗ' : 'EEA data-protection authorities'}</a></li>
          <li><a href="https://ico.org.uk/make-a-complaint/">Information Commissioner’s Office (UK)</a></li>
        </ul></section>
      </>}
      {kind !== 'terms' && <section><h2>{uk ? 'Керування приватністю' : 'Privacy controls'}</h2><button type="button" onClick={show}>{uk ? 'Налаштування cookie' : 'Cookie settings'}</button><p><a href="https://www.facebook.com/privacy/policy/">{uk ? 'Політика конфіденційності Meta' : 'Meta privacy policy'}</a> · <a href="https://www.facebook.com/privacy/policies/cookies/">{uk ? 'Політика cookie Meta' : 'Meta cookie policy'}</a></p></section>}
    </main>
    <footer className="natal-legal-footer"><LegalLinks language={language} origin="" /><a href="/">{uk ? 'До Natal' : 'Back to Natal'}</a></footer>
  </div>
}
