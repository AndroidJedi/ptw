BEGIN;

ALTER TABLE commander_outbox
  ADD COLUMN available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  ADD COLUMN last_error text;

CREATE INDEX commander_outbox_available_idx
  ON commander_outbox (available_at, created_at)
  WHERE published_at IS NULL;

COMMIT;
