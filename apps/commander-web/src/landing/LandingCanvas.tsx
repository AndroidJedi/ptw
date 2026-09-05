import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { X } from 'lucide-react'

export function LandingCanvas({ width, children }: { width: number; children: ReactNode }) {
  const frame = useRef<HTMLDivElement>(null)
  const page = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width, height: 1000 })
  useLayoutEffect(() => {
    if (!frame.current || !page.current || typeof ResizeObserver === 'undefined') return
    const update = () => setSize({ width: frame.current!.clientWidth, height: page.current!.offsetHeight })
    const observer = new ResizeObserver(update)
    observer.observe(frame.current); observer.observe(page.current); update()
    return () => observer.disconnect()
  }, [width])
  const scale = Math.min(1, size.width / width)
  return <div className="landing-stage" ref={frame}><div className="landing-scaled-frame" style={{ width: width * scale, height: size.height * scale }}><div ref={page} className="landing-device-page" style={{ width, transform: `scale(${scale})` }}>{children}</div></div></div>
}

export function LandingDialog({ title, onClose, children, className = '' }: { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const dialog = ref.current
    if (dialog?.showModal) dialog.showModal()
    else dialog?.setAttribute('open', '')
    return () => { dialog?.close?.(); previous?.focus() }
  }, [])
  return <dialog ref={ref} className={`landing-dialog ${className}`} aria-label={title} onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) onClose() }}><div className="landing-dialog-body"><header><strong>{title}</strong><button className="ghost" aria-label="Close full-screen preview" onClick={onClose}><X /></button></header>{children}</div></dialog>
}
