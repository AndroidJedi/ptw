import { ArrowDown, ArrowRight, ArrowUpRight, Check, ChevronDown, Layers, Pencil, ScanLine } from 'lucide-react'
import { useId, useRef, type CSSProperties, type ReactNode } from 'react'
import type { LandingConfiguration, LandingContent } from '../types'
import { contactHref, defaults, labels, type Section } from './model'
import './fonts.css'
import './landing.css'

export function LandingPage({ configuration, content, imageUrls, editing = false, selected, onSelect }: {
  configuration: LandingConfiguration; content: LandingContent; imageUrls: Record<string, string>
  editing?: boolean; selected?: Section; onSelect?: (section: Section) => void
}) {
  const id = useId().replace(/:/g, '')
  const root = useRef<HTMLElement>(null)
  const p = configuration.presentation || defaults
  const t = labels[p.language]
  const theme = configuration.theme
  const serif = (name: string) => /Lora|Cormorant/.test(name) ? 'Georgia, serif' : 'system-ui, sans-serif'
  const style = {
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
  const cta = (className = '') => <a className={`lp-cta ${className}`} href={href} aria-disabled={!href || undefined} onClick={event => {
    if (editing) { event.preventDefault(); onSelect?.('hero') }
    else if (target === 'contacts') { event.preventDefault(); scroll('contacts') }
    else if (!href) event.preventDefault()
  }} {...(target === 'url' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>{content.hero.cta_label || t.contact}<ArrowUpRight aria-hidden="true" /></a>
  const section = (key: Exclude<Section, 'theme'>, className: string, children: ReactNode) => <section id={`${id}-${key}`} data-section={key} tabIndex={-1} className={`lp-section ${className} ${editing && selected === key ? 'lp-selected' : ''}`} onClickCapture={event => {
    if (editing) { event.preventDefault(); event.stopPropagation(); onSelect?.(key) }
  }}>{editing && <button className="lp-edit-section" onClick={() => onSelect?.(key)} aria-label={`${p.language === 'uk' ? 'Редагувати' : 'Edit'}: ${t[key]}`}><Pencil aria-hidden="true" />{t[key]}</button>}{children}</section>
  const proof = content.social_proof.items.filter(item => item.statement.trim() && item.attribution.trim())
  const featureIcons = [ScanLine, Layers, Check]
  return <div className="lp-container"><article ref={root} className={`lp-page ${editing ? 'lp-editing' : ''}`} style={style} lang={p.language} aria-label="Landing live preview">
    <div className="lp-inner">
      <nav className="lp-nav" aria-label={p.language === 'uk' ? 'Навігація сторінки' : 'Page navigation'}>
        {anchor('hero', t.top, 'lp-top', <ArrowUpRight aria-hidden="true" />)}
        <div>{anchor('features', t.features)}{anchor('faq', t.faq)}{anchor('contacts', t.contact, 'lp-nav-contact', <ArrowUpRight aria-hidden="true" />)}</div>
      </nav>
      {section('hero', `lp-hero lp-image-${configuration.hero.image_position} lp-align-${configuration.hero.alignment}`, <>
        <div className="lp-hero-copy"><h1>{content.hero.title}</h1><p>{content.hero.supporting_text}</p><div className="lp-hero-actions">{cta()}{anchor('features', t.explore, 'lp-secondary-link', <ArrowDown aria-hidden="true" />)}</div></div>
        <div className="lp-hero-art">{imageUrls.hero_visual && <img src={imageUrls.hero_visual} alt="" style={{ objectPosition: `${p.hero_focus.x}% ${p.hero_focus.y}%` }} />}</div>
      </>)}
      {section('features', `lp-features lp-features-${configuration.features.layout}`, <><div className="lp-section-heading"><span className="lp-eyebrow">01 / {t.features}</span><h2>{t.features}</h2></div><div className="lp-feature-grid">{content.features.map((feature, index) => { const Icon = featureIcons[index]; return <article key={index}><span className="lp-feature-icon"><Icon aria-hidden="true" /></span><h3>{feature.title}</h3><p>{feature.description}</p></article> })}</div></>)}
      {proof.length > 0 && section('social_proof', `lp-proof lp-proof-${configuration.social_proof.layout}`, <><h2>{content.social_proof.heading}</h2><div className="lp-proof-grid">{proof.map((item, index) => <blockquote key={index}><p>“{item.statement}”</p><footer>{item.attribution}</footer></blockquote>)}</div></>)}
      {section('visual_break', `lp-visual lp-visual-${configuration.visual_break.height}`, <div className="lp-visual-frame">{imageUrls.visual_break_visual && <img src={imageUrls.visual_break_visual} alt="" loading="lazy" style={{ objectPosition: `${p.visual_break_focus.x}% ${p.visual_break_focus.y}%` }} />}</div>)}
      {section('contacts', `lp-contacts lp-align-${configuration.contacts.alignment}`, <div className="lp-contact-panel"><div><span className="lp-eyebrow">{t.contact}</span><h2>{content.contacts.heading}</h2><p>{content.contacts.supporting_text}</p></div><div className="lp-contact-links">{(['url', 'email', 'phone'] as const).map(field => {
        const value = content.contacts[field]; const link = contactHref(field, value)
        return link && <a key={field} href={link} {...(field === 'url' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}><span><small>{field === 'url' ? t.visit : t[field]}</small>{field === 'url' ? new URL(value).hostname : value}</span><ArrowUpRight aria-hidden="true" /></a>
      })}</div></div>)}
      {section('faq', `lp-faq lp-faq-${configuration.faq.style}`, <><div className="lp-section-heading"><span className="lp-eyebrow">FAQ</span><h2>{t.faq}</h2></div><div>{content.faq.map((item, index) => <details key={index}><summary>{item.question}<ChevronDown aria-hidden="true" /></summary><p>{item.answer}</p></details>)}</div></>)}
      <footer className="lp-footer">{anchor('hero', t.top, undefined, <ArrowRight aria-hidden="true" />)}</footer>
    </div>
  </article></div>
}
