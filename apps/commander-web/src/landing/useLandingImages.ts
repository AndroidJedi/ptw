import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import type { LandingDetail } from '../types'

export function useLandingImages(api: ApiClient, detail: LandingDetail | null, pagePath: string, section: string) {
  const cache = useRef(new Map<string, string>())
  const pending = useRef(new Set<string>())
  const [images, setImages] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const latest = useRef(detail); latest.current = detail
  const generation = useRef(0)
  useEffect(() => {
    generation.current++; cache.current.forEach(url => URL.revokeObjectURL(url)); cache.current.clear(); pending.current.clear(); setImages({}); setError('')
    return () => { generation.current++; cache.current.forEach(url => URL.revokeObjectURL(url)); cache.current.clear(); pending.current.clear() }
  }, [pagePath])
  useEffect(() => {
    if (!detail || !pagePath) return
    const epoch = generation.current
    const update = () => {
      const next: Record<string, string> = Object.fromEntries(cache.current)
      latest.current?.assets.forEach(asset => { const url = asset.sha256 && cache.current.get(asset.sha256); if (url) next[asset.slot] = url })
      setImages(previous => ({ ...previous, ...next }))
    }
    update()
    const inspectorSlot = ({ hero: 'hero_visual', visual_break: 'visual_break_visual', walkthrough: 'walkthrough_visual' } as Record<string, string>)[section] || section
    const work = detail.assets.flatMap(asset => asset.history.filter(entry => entry.selected || inspectorSlot === asset.slot || (section === 'app_screens' && asset.slot.startsWith('app_screen_'))).map(entry => ({ slot: asset.slot, entry })))
      .sort((a, b) => Number(b.entry.selected) - Number(a.entry.selected))
    void (async () => {
      // Selected images enter first; history never delays their display.
      for (let offset = 0; offset < work.length; offset += 3) {
        if (epoch !== generation.current) return
        await Promise.all(work.slice(offset, offset + 3).map(async ({ slot, entry }) => {
          if (cache.current.has(entry.sha256) || pending.current.has(entry.sha256)) return
          pending.current.add(entry.sha256)
          let url = ''
          try {
            const variants = entry.variants
            const variant = variants?.find(item => item.width >= 720) || variants?.at(-1)
            const original = `${pagePath}/visuals/${slot}/history/${entry.sha256}`
            let blob: Blob
            try { blob = variant ? await api.image(`${original}/webp-v1/${variant.sha256}.webp`, 'image/webp', variant.sha256) : await api.image(original, 'image/png', entry.sha256) }
            catch (cause) { if (!variant) throw cause; blob = await api.image(original, 'image/png', entry.sha256) }
            url = URL.createObjectURL(blob)
            const decoded = new Image(); decoded.src = url
            if (decoded.decode) await decoded.decode()
            if (epoch !== generation.current) { URL.revokeObjectURL(url); return }
            cache.current.set(entry.sha256, url); update()
          } catch (cause) { if (url) URL.revokeObjectURL(url); if (epoch === generation.current) setError(cause instanceof Error ? cause.message : String(cause)) }
          finally { if (epoch === generation.current) pending.current.delete(entry.sha256) }
        }))
      }
    })()
  }, [api, pagePath, JSON.stringify(detail?.assets), section, retryCount]) // eslint-disable-line react-hooks/exhaustive-deps
  return { images, error, ready: Boolean(detail && detail.assets.every(asset => !asset.sha256 || images[asset.sha256])),
    retry: () => { setError(''); setRetryCount(value => value + 1) } }
}
