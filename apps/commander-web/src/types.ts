export type Page = 'briefs' | 'result'
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

export type OutputProfile = 'marketing_copy_v1' | 'instagram_static_ad_v1'
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
  task: string
  status: ResultRunStatus
  current_stage: ResultRunStage
  progress_percent: number
  maximum_minutes: 45
  error_code?: string | null
  error_message?: string | null
  final_result_id?: string | null
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
  width: 1080
  height: 1080
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
