import { MarketingSections, NatalMark } from './MarketingSections'
import { marketingStyle } from './marketing'
import { AppShowcasePage } from './AppShowcasePage'
import { ArrowDown, ArrowRight, ArrowUpRight, Check, ChevronDown, Instagram, Layers, Pencil, ScanLine } from 'lucide-react'
import { useId, useRef, type CSSProperties, type ReactNode } from 'react'
import type { LandingConfiguration, LandingContent } from '../types'
import { contactHref, defaults, componentDefaults, instagramUsername, labels, telegramBotUsername, type Section } from './model'
import natalLogo from '../../../../natal/assets/logo-natal.png'
import { LandingPhone } from './LandingPhone'
import { phoneDefaults, resolvedAppFeature } from './model'
import './fonts.css'
import './landing.css'
import './showcase.css'

export type LandingPageProps = {
  configuration: LandingConfiguration; content: LandingContent; imageUrls: Record<string, string>
  showDraftHints?: boolean; editing?: boolean; selected?: Section; onSelect?: (section: Section) => void
  onAnalyticsEvent?: (eventType: 'primary_cta_click' | 'contact_click', surface: 'hero' | 'phone' | 'telegram' | 'instagram' | 'email', target: 'contacts' | 'telegram' | 'instagram' | 'email' | 'phone') => void
}
export function LandingPage(props: LandingPageProps) {
  return props.configuration.showcase ? <AppShowcasePage {...props} /> : <ProjectLandingPage {...props} />
}

function ProjectLandingPage({ configuration, content, imageUrls, showDraftHints, editing = false, selected, onSelect, onAnalyticsEvent }: LandingPageProps) {
  const id = useId().replace(/:/g, '')
  const root = useRef<HTMLElement>(null)
  const p = configuration.presentation || defaults
  const t = labels[p.language]
  const theme = configuration.theme
  const components = configuration.components || componentDefaults
  const serif = (name: string) => /Lora|Cormorant/.test(name) ? 'Georgia, serif' : 'system-ui, sans-serif'
  const style = {
    ...marketingStyle(configuration),
    '--lp-button': components.button_color, '--lp-button-text': components.button_text_color,
    '--lp-button-radius': { square: '0px', rounded: `${Math.min(theme.corner_radius, 16)}px`, pill: '999px' }[components.button_shape],
    '--lp-bg': theme.background_color, '--lp-surface': theme.surface_color, '--lp-text': theme.text_color,
    '--lp-accent': theme.accent_color, '--lp-radius': `${theme.corner_radius}px`,
    '--lp-font': `"Landing ${theme.font_family}", ${serif(theme.font_family)}`,
    '--lp-heading-font': `"Landing ${theme.heading_font_family}", ${serif(theme.heading_font_family)}`,
    '--lp-font-style': theme.font_family.includes('Italic') ? 'italic' : 'normal',
    '--lp-heading-style': theme.heading_font_family.includes('Italic') ? 'italic' : 'normal',
    '--lp-font-width': theme.font_family === 'Roboto Condensed' ? '75' : '100',
    '--lp-heading-width': theme.heading_font_family === 'Roboto Condensed' ? '75' : '100',
    '--lp-scale': p.heading_scale, '--lp-space': { compact: .75, comfortable: 1, airy: 1.2 }[p.spacing],
  } as CSSProperties
  const scroll = (section: string) => {
    const element = root.current?.querySelector<HTMLElement>(`[data-section="${section}"]`)
    element?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' })
    element?.focus({ preventScroll: true })
  }
  const anchor = (section: Section, text: string, className?: string, icon?: ReactNode) => <a className={className} href={`#${id}-${section}`} onClick={event => { event.preventDefault(); if (editing) onSelect?.(section); else scroll(section) }}>{text}{icon}</a>
  const target = p.cta_target
  const href = target === 'contacts' ? `#${id}-contacts` : contactHref(target, content.contacts[target])
  const contactTarget = target === 'url' ? 'telegram' : target
  const trackPrimary = (surface: 'hero' | 'phone') => {
    if (!href) return
    onAnalyticsEvent?.('primary_cta_click', surface, contactTarget)
    if (contactTarget !== 'contacts') onAnalyticsEvent?.('contact_click', contactTarget, contactTarget)
  }
  const cta = (className = '') => <a className={`lp-cta ${className}`} href={href} aria-disabled={!href || undefined} onClick={event => {
    if (editing) { event.preventDefault(); onSelect?.('hero') }
    else if (target === 'contacts') { trackPrimary('hero'); event.preventDefault(); scroll('contacts') }
    else if (!href) event.preventDefault()
    else trackPrimary('hero')
  }} {...(target === 'url' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>{content.hero.cta_label || t.contact}<ArrowUpRight aria-hidden="true" /></a>
  const section = (key: Exclude<Section, 'theme'>, className: string, children: ReactNode) => <section id={`${id}-${key}`} data-section={key} tabIndex={-1} className={`lp-section ${className} ${editing && selected === key ? 'lp-selected' : ''}`} onClickCapture={event => {
    if (editing) { event.preventDefault(); event.stopPropagation(); onSelect?.((event.target as HTMLElement).closest('[data-phone-editor]') ? 'app_feature' : key) }
  }}>{editing && <button className="lp-edit-section" onClick={() => onSelect?.(key)} aria-label={`${p.language === 'uk' ? 'Редагувати' : 'Edit'}: ${t[key]}`}><Pencil aria-hidden="true" />{t[key]}</button>}{children}</section>
  const extra = (part: Parameters<typeof MarketingSections>[0]['part']) => <MarketingSections showDraftHints={showDraftHints} configuration={configuration} content={content} imageUrls={imageUrls} editing={editing} selected={selected} onSelect={onSelect} onAnalyticsEvent={onAnalyticsEvent} contactId={`${id}-contacts`} part={part} />
  const proof = content.social_proof.items.filter(item => item.statement.trim() && item.attribution.trim())
  const featureIcons = [ScanLine, Layers, Check]
  return <div className="lp-container"><article ref={root} className={`lp-page lp-button-${components.button_style} lp-card-${components.card_style} lp-icon-${components.icon_style} lp-panel-${components.contact_style} ${editing ? 'lp-editing' : ''}`} style={style} lang={p.language} aria-label="Landing live preview">
    <div className="lp-inner">
      <nav className="lp-nav" aria-label={p.language === 'uk' ? 'Навігація сторінки' : 'Page navigation'}>
        <a className="lp-brand" href={`#${id}-hero`} aria-label="Natal" onClick={event => { event.preventDefault(); if (editing) onSelect?.('theme'); else scroll('hero') }}>{configuration.marketing ? <NatalMark /> : <img src={natalLogo} alt="Natal" />}</a>
        <div>{anchor('features', t.features)}{anchor('faq', t.faq)}{anchor('contacts', t.contact, 'lp-nav-contact', <ArrowUpRight aria-hidden="true" />)}</div>
      </nav>
      {section('hero', `lp-hero lp-image-${configuration.hero.image_position} lp-align-${configuration.hero.alignment}`, <>
        <div className="lp-hero-copy"><h1>{content.hero.title}</h1><p>{content.hero.supporting_text}</p><div className="lp-hero-actions">{cta()}{anchor('features', t.explore, 'lp-secondary-link', <ArrowDown aria-hidden="true" />)}</div></div>
        <div className="lp-hero-art">{imageUrls.hero_visual && <img src={imageUrls.hero_visual} alt="" style={{ objectPosition: `${p.hero_focus.x}% ${p.hero_focus.y}%` }} />}{configuration.visual_mode !== 'image' && <LandingPhone feature={resolvedAppFeature(content, p.language)} appearance={configuration.phone_mockup || phoneDefaults} language={p.language} editing={editing} selected={selected === 'app_feature'} onSelect={() => onSelect?.('app_feature')} actionHref={href} external={target === 'url'} onAction={event => { if (editing) return; if (target === 'contacts') { trackPrimary('phone'); event.preventDefault(); scroll('contacts') } else if (!href) event.preventDefault(); else trackPrimary('phone') }} />}</div>
      </>)}
      {configuration.marketing?.carousel_enabled ? extra('carousel') : section('features', `lp-features lp-features-${configuration.features.layout}`, <><div className="lp-section-heading"><span className="lp-eyebrow">01 / {t.features}</span><h2>{t.features}</h2></div><div className="lp-feature-grid">{content.features.map((feature, index) => { const Icon = featureIcons[index]; return <article key={index}><span className="lp-feature-icon"><Icon aria-hidden="true" /></span><h3>{feature.title}</h3><p>{feature.description}</p></article> })}</div></>)}
      {extra('comparison')}{extra('walkthrough')}
      {proof.length > 0 && section('social_proof', `lp-proof lp-proof-${configuration.social_proof.layout}`, <><h2>{content.social_proof.heading}</h2><div className="lp-proof-grid">{proof.map((item, index) => <blockquote key={index}><p>“{item.statement}”</p><footer>{item.attribution}</footer></blockquote>)}</div></>)}
      {configuration.marketing?.benefits_enabled ? extra('benefits') : section('visual_break', `lp-visual lp-visual-${configuration.visual_break.height}`, <div className="lp-visual-frame">{imageUrls.visual_break_visual && <img src={imageUrls.visual_break_visual} alt="" loading="lazy" style={{ objectPosition: `${p.visual_break_focus.x}% ${p.visual_break_focus.y}%` }} />}</div>)}
      {extra('reviews')}{extra('values')}{extra('cta')}
      {!configuration.marketing?.footer_enabled && section('contacts', `lp-contacts lp-align-${configuration.contacts.alignment}`, <div className="lp-contact-panel"><div><span className="lp-eyebrow">{t.contact}</span><h2>{content.contacts.heading}</h2><p>{content.contacts.supporting_text}</p></div><div className="lp-contact-links">{(['url', 'instagram', 'email', 'phone'] as const).map(field => {
        const value = content.contacts[field] || ''; const link = contactHref(field, value)
        const analyticsTarget = field === 'url' ? 'telegram' : field
        return link && <a key={field} href={link} onClick={() => { if (!editing) onAnalyticsEvent?.('contact_click', analyticsTarget, analyticsTarget) }} {...(field === 'url' || field === 'instagram' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}><span><small>{field === 'url' ? t.visit : t[field]}</small>{field === 'url' ? `@${telegramBotUsername(value)}` : field === 'instagram' ? `@${instagramUsername(value)}` : value}</span>{field === 'instagram' ? <Instagram aria-hidden="true" /> : <ArrowUpRight aria-hidden="true" />}</a>
      })}</div></div>)}
      {section('faq', `lp-faq lp-faq-${configuration.faq.style}`, <><div className="lp-section-heading"><span className="lp-eyebrow">FAQ</span><h2>{t.faq}</h2></div><div>{content.faq.map((item, index) => <details key={index}><summary>{item.question}<ChevronDown aria-hidden="true" /></summary><p>{item.answer}</p></details>)}</div></>)}
      {extra('footer')}
      <footer className="lp-footer">{anchor('hero', t.top, undefined, <ArrowRight aria-hidden="true" />)}</footer>
    </div>
  </article></div>
}
