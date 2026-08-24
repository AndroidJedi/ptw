import { LayoutTemplate } from 'lucide-react'
import { PageHeader } from '../components/State'

export function LandingPlaceholderView() {
  return <>
    <PageHeader eyebrow="STAGE 3 · INACTIVE" title="Landing" />
    <section className="panel landing-placeholder"><LayoutTemplate /><div><h2>Stage 3 pending</h2><p>Landing generation is intentionally inactive in this release. The three Natal templates and dormant source assets remain preserved for the later simplified conversion-checkpoint rebuild.</p></div></section>
  </>
}
