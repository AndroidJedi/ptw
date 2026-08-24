import { useEffect, useId, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function Diagram({ source }: { source: string }) {
  const id = `mermaid-${useId().replaceAll(':', '')}`
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let active = true
    void import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          background: '#000000',
          primaryColor: '#121212',
          primaryTextColor: '#ffffff',
          primaryBorderColor: '#ffffff',
          secondaryColor: '#1f1f1f',
          secondaryTextColor: '#ffffff',
          secondaryBorderColor: '#a3a3a3',
          tertiaryColor: '#000000',
          tertiaryTextColor: '#ffffff',
          tertiaryBorderColor: '#a3a3a3',
          lineColor: '#ffffff',
          textColor: '#ffffff',
          mainBkg: '#121212',
          nodeBorder: '#ffffff',
          clusterBkg: '#121212',
          clusterBorder: '#a3a3a3',
          edgeLabelBackground: '#000000',
          titleColor: '#ffffff',
        },
      })
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
