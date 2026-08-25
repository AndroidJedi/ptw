import { LayoutTemplate } from 'lucide-react'
import { PageHeader } from '../components/State'
import type { ValidationProject } from '../types'

export function LandingPlaceholderView({ project }: { project: ValidationProject | null }) {
  return <>
    <PageHeader eyebrow="STAGE 3 · INACTIVE" title="Landing" />
    <section className="panel landing-placeholder"><LayoutTemplate /><div><h2>Stage 3 pending</h2>{project && <p><strong>{project.name}</strong><br /><span className="uuid-line">Project {project.project_id}</span></p>}<p>Landing generation is intentionally inactive in this release. The three Natal templates and dormant source assets remain preserved for the later simplified conversion-checkpoint rebuild.</p></div></section>
  </>
}
