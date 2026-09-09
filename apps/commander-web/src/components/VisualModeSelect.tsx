import type { Language } from '../i18n'

export function VisualModeSelect({ value = 'phone', onChange, language, disabled = false }: {
  value?: 'phone' | 'image'
  onChange: (value: 'phone' | 'image') => void
  language: Language
  disabled?: boolean
}) {
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  return <label className="landing-field">
    <span>{tr('Visual mode', 'Режим зображення')}</span>
    <select value={value} disabled={disabled} onChange={event => onChange(event.target.value as 'phone' | 'image')}>
      <option value="phone">{tr('Phone frame & buttons', 'Рамка телефону та кнопки')}</option>
      <option value="image">{tr('Image only', 'Лише зображення')}</option>
    </select>
  </label>
}
