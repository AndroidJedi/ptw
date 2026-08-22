BEGIN;

ALTER TABLE brand_runs
  ADD COLUMN IF NOT EXISTS project_version integer,
  ADD COLUMN IF NOT EXISTS create_intent text NOT NULL DEFAULT 'initial',
  ADD COLUMN IF NOT EXISTS client_request_id text;

WITH numbered AS (
  SELECT id,
         row_number() OVER (
           PARTITION BY source_laval_run_id ORDER BY created_at,id
         )::integer AS project_version
    FROM brand_runs
)
UPDATE brand_runs run
   SET project_version=numbered.project_version
  FROM numbered
 WHERE run.id=numbered.id AND run.project_version IS NULL;

ALTER TABLE brand_runs
  ALTER COLUMN project_version SET NOT NULL,
  ADD CONSTRAINT brand_runs_project_version_positive CHECK (project_version >= 1),
  ADD CONSTRAINT brand_runs_create_intent_check
    CHECK (create_intent IN ('initial','full_rebuild'));

CREATE UNIQUE INDEX IF NOT EXISTS brand_runs_project_version_unique
  ON brand_runs(source_laval_run_id,project_version);
CREATE UNIQUE INDEX IF NOT EXISTS brand_runs_create_request_unique
  ON brand_runs(source_laval_run_id,client_request_id)
  WHERE client_request_id IS NOT NULL;

ALTER TABLE brand_kits
  DROP CONSTRAINT IF EXISTS brand_kits_run_id_key,
  DROP CONSTRAINT IF EXISTS brand_kits_direction_id_key;

ALTER TABLE brand_kits
  ADD COLUMN IF NOT EXISTS source_laval_run_id uuid REFERENCES laval_runs(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS project_version integer,
  ADD COLUMN IF NOT EXISTS supersedes_kit_id uuid REFERENCES brand_kits(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS logo_creative_id uuid,
  ADD COLUMN IF NOT EXISTS logo_artifact_id uuid,
  ADD COLUMN IF NOT EXISTS logo_artifact_digest text,
  ADD COLUMN IF NOT EXISTS logo_path text;

UPDATE brand_kits kit
   SET source_laval_run_id=run.source_laval_run_id,
       project_version=run.project_version,
       logo_creative_id=direction.creative_id,
       logo_artifact_id=direction.artifact_id,
       logo_artifact_digest=direction.artifact_digest,
       logo_path=direction.logo_path
  FROM brand_runs run,brand_directions direction
 WHERE kit.run_id=run.id AND kit.direction_id=direction.id
   AND (kit.source_laval_run_id IS NULL OR kit.project_version IS NULL
        OR kit.logo_creative_id IS NULL OR kit.logo_artifact_id IS NULL
        OR kit.logo_artifact_digest IS NULL OR kit.logo_path IS NULL);

ALTER TABLE brand_kits
  ALTER COLUMN source_laval_run_id SET NOT NULL,
  ALTER COLUMN project_version SET NOT NULL,
  ALTER COLUMN logo_creative_id SET NOT NULL,
  ALTER COLUMN logo_artifact_id SET NOT NULL,
  ALTER COLUMN logo_artifact_digest SET NOT NULL,
  ALTER COLUMN logo_path SET NOT NULL,
  ADD CONSTRAINT brand_kits_project_version_positive CHECK (project_version >= 1),
  ADD CONSTRAINT brand_kits_logo_digest_check CHECK (length(logo_artifact_digest)=64);

CREATE UNIQUE INDEX IF NOT EXISTS brand_kits_project_version_unique
  ON brand_kits(source_laval_run_id,project_version);
CREATE UNIQUE INDEX IF NOT EXISTS brand_kits_one_active_per_project
  ON brand_kits(source_laval_run_id) WHERE status='approved';
CREATE INDEX IF NOT EXISTS brand_kits_project_history_idx
  ON brand_kits(source_laval_run_id,project_version DESC,approved_at DESC);

ALTER TABLE brand_logo_revisions
  ADD COLUMN IF NOT EXISTS strategy text,
  ADD COLUMN IF NOT EXISTS requested_change text,
  ADD COLUMN IF NOT EXISTS literal_text text,
  ADD COLUMN IF NOT EXISTS invariants jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS reference_used boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS reference_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS compliance jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS brand_kit_logo_revisions (
  id uuid PRIMARY KEY,
  source_laval_run_id uuid NOT NULL REFERENCES laval_runs(id) ON DELETE RESTRICT,
  base_kit_id uuid NOT NULL REFERENCES brand_kits(id) ON DELETE RESTRICT,
  proposed_project_version integer NOT NULL CHECK (proposed_project_version >= 2),
  feedback_id uuid NOT NULL UNIQUE,
  client_request_id text NOT NULL,
  source_creative_id uuid NOT NULL,
  source_artifact_id uuid NOT NULL,
  source_artifact_digest text NOT NULL CHECK (length(source_artifact_digest)=64),
  source_logo_path text NOT NULL,
  strategy text CHECK (strategy IN ('reference_edit','lettermark','new_concept')),
  requested_change text,
  literal_text text,
  invariants jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(invariants)='array'),
  structural_change boolean,
  status text NOT NULL CHECK (status IN ('pending','running','completed','failed','approved','rejected')),
  attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 2),
  input_hash text NOT NULL CHECK (length(input_hash)=64),
  provider text NOT NULL,
  model text NOT NULL,
  actor text NOT NULL,
  creative_id uuid,
  artifact_id uuid,
  artifact_digest text CHECK (artifact_digest IS NULL OR length(artifact_digest)=64),
  logo_path text,
  reference_used boolean NOT NULL DEFAULT false,
  reference_trace jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(reference_trace)='object'),
  compliance jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(compliance)='object'),
  error jsonb,
  approved_kit_id uuid REFERENCES brand_kits(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  started_at timestamptz,
  completed_at timestamptz,
  reviewed_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(source_laval_run_id,client_request_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS brand_kit_logo_revisions_one_active
  ON brand_kit_logo_revisions(source_laval_run_id)
  WHERE status IN ('pending','running','completed');
CREATE INDEX IF NOT EXISTS brand_kit_logo_revisions_history_idx
  ON brand_kit_logo_revisions(source_laval_run_id,created_at DESC);

-- A pause during a provider call used to leave the stage projection running.
-- Retain the completed provider task and reconcile only the projection; startup
-- must not resume or increment the attempt.
UPDATE brand_stage_runs stage
   SET status='paused',updated_at=clock_timestamp()
  FROM brand_runs run
 WHERE stage.run_id=run.id AND run.status='paused' AND stage.status='running';

COMMIT;
