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
  idea_score_trend: Array<{ generation: number; best: number; average: number }>
  pending_reviews: number
  jobs: { active: number; blocked: number; last_deploy?: string }
}

export interface Idea {
  id: number
  generation: number
  mode: string
  score?: number
  title: I18n
  one_liner: I18n
  details: Record<string, I18n<string | string[]>>
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
