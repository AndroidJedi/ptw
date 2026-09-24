import emailIcon from '../../../../validation_pipeline/studio_assets/app-showcase/email.svg'
import phoneIcon from '../../../../validation_pipeline/studio_assets/app-showcase/phone.svg'
import telegramIcon from '../../../../validation_pipeline/studio_assets/app-showcase/telegram.svg'
import instagramIcon from '../../../../validation_pipeline/studio_assets/app-showcase/instagram.svg'
import threadsIcon from '../../../../validation_pipeline/studio_assets/app-showcase/threads-icon.svg'
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { ArrowLeft, ArrowRight, ArrowUpRight, Check } from 'lucide-react'
import type { LandingPageProps } from './LandingPage'
import type { Section } from './model'
import { contactHref } from './model'
import { marketingContentDefaults } from './marketing'
import logo from '../../../../natal/assets/logo-natal.png'
import symbol from '../../../../validation_pipeline/studio_assets/app-showcase/natal-symbol.png'
import apple from '../../../../validation_pipeline/studio_assets/app-showcase/apple.svg'
import google from '../../../../validation_pipeline/studio_assets/app-showcase/google.svg'
import office from '../../../../validation_pipeline/studio_assets/app-showcase/office.svg'
import user from '../../../../validation_pipeline/studio_assets/app-showcase/user.svg'
import safe from '../../../../validation_pipeline/studio_assets/app-showcase/safe.svg'
import review from '../../../../validation_pipeline/studio_assets/app-showcase/review.svg'
import comment from '../../../../validation_pipeline/studio_assets/app-showcase/comment.svg'
import requirements from '../../../../validation_pipeline/studio_assets/app-showcase/requirements.svg'
import employment from '../../../../validation_pipeline/studio_assets/app-showcase/employment.svg'
import support from '../../../../validation_pipeline/studio_assets/app-showcase/support.svg'
import line from '../../../../validation_pipeline/studio_assets/app-showcase/line-decor.svg'
import iryna from '../../../../validation_pipeline/studio_assets/app-showcase/iryna.png'
import mykyta from '../../../../validation_pipeline/studio_assets/app-showcase/mykyta.png'
import maryna from '../../../../validation_pipeline/studio_assets/app-showcase/maryna.png'
import star from '../../../../validation_pipeline/studio_assets/app-showcase/star.svg'
import './marketing.css'

export function NatalMark({ small = false }: { small?: boolean }) {
  return <span role={small ? undefined : 'img'} aria-label={small ? undefined : 'Natal'} aria-hidden={small || undefined} className={small ? 'mk-symbol' : 'mk-logo'} style={{ maskImage: `url("${small ? symbol : logo}")`, WebkitMaskImage: `url("${small ? symbol : logo}")` }} />
}
export function NatalMotifs({ enabled }: { enabled?: boolean }) {
  return enabled ? <div className="mk-motifs" aria-hidden="true">{Array.from({ length: 8 }, (_, i) => <span key={i} style={{ '--i': i } as CSSProperties}><NatalMark small /></span>)}</div> : null
}
type Props = LandingPageProps & { part: 'carousel' | 'comparison' | 'walkthrough' | 'benefits' | 'reviews' | 'values' | 'cta' | 'footer'; contactId: string }
export function StoreButtons({ configuration: c, content: v, editing, onSelect, contactId, onAnalyticsEvent }: Omit<Props, 'part'>) {
  const m = c.marketing; const copy = v.marketing || marketingContentDefaults
  if (!m?.downloads_enabled) return null
  const uk = c.presentation?.language !== 'en'
  return <div className="mk-stores">{(['apple', 'google'] as const).map(store => {
    const url = copy[`${store}_url`]
    if (!url && m.missing_store_target === 'hide') return null
    return <a key={store} className="mk-store" href={url || `#${contactId}`} aria-label={`${store === 'apple' ? 'App Store' : 'Google Play'} · ${copy.store_label || v.hero.cta_label}`} {...(url ? { target: '_blank', rel: 'noopener noreferrer' } : {})} onClick={event => {
      if (editing) { event.preventDefault(); onSelect?.('downloads'); return }
      if (!url) { event.preventDefault(); document.getElementById(contactId)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); document.getElementById(contactId)?.focus({ preventScroll: true }); onAnalyticsEvent?.('primary_cta_click', 'hero', 'contacts') }
    }}><img src={store === 'apple' ? apple : google} alt="" />{copy.store_label || (url ? (uk ? 'Завантажити додаток' : 'Download the app') : v.hero.cta_label)}</a>
  })}</div>
}
const references = [
  { name: 'Ірина, Дніпро', image: iryna, text: 'Спершу сумнівалася, але подруга порадила спробувати. Розмістила квартиру безкоштовно, і вже наступного дня отримала 4 відгуки. Дуже круто, що не треба платити жодної копійки за розміщення.' },
  { name: 'Микита, Івано-Франківськ', image: mykyta, text: 'Мені сподобалось, що все через телефон - не треба сидіти на дзвінках. Просто завантажив фото квартири, вказав умови й отримав повідомлення. Все просто і прозоро.' },
  { name: 'Марина, Одеса', image: maryna, text: 'Здаю квартиру в Одесі. Завжди було напружено: агенти, дзвінки, покази. У застосунку сама призначаю зустріч, бачу профіль орендаря, можу відмовити. Це зручно та безпечно.' },
]
export function MarketingSections(props: Props) {
  const { configuration: c, content: v, imageUrls, editing, showDraftHints, onSelect, selected, part, contactId } = props
  const m = c.marketing, copy = v.marketing || marketingContentDefaults, uk = c.presentation?.language !== 'en'
  const policies = [
    { key: 'privacy', url: copy.privacy_url, label: uk ? 'Політика конфіденційності' : 'Privacy policy' },
    { key: 'terms', url: copy.terms_url, label: uk ? 'Публічна оферта' : 'Terms of service' },
  ]
  const rail = useRef<HTMLDivElement>(null)
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    if (part !== 'carousel' || !m?.carousel_enabled || !m.carousel_autoplay || paused || editing || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const timer = window.setInterval(() => {
      const el = rail.current; if (!el) return
      el.scrollTo({ left: el.scrollLeft + el.clientWidth >= el.scrollWidth - 5 ? 0 : el.scrollLeft + (el.firstElementChild?.getBoundingClientRect().width || 300) + 28, behavior: 'smooth' })
    }, m.carousel_speed * 1000)
    return () => clearInterval(timer)
  }, [part, m?.carousel_enabled, m?.carousel_autoplay, m?.carousel_speed, paused, editing])
  if (!m) return null
  const missing = (value: string, index?: number) => value || ((editing || showDraftHints) ? `${uk ? 'Заповніть вручну в Landing Studio' : 'Complete manually in Landing Studio'}${index === undefined ? '' : ` · ${index + 1}`}` : '—')
  const section = (key: Section, body: ReactNode, className = '') => <section data-section={key} className={`mk-section mk-section-${part} ${className} ${editing && selected === key ? 'as-selected' : ''}`} onClickCapture={event => { if (editing) { event.preventDefault(); event.stopPropagation(); onSelect?.(key) } }}>{body}</section>
  if (part === 'carousel' && m.carousel_enabled) return section('features', <><p className="mk-intro">{copy.introduction || v.hero.supporting_text}</p><div className="mk-rail" ref={rail} tabIndex={0} aria-label={uk ? 'Можливості застосунку' : 'App benefits'} onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>{v.features.map((f, i) => <article className="mk-notch-card" key={i}><span className="mk-card-arrow"><ArrowUpRight /></span><span className="mk-icon" style={{ maskImage: `url("${[office, user, safe][i]}")`, WebkitMaskImage: `url("${[office, user, safe][i]}")` }} /><h3>{f.title}</h3><p>{f.description}</p></article>)}</div><div className="mk-rail-controls"><button aria-label={uk ? 'Попередня картка' : 'Previous card'} onClick={() => rail.current?.scrollBy({ left: -360, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })}><ArrowLeft /></button><button aria-label={uk ? 'Наступна картка' : 'Next card'} onClick={() => rail.current?.scrollBy({ left: 360, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })}><ArrowRight /></button><button aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? (uk ? 'Продовжити' : 'Play') : (uk ? 'Пауза' : 'Pause')}</button></div><StoreButtons {...props} /></>)
  if (part === 'comparison' && m.comparison_enabled) return section('comparison', <><h2 className="mk-gradient-title">{copy.comparison_heading || (uk ? 'Що змінюється з Natal' : 'What changes with Natal')}</h2><div className="mk-comparison"><div className="mk-comparison-head"><span /><strong>{uk ? 'З Natal' : 'With Natal'}</strong></div>{copy.comparison_rows.map((item, i) => item.enabled && <div className={`mk-comparison-row ${!item.text ? 'mk-missing' : ''}`} key={i}><strong>{missing(item.text, i)}</strong><span>{item.text ? <Check aria-label={uk ? 'Так' : 'Yes'} /> : '—'}</span></div>)}</div></>)
  if (part === 'walkthrough' && m.walkthrough_enabled) return section('walkthrough', <><NatalMotifs enabled={m.motifs_enabled} /><h2>{copy.walkthrough_heading || (uk ? 'Як це працює?' : 'How does it work?')}</h2><div className="mk-how-grid"><ol>{copy.walkthrough_steps.map((s, i) => s.enabled && <li key={i}><span>{i + 1}</span><div><h3>{missing(s.title, i)}</h3><p>{s.description}</p></div></li>)}</ol><div className="mk-mockup">{imageUrls.walkthrough_visual ? <img src={imageUrls.walkthrough_visual} alt={copy.walkthrough_heading} loading="lazy" /> : editing && <p>{uk ? 'Створіть композицію мокапів у Landing Studio → Як це працює' : 'Generate the mockup composition in Landing Studio → How it works'}</p>}</div></div><StoreButtons {...props} /></>, 'mk-gradient-panel')
  if (part === 'benefits' && m.benefits_enabled) return section('visual_break', <><h2 className="mk-gradient-title">{copy.benefits_heading}</h2><div className="mk-benefits-grid">{imageUrls.visual_break_visual && <img src={imageUrls.visual_break_visual} alt="" loading="lazy" style={{ objectPosition: `${c.presentation?.visual_break_focus.x ?? 50}% ${c.presentation?.visual_break_focus.y ?? 50}%` }} />}<div><h3>{copy.benefits_supporting}</h3><article><img className="mk-icon mk-review-icon" src={review} alt="" /><h3>{copy.benefit_highlight_title}</h3><p>{copy.benefit_highlight_text}</p></article></div></div></>)
  if (part === 'reviews' && m.reference_reviews_enabled) return section('social_proof', <><h2 className="mk-gradient-title">{uk ? 'Приклад оформлення відгуків' : 'Sample review layout'}</h2><p className="mk-reference-note">{uk ? 'Демонстраційний вміст для макета. Це не відгуки клієнтів Natal.' : 'Demonstration content for the layout. These are not Natal customer reviews.'}</p><div className="mk-reviews">{references.map(r => <blockquote key={r.name}><header><img src={r.image} alt="" /><div><strong>{r.name}</strong><span className="mk-stars" aria-label="5 / 5">{Array.from({ length: 5 }, (_, i) => <img key={i} src={star} alt="" />)}</span></div></header><p>{r.text}</p></blockquote>)}</div></>)
  if (part === 'values' && m.benefits_enabled) return section('values', <div className="mk-values">{copy.values.map((value, i) => value.enabled && <article key={i}><span className="mk-icon" style={{ maskImage: `url("${[comment, requirements, employment, support][i]}")`, WebkitMaskImage: `url("${[comment, requirements, employment, support][i]}")` }} /><h3>{missing(value.title, i)}</h3><p>{value.description}</p></article>)}</div>)
  if (part === 'cta' && m.cta_enabled) return section('cta', <><NatalMotifs enabled={m.motifs_enabled} /><h2>{copy.cta_heading || v.contacts.heading}</h2><p>{copy.cta_text || v.contacts.supporting_text}</p><img className="mk-line" src={line} alt="" /><StoreButtons {...props} /></>, 'mk-gradient-panel')
  if (part === 'footer' && m.footer_enabled) return <footer id={contactId} data-section="contacts" tabIndex={-1} className="mk-footer" onClickCapture={e => { if (editing) { e.preventDefault(); e.stopPropagation(); onSelect?.('contacts') } }}>
    <div><NatalMark /><div className="mk-legal" aria-label={uk ? 'Правові документи' : 'Policies'}>{policies.map(policy => policy.url
      ? <a key={policy.key} href={policy.url}>{policy.label}</a>
      : <span key={policy.key} className="mk-policy-pending">{policy.label}</span>
    )}</div></div>
    <div><h3>{v.contacts.heading}</h3>{(['phone', 'email'] as const).map(k => {
      const value = v.contacts[k] || ''; const link = contactHref(k, value)
      return link && <a className="mk-contact-link" key={k} href={link} onClick={() => { if (!editing) props.onAnalyticsEvent?.('contact_click', k, k) }}><img src={k === 'email' ? emailIcon : phoneIcon} alt="" /><span>{value}</span></a>
    })}<div className="mk-socials">{([{ name: 'Telegram', image: telegramIcon, key: 'url' }, { name: 'Instagram', image: instagramIcon, key: 'instagram' }, { name: 'Threads', image: threadsIcon, key: null }] as const).map(social => {
      const href = social.key ? contactHref(social.key, v.contacts[social.key] || '') : ''
      const icon = <img src={social.image} alt={social.name} />
      return href ? <a key={social.name} href={href} target="_blank" rel="noopener noreferrer" onClick={() => { if (!editing) props.onAnalyticsEvent?.('contact_click', social.key === 'url' ? 'telegram' : 'instagram', social.key === 'url' ? 'telegram' : 'instagram') }}>{icon}</a> : <span key={social.name}>{icon}</span>
    })}</div></div>
    <div><h3>{uk ? 'Почніть тут' : 'Start here'}</h3><StoreButtons {...props} /></div>
  </footer>
  return null
}
