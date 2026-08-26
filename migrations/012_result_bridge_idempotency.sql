ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS structured_idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS jobs_structured_idempotency_key_idx
    ON jobs (structured_idempotency_key)
    WHERE type = 'llm_structured' AND structured_idempotency_key IS NOT NULL;
