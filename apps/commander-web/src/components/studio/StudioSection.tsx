import { useState, type ReactNode } from 'react'

export function StudioSection({ eyebrow, title, children, className = '', defaultOpen = false, expandLabel, collapseLabel }: {
  eyebrow: string
  title: string
  children: ReactNode
  className?: string
  defaultOpen?: boolean
  expandLabel: string
  collapseLabel: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  return <details
    className={`panel universal-section universal-disclosure ${className}`.trim()}
    open={open}
    onToggle={(event) => setOpen(event.currentTarget.open)}
  >
    <summary>
      <span><small>{eyebrow}</small><h2>{title}</h2></span>
      <em>{open ? collapseLabel : expandLabel}</em>
    </summary>
    <div className="universal-section-body">{children}</div>
  </details>
}
