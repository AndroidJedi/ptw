BEGIN;

ALTER TYPE commander_entity_kind ADD VALUE IF NOT EXISTS 'landing';

COMMIT;

BEGIN;

CREATE TABLE natal_landing_builds (
  entity_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  request_id uuid NOT NULL UNIQUE,
  source_laval_run_id uuid NOT NULL,
  source_thesis_id uuid,
  template_id text NOT NULL CHECK (template_id IN ('product', 'community', 'waitlist')),
  brief jsonb NOT NULL CHECK (jsonb_typeof(brief) = 'object'),
  status text NOT NULL CHECK (status IN ('queued', 'building', 'publishing', 'published', 'failed')),
  output_path text NOT NULL,
  build_manifest jsonb CHECK (build_manifest IS NULL OR jsonb_typeof(build_manifest) = 'object'),
  artifact_sha256 text CHECK (artifact_sha256 IS NULL OR length(artifact_sha256) = 64),
  firebase_site_id text NOT NULL,
  firebase_version text,
  public_url text,
  error_code text,
  error_message text,
  requested_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz
);

CREATE INDEX natal_landing_builds_recent_idx
  ON natal_landing_builds (created_at DESC);

CREATE UNIQUE INDEX natal_landing_builds_one_active_idx
  ON natal_landing_builds ((true))
  WHERE status IN ('queued', 'building', 'publishing');

COMMIT;
