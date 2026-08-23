export type Page = 'positioning' | 'landing' | 'ads' | 'admin'
export type I18n<T = string> = { en: T; uk: T }

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
  privacy_policy_url: string
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
  status: string
  destructive?: boolean
  plan?: string
  plan_digest?: string
  deployment_revision?: string
}
