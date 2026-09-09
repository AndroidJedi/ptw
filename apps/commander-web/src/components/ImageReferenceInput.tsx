import { useEffect, useId, useRef, useState } from 'react'
import './ImageReferenceInput.css'

export type ImageReference = { mime_type: string; bytes_base64: string }
const maxBytes = 8 * 1024 * 1024

export async function imageReferencePayload(file: File): Promise<ImageReference> {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || !file.size || file.size > maxBytes) {
    throw new Error('Use a PNG, JPEG, or WebP image up to 8 MB.')
  }
  const bytes_base64 = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = () => reject(new Error('Could not read reference image.'))
    reader.readAsDataURL(file)
  })
  return { mime_type: file.type, bytes_base64 }
}

/** File and preview live only in component state; never upload on selection. */
export function ImageReferenceInput({ value, onChange, disabled, language }: {
  value: File | null; onChange: (file: File | null) => void; disabled: boolean; language: 'en' | 'uk'
}) {
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const tr = (en: string, uk: string) => language === 'uk' ? uk : en
  useEffect(() => {
    if (!value) { setUrl(''); if (input.current) input.current.value = ''; return }
    const next = URL.createObjectURL(value)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [value])
  return <div className="image-reference-input">
    <label htmlFor={id}>{tr('Upload reference image', 'Завантажити зображення-референс')} <small>{tr('(optional)', '(необов’язково)')}</small></label>
    <input ref={input} id={id} type="file" accept="image/png,image/jpeg,image/webp" disabled={disabled}
      aria-describedby={`${id}-hint`} onChange={event => {
        const file = event.target.files?.[0]
        if (!file) return
        if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || !file.size || file.size > maxBytes) {
          setError(tr('Use a PNG, JPEG, or WebP image up to 8 MB.', 'Оберіть PNG, JPEG або WebP до 8 МБ.'))
          event.target.value = ''; return
        }
        setError(''); onChange(file)
      }} />
    <small id={`${id}-hint`}>{tr('PNG, JPEG or WebP · up to 8 MB. Describe what to keep or change. Used only for this generation; not saved to the project.', 'PNG, JPEG або WebP · до 8 МБ. Опишіть, що залишити або змінити. Лише для цієї генерації; не зберігається в проєкті.')}</small>
    {value && <div className="image-reference-preview">
      {url && <img src={url} alt={tr('Reference preview', 'Прев’ю референсу')} />}
      <span>{value.name}</span>
      <button type="button" className="secondary" disabled={disabled} onClick={() => { onChange(null); setError('') }}>{tr('Remove reference', 'Видалити референс')}</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </div>
}
