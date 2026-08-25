export type Page = 'briefs' | 'studio' | 'ads' | 'landing' | 'admin'
export type I18n<T = string> = { en: T; uk: T }

export type BriefStatus = 'queued' | 'generating' | 'completed' | 'failed'
export type CreativeAngle = 'emotional' | 'practical' | 'curiosity' | 'authority' | 'problem_first'

export interface ValidationProject {
  project_id: string
  request_id: string
  owner_idea_source_id: string
  name: string
  name_source: 'raw_idea' | 'product_brief' | 'owner'
  requested_by: string
  latest_brief_id?: string | null
  latest_brief_status?: BriefStatus | null
  brief_count: number
  ad_batch_count: number
  created_at: string
  updated_at: string
}

export interface ProductBriefDocument {
  schema_version: 1
  language: 'uk' | 'en'
  product: string
  target_audience: string
  main_pain: string
  promise: string
  key_benefits: string[]
  cta: string
  trust_strategy: string
  offer: string
}

export interface ProductBrief extends Partial<ProductBriefDocument> {
  brief_id: string
  project_id: string
  project_name: string
  request_id: string
  owner_idea_source_id: string
  raw_idea: string
  base_brief_id?: string | null
  feedback_id?: string | null
  status: BriefStatus
  document?: ProductBriefDocument | null
  document_sha256?: string | null
  failure_count: number
  error_code?: string | null
  error_message?: string | null
  approved: boolean
  creative_batch_id?: string | null
  creative_batch_status?: BriefStatus | null
  created_at: string
}

export interface StudioToolDefinition {
  tool_id: string
  kind: 'placement' | 'frame' | 'layout' | 'color' | 'effect' | 'motion' | 'strategy' | 'guard'
  label: string
  parameter_schema: Record<string, unknown>
  supported_placements: Array<'static' | 'motion'>
  renderer_handler: string
  defaults: Record<string, unknown>
  bounds: Record<string, unknown>
  source_refs: string[]
  deprecated: boolean
}

export interface StudioBrandKit {
  brand_kit_id: string
  project_id: string
  parent_brand_kit_id?: string | null
  document: {
    name: string
    colors: string[]
    fonts: string[]
    tone_notes: string
    logo_source_asset_id?: string | null
  }
  document_sha256: string
  created_by: string
  created_at: string
}

export interface StudioSourceAsset {
  source_asset_id: string
  project_id: string
  origin: 'owner_upload' | 'pexels' | 'canonical_brand' | 'ai_generated'
  title: string
  mime_type: 'image/jpeg' | 'image/png' | 'image/webp' | 'video/mp4' | 'video/quicktime'
  width: number
  height: number
  duration_seconds?: number | null
  bytes_sha256: string
  source_uri?: string | null
  provider: string
  external_id?: string | null
  license?: string | null
  attribution?: string | null
  metadata: Record<string, unknown>
  asset_url?: string
  created_at: string
}

export interface StudioToolInstance {
  instance_id: string
  tool_id: string
  frame: { x: number; y: number; width: number; height: number }
  z_index: number
  params: Record<string, string | number | boolean>
  timeline?: { start: number; end: number } | null
  source_asset_ids: string[]
}

export interface StudioRecipeDocumentV1 {
  schema_version: 1
  parent_recipe_id?: string | null
  placement_tool_id: string
  duration_seconds?: number | null
  frame_rate?: number | null
  tools: StudioToolInstance[]
  strategy_ids: string[]
  validation_ids: string[]
  source_reference_ids: string[]
}

export interface StudioModifierInstance {
  instance_id: string
  tool_id: string
  params: Record<string, string | number | boolean>
}

export interface StudioRecipeDocumentV2 {
  schema_version: 2
  parent_recipe_id?: string | null
  placement_tool_id: string
  duration_seconds?: number | null
  frame_rate?: number | null
  frames: StudioToolInstance[]
  modifiers: StudioModifierInstance[]
  strategy_ids: string[]
  validation_ids: string[]
  source_reference_ids: string[]
  share: {
    caption: string
    alt_text: string
  }
}

export type StudioRecipeDocument = StudioRecipeDocumentV1 | StudioRecipeDocumentV2

export interface StudioTemplate {
  template_id: string
  project_id: string
  name: string
  placement_tool_id: string
  document: {
    schema_version: 1 | 2
    placement_tool_id: string
    duration_seconds?: number | null
    frame_rate?: number | null
    tools?: StudioToolInstance[]
    frames?: StudioToolInstance[]
    modifiers?: StudioModifierInstance[]
    strategy_ids: string[]
    bindings?: Record<string, unknown>
  }
  document_sha256: string
  created_by: string
  created_at: string
}

export interface StudioRecipe {
  recipe_id: string
  project_id: string
  brief_id: string
  brand_kit_id: string
  parent_recipe_id?: string | null
  placement_tool_id: string
  document: StudioRecipeDocument & {
    width: number; height: number; source_asset_ids: string[]; renderer_version: string
  }
  document_sha256: string
  renderer_version: string
  created_by: string
  created_at: string
}

export interface StudioRender {
  render_id: string
  recipe_id: string
  mime_type: 'image/jpeg' | 'video/mp4'
  width: number
  height: number
  duration_seconds?: number | null
  bytes_sha256: string
  manifest: Record<string, unknown>
  manifest_sha256: string
  renderer_version: string
  published: boolean
  created_at: string
  asset_url: string
  manifest_url: string
}

export interface StudioSampleSetItem {
  ordinal: 0 | 1 | 2 | 3 | 4
  angle: CreativeAngle
  name: string
  source_creative_id?: string
  template_id: string
  recipe_id: string
  render_id: string
  caption: string
  alt_text: string
  template: StudioTemplate
  recipe: StudioRecipe
  render: StudioRender
}

export interface StudioSampleSet {
  sample_set_id: string
  project_id: string
  brief_id: string
  batch_id: string
  brand_kit_id: string
  status: 'building' | 'completed' | 'failed'
  error_message?: string | null
  created_at: string
  download_url: string
  download_sha256?: string
  download_mime_type?: 'application/zip'
  items: StudioSampleSetItem[]
}

export interface StudioWizardProposal {
  proposal_id: string
  recipe_id: string
  status: 'previewed' | 'applied' | 'failed'
  instruction: string
  target_instance_id?: string | null
  patch: Record<string, unknown>
  before_sha256: string
  after_sha256: string
  preview_url: string
  preview_sha256?: string
  preview_mime_type?: 'image/jpeg'
  applied_recipe_id?: string | null
  created_at: string
}

export interface CreativeImage {
  asset_id: string
  url: string
  mime_type: 'image/jpeg'
  width: 1080
  height: 1080
  sha256: string
  provider: 'pexels'
  source_photo_id: string
  source_url: string
  photographer: string
  photographer_url: string
  license: string
  license_url: string
  attribution: string
  alt: string
}

export interface AdCreative {
  creative_id: string
  brief_id: string
  ordinal: number
  angle: CreativeAngle
  hook: string
  primary_text: string
  image_description: string
  cta: string
  offer: string
  desired_emotion: string
  image_category: string
  image_search_query: string
  crop_focus: 'left' | 'center' | 'right'
  content_sha256: string
  image: CreativeImage
}

export interface CreativeBatch {
  batch_id: string
  brief_id: string
  project_id: string
  project_name: string
  brief_product?: string | null
  status: BriefStatus
  batch_sha256?: string | null
  failure_count: number
  error_code?: string | null
  error_message?: string | null
  approved_offer?: string | null
  request_id?: string | null
  rerun_of_batch_id?: string | null
  requested_by?: string | null
  skill_sha256?: string | null
  rerun_batch_id?: string | null
  lesson_status_counts?: Partial<Record<ValidationSkillProposal['status'], number>>
  last_failed_attempt?: {
    attempt_id: string
    attempt_number: number
    error_code?: string | null
    error_message?: string | null
    started_at: string
    completed_at?: string | null
  } | null
  failure_notification?: {
    status: 'pending' | 'sent' | 'failed' | 'ambiguous' | 'suppressed'
    attempt_id?: string | null
    recorded_at: string
  } | null
  creatives: AdCreative[]
  created_at: string
}

export interface ValidationSkillProposal {
  proposal_id: string
  feedback_id: string
  target_id: string
  lesson: string
  status: 'pending' | 'planning' | 'promoted' | 'rejected' | 'failed'
  command_session_id?: string | null
  created_at: string
  updated_at: string
}

export interface EvidenceStatement {
  text: string
  source_ids: string[]
  assumption: boolean
}

export interface PositioningDocument {
  schema_version: 1
  output_language: 'uk' | 'en'
  positioning_foundation: {
    category: EvidenceStatement
    competitive_alternatives: EvidenceStatement[]
    definitive_audience: EvidenceStatement
    jobs: EvidenceStatement[]
    pains: EvidenceStatement[]
    gains: EvidenceStatement[]
    uvp: EvidenceStatement
  }
  messaging_matrix: Array<{
    feature: EvidenceStatement
    functional_benefit: EvidenceStatement
    emotional_reward: EvidenceStatement
  }>
  landing_copy: {
    hero: Record<'eyebrow' | 'headline' | 'subheadline' | 'cta', EvidenceStatement>
    value_sections: Array<{ title: EvidenceStatement; body: EvidenceStatement }>
    honest_limitation: EvidenceStatement
    lead_capture_strategy: EvidenceStatement
  }
  ad_concepts: Array<{
    kind: 'contextual_relatable' | 'direct_problem_solution'
    hook: EvidenceStatement
    body: EvidenceStatement
    visual_direction: EvidenceStatement
  }>
  aeo_faqs: Array<Record<'question' | 'definition' | 'data' | 'context', EvidenceStatement>>
  evidence_references: string[]
  assumptions: string[]
}

export interface PositioningRevision {
  id: string
  project_id: string
  request_id: string
  revision_number: number
  base_revision_id?: string | null
  feedback_id?: string | null
  status: 'queued' | 'researching' | 'synthesizing' | 'completed' | 'failed'
  document?: PositioningDocument | null
  document_sha256?: string | null
  quality_gates?: Record<string, boolean> | null
  failure_count: number
  error_code?: string | null
  error_message?: string | null
  approved: boolean
  created_at: string
}

export interface PositioningSource {
  id: string
  source_type: 'owner_idea' | 'research_finding'
  title: string
  source_uri?: string | null
  publisher?: string | null
  content: string
  provider: string
  metadata: Record<string, unknown>
}

export interface PositioningProject {
  id: string
  request_id: string
  owner_idea_source_id: string
  raw_idea: string
  target_country: string
  research_language: string
  output_language: 'uk' | 'en'
  active_approved_revision_id?: string | null
  latest_revision_id?: string
  latest_revision_status?: PositioningRevision['status']
  revisions?: PositioningRevision[]
  sources?: PositioningSource[]
  created_at: string
}

export interface PositioningCatalog {
  default_country: string
  default_research_language: string
  countries: Array<{ code: string; name: string }>
  research_languages: Array<{ code: string; name: string }>
  output_languages: Array<{ code: 'uk' | 'en'; name: string }>
}

export type LandingTemplateId = 'product' | 'community' | 'waitlist'
export type LandingBlockId = 'hero' | 'problem' | 'features' | 'steps' | 'proof' | 'faq' | 'final_cta' | 'lead_form'

export interface LandingTemplate {
  id: LandingTemplateId
  name: { uk: string; en: string }
  description: { uk: string; en: string }
}

export interface LandingSnapshot {
  id: string
  draft_set_id: string
  template_id: LandingTemplateId
  snapshot_number: number
  page_content: { schema_version: 2; template_id: LandingTemplateId; language: 'uk' | 'en'; blocks: Record<LandingBlockId, Record<string, unknown>> }
  page_content_sha256: string
  is_current: boolean
}

export interface LandingEdit {
  request_id: string
  draft_set_id: string
  template_id: LandingTemplateId
  block_id: LandingBlockId
  instruction: string
  status: 'queued' | 'editing' | 'completed' | 'failed'
  result_snapshot_id?: string | null
  error_message?: string | null
}

export interface LandingDraftSet {
  id: string
  request_id: string
  positioning_project_id: string
  positioning_revision_id: string
  brief: Record<string, unknown>
  status: 'queued' | 'populating' | 'completed' | 'failed'
  population_summary?: string | null
  error_message?: string | null
  snapshots: LandingSnapshot[]
  current_snapshots: Partial<Record<LandingTemplateId, LandingSnapshot>>
}

export interface LandingBuild {
  id: string
  request_id: string
  positioning_project_id: string
  positioning_revision_id: string
  source_draft_snapshot_id: string
  template_id: LandingTemplateId
  status: 'queued' | 'building' | 'publishing' | 'published' | 'failed'
  public_url?: string | null
  error_message?: string | null
  created_at: string
}

export interface LandingLead {
  id: string
  build_id: string
  form_id: 'waitlist' | 'contact_request' | 'community_interest'
  fields: Record<string, string>
  submitted_at: string
  notification_attempts: Array<{ status: 'sent' | 'failed' | 'ambiguous' | 'suppressed'; error_message?: string | null }>
}

export interface SkillProposal {
  id: string
  feedback_id: string
  revision_id?: string
  lesson: string
  status: 'pending_generation' | 'pending' | 'planning' | 'promoted' | 'rejected' | 'failed'
  command_session_id?: string | null
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  mode: 'plan' | 'execute'
  title: string
  instruction?: string
  status: string
  destructive?: boolean
  plan?: string
  plan_digest?: string
  execution_count?: number
  error?: string | null
  created_at?: string
  updated_at?: string
  deployment_revision?: string
}
