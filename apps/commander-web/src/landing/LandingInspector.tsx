import { ImagePlus, RefreshCcw, Trash2 } from 'lucide-react'
import { useId, type CSSProperties } from 'react'
import type { LandingAppFeature, LandingPhoneMockup, LandingComponents, LandingConfiguration, LandingContent, LandingDetail, LandingPresentation } from '../types'
import { PhoneHeroDirectionPicker, styles as imageStyles, backgrounds as imageBackgrounds } from '../components/studio/PhoneHeroDirectionPicker'
import { phoneDefaults, resolvedAppFeature, appFeatureLimits, defaults, componentDefaults, imageDirectionDefaults, type Issue, type Section } from './model'

type Props = {
  section: Section; configuration: LandingConfiguration; content: LandingContent; detail: LandingDetail
  onConfiguration: (value: LandingConfiguration) => void; onContent: (value: LandingContent) => void
  language: 'en' | 'uk'; busy: boolean; issues: Issue[]; imageUrls: Record<string, string>
  onGenerate: (slot: 'hero_visual' | 'visual_break_visual', enhance?: boolean) => void
  onSelectImage: (slot: 'hero_visual' | 'visual_break_visual', sha: string) => void
}
export function LandingInspector({ section, configuration: c, content: v, detail, onConfiguration, onContent, language, busy, issues, imageUrls, onGenerate, onSelectImage }: Props) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  const phone = c.phone_mockup || phoneDefaults
  const feature = resolvedAppFeature(v, c.presentation?.language || 'uk')
  const setFeature = (patch: Partial<LandingAppFeature>) => onContent({ ...v, app_feature: { ...feature, ...patch } })
  const components = c.components || componentDefaults
  const directions = c.image_directions || imageDirectionDefaults
  const setComponent = <K extends keyof LandingComponents>(key: K, value: LandingComponents[K]) => onConfiguration({ ...c, components: { ...components, [key]: value } })
  const presentation = c.presentation || defaults
  const setP = <K extends keyof LandingPresentation>(key: K, value: LandingPresentation[K]) => onConfiguration({ ...c, presentation: { ...presentation, [key]: value } })
  const error = (path: string) => issues.find(i => i.path === path)?.[language]
  const field = (label: string, value: string, max: number, onChange: (value: string) => void, path?: string, multiline = false) => <LandingField label={label} value={value} max={max} onChange={onChange} error={path ? error(path) : undefined} multiline={multiline} />
  const select = (label: string, value: string, options: Array<[string, string]>, onChange: (value: string) => void) => <label className="landing-field"><span>{label}</span><select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>{options.map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>
  const range = (label: string, value: number, min: number, max: number, step: number, onChange: (value: number) => void) => <label className="landing-field"><span>{label}<small aria-hidden="true">{value}</small></span><input aria-label={label} type="range" min={min} max={max} step={step} value={value} onChange={event => onChange(Number(event.target.value))} /></label>
  const layout = (section: 'features' | 'social_proof' | 'faq', field: 'layout' | 'style', value: string) => onConfiguration({ ...c, [section]: { [field]: value } } as LandingConfiguration)
  const alignment = (key: 'hero' | 'contacts') => select(tr('Text alignment', 'Вирівнювання тексту'), c[key].alignment, [['left', tr('Left', 'Ліворуч')], ['center', tr('Centered', 'По центру')]], value => onConfiguration({ ...c, [key]: { ...c[key], alignment: value } } as LandingConfiguration))
  const componentSelect = (key: keyof LandingComponents, label: string, options: Array<[string, string]>) => select(label, components[key], options, value => setComponent(key, value as LandingComponents[typeof key]))
  const buttonControls = () => <div className="landing-repeater">
    <h3>{tr('Button appearance', 'Вигляд кнопки')}</h3>
    {componentSelect('button_style', tr('Button style', 'Стиль кнопки'), [['filled', tr('Filled', 'Заливка')], ['outlined', tr('Outlined', 'Контур')], ['elevated', tr('Elevated', 'Тінь')], ['text', tr('Text only', 'Лише текст')]])}
    {componentSelect('button_shape', tr('Button shape', 'Форма кнопки'), [['square', tr('Square', 'Прямокутна')], ['rounded', tr('Rounded', 'Заокруглена')], ['pill', tr('Pill', 'Капсула')]])}
    {(['button_color', 'button_text_color'] as const).map(key => <label className="landing-field landing-color-field" key={key}><span>{key === 'button_color' ? tr('Button color', 'Колір кнопки') : tr('Button text color', 'Колір тексту кнопки')}</span><input aria-label={key === 'button_color' ? tr('Button color', 'Колір кнопки') : tr('Button text color', 'Колір тексту кнопки')} type="color" value={components[key]} onChange={event => setComponent(key, event.target.value)} /><code>{components[key]}</code></label>)}
    <p className="landing-field-hint">{tr('Outlined and text buttons use the button color for their text.', 'Контурна й текстова кнопки використовують колір кнопки для тексту.')}</p>
  </div>
  const cardControls = () => componentSelect('card_style', tr('Card style', 'Стиль карток'), [['filled', tr('Filled', 'Заливка')], ['outlined', tr('Outlined', 'Контур')], ['elevated', tr('Elevated', 'Тінь')], ['minimal', tr('Minimal', 'Мінімальний')]])
  const visuals = (slot: 'hero_visual' | 'visual_break_visual') => {
    const hero = slot === 'hero_visual'; const focusKey = hero ? 'hero_focus' : 'visual_break_focus'
    const asset = detail.assets.find(a => a.slot === slot)
    const direction = hero ? v.hero.visual_direction : v.visual_break.visual_direction
    return <div className="landing-image-editor">
      {imageUrls[slot] && <img className="landing-current-image" src={imageUrls[slot]} alt={tr('Selected artwork', 'Обране зображення')} />}
      <details className="landing-direction-picker"><summary>{tr('Image style & background', 'Стиль зображення та фон')}<small>{imageStyles.find(item => item.id === directions[slot].style)?.[language]} · {imageBackgrounds.find(item => item.id === directions[slot].background)?.[language]}</small></summary>
        <PhoneHeroDirectionPicker language={language} idPrefix={`landing-${slot}`} value={directions[slot]} disabled={busy} onChange={value => { if (value.style && value.background) onConfiguration({ ...c, image_directions: { ...directions, [slot]: { style: value.style, background: value.background } } }) }} />
      </details>
      <p className="landing-field-hint">{tr('The selected style is saved with this image slot and used by Generate and Enhance. Existing artwork changes only after generation.', 'Обраний стиль зберігається для цієї секції та використовується для створення й покращення. Поточне зображення зміниться лише після генерації.')}</p>
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
      <p className="landing-field-hint">{tr('All apps use the canonical Natal logo and name. Themes style the page components.', 'Усі застосунки використовують канонічний логотип і назву Natal. Теми змінюють вигляд компонентів сторінки.')}</p>
      <div className="landing-theme-presets" aria-label={tr('Page themes', 'Теми сторінки')}>
        {detail.catalog.theme_presets?.map(preset => <button key={preset.id} className="landing-theme-preset" aria-pressed={Object.entries(preset.theme).every(([key, value]) => c.theme[key as keyof typeof c.theme] === value) && Object.entries(preset.components).every(([key, value]) => components[key as keyof typeof components] === value) && c.faq.style === preset.faq.style} onClick={() => onConfiguration({ ...c, theme: { ...preset.theme }, components: { ...preset.components }, faq: { ...preset.faq } })}>
          <span className="landing-theme-sample" style={{ '--sample-bg': preset.theme.background_color, '--sample-ink': preset.theme.text_color, '--sample-accent': preset.components.button_color, '--sample-radius': `${preset.theme.corner_radius / 2}px`, fontFamily: `"Landing ${preset.theme.heading_font_family}"` } as CSSProperties}><b>Aa</b><i /><i /><i /><em /></span>
          <strong>{preset[language]}</strong><small>{language === 'uk' ? preset.description_uk : preset.description_en}</small>
        </button>)}
      </div>
      <p className="landing-field-hint">{tr('A theme sets colors, fonts, buttons, cards, icons and FAQ styling. Fine-tune each section below.', 'Тема задає кольори, шрифти, кнопки, картки, іконки та FAQ. Кожну секцію можна налаштувати окремо.')}</p>
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
      {buttonControls()}
      {alignment('hero')}
      {select(tr('Image placement', 'Розташування зображення'), c.hero.image_position, [['right', tr('Right', 'Праворуч')], ['left', tr('Left', 'Ліворуч')], ['below', tr('Below', 'Знизу')]], value => onConfiguration({ ...c, hero: { ...c.hero, image_position: value as LandingConfiguration['hero']['image_position'] } }))}
      {visuals('hero_visual')}
    </>}
    {section === 'app_feature' && <>
      <p className="landing-field-hint">{tr('Show the task people use your app for. Edit the screen directly; its artwork style is controlled in Hero. This is an interface preview, and its action uses the page CTA destination.', 'Покажіть завдання, яке люди виконують у застосунку. Редагуйте екран; стиль зображення задається в першому екрані. Це прев’ю інтерфейсу, його кнопка використовує адресу головної дії сторінки.')}</p>
      <div className="landing-phone-themes" aria-label={tr('App screen themes', 'Теми екрана застосунку')}>{(['light', 'dark', 'glass'] as const).map((theme, i) => <button className={`landing-phone-theme landing-phone-theme-${theme}`} key={theme} aria-pressed={phone.theme === theme} onClick={() => onConfiguration({ ...c, phone_mockup: { ...phone, theme } })}><span aria-hidden="true"><i /><i /><i /></span><strong>{[tr('Light', 'Світла'), tr('Dark', 'Темна'), tr('Glass', 'Скло')][i]}</strong></button>)}</div>
      {select(tr('Feature screen layout', 'Макет функції'), phone.layout, [['overview', tr('Overview', 'Огляд')], ['booking', tr('Booking', 'Бронювання')], ['checklist', tr('Checklist', 'Список')]], value => onConfiguration({ ...c, phone_mockup: { ...phone, layout: value as LandingPhoneMockup['layout'] } }))}
      {field(tr('Key feature title', 'Назва ключової функції'), feature.title, appFeatureLimits.title, value => setFeature({ title: value }), 'app_feature.title')}
      {field(tr('Feature screen description', 'Опис функції на екрані'), feature.description, appFeatureLimits.description, value => setFeature({ description: value }), 'app_feature.description', true)}
      {field(tr('App action label', 'Текст дії в застосунку'), feature.action_label, appFeatureLimits.action_label, value => setFeature({ action_label: value }), 'app_feature.action_label')}
      {feature.items.map((item, index) => <div className="landing-repeater" key={index}><h3>{tr('Screen row', 'Рядок екрана')} {index + 1}</h3>{field(tr('Row label', 'Назва рядка'), item.label, appFeatureLimits.label, value => setFeature({ items: feature.items.map((row, i) => i === index ? { ...row, label: value } : row) }), `app_feature.items.${index}.label`)}{field(tr('Row detail (optional)', 'Деталі рядка (необов’язково)'), item.value, appFeatureLimits.value, value => setFeature({ items: feature.items.map((row, i) => i === index ? { ...row, value } : row) }), `app_feature.items.${index}.value`)}</div>)}
    </>}
    {section === 'features' && <>
      {cardControls()}
      {componentSelect('icon_style', tr('Icon style', 'Стиль іконок'), [['soft', tr('Soft', 'М’який')], ['solid', tr('Solid', 'Суцільний')], ['line', tr('Line', 'Лінійний')], ['hidden', tr('Hidden', 'Прихований')]])}
      {select(tr('Feature layout', 'Вигляд переваг'), c.features.layout, [['three_columns', tr('Three cards', 'Три картки')], ['stacked', tr('Stacked rows', 'Рядки')]], value => layout('features', 'layout', value))}
      {v.features.map((item, index) => <div className="landing-repeater" key={index}><h3>{tr('Feature', 'Перевага')} {index + 1}</h3>{field(tr('Title', 'Назва'), item.title, 90, value => onContent({ ...v, features: v.features.map((f, i) => i === index ? { ...f, title: value } : f) }), `features.${index}.title`)}{field(tr('Description', 'Опис'), item.description, 300, value => onContent({ ...v, features: v.features.map((f, i) => i === index ? { ...f, description: value } : f) }), `features.${index}.description`, true)}</div>)}
    </>}
    {section === 'social_proof' && <>
      {cardControls()}
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
      {componentSelect('contact_style', tr('Panel style', 'Стиль панелі'), [['contrast', tr('Contrast', 'Контрастний')], ['surface', tr('Light surface', 'Світла поверхня')], ['accent', tr('Accent', 'Акцентний')]])}
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
