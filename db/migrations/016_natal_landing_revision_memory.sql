BEGIN;

ALTER TABLE natal_landing_builds
  DROP CONSTRAINT natal_landing_builds_status_check;

ALTER TABLE natal_landing_builds
  ADD CONSTRAINT natal_landing_builds_status_check
    CHECK (status IN ('queued', 'revising', 'building', 'publishing', 'published', 'failed')),
  ADD COLUMN parent_build_id uuid REFERENCES natal_landing_builds(entity_id),
  ADD COLUMN revision_number integer,
  ADD COLUMN input_brief jsonb,
  ADD COLUMN skill_memory_feedback_ids uuid[] NOT NULL DEFAULT '{}',
  ADD COLUMN revision_summary text,
  ADD COLUMN revision_invocation jsonb;

DROP INDEX natal_landing_builds_one_active_idx;
CREATE UNIQUE INDEX natal_landing_builds_one_active_idx
  ON natal_landing_builds ((true))
  WHERE status IN ('queued', 'revising', 'building', 'publishing');

WITH numbered AS (
  SELECT entity_id,
         row_number() OVER (
           PARTITION BY source_laval_run_id ORDER BY created_at, entity_id
         ) AS revision_number
  FROM natal_landing_builds
)
UPDATE natal_landing_builds build
SET revision_number=numbered.revision_number,
    input_brief=build.brief
FROM numbered
WHERE numbered.entity_id=build.entity_id;

ALTER TABLE natal_landing_builds
  ALTER COLUMN revision_number SET NOT NULL,
  ALTER COLUMN input_brief SET NOT NULL;

ALTER TABLE natal_landing_builds
  ADD CONSTRAINT natal_landing_builds_revision_unique
    UNIQUE (source_laval_run_id, revision_number),
  ADD CONSTRAINT natal_landing_builds_parent_not_self
    CHECK (parent_build_id IS NULL OR parent_build_id <> entity_id),
  ADD CONSTRAINT natal_landing_builds_input_brief_object
    CHECK (jsonb_typeof(input_brief) = 'object'),
  ADD CONSTRAINT natal_landing_builds_revision_invocation_object
    CHECK (revision_invocation IS NULL OR jsonb_typeof(revision_invocation) = 'object');

CREATE TABLE natal_landing_feedback (
  feedback_id uuid PRIMARY KEY REFERENCES commander_entities(id),
  landing_build_id uuid NOT NULL REFERENCES natal_landing_builds(entity_id),
  source_laval_run_id uuid NOT NULL,
  template_id text NOT NULL CHECK (template_id IN ('product', 'community', 'waitlist')),
  comment text NOT NULL CHECK (length(btrim(comment)) BETWEEN 1 AND 2000),
  artifact_sha256 text NOT NULL CHECK (length(artifact_sha256) = 64),
  requested_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX natal_landing_feedback_memory_idx
  ON natal_landing_feedback (source_laval_run_id, created_at, feedback_id);

COMMIT;
