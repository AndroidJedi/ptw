import { useEffect, useRef, useState, type ImgHTMLAttributes } from 'react'

export type LandingImageVariant = { url: string; sha256: string; width: number; height: number; mime_type: string; byte_count: number }
export type LandingImageVariants = Record<string, LandingImageVariant[]>

/** One image element preserves the shared renderer's geometry and aperture rules. */
export function LandingImage({ src, variants, priority = false, sizes, className = '', ...props }: ImgHTMLAttributes<HTMLImageElement> & {
  variants?: LandingImageVariant[]; priority?: boolean
}) {
  const [fallback, setFallback] = useState(false)
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading')
  const ref = useRef<HTMLImageElement>(null)
  const previousSrc = useRef(src)
  const available = !fallback ? variants : undefined
  const selected = available?.find(item => item.width >= 720) || available?.at(-1)
  const source = selected?.url || src
  useEffect(() => {
    if (previousSrc.current !== src) { previousSrc.current = src; setFallback(false); setState('loading') }
  }, [src])
  useEffect(() => { if (ref.current?.complete && ref.current.naturalWidth) setState('ready') }, [source])
  return <img {...props} key={`${src}:${fallback ? 'original' : 'display'}`} ref={ref} src={source}
    srcSet={available?.map(item => `${item.url} ${item.width}w`).join(', ')} sizes={available ? sizes : undefined}
    width={selected?.width} height={selected?.height}
    loading={priority ? 'eager' : 'lazy'} fetchPriority={priority ? 'high' : 'auto'} decoding="async"
    className={`${className} lp-delivery-image is-${state}`} data-image-state={state}
    onLoad={() => setState('ready')} onError={() => {
      if (available?.length) { setFallback(true); setState('loading') } else setState('failed')
    }} />
}
