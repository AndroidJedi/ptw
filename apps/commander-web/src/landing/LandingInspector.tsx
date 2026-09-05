import { ImagePlus, RefreshCcw, Trash2 } from 'lucide-react'
import { useId } from 'react'
import type { LandingConfiguration, LandingContent, LandingDetail, LandingPresentation } from '../types'
import { defaults, type Issue, type Section } from './model'

type Props = {
  section: Section; configuration: LandingConfiguration; content: LandingContent; detail: LandingDetail
  onConfiguration: (value: LandingConfiguration) => void; onContent: (value: LandingContent) => void
  language: 'en' | 'uk'; busy: boolean; issues: Issue[]; imageUrls: Record<string, string>
  onGenerate: (slot: 'hero_visual' | 'visual_break_visual', enhance?: boolean) => void
  onSelectImage: (slot: 'hero_visual' | 'visual_break_visual', sha: string) => void
}
export function LandingInspector({ section, configuration: c, content: v, detail, onConfiguration, onContent, language, busy, issues, imageUrls, onGenerate, onSelectImage }: Props) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const presentation = c.presentation || defaults
  const setP = <K extends keyof LandingPresentation>(key: K, value: LandingPresentation[K]) => onConfiguration({ ...c, presentation: { ...presentation, [key]: value } })
  const error = (path: string) => issues.find(i => i.path === path)?.[language]
  const field = (label: string, value: string, max: number, onChange: (value: string) => void, path?: string, multiline = false) => <LandingField label={label} value={value} max={max} onChange={onChange} error={path ? error(path) : undefined} multiline={multiline} />
  const select = (label: string, value: string, options: Array<[string, string]>, onChange: (value: string) => void) => <label className="landing-field"><span>{label}</span><select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>{options.map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>
  const range = (label: string, value: number, min: number, max: number, step: number, onChange: (value: number) => void) => <label className="landing-field"><span>{label}<small aria-hidden="true">{value}</small></span><input aria-label={label} type="range" min={min} max={max} step={step} value={value} onChange={event => onChange(Number(event.target.value))} /></label>
  const layout = (section: 'features' | 'social_proof' | 'faq', field: 'layout' | 'style', value: string) => onConfiguration({ ...c, [section]: { [field]: value } } as LandingConfiguration)
  const alignment = (key: 'hero' | 'contacts') => select(tr('Text alignment', 'Вирівнювання тексту'), c[key].alignment, [['left', tr('Left', 'Ліворуч')], ['center', tr('Centered', 'По центру')]], value => onConfiguration({ ...c, [key]: { ...c[key], alignment: value } } as LandingConfiguration))
  const visuals = (slot: 'hero_visual' | 'visual_break_visual') => {
    const hero = slot === 'hero_visual'; const focusKey = hero ? 'hero_focus' : 'visual_break_focus'
    const asset = detail.assets.find(a => a.slot === slot)
    const direction = hero ? v.hero.visual_direction : v.visual_break.visual_direction
    return <div className="landing-image-editor">
      {imageUrls[slot] && <img className="landing-current-image" src={imageUrls[slot]} alt={tr('Selected artwork', 'Обране зображення')} />}
      {field(tr('Visual direction', 'Напрям зображення'), direction, 600, value => onContent(hero ? { ...v, hero: { ...v.hero, visual_direction: value } } : { ...v, visual_break: { visual_direction: value } }), undefined, true)}
      {direction.length > 0 && direction.trim().length < 8 && <p className="landing-field-error">{tr('Use at least 8 characters.', 'Введіть щонайменше 8 символів.')}</p>}
      <div className="landing-visual-actions"><button className="secondary" disabled={busy || !detail.image_generation_available || direction.trim().length < 8} onClick={() => onGenerate(slot)}><ImagePlus />{tr('Generate', 'Створити')}</button><button className="secondary" disabled={busy || !detail.image_generation_available || !asset?.available || direction.trim().length < 8} onClick={() => onGenerate(slot, true)}><RefreshCcw />{tr('Enhance', 'Покращити')}</button></div>
      {!detail.image_generation_available && <p className="landing-field-hint">{tr('Image generation is unavailable.', 'Генерація зображень недоступна.')}</p>}
      {asset && asset.history.length > 0 && <div className="landing-image-history" aria-label={tr('Image history', 'Історія зображень')}>{asset.history.map((item, index) => <button key={item.sha256} className={item.selected ? 'active' : ''} disabled={busy || item.selected} aria-label={`${tr('Select image', 'Обрати зображення')} ${index + 1}`} aria-pressed={item.selected} onClick={() => onSelectImage(slot, item.sha256)}>{imageUrls[item.sha256] && <img src={imageUrls[item.sha256]} alt="" />}<span>{item.selected ? tr('Selected', 'Обрано') : index + 1}</span></button>)}</div>}
      <h3>{tr('Crop focus', 'Центр кадрування')}</h3>
      {range(tr('Horizontal focus', 'Горизонтальний центр'), presentation[focusKey].x, 0, 100, 1, value => setP(focusKey, { ...presentation[focusKey], x: value }))}
      {range(tr('Vertical focus', 'Вертикальний центр'), presentation[focusKey].y, 0, 100, 1, value => setP(focusKey, { ...presentation[focusKey], y: value }))}
    </div>
  }
  return <fieldset className="landing-inspector-fields" disabled={busy}>
    {section === 'theme' && <>
      {select(tr('Page language', 'Мова сторінки'), presentation.language, [['uk', 'Українська'], ['en', 'English']], value => setP('language', value as 'uk' | 'en'))}
      <p className="landing-field-hint">{tr('Changes navigation and section labels. Your copy stays as written.', 'Змінює навігацію та назви секцій. Ваш текст зберігається.')}</p>
      {(['background_color', 'surface_color', 'text_color', 'accent_color'] as const).map((key, index) => <label className="landing-field landing-color-field" key={key}><span>{[tr('Background', 'Тло'), tr('Surface', 'Поверхня'), tr('Text', 'Текст'), tr('Accent', 'Акцент')][index]}</span><input aria-label={['Background color', 'Surface color', 'Text color', 'Accent color'][index]} type="color" value={c.theme[key]} onChange={event => onConfiguration({ ...c, theme: { ...c.theme, [key]: event.target.value } })} /><code>{c.theme[key]}</code></label>)}
      {(['heading_font_family', 'font_family'] as const).map((key, index) => <div key={key}>{select(index === 0 ? tr('Heading font', 'Шрифт заголовків') : tr('Body font', 'Шрифт тексту'), c.theme[key], detail.catalog.font_families.map(font => [font, font]), value => onConfiguration({ ...c, theme: { ...c.theme, [key]: value } }))}</div>)}
      {range(tr('Heading scale', 'Масштаб заголовків'), presentation.heading_scale, .85, 1.15, .05, value => setP('heading_scale', value))}
      {range(tr('Corner radius', 'Радіус кутів'), c.theme.corner_radius, 0, 48, 1, value => onConfiguration({ ...c, theme: { ...c.theme, corner_radius: value } }))}
      {select(tr('Section spacing', 'Відступи між секціями'), presentation.spacing, [['compact', tr('Compact', 'Компактні')], ['comfortable', tr('Comfortable', 'Збалансовані')], ['airy', tr('Airy', 'Просторі')]], value => setP('spacing', value as LandingPresentation['spacing']))}
    </>}
    {section === 'hero' && <>
      {field(tr('Hero title', 'Заголовок першого екрана'), v.hero.title, 140, value => onContent({ ...v, hero: { ...v.hero, title: value } }), 'hero.title', true)}
      {field(tr('Supporting text', 'Підтримувальний текст'), v.hero.supporting_text, 360, value => onContent({ ...v, hero: { ...v.hero, supporting_text: value } }), 'hero.supporting_text', true)}
      {field(tr('CTA label', 'Текст кнопки'), v.hero.cta_label, 60, value => onContent({ ...v, hero: { ...v.hero, cta_label: value } }), 'hero.cta_label')}
      <p className="landing-field-hint">{tr('Keep the button short. Put offer details in supporting copy.', 'Коротка дія на кнопці. Деталі пропозиції — в описі.')}</p>
      {select(tr('Button destination', 'Дія кнопки'), presentation.cta_target, [['contacts', tr('Contact section', 'Секція контактів')], ['url', tr('HTTPS / booking URL', 'HTTPS / запис на зустріч')], ['email', 'Email'], ['phone', tr('Phone', 'Телефон')]], value => setP('cta_target', value as LandingPresentation['cta_target']))}
      {error('hero.cta_target') && <p className="landing-field-error">{error('hero.cta_target')}</p>}
      {alignment('hero')}
      {select(tr('Image placement', 'Розташування зображення'), c.hero.image_position, [['right', tr('Right', 'Праворуч')], ['left', tr('Left', 'Ліворуч')], ['below', tr('Below', 'Знизу')]], value => onConfiguration({ ...c, hero: { ...c.hero, image_position: value as LandingConfiguration['hero']['image_position'] } }))}
      {visuals('hero_visual')}
    </>}
    {section === 'features' && <>
      {select(tr('Feature layout', 'Вигляд переваг'), c.features.layout, [['three_columns', tr('Three cards', 'Три картки')], ['stacked', tr('Stacked rows', 'Рядки')]], value => layout('features', 'layout', value))}
      {v.features.map((item, index) => <div className="landing-repeater" key={index}><h3>{tr('Feature', 'Перевага')} {index + 1}</h3>{field(tr('Title', 'Назва'), item.title, 90, value => onContent({ ...v, features: v.features.map((f, i) => i === index ? { ...f, title: value } : f) }), `features.${index}.title`)}{field(tr('Description', 'Опис'), item.description, 300, value => onContent({ ...v, features: v.features.map((f, i) => i === index ? { ...f, description: value } : f) }), `features.${index}.description`, true)}</div>)}
    </>}
    {section === 'social_proof' && <>
      <p className="landing-field-hint">{tr('Optional. Hidden from the page until you add real evidence.', 'Необов’язково. Секція прихована, доки ви не додасте справжні докази.')}</p>
      {field(tr('Evidence heading', 'Заголовок доказів'), v.social_proof.heading, 120, value => onContent({ ...v, social_proof: { ...v.social_proof, heading: value } }), 'social_proof.heading')}
      {select(tr('Evidence layout', 'Вигляд доказів'), c.social_proof.layout, [['cards', tr('Cards', 'Картки')], ['quote', tr('Wide quotes', 'Широкі цитати')]], value => layout('social_proof', 'layout', value))}
      {v.social_proof.items.map((item, index) => <div className="landing-repeater" key={index}>{field(tr('Evidence statement', 'Текст доказу'), item.statement, 360, value => onContent({ ...v, social_proof: { ...v.social_proof, items: v.social_proof.items.map((f, i) => i === index ? { ...f, statement: value } : f) } }), `social_proof.${index}.statement`, true)}{field(tr('Evidence source', 'Джерело доказу'), item.attribution, 120, value => onContent({ ...v, social_proof: { ...v.social_proof, items: v.social_proof.items.map((f, i) => i === index ? { ...f, attribution: value } : f) } }), `social_proof.${index}.attribution`)}<button className="secondary" onClick={() => onContent({ ...v, social_proof: { ...v.social_proof, items: v.social_proof.items.filter((_, i) => i !== index) } })}><Trash2 />{tr('Remove evidence', 'Видалити доказ')}</button></div>)}
      {v.social_proof.items.length < 3 && <button className="secondary" onClick={() => onContent({ ...v, social_proof: { ...v.social_proof, items: [...v.social_proof.items, { statement: '', attribution: '' }] } })}>{tr('Add owner evidence', 'Додати доказ власника')}</button>}
    </>}
    {section === 'visual_break' && <>
      {select(tr('Image height', 'Висота зображення'), c.visual_break.height, [['small', tr('Shallow', 'Низьке')], ['medium', tr('Balanced', 'Збалансоване')], ['large', tr('Tall', 'Високе')]], value => onConfiguration({ ...c, visual_break: { height: value as LandingConfiguration['visual_break']['height'] } }))}
      {visuals('visual_break_visual')}
    </>}
    {section === 'contacts' && <>
      {field(tr('Contact heading', 'Заголовок контактів'), v.contacts.heading, 120, value => onContent({ ...v, contacts: { ...v.contacts, heading: value } }), 'contacts.heading')}
      {field(tr('Next step', 'Наступний крок'), v.contacts.supporting_text, 300, value => onContent({ ...v, contacts: { ...v.contacts, supporting_text: value } }), 'contacts.supporting_text', true)}
      {(['url', 'email', 'phone'] as const).map(key => <div key={key}>{field(key === 'url' ? tr('HTTPS contact URL', 'HTTPS-адреса контакту') : key === 'email' ? 'Email' : tr('Phone', 'Телефон'), v.contacts[key], key === 'url' ? 2048 : key === 'email' ? 254 : 60, value => onContent({ ...v, contacts: { ...v.contacts, [key]: value } }), `contacts.${key}`)}</div>)}
      {error('contacts.endpoint') && <p className="landing-field-error">{error('contacts.endpoint')}</p>}
      {alignment('contacts')}
    </>}
    {section === 'faq' && <>
      {select(tr('FAQ style', 'Вигляд запитань'), c.faq.style, [['divided', tr('Dividers', 'Розділювачі')], ['cards', tr('Cards', 'Картки')]], value => layout('faq', 'style', value))}
      {v.faq.map((item, index) => <div className="landing-repeater" key={index}><h3>FAQ {index + 1}</h3>{field(tr('Question', 'Запитання'), item.question, 180, value => onContent({ ...v, faq: v.faq.map((f, i) => i === index ? { ...f, question: value } : f) }), `faq.${index}.question`)}{field(tr('Answer', 'Відповідь'), item.answer, 500, value => onContent({ ...v, faq: v.faq.map((f, i) => i === index ? { ...f, answer: value } : f) }), `faq.${index}.answer`, true)}</div>)}
    </>}
  </fieldset>
}

export function LandingField({ label, value, max, onChange, error, multiline = false }: { label: string; value: string; max: number; onChange: (value: string) => void; error?: string; multiline?: boolean }) {
  const id = useId()
  const props = { id, 'aria-label': label, value, maxLength: max, 'aria-invalid': Boolean(error || value.length > max), 'aria-describedby': error ? `${id}-error` : undefined, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.target.value) }
  return <div className="landing-field"><label htmlFor={id}><span>{label}<small>{value.length}/{max}</small></span></label>{multiline ? <textarea {...props} /> : <input {...props} />}{error && <p className="landing-field-error" id={`${id}-error`}>{error}</p>}</div>
}
