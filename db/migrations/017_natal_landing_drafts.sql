BEGIN;

ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'landing_draft';

COMMIT;

BEGIN;

CREATE TABLE natal_landing_draft_sets (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  request_id uuid NOT NULL UNIQUE,
  source_laval_run_id uuid NOT NULL,
  source_thesis_id uuid,
  source_brief jsonb NOT NULL CHECK (jsonb_typeof(source_brief) = 'object'),
  recommended_template_id text NOT NULL CHECK (recommended_template_id IN ('product', 'community', 'waitlist')),
  skill_memory_feedback_ids uuid[] NOT NULL DEFAULT '{}',
  status text NOT NULL CHECK (status IN ('queued', 'populating', 'ready', 'failed')),
  population_summary text,
  population_invocation jsonb CHECK (population_invocation IS NULL OR jsonb_typeof(population_invocation) = 'object'),
  error_code text,
  error_message text,
  requested_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz
);

CREATE INDEX natal_landing_draft_sets_recent_idx
  ON natal_landing_draft_sets (source_laval_run_id, created_at DESC);

CREATE UNIQUE INDEX natal_landing_draft_sets_one_active_idx
  ON natal_landing_draft_sets ((true)) WHERE status IN ('queued', 'populating');

CREATE TABLE natal_landing_draft_snapshots (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  draft_set_id uuid NOT NULL REFERENCES natal_landing_draft_sets(entity_id),
  template_id text NOT NULL CHECK (template_id IN ('product', 'community', 'waitlist')),
  snapshot_number integer NOT NULL CHECK (snapshot_number > 0),
  parent_snapshot_id uuid REFERENCES natal_landing_draft_snapshots(entity_id),
  source_feedback_id uuid REFERENCES commander_entities(id),
  page_content jsonb NOT NULL CHECK (jsonb_typeof(page_content) = 'object'),
  page_content_sha256 text NOT NULL CHECK (length(page_content_sha256) = 64),
  preview_html text NOT NULL,
  artifact_sha256 text NOT NULL CHECK (length(artifact_sha256) = 64),
  is_current boolean NOT NULL DEFAULT true,
  application_summary text,
  invocation jsonb CHECK (invocation IS NULL OR jsonb_typeof(invocation) = 'object'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (draft_set_id, template_id, snapshot_number),
  CHECK (parent_snapshot_id IS NULL OR parent_snapshot_id <> entity_id)
);

CREATE UNIQUE INDEX natal_landing_draft_snapshots_current_idx
  ON natal_landing_draft_snapshots (draft_set_id, template_id) WHERE is_current;

ALTER TABLE natal_landing_feedback
  ADD COLUMN target_entity_id uuid REFERENCES commander_entities(id),
  ADD COLUMN draft_set_id uuid REFERENCES natal_landing_draft_sets(entity_id),
  ADD COLUMN block_id text,
  ADD COLUMN snapshot_number integer;

UPDATE natal_landing_feedback SET target_entity_id=landing_build_id;

ALTER TABLE natal_landing_feedback
  ALTER COLUMN target_entity_id SET NOT NULL,
  ALTER COLUMN landing_build_id DROP NOT NULL,
  ADD CONSTRAINT natal_landing_feedback_one_target
    CHECK ((landing_build_id IS NOT NULL) <> (draft_set_id IS NOT NULL)),
  ADD CONSTRAINT natal_landing_feedback_block_check
    CHECK (block_id IS NULL OR block_id IN ('hero', 'problem', 'features', 'steps', 'proof', 'faq', 'final_cta'));

CREATE TABLE natal_landing_draft_edits (
  request_id uuid PRIMARY KEY,
  draft_set_id uuid NOT NULL REFERENCES natal_landing_draft_sets(entity_id),
  template_id text NOT NULL CHECK (template_id IN ('product', 'community', 'waitlist')),
  base_snapshot_id uuid NOT NULL REFERENCES natal_landing_draft_snapshots(entity_id),
  block_id text NOT NULL CHECK (block_id IN ('hero', 'problem', 'features', 'steps', 'proof', 'faq', 'final_cta')),
  instruction text NOT NULL CHECK (length(btrim(instruction)) BETWEEN 1 AND 2000),
  feedback_id uuid NOT NULL UNIQUE REFERENCES commander_entities(id),
  proposal_id uuid NOT NULL UNIQUE REFERENCES commander_entities(id),
  result_snapshot_id uuid REFERENCES natal_landing_draft_snapshots(entity_id),
  status text NOT NULL CHECK (status IN ('queued', 'editing', 'completed', 'failed')),
  error_code text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz
);

CREATE UNIQUE INDEX natal_landing_draft_edits_one_active_idx
  ON natal_landing_draft_edits ((true)) WHERE status IN ('queued', 'editing');

CREATE TABLE natal_landing_skill_proposals (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  feedback_id uuid NOT NULL UNIQUE REFERENCES commander_entities(id),
  draft_set_id uuid NOT NULL REFERENCES natal_landing_draft_sets(entity_id),
  template_id text NOT NULL CHECK (template_id IN ('product', 'community', 'waitlist')),
  block_id text NOT NULL CHECK (block_id IN ('hero', 'problem', 'features', 'steps', 'proof', 'faq', 'final_cta')),
  proposed_lesson text,
  reviewed_lesson text,
  status text NOT NULL CHECK (status IN ('pending_generation', 'pending_review', 'dismissed', 'planning', 'promoted', 'failed')),
  command_session_id text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE natal_landing_builds
  ADD COLUMN source_draft_snapshot_id uuid REFERENCES natal_landing_draft_snapshots(entity_id),
  ADD COLUMN page_content jsonb,
  ADD COLUMN page_content_sha256 text,
  ADD CONSTRAINT natal_landing_builds_page_content_object
    CHECK (page_content IS NULL OR jsonb_typeof(page_content) = 'object'),
  ADD CONSTRAINT natal_landing_builds_page_content_digest
    CHECK (page_content_sha256 IS NULL OR length(page_content_sha256) = 64);

COMMIT;
