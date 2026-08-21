BEGIN;

ALTER TABLE brand_directions
  ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1
    CHECK (revision >= 1);

CREATE TABLE IF NOT EXISTS brand_logo_revisions (
  id uuid PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES brand_runs(id) ON DELETE CASCADE,
  direction_id uuid NOT NULL REFERENCES brand_directions(id) ON DELETE CASCADE,
  revision integer NOT NULL CHECK (revision >= 2),
  feedback_id uuid NOT NULL UNIQUE,
  source_creative_id uuid NOT NULL,
  source_artifact_id uuid NOT NULL,
  source_artifact_digest text NOT NULL CHECK (length(source_artifact_digest) = 64),
  source_logo_path text NOT NULL,
  status text NOT NULL CHECK (status IN ('pending','running','completed','failed')),
  attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
  input_hash text NOT NULL CHECK (length(input_hash) = 64),
  provider text NOT NULL,
  model text NOT NULL,
  actor text NOT NULL,
  creative_id uuid,
  artifact_id uuid,
  artifact_digest text CHECK (artifact_digest IS NULL OR length(artifact_digest) = 64),
  logo_path text,
  error jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(direction_id, revision)
);

CREATE INDEX IF NOT EXISTS brand_logo_revisions_run_status_idx
  ON brand_logo_revisions(run_id, status, created_at);

COMMIT;
