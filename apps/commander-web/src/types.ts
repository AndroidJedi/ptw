export type I18n<T = string> = { en: T; uk: T }
export type Page = 'overview' | 'ideas' | 'branding' | 'landings' | 'jobs' | 'more'

export interface Mission {
  code: string
  name: I18n
  activated_at: string
  deadline_at: string
  status: string
}

export interface Overview {
  mission: Mission
  health: Record<string, string>
  laval_runs: { total: number; active: number; completed: number }
  branding_runs: { total: number; active: number; completed: number }
  jobs: { active: number; blocked: number; last_deploy?: string }
}

export type LavalStageStatus = 'pending' | 'running' | 'partial' | 'completed' | 'failed' | 'paused' | 'stale'
export type LavalEvidenceMode = 'demo_fixture' | 'live_search_pending_trends' | 'live_complete' | 'live_market_signals'

export interface LavalProviderReadiness {
  llm_provider: string
  search_provider: string
  trend_provider: string
  search_live_ready: boolean
  trends_live_ready: boolean
  youtube_provider?: string
  youtube_live_ready?: boolean
  demo_available: boolean
  default_evidence_mode: LavalEvidenceMode
  max_spend_usd: number
  reserved_spend_usd: number
  missing: string[]
  optional_sources?: { google_trends: { ready: boolean; required: false } }
  required_sources?: { youtube: { ready: boolean } }
}

export interface ProductMechanism {
  id: string
  name: I18n
  description: I18n
  mechanism_type: 'value' | 'behavior' | 'trust' | 'retention' | 'distribution' | 'proof'
  support_dimensions: Record<string, number>
  evidence_ids: string[]
}

export interface FalsificationReport {
  risks: Array<{ assumption_id: string; severity: 'low' | 'medium' | 'high'; supported: boolean; objection: string; counterargument: string; fatal: boolean }>
  fatal_objection?: string | null
  unsupported_high_severity_count: number
  weakest_mechanism_coverage: number
}

export interface ProductThesis extends FalsificationReport {
  id: string
  title: I18n
  target_user: I18n
  problem: I18n
  loop_steps: I18n[]
  value_moment: I18n
  zero_audience_behavior: I18n
  substitutes: I18n[]
  dangerous_assumptions: Array<{ id: string; statement: I18n; severity: 'low' | 'medium' | 'high' }>
  success_criterion: { metric: string; operator: '>='; threshold: number; sample_target: number }
  mechanism_ids: string[]
  evidence_ids: string[]
  verdict: 'survives' | 'weak' | 'rejected'
  recommended: boolean
  recommendation_reason?: string
  commander_hypothesis_id?: string
  validation_workspace_id?: string
  validation_stale?: boolean
}

export interface ThesisCollection {
  run_id: string
  status: 'ready' | 'no_surviving_thesis'
  items: ProductThesis[]
  mechanisms: ProductMechanism[]
  recommended_thesis_id?: string | null
}

export interface GraphEntity<T extends Record<string, unknown> = Record<string, unknown>> {
  id: string
  kind: string
  created_at: string
  attributes: T
}

export interface MarketProbe extends GraphEntity<{
  experiment_type: 'market_probe'
  probe_type: string
  assumption_id: string
  assumption: string
  procedure: string
  target_segment: string
  success_criterion: { metric: string; operator: '>='; threshold: number }
  sample_target: number
  duration_days: number
  budget_minor: number
  external_execution: 'manual_owner_only'
}> { status: 'proposed' | 'running' | 'completed' | 'evaluated' | 'cancelled' | 'superseded' }

export interface ValidationWorkspace {
  workspace: GraphEntity<{ hypothesis_id: string; idea_laval_run_id: string; idea_laval_thesis_id: string; status: string; external_actions_automatic: false }>
  hypothesis: GraphEntity<{ claim: string; success_criterion: { metric: string; operator: '>='; threshold: number } }>
  probes: MarketProbe[]
  observations: GraphEntity[]
  insights: GraphEntity[]
  decisions: GraphEntity<{ action: 'continue' | 'mutate' | 'pivot' | 'reject'; reasoning_summary: string }>[]
  mechanisms: GraphEntity<{ name: I18n; description: I18n; mechanism_type: string }>[]
}

export interface LavalRun {
  id: string
  owner_idea_id: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  current_stage?: string
  through_stage?: string
  approval_mode: 'manual' | 'automatic'
  approval_gates: string[]
  owner_preview?: string
  completed_stages?: number
  processed_stages?: number
  partial_stages?: number
  variant_count?: number
  error_text?: string
  created_at: string
  updated_at: string
  config: Record<string, unknown>
  evidence_mode: LavalEvidenceMode
  provider_snapshot: Record<string, string>
  max_spend_usd: number
  reserved_spend_usd: number
  awaiting_reason?: string | null
  pipeline_version?: string
}

export interface LavalStage {
  stage: string
  ordinal: number
  status: LavalStageStatus
  started_at?: string
  completed_at?: string
  input_hash?: string
  attempt: number
  provider?: string
  model?: string
  metrics: Record<string, unknown>
  error?: { type?: string; message?: string }
}

export interface LavalQualityCount {
  stage?: string
  verdict: 'verified' | 'invalid' | 'pending' | 'fixture' | 'not_applicable'
  attempted: number
  success: number
  fallback: number
  failed: number
  recovered_failures?: number
  unresolved_failures?: number
}

export interface LavalRunQuality extends LavalQualityCount {
  message: string
  missing_stages: string[]
  by_stage: LavalQualityCount[]
}

export interface LavalStatus {
  run: LavalRun
  stages: LavalStage[]
  quality?: LavalRunQuality
  cost: { items: Array<Record<string, unknown>>; total_usd: number; provider_projected_usd?: number; provider_reserved_usd?: number; provider_actual_usd?: number; max_spend_usd?: number }
  recovery?: {
    available: boolean
    stage?: string | null
    stage_status?: LavalStageStatus | null
    attempt: number
    failed_at?: string | null
    failure?: { type?: string; message?: string } | null
    provider_tasks: {
      total: number; reserved: number; submitted: number; completed: number; failed: number
      persisted_remote_ids: number; cost_recorded: number; actual_cost_usd: number
    }
    resume_behavior: {
      reuses_persisted_remote_ids: boolean
      reposts_submitted_tasks: boolean
      duplicates_recorded_cost: boolean
    }
    history: Array<{
      action: string; stage?: string; actor: string; previous_status?: string; outcome: string
      details: Record<string, unknown>; created_at: string
    }>
  }
  runner_active?: boolean
  resume_with_market_signals_available?: boolean
}

export interface BrandCandidate {
  idea_run_id: string
  owner_idea: string
  created_at: string
  theses: ProductThesis[]
  mechanisms: ProductMechanism[]
  quality: { successful: number; attempted: number }
  recommended_thesis_id?: string | null
  surviving_thesis_count: number
  active_brand_kit?: { name: string; status: 'approved' | 'superseded' | 'stale'; approved_at: string } | null
}

export type BrandRunStatus = 'pending' | 'running' | 'paused' | 'awaiting_review' | 'completed' | 'failed' | 'cancelled'

export interface BrandRun {
  id: string
  source_laval_run_id: string
  status: BrandRunStatus
  current_stage: string
  source_snapshot: { owner_idea: string; theses: ProductThesis[]; mechanisms: ProductMechanism[] }
  source_stale: boolean
  constraints_text: string
  provider_snapshot: Record<string, unknown>
  commander_brand_kit_id?: string | null
  created_at: string
  updated_at: string
  owner_preview?: string
  completed_stages?: number
  project_version?: number
  create_intent?: 'initial' | 'full_rebuild'
  logo_thumbnail_digest?: string | null
}

export interface BrandStage {
  stage: string
  ordinal: number
  status: LavalStageStatus
  attempt: number
  input_hash?: string
  provider?: string
  model?: string
  artifact?: unknown
  metrics: Record<string, unknown>
  error?: { type?: string; message?: string }
}

export interface BrandEvaluation {
  passed: boolean
  checks: Record<string, { passed: boolean; [key: string]: unknown }>
}

export interface BrandAsset {
  digest: string
  mime_type: string
  width?: number
  height?: number
  generation_provenance: {
    provider?: string
    requested_model?: string
    resolved_model?: string
    request_id?: string
    prompt?: string
  }
  url: string
  cache: 'private, no-store'
}

export interface BrandDirection {
  id: string
  ordinal: number
  revision?: number
  name: string
  status: string
  manifest: {
    name: string
    tagline: I18n
    positioning: I18n
    personality: string[]
    palette: Record<'light' | 'dark', Record<string, string>>
    typography: { display: string; body: string; mono: string }
    design_principles: string[]
    retention_patterns: string[]
    ui_system: Record<string, unknown>
  }
  evaluation: BrandEvaluation
  artifact_digest?: string
  logo_asset?: BrandAsset
  latest_feedback_id?: string | null
  feedback_type?: string | null
  review_state?: 'pending' | 'changes_requested' | 'approved'
  regeneration_id?: string | null
  regeneration_status?: 'pending' | 'running' | 'completed' | 'failed' | null
  regeneration_feedback_id?: string | null
  regeneration_error?: { type?: string; message?: string } | null
  regeneration_strategy?: 'reference_edit' | 'lettermark' | 'new_concept' | null
  regeneration_reference_used?: boolean | null
  regeneration_compliance?: { passed?: boolean; reason?: string; [key: string]: unknown } | null
  regeneration_verification?: 'verified' | 'failed_compliance' | 'legacy_unverified'
  regeneration_requested_at?: string | null
  regeneration_completed_at?: string | null
  rating?: number | null
  overall_comment?: string | null
  annotations?: Region[]
  reviewed_at?: string | null
}

export interface BrandReview {
  feedback_id: string
  rating?: number | null
  overall_comment: string
  annotations: Region[]
  supersedes_feedback_id?: string | null
  created_at: string
}

export interface BrandKit {
  id: string
  commander_brand_kit_id: string
  name: string
  status: 'approved' | 'superseded' | 'stale'
  zip_digest: string
  source_stale: boolean
  approved_at: string
  project_version?: number
  run_id?: string
  logo_artifact_digest?: string
  logo_asset?: BrandAsset
  manifest: BrandDirection['manifest'] & Record<string, unknown>
  download?: { digest: string; mime_type: 'application/zip'; url: string; cache: 'private, no-store' }
}

export interface BrandLogoRevision {
  id: string
  source_laval_run_id: string
  base_kit_id: string
  proposed_project_version: number
  client_request_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'approved' | 'rejected'
  attempt: number
  strategy?: 'reference_edit' | 'lettermark' | 'new_concept' | null
  requested_change?: string | null
  feedback?: string | null
  literal_text?: string | null
  structural_change?: boolean | null
  reference_used: boolean
  reference_trace: Record<string, unknown>
  compliance: { passed?: boolean; reason?: string; [key: string]: unknown }
  error?: { type?: string; message?: string } | null
  before_asset?: BrandAsset
  after_asset?: BrandAsset
  created_at: string
  completed_at?: string | null
}

export interface BrandProjectVersion {
  kind: 'run' | 'logo_revision' | 'kit'
  version: number
  status: string
  run_id?: string
  revision_id?: string
  kit_id?: string
  logo_thumbnail_digest?: string | null
  created_at: string
  updated_at: string
}

export interface BrandProject {
  id: string
  status: 'active' | 'draft' | 'revision_running' | 'revision_review'
  source_idea: { run_id: string; owner_idea: string; created_at: string }
  active_kit?: BrandKit | null
  kits: BrandKit[]
  runs: BrandRun[]
  logo_revisions: BrandLogoRevision[]
  versions: BrandProjectVersion[]
  created_at: string
  updated_at: string
}

export interface BrandStatus {
  run: BrandRun
  stages: BrandStage[]
  directions: BrandDirection[]
  cost: { items: Array<Record<string, unknown>>; total_usd: number }
  runner_active?: boolean
}

export interface LandingFeature {
  title: string
  description: string
}

export interface LandingBrief {
  schema_version: 1
  brand: 'Natal'
  language: 'uk' | 'en'
  source: { laval_run_id: string; thesis_id?: string }
  business_idea: string
  target_audience: string
  pain: string
  promise: string
  key_features: LandingFeature[]
  steps: LandingFeature[]
  proof_points: string[]
  faq: Array<{ question: string; answer: string }>
  cta: { label: string; url: string }
}

export interface LandingTemplate {
  id: 'product' | 'community' | 'waitlist'
  version: number
  name: I18n
  description: I18n
  best_for: string[]
  adapted_from: string
}

export interface LandingCandidate {
  idea_run_id: string
  recommended_template_id: LandingTemplate['id']
  brief: LandingBrief
  quality: { successful?: number; attempted?: number }
  verdict?: 'survives' | 'weak' | 'rejected' | null
}

export type LandingBuildStatus = 'queued' | 'building' | 'publishing' | 'published' | 'failed'

export interface LandingBuild {
  id: string
  request_id: string
  idea_run_id: string
  thesis_id?: string | null
  template_id: LandingTemplate['id']
  brief: LandingBrief
  status: LandingBuildStatus
  build_manifest?: Record<string, unknown> | null
  artifact_sha256?: string | null
  firebase_site_id: string
  firebase_version?: string | null
  public_url?: string | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
}

export interface Creative {
  uuid: string
  artifact_digest: string
  image_url: string
  title: I18n
  batch_id?: string
  position?: number
  review_status: string
  latest_feedback_id?: string
  rating?: number
  predicted_ctr?: number
  reviewed_at?: string
}

export interface Job {
  id: string
  mode: 'plan' | 'execute'
  title: string
  status: string
  plan_digest?: string
  plan?: string
  created_at: string
  deployment_revision?: string
  destructive?: boolean
}

export type Region =
  | { id: string; kind: 'pin'; x: number; y: number; comment: string }
  | { id: string; kind: 'rectangle'; x: number; y: number; width: number; height: number; comment: string }
  | { id: string; kind: 'freehand'; points: Array<{ x: number; y: number }>; comment: string }
