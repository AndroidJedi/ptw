export type Page = 'briefs' | 'posts' | 'studio'
export type I18n<T = string> = { en: T; uk: T }

export type BriefStatus = 'queued' | 'generating' | 'completed' | 'failed'

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

export type StudioUniversalFontFamily = 'Inter' | 'Manrope' | 'Oswald' | 'Cormorant Garamond'

export interface StudioUniversalConfiguration {
  schema: 'ptw.studio.universal-ad-config.v5'
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
    font_size: number
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
  configuration_schema: 'ptw.studio.universal-ad-config.v5'
  components: Array<Omit<StudioUniversalComponentDefinition, 'setting_ids'> & {
    settings: Array<{ setting_id: string; value: unknown }>
  }>
  sha256: string
}

export interface StudioUniversalSettingDefinition {
  setting_id: string
  component_id: string
  value_type: 'boolean' | 'color' | 'enum' | 'integer' | 'number'
  aliases: string[]
  minimum?: number
  maximum?: number
  step?: number
  values?: Array<string | number>
  value_aliases?: Record<string, string[]>
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
  schema: 'ptw.studio.universal-ad-catalog.v5' | 'ptw.studio.universal-ad-catalog.v6'
  template_id: 'universal_ad'
  template_version: number
  semantic_roles: Array<'background' | 'sticker' | 'hero_title' | 'supporting_text' | 'offer' | 'bullet_list' | 'cta' | 'logo'>
  components: StudioUniversalComponentDefinition[]
  asset_slots: Record<string, {
    role: string
    allowed_mime_types: string[]
    description: string
  }>
  setting_definitions?: StudioUniversalSettingDefinition[]
  variation: {
    background_modes: string[]
    image_layouts: string[]
    image_percents: number[]
    texture_presets: string[]
    bullet_styles: string[]
    cta_styles: string[]
    cta_positions: string[]
    cta_font_size: { minimum: number; maximum: number; default: number }
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

export type SimplePostStatus = 'queued' | 'generating' | 'draft' | 'tuning' | 'failed' | 'approved'

export interface SimplePostCommand {
  setting_id: string
  value: string | number | boolean | string[]
}

export type SimplePostImageRequest =
  | { slot: 'background_image'; query: string }
  | { slot: 'sticker_object'; query: string; required_subject_terms: string[] }

export interface SimplePostAsset {
  schema: 'ptw.simple-post-asset.v1'
  asset_id: string
  post_id: string
  project_id: string
  brief_id: string
  mime_type: 'image/png'
  sha256: string
  width: number
  height: number
  state_sha256: string
  template_sha256: string
  approved_by: string
  created_at: string
}

export interface SimplePost {
  schema: 'ptw.simple-post.v1'
  post_id: string
  request_id: string
  project_id: string
  brief_id: string
  brief_document_sha256: string
  status: SimplePostStatus
  failure_count: number
  state_sha256?: string | null
  template_sha256?: string | null
  last_commands: SimplePostCommand[]
  last_image_request?: SimplePostImageRequest | null
  last_comment?: string | null
  last_error?: string | null
  active_tune_id?: string | null
  approved_asset_id?: string | null
  approved_asset?: SimplePostAsset | null
  preview?: { mime_type: 'image/png'; sha256: string; width: number; height: number } | null
  studio?: StudioUniversalDetail | null
  created_at: string
  updated_at: string
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
