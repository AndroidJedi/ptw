import { Check, Download, Image as ImageIcon, Package, RefreshCcw, Sparkles, WandSparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApiClient } from '../api'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type {
  ProductBrief, StudioCreativeValidation, StudioRecipe, StudioRender, StudioSampleSet, StudioSampleSetItem,
  StudioWizardProposal,
} from '../types'

const STUDIO_GENERATION_DEADLINE_MS = 7_200_000
const STUDIO_WIZARD_DEADLINE_MS = 2_400_000
const ANGLE_LABELS: Record<StudioSampleSetItem['angle'], string> = {
  emotional: 'Emotional', practical: 'Practical', curiosity: 'Curiosity',
  authority: 'Authority', problem_first: 'Problem-first',
}

function validationReceipt(validation?: StudioCreativeValidation | null) {
  if (!validation) return ''
  if (validation.recreation_count === 0) return 'Automatically reviewed · passed the first quality check.'
  const rounds = validation.recreation_count === 1 ? 'round' : 'rounds'
  return `Automatically reviewed · improved and rechecked for ${validation.recreation_count} ${rounds}.`
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = window.document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}

function useAuthenticatedUrl(api: ApiClient, path?: string, mime?: string, sha256?: string) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    let objectUrl = ''
    setUrl('')
    setError('')
    if (!path || !mime || !sha256) return () => { active = false }
    void api.media(path, mime, sha256).then((blob) => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch((cause: Error) => { if (active) setError(cause.message) })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, path, mime, sha256])
  return { url, error }
}

function RenderImage({ api, render, alt, compact = false }: { api: ApiClient; render: StudioRender; alt: string; compact?: boolean }) {
  const { url, error } = useAuthenticatedUrl(api, render.asset_url, render.mime_type, render.bytes_sha256)
  if (error) return <div className="studio-render-fallback" role="alert"><ImageIcon /><span>Post unavailable</span></div>
  if (!url) return <div className="studio-render-fallback"><span>Loading post…</span></div>
  return render.mime_type === 'video/mp4'
    ? <video src={url} controls={!compact} playsInline muted aria-label={alt} />
    : <img src={url} alt={alt} />
}

function RenderDownloadButton({ api, render, name }: { api: ApiClient; render: StudioRender; name: string }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const download = async () => {
    setBusy(true)
    setError('')
    try {
      const blob = await api.media(render.asset_url, render.mime_type, render.bytes_sha256)
      const base = name.replace(/[^a-z0-9\u0400-\u04ff]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'ptw-studio-post'
      downloadBlob(blob, `${base}.${render.mime_type === 'video/mp4' ? 'mp4' : 'jpg'}`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return <div className="studio-download-action">
    <button className="secondary" disabled={busy} onClick={() => void download()} aria-label={`Download ${name}`}>
      <Download /> {busy ? 'Downloading…' : 'Download post'}
    </button>
    {error && <small className="studio-card-error" role="alert">{error}</small>}
  </div>
}

function SampleGallery({ api, sampleSet, selectedRecipeId, busy, onOpen, onDownload }: {
  api: ApiClient
  sampleSet: StudioSampleSet
  selectedRecipeId: string | null
  busy: boolean
  onOpen: (item: StudioSampleSetItem) => void
  onDownload: () => void
}) {
  return <section className="panel studio-sample-set" aria-label="Your five Studio posts">
    <header>
      <div><small>YOUR POSTS</small><h2>Choose a post</h2></div>
      <button className="secondary" disabled={busy || !sampleSet.download_sha256} onClick={onDownload}><Package /> Download all 5</button>
    </header>
    <div className="studio-sample-grid">
      {[...sampleSet.items].sort((a, b) => a.ordinal - b.ordinal).map((item) => <article key={item.recipe_id} className={selectedRecipeId === item.recipe_id ? 'selected' : ''}>
        <button className="studio-sample-open" onClick={() => onOpen(item)} aria-label={`Change ${item.name} with AI`}>
          <div className="studio-sample-art"><RenderImage api={api} render={item.render} alt={item.alt_text || item.name} compact /></div>
          <span className="studio-angle">{ANGLE_LABELS[item.angle]}</span>
          <strong>{item.name}</strong>
          <span className="studio-sample-change"><WandSparkles /> Change with AI</span>
        </button>
      </article>)}
    </div>
  </section>
}

function WizardPreview({ api, proposal }: { api: ApiClient; proposal: StudioWizardProposal }) {
  const { url, error } = useAuthenticatedUrl(api, proposal.preview_url, proposal.preview_mime_type || 'image/jpeg', proposal.preview_sha256)
  if (error) return <ErrorState message={error} />
  if (!url) return <div className="studio-wizard-media-loading" role="status"><RefreshCcw className="spin" /> Loading preview…</div>
  return <img className="studio-wizard-preview" src={url} alt="Preview of proposed change" />
}

function elapsedLabel(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}

function WizardPanel({ api, recipe, recoveredProposal, onProposalChange, onApplied }: {
  api: ApiClient
  recipe: StudioRecipe
  recoveredProposal: StudioWizardProposal | null
  onProposalChange: (proposal: StudioWizardProposal | null) => void
  onApplied: (recipe: StudioRecipe, render: StudioRender, validation?: StudioCreativeValidation | null) => void
}) {
  const [instruction, setInstruction] = useState('')
  const [proposal, setProposal] = useState<StudioWizardProposal | null>(recoveredProposal)
  const [operation, setOperation] = useState<'preview' | 'apply' | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState<{ message: string; operation: 'preview' | 'apply' } | null>(null)
  const busy = operation !== null

  useEffect(() => {
    setProposal(recoveredProposal)
    setInstruction(recoveredProposal?.instruction || '')
    onProposalChange(recoveredProposal)
  }, [recipe.recipe_id, recoveredProposal?.proposal_id, onProposalChange])
  useEffect(() => {
    setElapsedSeconds(0)
    if (!operation) return
    const startedAt = Date.now()
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [operation])

  const preview = async () => {
    const normalizedInstruction = instruction.trim()
    if (!normalizedInstruction || busy) return
    setOperation('preview')
    setError(null)
    setProposal(null)
    onProposalChange(null)
    try {
      const value = await api.post<StudioWizardProposal>(`/api/v1/ad-studio/recipes/${recipe.recipe_id}/wizard-proposals`, {
        instruction: normalizedInstruction,
        target_instance_id: null,
      }, { deadlineMs: STUDIO_WIZARD_DEADLINE_MS })
      setProposal(value)
      onProposalChange(value)
    } catch (cause) {
      setError({ message: (cause as Error).message, operation: 'preview' })
    } finally {
      setOperation(null)
    }
  }
  const apply = async () => {
    if (!proposal || busy) return
    setOperation('apply')
    setError(null)
    try {
      const result = await api.post<{ proposal: StudioWizardProposal; recipe: StudioRecipe; render: StudioRender }>(`/api/v1/ad-studio/wizard-proposals/${proposal.proposal_id}/apply`, {}, { deadlineMs: STUDIO_WIZARD_DEADLINE_MS })
      setProposal(result.proposal)
      setInstruction('')
      onProposalChange(null)
      onApplied(result.recipe, result.render, result.proposal.creative_validation)
    } catch (cause) {
      setError({ message: (cause as Error).message, operation: 'apply' })
    } finally {
      setOperation(null)
    }
  }
  const retry = () => error?.operation === 'apply' ? void apply() : void preview()

  return <section className="panel studio-wizard" aria-label="AI wizard" aria-busy={busy}>
    <header><WandSparkles /><div><small>AI WIZARD</small><h2>Change this post</h2></div></header>
    <p>Describe the result you want. AI can change the image, layout, and copy together.</p>
    <label>What should change?
      <textarea disabled={busy} rows={6} maxLength={1000} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="For example: make it feel more personal, use a horoscope visual, and shorten the copy." />
    </label>
    <p className="studio-wizard-policy-note">People must use approved photos. Generated graphics cannot show people.</p>
    <button className="primary" disabled={busy || !instruction.trim()} onClick={() => void preview()}>
      {operation === 'preview' ? <RefreshCcw className="spin" /> : <WandSparkles />}
      {operation === 'preview' ? 'Creating preview…' : proposal?.status === 'previewed' ? 'Preview another change' : 'Preview change'}
    </button>
    {!operation && !proposal && !error && <p className="studio-wizard-submit-note">You will review it before anything changes.</p>}
    {operation && <div className="studio-wizard-progress" role="status" aria-live="polite">
      <RefreshCcw className="spin" />
      <div><strong>{operation === 'apply' ? 'Saving your new version…' : 'Working on your preview…'}</strong><p>{operation === 'apply' ? 'The approved preview is being saved.' : 'Nothing has changed yet. Keep this page open.'}</p><small>Elapsed {elapsedLabel(elapsedSeconds)}</small></div>
      <div className="studio-wizard-progress-bar" role="progressbar" aria-label="AI change in progress" aria-valuetext="In progress" />
    </div>}
    {error && <div className="studio-wizard-error" role="alert"><strong>{error.operation === 'apply' ? 'Could not save this version.' : 'Could not create the preview.'}</strong><p>{error.message}</p><button className="secondary" disabled={busy} onClick={retry}><RefreshCcw /> Try again</button></div>}
    {proposal?.status === 'previewed' && <div className="studio-wizard-ready" role="status">
      <div><strong>New preview ready.</strong><span>Nothing changed yet. Review it beside this panel.</span>{proposal.creative_validation && <span>{validationReceipt(proposal.creative_validation)}</span>}</div>
      <button className="primary" disabled={busy} onClick={() => void apply()}>{operation === 'apply' ? <RefreshCcw className="spin" /> : <Check />} {operation === 'apply' ? 'Saving…' : 'Use this version'}</button>
    </div>}
  </section>
}

function PostPreview({ api, name, render, proposal, validation }: { api: ApiClient; name: string; render: StudioRender; proposal: StudioWizardProposal | null; validation?: StudioCreativeValidation | null }) {
  const proposed = proposal?.status === 'previewed'
  return <section className="panel studio-focus" aria-label="Post preview">
    <header>
      <div><small>{proposed ? 'NEW PREVIEW · NOT SAVED' : 'CURRENT VERSION'}</small><h2>{name}</h2></div>
      {!proposed && <RenderDownloadButton api={api} render={render} name={name} />}
    </header>
    <div className="studio-post-art">
      {proposed ? <WizardPreview api={api} proposal={proposal} /> : <RenderImage api={api} render={render} alt={name} />}
    </div>
    <p>{proposed ? 'Review this preview. Use this version only if it is right.' : 'Use the Wizard to change anything in this post.'}</p>
    {validation && <p className="studio-validation-receipt" role="status"><Check /> {validationReceipt(validation)}</p>}
  </section>
}

export function StudioView({ api, projectId }: { api: ApiClient; projectId: string | null }) {
  const [briefs, setBriefs] = useState<ProductBrief[]>([])
  const [sampleSets, setSampleSets] = useState<StudioSampleSet[]>([])
  const [briefId, setBriefId] = useState('')
  const [selectedPost, setSelectedPost] = useState<StudioSampleSetItem | null>(null)
  const [recipe, setRecipe] = useState<StudioRecipe | null>(null)
  const [render, setRender] = useState<StudioRender | null>(null)
  const [recoveredProposal, setRecoveredProposal] = useState<StudioWizardProposal | null>(null)
  const [activeProposal, setActiveProposal] = useState<StudioWizardProposal | null>(null)
  const [currentValidation, setCurrentValidation] = useState<StudioCreativeValidation | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const openPost = async (item: StudioSampleSetItem) => {
    setError('')
    setSelectedPost(item)
    setRecipe(item.recipe)
    setRender(item.render)
    setRecoveredProposal(null)
    setActiveProposal(null)
    setCurrentValidation(item.creative_validation || null)
    try {
      const value = await api.get<{ items: StudioWizardProposal[] }>(`/api/v1/ad-studio/recipes/${item.recipe.recipe_id}/wizard-proposals`)
      const latest = value.items.find((proposal) => proposal.status === 'previewed') || null
      setRecoveredProposal(latest)
      setActiveProposal(latest)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  const load = async () => {
    setLoading(true)
    setError('')
    setNotice('')
    setSelectedPost(null)
    setRecipe(null)
    setRender(null)
    setRecoveredProposal(null)
    setActiveProposal(null)
    setCurrentValidation(null)
    if (!projectId) {
      setBriefs([])
      setSampleSets([])
      setLoading(false)
      return
    }
    try {
      const [briefValue, sampleValue] = await Promise.all([
        api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
        api.get<{ items: StudioSampleSet[] }>(`/api/v1/ad-studio/sample-sets?project_id=${encodeURIComponent(projectId)}`),
      ])
      const approved = briefValue.items.filter((brief) => brief.status === 'completed' && brief.approved)
      setBriefs(approved)
      setBriefId(approved[0]?.brief_id || '')
      setSampleSets(sampleValue.items)
      const firstPost = sampleValue.items[0]?.items.slice().sort((a, b) => a.ordinal - b.ordinal)[0]
      if (firstPost) await openPost(firstPost)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void load() }, [api, projectId])

  const brief = briefs.find((item) => item.brief_id === briefId) || briefs[0] || null
  const activeSampleSet = sampleSets[0] || null
  const createSampleSet = async () => {
    const batchId = brief?.creative_batch_id
    if (!batchId) return
    setBusy(true)
    setError('')
    try {
      const value = await api.post<StudioSampleSet>('/api/v1/ad-studio/sample-sets', { batch_id: batchId }, { deadlineMs: STUDIO_GENERATION_DEADLINE_MS })
      setSampleSets((items) => [value, ...items.filter((item) => item.sample_set_id !== value.sample_set_id)])
      setNotice('Your five posts are ready.')
      const firstPost = value.items.slice().sort((a, b) => a.ordinal - b.ordinal)[0]
      if (firstPost) await openPost(firstPost)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const downloadSampleSet = async () => {
    if (!activeSampleSet?.download_sha256) return
    setBusy(true)
    setError('')
    try {
      const blob = await api.media(activeSampleSet.download_url, activeSampleSet.download_mime_type || 'application/zip', activeSampleSet.download_sha256)
      downloadBlob(blob, `ptw-studio-${activeSampleSet.sample_set_id}-five-posts.zip`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const wizardApplied = (nextRecipe: StudioRecipe, nextRender: StudioRender, validation?: StudioCreativeValidation | null) => {
    setRecipe(nextRecipe)
    setRender(nextRender)
    setRecoveredProposal(null)
    setActiveProposal(null)
    setCurrentValidation(validation || null)
    setNotice('New version saved.')
  }

  if (loading) return <Loading />
  if (!projectId) return <><PageHeader eyebrow="CREATE WITH AI" title="Ad Studio" /><Empty><Sparkles /><h2>No Project selected</h2><p>Select or create a Validation Project first.</p></Empty></>
  if (!briefs.length) return <><PageHeader eyebrow="CREATE WITH AI" title="Ad Studio" /><Empty><Sparkles /><h2>No approved Brief</h2><p>Approve a Product Brief before creating posts.</p></Empty></>

  return <>
    <PageHeader eyebrow="CREATE WITH AI" title="Ad Studio" />
    <p className="studio-page-intro">Choose a post, tell AI what to change, review it, and save.</p>
    {error && <ErrorState message={error} retry={() => void load()} />}
    {notice && <p className="landing-notice" role="status">{notice}</p>}
    {activeSampleSet
      ? <SampleGallery api={api} sampleSet={activeSampleSet} selectedRecipeId={selectedPost?.recipe_id || null} busy={busy} onOpen={(item) => void openPost(item)} onDownload={() => void downloadSampleSet()} />
      : <section className="panel studio-sample-empty"><Sparkles /><div><small>FIRST STEP</small><h2>Create your five posts</h2><p>AI creates five ready-to-use posts from the approved Brief.</p></div><button className="primary" disabled={busy || !brief?.creative_batch_id} onClick={() => void createSampleSet()}><Sparkles /> {busy ? 'Creating posts…' : 'Create 5 posts'}</button>{!brief?.creative_batch_id && <small>The approved Brief needs a completed five-Ad batch first.</small>}</section>}
    {selectedPost && recipe && render
      ? <div className="studio-ai-workspace">
        <PostPreview api={api} name={selectedPost.name} render={render} proposal={activeProposal} validation={activeProposal?.creative_validation || currentValidation} />
        <WizardPanel api={api} recipe={recipe} recoveredProposal={recoveredProposal} onProposalChange={setActiveProposal} onApplied={wizardApplied} />
      </div>
      : activeSampleSet && <Empty><WandSparkles /><h2>Choose a post</h2><p>Select one of the five posts above to change it with AI.</p></Empty>}
  </>
}
