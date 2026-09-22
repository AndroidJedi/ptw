import { useEffect, useId, useRef, useState } from 'react'
import './ImageReferenceInput.css'

export type ImageReference = { mime_type: string; bytes_base64: string }
const maxBytes = 8 * 1024 * 1024
export const referenceAccept = 'image/png,image/jpeg,image/webp,image/svg+xml,.svg'
export const supportedReference = (file: File) =>
  ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'].includes(file.type) || (file.type === '' && file.name.toLowerCase().endsWith('.svg'))
const unsafeSvgValue = (value: string) => /url\s*\(|@import|@font-face|https?:|data:|javascript:/i.test(
  value.replace(/url\(\s*['"]?#[A-Za-z_][\w.-]*['"]?\s*\)/gi, ''),
)

async function safeSvgPng(file: File): Promise<Blob> {
  const source = await file.text()
  if (/<!DOCTYPE|<!ENTITY/i.test(source)) throw new Error('SVG declarations and entities are not supported.')
  const svgDocument = new DOMParser().parseFromString(source, 'image/svg+xml')
  const root = svgDocument.documentElement
  const allowed = new Set(['svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'defs', 'linearGradient', 'radialGradient', 'stop', 'clipPath', 'mask', 'style', 'title', 'desc'])
  if (root.localName !== 'svg' || svgDocument.querySelector('parsererror')) throw new Error('SVG is invalid.')
  for (const element of Array.from(svgDocument.querySelectorAll('*'))) {
    if (element.namespaceURI !== 'http://www.w3.org/2000/svg' || !allowed.has(element.localName)) throw new Error('SVG contains unsupported content.')
    for (const attribute of Array.from(element.attributes)) {
      if (attribute.name === 'xmlns' || attribute.name.startsWith('xmlns:')) continue
      if (/^on/i.test(attribute.name) || /href$/i.test(attribute.name) || unsafeSvgValue(attribute.value)) throw new Error('SVG contains external or active content.')
    }
    if (element.localName === 'style' && unsafeSvgValue(element.textContent || '')) throw new Error('SVG contains external styles.')
  }
  const dimensions = (root.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number)
  const width = dimensions.length === 4 ? dimensions[2] : Number.parseFloat(root.getAttribute('width') || '')
  const height = dimensions.length === 4 ? dimensions[3] : Number.parseFloat(root.getAttribute('height') || '')
  if (![width, height].every(value => Number.isFinite(value) && value >= 64 && value <= 8192) || width * height > 16_777_216) throw new Error('SVG dimensions must be 64–8192 pixels and at most 16 megapixels.')
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(root)], { type: 'image/svg+xml' }))
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    const scale = Math.min(1, 2048 / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Canvas is unavailable for SVG conversion.')
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('Could not rasterize SVG.')), 'image/png'))
    if (blob.size > maxBytes) throw new Error('Rasterized SVG exceeds 8 MB.')
    return blob
  } finally { URL.revokeObjectURL(url) }
}

export async function imageReferencePayload(file: File): Promise<ImageReference> {
  if (!supportedReference(file) || !file.size || file.size > maxBytes) {
    throw new Error('Use a PNG, JPEG, WebP, or SVG image up to 8 MB.')
  }
  const raster = file.type === 'image/svg+xml' || file.name.toLowerCase().endsWith('.svg') ? await safeSvgPng(file) : file
  const bytes_base64 = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = () => reject(new Error('Could not read reference image.'))
    reader.readAsDataURL(raster)
  })
  return { mime_type: raster.type, bytes_base64 }
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
    let cancelled = false, next = ''
    if (value.type === 'image/svg+xml' || value.name.toLowerCase().endsWith('.svg')) {
      setUrl('')
      void safeSvgPng(value).then(blob => { if (!cancelled) { next = URL.createObjectURL(blob); setUrl(next); setError('') } }).catch(cause => { if (!cancelled) setError((cause as Error).message) })
    } else { next = URL.createObjectURL(value); setUrl(next) }
    return () => { cancelled = true; if (next) URL.revokeObjectURL(next) }
  }, [value])
  return <div className="image-reference-input">
    <label htmlFor={id}>{tr('Upload reference image', 'Завантажити зображення-референс')} <small>{tr('(optional)', '(необов’язково)')}</small></label>
    <input ref={input} id={id} type="file" accept={referenceAccept} disabled={disabled}
      aria-describedby={`${id}-hint`} onChange={event => {
        const file = event.target.files?.[0]
        if (!file) return
        if (!supportedReference(file) || !file.size || file.size > maxBytes) {
          setError(tr('Use a PNG, JPEG, WebP, or SVG image up to 8 MB.', 'Оберіть PNG, JPEG, WebP або SVG до 8 МБ.'))
          event.target.value = ''; return
        }
        setError(''); onChange(file)
      }} />
    <small id={`${id}-hint`}>{tr('PNG, JPEG, WebP or SVG · up to 8 MB. SVG is safely rasterized for visual reference only.', 'PNG, JPEG, WebP або SVG · до 8 МБ. SVG безпечно перетворюється на зображення лише для візуального референсу.')}</small>
    {value && <div className="image-reference-preview">
      {url && <img src={url} alt={tr('Reference preview', 'Прев’ю референсу')} />}
      <span>{value.name}</span>
      <button type="button" className="secondary" disabled={disabled} onClick={() => { onChange(null); setError('') }}>{tr('Remove reference', 'Видалити референс')}</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </div>
}
