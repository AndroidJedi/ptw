export type Page = 'briefs' | 'result' | 'studio'
export type I18n<T = string> = { en: T; uk: T }

export type BriefStatus = 'queued' | 'generating' | 'completed' | 'failed'

export interface ValidationProject {
  project_id: string
  request_id: string
  owner_idea_source_id: string
  name: string
  name_source: 'raw_idea' | 'product_brief' | 'owner'
  requested_by: string
  result_creation_enabled: boolean
  latest_brief_id?: string | null
  latest_brief_status?: BriefStatus | null
  brief_count: number
  result_run_count: number
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
  created_at: string
}

export type SocialPlatform = 'instagram' | 'tiktok'
export type ReviewState = 'unreviewed' | 'ready' | 'needs_changes'
export type OutputProfile = 'marketing_copy_v1' | 'instagram_static_ad_v1' | 'tiktok_photo_post_v1'
export type ResultRunStatus = 'queued' | 'generating' | 'completed' | 'failed'
export type ResultRunStage =
  | 'queued'
  | 'initial_candidates'
  | 'critic_pass_1'
  | 'critic_pass_2'
  | 'critic_pass_3'
  | 'materializing_result'
  | 'completed'
  | 'failed'

export interface ContentRun {
  run_id: string
  request_id: string
  parent_run_id?: string | null
  project_id: string
  brief_id: string
  output_profile: OutputProfile
  platform?: SocialPlatform
  task: string
  status: ResultRunStatus
  current_stage: ResultRunStage
  progress_percent: number
  maximum_minutes: 45
  error_code?: string | null
  error_message?: string | null
  final_result_id?: string | null
  review_state?: ReviewState
  review_feedback_id?: string | null
  review_comment?: string | null
  revision_number?: number
  preview?: CandidatePreview | null
  created_at: string
  updated_at: string
}

export interface CandidateContent {
  hook: string
  headline: string
  primary_text: string
  supporting_text: string
  offer: string
  cta: string
  caption: string
  alt_text: string
  desired_emotion: string
  visual_concept: string
}

export interface ContentResult {
  creative_id: string
  run_id: string
  selected_candidate_id: string
  recipe_id?: string | null
  render_id?: string | null
  decision_summary: string[]
  result_sha256: string
  content: CandidateContent
  content_sha256: string
  asset_sha256?: string | null
  asset_mime_type?: 'image/jpeg' | null
  asset_width?: number | null
  asset_height?: number | null
  asset_url?: string | null
  created_at: string
}

export type CandidateParameterName =
  | 'hook_pressure'
  | 'emotional_intensity'
  | 'conceptual_novelty'
  | 'information_density'
  | 'visual_complexity'

export interface CandidatePreview {
  asset_url: string
  sha256: string
  mime_type: 'image/jpeg'
  width: number
  height: number
}

export interface ContentCandidate {
  candidate_id: string
  alias: string
  round: number
  generation_kind: 'initial' | 'recomposition' | 'element_regeneration' | 'template_rerun'
  parent_candidate_id?: string | null
  template_id: string
  template_version: number
  parameters: Record<CandidateParameterName, number>
  document: CandidateContent
  preview: CandidatePreview
}

export interface CriticCandidateScore {
  scores: Record<string, number>
  complexity: 'none' | 'moderate' | 'harmful'
  weighted_total: number
  eligible: boolean
  reason_codes: string[]
}

export interface CriticPairwiseResult {
  left: string
  right: string
  winner: string
  reason_codes: string[]
}

export interface CriticAction {
  action_type: 'recompose' | 'regenerate_elements' | 'rerun_template' | 'discard'
  base_candidate_id?: string | null
  output_candidate_id?: string | null
  parameter_deltas?: Record<string, [number, number]> | null
  status: string
}

export interface CriticPassDebug {
  pass_id: string
  pass_number: 1 | 2 | 3
  active_candidate_ids: string[]
  hard_gates: Record<string, Record<string, boolean>>
  candidate_scores: Record<string, CriticCandidateScore>
  ranking: string[]
  pairwise_results: CriticPairwiseResult[]
  observations: string[]
  actions: CriticAction[]
  final_selection?: { candidate_id: string; decision_summary: string[] } | null
}

export interface ContentDebug {
  candidates: ContentCandidate[]
  critic_passes: CriticPassDebug[]
  result?: ContentResult | null
}

export interface ProjectAsset {
  source_asset_id: string
  project_id: string
  approval_status: 'approved' | 'pending_review' | 'rejected'
  title: string
  mime_type: 'image/jpeg' | 'image/png' | 'image/webp'
  width: number
  height: number
  bytes_sha256: string
}

export interface ProjectBrandKit {
  brand_kit_id: string
  project_id: string
  document: {
    name: string
    colors: string[]
    fonts: string[]
    tone_notes: string
    logo_source_asset_id?: string | null
  }
  document_sha256: string
  created_at: string
}

export type StudioUniversalFontFamily = 'Inter' | 'Manrope' | 'Oswald' | 'Cormorant Garamond'

export interface StudioUniversalConfiguration {
  schema: 'ptw.studio.universal-ad-config.v4'
  background: {
    mode: 'solid' | 'texture' | 'image'
    color: string
    texture: 'grain' | 'stone' | 'marble' | 'concrete' | 'granite' | 'slate' | 'travertine'
    texture_intensity: number
    image_layout: 'full' | 'left' | 'right' | 'top' | 'bottom'
    image_percent: 25 | 75
    image_fit: 'cover' | 'contain'
    focal_x: number
    focal_y: number
    overlay_color: string
    overlay_opacity: number
  }
  typography: {
    font_family: StudioUniversalFontFamily
    benefits_font_family: StudioUniversalFontFamily
    hero_size: number
    hero_weight: number
    supporting_size: number
    text_color: string
    alignment: 'left' | 'center'
  }
  layout: {
    content_x: number
    content_y: number
    content_width: number
    gap: number
  }
  bullets: { enabled: boolean; style: 'check' | 'circle' | 'circle_outline' }
  cta: {
    style: 'filled' | 'gradient' | 'reverse' | 'link' | 'outlined'
    position: 'below_text' | 'bottom_left' | 'bottom_right'
    background_color: string
    text_color: string
    radius: number
  }
  sticker: {
    enabled: boolean
    position:
      | 'top_left' | 'top_right' | 'bottom_left' | 'bottom_right'
      | 'right_edge' | 'bottom_edge' | 'bullet_list' | 'hero_title' | 'cta'
    rotation: number
    width: number
    object_scale: number
    offset_right: number
    offset_bottom: number
  }
  logo: {
    enabled: boolean
    position: 'top_left' | 'top_right'
    width: number
    background_enabled: boolean
    background_color: string
  }
}

export interface StudioUniversalContent {
  schema: 'ptw.studio.universal-ad-content.v2'
  hero_title: string
  supporting_text: string
  offer: string
  bullets: string[]
  cta: string
}

export interface StudioUniversalAssetSummary {
  slot: 'background_image' | 'sticker_object' | 'logo'
  role: 'background' | 'sticker' | 'logo'
  description: string
  allowed_mime_types: string[]
  available: boolean
  mime_type: string | null
  sha256: string | null
  byte_count: number | null
  source: Record<string, unknown> | null
}

export interface StudioUniversalVersionSummary {
  version: number
  state_sha256: string
  template_sha256: string
  render_sha256: string
  change_note: string
}

export interface StudioUniversalComponentDefinition {
  component_id: string
  role: 'background' | 'sticker' | 'hero_title' | 'supporting_text' | 'offer' | 'bullet_list' | 'cta' | 'logo'
  node_ids: string[]
  asset_slot_ids: string[]
  setting_ids: string[]
}

export interface StudioUniversalComponentSettings {
  schema: 'ptw.studio.universal-ad-component-settings.v2'
  template_id: 'universal_ad'
  template_version: number
  configuration_schema: 'ptw.studio.universal-ad-config.v4'
  components: Array<Omit<StudioUniversalComponentDefinition, 'setting_ids'> & {
    settings: Array<{ setting_id: string; value: unknown }>
  }>
  sha256: string
}

export interface StudioUniversalAgentContext {
  schema: 'ptw.studio.universal-ad-agent-context.v2'
  template_id: 'universal_ad'
  template_version: number
  state_sha256: string
  template_sha256: string
  component_settings: StudioUniversalComponentSettings
  assets: Array<Pick<StudioUniversalAssetSummary, 'slot' | 'available' | 'mime_type' | 'sha256' | 'source'>>
  sha256: string
}

export interface StudioUniversalCatalog {
  schema: 'ptw.studio.universal-ad-catalog.v4'
  template_id: 'universal_ad'
  template_version: number
  semantic_roles: Array<'background' | 'sticker' | 'hero_title' | 'supporting_text' | 'offer' | 'bullet_list' | 'cta' | 'logo'>
  components: StudioUniversalComponentDefinition[]
  asset_slots: Record<string, {
    role: string
    allowed_mime_types: string[]
    description: string
  }>
  variation: {
    background_modes: string[]
    image_layouts: string[]
    image_percents: number[]
    texture_presets: string[]
    bullet_styles: string[]
    cta_styles: string[]
    cta_positions: string[]
    sticker_positions: string[]
    font_families: string[]
    optional_elements: string[]
  }
  sha256: string
}

export interface StudioUniversalDetail {
  schema: 'ptw.studio.universal-ad-workspace.v5'
  catalog: StudioUniversalCatalog
  state_sha256: string
  template_sha256: string
  configuration: StudioUniversalConfiguration
  content: StudioUniversalContent
  component_settings: StudioUniversalComponentSettings
  assets: StudioUniversalAssetSummary[]
  pexels_available: boolean
  versions: StudioUniversalVersionSummary[]
}

export type StudioTuneRunStatus = 'queued' | 'running' | 'completed' | 'failed'
export type StudioTuneRunStage =
  | 'queued'
  | 'preparing'
  | 'generating'
  | 'verifying'
  | 'applying'
  | 'completed'
  | 'failed'

export interface StudioTuneApprovedRule {
  rule: string
  rule_sha256: string
  skill_path: 'skills/studio-tune-local/references/owner-approved-rules.md'
}

export interface StudioTuneRun {
  schema: 'ptw.studio.tune-run.v1'
  run_id: string
  iteration: number
  status: StudioTuneRunStatus
  stage: StudioTuneRunStage
  project_idea: string
  implementation: string
  feedback: string
  studio_context?: StudioUniversalAgentContext | null
  request_sha256: string
  changed_files: string[]
  verification: string[]
  summary: string | null
  error: string | null
  approved_rules?: StudioTuneApprovedRule[]
  preview: {
    mime_type: 'image/png'
    sha256: string
    width: number
    height: number
  } | null
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
}

export interface StudioTuneRuleApproval extends StudioTuneApprovedRule {
  schema: 'ptw.studio.tune-rule-approval.v1'
  run_id: string
  created: boolean
}

export interface StudioTuneDetail {
  schema: 'ptw.studio.tune-service.v1'
  mode: 'local_only'
  available: boolean
  unavailable_reason: string | null
  active_run_id: string | null
  allowed_paths: string[]
  runs: StudioTuneRun[]
}
