BEGIN;

CREATE TABLE commander_session_checkpoints (
  id uuid PRIMARY KEY,
  scope text NOT NULL,
  workspace_session_id text NOT NULL,
  version integer NOT NULL CHECK (version = 1),
  payload jsonb NOT NULL,
  checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (payload->>'scope' = scope),
  CHECK (payload->>'workspace_session_id' = workspace_session_id),
  CHECK ((payload->>'version')::integer = version)
);

CREATE INDEX commander_session_checkpoints_latest_idx
  ON commander_session_checkpoints (scope, created_at DESC, id DESC);

COMMENT ON TABLE commander_session_checkpoints IS
  'Append-only bounded resume state; payload integrity is verified by Commander.';

COMMIT;
