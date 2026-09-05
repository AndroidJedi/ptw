import type {
  StudioPhoneHeroBackground, StudioPhoneHeroCreativeDirection, StudioPhoneHeroStyle,
} from '../../types'
import { translate, type Language } from '../../i18n'
import { Pencil } from 'lucide-react'

export type PhoneHeroDirectionDraft = {
  style: StudioPhoneHeroStyle | ''
  background: StudioPhoneHeroBackground | ''
}

export const styles: Array<{ id: StudioPhoneHeroStyle; en: string; uk: string; detailEn: string; detailUk: string }> = [
  { id: 'business_professional', en: 'Business professional', uk: 'Діловий професійний', detailEn: 'Credible commercial still life', detailUk: 'Переконливий комерційний натюрморт' },
  { id: 'ultra_realistic_lifestyle', en: 'Ultra-realistic lifestyle', uk: 'Ультрареалістичний лайфстайл', detailEn: 'Natural, high-fidelity product scene', detailUk: 'Природна деталізована продуктова сцена' },
  { id: 'cinematic', en: 'Cinematic', uk: 'Кінематографічний', detailEn: 'Filmic light and depth', detailUk: 'Кінематографічне світло й глибина' },
  { id: 'premium_editorial', en: 'Premium editorial', uk: 'Преміальний редакційний', detailEn: 'Refined art direction', detailUk: 'Вишукана артдирекція' },
  { id: 'contemporary_3d', en: 'Contemporary 3D', uk: 'Сучасний 3D', detailEn: 'Tactile dimensional forms', detailUk: 'Тактильні об’ємні форми' },
  { id: 'minimal_sculptural', en: 'Minimal sculptural', uk: 'Мінімалістичний скульптурний', detailEn: 'Bold forms, generous space', detailUk: 'Виразні форми й багато простору' },
  { id: 'artistic_illustration', en: 'Artistic illustration', uk: 'Художня ілюстрація', detailEn: 'Expressive illustrated direction', detailUk: 'Виразна ілюстративна подача' },
  { id: 'playful_balloons', en: 'Playful balloons', uk: 'Грайливі кульки', detailEn: 'Inflated forms and optimistic colour', detailUk: 'Надуті форми й оптимістичний колір' },
  { id: 'tactile_handmade', en: 'Tactile handmade', uk: 'Тактильний handmade', detailEn: 'Paper, clay, textile, craft', detailUk: 'Папір, глина, текстиль, ручна робота' },
  { id: 'futuristic_tech', en: 'Futuristic tech', uk: 'Футуристичний техно', detailEn: 'Abstract luminous technology', detailUk: 'Абстрактна світлова технологічність' },
]

export const backgrounds: Array<{ id: StudioPhoneHeroBackground; en: string; uk: string; detailEn: string; detailUk: string }> = [
  { id: 'scene', en: 'Keep a scene background', uk: 'Залишити сценічний фон', detailEn: 'A contextual, uncluttered backdrop', detailUk: 'Контекстний, але чистий фон' },
  { id: 'isolated_key_element', en: 'Remove scene background', uk: 'Прибрати сценічний фон', detailEn: 'One object on a clean tonal field, never transparent', detailUk: 'Один об’єкт на чистому тональному полі, без прозорості' },
]

export const creativeDirectionFromDraft = (value: PhoneHeroDirectionDraft): StudioPhoneHeroCreativeDirection | null => (
  value.style && value.background
    ? { schema: 'ptw.studio.phone-hero-direction.v1', style: value.style, background: value.background }
    : null
)

export function PhoneHeroDirectionPicker({
  language, value, onChange, onReset, disabled = false, locked = false, idPrefix,
}: {
  language: Language
  value: PhoneHeroDirectionDraft
  onChange?: (value: PhoneHeroDirectionDraft) => void
  onReset?: () => void
  disabled?: boolean
  locked?: boolean
  idPrefix: string
}) {
  const tr = (en: string, uk: string) => translate(language, en, uk)
  const selectedStyle = styles.find((item) => item.id === value.style)
  const selectedBackground = backgrounds.find((item) => item.id === value.background)
  const pendingSelection = !value.style
    ? tr('Select an image style to continue.', 'Оберіть стиль зображення, щоб продовжити.')
    : !value.background
      ? tr('Now choose a background treatment to enable saving.', 'Тепер оберіть варіант фону, щоб увімкнути збереження.')
      : tr('Direction is ready to save.', 'Напрям готовий до збереження.')

  if (locked && selectedStyle && selectedBackground) return <section className="phone-hero-direction phone-hero-direction-locked" aria-label={tr('Selected image direction', 'Обраний напрям зображення')}>
    <small>{tr('SELECTED IMAGE DIRECTION', 'ОБРАНИЙ НАПРЯМ ЗОБРАЖЕННЯ')}</small>
    <strong>{language === 'uk' ? selectedStyle.uk : selectedStyle.en}</strong>
    <span>{language === 'uk' ? selectedBackground.uk : selectedBackground.en}</span>
    {onReset && <button
      className="icon-button phone-hero-direction-reset" type="button"
      aria-label={tr('Reset image direction', 'Скинути напрям зображення')}
      title={tr('Reset image direction', 'Скинути напрям зображення')}
      disabled={disabled} onClick={onReset}
    ><Pencil aria-hidden="true" /></button>}
  </section>

  return <section className="phone-hero-direction" aria-label={tr('Choose image direction', 'Оберіть напрям зображення')}>
    <div><small>{tr('IMAGE DIRECTION', 'НАПРЯМ ЗОБРАЖЕННЯ')}</small><strong>{tr('Choose image style', 'Оберіть стиль зображення')}</strong></div>
    <div className="phone-hero-style-grid" role="radiogroup" aria-label={tr('Image style', 'Стиль зображення')}>
      {styles.map((item) => <label key={item.id} className={`phone-hero-direction-option ${value.style === item.id ? 'is-selected' : ''}`}>
        <input type="radio" name={`${idPrefix}-style`} value={item.id} checked={value.style === item.id} disabled={disabled} onChange={() => onChange?.({ ...value, style: item.id })} />
        <strong>{language === 'uk' ? item.uk : item.en}</strong><small>{language === 'uk' ? item.detailUk : item.detailEn}</small>
      </label>)}
    </div>
    <div className="phone-hero-background-heading"><small>{tr('BACKGROUND TREATMENT', 'ВАРІАНТ ФОНУ')}</small><strong>{tr('Keep a scene or remove it', 'Залишити сцену або прибрати її')}</strong><span>{tr('Removing the scene keeps a solid clean tonal field; it does not create a transparent image.', 'Прибирання сцени залишає суцільне чисте тональне поле, а не прозоре зображення.')}</span></div>
    <div className="phone-hero-background-options" role="radiogroup" aria-label={tr('Background treatment', 'Обробка фону')}>
      {backgrounds.map((item) => <label key={item.id} className={`phone-hero-direction-option ${value.background === item.id ? 'is-selected' : ''}`}>
        <input type="radio" name={`${idPrefix}-background`} value={item.id} checked={value.background === item.id} disabled={disabled} onChange={() => onChange?.({ ...value, background: item.id })} />
        <strong>{language === 'uk' ? item.uk : item.en}</strong><small>{language === 'uk' ? item.detailUk : item.detailEn}</small>
      </label>)}
    </div>
    <p className={`phone-hero-direction-progress ${selectedStyle && selectedBackground ? 'is-ready' : ''}`} aria-live="polite">{pendingSelection}</p>
  </section>
}
