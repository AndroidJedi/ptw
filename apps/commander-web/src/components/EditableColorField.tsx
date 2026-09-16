import { useEffect, useState } from 'react'

const HEX_COLOR = /^#[0-9A-F]{6}$/

function normalize(value: string) {
  const trimmed = value.trim().toUpperCase()
  return trimmed.startsWith('#') ? trimmed : `#${trimmed}`
}

export function EditableColorField({ label, value, onChange, className = '', hexLabel = `${label} hex` }: {
  label: string
  value: string
  onChange: (value: string) => void
  className?: string
  hexLabel?: string
}) {
  const canonical = normalize(value)
  const [draft, setDraft] = useState(canonical)
  const accessibleHexLabel = hexLabel.includes(' ')
    ? hexLabel.replace(/\s+/, ' · HEX · ')
    : `HEX · ${hexLabel}`

  useEffect(() => setDraft(canonical), [canonical])

  const commit = (candidate: string) => {
    const normalized = normalize(candidate)
    if (!HEX_COLOR.test(normalized)) {
      setDraft(canonical)
      return
    }
    setDraft(normalized)
    if (normalized !== canonical) onChange(normalized)
  }

  return <label className={`editable-color-field ${className}`.trim()}>
    <span>{label}</span>
    <span className="editable-color-controls">
      <input
        aria-label={label} type="color" value={canonical}
        onChange={(event) => commit(event.target.value)}
      />
      <input
        className="editable-color-hex" aria-label={accessibleHexLabel} type="text"
        inputMode="text" autoCapitalize="characters" autoComplete="off" spellCheck={false}
        maxLength={7} value={draft} pattern="#[0-9A-Fa-f]{6}"
        onChange={(event) => {
          const next = event.target.value.toUpperCase()
          setDraft(next)
          const normalized = normalize(next)
          if (HEX_COLOR.test(normalized) && normalized !== canonical) onChange(normalized)
        }}
        onBlur={(event) => commit(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur()
          if (event.key === 'Escape') {
            setDraft(canonical)
            event.currentTarget.blur()
          }
        }}
      />
    </span>
  </label>
}
