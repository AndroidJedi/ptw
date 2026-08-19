ALTER TABLE commander_outbox
    ADD COLUMN IF NOT EXISTS cancelled_at timestamptz,
    ADD COLUMN IF NOT EXISTS cancel_reason text;

UPDATE commander_outbox
SET cancelled_at = clock_timestamp(),
    cancel_reason = 'outbound notifications retired on 1 GB production profile'
WHERE published_at IS NULL
  AND cancelled_at IS NULL
  AND topic LIKE 'telegram.%';

DROP INDEX IF EXISTS commander_outbox_pending_idx;
CREATE INDEX commander_outbox_pending_idx
    ON commander_outbox (available_at, created_at)
    WHERE published_at IS NULL AND cancelled_at IS NULL;
