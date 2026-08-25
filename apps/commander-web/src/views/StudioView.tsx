import {
  Box, ChevronDown, ChevronUp, Download, Eye, Image as ImageIcon, Layers3, Move,
  Package, Palette, Pencil, Play, Redo2, RefreshCcw, Save, Search, Send, Sparkles, Undo2,
  Upload, WandSparkles, X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { ApiClient } from '../api'
import { OwnerLessonProposals } from '../components/OwnerLessonProposals'
import { Empty, ErrorState, Loading, PageHeader } from '../components/State'
import type {
  ProductBrief, StudioBrandKit, StudioModifierInstance, StudioRecipe,
  StudioRecipeDocumentV2, StudioRender, StudioSampleSet, StudioSampleSetItem,
  StudioSourceAsset, StudioTemplate, StudioToolDefinition, StudioToolInstance,
  StudioWizardProposal,
} from '../types'

const COLOR_SOURCE = 'https://www.manypixels.co/blog/social-media-design/instagram-color'
const ADS_SOURCE = 'https://www.manypixels.co/blog/social-media-design/best-instagram-ads'
const STUDIO_GENERATION_DEADLINE_MS = 300_000
const STUDIO_WIZARD_DEADLINE_MS = 600_000
const ANGLE_LABELS: Record<StudioSampleSetItem['angle'], string> = {
  emotional: 'Emotional', practical: 'Practical', curiosity: 'Curiosity',
  authority: 'Authority', problem_first: 'Problem-first',
}
const placementLabels: Record<string, string> = {
  'studio.placement.instagram.feed_square.v1': 'Instagram feed · square',
  'studio.placement.instagram.feed_portrait.v1': 'Instagram feed · portrait',
  'studio.placement.instagram.story_vertical.v1': 'Instagram Story',
  'studio.placement.instagram.reel_vertical.v1': 'Instagram Reel',
  'studio.placement.instagram.carousel_square.v1': 'Instagram carousel · square',
  'studio.placement.instagram.carousel_portrait.v1': 'Instagram carousel · portrait',
  'studio.placement.tiktok.vertical_video.v1': 'TikTok vertical video',
}

function uuidv7() {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); let timestamp = Date.now()
  for (let index = 5; index >= 0; index -= 1) { bytes[index] = timestamp & 0xff; timestamp = Math.floor(timestamp / 256) }
  bytes[6] = (bytes[6] & 0x0f) | 0x70; bytes[8] = (bytes[8] & 0x3f) | 0x80
  const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`
}
function framesOf(document: StudioRecipe['document'] | StudioTemplate['document']) {
  return document.schema_version === 2 ? document.frames || [] : document.tools || []
}
function modifiersOf(document: StudioRecipe['document'] | StudioTemplate['document']) {
  return document.schema_version === 2 ? document.modifiers || [] : []
}
function shareOf(document: StudioRecipe['document']) {
  return document.schema_version === 2 ? document.share : { caption: '', alt_text: '' }
}
function frameTool(tool_id: string, z_index: number, text = ''): StudioToolInstance {
  const placements: Record<string, StudioToolInstance['frame']> = {
    'studio.frame.headline.v1': { x: .08, y: .12, width: .84, height: .24 },
    'studio.frame.offer.v1': { x: .08, y: .68, width: .84, height: .12 },
    'studio.frame.cta.v1': { x: .08, y: .83, width: .58, height: .1 },
    'studio.frame.media.v1': { x: 0, y: 0, width: 1, height: .62 },
  }
  return {
    instance_id: uuidv7(), tool_id, frame: placements[tool_id] || { x: .12, y: .25, width: .76, height: .25 }, z_index,
    params: text ? { text, color: '#FFFFFF', font_size: tool_id.includes('headline') ? 72 : 42, font_weight: 800, line_height: 1.05, align: 'left', vertical_align: 'top', max_lines: 4 } : {},
    timeline: null, source_asset_ids: [],
  }
}
function initialFrames(brief: ProductBrief) {
  return [frameTool('studio.frame.headline.v1', 1, brief.promise || brief.product || ''), frameTool('studio.frame.offer.v1', 2, brief.offer || ''), frameTool('studio.frame.cta.v1', 3, brief.cta || '')]
}
function fileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('Could not read the selected media file.')); reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || ''); reader.readAsDataURL(file) })
}
function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob); const link = window.document.createElement('a'); link.href = url; link.download = fileName; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
function useAuthenticatedUrl(api: ApiClient, path?: string, mime?: string, sha256?: string) {
  const [url, setUrl] = useState(''); const [error, setError] = useState('')
  useEffect(() => {
    let active = true; let objectUrl = ''; setUrl(''); setError('')
    if (!path || !mime || !sha256) return () => { active = false }
    void api.media(path, mime, sha256).then((blob) => { if (!active) return; objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) }).catch((cause: Error) => { if (active) setError(cause.message) })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, path, mime, sha256])
  return { url, error }
}

function SourceMedia({ api, asset, fit = 'cover', focalX = .5, focalY = .5 }: { api: ApiClient; asset: StudioSourceAsset | null; fit?: string; focalX?: number; focalY?: number }) {
  const path = asset?.asset_url || (asset ? `/api/v1/ad-studio/sources/${asset.source_asset_id}/asset` : '')
  const { url, error } = useAuthenticatedUrl(api, path, asset?.mime_type, asset?.bytes_sha256)
  if (!asset) return <span className="studio-media-empty"><ImageIcon />Choose a Project source</span>
  if (error) return <span className="studio-media-empty"><ImageIcon />Source preview unavailable</span>
  if (!url) return <span className="studio-media-empty studio-media-loading">Loading source…</span>
  const style = { objectFit: fit === 'contain' ? 'contain' : 'cover', objectPosition: `${focalX * 100}% ${focalY * 100}%` } as CSSProperties
  return asset.mime_type.startsWith('video/') ? <video src={url} muted playsInline aria-label={asset.title} style={style} /> : <img src={url} alt={asset.title} style={style} />
}
function RenderImage({ api, render, alt, compact = false }: { api: ApiClient; render: StudioRender; alt: string; compact?: boolean }) {
  const { url, error } = useAuthenticatedUrl(api, render.asset_url, render.mime_type, render.bytes_sha256)
  if (error) return <div className="studio-render-fallback"><ImageIcon /><span>Render unavailable</span></div>
  if (!url) return <div className="studio-render-fallback"><span>Loading render…</span></div>
  return render.mime_type === 'video/mp4' ? <video src={url} controls={!compact} playsInline muted aria-label={alt} /> : <img src={url} alt={alt} />
}
function RenderPreview({ api, render }: { api: ApiClient; render: StudioRender }) {
  const { url, error } = useAuthenticatedUrl(api, render.asset_url, render.mime_type, render.bytes_sha256)
  if (error) return <ErrorState message={error} />
  if (!url) return <Loading />
  const downloadManifest = () => downloadBlob(new Blob([JSON.stringify(render.manifest, null, 2)], { type: 'application/json' }), `ptw-studio-${render.render_id}-manifest.json`)
  return <div className="studio-render-preview">
    {render.mime_type === 'video/mp4' ? <video src={url} controls playsInline muted aria-label="Rendered Studio video" /> : <img src={url} alt="Rendered Studio creative" />}
    <dl><dt>Render UUID</dt><dd>{render.render_id}</dd><dt>SHA-256</dt><dd>{render.bytes_sha256}</dd><dt>Recipe UUID</dt><dd>{render.recipe_id}</dd></dl>
    <a className="secondary studio-download" href={url} download={`ptw-studio-${render.render_id}.${render.mime_type === 'video/mp4' ? 'mp4' : 'jpg'}`}><Download /> Download media</a>
    <button className="secondary studio-download" onClick={downloadManifest}><Download /> Download JSON manifest</button>
  </div>
}
function RenderDownloadButton({ api, render, name }: { api: ApiClient; render: StudioRender; name: string }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const download = async () => {
    setBusy(true); setError('')
    try { const blob = await api.media(render.asset_url, render.mime_type, render.bytes_sha256); downloadBlob(blob, `${name.replace(/[^a-z0-9\u0400-\u04ff]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'ptw-studio-post'}.jpg`) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  return <>{<button className="secondary" disabled={busy} onClick={() => void download()} aria-label={`Download ${name} JPEG`}><Download /> {busy ? 'Downloading…' : 'Download JPEG'}</button>}{error && <small className="studio-card-error">{error}</small>}</>
}
function frameStyle(item: StudioToolInstance): CSSProperties {
  const vertical = String(item.params.vertical_align || 'top'); const align = String(item.params.align || 'left')
  return {
    left: `${item.frame.x * 100}%`, top: `${item.frame.y * 100}%`, width: `${item.frame.width * 100}%`, height: `${item.frame.height * 100}%`, zIndex: item.z_index,
    color: String(item.params.color || '#FFFFFF'), background: item.tool_id === 'studio.frame.shape.v1' ? String(item.params.background || '#FFFFFF') : undefined,
    borderRadius: item.tool_id === 'studio.frame.shape.v1' ? `${Number(item.params.radius || 0) / 10}%` : undefined, opacity: Number(item.params.opacity ?? 1),
    textAlign: align as CSSProperties['textAlign'], fontSize: `${Math.max(8, Number(item.params.font_size || 36)) / 10}cqw`, fontWeight: Number(item.params.font_weight || 800), lineHeight: Number(item.params.line_height || 1.05),
    alignItems: vertical === 'middle' ? 'center' : vertical === 'bottom' ? 'flex-end' : 'flex-start', justifyContent: align === 'center' ? 'center' : align === 'right' ? 'flex-end' : 'flex-start',
  }
}
function CanvasFrame({ api, item, asset, editing, selected, onBegin, onMove, onEnd, onKey }: {
  api: ApiClient; item: StudioToolInstance; asset: StudioSourceAsset | null; editing: boolean; selected: boolean
  onBegin: (event: React.PointerEvent, item: StudioToolInstance, mode: 'move' | 'resize') => void; onMove: (event: React.PointerEvent) => void; onEnd: () => void; onKey: (event: React.KeyboardEvent, item: StudioToolInstance) => void
}) {
  const isMedia = ['studio.frame.media.v1', 'studio.frame.product.v1', 'studio.frame.logo.v1'].includes(item.tool_id); const isShape = item.tool_id === 'studio.frame.shape.v1'
  const content = isMedia ? <SourceMedia api={api} asset={asset} fit={String(item.params.fit || (item.tool_id === 'studio.frame.logo.v1' ? 'contain' : 'cover'))} focalX={Number(item.params.focal_x ?? .5)} focalY={Number(item.params.focal_y ?? .5)} /> : isShape ? null : <span className="studio-frame-text" style={{ WebkitLineClamp: Number(item.params.max_lines || 5) }}>{String(item.params.text || '')}</span>
  if (!editing) return <div className={`studio-frame clean ${isMedia ? 'media' : ''} ${isShape ? 'shape' : ''}`} style={frameStyle(item)}>{content}</div>
  return <button className={`studio-frame editing ${isMedia ? 'media' : ''} ${isShape ? 'shape' : ''} ${selected ? 'selected' : ''}`} style={frameStyle(item)} onPointerDown={(event) => onBegin(event, item, 'move')} onPointerMove={onMove} onPointerUp={onEnd} onPointerCancel={onEnd} onKeyDown={(event) => onKey(event, item)} aria-label={`${item.tool_id} frame`}>
    {content}<small>{item.tool_id}</small><i className="studio-resize-handle" aria-hidden="true" onPointerDown={(event) => onBegin(event, item, 'resize')} />
  </button>
}
function SampleGallery({ api, sampleSet, selectedRecipeId, busy, onOpen, onDownload }: { api: ApiClient; sampleSet: StudioSampleSet; selectedRecipeId: string | null; busy: boolean; onOpen: (item: StudioSampleSetItem) => void; onDownload: () => void }) {
  return <section className="panel studio-sample-set" aria-label="Five ready-to-share Studio posts">
    <header><div><small>READY-TO-SHARE SAMPLE SET</small><h2>Five real editable posts</h2><p>Each post is a reusable template, immutable recipe, clean 1080×1080 render, caption, and alt text.</p></div><button className="primary" disabled={busy || !sampleSet.download_sha256} onClick={onDownload}><Package /> Download all 5</button></header>
    <div className="studio-sample-grid">{[...sampleSet.items].sort((a, b) => a.ordinal - b.ordinal).map((item) => <article key={item.recipe_id} className={selectedRecipeId === item.recipe_id ? 'selected' : ''}>
      <button className="studio-sample-open" onClick={() => onOpen(item)} aria-label={`Open ${item.name} editable post`}><div className="studio-sample-art"><RenderImage api={api} render={item.render} alt={item.alt_text || item.name} compact /></div><span className="studio-angle">{String(item.ordinal + 1).padStart(2, '0')} · {ANGLE_LABELS[item.angle]}</span><strong>{item.name}</strong><span className="studio-sample-caption">{item.caption}</span></button>
      <div className="studio-sample-actions"><button className="secondary" onClick={() => onOpen(item)}><Pencil /> Edit</button><RenderDownloadButton api={api} render={item.render} name={item.name} /></div>
    </article>)}</div>
  </section>
}
function WizardPreview({ api, proposal }: { api: ApiClient; proposal: StudioWizardProposal }) {
  const { url, error } = useAuthenticatedUrl(api, proposal.preview_url, proposal.preview_mime_type || 'image/jpeg', proposal.preview_sha256)
  if (error) return <ErrorState message={error} />
  if (!url) return <div className="studio-wizard-media-loading" role="status"><RefreshCcw className="spin" /> Loading the verified preview…</div>
  return <img className="studio-wizard-preview" src={url} alt="Preview of the proposed AI Studio update" />
}
function elapsedLabel(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}
function WizardPanel({ api, recipe, target, recoveredProposal, onApplied }: { api: ApiClient; recipe: StudioRecipe; target: StudioToolInstance | null; recoveredProposal: StudioWizardProposal | null; onApplied: (recipe: StudioRecipe, render: StudioRender) => void }) {
  const [instruction, setInstruction] = useState('')
  const [scope, setScope] = useState<'component' | 'post'>(target ? 'component' : 'post')
  const [proposal, setProposal] = useState<StudioWizardProposal | null>(recoveredProposal)
  const [operation, setOperation] = useState<'preview' | 'apply' | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState<{ message: string; operation: 'preview' | 'apply' } | null>(null)
  const busy = operation !== null
  useEffect(() => { if (!target) setScope('post') }, [target?.instance_id])
  useEffect(() => { setProposal(recoveredProposal); setInstruction(recoveredProposal?.instruction || '') }, [recipe.recipe_id, recoveredProposal?.proposal_id])
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
    setOperation('preview'); setError(null); setProposal(null)
    try {
      setProposal(await api.post<StudioWizardProposal>(`/api/v1/ad-studio/recipes/${recipe.recipe_id}/wizard-proposals`, {
        instruction: normalizedInstruction,
        target_instance_id: scope === 'component' ? target?.instance_id || null : null,
      }, { deadlineMs: STUDIO_WIZARD_DEADLINE_MS }))
    } catch (cause) {
      setError({ message: (cause as Error).message, operation: 'preview' })
    } finally {
      setOperation(null)
    }
  }
  const apply = async () => {
    if (!proposal || busy) return
    setOperation('apply'); setError(null)
    try {
      const result = await api.post<{ proposal: StudioWizardProposal; recipe: StudioRecipe; render: StudioRender }>(`/api/v1/ad-studio/wizard-proposals/${proposal.proposal_id}/apply`, {}, { deadlineMs: STUDIO_WIZARD_DEADLINE_MS })
      setProposal(result.proposal); onApplied(result.recipe, result.render); setInstruction('')
    } catch (cause) {
      setError({ message: (cause as Error).message, operation: 'apply' })
    } finally {
      setOperation(null)
    }
  }
  const retry = () => error?.operation === 'apply' ? void apply() : void preview()
  const statusTitle = operation === 'apply' ? 'Applying the approved preview…' : 'Creating your review preview…'
  const statusDetail = operation === 'apply'
    ? 'The reviewed change is being saved and rendered as a new version.'
    : elapsedSeconds < 30
      ? 'Your request is running. The post has not changed.'
      : 'Still working. AI and image verification can take several minutes; keep this tab open.'
  return <section className="panel studio-wizard" aria-label="AI wizard" aria-busy={busy}>
    <header><WandSparkles /><div><small>AI WIZARD · REVIEW FIRST</small><h2>Revise this open post</h2></div></header>
    <p>Describe the result you want. The wizard creates one review preview; only Apply saves it as a new version.</p>
    <label>Scope
      <select disabled={busy} value={scope} onChange={(event) => setScope(event.target.value as 'component' | 'post')}>
        <option value="post">This post · all elements</option>
        {target && <option value="component">Selected component · {target.tool_id}</option>}
      </select>
    </label>
    <p className="studio-wizard-scope-note">{scope === 'post'
      ? 'This revises only the post open above. The other four posts and your saved templates stay unchanged.'
      : 'Only the selected component can change. The wizard cannot expand the request to the rest of the post.'}</p>
    <label>Instruction
      <textarea disabled={busy} rows={3} maxLength={1000} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Make the headline calmer and move it away from the face" />
    </label>
    <p className="studio-wizard-policy-note">Use approved Project photos for people. AI-generated media is limited to abstract or symbolic graphics without people, faces, logos, or embedded text.</p>
    <button className="primary" disabled={busy || !instruction.trim()} onClick={() => void preview()}>
      {operation === 'preview' ? <RefreshCcw className="spin" /> : <WandSparkles />}
      {operation === 'preview' ? 'Creating preview…' : 'Create review preview'}
    </button>
    {!operation && !proposal && !error && <p className="studio-wizard-submit-note">This may take several minutes. Nothing is applied automatically.</p>}
    {operation && <div className="studio-wizard-progress" role="status" aria-live="polite">
      <RefreshCcw className="spin" />
      <div><strong>{statusTitle}</strong><p>{statusDetail}</p><small aria-hidden="true">Elapsed {elapsedLabel(elapsedSeconds)} · 10-minute request limit</small></div>
      <div className="studio-wizard-progress-bar" role="progressbar" aria-label={statusTitle} aria-valuetext="In progress" />
    </div>}
    {error && <div className="studio-wizard-error" role="alert"><strong>{error.operation === 'apply' ? 'Could not apply the preview.' : 'Could not create the preview.'}</strong><p>{error.message}</p><button className="secondary" disabled={busy} onClick={retry}><RefreshCcw /> Try again</button></div>}
    {proposal && <div className="studio-wizard-proposal">
      {proposal.status === 'previewed' && <p className="studio-wizard-ready" role="status"><strong>Preview ready — nothing changed yet.</strong><span>Compare the image below, then apply it only if it is right.</span></p>}
      <div className="studio-wizard-patch-header"><span className="studio-angle">PROPOSED PATCH</span><code>{proposal.before_sha256.slice(0, 10)} → {proposal.after_sha256.slice(0, 10)}</code></div>
      {proposal.preview_sha256 ? <WizardPreview api={api} proposal={proposal} /> : <p className="studio-preview-pending">Preview render is being verified.</p>}
      <details><summary>Review typed diff</summary><pre>{JSON.stringify(proposal.patch, null, 2)}</pre></details>
      {proposal.status === 'previewed' && <button className="primary" disabled={busy} onClick={() => void apply()}>{operation === 'apply' ? <RefreshCcw className="spin" /> : <Save />} {operation === 'apply' ? 'Applying new version…' : 'Apply preview as new version'}</button>}
      {proposal.status === 'applied' && <p role="status">Applied as immutable recipe {proposal.applied_recipe_id}.</p>}
    </div>}
  </section>
}

export function StudioView({ api, projectId }: { api: ApiClient; projectId: string | null }) {
  const [catalog, setCatalog] = useState<StudioToolDefinition[] | null>(null)
  const [briefs, setBriefs] = useState<ProductBrief[]>([]); const [kits, setKits] = useState<StudioBrandKit[]>([]); const [assets, setAssets] = useState<StudioSourceAsset[]>([])
  const [recipes, setRecipes] = useState<StudioRecipe[]>([]); const [templates, setTemplates] = useState<StudioTemplate[]>([]); const [sampleSets, setSampleSets] = useState<StudioSampleSet[]>([])
  const [activeSampleSetId, setActiveSampleSetId] = useState(''); const [briefId, setBriefId] = useState(''); const [kitId, setKitId] = useState(''); const [placementId, setPlacementId] = useState('studio.placement.instagram.feed_square.v1')
  const [instances, setInstances] = useState<StudioToolInstance[]>([]); const [modifiers, setModifiers] = useState<StudioModifierInstance[]>([]); const [selectedId, setSelectedId] = useState('')
  const [past, setPast] = useState<StudioToolInstance[][]>([]); const [future, setFuture] = useState<StudioToolInstance[][]>([]); const [parentRecipeId, setParentRecipeId] = useState<string | null>(null)
  const [savedRecipe, setSavedRecipe] = useState<StudioRecipe | null>(null); const [render, setRender] = useState<StudioRender | null>(null); const [renderHistory, setRenderHistory] = useState<StudioRender[]>([])
  const [recoveredWizardProposal, setRecoveredWizardProposal] = useState<StudioWizardProposal | null>(null)
  const [mode, setMode] = useState<'preview' | 'edit'>('preview'); const [caption, setCaption] = useState(''); const [altText, setAltText] = useState(''); const [busy, setBusy] = useState(false)
  const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [feedback, setFeedback] = useState(''); const [proposalRevision, setProposalRevision] = useState(0)
  const [pexelsQuery, setPexelsQuery] = useState(''); const [pexels, setPexels] = useState<Array<Record<string, string | number>>>([]); const [templateName, setTemplateName] = useState('')
  const [kitForm, setKitForm] = useState({ name: 'Natal', colors: '#06090D, #F8FAFC, #00D8FF, #59616C', font: 'Inter', tone: 'Clear, calm, specific, human.', logoAsset: '' })
  const drag = useRef<{ id: string; mode: 'move' | 'resize'; x: number; y: number; frame: StudioToolInstance['frame']; snapshot: StudioToolInstance[] } | null>(null)
  const templateApplyRequests = useRef(new Map<string, string>())

  const load = async () => {
    if (!projectId) { setCatalog([]); setBriefs([]); setKits([]); setAssets([]); setRecipes([]); setTemplates([]); setSampleSets([]); return }
    const [toolsValue, briefValue, kitValue, assetValue, recipeValue, templateValue] = await Promise.all([
      api.get<{ items: StudioToolDefinition[] }>('/api/v1/ad-studio/tools'), api.get<{ items: ProductBrief[] }>(`/api/v1/briefs?limit=100&project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: StudioBrandKit[] }>(`/api/v1/ad-studio/brand-kits?project_id=${encodeURIComponent(projectId)}`), api.get<{ items: StudioSourceAsset[] }>(`/api/v1/ad-studio/sources?project_id=${encodeURIComponent(projectId)}`),
      api.get<{ items: StudioRecipe[] }>(`/api/v1/ad-studio/recipes?project_id=${encodeURIComponent(projectId)}`), api.get<{ items: StudioTemplate[] }>(`/api/v1/ad-studio/templates?project_id=${encodeURIComponent(projectId)}`),
    ])
    const approved = briefValue.items.filter((brief) => brief.status === 'completed' && brief.approved)
    setCatalog(toolsValue.items); setBriefs(approved); setKits(kitValue.items); setAssets(assetValue.items); setRecipes(recipeValue.items); setTemplates(templateValue.items)
    setBriefId((current) => approved.some((item) => item.brief_id === current) ? current : approved[0]?.brief_id || ''); setKitId((current) => kitValue.items.some((item) => item.brand_kit_id === current) ? current : kitValue.items[0]?.brand_kit_id || '')
    try { const value = await api.get<{ items: StudioSampleSet[] }>(`/api/v1/ad-studio/sample-sets?project_id=${encodeURIComponent(projectId)}`); setSampleSets(value.items); setActiveSampleSetId((current) => value.items.some((item) => item.sample_set_id === current) ? current : value.items[0]?.sample_set_id || '') } catch { setSampleSets([]) }
  }
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [api, projectId])
  const brief = briefs.find((item) => item.brief_id === briefId) || null; const placement = catalog?.find((item) => item.tool_id === placementId); const mediaKind = placement?.supported_placements[0] || 'static'
  const kit = kits.find((item) => item.brand_kit_id === kitId) || null; const selected = instances.find((item) => item.instance_id === selectedId) || null; const selectedAsset = assets.find((item) => item.source_asset_id === selected?.source_asset_ids[0]) || null
  const activeSampleSet = sampleSets.find((item) => item.sample_set_id === activeSampleSetId) || sampleSets[0] || null
  useEffect(() => { if (!brief || instances.length) return; setInstances(initialFrames(brief)); setCaption(''); setAltText('') }, [briefId, brief?.offer, brief?.cta])

  const commit = (next: StudioToolInstance[]) => { setPast((items) => [...items.slice(-49), instances]); setFuture([]); setInstances(next); setSavedRecipe(null); setRender(null) }
  const undo = () => { const previous = past.at(-1); if (!previous) return; setFuture((items) => [instances, ...items]); setInstances(previous); setPast((items) => items.slice(0, -1)); setSavedRecipe(null); setRender(null) }
  const redo = () => { const next = future[0]; if (!next) return; setPast((items) => [...items, instances]); setInstances(next); setFuture((items) => items.slice(1)); setSavedRecipe(null); setRender(null) }
  const updateSelected = (change: Partial<StudioToolInstance>) => { if (selected) commit(instances.map((item) => item.instance_id === selected.instance_id ? { ...item, ...change } : item)) }
  const updateParams = (change: StudioToolInstance['params']) => selected && updateSelected({ params: { ...selected.params, ...change } })
  const updateFrame = (key: keyof StudioToolInstance['frame'], raw: number) => {
    if (!selected) return; const frame = { ...selected.frame }; const value = Math.max(0, Math.min(1, raw || 0))
    if (key === 'x') frame.x = Math.min(value, 1 - frame.width); if (key === 'y') frame.y = Math.min(value, 1 - frame.height); if (key === 'width') frame.width = Math.max(.01, Math.min(value, 1 - frame.x)); if (key === 'height') frame.height = Math.max(.01, Math.min(value, 1 - frame.y)); updateSelected({ frame })
  }
  const addTool = (definition: StudioToolDefinition) => {
    if (definition.kind !== 'frame') { setModifiers((items) => [...items, { instance_id: uuidv7(), tool_id: definition.tool_id, params: { ...definition.defaults } as StudioModifierInstance['params'] }]); setNotice(`${definition.label} added as a recipe modifier.`); return }
    if (['offer', 'cta'].some((name) => definition.tool_id === `studio.frame.${name}.v1` && instances.some((item) => item.tool_id === definition.tool_id))) return
    const text = definition.tool_id === 'studio.frame.offer.v1' ? brief?.offer || '' : definition.tool_id === 'studio.frame.cta.v1' ? brief?.cta || '' : ''; const item = frameTool(definition.tool_id, Math.max(0, ...instances.map((value) => value.z_index)) + 1, text)
    if (definition.tool_id === 'studio.frame.logo.v1' && kit?.document.logo_source_asset_id) item.source_asset_ids = [kit.document.logo_source_asset_id]; commit([...instances, item]); setSelectedId(item.instance_id); setMode('edit')
  }
  const changePlacement = (next: string) => { setPlacementId(next); setSavedRecipe(null); setRender(null) }
  const removeSelected = () => { if (!selected || ['studio.frame.offer.v1', 'studio.frame.cta.v1'].includes(selected.tool_id)) return; commit(instances.filter((item) => item.instance_id !== selected.instance_id)); setSelectedId('') }
  const moveLayer = (direction: -1 | 1) => { if (!selected) return; const ordered = [...instances].sort((a, b) => a.z_index - b.z_index); const index = ordered.findIndex((item) => item.instance_id === selected.instance_id); const swap = index + direction; if (swap < 0 || swap >= ordered.length) return; const first = ordered[index].z_index; ordered[index].z_index = ordered[swap].z_index; ordered[swap].z_index = first; commit([...ordered].sort((a, b) => a.z_index - b.z_index)) }
  const keyboardMove = (event: React.KeyboardEvent, item: StudioToolInstance) => { const delta = event.shiftKey ? .05 : .01; const frame = { ...item.frame }; if (event.key === 'ArrowLeft') frame.x = Math.max(0, frame.x - delta); else if (event.key === 'ArrowRight') frame.x = Math.min(1 - frame.width, frame.x + delta); else if (event.key === 'ArrowUp') frame.y = Math.max(0, frame.y - delta); else if (event.key === 'ArrowDown') frame.y = Math.min(1 - frame.height, frame.y + delta); else return; event.preventDefault(); setSelectedId(item.instance_id); commit(instances.map((value) => value.instance_id === item.instance_id ? { ...value, frame } : value)) }
  const beginDrag = (event: React.PointerEvent, item: StudioToolInstance, dragMode: 'move' | 'resize') => { event.stopPropagation(); event.currentTarget.setPointerCapture?.(event.pointerId); setSelectedId(item.instance_id); drag.current = { id: item.instance_id, mode: dragMode, x: event.clientX, y: event.clientY, frame: { ...item.frame }, snapshot: instances } }
  const dragMove = (event: React.PointerEvent) => { const active = drag.current; if (!active) return; const canvas = (event.currentTarget as HTMLElement).closest('.studio-canvas')?.getBoundingClientRect(); if (!canvas) return; const dx = (event.clientX - active.x) / canvas.width; const dy = (event.clientY - active.y) / canvas.height; const snap = (value: number) => Math.round(value * 100) / 100; setInstances((items) => items.map((item) => { if (item.instance_id !== active.id) return item; const frame = active.mode === 'resize' ? { ...item.frame, width: snap(Math.max(.04, Math.min(1 - active.frame.x, active.frame.width + dx))), height: snap(Math.max(.04, Math.min(1 - active.frame.y, active.frame.height + dy))) } : { ...item.frame, x: snap(Math.max(0, Math.min(1 - item.frame.width, active.frame.x + dx))), y: snap(Math.max(0, Math.min(1 - item.frame.height, active.frame.y + dy))) }; return { ...item, frame } })) }
  const endDrag = () => { const completed = drag.current; if (!completed) return; drag.current = null; setPast((items) => [...items.slice(-49), completed.snapshot]); setFuture([]); setSavedRecipe(null); setRender(null) }

  const createKit = async () => { if (!projectId) return; setBusy(true); setError(''); try { const value = await api.post<StudioBrandKit>('/api/v1/ad-studio/brand-kits', { project_id: projectId, parent_brand_kit_id: kitId || null, document: { name: kitForm.name, colors: kitForm.colors.split(',').map((item) => item.trim()), fonts: [kitForm.font], tone_notes: kitForm.tone, logo_source_asset_id: kitForm.logoAsset || null } }); setKits((items) => [value, ...items]); setKitId(value.brand_kit_id); setNotice(`Brand kit ${value.brand_kit_id} saved.`) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const saveTemplate = async () => {
    if (!projectId || !templateName.trim()) return; setBusy(true); setError('')
    try {
      const frames = instances.map((item) => ({ ...item, params: item.tool_id === 'studio.frame.offer.v1' ? { ...item.params, text: '{{offer}}' } : item.tool_id === 'studio.frame.cta.v1' ? { ...item.params, text: '{{cta}}' } : item.params }))
      const offer = frames.find((item) => item.tool_id === 'studio.frame.offer.v1'); const cta = frames.find((item) => item.tool_id === 'studio.frame.cta.v1')
      if (!offer || !cta) throw new Error('A reusable template requires its protected offer and CTA frames.')
      const value = await api.post<StudioTemplate>('/api/v1/ad-studio/templates', { project_id: projectId, name: templateName.trim(), document: { schema_version: 2, placement_tool_id: placementId, duration_seconds: null, frame_rate: null, frames, modifiers, strategy_ids: ['studio.strategy.one_message.v1'], bindings: { offer: { target: `/frames/${offer.instance_id}/params/text`, source: 'brief.offer' }, cta: { target: `/frames/${cta.instance_id}/params/text`, source: 'brief.cta' } } } })
      setTemplates((items) => [value, ...items]); setTemplateName(''); setNotice(`Template “${value.name}” saved as ${value.template_id}.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const applyTemplate = async (template: StudioTemplate) => {
    if (!brief || !kitId) return
    if (template.document.schema_version === 1) {
      const rebound = framesOf(template.document).map((item) => ({ ...item, instance_id: uuidv7(), frame: { ...item.frame }, params: { ...item.params, ...(item.tool_id === 'studio.frame.offer.v1' ? { text: brief.offer || '' } : {}), ...(item.tool_id === 'studio.frame.cta.v1' ? { text: brief.cta || '' } : {}) } }))
      commit(rebound); setModifiers([]); setPlacementId(template.placement_tool_id); setSelectedId(''); setParentRecipeId(null); setMode('preview'); setNotice(`Legacy template “${template.name}” applied and rebound to the selected Brief.`); return
    }
    const linked = activeSampleSet?.items.find((item) => item.template_id === template.template_id)
    setBusy(true); setError('')
    try {
      const requestId = templateApplyRequests.current.get(template.template_id) || uuidv7(); templateApplyRequests.current.set(template.template_id, requestId)
      const value = await api.post<{ template_id: string; recipe: StudioRecipe; created: boolean }>(`/api/v1/ad-studio/templates/${template.template_id}/apply`, { request_id: requestId, brief_id: brief.brief_id, creative_id: linked?.source_creative_id || null, brand_kit_id: kitId }, { deadlineMs: STUDIO_GENERATION_DEADLINE_MS })
      templateApplyRequests.current.delete(template.template_id); setRecipes((items) => [value.recipe, ...items.filter((item) => item.recipe_id !== value.recipe.recipe_id)]); await openRecipe(value.recipe); setNotice(`Template “${template.name}” resolved and saved as immutable recipe ${value.recipe.recipe_id}.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const upload = async (file?: File) => { if (!file || !projectId) return; setBusy(true); setError(''); try { const value = await api.post<StudioSourceAsset>('/api/v1/ad-studio/sources/upload', { project_id: projectId, title: file.name, mime_type: file.type, base64: await fileBase64(file) }); setAssets((items) => [value, ...items.filter((item) => item.source_asset_id !== value.source_asset_id)]); setNotice(`Source ${value.source_asset_id} imported.`) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const searchPexels = async () => { if (!pexelsQuery.trim()) return; setBusy(true); setError(''); try { setPexels((await api.get<{ items: Array<Record<string, string | number>> }>(`/api/v1/ad-studio/pexels/search?query=${encodeURIComponent(pexelsQuery.trim())}`)).items) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const importPexels = async (photoId: string) => { if (!projectId) return; setBusy(true); setError(''); try { const value = await api.post<StudioSourceAsset>('/api/v1/ad-studio/sources/pexels', { project_id: projectId, query: pexelsQuery.trim(), photo_id: photoId }); setAssets((items) => [value, ...items.filter((item) => item.source_asset_id !== value.source_asset_id)]); setNotice(`Pexels source ${value.source_asset_id} imported with attribution.`) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const saveRecipe = async () => {
    if (!projectId || !brief || !kitId || !catalog) return null; setBusy(true); setError(''); setNotice('')
    try {
      const document: StudioRecipeDocumentV2 = { schema_version: 2, parent_recipe_id: parentRecipeId, placement_tool_id: placementId, duration_seconds: null, frame_rate: null, frames: instances, modifiers, strategy_ids: ['studio.strategy.one_message.v1'], validation_ids: catalog.filter((item) => item.kind === 'guard').map((item) => item.tool_id), source_reference_ids: [COLOR_SOURCE, ADS_SOURCE], share: { caption: caption.trim(), alt_text: altText.trim() } }
      const value = await api.post<StudioRecipe>('/api/v1/ad-studio/recipes', { project_id: projectId, brief_id: brief.brief_id, brand_kit_id: kitId, document })
      setSavedRecipe(value); setRecoveredWizardProposal(null); setParentRecipeId(value.recipe_id); setRecipes((items) => [value, ...items.filter((item) => item.recipe_id !== value.recipe_id)]); setNotice(`Immutable recipe ${value.recipe_id} saved.`)
      try { setRenderHistory((await api.get<{ items: StudioRender[] }>(`/api/v1/ad-studio/recipes/${value.recipe_id}/renders`)).items) } catch { setRenderHistory([]) }
      return value
    } catch (cause) { setError((cause as Error).message); return null } finally { setBusy(false) }
  }
  const renderRecipe = async () => { setBusy(true); setError(''); try { const recipe = savedRecipe || await saveRecipe(); if (!recipe) return; const value = await api.post<StudioRender>(`/api/v1/ad-studio/recipes/${recipe.recipe_id}/render`, {}); setRender(value); setRenderHistory((items) => [value, ...items.filter((item) => item.render_id !== value.render_id)]); setMode('preview'); setNotice(`Authoritative render ${value.render_id} created with embedded Studio metadata.`) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const publish = async () => { if (!render) return; setBusy(true); setError(''); try { const value = await api.post<StudioRender>(`/api/v1/ad-studio/renders/${render.render_id}/publish`, {}); setRender(value); setNotice('Published as an immutable training example. Add feedback below.') } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const submitFeedback = async () => { if (!render || !feedback.trim()) return; setBusy(true); setError(''); try { const value = await api.post<{ feedback_id: string; proposal_id: string }>(`/api/v1/ad-studio/renders/${render.render_id}/feedback`, { comment: feedback.trim() }); setFeedback(''); setProposalRevision((item) => item + 1); setNotice(`Feedback ${value.feedback_id} saved; future-rule proposal ${value.proposal_id} is ready.`) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const openRecipe = async (recipe: StudioRecipe, nextRender?: StudioRender | null) => {
    const frames = framesOf(recipe.document); const share = shareOf(recipe.document); setBriefId(recipe.brief_id); setKitId(recipe.brand_kit_id); setPlacementId(recipe.document.placement_tool_id); setInstances(frames); setModifiers(modifiersOf(recipe.document)); setCaption(share.caption); setAltText(share.alt_text); setParentRecipeId(recipe.recipe_id); setSavedRecipe(recipe); setRender(nextRender || null); setPast([]); setFuture([]); setSelectedId(''); setMode('preview'); setRecoveredWizardProposal(null)
    const [rendersResult, proposalsResult] = await Promise.allSettled([
      api.get<{ items: StudioRender[] }>(`/api/v1/ad-studio/recipes/${recipe.recipe_id}/renders`),
      api.get<{ items: StudioWizardProposal[] }>(`/api/v1/ad-studio/recipes/${recipe.recipe_id}/wizard-proposals`),
    ])
    setRenderHistory(rendersResult.status === 'fulfilled' ? rendersResult.value.items : nextRender ? [nextRender] : [])
    setRecoveredWizardProposal(proposalsResult.status === 'fulfilled' ? proposalsResult.value.items[0] || null : null)
  }
  const createSampleSet = async () => {
    const batchId = brief?.creative_batch_id; if (!batchId) return; setBusy(true); setError('')
    try { const value = await api.post<StudioSampleSet>('/api/v1/ad-studio/sample-sets', { batch_id: batchId }, { deadlineMs: STUDIO_GENERATION_DEADLINE_MS }); setSampleSets((items) => [value, ...items.filter((item) => item.sample_set_id !== value.sample_set_id)]); setActiveSampleSetId(value.sample_set_id); setNotice(`Five share-ready editable posts were created from batch ${value.batch_id}.`); if (value.items[0]) await openRecipe(value.items[0].recipe, value.items[0].render) }
    catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }
  const downloadSampleSet = async () => { if (!activeSampleSet?.download_sha256) return; setBusy(true); setError(''); try { const blob = await api.media(activeSampleSet.download_url, activeSampleSet.download_mime_type || 'application/zip', activeSampleSet.download_sha256); downloadBlob(blob, `ptw-studio-${activeSampleSet.sample_set_id}-five-posts.zip`) } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) } }
  const wizardApplied = (recipe: StudioRecipe, nextRender: StudioRender) => { setRecipes((items) => [recipe, ...items.filter((item) => item.recipe_id !== recipe.recipe_id)]); void openRecipe(recipe, nextRender); setNotice(`AI update applied as immutable recipe ${recipe.recipe_id}.`) }
  const compatible = useMemo(() => (catalog || []).filter((item) => item.kind !== 'placement' && item.kind !== 'guard' && item.supported_placements.includes(mediaKind)), [catalog, mediaKind])

  if (!catalog) return error ? <ErrorState message={error} retry={() => void load()} /> : <Loading />
  if (!projectId) return <><PageHeader eyebrow="STAGE 2 · MANUAL TRAINING" title="Ad Studio" /><Empty><Sparkles /><h2>No Project selected</h2><p>Select or create a Validation Project first.</p></Empty></>
  if (!briefs.length) return <><PageHeader eyebrow="STAGE 2 · MANUAL TRAINING" title="Ad Studio" /><Empty><Sparkles /><h2>No approved Brief</h2><p>Studio recipes must retain an approved Product Brief’s exact offer and CTA.</p></Empty></>

  return <>
    <PageHeader eyebrow="STAGE 2 · EDITABLE SHARE ASSETS" title="Ad Studio" />
    {error && <ErrorState message={error} />}{notice && <p className="landing-notice" role="status">{notice}</p>}
    {activeSampleSet ? <SampleGallery api={api} sampleSet={activeSampleSet} selectedRecipeId={savedRecipe?.recipe_id || null} busy={busy} onOpen={(item) => void openRecipe(item.recipe, item.render)} onDownload={() => void downloadSampleSet()} />
      : <section className="panel studio-sample-empty"><Sparkles /><div><small>REAL DATA · FIVE DISTINCT ANGLES</small><h2>Create five ready-to-share posts</h2><p>Build five editable square templates from the selected approved Brief and completed Ad batch. Licensed photos, Natal branding, exact offer/CTA, captions, alt text, and clean JPEGs stay linked.</p></div><button className="primary" disabled={busy || !brief?.creative_batch_id} onClick={() => void createSampleSet()}><Sparkles /> Generate 5 editable posts</button>{!brief?.creative_batch_id && <small>The selected Brief needs a completed five-Ad batch first.</small>}</section>}
    <div className="studio-workspace">
      <aside className="studio-sidebar">
        <section className="panel studio-setup"><h2><Palette /> Project brand</h2>{kits.length ? <label>Brand-kit revision<select value={kitId} onChange={(event) => { setKitId(event.target.value); setSavedRecipe(null); setRender(null) }}>{kits.map((item) => <option key={item.brand_kit_id} value={item.brand_kit_id}>{item.document.name} · {item.brand_kit_id.slice(0, 8)}</option>)}</select></label> : <p>No Project brand kit yet.</p>}
          <details open={!kits.length}><summary>Create brand-kit revision</summary><label>Name<input value={kitForm.name} onChange={(event) => setKitForm({ ...kitForm, name: event.target.value })} /></label><label>4–6 hex colors<input value={kitForm.colors} onChange={(event) => setKitForm({ ...kitForm, colors: event.target.value })} /></label><label>Font<select value={kitForm.font} onChange={(event) => setKitForm({ ...kitForm, font: event.target.value })}><option>Inter</option><option>DejaVu Sans</option><option>DejaVu Serif</option><option>DejaVu Mono</option></select></label><label>Logo source<select value={kitForm.logoAsset} onChange={(event) => setKitForm({ ...kitForm, logoAsset: event.target.value })}><option value="">No logo</option>{assets.filter((item) => item.mime_type.startsWith('image/')).map((item) => <option key={item.source_asset_id} value={item.source_asset_id}>{item.title}</option>)}</select></label><label>Tone notes<textarea rows={2} value={kitForm.tone} onChange={(event) => setKitForm({ ...kitForm, tone: event.target.value })} /></label><button className="secondary" disabled={busy} onClick={() => void createKit()}><Save /> Save brand kit</button></details></section>
        <section className="panel studio-setup"><h2><Box /> Post source</h2><label>Approved Brief<select value={briefId} onChange={(event) => { setBriefId(event.target.value); setInstances([]); setPast([]); setFuture([]); setParentRecipeId(null) }}>{briefs.map((item) => <option key={item.brief_id} value={item.brief_id}>{item.product} · {item.brief_id.slice(0, 8)}</option>)}</select></label><label>Placement<select value={placementId} onChange={(event) => changePlacement(event.target.value)}>{catalog.filter((item) => item.kind === 'placement').map((item) => <option key={item.tool_id} value={item.tool_id}>{placementLabels[item.tool_id] || item.label}</option>)}</select></label><small>{placementId}</small>{sampleSets.length > 1 && <label>Sample set<select value={activeSampleSet?.sample_set_id || ''} onChange={(event) => setActiveSampleSetId(event.target.value)}>{sampleSets.map((item) => <option key={item.sample_set_id} value={item.sample_set_id}>{item.created_at.slice(0, 10)} · {item.batch_id.slice(0, 8)}</option>)}</select></label>}{recipes.length > 0 && <label>Continue from saved version<select value="" onChange={(event) => { const item = recipes.find((recipe) => recipe.recipe_id === event.target.value); if (item) void openRecipe(item) }}><option value="">Choose immutable recipe…</option>{recipes.map((item) => <option key={item.recipe_id} value={item.recipe_id}>{item.recipe_id.slice(0, 8)} · {placementLabels[item.placement_tool_id]}</option>)}</select></label>}</section>
        <section className="panel studio-setup"><h2><Layers3 /> Reusable templates</h2><p>Templates retain the design and resolve their typed Brief, creative, and brand bindings on the server with fresh component IDs.</p><label>Template name<input aria-label="Template name" value={templateName} maxLength={120} onChange={(event) => setTemplateName(event.target.value)} placeholder="e.g. Cinematic clarity" /></label><button className="secondary" disabled={busy || !templateName.trim()} onClick={() => void saveTemplate()}><Save /> Save current template</button>{templates.length > 0 && <div className="studio-template-list">{templates.map((item) => { const creativeBound = item.document.schema_version === 2 && Object.values(item.document.bindings || {}).some((binding) => typeof binding === 'object' && binding !== null && 'source' in binding && String(binding.source).startsWith('creative.')); const linked = activeSampleSet?.items.find((sample) => sample.template_id === item.template_id); const available = !creativeBound || Boolean(linked?.source_creative_id); return <button key={item.template_id} disabled={busy || !available} onClick={() => void applyTemplate(item)} title={available ? 'Resolve and apply this template' : 'Open this creative-bound template from its five-post sample gallery'}><strong>{item.name}</strong><small>{available ? 'Resolve with fresh editable components' : 'Creative-bound sample · open from gallery'}<br />{item.placement_tool_id}</small></button> })}</div>}</section>
        <section className="panel studio-tool-shelf"><h2><Sparkles /> Components</h2><p>Add editable content or styling to the selected post.</p>{['frame', 'layout', 'color', 'effect', 'motion', 'strategy'].map((kind) => { const items = compatible.filter((item) => item.kind === kind); if (!items.length) return null; return <details key={kind} open={kind === 'frame'}><summary>{kind}</summary>{items.map((item) => <button key={item.tool_id} className="studio-tool" onClick={() => addTool(item)}><strong>{item.label}</strong><small>{item.tool_id}</small></button>)}</details> })}</section>
        <section className="panel studio-sources"><h2><ImageIcon /> Source library</h2><label className="secondary studio-upload"><Upload /> Upload image/video<input type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime" disabled={busy} onChange={(event) => void upload(event.target.files?.[0])} /></label><div className="studio-search"><input value={pexelsQuery} onChange={(event) => setPexelsQuery(event.target.value)} placeholder="Search licensed Pexels photos" /><button className="secondary" disabled={busy || !pexelsQuery.trim()} onClick={() => void searchPexels()} aria-label="Search Pexels"><Search /></button></div>{pexels.map((photo) => <button key={String(photo.photo_id)} className="studio-source-result" onClick={() => void importPexels(String(photo.photo_id))}><span>{String(photo.alt || 'Pexels photo')}</span><small>{String(photo.photographer)}</small></button>)}<div className="studio-source-library">{assets.map((item) => <article key={item.source_asset_id}><div><SourceMedia api={api} asset={item} /></div><span>{item.title}</span><small>{item.origin}</small></article>)}</div></section>
      </aside>
      <div className={`studio-editor ${mode === 'edit' && selected ? 'has-selection' : ''}`}>
        <section className="panel studio-toolbar"><div className="studio-mode-toggle"><button className={mode === 'preview' ? 'primary' : 'secondary'} aria-pressed={mode === 'preview'} onClick={() => { setMode('preview'); setSelectedId('') }}><Eye /> Preview</button><button className={mode === 'edit' ? 'primary' : 'secondary'} aria-pressed={mode === 'edit'} onClick={() => setMode('edit')}><Pencil /> Edit</button></div><div><button className="secondary" disabled={!past.length || mode !== 'edit'} onClick={undo}><Undo2 /> Undo</button><button className="secondary" disabled={!future.length || mode !== 'edit'} onClick={redo}><Redo2 /> Redo</button></div><div><button className="secondary" disabled={busy || !kitId} onClick={() => void saveRecipe()}><Save /> Save version</button><button className="primary" disabled={busy || !kitId} onClick={() => void renderRecipe()}><Play /> Render JPEG</button></div></section>
        <section className="studio-stage-panel"><div className={`studio-canvas ${mode}`} style={{ aspectRatio: placementId.includes('vertical') ? '9 / 16' : placementId.includes('portrait') ? '4 / 5' : '1 / 1', background: kit ? `linear-gradient(145deg, ${kit.document.colors[0]}, ${kit.document.colors[2] || kit.document.colors[1]})` : undefined }} aria-label="Constrained Ad Studio canvas">
          {mode === 'edit' && <div className="studio-safe-zone" style={{ inset: mediaKind === 'motion' ? '8% 5% 5%' : '4%' }} aria-hidden="true" />}
          {[...instances].sort((a, b) => a.z_index - b.z_index).map((item) => <CanvasFrame key={item.instance_id} api={api} item={item} asset={assets.find((asset) => asset.source_asset_id === item.source_asset_ids[0]) || null} editing={mode === 'edit'} selected={selectedId === item.instance_id} onBegin={beginDrag} onMove={dragMove} onEnd={endDrag} onKey={keyboardMove} />)}
        </div></section>
        <section className="panel studio-share-copy"><h2>Share copy</h2><p>Caption and accessibility text stay editable and travel with the recipe and ZIP package.</p><label>Caption<textarea rows={5} maxLength={2200} value={caption} onChange={(event) => { setCaption(event.target.value); setSavedRecipe(null) }} /></label><label>Alt text<textarea rows={3} maxLength={1000} value={altText} onChange={(event) => { setAltText(event.target.value); setSavedRecipe(null) }} /></label></section>
        {mode === 'edit' && <section className="panel studio-layers"><h2><Layers3 /> Layers</h2>{[...instances].sort((a, b) => b.z_index - a.z_index).map((item) => <button key={item.instance_id} className={selectedId === item.instance_id ? 'selected' : ''} onClick={() => setSelectedId(item.instance_id)}><Move /><span>{catalog.find((definition) => definition.tool_id === item.tool_id)?.label || item.tool_id}</span><small>{item.tool_id}</small></button>)}</section>}
        {mode === 'edit' && selected && <section className="panel studio-inspector" aria-label="Selected component inspector"><header><div><small>SELECTED COMPONENT</small><h2>{catalog.find((item) => item.tool_id === selected.tool_id)?.label || selected.tool_id}</h2><code>{selected.instance_id}</code></div><div><button className="secondary" onClick={() => moveLayer(1)} aria-label="Move layer up"><ChevronUp /></button><button className="secondary" onClick={() => moveLayer(-1)} aria-label="Move layer down"><ChevronDown /></button><button className="secondary studio-inspector-close" onClick={() => setSelectedId('')} aria-label="Close component inspector"><X /></button></div></header>
          <div className="studio-frame-fields">{(['x', 'y', 'width', 'height'] as const).map((key) => <label key={key}>{key}<input type="number" min="0" max="1" step="0.01" value={selected.frame[key]} onChange={(event) => updateFrame(key, Number(event.target.value))} /></label>)}</div>
          {selected.tool_id.startsWith('studio.frame.') && !['studio.frame.media.v1', 'studio.frame.product.v1', 'studio.frame.logo.v1', 'studio.frame.shape.v1'].includes(selected.tool_id) && <><label>Text<textarea rows={3} value={String(selected.params.text || '')} disabled={['studio.frame.offer.v1', 'studio.frame.cta.v1'].includes(selected.tool_id)} onChange={(event) => updateParams({ text: event.target.value })} /></label><div className="studio-frame-fields"><label>Color<input value={String(selected.params.color || '#FFFFFF')} onChange={(event) => updateParams({ color: event.target.value })} /></label><label>Font size<input type="number" min="10" max="180" value={Number(selected.params.font_size || 36)} onChange={(event) => updateParams({ font_size: Number(event.target.value) })} /></label><label>Weight<select value={Number(selected.params.font_weight || 800)} onChange={(event) => updateParams({ font_weight: Number(event.target.value) })}><option value="400">Regular</option><option value="600">Semibold</option><option value="700">Bold</option><option value="800">Extra bold</option><option value="900">Black</option></select></label><label>Alignment<select value={String(selected.params.align || 'left')} onChange={(event) => updateParams({ align: event.target.value })}><option>left</option><option>center</option><option>right</option></select></label><label>Line height<input type="number" min="0.8" max="2" step="0.05" value={Number(selected.params.line_height || 1.05)} onChange={(event) => updateParams({ line_height: Number(event.target.value) })} /></label><label>Maximum lines<input type="number" min="1" max="12" value={Number(selected.params.max_lines || 5)} onChange={(event) => updateParams({ max_lines: Number(event.target.value) })} /></label><label>Vertical align<select value={String(selected.params.vertical_align || 'top')} onChange={(event) => updateParams({ vertical_align: event.target.value })}><option value="top">Top</option><option value="middle">Middle</option><option value="bottom">Bottom</option></select></label></div></>}
          {selected.tool_id === 'studio.frame.shape.v1' && <div className="studio-frame-fields"><label>Background<input value={String(selected.params.background || '#FFFFFF')} onChange={(event) => updateParams({ background: event.target.value })} /></label><label>Corner radius<input type="number" min="0" max="120" step="1" value={Number(selected.params.radius || 0)} onChange={(event) => updateParams({ radius: Number(event.target.value) })} /></label><label>Opacity<input type="number" min="0" max="1" step="0.05" value={Number(selected.params.opacity ?? 1)} onChange={(event) => updateParams({ opacity: Number(event.target.value) })} /></label></div>}
          {['studio.frame.media.v1', 'studio.frame.product.v1', 'studio.frame.logo.v1'].includes(selected.tool_id) && <><label>Source asset<select value={selected.source_asset_ids[0] || ''} onChange={(event) => updateSelected({ source_asset_ids: event.target.value ? [event.target.value] : [] })}><option value="">Choose Project source…</option>{assets.map((item) => <option key={item.source_asset_id} value={item.source_asset_id}>{item.title} · {item.origin}</option>)}</select></label><div className="studio-frame-fields"><label>Fit<select value={String(selected.params.fit || (selected.tool_id === 'studio.frame.logo.v1' ? 'contain' : 'cover'))} onChange={(event) => updateParams({ fit: event.target.value })}><option value="cover">Cover</option><option value="contain">Contain</option></select></label><label>Focal X<input type="number" min="0" max="1" step="0.05" value={Number(selected.params.focal_x ?? .5)} onChange={(event) => updateParams({ focal_x: Number(event.target.value) })} /></label><label>Focal Y<input type="number" min="0" max="1" step="0.05" value={Number(selected.params.focal_y ?? .5)} onChange={(event) => updateParams({ focal_y: Number(event.target.value) })} /></label></div></>}
          {selectedAsset?.mime_type.startsWith('video/') && <div className="studio-frame-fields"><label>Trim start<input type="number" min="0" max={selectedAsset.duration_seconds || 30} step="0.1" value={Number(selected.params.trim_start_seconds || 0)} onChange={(event) => updateParams({ trim_start_seconds: Number(event.target.value) })} /></label><label>Original audio<select value={String(selected.params.original_audio || 'mute')} onChange={(event) => updateParams({ original_audio: event.target.value })}><option value="mute">Mute</option><option value="preserve">Preserve</option></select></label></div>}
          <button className="secondary" disabled={['studio.frame.offer.v1', 'studio.frame.cta.v1'].includes(selected.tool_id)} onClick={removeSelected}>Remove component</button>
        </section>}
        {savedRecipe && <WizardPanel api={api} recipe={savedRecipe} target={selected} recoveredProposal={recoveredWizardProposal} onApplied={wizardApplied} />}
        {renderHistory.length > 0 && <section className="panel studio-render-history"><h2>Render history</h2><div>{renderHistory.map((item) => <button key={item.render_id} onClick={() => setRender(item)} className={render?.render_id === item.render_id ? 'selected' : ''}><RenderImage api={api} render={item} alt={`Render ${item.render_id}`} compact /><span>{item.created_at.slice(0, 16).replace('T', ' ')}</span></button>)}</div></section>}
        {render && <section className="panel studio-result"><h2>Authoritative render</h2><RenderPreview api={api} render={render} />{!render.published ? <button className="primary" disabled={busy} onClick={() => void publish()}><Sparkles /> Publish training example</button> : <div className="studio-feedback"><label>Feedback for this published example<textarea rows={3} maxLength={2000} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="What should future Studio recipes learn?" /></label><button className="secondary" disabled={busy || !feedback.trim()} onClick={() => void submitFeedback()}><Send /> Save feedback</button></div>}</section>}
        <OwnerLessonProposals api={api} domain="ad_studio" refreshKey={proposalRevision} />
      </div>
    </div>
  </>
}
