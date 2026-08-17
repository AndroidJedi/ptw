import { useEffect, useId, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function Diagram({ source }: { source: string }) {
  const id = `mermaid-${useId().replaceAll(':', '')}`
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let active = true
    void import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'dark' })
      return mermaid.render(id, source)
    }).then(({ svg }) => { if (active && host.current) host.current.innerHTML = svg })
    return () => { active = false }
  }, [id, source])
  return <div className="mermaid-diagram" ref={host} role="img" aria-label="Architecture diagram" />
}

export function MarkdownDoc({ body }: { body: string }) {
  return <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      code({ className, children, ...props }) {
        const source = String(children).replace(/\n$/, '')
        if (className === 'language-mermaid') return <Diagram source={source} />
        return <code className={className} {...props}>{children}</code>
      },
    }}
  >{body}</ReactMarkdown>
}
