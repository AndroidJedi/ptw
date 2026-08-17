import { useRef, useState } from 'react'
import { MapPin, Pencil, Square } from 'lucide-react'
import type { PointerEvent } from 'react'
import type { Region } from '../types'

type Tool = Region['kind']
type DraftRegion =
  | { kind: 'pin'; x: number; y: number }
  | { kind: 'rectangle'; x: number; y: number; width: number; height: number }
  | { kind: 'freehand'; points: Array<{ x: number; y: number }> }

function normalized(event: PointerEvent<SVGSVGElement>) {
  const box = event.currentTarget.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)),
    y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)),
  }
}

export function AnnotationCanvas({ src, alt, regions, onChange }: {
  src: string
  alt: string
  regions: Region[]
  onChange: (regions: Region[]) => void
}) {
  const [tool, setTool] = useState<Tool>('pin')
  const [pending, setPending] = useState<DraftRegion | null>(null)
  const [comment, setComment] = useState('')
  const draft = useRef<{ start: { x: number; y: number }; points: Array<{ x: number; y: number }> } | null>(null)

  const stage = (region: DraftRegion) => {
    setPending(region)
    setComment('')
  }
  const add = () => {
    if (!pending || !comment.trim()) return
    onChange([...regions, { ...pending, id: crypto.randomUUID(), comment: comment.trim() } as Region])
    setPending(null)
    setComment('')
  }

  const down = (event: PointerEvent<SVGSVGElement>) => {
    if (pending) return
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = normalized(event)
    if (tool === 'pin') stage({ kind: 'pin', ...point })
    else draft.current = { start: point, points: [point] }
  }
  const move = (event: PointerEvent<SVGSVGElement>) => {
    if (tool === 'freehand' && draft.current) draft.current.points.push(normalized(event))
  }
  const up = (event: PointerEvent<SVGSVGElement>) => {
    if (!draft.current) return
    const end = normalized(event)
    if (tool === 'rectangle') {
      const x = Math.min(draft.current.start.x, end.x)
      const y = Math.min(draft.current.start.y, end.y)
      stage({ kind: 'rectangle', x, y, width: Math.abs(end.x - draft.current.start.x), height: Math.abs(end.y - draft.current.start.y) })
    } else stage({ kind: 'freehand', points: draft.current.points })
    draft.current = null
  }

  return <section className="annotation-editor">
    <div className="annotation-tools" aria-label="Інструменти анотації">
      <button className={tool === 'pin' ? 'selected' : ''} onClick={() => setTool('pin')}><MapPin />Точка</button>
      <button className={tool === 'rectangle' ? 'selected' : ''} onClick={() => setTool('rectangle')}><Square />Область</button>
      <button className={tool === 'freehand' ? 'selected' : ''} onClick={() => setTool('freehand')}><Pencil />Лінія</button>
    </div>
    <div className="image-stage">
      <img src={src} alt={alt} draggable={false} />
      <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Області зворотного зв’язку" onPointerDown={down} onPointerMove={move} onPointerUp={up}>
        {regions.map((region, index) => {
          if (region.kind === 'pin') return <g key={region.id}><circle cx={region.x * 1000} cy={region.y * 1000} r="24" /><text x={region.x * 1000} y={region.y * 1000 + 8}>{index + 1}</text></g>
          if (region.kind === 'rectangle') return <rect key={region.id} x={region.x * 1000} y={region.y * 1000} width={region.width * 1000} height={region.height * 1000} />
          return <polyline key={region.id} points={region.points.map((p) => `${p.x * 1000},${p.y * 1000}`).join(' ')} />
        })}
        {pending?.kind === 'pin' && <circle className="draft" cx={pending.x * 1000} cy={pending.y * 1000} r="24" />}
        {pending?.kind === 'rectangle' && <rect className="draft" x={pending.x * 1000} y={pending.y * 1000} width={pending.width * 1000} height={pending.height * 1000} />}
        {pending?.kind === 'freehand' && <polyline className="draft" points={pending.points.map((point) => `${point.x * 1000},${point.y * 1000}`).join(' ')} />}
      </svg>
    </div>
    {pending && <div className="annotation-comment">
      <label htmlFor="region-comment">Що саме треба змінити?</label>
      <textarea id="region-comment" autoFocus rows={2} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Конкретний коментар до виділеної області" />
      <div><button onClick={() => { setPending(null); setComment('') }}>Скасувати</button><button className="primary" disabled={!comment.trim()} onClick={add}>Додати область</button></div>
    </div>}
    {regions.length > 0 && <ol className="annotation-list">{regions.map((region) => <li key={region.id}><span>{{ pin: 'точка', rectangle: 'область', freehand: 'лінія' }[region.kind]}</span>{region.comment}<button aria-label="Видалити анотацію" onClick={() => onChange(regions.filter((item) => item.id !== region.id))}>×</button></li>)}</ol>}
  </section>
}
