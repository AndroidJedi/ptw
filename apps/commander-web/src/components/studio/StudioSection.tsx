import { useState, type ReactNode } from 'react'

export function StudioSection({ eyebrow, title, children, className = '', defaultOpen = false, expandLabel, collapseLabel, onOpenChange }: {
  eyebrow: string
  title: string
  children: ReactNode
  className?: string
  defaultOpen?: boolean
  expandLabel: string
  collapseLabel: string
  onOpenChange?: (open: boolean) => void
}) {
  const [open, setOpen] = useState(defaultOpen)
  return <details
    className={`panel studio-section studio-disclosure ${className}`.trim()}
    open={open}
    onToggle={(event) => { setOpen(event.currentTarget.open); onOpenChange?.(event.currentTarget.open) }}
  >
    <summary>
      <span><small>{eyebrow}</small><h2>{title}</h2></span>
      <em>{open ? collapseLabel : expandLabel}</em>
    </summary>
    <div className="studio-section-body">{children}</div>
  </details>
}
