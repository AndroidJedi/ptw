import { Megaphone } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type { PositioningProject, PositioningRevision } from '../types'

interface AdsState {
  positionings: PositioningProject[]
  selected_revision?: PositioningRevision | null
  ad_concepts: NonNullable<PositioningRevision['document']>['ad_concepts']
  implemented: false
  message: string
}

export function AdsView({ api }: { api: ApiClient }) {
  const [state, setState] = useState<AdsState | null>(null)
  const [selected, setSelected] = useState('')
  const [error, setError] = useState('')
  const load = (projectId = '') => api.get<AdsState>(`/api/v1/ads${projectId ? `?positioning_project_id=${projectId}` : ''}`).then((value) => { setState(value); if (!selected && value.positionings[0]) setSelected(value.positionings[0].id) }).catch((cause: Error) => setError(cause.message))
  useEffect(() => { void load() }, [api])
  useEffect(() => { if (selected) void load(selected) }, [selected])
  if (!state) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  return <>
    <PageHeader eyebrow="ADS · READ-ONLY STUB" title="Реклама" />
    {error && <ErrorState message={error} />}
    {!state.positionings.length ? <Empty><Megaphone className="empty-mark" /><h2>No approved positioning</h2><p>Ads can inspect only the active approved revision.</p></Empty> : <div className="ads-workspace">
      <section className="panel"><label>Approved positioning<select value={selected} onChange={(event) => setSelected(event.target.value)}>{state.positionings.map((item) => <option key={item.id} value={item.id}>{item.raw_idea.slice(0, 120)}</option>)}</select></label>{state.selected_revision && <p>Revision {state.selected_revision.id}</p>}</section>
      <section className="ads-grid">{state.ad_concepts.map((concept) => <article className="panel" key={concept.kind}><small>{concept.kind}</small><h2>{concept.hook.text}</h2><p>{concept.body.text}</p><h3>Creative direction</h3><p>{concept.visual_direction.text}</p></article>)}</section>
      <section className="panel ads-stub"><Megaphone /><div><h2>{state.message}</h2><p>No post, image, campaign, or publishing mutation exists in PTW v2.</p></div></section>
    </div>}
  </>
}
