export type I18n<T = string> = { en: T; uk: T }
export type Page = 'overview' | 'ideas' | 'posts' | 'jobs' | 'more'

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
  pending_reviews: number
  jobs: { active: number; blocked: number; last_deploy?: string }
}

export type LavalStageStatus = 'pending' | 'running' | 'partial' | 'completed' | 'failed' | 'paused' | 'stale'
export type LavalEvidenceMode = 'demo_fixture' | 'live_search_pending_trends' | 'live_complete'

export interface LavalProviderReadiness {
  llm_provider: string
  search_provider: string
  trend_provider: string
  search_live_ready: boolean
  trends_live_ready: boolean
  demo_available: boolean
  default_evidence_mode: LavalEvidenceMode
  max_spend_usd: number
  reserved_spend_usd: number
  missing: string[]
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

export interface LavalStatus {
  run: LavalRun
  stages: LavalStage[]
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
