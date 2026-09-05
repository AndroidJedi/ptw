export type Page = 'briefs' | 'posts'
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

export type StudioUniversalFontFamily =
  | 'Inter' | 'Roboto Condensed' | 'Manrope' | 'Montserrat' | 'Source Sans 3'
  | 'Oswald' | 'Cormorant Garamond' | 'Cormorant Garamond Italic'
  | 'Lora' | 'Lora Italic'

export interface StudioUniversalConfiguration {
  schema: 'ptw.studio.universal-ad-config.v6'
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
    supporting_font_family: StudioUniversalFontFamily
    offer_font_family: StudioUniversalFontFamily
    benefits_font_family: StudioUniversalFontFamily
    hero_size: number
    hero_weight: number
    supporting_size: number
    offer_size: number
    benefits_size: number
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
    font_family: StudioUniversalFontFamily
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
  asset_id?: string
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
  version_id?: string
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
  schema: 'ptw.studio.universal-ad-component-settings.v3'
  template_id: 'universal_ad'
  template_version: number
  configuration_schema: 'ptw.studio.universal-ad-config.v6'
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
  schema: 'ptw.studio.universal-ad-catalog.v7'
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
  workspace_id?: string
  creative_id: string
  project_id: string
  source_brief_id: string
  ordinal: number
  origin: 'brief_generation' | 'approved_variant'
  status: StudioCreativeStatus
  generation: StudioCreativeSummary['generation']
  approved_version_count: number
  template_id: 'universal_ad'
  templates: StudioTemplateSummary[]
  schema: 'ptw.studio.workspace.v8'
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

export type StudioPhoneBackgroundTexture = 'none' | 'grain' | 'concrete' | 'travertine'
export type StudioPhoneScreenTexture = 'none' | 'grain' | 'paper' | 'frosted'
export type StudioPhoneMetricCardStyle = 'filled' | 'outlined'
export type StudioPhoneMetricCardShape = 'square' | 'rounded' | 'pill'
export type StudioPhoneActionButtonStyle = 'filled' | 'elevated' | 'outlined' | 'text'
export type StudioPhoneActionButtonShape = 'square' | 'rounded' | 'pill'
export type StudioPhoneHeroStyle =
  | 'business_professional' | 'ultra_realistic_lifestyle' | 'cinematic'
  | 'premium_editorial' | 'contemporary_3d' | 'minimal_sculptural'
  | 'artistic_illustration' | 'playful_balloons' | 'tactile_handmade'
  | 'futuristic_tech'
export type StudioPhoneHeroBackground = 'scene' | 'isolated_key_element'
export interface StudioPhoneHeroCreativeDirection {
  schema: 'ptw.studio.phone-hero-direction.v1'
  style: StudioPhoneHeroStyle
  background: StudioPhoneHeroBackground
}
export type StudioFontFamily = StudioUniversalFontFamily
export type StudioPhoneTypographyRole =
  | 'offer' | 'hero_title' | 'supporting_text' | 'cta'
  | 'metric_value' | 'metric_label' | 'phone_title' | 'phone_buttons'
export interface StudioPhoneTypographyConfiguration {
  font_family: StudioFontFamily
  font_size: number
}

export interface StudioPhoneMetricCardConfiguration {
  style: StudioPhoneMetricCardStyle
  text_color: string
  background_color: string
  shape: StudioPhoneMetricCardShape
}

export interface StudioPhoneActionButtonConfiguration {
  style: StudioPhoneActionButtonStyle
  text_color: string
  background_color: string
  shape: StudioPhoneActionButtonShape
}

export interface StudioPhoneMetricsConfiguration {
  schema: 'ptw.studio.phone-metrics-config.v8'
  background: {
    color: string
    texture: StudioPhoneBackgroundTexture
    texture_intensity: number
  }
  copy_background: { texture: StudioPhoneBackgroundTexture }
  offer: { enabled: boolean }
  supporting_text: { highlight_color: string }
  typography: Record<StudioPhoneTypographyRole, StudioPhoneTypographyConfiguration>
  phone_screen: { texture: StudioPhoneScreenTexture }
  metric_cards: StudioPhoneMetricCardConfiguration[]
  phone_buttons: StudioPhoneActionButtonConfiguration[]
  device: { x: number; y: number; width: number; rotation: number }
}

export interface StudioPhoneMetricsContent {
  schema: 'ptw.studio.phone-metrics-content.v2'
  offer: string
  hero_title: string
  supporting_text: string
  cta: string
  stats: Array<{ value: string; label: string }>
  phone_hero_title: string
  phone_buttons: string[]
}

export interface StudioPhoneMetricsAssetSummary {
  asset_id?: string
  slot: 'phone_screen' | 'iphone_frame' | 'logo'
  role: string
  description: string
  allowed_mime_types: string[]
  editable: boolean
  available: boolean
  mime_type: string | null
  sha256: string | null
  byte_count: number | null
  source: Record<string, unknown> | null
}

export interface StudioPhoneScreenHistoryItem {
  asset_id?: string
  mime_type: 'image/png'
  sha256: string
  width: number
  height: number
  byte_count: number
  source: Record<string, unknown>
  selected: boolean
}

export interface StudioTemplateSummary {
  template_id: 'universal_ad' | 'phone_metrics'
  name: string
  description: string
  canvas: { width: number; height: number }
  template_version?: number
  template_sha256?: string
  creative_direction_options?: {
    schema: 'ptw.studio.phone-hero-direction.v1'
    styles: StudioPhoneHeroStyle[]
    backgrounds: StudioPhoneHeroBackground[]
  }
}

export type StudioCreativeStatus = 'queued' | 'composing' | 'generating_image' | 'draft' | 'failed'

export interface StudioCreativeSummary {
  creative_id: string
  project_id: string
  source_brief_id: string
  ordinal: number
  origin: 'brief_generation' | 'approved_variant'
  template_id: 'universal_ad' | 'phone_metrics'
  template_version: number | null
  template_sha256: string | null
  status: StudioCreativeStatus
  state_sha256: string | null
  approved_version_count: number
  generation: {
    stage?: StudioCreativeStatus
    error_type?: string
    error_message?: string
    phone_image?: { status?: 'generating' | 'completed' | 'failed'; visual_direction?: string; error_message?: string }
    creative_direction?: StudioPhoneHeroCreativeDirection
  }
  created_at: string
  updated_at: string
}

export interface StudioLearningProposal {
  proposal_id: string
  checkpoint_id: string
  project_skill_snapshot_id: string
  global_rule: string
  global_rule_sha256: string
  decision: 'pending'
}

export interface StudioEditCheckpoint {
  checkpoint_id: string
  creative_id: string
  project_id: string
  kind: 'save' | 'approve'
  before_state_sha256: string
  after_state_sha256: string
  changed_paths: string[]
  status: 'completed' | 'queued'
  edit_summary: string
  project_lesson?: string
  error_message?: string
}

export interface StudioCheckpointResponse<T> {
  creative: T
  checkpoint_created: boolean
  version_created: boolean
  checkpoint: StudioEditCheckpoint | null
  learning_proposal: StudioLearningProposal | null
}

export interface StudioPhoneMetricsDetail {
  creative_id: string
  project_id: string
  source_brief_id: string
  ordinal: number
  origin: 'brief_generation' | 'approved_variant'
  status: StudioCreativeStatus
  generation: StudioCreativeSummary['generation']
  approved_version_count: number
  workspace_id?: string
  schema: 'ptw.studio.workspace.v8'
  template_id: 'phone_metrics'
  templates: StudioTemplateSummary[]
  catalog: {
    schema: 'ptw.studio.phone-metrics-catalog.v2'
    template_id: 'phone_metrics'
    template_version: number
    canvas: { width: 1080; height: 1350 }
    semantic_roles: string[]
    components: StudioUniversalComponentDefinition[]
    asset_slots: Record<string, { role: string; allowed_mime_types: string[]; description: string }>
    variation: {
      optional_elements: string[]
      brand: 'Natal'
      device_pose: 'front_facing_upright'
      device_rotation_degrees: number
      background_textures: StudioPhoneBackgroundTexture[]
      copy_background_textures: StudioPhoneBackgroundTexture[]
      phone_screen_textures: StudioPhoneScreenTexture[]
      metric_card_styles: StudioPhoneMetricCardStyle[]
      metric_card_shapes: StudioPhoneMetricCardShape[]
      phone_button_styles: StudioPhoneActionButtonStyle[]
      phone_button_shapes: StudioPhoneActionButtonShape[]
      font_families: StudioFontFamily[]
      typography: Record<StudioPhoneTypographyRole, {
        minimum: number; maximum: number; default: number
      }>
    }
    sha256: string
  }
  state_sha256: string
  template_sha256: string
  configuration: StudioPhoneMetricsConfiguration
  content: StudioPhoneMetricsContent
  component_settings: { sha256: string }
  assets: StudioPhoneMetricsAssetSummary[]
  phone_screen_history: StudioPhoneScreenHistoryItem[]
  pexels_available: boolean
  phone_screen_generation_available: boolean
  versions: StudioUniversalVersionSummary[]
}

export type StudioCreativeDetail = (StudioUniversalDetail | StudioPhoneMetricsDetail) & StudioCreativeSummary

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
