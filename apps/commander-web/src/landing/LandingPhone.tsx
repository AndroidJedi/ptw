import { ArrowUpRight, BatteryFull, CalendarDays, Check, ChevronRight, LayoutGrid, Signal, Wifi } from 'lucide-react'
import { useState, type CSSProperties, type MouseEventHandler } from 'react'
import type { LandingAppFeature, LandingPhoneMockup } from '../types'
import phoneFrame from '../../../../validation_pipeline/studio_assets/iphone-15-pro-black.png'
import './phone.css'

/** Same fixed front-facing hardware as Post Studio; app UI stays editable HTML. */
export function LandingPhone({ feature, appearance, language, editing, selected, onSelect, onAction, actionHref, external }: {
  feature: LandingAppFeature; appearance: LandingPhoneMockup; language: 'uk' | 'en'
  editing: boolean; selected: boolean; onSelect: () => void; onAction: MouseEventHandler<HTMLAnchorElement>; actionHref?: string; external: boolean
}) {
  const [active, setActive] = useState<number[]>([])
  const uk = language === 'uk'
  return <div data-phone-editor data-section="app_feature" className={`lp-phone-stage ${editing && selected ? 'lp-phone-selected' : ''}`}>
    {editing && <button className="lp-phone-edit" onClick={onSelect}>{uk ? 'Редагувати екран' : 'Edit app screen'}</button>}
    <div className={`lp-phone lp-phone-${appearance.theme} lp-phone-${appearance.layout}`} aria-label={uk ? 'Прев’ю застосунку Natal' : 'Natal app preview'}>
      <div className="lp-phone-screen">
        <div className="lp-phone-status" aria-hidden="true"><span>9:41</span><span><Signal /><Wifi /><BatteryFull /></span></div>
        <div className="lp-phone-scroll" tabIndex={0} role="region" aria-label={uk ? 'Екран ключової функції' : 'Key feature screen'}>
          <div className="lp-phone-brand"><strong>Natal</strong><span>{uk ? 'Застосунок' : 'Your app'}</span></div>
          <div className="lp-phone-intro"><h2>{feature.title}</h2><p>{feature.description}</p></div>
          <div className="lp-phone-rows" aria-label={uk ? 'Можливості екрана' : 'Screen options'}>{feature.items.map((item, index) => <button key={index} className="lp-phone-row" aria-pressed={active.includes(index)} onClick={() => {
            if (editing) { onSelect(); return }
            setActive(previous => appearance.layout === 'checklist' ? previous.includes(index) ? previous.filter(i => i !== index) : [...previous, index] : [index])
          }}><span className="lp-phone-row-icon" aria-hidden="true">{appearance.layout === 'booking' ? <CalendarDays /> : appearance.layout === 'checklist' ? active.includes(index) ? <Check /> : <span className="lp-phone-checkbox" /> : <LayoutGrid />}</span><span><strong>{item.label}</strong>{item.value && <small>{item.value}</small>}</span><ChevronRight className="lp-phone-chevron" aria-hidden="true" /></button>)}</div>
        </div>
        <div className="lp-phone-bottom"><a className="lp-phone-action" href={actionHref} aria-disabled={!actionHref || undefined} {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})} onClick={event => { if (editing) { event.preventDefault(); onSelect() } else onAction(event) }}>{feature.action_label}<ArrowUpRight aria-hidden="true" /></a><small>{uk ? 'Прев’ю інтерфейсу' : 'Interface preview'}</small></div>
        <div className="lp-phone-home" aria-hidden="true" />
      </div>
      <div className="lp-phone-hardware" style={{ backgroundImage: `url(${phoneFrame})` } as CSSProperties} aria-hidden="true" />
    </div>
  </div>
}
