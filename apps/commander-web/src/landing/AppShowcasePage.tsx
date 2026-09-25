import { LandingImage } from './LandingImage'
import { MarketingSections, NatalMark, NatalMotifs, StoreButtons } from './MarketingSections'
import { marketingStyle } from './marketing'
import { ArrowUpRight, Check, ChevronDown, Pencil } from 'lucide-react'
import { useId, useRef, type CSSProperties, type ReactNode } from 'react'
import type { LandingPageProps } from './LandingPage'
import type { Section } from './model'
import { componentDefaults, contactHref, defaults, labels } from './model'
import natalLogo from '../../../../natal/assets/logo-natal.png'
import phoneFrame from '../../../../validation_pipeline/studio_assets/landing-display-v1/iphone-15-pro-black.webp'
import office from '../../../../validation_pipeline/studio_assets/app-showcase/office.svg'
import message from '../../../../validation_pipeline/studio_assets/app-showcase/message.svg'
import time from '../../../../validation_pipeline/studio_assets/app-showcase/time.svg'
import arrow from '../../../../validation_pipeline/studio_assets/app-showcase/arrow.svg'

export function AppShowcasePage({ configuration: c, content: v, imageUrls, imageVariants, showDraftHints, editing = false, selected, onSelect, onAnalyticsEvent }: LandingPageProps) {
  const id = useId().replace(/:/g, '')
  const root = useRef<HTMLElement>(null)
  const p = c.presentation || defaults
  const t = labels[p.language]
  const uk = p.language === 'uk'
  const screens = v.app_screens || []
  const appearance = c.showcase!
  const components = c.components || componentDefaults
  const style = {
    ...marketingStyle(c),
    '--as-end': appearance.gradient_end, '--as-offset': `${appearance.screen_offset}px`, '--as-screen-scale': appearance.screen_scale,
    '--lp-bg': c.theme.background_color, '--lp-surface': c.theme.surface_color, '--lp-text': c.theme.text_color,
    '--lp-accent': c.theme.accent_color, '--lp-radius': `${c.theme.corner_radius}px`,
    '--lp-font': `"Landing ${c.theme.font_family}", sans-serif`, '--lp-heading-font': `"Landing ${c.theme.heading_font_family}", sans-serif`,
    '--lp-scale': p.heading_scale, '--lp-space': { compact: .75, comfortable: 1, airy: 1.2 }[p.spacing],
    '--lp-button': components.button_color, '--lp-button-text': components.button_text_color,
    '--lp-button-radius': { square: '0', rounded: '16px', pill: '999px' }[components.button_shape],
  } as CSSProperties
  const target = p.cta_target
  const href = target === 'contacts' ? `#${id}-contacts` : contactHref(target, v.contacts[target])
  const scroll = (section: string) => {
    const element = root.current?.querySelector<HTMLElement>(`[data-section="${section}"]`)
    element?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); element?.focus({ preventScroll: true })
  }
  const cta = () => <a className="lp-cta as-cta" href={href} aria-disabled={!href || undefined} {...(target === 'url' ? { target: '_blank', rel: 'noopener noreferrer' } : {})} onClick={event => {
    if (editing) { event.preventDefault(); onSelect?.('hero'); return }
    if (!href) { event.preventDefault(); return }
    const destination = target === 'url' ? 'telegram' : target
    onAnalyticsEvent?.('primary_cta_click', 'hero', destination)
    if (destination !== 'contacts') onAnalyticsEvent?.('contact_click', destination, destination)
    if (target === 'contacts') { event.preventDefault(); scroll('contacts') }
  }}>{v.hero.cta_label || t.contact}<ArrowUpRight aria-hidden="true" /></a>
  const section = (key: Exclude<Section, 'theme'>, className: string, children: ReactNode) => <section id={`${id}-${key}`} data-section={key} tabIndex={-1} className={`as-section ${className} ${editing && selected === key ? 'as-selected' : ''}`} onClickCapture={event => {
    if (editing) { event.preventDefault(); event.stopPropagation(); const screen = (event.target as HTMLElement).closest<HTMLElement>('[data-screen]')?.dataset.screen; onSelect?.(screen ? screen as Section : key) }
  }}>{editing && <button className="as-edit" onClick={() => onSelect?.(key)}><Pencil size={14} />{t[key]}</button>}{children}</section>
  const phone = (index: number, priority = false) => <div className="as-phone" data-screen={`app_screen_${index + 1}`}>
    <div className="as-screen">{imageUrls[`app_screen_${index + 1}`] && <LandingImage priority={priority} variants={imageVariants?.[`app_screen_${index + 1}`]} sizes="(max-width: 600px) 180px, 300px" src={imageUrls[`app_screen_${index + 1}`]} alt={screens[index]?.title || ''} />}</div>
    <img className="as-hardware" src={phoneFrame} alt="" aria-hidden="true" />
  </div>
  const marketingProps = { showDraftHints, configuration: c, content: v, imageUrls, imageVariants, editing, selected, onSelect, onAnalyticsEvent, contactId: `${id}-contacts` }
  const extra = (part: Parameters<typeof MarketingSections>[0]['part']) => <MarketingSections {...marketingProps} part={part} />
  const icons = [office, message, time]
  const proof = v.social_proof.items.filter(item => item.statement && item.attribution)
  return <div className="lp-container"><article ref={root} className={`lp-page as-page lp-button-${components.button_style} lp-card-${components.card_style} lp-icon-${components.icon_style} lp-panel-${components.contact_style}`} style={style} lang={p.language} aria-label="Landing live preview">
    <div className="as-hero-wrap"><NatalMotifs enabled={c.marketing?.motifs_enabled} />
      <nav className="as-nav">{c.marketing ? <NatalMark /> : <img src={natalLogo} alt="Natal" />}<a href={`#${id}-contacts`} onClick={event => { event.preventDefault(); if (editing) onSelect?.('contacts'); else scroll('contacts') }}>{t.contact}<ArrowUpRight size={16} /></a></nav>
      {section('hero', `as-hero as-image-${c.hero.image_position} as-align-${c.hero.alignment}`, <><div className="as-hero-copy"><span className="as-kicker">{uk ? 'Ваш простір. Ваші можливості.' : 'Your space. Your possibilities.'}</span><h1>{v.hero.title}</h1><p>{v.hero.supporting_text}</p>{c.marketing?.downloads_enabled ? <StoreButtons {...marketingProps} /> : cta()}</div><div className="as-hero-phones">{phone(0, true)}{phone(1, true)}</div></>)}
      <svg className="as-wave" viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0 42 Q350 -10 720 42 T1440 42 V90 H0Z" /></svg>
    </div>
    <div className="as-body">
      {c.marketing?.carousel_enabled ? extra('carousel') : section('features', `as-benefits as-features-${c.features.layout}`, <><h2>{t.features}</h2><div className="as-card-grid">{v.features.map((item, i) => <article key={i}><img className="as-icon" src={icons[i]} alt="" /><img className="as-arrow" src={arrow} alt="" /><h3>{item.title}</h3><p>{item.description}</p></article>)}</div><div className="as-checklist">{v.features.map((item, i) => <div key={i}><span>{item.title}</span><Check aria-hidden="true" /></div>)}</div></>)}
      {extra('comparison')}
      {extra('walkthrough')}
      {section('app_screens', 'as-walkthrough', <><h2>{uk ? 'Як це працює' : 'How it works'}</h2><div className="as-steps">{screens.map((item, i) => <div className="as-step" key={i} data-screen={`app_screen_${i + 1}`}><div className="as-step-copy"><span className="as-number">0{i + 1}</span><h3>{item.title}</h3><p>{item.description}</p></div>{phone(i)}</div>)}</div><p className="as-preview-label">{uk ? 'Прев’ю інтерфейсу' : 'Interface preview'}</p>{cta()}</>)}
      {c.marketing?.benefits_enabled ? extra('benefits') : section('visual_break', `as-photo as-photo-${c.visual_break.height}`, <>{imageUrls.visual_break_visual && <LandingImage variants={imageVariants?.visual_break_visual} sizes="(max-width: 900px) 100vw, 70vw" src={imageUrls.visual_break_visual} alt="" loading="lazy" style={{ objectPosition: `${p.visual_break_focus.x}% ${p.visual_break_focus.y}%` }} />}</>)}
      {proof.length > 0 && section('social_proof', `as-proof as-proof-${c.social_proof.layout}`, <><h2>{v.social_proof.heading}</h2><div className="as-card-grid">{proof.map((item, i) => <blockquote key={i}><p>{item.statement}</p><footer>{item.attribution}</footer></blockquote>)}</div></>)}
      {extra('reviews')}{extra('values')}{extra('cta')}
      {!c.marketing && <div className="as-banner"><h2>{v.contacts.heading}</h2><p>{v.contacts.supporting_text}</p>{cta()}</div>}
      {section('faq', `as-faq as-faq-${c.faq.style}`, <><h2>{t.faq}</h2>{v.faq.map((item, i) => <details key={i}><summary>{item.question}<ChevronDown size={20} /></summary><p>{item.answer}</p></details>)}</>)}
      {c.marketing?.footer_enabled ? extra('footer') : section('contacts', `as-contact as-align-${c.contacts.alignment}`, <><img src={natalLogo} alt="Natal" /><div><h2>{v.contacts.heading}</h2><p>{v.contacts.supporting_text}</p><div className="as-contact-links">{(['email', 'phone', 'url', 'instagram'] as const).map(field => {
        const value = v.contacts[field] || ''; const link = contactHref(field, value); const destination = field === 'url' ? 'telegram' : field
        return link && <a key={field} href={link} {...(['url', 'instagram'].includes(field) ? { target: '_blank', rel: 'noopener noreferrer' } : {})} onClick={() => { if (!editing) onAnalyticsEvent?.('contact_click', destination, destination) }}>{value}<ArrowUpRight size={18} /></a>
      })}</div></div></>)}
    </div>
  </article></div>
}
